"""Bounded, non-destructive tools for the owned loopback lab. No arbitrary shell/URL executor."""
import re
import secrets
import socket
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROLE_TOOLS = {
    "recon_agent": ["http_probe", "port_scan", "discover_endpoints"],
    "webapp_agent": ["xss_test", "sql_injection_test", "command_injection_test", "directory_traversal"],
    "network_agent": ["port_scan", "service_scan"],
}
MITRE = {"http_probe": "T1592", "port_scan": "T1046", "discover_endpoints": "T1590", "service_scan": "T1046",
         "xss_test": "T1190", "sql_injection_test": "T1190", "command_injection_test": "T1059", "directory_traversal": "T1190"}
FINDING_TYPES = {"xss_test": "xss", "sql_injection_test": "sql_injection", "command_injection_test": "command_injection", "directory_traversal": "path_traversal"}


class LabTools:
    def __init__(self, target):
        if target.rstrip("/") != "http://127.0.0.1:8888":
            raise ValueError("MVP tools only support the owned http://127.0.0.1:8888 lab")
        self.target = target.rstrip("/")
        self.client = httpx.Client(timeout=8, follow_redirects=False)

    def run(self, tool, verification=False):
        marker = "KAYAN_" + secrets.token_hex(8)
        if tool == "port_scan":
            with socket.socket() as connection:
                connection.settimeout(2)
                opened = connection.connect_ex(("127.0.0.1", 8888)) == 0
            return {"open_ports": [8888] if opened else [], "scope": "ROE lab port only"}
        if tool in ("http_probe", "service_scan"):
            response = self.client.get(self.target)
            return {"status_code": response.status_code, "server": response.headers.get("server"), "body_excerpt": response.text[:1200]}
        if tool == "discover_endpoints":
            paths = ["/", "/login", "/search", "/api/products"]
            return {"endpoints": [{"path": path, "status_code": self.client.get(self.target+path).status_code} for path in paths]}
        if tool == "xss_test":
            payload = f"<script>/*{marker}*/</script>"
            response = self.client.get(self.target+"/search", params={"q": payload})
            supported = response.status_code == 200 and payload in response.text
        elif tool == "sql_injection_test":
            payload = "' OR 1=1 --"
            response = self.client.post(self.target+"/login", data={"username": payload, "password": marker})
            supported = response.status_code == 200 and "Welcome," in response.text and "Role:" in response.text
        elif tool == "command_injection_test":
            # Fixed benign echo marker: the model never supplies an arbitrary command.
            payload = f"127.0.0.1 & echo {marker}"
            response = self.client.get(self.target+"/ping", params={"host": payload})
            supported = bool(re.search(r"(?m)^" + re.escape(marker) + r"\s*$", response.text.replace("</pre>", "\n")))
        elif tool == "directory_traversal":
            root = Path(__file__).resolve().parents[1]
            fixture = root / "lab/fixtures/verification_marker.txt"
            fixture.parent.mkdir(exist_ok=True)
            fixture.write_text(marker, encoding="utf-8")
            payload = "../kayan-trustgate/lab/fixtures/verification_marker.txt"
            response = self.client.get(self.target+"/file", params={"path": payload})
            supported = response.status_code == 200 and marker in response.text
        else:
            raise ValueError(f"No registered lab executor for {tool}")
        return {"supported": supported, "verification": verification, "marker": marker,
                "payload": payload, "status_code": response.status_code, "response_excerpt": response.text[:12000]}

    def close(self):
        self.client.close()
