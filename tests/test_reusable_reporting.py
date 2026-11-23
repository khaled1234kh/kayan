import asyncio
from dataclasses import asdict
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from ai.trustgate.client import TrustGateDecision
from console.backend.reporting_api import install_reporting_api
from console.backend.reporting_evidence import ReportingCatalog, capture, canonical, digest
from console.backend.session_store import SessionStore
from eval.fixtures.ai.attack_admission_v2 import issue
from pentagi.agents.archived_reporting import ARCHIVE, ARCHIVE_SHA256, request_for

ID = "bbbbbbbb-1111-2222-3333-444444444444"
NEIGHBOR = "aaaaaaaa-1111-2222-3333-444444444444"


def completed(eid, records=(("source-local", "Observed result"),)):
    return {
        "engagement_id": eid, "status": "completed", "execution_engine": "local_llm",
        "target": "http://127.0.0.1:8888", "roe": {"targets": ["127.0.0.1"]},
        "findings": [{"mitre": "T1486", "verified": True}],
        "transcript": [
            {"id": source, "result": result, "agent_role": "network_agent", "kind": "tool_result",
             "timestamp": 1710000000000, "engagement_id": eid, "task_id": f"task-{i}"}
            for i, (source, result) in enumerate(records)
        ],
    }


def client_for(catalog, output, *, before_write_decision=None):
    class Gate:
        async def authorize(self, **kwargs):
            assert kwargs["engagement_id"] == f"archived-{ID}"
            if before_write_decision:
                assert kwargs["action"] == "write_report"
                await asyncio.sleep(0)
                before_write_decision()
            return TrustGateDecision("reporting_agent", kwargs["action"], True, "ALLOW", "fixture", None, "audit")

        def close(self):
            pass

    app = FastAPI()
    install_reporting_api(app, catalog=catalog, output=output, make_gate=lambda _: Gate())
    return TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000))


def test_operational_archives_are_bound_and_survive_app_restart(tmp_path, monkeypatch):
    monkeypatch.delenv("KAYAN_REPORTING_CUSTODY_FILE", raising=False)
    monkeypatch.delenv("KAYAN_REPORTING_CUSTODY_SHA256", raising=False)
    store = SessionStore(tmp_path / "sessions")
    snapshot = completed(ID)
    snapshot["transcript"].extend(completed(NEIGHBOR, [("foreign", "Other case")])["transcript"])
    store.save(snapshot)
    store.save(completed(NEIGHBOR))
    output = tmp_path / "reports"
    catalog = ReportingCatalog(store, tmp_path / "evidence")
    with client_for(catalog, output) as client:
        assert {row["assessment_id"] for row in client.get("/reporting/assessments").json()} == {
            ID, NEIGHBOR, "synthetic-slate-reporting",
        }
        meta = client.get("/reporting/archive", params={"assessment_id": ID}).json()
        assert meta["verification"] == "missing_custody"
        assert meta["coverage"]["recorded_tools"] == 1
        assert not meta["cloud_available"]
        assert client.post("/reporting/archive/run", json={"mode": "sovereigneg", "assessment_id": ID}).status_code == 409
        result = client.post("/reporting/archive/run", json={"mode": "local", "assessment_id": ID}).json()
        assert result["findings"] == []
        assert result["withheld"] == [{"technique": "T1486", "reasons": ["independent_custody_missing"]}]

    evidence = tmp_path / "evidence"
    ledger, = evidence.glob("*.json")
    body = json.loads(ledger.read_bytes())
    record, = body["records"]
    assert body["assessment_id"] == ID
    assert record["source_id"] == "source-local"
    assert record["sha256"] == digest(b"Observed result")
    assert record["authorization_status"] == "unavailable" and record["attribution_status"] == "unreviewed"

    reopened = ReportingCatalog(SessionStore(tmp_path / "sessions"), evidence)
    with client_for(reopened, output) as client:
        exported = client.get("/reporting/archive/result", params={"assessment_id": ID, "download": True})
        assert "attachment" in exported.headers["content-disposition"]
        assert exported.json() == result
        assert client.get("/reporting/archive/result", params={"assessment_id": NEIGHBOR}).status_code == 404


@pytest.fixture
def reviewed_catalog(tmp_path, monkeypatch):
    fixture = ARCHIVE.read_bytes()
    assert digest(fixture) == ARCHIVE_SHA256
    archive = json.loads(fixture)
    case = json.loads(archive["snapshot"])
    records = {(row["id"], row["revision"]): row["text"].encode("utf-8") for row in archive["records"]}
    case["case_id"] = ID
    raw, authority = issue(case)
    state = completed(ID, [(rec, value.decode()) for (rec, _), value in records.items()])
    state["findings"].append({"mitre": "T1078"})
    snapshot = capture(state)
    store = SessionStore(tmp_path / "sessions")
    store.save(state)
    store.save(completed(NEIGHBOR))
    catalogue = tmp_path / "external-custody.json"
    monkeypatch.setenv("KAYAN_REPORTING_CUSTODY_FILE", str(catalogue))
    package = {
        "assessment_id": ID, "title": "Synthetic review", "status": "completed",
        "snapshot": raw.decode("ascii"), "custody": asdict(authority),
        "operational_evidence_sha256": digest(canonical(snapshot)),
        "records": [{"id": rec, "revision": rev, "text": value.decode()}
                    for (rec, rev), value in records.items()],
    }

    def pin(value):
        catalogue.write_text(json.dumps(value, default=sorted), encoding="utf-8")
        monkeypatch.setenv("KAYAN_REPORTING_CUSTODY_SHA256", digest(catalogue.read_bytes()))

    pin({ID: package, NEIGHBOR: package})
    catalog = ReportingCatalog(store, tmp_path / "evidence")
    return catalog, catalogue, package, pin


def test_catalogue_uses_admission_and_rejects_other_case_or_mutated_record(tmp_path, reviewed_catalog):
    catalog, _, package, pin = reviewed_catalog
    reviewed = catalog.load(ID)
    assert reviewed["verification"] == "independent_custody"
    assert [row["technique"] for row in reviewed["findings"]] == ["T1486"]
    assert {row["technique"] for row in reviewed["withheld"]} == {"T1490", "T1078"}
    assert request_for(reviewed)[2] != request_for({**reviewed, "assessment_id": NEIGHBOR})[2]
    assert catalog.load(NEIGHBOR)["verification"] == "invalid_custody"

    with client_for(catalog, tmp_path / "reports") as client:
        result_url = "/reporting/archive/result"
        selection = {"assessment_id": ID}
        run_payload = {"mode": "local", **selection}
        admitted = client.post("/reporting/archive/run", json=run_payload)
        assert admitted.status_code == 200
        before = client.get(result_url, params=selection)
        before_export = client.get(result_url, params={**selection, "download": True})
        expected = digest(before_export.content)
        assert before.json() == before_export.json()
        assert [row["technique"] for row in before.json()["findings"]] == ["T1486"]

        package["records"][0]["text"] += "modified"
        pin({ID: package})
        failed = catalog.load(ID)
        assert failed["verification"] == "invalid_custody"
        assert failed["findings"] == [] and request_for(failed) is None

        download_params = {**selection, "download": True, "expected_sha256": expected}
        assert client.get(result_url, params=download_params).status_code == 409
        next_run = client.post("/reporting/archive/run", json=run_payload)
        assert next_run.status_code == 200
        assert next_run.json()["findings"] == []
        stale = client.get(result_url, params=download_params)
        assert stale.status_code == 409
        assert "content-disposition" not in stale.headers

        current = client.get(result_url, params=selection)
        assert current.content == next_run.content
        assert admitted.content == before.content == before_export.content
        assert admitted.headers["etag"] == before.headers["etag"] == f'"{expected}"'
        fresh = client.get(result_url, params={**download_params, "expected_sha256": digest(current.content)})
        assert fresh.status_code == 200 and fresh.content == current.content
        assert fresh.headers["cache-control"] == "no-store"


def test_local_reporting_refuses_custody_change_during_write_decision(tmp_path, reviewed_catalog):
    catalog, catalogue, _, _ = reviewed_catalog
    original = catalog.load(ID)
    assert original["verification"] == "independent_custody"
    assert [row["technique"] for row in original["findings"]] == ["T1486"]
    output = tmp_path / "reports"

    def invalidate_catalogue():
        # The approval digest remains pinned to the prior catalogue bytes.
        catalogue.write_bytes(b"{}")

    payload = {"mode": "local", "assessment_id": ID}
    with client_for(catalog, output, before_write_decision=invalidate_catalogue) as client:
        refused = client.post("/reporting/archive/run", json=payload)
        assert refused.status_code == 409
        assert "findings" not in refused.json()
        assert not list(output.glob("*.json"))

    current = catalog.load(ID)
    assert current["source_sha256"] == original["source_sha256"]
    assert current["report_revision"] != original["report_revision"]
    with client_for(catalog, output) as client:
        retry = client.post("/reporting/archive/run", json=payload)
        assert retry.status_code == 200
        assert retry.json()["verification"] == "invalid_custody"
        assert retry.json()["findings"] == []
        assert {row["technique"] for row in retry.json()["withheld"]} == {"T1486", "T1078"}


@pytest.mark.parametrize("changes", [{"status": "active"}, {"target": "http://outside.invalid"},
                                    {"roe": {"targets": ["127.0.0.1", "other"]}}])
def test_only_completed_owned_lab_records_can_be_imported(changes):
    with pytest.raises(ValueError, match="completed owned-lab scope"):
        capture({**completed(ID), **changes})

