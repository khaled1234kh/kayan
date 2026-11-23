import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from threading import Barrier

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai.providers.reporting_sovereign import DESTINATION, MODEL, ReportingSovereignProvider
from ai.trustgate.client import TrustGateDecision
from console.backend.reporting_api import install_reporting_api
from eval.archived_reporting_projection import compare, fixtures
from pentagi.agents.archived_reporting import compose, request_for, review_archive, review_archive_document


def reviewed(case):
    raw, *_ = dict(fixtures())[case]
    return review_archive_document(json.loads(raw), sha256(raw).hexdigest())


def choice(*ids):
    return json.dumps({"highlights": ids, "recommendations": ["T1486-1"], "emphasis": "observed_impact"})


def provider_reply():
    return httpx.Response(200, json={
        "model": MODEL,
        "choices": [{"finish_reason": "stop", "message": {"content": choice("F1/S1")}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 13,
                  "completion_tokens_details": {"reasoning_tokens": 0}},
    })


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
def test_reporting_api_preserves_occurrences_without_cloud_approval(tmp_path, case, expected):
    report = reviewed(case)
    assert bool(request_for(report)) == bool(expected)

    class Gate:
        def close(self):
            pass

        async def authorize(self, **arguments):
            assert arguments["action"] == "write_report"
            return TrustGateDecision("reporting_agent", "write_report", True, "ALLOW", "fixture", None, "audit-occurrence")

    def provider(*args, **kwargs):
        pytest.fail("An unapproved report must not initialize a cloud provider")

    app = FastAPI()
    install_reporting_api(app, load_archive=lambda: report, output=tmp_path,
                          make_gate=lambda _: Gate(), make_provider=provider, approved_scope="")
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
        archive_status = client.get("/reporting/archive").json()
        assert not archive_status["cloud_available"]
        assert archive_status["cloud_selection_supported"] == bool(expected)
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


def test_occurrence_selection_resolves_shared_source_ids_without_overwriting():
    report = reviewed("repeated-supported")
    # The same source address may legitimately have distinct context in two findings.
    report["findings"][1]["sources"][0]["id"] = report["findings"][0]["sources"][0]["id"]
    _, schema, _ = request_for(report)
    ids = schema["json_schema"]["schema"]["properties"]["highlights"]["items"]["enum"]
    assert len(ids) == len(set(ids)) and {"F1/S1", "F2/S1"} <= set(ids)
    picked = compose(report, choice("F2/S1", "F1/S1"))
    assert [row["occurrence"] for row in picked["summary"]] == ["incident-2", "incident-1"]
    assert picked["summary"][0]["statements"] != picked["summary"][1]["statements"]
    assert picked["findings"] == report["findings"]


@pytest.mark.parametrize("ids", [
    ("T1486/E1.1",), ("W1/S1",), ("F2/S1",), ("F1/S1", "F1/S1"), ("F1/S99",),
])
def test_occurrence_selection_rejects_ambiguous_withheld_or_duplicate_ids(ids):
    report = reviewed("repeated-mixed")
    with pytest.raises(ValueError, match="unsupported or duplicate"):
        compose(report, choice(*ids))


def test_occurrence_selection_rejects_duplicate_json_fields():
    report = reviewed("repeated-mixed")
    ambiguous = '{"highlights":["W1/S1"],"highlights":["F1/S1"],' \
                '"recommendations":["T1486-1"],"emphasis":"observed_impact"}'
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        compose(report, ambiguous)


def test_occurrence_packet_contains_only_selected_archive_public_context():
    report = reviewed("repeated-mixed")
    report.update(assessment_id="private-assessment-label", report_revision="local-review-label",
                  bind_request_to_assessment=True)
    report["withheld"][0]["reasons"] = ["private-withheld-reason"]
    report["withheld"][0]["occurrence"] = "private-withheld-occurrence"
    report["findings"][0]["review_bindings"] = [{"reviewer": "private-reviewer-label"}]
    messages, schema, digest = request_for(report)
    packet = json.loads(messages[-1].content)
    assert packet["withheld_occurrences"] == [{"ref": "W1", "technique": "T1486"}]
    assert {row["finding"] for row in packet["admitted"]} == {"F1"}
    assert set(schema["json_schema"]["schema"]["properties"]["recommendations"]["items"]["enum"]) == {
        "T1486-1", "T1486-2",
    }
    assert "private-" not in messages[-1].content and "local-review-label" not in messages[-1].content
    assert request_for({**report, "report_revision": "changed-review"})[2] != digest
    assert request_for({**report, "assessment_id": "changed-assessment"})[2] != digest
    assert request_for(review_archive())[2] != digest


def test_occurrence_cloud_path_requires_fresh_exact_scope_and_attempts_once(tmp_path, monkeypatch):
    monkeypatch.setenv("SOVEREIGNEG_API_KEY", "synthetic-test-key")
    report = reviewed("repeated-mixed")
    digest = request_for(report)[2]
    decisions, requests = [], []

    class Gate:
        def close(self):
            pass

        async def authorize(self, **arguments):
            decisions.append(arguments)
            action = arguments["action"]
            return TrustGateDecision("reporting_agent", action, True, "ALLOW", "fixture", None, f"audit-{action}")

    def respond(request):
        requests.append(request)
        return provider_reply()

    app = FastAPI()
    install_reporting_api(app, load_archive=lambda: report, output=tmp_path, make_gate=lambda _: Gate(),
                          make_provider=lambda config, **kw: ReportingSovereignProvider(
                              config, transport=httpx.MockTransport(respond), **kw))
    run = "/reporting/archive/run"
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
        monkeypatch.setenv("KAYAN_REPORTING_APPROVED_SHA256", request_for(review_archive())[2])
        assert client.post(run, json={"mode": "sovereigneg"}).status_code == 409
        assert not decisions and not requests
        monkeypatch.setenv("KAYAN_REPORTING_APPROVED_SHA256", digest)
        result = client.post(run, json={"mode": "sovereigneg"})
        assert result.status_code == 200 and result.json()["status"] == "selected"
        assert client.post(run, json={"mode": "sovereigneg"}).status_code == 409
    body = result.json()
    assert body["summary"][0]["occurrence"] == "incident-1"
    assert body["withheld"][0]["occurrence"] == "incident-2"
    assert [row["action"] for row in decisions] == ["write_report", "llm_inference"]
    assert decisions[1]["tool_args"]["request_sha256"] == digest == body["request_sha256"]
    request, = requests
    assert str(request.url) == DESTINATION
    assert json.loads(request.content)["response_format"]["json_schema"]["name"] == "archived_reporting_occurrences_v2"


@pytest.mark.parametrize("change_at, attempts", [("authorization", 0), ("provider", 1)])
@pytest.mark.parametrize("change", ["custody", "approval"])
def test_cloud_request_does_not_publish_after_scope_changes(tmp_path, monkeypatch, change_at, attempts, change):
    monkeypatch.setenv("SOVEREIGNEG_API_KEY", "synthetic-test-key")
    archive = reviewed("repeated-mixed")
    digest = request_for(archive)[2]
    monkeypatch.setenv("KAYAN_REPORTING_APPROVED_SHA256", digest)
    current = archive
    requests = []

    def invalidate_scope():
        nonlocal current
        if change == "approval":
            monkeypatch.delenv("KAYAN_REPORTING_APPROVED_SHA256")
        else:
            current = {**archive, "report_revision": "fixture-revision-2", "findings": []}

    class Gate:
        def close(self):
            pass

        async def authorize(self, **arguments):
            action = arguments["action"]
            if action == "llm_inference" and change_at == "authorization":
                invalidate_scope()
            return TrustGateDecision("reporting_agent", action, True, "ALLOW", "fixture", None, f"audit-{action}")

    def respond(request):
        requests.append(request)
        if change_at == "provider":
            invalidate_scope()
        return provider_reply()

    app = FastAPI()
    install_reporting_api(app, load_archive=lambda: current, output=tmp_path,
                          make_gate=lambda _: Gate(),
                          make_provider=lambda config, **kw: ReportingSovereignProvider(
                              config, transport=httpx.MockTransport(respond), **kw))
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
        result = client.post("/reporting/archive/run", json={"mode": "sovereigneg"})
        assert result.status_code == 409
        saved = client.get("/reporting/archive/result?mode=sovereigneg")
        if attempts and change == "approval":
            assert saved.status_code == 200 and saved.json()["status"] == "degraded"
        else:
            assert saved.status_code == 404
    assert len(requests) == attempts
    assert len(list(tmp_path.glob("attempt-*.lock"))) == attempts
    assert not list(tmp_path.glob("*-sovereigneg.json"))


def test_competing_app_instances_reserve_one_attempt(tmp_path, monkeypatch):
    monkeypatch.setenv("SOVEREIGNEG_API_KEY", "synthetic-test-key")
    report = reviewed("repeated-mixed")
    digest = request_for(report)[2]
    checkpoint = Barrier(2)
    requests = []

    class Gate:
        def close(self):
            pass

        async def authorize(self, **arguments):
            action = arguments["action"]
            if action == "llm_inference":
                await asyncio.to_thread(checkpoint.wait, 5)
            return TrustGateDecision("reporting_agent", action, True, "ALLOW", "fixture", None, f"audit-{action}")

    def respond(request):
        requests.append(request)
        return provider_reply()

    def run():
        # Separate FastAPI instances have separate asyncio locks.
        app = FastAPI()
        install_reporting_api(app, load_archive=lambda: report, output=tmp_path,
                              make_gate=lambda _: Gate(), approved_scope=digest,
                              make_provider=lambda config, **kw: ReportingSovereignProvider(
                                  config, transport=httpx.MockTransport(respond), **kw))
        with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
            return client.post("/reporting/archive/run", json={"mode": "sovereigneg"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = [future.result(timeout=12) for future in (pool.submit(run), pool.submit(run))]
    assert sorted(item.status_code for item in responses) == [200, 409]
    assert len(requests) == 1
    assert list(tmp_path.glob("attempt-*.lock")) == [tmp_path / f"attempt-{digest}.lock"]
