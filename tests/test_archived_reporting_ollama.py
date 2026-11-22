import asyncio
from copy import deepcopy
from hashlib import sha256
import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai.providers.reporting_ollama import DESTINATION, MODEL, MODEL_DIGEST, REQUEST_BYTES, rank_verified
from ai.trustgate.client import TrustGateDecision
from console.backend import reporting_api
from console.backend.reporting_api import install_reporting_api
from pentagi.agents.archived_reporting import compose, review_archive

PREFIX = "/reporting/archive"
RESULT = PREFIX + "/result?mode=ollama"
SELECTION = {"highlights": ["T1486/E1.1"], "recommendations": ["T1486-1"], "emphasis": "observed_impact"}


@pytest.fixture
def center(monkeypatch, tmp_path):
    monkeypatch.setenv("KAYAN_REPORTING_LOCAL_RANKING", "1")
    decisions, requests = [], []
    baseline = review_archive()
    scenario = {}

    def load_archive():
        return {**deepcopy(baseline), **scenario.get("archive", {})}

    class Gate:
        async def authorize(self, **args):
            decisions.append(args)
            allowed = args["action"] != scenario.get("denied")
            return TrustGateDecision("reporting_agent", args["action"], allowed, "ALLOW" if allowed else "DENY",
                                     "test policy", None, f"test-{len(decisions)}")

        def close(self):
            pass

    async def loopback(request):
        requests.append(request)
        assert request.url.host == "127.0.0.1" and request.url.port == 11534
        if scenario.get("change_at") == request.method:
            scenario["archive"] = {"review_status": "submitted"}
        if request.method == "GET":
            return httpx.Response(200, json={"models": [
                {"name": MODEL, "digest": scenario.get("digest", MODEL_DIGEST),
                 "details": {"quantization_level": "Q4_K_M"}},
            ]})
        if scenario.get("delay"):
            await asyncio.sleep(scenario["delay"])
        if scenario.get("redirect"):
            return httpx.Response(302, headers={"Location": "https://invalid.example/api/chat"})
        if scenario.get("oversized_reply"):
            return httpx.Response(200, content=b"x" * 65537)
        return httpx.Response(200, json={
            "model": MODEL, "done": True, "done_reason": "stop", "prompt_eval_count": 400, "eval_count": 31,
            "message": {"role": "assistant", "content": json.dumps(SELECTION)},
            **scenario.get("response", {}),
        })

    async def rank(body, **kwargs):
        return await rank_verified(body, transport=httpx.MockTransport(loopback), **kwargs)

    app = FastAPI()
    install_reporting_api(app, output=tmp_path, load_archive=load_archive, make_gate=lambda _: Gate(), rank_local=rank)
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 5080)) as client:
        yield client, decisions, requests, scenario, baseline


def run(client):
    saved = client.post(PREFIX + "/run", json={"mode": "ollama"})
    assert saved.status_code == 200, saved.text
    exported = client.get(RESULT + f"&download=true&expected_sha256={sha256(saved.content).hexdigest()}")
    assert exported.status_code == 200 and exported.content == saved.content
    return saved.json()


def test_local_ranking_keeps_an_exportable_report_when_inference_is_denied(center):
    client, decisions, requests, scenario, baseline = center
    scenario["denied"] = "llm_inference"
    result = run(client)
    assert result["status"] == "degraded" and result["provider"] is None
    assert result["audit"]["llm_inference_denied"] == "test-2"
    assert [entry["action"] for entry in decisions] == ["write_report", "llm_inference"]
    assert result["summary"] == compose(baseline)["summary"]
    assert result["findings"] == baseline["findings"] and result["withheld"] == baseline["withheld"]
    assert requests == []


def test_local_ranking_selects_only_verified_evidence_and_exports_identical_bytes(center, tmp_path):
    client, decisions, requests, _, baseline = center
    setup = client.get(PREFIX).json()
    assert setup["local_ranking_enabled"] and setup["local_ranking_supported"]
    assert not setup["cloud_available"]
    result = run(client)
    assert (result["status"], result["provider"], result["model"]) == ("selected", "ollama", MODEL)
    assert result["finish_reason"] == "stop"
    assert result["usage"]["input"] == 400 and result["usage"]["output"] == 31
    assert "reasoning" not in result["usage"]
    assert [item["id"] for item in result["summary"]] == ["E1.1", "E2.1"]
    assert [row["technique"] for row in result["findings"]] == ["T1486"]
    assert [row["technique"] for row in result["withheld"]] == ["T1490"]
    assert result["findings"] == baseline["findings"] and result["withheld"] == baseline["withheld"]
    assert [entry["action"] for entry in decisions] == ["write_report", "llm_inference"]
    assert [request.method for request in requests] == ["GET", "POST"]
    body = requests[1].content
    assert str(requests[1].url) == DESTINATION and len(body) <= REQUEST_BYTES
    envelope = json.loads(body)
    assert envelope["model"] == MODEL and envelope["stream"] is False and "tools" not in envelope
    prompt = json.loads(envelope["messages"][1]["content"])
    assert set(prompt) == {"admitted", "defensive_controls"}
    assert all(row["id"].startswith("T1486/") for row in prompt["admitted"])
    assert decisions[-1]["tool_args"]["request_sha256"] == sha256(DESTINATION.encode() + b"\0" + body).hexdigest()
    assert decisions[-1]["tool_args"]["model_sha256"] == MODEL_DIGEST
    assert decisions[-1]["tool_args"]["request_sha256"] == result["request_sha256"] != setup["request_sha256"]

    saved, = tmp_path.glob("*-ollama.json")
    saved.write_text(json.dumps({**result, "provider": "sovereigneg"}), encoding="utf-8")
    assert client.get(RESULT).status_code == 409


@pytest.mark.parametrize(("change", "methods"), [
    ({"digest": "different"}, ["GET"]),
    ({"response": {"model": "different"}}, ["GET", "POST"]),
    ({"response": {"done_reason": "length"}}, ["GET", "POST"]),
    ({"response": {"eval_count": True}}, ["GET", "POST"]),
    ({"response": {"message": {"role": "assistant", "content": json.dumps(
        {**SELECTION, "highlights": ["T1490/E4.1"]},
    )}}}, ["GET", "POST"]),
    ({"oversized_reply": True}, ["GET", "POST"]),
    ({"redirect": True}, ["GET", "POST"]),
])
def test_local_runtime_or_selection_failure_falls_back_without_retry(center, change, methods):
    client, _, requests, scenario, baseline = center
    scenario.update(change)
    result = run(client)
    assert result["status"] == "degraded" and result["provider"] is None
    assert result["summary"] == compose(baseline)["summary"]
    assert result["withheld"] == baseline["withheld"]
    assert [request.method for request in requests] == methods


def test_local_ranker_total_deadline_returns_deterministic_output(center, monkeypatch):
    client, _, requests, scenario, _ = center
    monkeypatch.setattr(reporting_api, "LOCAL_TIMEOUT_SECONDS", 0.08)
    scenario["delay"] = 1
    result = run(client)
    assert result["status"] == "degraded" and "time limit" in result["notice"]
    assert [request.method for request in requests] == ["GET", "POST"]


@pytest.mark.parametrize(("stage", "methods"), [("GET", ["GET"]), ("POST", ["GET", "POST"])])
def test_stale_archive_cannot_publish_local_ranking(center, stage, methods):
    client, _, requests, scenario, _ = center
    scenario["change_at"] = stage
    assert client.post(PREFIX + "/run", json={"mode": "ollama"}).status_code == 409
    assert [request.method for request in requests] == methods
    assert client.get(RESULT).status_code == 404


@pytest.mark.parametrize("condition", ["disabled", "no_findings", "oversized_input", "test_only"])
def test_local_ranking_unsupported_request_uses_only_the_write_grant(center, monkeypatch, condition):
    client, decisions, requests, scenario, baseline = center
    if condition == "disabled":
        monkeypatch.delenv("KAYAN_REPORTING_LOCAL_RANKING")
    elif condition == "no_findings":
        scenario["archive"] = {"findings": []}
    elif condition == "test_only":
        scenario["archive"] = {"custody_test_only": True}
    else:
        baseline["findings"][0]["sources"][0]["statements"] = ["x" * REQUEST_BYTES]
    result = run(client)
    assert result["status"] == "degraded" and result["provider"] is None
    assert [entry["action"] for entry in decisions] == ["write_report"] and not requests


def test_denied_write_avoids_local_inference_and_persistence(center):
    client, decisions, requests, scenario, _ = center
    scenario["denied"] = "write_report"
    assert client.post(PREFIX + "/run", json={"mode": "ollama"}).status_code == 403
    assert [entry["action"] for entry in decisions] == ["write_report"] and not requests
    assert client.get(RESULT).status_code == 404
