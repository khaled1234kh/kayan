"""TrustGate enforcement for the new AI agents.

Reuses the project's existing ``integration.trustgate_client.TrustGateClient``
so the policy payload and fail-closed semantics stay identical to the legacy
runtime. Every model inference and evidence write is an authorization request;
an LLM response never grants itself authority.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from integration.trustgate_client import TrustGateClient

from ..config import TrustGateClientConfig, require_local_http

# These are the Gate's canonical technique/capability names (see policy.rs).
INFERENCE_TECHNIQUE = "planning"
INFERENCE_ACTION = "llm_inference"
REPORT_TECHNIQUE = "reporting"
REPORT_ACTION = "write_report"
ROE_TARGET = "127.0.0.1"


@dataclass(frozen=True)
class TrustGateDecision:
    agent: str
    action: str
    allowed: bool
    decision: str
    reason: str
    policy_id: str | None
    audit_entry_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "action": self.action,
            "allowed": self.allowed,
            "decision": self.decision,
            "reason": self.reason,
            "policy_id": self.policy_id,
            "audit_entry_id": self.audit_entry_id,
        }


class AITrustGate:
    def __init__(self, config: TrustGateClientConfig) -> None:
        self.config = config
        require_local_http(config.base_url)
        self._client = TrustGateClient(config.base_url, trust_env=False)

    async def authorize(
        self,
        *,
        engagement_id: str,
        agent_id: str,
        agent_role: str,
        action: str,
        target: str = ROE_TARGET,
        technique: str = INFERENCE_TECHNIQUE,
        tool_args: dict[str, Any] | None = None,
        untrusted: bool = False,
    ) -> TrustGateDecision:
        """Authorize one agent action. Fails closed on any transport error."""
        result = await asyncio.to_thread(
            self._client.authorize,
            engagement_id,
            agent_id,
            agent_role,
            action,
            tool_args or {},
            target,
            technique,
            {"target": "trusted", "body": "untrusted" if untrusted else "trusted"},
        )
        return TrustGateDecision(
            agent=agent_id,
            action=action,
            allowed=result.allowed,
            decision=result.decision,
            reason=result.reason,
            policy_id=result.policy_id,
            audit_entry_id=result.audit_entry_id,
        )

    async def require(self, **kwargs: Any) -> TrustGateDecision:
        decision = await self.authorize(**kwargs)
        if not decision.allowed:
            raise PermissionError(
                f"TrustGate denied {kwargs.get('action')} for "
                f"{kwargs.get('agent_id')}: {decision.reason}"
            )
        return decision

    def close(self) -> None:
        self._client.close()
