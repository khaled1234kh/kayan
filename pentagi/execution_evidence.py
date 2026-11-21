"""Passive evidence capture for the owned lab's Python execution boundary."""

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

ROOT = Path(__file__).resolve().parents[1] / "data/runtime/tool-evidence"
VERSION = "kayan.tool-evidence/1"
LAB_URL = "http://127.0.0.1:8888"
ENGAGEMENT = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}")
TASK = re.compile(r"tool-[0-9a-f]{32}")
DIGEST = re.compile(r"[0-9a-f]{64}")


def encode(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")


def digest(data):
    return sha256(data).hexdigest()


def safe_outcome(result):
    # Tool responses may contain credentials or reflected request values. Retain
    # a closed set of typed fields. Free-form responses and errors stay out.
    if not isinstance(result, dict):
        return {}, result is not None
    safe = {}
    for key in ("supported", "verification"):
        if type(result.get(key)) is bool:
            safe[key] = result[key]
    status = result.get("status_code")
    if type(status) is int and 100 <= status <= 599:
        safe["status_code"] = status
    ports = result.get("open_ports")
    if isinstance(ports, list) and ports in ([], [8888]) and all(type(port) is int for port in ports):
        safe["open_ports"] = ports
    return safe, safe != result


class ToolEvidenceStore:
    def __init__(self, root=ROOT):
        self.root = Path(root)

    def record(self, *, engagement, agent, role, task, tool, target, auth, result, dispatched):
        if not ENGAGEMENT.fullmatch(engagement) or not TASK.fullmatch(task) or target != "127.0.0.1":
            raise ValueError("Capture is outside the owned lab identity scope")
        outcome, projected = safe_outcome(result) if dispatched else ({}, False)
        allowed = auth.allowed and auth.decision == "ALLOW" and bool(auth.audit_entry_id)
        failed = dispatched and (not isinstance(result, dict) or not result or "error" in result
                                 or ("supported" in result and type(result["supported"]) is not bool))
        status = ("denied" if not auth.allowed else "authorization_unverified" if not allowed
                  else "not_dispatched" if not dispatched else "failed" if failed else "completed")
        record = {
            "version": VERSION, "engagement_id": engagement, "assessment_id": engagement,
            "source_id": task, "task_id": task, "revision": 1, "agent": agent, "role": role,
            "tool": tool, "approved_target": target if allowed else None,
            "arguments": {"target": LAB_URL}, "authorization_decision": auth.decision,
            "audit_entry_id": auth.audit_entry_id or None, "status": status,
            "completed_at": datetime.now(timezone.utc).isoformat(), "collector": "kayan-python-governed-executor",
            "outcome": outcome, "output_sha256": digest(encode(outcome)), "output_projected": projected,
            "error_category": "executor_error_or_invalid_outcome" if failed else None,
            "process_id": None, "session_id": None, "exit_status": None,
        }
        body = encode(record)
        sha = digest(body)
        folder = self.root / engagement
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{task}-{sha}.json"
        with NamedTemporaryFile(dir=folder, delete=False) as pending:
            temporary = Path(pending.name)
            pending.write(body)
            pending.flush()
            os.fsync(pending.fileno())
        try:
            os.link(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return sha

    def load(self, engagement, task, sha):
        if not ENGAGEMENT.fullmatch(engagement) or not TASK.fullmatch(task) or not DIGEST.fullmatch(sha):
            raise ValueError("Invalid source artifact reference")
        raw = (self.root / engagement / f"{task}-{sha}.json").read_bytes()
        if digest(raw) != sha:
            raise ValueError("Source artifact digest mismatch")
        record = json.loads(raw)
        if (record["version"] != VERSION or record["engagement_id"] != engagement
                or record["assessment_id"] != engagement or record["task_id"] != task
                or record["source_id"] != task or record["output_sha256"] != digest(encode(record["outcome"]))):
            raise ValueError("Source artifact identity mismatch")
        return record

