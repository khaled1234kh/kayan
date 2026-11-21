import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import FastAPI
from fastapi.testclient import TestClient

from console.backend.reporting_custody import verify_catalogue
from console.backend.reporting_evidence import ReportingCatalog, digest
from console.backend.reporting_review import install_review_api
from console.backend.session_store import SessionStore
from integration.trustgate_client import AuthorizationResult
from pentagi.agents.base_agent import BaseAgent
from pentagi.execution_evidence import LAB_URL, ToolEvidenceStore

ID = "bbbbbbbb-1111-2222-3333-444444444444"
OTHER = "aaaaaaaa-1111-2222-3333-444444444444"


class Specialist(BaseAgent):
    def run(self, target):
        return []


def execute(store, result, gate_allowed=True):
    class Gate:
        def authorize(self, **kwargs):
            return AuthorizationResult(gate_allowed, "ALLOW" if gate_allowed else "DENY", "test only",
                                       audit_entry_id="test-audit")
    agent = Specialist("test-specialist", "recon_agent", ID, Gate())
    agent.evidence_store = store
    events = []
    agent.event_sink = lambda agent, kind, task, _, details: events.append({
        "id": str(len(events)), "engagement_id": ID, "agent_id": agent.agent_id,
        "agent_role": agent.role, "kind": kind, "task_id": task, **details,
    })
    calls = []

    def callback(args):
        calls.append(True)
        if isinstance(result, Exception):
            raise result
        return result

    agent.execute_tool("test_observation", {"target": LAB_URL, "password": "private-argument"},
                       "127.0.0.1", "recon", executor_fn=callback)
    assert bool(calls) == gate_allowed
    return events


def completed(events):
    return {"engagement_id": ID, "status": "completed", "execution_engine": "local_llm",
            "target": LAB_URL, "roe": {"targets": ["127.0.0.1"]}, "transcript": events,
            "findings": [{"mitre": "T1486"}]}


def test_boundary_capture_binds_outcome_and_survives_restoration(tmp_path):
    source = ToolEvidenceStore(tmp_path / "source")
    events = execute(source, {"status_code": 200, "body_excerpt": "private-response"})
    event = events[-1]
    result = source.load(ID, event["task_id"], event["source_artifact_sha256"])
    assert result["outcome"] == {"status_code": 200}
    assert result["output_projected"]
    assert result["status"] == "completed" and result["audit_entry_id"] == "test-audit"
    file, = (source.root / ID).glob("*.json")
    assert b"private-" not in file.read_bytes()
    with pytest.raises(OSError):
        source.load(OTHER, event["task_id"], event["source_artifact_sha256"])

    sessions = tmp_path / "sessions"
    SessionStore(sessions).save(completed(events))
    catalog = ReportingCatalog(SessionStore(sessions), tmp_path / "archive", ToolEvidenceStore(source.root))
    report = catalog.load(ID)
    assert report["source_status"] == "source_captured"
    assert report["verification"] == "missing_custody" and report["findings"] == []
    assert report["coverage"]["captured_tools"] == 1
    file.write_bytes(file.read_bytes() + b" ")
    rejected = catalog.load(ID)
    assert rejected["source_status"] == "invalid_source" and rejected["findings"] == []
    assert rejected["coverage"]["captured_tools"] == 0


@pytest.mark.parametrize(("outcome","allowed","status"), [
    (RuntimeError("private-error"), True, "failed"), (None, False, "denied"),
])
def test_failed_or_denied_is_not_successful(tmp_path, outcome, allowed, status):
    source = ToolEvidenceStore(tmp_path)
    event = execute(source, outcome, allowed)[-1]
    recorded = source.load(ID, event["task_id"], event["source_artifact_sha256"])
    assert recorded["status"] == status and recorded["outcome"] == {}


def test_conflicting_decisions_and_reused_reference_withheld(tmp_path):
    source = ToolEvidenceStore(tmp_path / "source")
    events = execute(source, {"status_code": 200})
    authorization = next(row for row in events if row["kind"] == "authorization_decision")
    events.insert(-1, {**authorization, "decision": "DENY"})
    store = SessionStore(tmp_path / "sessions")
    store.save(completed(events))
    store.save({**completed([{**row, "engagement_id": OTHER} for row in events]), "engagement_id": OTHER})
    catalog = ReportingCatalog(store, tmp_path / "archive", source)
    for case in (ID, OTHER):
        assert catalog.load(case)["source_status"] == "invalid_source"
        assert catalog.load(case)["findings"] == []


def test_review_is_scoped_and_draft_does_not_promote_evidence(tmp_path, monkeypatch):
    source = ToolEvidenceStore(tmp_path / "source")
    sessions = SessionStore(tmp_path / "sessions")
    sessions.save(completed(execute(source, {"status_code": 200})))
    catalog = ReportingCatalog(sessions, tmp_path / "archive", source)
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps([{"reviewer_id": "test-only-reviewer", "assessment_ids": [ID],
                                   "token_sha256": digest(b"test-only-token")}]))
    monkeypatch.setenv("KAYAN_REPORTING_REVIEWERS_FILE", str(roster))
    monkeypatch.setenv("KAYAN_REPORTING_REVIEWERS_SHA256", digest(roster.read_bytes()))
    app = FastAPI()
    install_review_api(app, catalog, tmp_path / "reviews")
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 5555)) as client:
        url = "/reporting/review"
        headers = {"Authorization": "Bearer test-only-token"}
        assert client.get(url, params={"assessment_id": ID}).status_code == 403
        assert client.get(url, params={"assessment_id": OTHER}, headers=headers).status_code == 403
        data = client.get(url, params={"assessment_id": ID}, headers=headers).json()
        decision = {"assessment_id": ID, "source_sha256": data["source_sha256"], "assertions":
                    [{"source_id": data["records"][0]["source_id"], "technique": "T1486", "role": "actor",
                      "disposition": "unresolved"}]}
        assert client.post(url, json={**decision, "source_sha256": "wrong"}, headers=headers).status_code == 409
        reply = client.post(url, json=decision, headers=headers)
        assert reply.status_code == 200 and reply.json()["reviewer"] == "test-only-reviewer"
        assert reply.json()["status"] == "submitted_awaiting_independent_admission"
    result = catalog.load(ID)
    assert result["verification"] == "missing_custody" and result["review_status"] == "submitted"


def test_external_catalogue_signature_covers_exact_bytes(tmp_path, monkeypatch):
    key = Ed25519PrivateKey.generate()
    public, signature = tmp_path / "public.pem", tmp_path / "signature.b64"
    public.write_bytes(key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
    signature.write_bytes(base64.b64encode(key.sign(b"original")))
    monkeypatch.setenv("KAYAN_REPORTING_CUSTODY_PUBLIC_KEY", str(public))
    monkeypatch.setenv("KAYAN_REPORTING_CUSTODY_SIGNATURE", str(signature))
    assert verify_catalogue(b"original", checkout=tmp_path / "repo")
    with pytest.raises(ValueError, match="signature is invalid"):
        verify_catalogue(b"modified", checkout=tmp_path / "repo")

