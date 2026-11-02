"""Network scanning agent — port scanning and service detection.

Maps to MITRE ATT&CK: Discovery (TA0007), Reconnaissance (TA0043).
"""

import uuid
import socket
import asyncio
from typing import Any, Dict, List
from pentagi.agents.base_agent import BaseAgent
from pentagi.host_utils import extract_host


class NetworkAgent(BaseAgent):
    """Network scanning agent for port and service discovery."""

    COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 143, 443, 993, 995, 3306, 3389, 5432, 8080, 8443, 8888]

    def __init__(self, engagement_id: str, trustgate):
        super().__init__(
            agent_id=f"network-{uuid.uuid4().hex[:8]}",
            role="network_agent",
            engagement_id=engagement_id,
            trustgate=trustgate,
        )
        self.mitre_techniques = [
            "T1046",  # Network Service Discovery
            "T1595",  # Active Scanning
        ]

    def run(self, target: str) -> List[Dict]:
        findings = []
        host = extract_host(target)

        # 1. TCP port scan
        result = self.execute_tool(
            tool_name="port_scan",
            tool_args={"target": host, "ports": ",".join(str(p) for p in self.COMMON_PORTS)},
            target=host,
            technique="network",
            provenance={"target": "trusted", "ports": "trusted"},
            executor_fn=lambda args: self._tcp_scan(args["target"], [int(p) for p in args["ports"].split(",")]),
        )
        if result["allowed"] and result["result"]:
            findings.append({
                "type": "open_ports",
                "agent": self.role,
                "target": target,
                "data": result["result"],
                "mitre": "T1046",
            })

        # 2. Service banner grab on open ports
        open_ports = result["result"].get("open_ports", []) if result["allowed"] and result["result"] else []
        if open_ports:
            result = self.execute_tool(
                tool_name="service_scan",
                tool_args={"target": host, "ports": open_ports},
                target=host,
                technique="network",
                provenance={"target": "trusted", "ports": "trusted"},
                executor_fn=lambda args: self._grab_banners(args["target"], args["ports"]),
            )
            if result["allowed"] and result["result"]:
                findings.append({
                    "type": "service_banners",
                    "agent": self.role,
                    "target": target,
                    "data": result["result"],
                    "mitre": "T1595",
                })

        self.findings = findings
        return findings

    def _tcp_scan(self, host: str, ports: List[int]) -> dict:
        """Perform TCP connect scan on given ports."""
        open_ports = []
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                result = sock.connect_ex((host, port))
                sock.close()
                if result == 0:
                    open_ports.append(port)
            except Exception:
                pass
        return {"open_ports": open_ports, "scanned": len(ports)}

    def _grab_banners(self, host: str, ports: List[int]) -> dict:
        """Grab service banners from open ports."""
        banners = {}
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                sock.connect((host, port))
                # Send a generic probe
                try:
                    sock.send(b"\r\n")
                except Exception:
                    pass
                sock.settimeout(2.0)
                banner = sock.recv(1024).decode("utf-8", errors="replace").strip()
                sock.close()
                if banner:
                    banners[str(port)] = banner[:200]
                else:
                    banners[str(port)] = "no banner"
            except Exception as e:
                banners[str(port)] = f"error: {e}"
        return {"banners": banners}
