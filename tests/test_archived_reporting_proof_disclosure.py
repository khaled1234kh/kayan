import json
from hashlib import sha256
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai.trustgate.client import TrustGateDecision
from console.backend.reporting_api import install_reporting_api
from eval.archived_reporting_proof_disclosure import FIXTURE, evaluate, shared_fixture
from pentagi.agents.archived_reporting import request_for


def test_frozen_disclosure_recovers_only_missing_reviewed_proof_links():
    report = evaluate()
    archived = Path("eval/reports/archived_reporting_proof_disclosure_v1_after.json")
    assert json.loads(archived.read_bytes()) == report
    cases = report["cases"]
    assert sum(case["baseline"]["complete_occurrences"] for case in cases) == 50
    assert sum(case["disclosure"]["complete_occurrences"] for case in cases) == 53
    assert all(not case["disclosure"][field] for case in cases for field in (
        "missing_links", "incorrect_links", "incorrect_occurrences",
    ))
    assert all(case["baseline"]["summary_coverage"] == case["disclosure"]["summary_coverage"] for case in cases)


@pytest.mark.parametrize("variant", ["current", "legacy", "foreign_source", "wrong_event_revision"])
def test_saved_reporting_verifies_proof_and_preserves_old_bytes(variant, tmp_path):
    report, _ = shared_fixture(json.loads(FIXTURE.read_bytes())["shared_context"])

    class Gate:
        async def authorize(self, **arguments):
            assert arguments["action"] == "write_report"
            return TrustGateDecision("reporting_agent", "write_report", True, "ALLOW", "fixture", None, "test-write")

        def close(self):
            pass

    app = FastAPI()
    install_reporting_api(app, output=tmp_path, load_archive=lambda: report, make_gate=lambda _: Gate())
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 5080)) as client:
        result = client.post("/reporting/archive/run", json={"mode": "local"})
        assert result.status_code == 200
        body = result.json()
        assert [row["occurrence"] for row in body["findings"]] == ["incident-1", "incident-2"]
        assert [row["occurrence"] for row in body["withheld"]] == ["incident-3"]
        for index, finding in enumerate(body["findings"], 1):
            assert {"role": "mechanic", "source_ids": [f"E{index}.1", "E9.1"]} in finding["proof"]["assertions"]
        assert "proof" not in request_for(report)[0][-1].content
        saved, = tmp_path.glob("*-local.json")
        previous = saved.read_bytes()
        if variant == "legacy":
            for finding in body["findings"]:
                del finding["proof"]
        elif variant == "foreign_source":
            mechanics = next(row for row in body["findings"][0]["proof"]["assertions"] if row["role"] == "mechanic")
            mechanics["source_ids"][1] = "E2.1"
        elif variant == "wrong_event_revision":
            body["findings"][0]["proof"]["event_revision"] += 1
        if variant != "current":
            previous = json.dumps(body).encode()
            saved.write_bytes(previous)

        digest = sha256(previous).hexdigest()
        response = client.get("/reporting/archive/result", params={"download": True, "expected_sha256": digest})
        if variant in {"current", "legacy"}:
            assert response.status_code == 200 and response.content == previous
        else:
            assert response.status_code == 409
        assert saved.read_bytes() == previous
