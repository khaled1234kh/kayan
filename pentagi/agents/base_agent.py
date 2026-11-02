"""Base agent class for pentesting agents."""

import uuid
import json
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod

from integration.trustgate_client import TrustGateClient, AuthorizationResult
from pentagi.agent_config import agent_config
from pentagi.call_context import prepare_context


class BaseAgent(ABC):
    """Base class for all pentesting agents.

    Every tool call goes through TrustGate before execution.
    """

    def __init__(self, agent_id: str, role: str, engagement_id: str, trustgate: TrustGateClient):
        self.agent_id = agent_id
        self.role = role
        self.engagement_id = engagement_id
        self.trustgate = trustgate
        self.findings: List[Dict] = []
        self.denied_actions: List[Dict] = []
        self.allowed_actions: List[Dict] = []
        self.event_sink = None
        self.capability_contract = agent_config(role)
        self.model_tier = self.capability_contract["model_tier"]
        self.model_name = self.capability_contract["model_name"]
        self.grounding_enabled = False
        self.last_call_context = None

    def _activity(self, kind: str, task_id: str, content: str, **details):
        """Report observed execution facts; this never authorizes an action."""
        if self.event_sink:
            self.event_sink(self, kind, task_id, content, details)

    def authorize_tool_call(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        target: str,
        technique: str,
        provenance: Optional[Dict[str, str]] = None,
    ) -> AuthorizationResult:
        """Request authorization from TrustGate before executing a tool."""
        return self.trustgate.authorize(
            engagement_id=self.engagement_id,
            agent_id=self.agent_id,
            agent_role=self.role,
            tool_name=tool_name,
            tool_args=tool_args,
            target=target,
            technique=technique,
            provenance=provenance or {},
        )

    def execute_tool(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        target: str,
        technique: str,
        provenance: Optional[Dict[str, str]] = None,
        executor_fn=None,
    ) -> Dict[str, Any]:
        """Execute a tool call through TrustGate.

        Returns a dict with: allowed, result, reason, audit_entry_id.
        """
        task_id = f"tool-{uuid.uuid4().hex}"
        details = {"tool_name": tool_name, "target": target, "technique": technique,
                   "tool_args": tool_args, "tool_args_summary": json.dumps(tool_args, ensure_ascii=False, default=str)}
        self.last_call_context = prepare_context(self.role, f"{tool_name.replace('_', ' ')} {technique} {tool_args}",
                                                 self.capability_contract, self.grounding_enabled)
        self._activity("context_prepared", task_id, f"Prepared {self.model_tier}-tier operation context for {tool_name}",
                       **details, call_context=self.last_call_context)
        self._activity("authorization_requested", task_id,
                       f"Requesting authorization: {tool_name} on {target}", **details)
        auth = self.authorize_tool_call(tool_name, tool_args, target, technique, provenance)
        decision = {**details, "decision": auth.decision, "reason": auth.reason,
                    "policy_id": auth.policy_id, "audit_entry_id": auth.audit_entry_id}
        self._activity("authorization_decision", task_id,
                       f"{auth.decision}: {tool_name} — {auth.reason}", **decision)

        if not auth.allowed:
            self.denied_actions.append({
                "tool": tool_name,
                "args": tool_args,
                "target": target,
                "technique": technique,
                "reason": auth.reason,
                "audit_entry_id": auth.audit_entry_id,
            })
            self._activity("tool_denied", task_id,
                           f"Skipped {tool_name}: {auth.reason}", **decision)
            return {
                "allowed": False,
                "result": None,
                "reason": auth.reason,
                "audit_entry_id": auth.audit_entry_id,
            }

        # Execute the tool
        self._activity("tool_started", task_id, f"Executing {tool_name} on {target}", **details)
        result = None
        if executor_fn:
            try:
                result = executor_fn({**tool_args, "_kayan_context": self.last_call_context})
            except Exception as e:
                result = {"error": str(e)}

        self.allowed_actions.append({
            "tool": tool_name,
            "args": tool_args,
            "target": target,
            "technique": technique,
            "result": result,
        })
        rendered = json.dumps(result, ensure_ascii=False, default=str)
        truncated = len(rendered) > 4000
        self._activity("tool_result", task_id,
                       f"{tool_name}: {rendered[:4000]}" + (" [truncated]" if truncated else ""),
                       **details, truncated=truncated,
                       result=result,
                       error=isinstance(result, dict) and "error" in result)

        return {
            "allowed": True,
            "result": result,
            "reason": auth.reason,
            "audit_entry_id": auth.audit_entry_id,
        }

    @abstractmethod
    def run(self, target: str) -> List[Dict]:
        """Run the agent against a target. Returns findings."""
        pass

    def get_findings(self) -> List[Dict]:
        return self.findings

    def get_denied_actions(self) -> List[Dict]:
        return self.denied_actions

    def get_allowed_actions(self) -> List[Dict]:
        return self.allowed_actions
