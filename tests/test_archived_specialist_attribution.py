import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai.trustgate.client import TrustGateDecision
from console.backend.reporting_api import install_reporting_api
from console.backend.reporting_evidence import ReportingCatalog, capture
from console.backend.session_store import SessionStore
from eval.archived_specialist_attribution import CASE, FIXTURE, fixture_session, run
from pentagi.execution_evidence import ToolEvidenceStore


CASES = json.loads(FIXTURE.read_bytes())["cases"]


def test_passive_attribution_replay_reproduces_frozen_result():
    data = run()
    saved = Path("eval/reports/archived_specialist_attribution_v1_after.json")
    assert data == json.loads(saved.read_bytes())
    assert data["exact_cases"] == len(CASES) == 9


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_api_exposes_only_retained_observations_by_their_validated_roles(tmp_path, case):
    source = ToolEvidenceStore(tmp_path / "source")
    store = SessionStore(tmp_path / "sessions")
    store.save(fixture_session(case, source))
    catalog = ReportingCatalog(store, tmp_path / "archive", source)
    app = FastAPI()
    install_reporting_api(app, catalog=catalog)
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 5555)) as client:
        response = client.get("/reporting/archive", params={"assessment_id": CASE})
    assert response.status_code == 200
    body = response.json()
    assert body["observations_by_role"] == case["expected"]
    assert body["coverage"]["invalid_sources"] == case["invalid_sources"]
    projected = catalog.load(CASE)
    assert projected["findings"] == []
    if case.get("declared_complete"):
        assert all(item["complete"] for item in body["coverage"]["specialists"])
        assert body["observations_by_role"] == {}


def test_conflicting_captures_have_no_first_writer_preference(tmp_path):
    case = next(item for item in CASES if item["id"] == "conflicting_capture_revision")
    source = ToolEvidenceStore(tmp_path)
    session = fixture_session(case, source)
    rows = session["transcript"]
    changed = capture(session, source)
    rows[1], rows[2] = rows[2], rows[1]
    rows.append(dict(rows[1]))
    assert capture(session, source) == changed
    assert changed["invalid_sources"] == 2
    assert len(changed["records"]) == 1 and changed["records"][0]["agent"] == "network_agent"


def test_saved_role_observations_are_bound_to_the_archive_and_optional_in_legacy_exports(tmp_path):
    source = ToolEvidenceStore(tmp_path / "source")
    sessions = SessionStore(tmp_path / "sessions")
    sessions.save(fixture_session(CASES[0], source))
    catalog = ReportingCatalog(sessions, tmp_path / "archive", source)
    output = tmp_path / "reports"

    class Gate:
        async def authorize(self, **args):
            assert args["action"] == "write_report"
            return TrustGateDecision("reporting_agent", "write_report", True, "ALLOW", "fixture", None, "audit")

        def close(self):
            pass

    app = FastAPI()
    install_reporting_api(app, catalog=catalog, output=output, make_gate=lambda _: Gate())
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 5555)) as client:
        saved = client.post("/reporting/archive/run", json={"mode": "local", "assessment_id": CASE})
        assert saved.status_code == 200 and saved.json()["observations_by_role"] == CASES[0]["expected"]
        url = "/reporting/archive/result"
        params = {"assessment_id": CASE, "download": True}
        assert client.get(url, params=params).content == saved.content
        file, = output.glob("*.json")
        altered = saved.json()
        altered["observations_by_role"]["recon_agent"]["completed"] += 1
        file.write_text(json.dumps(altered), encoding="utf-8")
        assert client.get(url, params=params).status_code == 409
        del altered["observations_by_role"]
        legacy = json.dumps(altered).encode()
        file.write_bytes(legacy)
        assert client.get(url, params=params).content == legacy
