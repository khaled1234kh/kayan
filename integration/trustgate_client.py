"""Thin HTTP client for TrustGate authorization.

Used by the pentesting agents to check if a tool call is authorized
before executing it.
"""

import httpx
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class AuthorizationResult:
    allowed: bool
    decision: str
    reason: str
    policy_id: Optional[str] = None
    audit_entry_id: str = ""


class TrustGateClient:
    """HTTP client for the TrustGate policy enforcement service."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=10.0)

    def authorize(
        self,
        engagement_id: str,
        agent_id: str,
        agent_role: str,
        tool_name: str,
        tool_args: Dict[str, Any],
        target: str,
        technique: str,
        provenance: Optional[Dict[str, str]] = None,
    ) -> AuthorizationResult:
        """Request authorization for a tool call."""
        payload = {
            "engagement_id": engagement_id,
            "agent_id": agent_id,
            "agent_role": agent_role,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "target": target,
            "technique": technique,
            "provenance": provenance or {},
        }

        try:
            resp = self._client.post(f"{self.base_url}/authorize", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return AuthorizationResult(
                allowed=data["decision"] == "ALLOW",
                decision=data["decision"],
                reason=data["reason"],
                policy_id=data.get("policy_id"),
                audit_entry_id=data.get("audit_entry_id", ""),
            )
        except httpx.HTTPError as e:
            # Fail closed: if TrustGate is unreachable, deny
            return AuthorizationResult(
                allowed=False,
                decision="DENY",
                reason=f"TrustGate unreachable: {e}",
            )

    def load_roe(self, roe_contract: dict) -> dict:
        """Load an ROE contract into TrustGate."""
        resp = self._client.post(f"{self.base_url}/roe/load", json=roe_contract)
        resp.raise_for_status()
        return resp.json()

    def get_audit_entries(self, limit: int = 100) -> list:
        """Read audit log entries."""
        resp = self._client.get(f"{self.base_url}/audit", params={"limit": limit})
        resp.raise_for_status()
        return resp.json().get("entries", [])

    def verify_audit_chain(self) -> dict:
        """Verify audit log hash chain integrity."""
        resp = self._client.get(f"{self.base_url}/audit/verify")
        resp.raise_for_status()
        return resp.json()

    def health(self) -> dict:
        """Check TrustGate health."""
        resp = self._client.get(f"{self.base_url}/health")
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._client.close()


# Global singleton
trustgate_client = TrustGateClient()
