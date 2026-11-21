import asyncio
import json
from concurrent.futures import CancelledError
from dataclasses import replace
from hashlib import sha256

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai.providers.reporting_sovereign import DESTINATION, MODEL, ReportingSovereignProvider
from ai.trustgate.client import TrustGateDecision
from console.backend import reporting_api
from console.backend.reporting_api import install_reporting_api
from pentagi.agents.archived_reporting import ARCHIVE, request_for, review_archive

SELECTION = {"highlights": ["T1486/E2.1"], "recommendations": ["T1486-1"], "emphasis": "observed_impact"}
PREFIX = "/reporting/archive"


@pytest.fixture
def center(tmp_path, monkeypatch):
    monkeypatch.setenv("SOVEREIGNEG_API_KEY", "test-only-placeholder")
    approvals, requests = [], []
    scenario = {"content": json.dumps(SELECTION), "finish": "stop", "denied": None}
    config = {"approved_scope": request_for(review_archive())[2]}

    class Gate:
        async def authorize(self, **args):
            approvals.append(args)
            allowed = args["action"] != scenario["denied"]
            return TrustGateDecision("reporting_agent", args["action"], allowed,
                                     "ALLOW" if allowed else "DENY", "fixture", None, str(len(approvals)))

        def close(self):
            pass

    async def transport(request):
        requests.append((str(request.url), json.loads(request.content)))
        for delay in scenario.get("response_delays", ()):
            await asyncio.sleep(delay)
        if scenario.get("cancelled"):
            raise asyncio.CancelledError
        if scenario.get("offline"):
            raise httpx.ReadTimeout("mock transport failure")
        return httpx.Response(200, json={
            "model": scenario.get("model", MODEL),
            "choices": [{"finish_reason": scenario["finish"], "message": {"content": scenario["content"]}}],
            "usage": {"prompt_tokens": scenario.get("prompt_tokens", 200),
                      "completion_tokens": scenario.get("completion_tokens", 22),
                      "completion_tokens_details": {"reasoning_tokens": 0}},
        })

    app = FastAPI()
    install_reporting_api(
        app, output=tmp_path, make_gate=lambda _: Gate(), **config,
        make_provider=lambda settings, **kwargs: ReportingSovereignProvider(
            settings, transport=httpx.MockTransport(transport), **kwargs),
    )
    return TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)), approvals, requests, scenario


def test_governed_report_has_same_stored_display_and_export(center):
    client, approvals, requests, _ = center
    info = client.get(PREFIX).json()
    assert info["cloud_available"]
    result = client.post(PREFIX + "/run", json={"mode": "sovereigneg"})
    assert result.status_code == 200
    body = result.json()
    assert body["status"] == "selected" and body["model"] == MODEL
    assert body["finish_reason"] == "stop"
    usage = dict(body["usage"])
    assert usage.pop("latency_s") >= 0
    assert usage == {"input": 200, "output": 22, "reasoning": 0}
    assert [claim["technique"] for claim in body["findings"]] == ["T1486"]
    assert "41 project archives" in body["summary"][0]["statements"][0]
    assert body["withheld"] == [{"technique": "T1490", "reasons": ["independent_attribution_missing"]}]
    assert body["summary"][0]["id"] == "E2.1"
    assert [entry["action"] for entry in approvals] == ["write_report", "llm_inference"]
    assert all(entry["agent_role"] == "reporting_agent" and entry["technique"] == "reporting" for entry in approvals)
    url, outgoing = requests[0]
    assert url == DESTINATION and outgoing["reasoning_effort"] == "none"
    assert approvals[-1]["tool_args"]["request_sha256"] == info["request_sha256"]
    data = json.loads(outgoing["messages"][1]["content"])
    assert data["hypotheses_withheld"] == ["T1490"]
    assert all("E4.1" not in row["id"] for row in data["admitted"])
    url = PREFIX + "/result?mode=sovereigneg"
    assert client.get(url).json() == body
    download = client.get(url + "&download=true")
    assert "attachment" in download.headers["content-disposition"] and download.json() == body
    assert not client.get(PREFIX).json()["cloud_available"]
    assert client.post(PREFIX + "/run", json={"mode": "sovereigneg"}).status_code == 409
    assert len(requests) == 1


@pytest.mark.parametrize("denied", ["write_report", "llm_inference"])
def test_denial_prevents_cloud_egress_and_publication(center, denied):
    client, _, requests, config = center
    config["denied"] = denied
    assert client.post(PREFIX + "/run", json={"mode": "sovereigneg"}).status_code == 403
    assert client.get(PREFIX + "/result?mode=sovereigneg").status_code == 404
    assert not requests
    assert client.get(PREFIX).json()["cloud_available"]


@pytest.mark.parametrize("failure", [
    {"content": ""}, {"content": "{"}, {"finish": "length"}, {"offline": True},
    {"model": "unexpected"}, {"content": '{"highlights":[],"recommendations":[],"emphasis":"observed_impact"}'},
    {"content": json.dumps({**SELECTION, "highlights": ["T1486/E4.1"]})},
    {"content": json.dumps({**SELECTION, "highlights": ["T1486/E2.1", "T1486/E2.1"]})},
    {"content": json.dumps({**SELECTION, "summary": "Unsupported prose"})},
    {"prompt_tokens": True}, {"prompt_tokens": -1},
    {"completion_tokens": 22.5}, {"completion_tokens": 1025},
])
def test_provider_failure_uses_verified_local_report_without_retry(center, failure):
    client, _, requests, config = center
    config.update(failure)
    decision = client.post(PREFIX + "/run", json={"mode": "sovereigneg"})
    assert decision.status_code == 200
    report = decision.json()
    assert report["status"] == "degraded" and report["model"] is None
    assert "usage" not in report and "finish_reason" not in report
    assert report["attempted_model"] == MODEL and report["summary"][0]["id"] == "E2.1"
    assert client.get(PREFIX + "/result?mode=sovereigneg").json() == report
    assert len(requests) == 1


def test_interrupted_cloud_report_recovers_fallback_after_restart(center, tmp_path):
    client, approvals, requests, scenario = center
    digest = client.get(PREFIX).json()["request_sha256"]
    scenario["cancelled"] = True
    with pytest.raises(CancelledError):
        client.post(PREFIX + "/run", json={"mode": "sovereigneg"})

    app = FastAPI()
    install_reporting_api(app, output=tmp_path, approved_scope=digest)
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as restarted:
        url = PREFIX + "/result?mode=sovereigneg"
        saved = restarted.get(url)
        assert saved.status_code == 200
        report = saved.json()
        assert report["status"] == "degraded" and report["model"] is None
        assert report["request_sha256"] == digest
        assert report["audit"] == {"write_report": "1", "llm_inference": "2"}
        assert [finding["technique"] for finding in report["findings"]] == ["T1486"]
        assert report["withheld"] == [{"technique": "T1490", "reasons": ["independent_attribution_missing"]}]
        fallback_digest = sha256(saved.content).hexdigest()
        assert saved.headers["etag"] == f'"{fallback_digest}"'
        download = restarted.get(PREFIX + "/result", params={
            "mode": "sovereigneg", "download": True, "expected_sha256": fallback_digest,
        })
        assert download.status_code == 200 and download.content == saved.content
        assert not restarted.get(PREFIX).json()["cloud_available"]
        assert restarted.post(PREFIX + "/run", json={"mode": "sovereigneg"}).status_code == 409
    assert len(requests) == 1
    assert [approval["action"] for approval in approvals] == ["write_report", "llm_inference"]


def test_legacy_attempt_marker_still_consumes_approval(center, tmp_path):
    client, approvals, requests, _ = center
    digest = client.get(PREFIX).json()["request_sha256"]
    marker = tmp_path / f"attempt-{digest}.lock"
    marker.write_text(digest, encoding="ascii")

    assert not client.get(PREFIX).json()["cloud_available"]
    assert client.get(PREFIX + "/result?mode=sovereigneg").status_code == 404
    assert client.post(PREFIX + "/run", json={"mode": "sovereigneg"}).status_code == 409
    assert marker.read_text(encoding="ascii") == digest
    assert not approvals and not requests


def test_reporting_deadline_bounds_a_slow_incremental_response(center, monkeypatch):
    client, _, requests, scenario = center
    config = reporting_api.load_config(load_env=False)
    provider = replace(config.get_provider("sovereigneg"), request_timeout_s=0.2)
    monkeypatch.setattr(reporting_api, "load_config", lambda **_: replace(
        config, providers={**config.providers, "sovereigneg": provider}))
    scenario["response_delays"] = (0.15, 0.15, 0.15)

    response = client.post(PREFIX + "/run", json={"mode": "sovereigneg"})
    assert response.status_code == 200
    report = response.json()
    assert report["status"] == "degraded" and "time limit" in report["notice"]
    assert "usage" not in report
    assert client.get(PREFIX + "/result?mode=sovereigneg&download=true").json() == report
    assert client.post(PREFIX + "/run", json={"mode": "sovereigneg"}).status_code == 409
    assert len(requests) == 1


def test_local_report_does_not_request_inference_and_cannot_supply_evidence(center):
    client, approvals, requests, _ = center
    assert client.post(PREFIX + "/run", json={"mode": "local", "snapshot": {}}).status_code == 422
    result = client.post(PREFIX + "/run", json={"mode": "local"})
    assert result.status_code == 200
    assert result.json()["model"] is None and result.json()["status"] == "local"
    assert client.get(PREFIX + "/result").json() == result.json()
    assert not requests
    assert [entry["action"] for entry in approvals] == ["write_report"]


def test_export_checks_exact_bytes_after_same_revision_rerun(center):
    client, _, requests, _ = center
    first = client.post(PREFIX + "/run", json={"mode": "local"})
    second = client.post(PREFIX + "/run", json={"mode": "local"})
    assert first.status_code == second.status_code == 200
    assert first.json()["source_sha256"] == second.json()["source_sha256"]
    assert first.json()["audit"] != second.json()["audit"]
    result = PREFIX + "/result"
    old_digest = sha256(first.content).hexdigest()
    assert client.get(result, params={"download": True, "expected_sha256": old_digest}).status_code == 409
    assert client.get(result, params={"download": True, "expected_sha256": "../report"}).status_code == 422
    current = client.get(result)
    assert current.content == second.content
    new_digest = sha256(current.content).hexdigest()
    assert current.headers["etag"] == f'"{new_digest}"'
    export = client.get(result, params={"download": True, "expected_sha256": new_digest})
    assert export.status_code == 200 and export.content == current.content
    assert not requests


def test_default_router_requires_exact_approval(center):
    app = FastAPI()
    install_reporting_api(app)
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
        assert not client.get(PREFIX).json()["cloud_available"]
        assert client.post(PREFIX + "/run", json={"mode": "sovereigneg"}).status_code == 409


def test_modified_archive_fails_before_admission(tmp_path):
    forged = tmp_path / "forged.json"
    forged.write_bytes(ARCHIVE.read_bytes() + b" ")
    with pytest.raises(ValueError, match="integrity"):
        review_archive(forged)



def test_authorized_activity_cannot_become_a_verified_finding(tmp_path):
    from dataclasses import asdict
    from hashlib import sha256

    from eval.attack_evidence_admission_v2 import VERSION
    from eval.fixtures.ai.attack_admission_v2 import issue
    from eval.fixtures.ai.attack_fact_registry_v1.demo import windows

    case, records = windows()
    case["schema_version"] = VERSION
    for source in case["sources"]:
        source["upstream"] = []
    next(row for row in case["assertions"] if row["role"] == "authorization")["value"] = "authorized"
    permission = (b"The Security log clear by BLUE\\operator on JUN-4 at 09:10 UTC "
                  b"was explicitly authorized in the signed maintenance window 09:05 to 09:15 UTC.")
    records["permission", 1] = permission
    digest = sha256(permission).hexdigest()
    next(row for row in case["records"] if row["id"] == "permission").update(
        sha256=digest, byte_length=len(permission))
    next(row for row in case["statements"] if row["id"] == "permission").update(
        sha256=digest, span=[0, len(permission)])
    manifest, authority = issue(case)
    archive = {
        "assessment_id": "synthetic-authorized-test", "title": "Authorized maintenance",
        "status": "completed", "snapshot": manifest.decode("ascii"), "custody": asdict(authority),
        "records": [{"id": key, "revision": revision, "text": value.decode()}
                    for (key, revision), value in records.items()],
    }
    path = tmp_path / "archive.json"
    path.write_bytes(json.dumps(archive, default=sorted).encode())
    verified = review_archive(path, sha256(path.read_bytes()).hexdigest())
    assert not verified["findings"]
    assert verified["withheld"] and verified["withheld"][0]["technique"] == "T1685.005"
    assert request_for(verified) is None
