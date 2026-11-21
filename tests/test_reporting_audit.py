import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from console.backend.reporting_api import install_reporting_api
from console.backend.reporting_audit import reconcile
from console.backend.reporting_evidence import ReportingCatalog, capture
from console.backend.session_store import SessionStore
from integration.trustgate_client import AuthorizationResult
from pentagi.execution_evidence import LAB_URL, ToolEvidenceStore


CASE = "bbbbbbbb-1111-2222-3333-444444444444"
OTHER_CASE = "cccccccc-1111-2222-3333-444444444444"
AUDIT_ID = "aaaaaaaa-1111-2222-3333-444444444444"
TASK = "tool-" + "1" * 32
REFERENCE = {
    "entry_id": AUDIT_ID, "engagement_id": CASE, "agent_id": "test-observer",
    "agent_role": "recon_agent", "tool_name": "fixture_read", "target": "127.0.0.1", "decision": "DENY",
}


def evidence(source, *, task=TASK, audit_id=AUDIT_ID, verdict="DENY"):
    allowed = verdict == "ALLOW"
    ref = source.record(
        engagement=CASE, agent="test-observer", role="recon_agent", tool="fixture_read",
        task=task, target="127.0.0.1", auth=AuthorizationResult(allowed, verdict, "fixture", audit_entry_id=audit_id),
        result={"status_code": 200} if allowed else None, dispatched=allowed,
    )
    common = {"engagement_id": CASE, "agent_id": "test-observer", "agent_role": "recon_agent",
              "tool_name": "fixture_read", "task_id": task, "target": "127.0.0.1"}
    return [
        {**common, "kind": "authorization_decision", "decision": verdict, "audit_entry_id": audit_id},
        {**common, "kind": "tool_result" if allowed else "tool_denied", "source_artifact_sha256": ref},
    ]


def session(events):
    return {"engagement_id": CASE, "status": "completed", "execution_engine": "local_llm",
            "target": LAB_URL, "roe": {"targets": ["127.0.0.1"]}, "transcript": events}


@pytest.mark.parametrize(("body", "status"), [
    ({"valid": True, "entries": [REFERENCE]}, "verified"),
    ({"valid": True, "entries": []}, "missing_entry"),
    ({"valid": False, "entries": [REFERENCE]}, "ledger_invalid"),
    ({"valid": 1, "entries": [REFERENCE]}, "unavailable"),
    ({"valid": True, "entries": [REFERENCE, REFERENCE]}, "unavailable"),
    ({"valid": True, "entries": [{**REFERENCE, "entry_id": OTHER_CASE}]}, "unavailable"),
    *[({"valid": True, "entries": [{**REFERENCE, field: value}]}, "mismatch") for field, value in [
        ("engagement_id", OTHER_CASE), ("agent_id", "other-observer"), ("agent_role", "network_agent"),
        ("tool_name", "other_read"), ("target", "other.invalid"), ("decision", "ALLOW"),
    ]],
])
def test_corroborates_only_a_verified_ledger_entry_for_the_exact_scope(tmp_path, body, status):
    source = ToolEvidenceStore(tmp_path)
    snapshot = capture(session(evidence(source)), source)
    calls = []

    def ledger(request):
        calls.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(200, json=body)

    result = reconcile(snapshot, "snapshot-hash", source, transport=httpx.MockTransport(ledger))
    assert result == {"assessment_id": CASE, "source_sha256": "snapshot-hash", "counts": {status: 1},
                      "references": [{"source_id": TASK, "status": status}]}
    assert calls == [("POST", "/audit/reconcile", {"engagement_id": CASE, "entry_ids": [AUDIT_ID]})]


def test_unavailable_service_and_missing_or_reused_id_are_distinct(tmp_path):
    source = ToolEvidenceStore(tmp_path)
    first = evidence(source)
    second = evidence(source, task="tool-" + "2" * 32, audit_id=None)
    third = evidence(source, task="tool-" + "3" * 32, audit_id=OTHER_CASE)
    fourth = evidence(source, task="tool-" + "4" * 32, audit_id=OTHER_CASE)
    snapshot = capture(session(first + second + third + fourth), source)

    def down(request):
        assert json.loads(request.content)["entry_ids"] == [AUDIT_ID]
        raise httpx.ReadTimeout("test only", request=request)

    result = reconcile(snapshot, "snapshot-hash", source, transport=httpx.MockTransport(down))
    assert result["counts"] == {"unavailable": 1, "missing_reference": 1, "reused_reference": 2}


def test_reporting_route_can_check_audit_without_changing_admission_or_writing_a_report(tmp_path):
    source = ToolEvidenceStore(tmp_path / "tool-evidence")
    sessions = SessionStore(tmp_path / "sessions")
    sessions.save(session(evidence(source, verdict="ALLOW")))
    catalog = ReportingCatalog(sessions, tmp_path / "evidence", source)
    before = catalog.load(CASE)
    output = tmp_path / "reports"
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={
        "valid": True, "entries": [{**REFERENCE, "decision": "ALLOW", "tool_args": {"secret": "test only"}}],
    }))
    app = FastAPI()
    install_reporting_api(app, catalog=catalog, output=output,
                          make_gate=lambda _: pytest.fail("The audit check requested authorization"),
                          make_provider=lambda *_: pytest.fail("The audit check created a model provider"),
                          reconcile_audit=lambda *args: reconcile(*args, transport=transport))
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 5555)) as client:
        result = client.get("/reporting/archive/audit", params={"assessment_id": CASE})
        assert result.status_code == 200
        assert result.json()["counts"] == {"verified": 1}
        assert result.json()["source_sha256"] == before["source_sha256"]
        assert "tool_args" not in result.text and "secret" not in result.text
        assert client.get("/reporting/archive/audit", params={"assessment_id": OTHER_CASE}).status_code == 404
    assert catalog.load(CASE) == before
    assert before["verification"] == "missing_custody" and before["findings"] == []
    assert not output.exists()
