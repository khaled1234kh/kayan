from dataclasses import asdict
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import FastAPI
from fastapi.testclient import TestClient

from console.backend.reporting_evidence import ReportingCatalog
from console.backend.reporting_exchange import canonical, digest
from console.backend.reporting_review import install_review_api
from console.backend.session_store import SessionStore
from console.backend.sign_reporting_receipt import build_receipt
from eval.attack_evidence_admission_v2 import VERSION
from eval.fixtures.ai.attack_admission_v2 import issue
from eval.fixtures.ai.attack_fact_registry_v1.demo import _fixture, _record
from integration.trustgate_client import AuthorizationResult
from pentagi.execution_evidence import LAB_URL, ToolEvidenceStore

ID = "bbbbbbbb-1111-2222-3333-444444444444"
OTHER = "aaaaaaaa-1111-2222-3333-444444444444"
TASK = "tool-" + "1" * 32
REVIEW = {"Authorization": "Bearer reviewer-test-only"}
SECOND = {"Authorization": "Bearer second-test-only"}
CUSTODY = {"Authorization": "Bearer custodian-test-only"}


def archived_fixture(package):
    case, payloads = _fixture(package["assessment_id"])
    case["schema_version"] = VERSION
    source = package["sources"][0]
    # The readiness result is not evidence for the candidate. Keep assertions empty.
    data = canonical(source["outcome"])
    _record(case, payloads, source["source_id"], data, "test-only-capture", "E1.1")
    case["sources"][0]["upstream"] = []
    manifest, authority = issue(case)
    return {
        "assessment_id": package["assessment_id"], "title": "Test-only diagnostic",
        "status": "completed", "snapshot": manifest.decode("ascii"), "custody": asdict(authority),
        "operational_evidence_sha256": package["source_sha256"],
        "review_receipt_sha256": [row["sha256"] for row in package["reviews"]],
        "records": [{"id": key, "revision": rev, "text": raw.decode()} for (key, rev), raw in payloads.items()],
    }


@pytest.fixture
def setup(tmp_path, monkeypatch):
    sessions = SessionStore(tmp_path / "sessions")
    sources = ToolEvidenceStore(tmp_path / "captures")
    ref = sources.record(engagement=ID, agent="fixture-agent", role="recon_agent", task=TASK, tool="readiness",
                         target="127.0.0.1", auth=AuthorizationResult(True, "ALLOW", "fixture", audit_entry_id="audit"),
                         result={"status_code": 200}, dispatched=True)
    meta = {"engagement_id": ID, "agent_id": "fixture-agent", "agent_role": "recon_agent",
            "task_id": TASK, "tool_name": "readiness", "target": "127.0.0.1"}
    sessions.save({"engagement_id": ID, "status": "completed", "execution_engine": "local_llm", "target": LAB_URL,
                   "roe": {"targets": ["127.0.0.1"]}, "findings": [{"mitre": "T1486"}], "transcript": [
                       {**meta, "kind": "authorization_decision", "decision": "ALLOW", "audit_entry_id": "audit"},
                       {**meta, "kind": "tool_result", "source_artifact_sha256": ref},
                   ]})
    key = Ed25519PrivateKey.generate()
    public = tmp_path / "test-only-public.pem"
    public.write_bytes(key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
    entries = [
        {"reviewer_id": "Test Reviewer", "role": "reviewer", "assessment_ids": [ID],
         "token_sha256": digest(b"reviewer-test-only"), "test_only": True},
        {"reviewer_id": "Other Test Reviewer", "role": "reviewer", "assessment_ids": [ID],
         "token_sha256": digest(b"second-test-only"), "test_only": True},
        {"reviewer_id": "Test Custodian", "role": "custodian", "assessment_ids": [ID, OTHER],
         "token_sha256": digest(b"custodian-test-only"), "test_only": True, "key_id": "fixture-key",
         "public_key_file": str(public), "public_key_sha256": digest(public.read_bytes())},
    ]

    def provision():
        roster = tmp_path / "enrolment.json"
        raw = canonical(entries)
        roster.write_bytes(raw)
        monkeypatch.setenv("KAYAN_REPORTING_REVIEWERS_FILE", str(roster))
        monkeypatch.setenv("KAYAN_REPORTING_REVIEWERS_SHA256", digest(raw))

    provision()

    def launch():
        catalog = ReportingCatalog(SessionStore(sessions.directory), tmp_path / "archive", sources)
        app = FastAPI()
        install_review_api(app, catalog, catalog.reviews_directory)
        return catalog, TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 5060))

    return launch, key, entries, provision, sources


def review(client, headers=REVIEW, disposition="unresolved"):
    response = client.get("/reporting/review", params={"assessment_id": ID}, headers=headers)
    data = response.json()
    result = client.post("/reporting/review", headers=headers, json={
        "assessment_id": ID, "source_sha256": data["source_sha256"], "previous_review_sha256": data["review_head"],
        "assertions": [{"source_id": TASK, "technique": "T1486", "role": "actor", "disposition": disposition}]})
    assert result.status_code == 200, result.text
    return result.json()


def export(client):
    response = client.get("/reporting/custody/package", params={"assessment_id": ID}, headers=CUSTODY)
    assert response.status_code == 200, response.text
    assert response.headers["Content-Disposition"].startswith("attachment")
    package = response.json()
    assert digest(canonical(package["package"])) == package["package_sha256"]
    return package


def sign(client, key):
    package = export(client)
    catalogue = archived_fixture(package["package"])
    # Normalize fixture frozensets exactly as external JSON files do.
    import json
    catalogue = json.loads(json.dumps(catalogue, default=sorted))
    return build_receipt(package, catalogue, "fixture-key", key).model_dump()


def test_signed_round_trip_replay_revocation_and_restart(setup):
    launch, key, entries, provision, _ = setup
    catalog, client = launch()
    assert catalog.load(ID)["verification"] == "missing_custody"
    assert client.get("/reporting/review", params={"assessment_id": ID}, headers=CUSTODY).status_code == 403
    assert client.get("/reporting/custody/package", params={"assessment_id": OTHER}, headers=REVIEW).status_code == 403
    first = review(client)
    second = review(client)
    assert second["revision"] == 2 and second["previous_review_sha256"] == first["review_sha256"]
    signed = sign(client, key)
    assert client.post("/reporting/custody/receipt", headers=REVIEW, json=signed).status_code == 403
    assert client.post("/reporting/custody/receipt", headers=CUSTODY, json={**signed, "signature": "invalid"}).status_code == 409
    assert client.post("/reporting/custody/receipt", headers=CUSTODY, json={**signed, "assessment_id": OTHER}).status_code == 409
    accepted = client.post("/reporting/custody/receipt", headers=CUSTODY, json=signed)
    assert accepted.status_code == 201, accepted.text
    assert client.post("/reporting/custody/receipt", headers=CUSTODY, json=signed).status_code == 409
    successor = sign(client, key)
    assert successor["sequence"] == 2
    assert successor["previous_receipt_sha256"] == accepted.json()["receipt_sha256"]
    assert client.post("/reporting/custody/receipt?assessment_id=" + OTHER, headers=CUSTODY,
                       json=successor).status_code == 409
    assert client.post("/reporting/custody/receipt", headers=CUSTODY, json=successor).status_code == 201
    assert client.post("/reporting/custody/receipt", headers=CUSTODY, json=signed).status_code == 409
    restored, _ = launch()
    report = restored.load(ID)
    assert report["verification"] == "independent_custody" and report["admission_status"] == "evaluated"
    assert report["custody_test_only"]
    assert report["findings"] == [] and report["withheld"][0]["technique"] == "T1486"
    entries[-1]["active"] = False
    provision()
    assert restored.load(ID)["verification"] == "invalid_custody"


def test_conflict_and_source_tampering_fail_closed(setup):
    launch, key, _, _, sources = setup
    catalog, client = launch()
    review(client, disposition="unresolved")
    previously_signed = sign(client, key)
    review(client, headers=SECOND, disposition="contradicted")
    assert client.post("/reporting/custody/receipt", headers=CUSTODY, json=previously_signed).status_code == 409
    conflict = sign(client, key)
    denied = client.post("/reporting/custody/receipt", headers=CUSTODY, json=conflict)
    assert denied.status_code == 409 and "disagree" in denied.text
    artifact, = (Path(sources.root) / ID).glob("*.json")
    artifact.write_bytes(artifact.read_bytes() + b" ")
    assert client.get("/reporting/custody/package", params={"assessment_id": ID}, headers=CUSTODY).status_code == 409
    assert catalog.load(ID)["source_status"] == "invalid_source"

