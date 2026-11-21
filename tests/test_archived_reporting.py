import asyncio
import json
from concurrent.futures import CancelledError
from dataclasses import asdict, replace
from hashlib import sha256

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai.providers.reporting_sovereign import DESTINATION, MODEL, ReportingSovereignProvider
from ai.trustgate.client import TrustGateDecision
from console.backend import reporting_api
from console.backend.reporting_api import install_reporting_api
from pentagi.agents.archived_reporting import ARCHIVE, compose, request_for, review_archive

SELECTION = {"highlights": ["T1486/E2.1"], "recommendations": ["T1486-1"], "emphasis": "observed_impact"}
PREFIX = "/reporting/archive"


@pytest.fixture
def center(tmp_path, monkeypatch):
    monkeypatch.setenv("SOVEREIGNEG_API_KEY", "test-only-placeholder")
    approvals, requests = [], []
    scenario = {"content": json.dumps(SELECTION), "finish": "stop", "denied": None}
    report = review_archive()
    config = {"approved_scope": request_for(report)[2]}

    def load_archive():
        if scenario.get("archive_missing"):
            raise LookupError("archive removed from test catalogue")
        return {**report, **scenario.get("archive_fields", {})}

    class Gate:
        async def authorize(self, **args):
            approvals.append(args)
            if scenario.get("change_at") == args["action"]:
                await asyncio.sleep(0)
                scenario.update(scenario["change"])
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
        if scenario.get("change_at") == "provider_response":
            scenario.update(scenario["change"])
        return httpx.Response(200, json={
            "model": scenario.get("model", MODEL),
            "choices": [{"finish_reason": scenario["finish"], "message": {"content": scenario["content"]}}],
            "usage": {"prompt_tokens": scenario.get("prompt_tokens", 200),
                      "completion_tokens": scenario.get("completion_tokens", 22),
                      "completion_tokens_details": {"reasoning_tokens": 0}},
        })

    app = FastAPI()
    install_reporting_api(
        app, output=tmp_path, load_archive=load_archive, make_gate=lambda _: Gate(), **config,
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


def test_archived_reporting_marks_appended_actions_in_saved_report_and_exact_export(center):
    client, approvals, requests, scenario = center
    scenario["content"] = json.dumps({**SELECTION, "highlights": ["T1486/E1.1"]})
    result = client.post(PREFIX + "/run", json={"mode": "sovereigneg"})
    assert result.status_code == 200
    report = result.json()
    assert report["status"] == "selected"
    assert [(item["id"], item.get("selection_origin")) for item in report["summary"]] == [
        ("E1.1", None), ("E2.1", "verified_action_supplement"),
    ]
    assert report["summary_coverage"] == {
        "admitted_occurrences": 1, "covered_occurrences": 1, "action_covered_occurrences": 1,
    }
    review = review_archive()
    assert report["findings"] == review["findings"] and report["withheld"] == review["withheld"]
    assert report["recommendations"] == review["findings"][0]["actions"][:1]
    assert [entry["action"] for entry in approvals] == ["write_report", "llm_inference"]
    assert len(requests) == 1
    download = client.get(PREFIX + "/result", params={
        "mode": "sovereigneg", "download": True, "expected_sha256": sha256(result.content).hexdigest(),
    })
    assert download.status_code == 200 and download.content == result.content


@pytest.mark.parametrize(("checkpoint", "attempts"), [
    ("write_report", 0), ("llm_inference", 0), ("provider_response", 1),
])
def test_archive_metadata_change_with_same_digest_blocks_cloud_publication(center, tmp_path, checkpoint, attempts):
    client, approvals, requests, scenario = center
    scenario["archive_fields"] = {"review_status": "verified"}
    initial = client.get(PREFIX).json()
    digest = initial["request_sha256"]
    scenario.update(change_at=checkpoint, change={"archive_fields": {"review_status": "submitted"}})
    reply = client.post(PREFIX + "/run", json={"mode": "sovereigneg"})
    assert reply.status_code == 409
    assert "findings" not in reply.json()
    assert [entry["action"] for entry in approvals] == (
        ["write_report"] if checkpoint == "write_report" else ["write_report", "llm_inference"]
    )
    assert not list(tmp_path.glob("*.json"))
    assert len(requests) == attempts
    assert len(list(tmp_path.glob("attempt-*.lock"))) == attempts
    current = client.get(PREFIX).json()
    assert current["request_sha256"] == digest and current["review_status"] == "submitted"
    assert current["cloud_available"] is (attempts == 0)
    assert client.get(PREFIX + "/result?mode=sovereigneg").status_code == (409 if attempts else 404)


def test_archive_removed_during_write_decision_is_reported_as_conflict(center, tmp_path):
    client, _, requests, scenario = center
    scenario.update(change_at="write_report", change={"archive_missing": True})
    response = client.post(PREFIX + "/run", json={"mode": "local"})
    assert response.status_code == 409
    assert not list(tmp_path.iterdir()) and not requests


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


@pytest.mark.parametrize("change", [
    {"assessment_id": "different-archive"},
    {"findings": []},
    {"withheld": []},
    {"verification": "independent_custody"},
    {"summary": [{"technique": "T1486", "id": "E2.1", "roles": ["mechanic"], "statements": ["Changed excerpt"]}]},
    {"summary_coverage": {"admitted_occurrences": 1, "covered_occurrences": 1, "action_covered_occurrences": 0}},
    {"summary_coverage": {"admitted_occurrences": True, "covered_occurrences": 1, "action_covered_occurrences": 1}},
    None,
])
def test_modified_saved_report_is_rejected_when_opened_or_exported_after_restart(center, tmp_path, change):
    client, _, requests, _ = center
    before = client.post(PREFIX + "/run", json={"mode": "local"})
    assert before.status_code == 200
    saved, = tmp_path.glob("*-local.json")
    altered = json.dumps({**before.json(), **change}).encode() if change is not None else b"{"
    saved.write_bytes(altered)
    app = FastAPI()
    install_reporting_api(app, output=tmp_path)
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as reopened:
        assert reopened.get(PREFIX + "/result").status_code == 409
        assert reopened.get(PREFIX + "/result", params={
            "download": True, "expected_sha256": sha256(altered).hexdigest(),
        }).status_code == 409
    assert saved.read_bytes() == altered and not requests


def test_legacy_selected_report_bytes_are_preserved_without_coverage_metadata(center, tmp_path):
    client, _, requests, _ = center
    current = client.post(PREFIX + "/run", json={"mode": "sovereigneg"}).json()
    current.pop("summary_coverage")
    current.pop("finish_reason")
    saved, = tmp_path.glob("*-sovereigneg.json")
    legacy = json.dumps(current).encode()
    saved.write_bytes(legacy)
    assert client.get(PREFIX + "/result", params={
        "mode": "sovereigneg", "download": True, "expected_sha256": sha256(legacy).hexdigest(),
    }).content == legacy
    assert len(requests) == 1


def test_modified_recovery_report_is_withheld_and_the_attempt_remains_consumed(center, tmp_path):
    client, _, requests, scenario = center
    scenario["cancelled"] = True
    with pytest.raises(CancelledError):
        client.post(PREFIX + "/run", json={"mode": "sovereigneg"})
    reservation, = tmp_path.glob("attempt-*.lock")
    body = json.loads(reservation.read_bytes())
    body["summary"][0]["statements"] = ["Changed excerpt"]
    altered = json.dumps(body).encode()
    reservation.write_bytes(altered)
    assert client.get(PREFIX + "/result?mode=sovereigneg").status_code == 409
    assert client.post(PREFIX + "/run", json={"mode": "sovereigneg"}).status_code == 409
    assert reservation.read_bytes() == altered and len(requests) == 1


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

def test_pinned_slate_request_identity_is_unchanged():
    assert request_for(review_archive())[2] == "0173f8049d8c4190487ac75f321d976dce58c9b557005dc5a1c2dbfece7d0fb0"


def signed_windows_report(tmp_path, *, authorized=False, include_secondary=True):
    from eval.attack_evidence_admission_v2 import VERSION
    from eval.fixtures.ai.attack_admission_v2 import issue
    from eval.fixtures.ai.attack_fact_registry_v1.demo import windows

    case, records = windows()
    case["schema_version"] = VERSION
    for source in case["sources"]:
        source["upstream"] = []
    if authorized:
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
    if not include_secondary:
        del records["logon", 1]
    archive = {
        "assessment_id": case["case_id"], "title": "Synthetic Windows assessment",
        "status": "completed", "snapshot": manifest.decode("ascii"), "custody": asdict(authority),
        "records": [{"id": key, "revision": revision, "text": value.decode()}
                    for (key, revision), value in records.items()],
    }
    path = tmp_path / "archive.json"
    path.write_bytes(json.dumps(archive, default=sorted).encode())
    return review_archive(path, sha256(path.read_bytes()).hexdigest())


def test_verified_multi_statement_finding_keeps_secondary_support(tmp_path):
    report = signed_windows_report(tmp_path)
    finding, = report["findings"]
    assert not report["withheld"]
    assert finding["technique"] == "T1685.005" and finding["occurrence"] == "clear-event"
    sources = {source["id"]: source for source in finding["sources"]}
    assert set(sources) == {"E1.1", "E1.2", "E2.1", "E3.1"}
    assert "mechanic" in sources["E1.1"]["roles"]
    assert sources["E1.2"]["statements"] and "mechanic" not in sources["E1.2"]["roles"]
    assert [source["id"] for source in compose(report)["summary"]] == ["E1.1"]


def test_multi_statement_finding_still_requires_verified_secondary_support(tmp_path):
    with pytest.raises(ValueError, match="admission could not verify"):
        signed_windows_report(tmp_path, include_secondary=False)


def test_authorized_activity_cannot_become_a_verified_finding(tmp_path):
    verified = signed_windows_report(tmp_path, authorized=True)
    assert not verified["findings"]
    assert verified["withheld"] and verified["withheld"][0]["technique"] == "T1685.005"
    assert "authorization_unverified" in verified["withheld"][0]["reasons"]
    assert request_for(verified) is None
