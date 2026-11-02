"""Reconnaissance agent — passive/active enumeration.

Maps to MITRE ATT&CK: Reconnaissance (TA0043) and Discovery (TA0007).
"""

import uuid
import httpx
from typing import Any, Dict, List
from .base_agent import BaseAgent
from ..host_utils import extract_host


class ReconAgent(BaseAgent):
    """Reconnaissance agent for target enumeration."""

    def __init__(self, engagement_id: str, trustgate):
        super().__init__(
            agent_id=f"recon-{uuid.uuid4().hex[:8]}",
            role="recon_agent",
            engagement_id=engagement_id,
            trustgate=trustgate,
        )
        self.mitre_techniques = [
            "T1595",  # Active Scanning
            "T1592",  # Gather Victim Host Information
            "T1590",  # Gather Victim Network Information
        ]

    def run(self, target: str) -> List[Dict]:
        """Run reconnaissance against a target."""
        findings = []
        host = extract_host(target)

        # 1. Port scan (simulated — HTTP probe)
        result = self.execute_tool(
            tool_name="port_scan",
            tool_args={"target": target, "ports": "80,443,8080,8888"},
            target=host,
            technique="recon",
            provenance={"target": "trusted", "ports": "trusted"},
            executor_fn=lambda args: self._probe_ports(args["target"], args["ports"]),
        )
        if result["allowed"] and result["result"]:
            findings.append({
                "type": "open_ports",
                "agent": self.role,
                "target": target,
                "data": result["result"],
                "mitre": "T1595",
            })

        # 2. Service detection (HTTP banner grab)
        result = self.execute_tool(
            tool_name="service_scan",
            tool_args={"target": target, "path": "/"},
            target=host,
            technique="recon",
            provenance={"target": "trusted", "path": "trusted"},
            executor_fn=lambda args: self._grab_banner(args["target"], args["path"]),
        )
        if result["allowed"] and result["result"]:
            findings.append({
                "type": "service_banner",
                "agent": self.role,
                "target": target,
                "data": result["result"],
                "mitre": "T1592",
            })

        # 3. API endpoint discovery
        result = self.execute_tool(
            tool_name="web_crawl",
            tool_args={"target": target, "paths": ["/", "/api/users", "/api/products", "/login", "/search", "/ping", "/file", "/fetch"]},
            target=host,
            technique="recon",
            provenance={"target": "trusted", "paths": "trusted"},
            executor_fn=lambda args: self._crawl_endpoints(args["target"], args["paths"]),
        )
        if result["allowed"] and result["result"]:
            findings.append({
                "type": "discovered_endpoints",
                "agent": self.role,
                "target": target,
                "data": result["result"],
                "mitre": "T1590",
            })

        self.findings = findings
        return findings

    def _probe_ports(self, target: str, ports: str) -> dict:
        """Probe common ports on the target."""
        open_ports = []
        for port in ports.split(","):
            port = port.strip()
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                host = target.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0]
                result = sock.connect_ex((host, int(port)))
                sock.close()
                if result == 0:
                    open_ports.append(int(port))
            except Exception:
                pass
        return {"open_ports": open_ports}

    def _grab_banner(self, target: str, path: str) -> dict:
        """Grab HTTP banner from target."""
        try:
            resp = httpx.get(f"{target}{path}", timeout=5.0)
            return {
                "status_code": resp.status_code,
                "server": resp.headers.get("server", "unknown"),
                "content_type": resp.headers.get("content-type", "unknown"),
            }
        except Exception as e:
            return {"error": str(e)}

    def _crawl_endpoints(self, target: str, paths: list) -> dict:
        """Crawl common endpoints on the target."""
        endpoints = []
        for path in paths:
            try:
                resp = httpx.get(f"{target}{path}", timeout=5.0)
                endpoints.append({
                    "path": path,
                    "status_code": resp.status_code,
                    "content_length": len(resp.text),
                })
            except Exception as e:
                endpoints.append({"path": path, "error": str(e)})
        return {"endpoints": endpoints}
