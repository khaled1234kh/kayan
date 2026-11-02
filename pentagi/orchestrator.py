"""Engagement orchestrator — coordinates multiple agents against a target.

Every agent's tool calls pass through TrustGate before execution.
"""

import uuid
import json
import sys
import os
import time
import httpx
from typing import Any, Dict, List
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integration.trustgate_client import TrustGateClient
from integration.roe_signing import sign_roe
from pentagi.agents.recon_agent import ReconAgent
from pentagi.agents.webapp_agent import WebAppAgent
from pentagi.agents.network_agent import NetworkAgent
from pentagi.agents.reporting_agent import ReportingAgent


class EngagementOrchestrator:
    """Orchestrates a multi-agent pentesting engagement.

    All tool calls from all agents pass through TrustGate.
    """

    def __init__(self, trustgate_url: str = "http://127.0.0.1:8000",
                 console_url: str = "http://127.0.0.1:8001", grounding_enabled: bool = True):
        self.trustgate = TrustGateClient(base_url=trustgate_url)
        self.engagement_id: str = ""
        self.agents: List = []
        self.findings: List[Dict] = []
        self.start_time: str = ""
        self.end_time: str = ""
        self.console_url = console_url.rstrip("/")
        self._console = httpx.Client(timeout=2.0)
        self.last_console_error = None
        self.transcript: List[Dict] = []
        self.agent_states: Dict[str, Dict] = {}
        self.status = "waiting"
        self.roe: Dict = {}
        self.policy: Dict = {}
        self.target = ""
        self.report = None
        self.reporting_agent = None
        self.grounding_enabled = grounding_enabled

    def create_engagement(
        self,
        authorized_by: str,
        targets: List[str],
        allowed_techniques: List[str],
        forbidden_actions: List[str] = None,
        engagement_id: str = None,
    ) -> str:
        """Create a new engagement with an ROE contract."""
        import hashlib

        engagement_id = engagement_id or str(uuid.uuid4())
        self.engagement_id = engagement_id

        import json as _json

        # Build ROE contract with Rust-compatible serialization order
        scope_obj = {
            "targets": targets,
            "allowed_techniques": allowed_techniques,
            "forbidden_actions": forbidden_actions or [],
        }
        time_obj = {
            "start": datetime.utcnow().isoformat(),
            "end": "2099-12-31T23:59:59",
        }

        # Rust serde serializes in struct field order (not sorted)
        scope_json = '{"targets":' + _json.dumps(targets, separators=(',', ':')) + ',"allowed_techniques":' + _json.dumps(allowed_techniques, separators=(',', ':')) + ',"forbidden_actions":' + _json.dumps(forbidden_actions or [], separators=(',', ':')) + '}'
        time_json = '{"start":"' + time_obj["start"] + '","end":"' + time_obj["end"] + '"}'

        canonical = f"{engagement_id}:{authorized_by}:{scope_json}:{time_json}"
        signature = hashlib.sha256(canonical.encode()).hexdigest()

        roe = {
            "engagement_id": engagement_id,
            "authorized_by": authorized_by,
            "scope": scope_obj,
            "time_window": time_obj,
            "signature": signature,
        }
        roe["signature"] = sign_roe(roe)

        # Load ROE into TrustGate
        result = self.trustgate.load_roe(roe)
        print(f"ROE loaded: {result}")
        self.roe = {**scope_obj, "time_window": time_obj, "authorized_by": authorized_by}
        self.policy = {"rules_compiled": result.get("rules_compiled"), "engine": "Cedar 4.14 (Rust/Axum)"}
        self.findings = []
        self.transcript = []
        self.agent_states = {}
        self.end_time = ""
        self.target = ""
        self.report = None

        # Create agents based on allowed techniques
        self.agents = []
        if "recon" in allowed_techniques:
            self.agents.append(ReconAgent(engagement_id, self.trustgate))
        if "web-app" in allowed_techniques:
            self.agents.append(WebAppAgent(engagement_id, self.trustgate))
        if "network" in allowed_techniques:
            self.agents.append(NetworkAgent(engagement_id, self.trustgate))

        self.reporting_agent = ReportingAgent(engagement_id)
        for agent in [*self.agents, self.reporting_agent]:
            agent.grounding_enabled = self.grounding_enabled
            self.agent_states[agent.agent_id] = {
                "agent_id": agent.agent_id, "name": agent.role.replace("_agent", ""),
                "role": agent.role, "status": "idle", "current_task": None,
                "task_id": None, "activity": "Standing by", "findings_count": 0,
                "model_tier": agent.model_tier, "model_name": agent.model_name,
                "capability_contract": agent.capability_contract,
            }
        for agent in self.agents:
            agent.event_sink = self._record_activity

        self.start_time = datetime.utcnow().isoformat()
        self.status = "ready"
        self._push_console_state()
        return engagement_id

    def run(self, target: str) -> Dict:
        """Run all agents against the target."""
        print(f"\n{'='*60}")
        print(f"Starting engagement: {self.engagement_id}")
        print(f"Target: {target}")
        print(f"Agents: {[a.role for a in self.agents]}")
        print(f"{'='*60}\n")

        if not self.engagement_id or not self.reporting_agent:
            raise RuntimeError("create_engagement must be called before run")
        self.target = target
        self.status = "active"
        agent = None
        try:
            for agent in self.agents:
                print(f"\n--- Running {agent.role} ---")
                self._record_activity(agent, "agent_started", "", f"Starting {agent.role}", {})
                findings = agent.run(target)
                for finding in findings:
                    finding["id"] = f"{self.engagement_id}:finding:{len(self.findings) + 1}"
                    self.findings.append(finding)
                    self._record_activity(agent, "finding", "", f"Reported {finding['type']} ({finding.get('mitre', 'unmapped')})", {
                        "finding_id": finding["id"], "finding": finding,
                    })
                self.agent_states[agent.agent_id]["findings_count"] = len(findings)
                self._record_activity(agent, "agent_completed", "", f"{agent.role} completed: {len(findings)} reported findings", {})
                print(f"  Findings: {len(findings)}")
                print(f"  Allowed actions: {len(agent.get_allowed_actions())}")
                print(f"  Denied actions: {len(agent.get_denied_actions())}")

            agent = self.reporting_agent
            self._record_activity(agent, "agent_started", "report", "Generating engagement report", {})
            report = agent.generate_report(self.findings, target, self.engagement_id)
            self._record_activity(agent, "context_prepared", "report", "Prepared reporting skill and grounding context", {
                "call_context": agent.last_call_context,
            })
            json_path, md_path = agent.save_report(report, "reports")
            print(f"  JSON report: {json_path}")
            print(f"  Markdown report: {md_path}")
            self.report = report
            self.end_time = datetime.utcnow().isoformat()
            self.status = "completed"
            self._record_activity(agent, "agent_completed", "report", "Report saved", {
                "json_path": str(json_path), "markdown_path": str(md_path),
            })
            return report
        except Exception as exc:
            self.status = "failed"
            self.end_time = datetime.utcnow().isoformat()
            if agent:
                self._record_activity(agent, "agent_error", "", str(exc), {})
            else:
                self._push_console_state()
            raise

    def generate_report(self, target: str) -> Dict:
        """Generate a summary report of the engagement."""
        total_allowed = sum(len(a.get_allowed_actions()) for a in self.agents)
        total_denied = sum(len(a.get_denied_actions()) for a in self.agents)

        report = {
            "engagement_id": self.engagement_id,
            "target": target,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "agents": [a.role for a in self.agents],
            "total_findings": len(self.findings),
            "total_allowed_actions": total_allowed,
            "total_denied_actions": total_denied,
            "findings": self.findings,
            "denied_actions": [a.get_denied_actions() for a in self.agents],
            "mitre_coverage": self._compute_mitre_coverage(),
        }

        # Save report
        report_path = f"engagement_report_{self.engagement_id[:8]}.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nReport saved to: {report_path}")

        return report

    def _compute_mitre_coverage(self) -> Dict:
        """Compute MITRE ATT&CK technique coverage."""
        techniques = set()
        for finding in self.findings:
            if "mitre" in finding:
                techniques.add(finding["mitre"])
        for agent in self.agents:
            techniques.update(getattr(agent, "mitre_techniques", []))

        # Known techniques in our lab
        known_techniques = {
            "T1595": "Active Scanning",
            "T1592": "Gather Victim Host Information",
            "T1590": "Gather Victim Network Information",
            "T1190": "Exploit Public-Facing Application",
            "T1059": "Command and Scripting Interpreter",
        }

        covered = {t: known_techniques.get(t, "Unknown") for t in techniques if t in known_techniques}
        return {
            "covered_techniques": covered,
            "coverage_count": len(covered),
            "total_known": len(known_techniques),
            "coverage_pct": round(len(covered) / len(known_techniques) * 100, 1),
        }

    def _record_activity(self, agent, kind, task_id, content, details):
        """Capture tool observations, not synthetic agent conversations or reasoning."""
        view = self.agent_states[agent.agent_id]
        view["activity"] = content
        if kind in ("authorization_requested", "tool_started", "agent_started"):
            view.update(status="working", current_task=details.get("tool_name", content),
                        task_id=task_id or None)
        elif kind in ("tool_result", "tool_denied", "agent_completed", "agent_error"):
            status = {"tool_result": "working", "tool_denied": "blocked",
                      "agent_completed": "completed", "agent_error": "blocked"}[kind]
            view.update(status=status, current_task=None, task_id=None)
        self.transcript.append({
            "id": uuid.uuid4().hex, "timestamp": int(time.time() * 1000),
            "engagement_id": self.engagement_id, "seq": len(self.transcript) + 1,
            "type": "llm_call" if kind.startswith("llm_") else "finding" if kind == "finding" else "tool_call" if kind.startswith(("tool_", "authorization_")) else "status_change",
            "model_tier": agent.model_tier, "model_name": agent.model_name,
            "task_summary": content, "trustgate_decision": details.get("decision", "").lower() or None,
            "trustgate_reason": details.get("reason"), "finding_id": details.get("finding_id"),
            "agent_id": agent.agent_id, "agent_role": agent.role,
            "kind": kind, "task_id": task_id or None, "content": content, **details,
        })
        self._push_console_state()

    def _push_console_state(self):
        """Publish a recoverable full snapshot; console failure cannot allow a tool."""
        if not self.console_url:
            return
        state = {
            "engagement_id": self.engagement_id, "status": self.status,
            "execution_engine": getattr(self, "execution_engine", "deterministic_baseline"),
            "target": self.target, "start_time": self.start_time, "end_time": self.end_time,
            "agents": list(self.agent_states.values()), "findings": self.findings,
            "denials": [{**d, "agent_id": a.agent_id, "agent_role": a.role}
                        for a in self.agents for d in a.get_denied_actions()],
            "roe": self.roe, "policy": self.policy, "transcript": self.transcript,
            "transcript_retention": "full engagement", "grounding_enabled": self.grounding_enabled,
        }
        try:
            self._console.post(f"{self.console_url}/engagement/update", json=state).raise_for_status()
            self.last_console_error = None
        except httpx.HTTPError as exc:
            if self.last_console_error is None:
                print(f"Console update unavailable: {exc}")
            self.last_console_error = str(exc)

    def close(self):
        self.trustgate.close()
        self._console.close()
