import json
from hashlib import sha256

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai.trustgate.client import TrustGateDecision
from console.backend.reporting_api import install_reporting_api
from eval.archived_reporting_projection import compare, fixtures
from pentagi.agents.archived_reporting import compose, request_for, review_archive_document


def test_frozen_reporting_projection_matches_occurrence_oracle():
    assert compare()["counts"] == {
        "eligible": 4, "withheld": 6, "invalid": 1, "empty": 1,
        "false_admissions": 0, "false_withholdings": 0, "false_rejections": 0,
        "invalid_accepted": 0, "citation_errors": 0, "verifier_disagreements": 0,
    }


@pytest.mark.parametrize("case, expected", [
    ("repeated-supported", ["incident-1", "incident-2"]),
    ("repeated-mixed", ["incident-1"]),
    ("shared-ambiguous-anchor", []),
])
def test_reporting_api_preserves_occurrences_and_stays_local(tmp_path, case, expected):
    raw, *_ = dict(fixtures())[case]
    report = review_archive_document(json.loads(raw), sha256(raw).hexdigest())
    assert request_for(report) is None
    with pytest.raises(ValueError, match="requires distinct techniques"):
        compose(report, selection="{}")

    class Gate:
        def close(self):
            pass

        async def authorize(self, **arguments):
            assert arguments["action"] == "write_report"
            return TrustGateDecision("reporting_agent", "write_report", True, "ALLOW", "fixture", None, "audit-occurrence")

    def provider(*args, **kwargs):
        pytest.fail("A repeated-technique report must not initialize a cloud provider")

    app = FastAPI()
    install_reporting_api(app, load_archive=lambda: report, output=tmp_path,
                          make_gate=lambda _: Gate(), make_provider=provider, approved_scope="")
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
        archive_status = client.get("/reporting/archive").json()
        assert not archive_status["cloud_available"] and not archive_status["cloud_selection_supported"]
        assert client.post("/reporting/archive/run", json={"mode": "sovereigneg"}).status_code == 409
        result = client.post("/reporting/archive/run", json={"mode": "local"})
        assert result.status_code == 200
        body = result.json()
        assert [finding["occurrence"] for finding in body["findings"]] == expected
        assert [source["occurrence"] for source in body["summary"]] == expected
        assert [claim["occurrence"] for claim in body["withheld"]] == [
            name for name in ("incident-1", "incident-2") if name not in expected
        ]
        saved = client.get("/reporting/archive/result", params={
            "download": True, "expected_sha256": sha256(result.content).hexdigest(),
        })
        assert saved.status_code == 200 and saved.content == result.content
