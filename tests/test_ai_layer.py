"""Offline tests for the SovereignEG provider, MITRE RAG and parallel graph.

No real network calls: provider HTTP is mocked with httpx.MockTransport and
TrustGate is replaced with a fake that records authorization decisions.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from hashlib import sha256
from zipfile import ZipFile

import httpx
import pytest

from ai.config import ProviderConfig, load_config
from ai.mitre.rag import MitreEvidence, MitreRAG
from ai.mitre.stix import MitreTechnique
from ai.orchestrator import run_assessment
from ai.providers.base import LLMResponse
from ai.trustgate.client import TrustGateDecision


def _provider_config(monkeypatch, **overrides) -> ProviderConfig:
    monkeypatch.setenv("SOVEREIGNEG_API_KEY", "test-key")
    values = dict(
        name="sovereigneg",
        base_url="https://backend.sovereigneg.com/v1",
        api_key_env="SOVEREIGNEG_API_KEY",
        chat_model="test-model",
        embedding_model="test-embed",
        max_concurrency=2,
        request_timeout_s=10,
    )
    values.update(overrides)
    return ProviderConfig(**values)


def _sov_provider(config, handler):
    from ai.providers.sovereign import SovereignEGProvider

    return SovereignEGProvider(config, transport=httpx.MockTransport(handler))


def test_chat_parses_reasoning_and_records_usage(monkeypatch):
    config = _provider_config(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "choices": [
                {
                    "message": {
                        "content": '{"agent":"security","summary":"ok"}',
                        "reasoning_content": "thinking",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "completion_tokens_details": {"reasoning_tokens": 12},
            },
            "model": "test-model",
        }
        return httpx.Response(200, json=body)

    provider = _sov_provider(config, handler)

    async def run():
        response = await provider.chat([], max_tokens=100)
        return response, provider.usage.snapshot()

    response, usage = asyncio.run(run())
    assert response.content.startswith('{"agent"')
    assert response.reasoning == "thinking"
    assert response.reasoning_tokens == 12
    assert usage["requests"] == 1
    assert usage["completion_tokens"] == 20


def test_chat_retries_rate_limit(monkeypatch):
    config = _provider_config(monkeypatch, max_retries=2)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, text="rate limited", headers={"retry-after": "0"})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {},
                "model": "test-model",
            },
        )

    provider = _sov_provider(config, handler)
    asyncio.run(provider.chat([]))
    assert calls["n"] == 2


def _stix_config(tmp_path):
    def stix(kind, key, name, external_id, **fields):
        return {"type": kind, "id": key, "name": name,
                "external_references": [{"source_name": "mitre-attack", "external_id": external_id}],
                **fields}

    objects = [
        {"type": "x-mitre-collection", "name": "Enterprise ATT&CK", "x_mitre_version": "20.1"},
        stix("attack-pattern", "parent", "Command interpreter", "T1059"),
        stix("attack-pattern", "child", "PowerShell", "T1059.001", x_mitre_is_subtechnique=True,
             x_mitre_version="1.6", description="PowerShell interpreter activity in endpoint telemetry."),
        stix("attack-pattern", "retired", "Retired", "T1234", revoked=True),
        stix("attack-pattern", "old", "Deprecated", "T1235", x_mitre_deprecated=True),
        stix("course-of-action", "m1", "Audit", "M1047"),
        stix("course-of-action", "m2", "Execution policy", "M1038"),
        {"type": "relationship", "relationship_type": "subtechnique-of", "source_ref": "child", "target_ref": "parent"},
        {"type": "relationship", "relationship_type": "mitigates", "source_ref": "m1", "target_ref": "child"},
        {"type": "relationship", "relationship_type": "mitigates", "source_ref": "m2", "target_ref": "child"},
    ]
    raw = json.dumps({"type": "bundle", "objects": objects}).encode()
    path = tmp_path / "pins.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr("enterprise.json", raw)
    return replace(load_config(load_env=False).mitre, archive_path=path,
                   archive_member="enterprise.json", sha256=sha256(raw).hexdigest())


def test_rag_retrieval_and_technique_id_validation(tmp_path):
    async def run():
        config = _stix_config(tmp_path)
        rag = MitreRAG(config)
        assert await rag.build() == 2
        evidence, = await rag.retrieve("PowerShell execution", top_k=1)
        assert evidence.technique_id == "T1059.001"
        assert evidence.bundle_sha256 == config.sha256 and evidence.object_version == "1.6"
        assert evidence.stix_id == "child"
        technique = rag.techniques[1]
        assert technique.parent_id == "T1059" and technique.mitigation_ids == ("M1038", "M1047")
        known, unknown = rag.validate_technique_ids(["T1059.001", "T1234", "T1235", "T9999"])
        assert known == ["T1059.001"]
        assert unknown == ["T1234", "T1235", "T9999"]
    asyncio.run(run())


@pytest.mark.parametrize("field,error", [("sha256", "SHA-256"), ("version", "version")])
def test_bad_corpus_identity_fails_closed(tmp_path, field, error):
    config = replace(_stix_config(tmp_path), **{field: "wrong"})
    rag = MitreRAG(config)
    with pytest.raises(ValueError, match=error):
        asyncio.run(rag.build())
    assert not rag.ready


class _FakeRegistry:
    def __init__(self, config):
        self.config = config

    async def chat(self, messages, **kwargs):
        return LLMResponse(
            content=json.dumps(
                {
                    "agent": "fake",
                    "summary": "PowerShell execution is evidenced.",
                    "findings": [
                        {
                            "technique_id": "T1059.001",
                            "tactic": "execution",
                            "claim": "Encoded PowerShell was executed.",
                            "evidence_refs": ["E1"],
                            "confidence": "high",
                            "assumptions": [],
                        }
                    ],
                    "recommendations": ["Review PowerShell logs."],
                    "citations": ["T1059.001"],
                }
            ),
            model="fake-model",
            provider="fake",
        )


class _FakeGate:
    def __init__(self, allowed=True):
        self.allowed = allowed

    async def require(self, **kwargs):
        assert kwargs["agent_role"] == kwargs["agent_id"]
        assert kwargs["agent_role"].startswith("ai-")
        if not self.allowed:
            raise PermissionError("test denial")
        return TrustGateDecision(
            agent=kwargs["agent_id"],
            action=kwargs["action"],
            allowed=True,
            decision="ALLOW",
            reason="test",
            policy_id=None,
            audit_entry_id="test",
        )


def _fake_rag():
    config = replace(load_config(load_env=False), provider="ollama")
    technique = MitreTechnique(
        technique_id="T1059.001",
        name="PowerShell",
        description="PowerShell execution",
        tactics=("execution",),
        detection="",
        mitigations=(),
        url="https://attack.mitre.org/techniques/T1059/001",
        raw_text="T1059.001 PowerShell",
    )

    rag = MitreRAG(config.mitre)
    rag.techniques = [technique]
    rag._index = (None, None)

    async def retrieve(query, top_k=5):
        return [
            MitreEvidence(
                technique_id="T1059.001",
                name="PowerShell",
                score=0.9,
                excerpt="PowerShell execution evidence",
                url=technique.url,
                tactics=("execution",),
            )
        ]

    rag.retrieve = retrieve  # type: ignore[method-assign]
    return config, rag


def test_parallel_graph_runs_four_agents():
    config, rag = _fake_rag()

    async def run():
        return await run_assessment(
            config=config,
            registry=_FakeRegistry(config),  # type: ignore[arg-type]
            rag=rag,
            gate=_FakeGate(),  # type: ignore[arg-type]
            founder_request="Analyze PowerShell execution alerts",
            engagement_id="test-parallel",
        )

    result = asyncio.run(run())
    assert len(result["agent_results"]) == 4
    assert all(d["allowed"] for d in result["trustgate_decisions"])
    techniques = [f["technique_id"] for f in result["consolidated"]["findings"]]
    assert "T1059.001" in techniques


def test_trustgate_denial_blocks_inference():
    config, rag = _fake_rag()

    async def run():
        return await run_assessment(
            config=config,
            registry=_FakeRegistry(config),  # type: ignore[arg-type]
            rag=rag,
            gate=_FakeGate(allowed=False),  # type: ignore[arg-type]
            founder_request="Analyze PowerShell execution alerts",
            engagement_id="test-denied",
        )

    result = asyncio.run(run())
    assert result["status"] == "withheld"
    assert "agent_results" not in result and "consolidated" not in result
    assert all(not item["allowed"] for item in result["trustgate_decisions"])


def test_rate_limiter_enforces_sliding_window():
    from ai.providers.base import RateLimiter

    limiter = RateLimiter(max_calls=2, period_s=0.15)

    async def run():
        start = asyncio.get_running_loop().time()
        for _ in range(3):
            await limiter.acquire()
        return asyncio.get_running_loop().time() - start

    # Two calls are free; the third must wait for the window to slide.
    assert asyncio.run(run()) >= 0.14


def test_rate_limiter_disabled_when_zero():
    from ai.providers.base import RateLimiter

    asyncio.run(RateLimiter(0).acquire())  # returns immediately, no error


def test_config_parses_student_plan_limits():
    config = load_config()
    assert config.primary.max_concurrency == 2
    assert config.primary.requests_per_minute == 20


@pytest.mark.parametrize("method,path", [
    ("POST", "/ai/assess"), ("POST", "/ai/mitre/reindex"), ("GET", "/ai/assess/fake"),
])
def test_experimental_http_refuses_jobs_without_needing_credentials(monkeypatch, method, path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai.api import install_ai_api

    def forbidden(*args, **kwargs):
        pytest.fail("Status or paused job attempted to initialize secrets or network")

    app = FastAPI()
    install_ai_api(app)
    monkeypatch.setattr("ai.config.load_dotenv", forbidden)
    monkeypatch.setattr(httpx, "AsyncClient", forbidden)
    with TestClient(app) as client:
        assert client.get("/ai/status").json()["enabled"] is False
        assert client.get("/ai/usage").json() == {}
        assert client.request(method, path).status_code == 503


@pytest.mark.parametrize("cloud,engagement", [(True, "independent-job"), (False, None)])
def test_graph_rejects_cloud_and_missing_scope_before_work(cloud, engagement):
    config = load_config(load_env=False)
    if not cloud:
        config = replace(config, provider="ollama")
    with pytest.raises(PermissionError):
        asyncio.run(run_assessment(config=config, registry=None, rag=None, gate=None,
                                   founder_request="Fictional audit record", engagement_id=engagement))


def test_report_denial_withholds_successful_agent_outputs():
    config, rag = _fake_rag()

    class ReportDenied(_FakeGate):
        async def require(self, **kwargs):
            if kwargs["action"] == "write_report":
                raise PermissionError("report withheld")
            return await super().require(**kwargs)

    result = asyncio.run(run_assessment(
        config=config, registry=_FakeRegistry(config), rag=rag, gate=ReportDenied(),
        founder_request="Fictional audit record", engagement_id="report-denied",
    ))
    assert result["status"] == "withheld"
    assert "agent_results" not in result and "consolidated" not in result
    assert sum(item["allowed"] for item in result["trustgate_decisions"]) == 4
    assert not result["trustgate_decisions"][-1]["allowed"]


def test_all_provider_attempts_share_rate_budget(monkeypatch):
    config = _provider_config(monkeypatch, max_retries=2)
    records = []

    def handler(request):
        records.append(request.url.path)
        if len(records) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        if request.url.path.endswith("embeddings"):
            return httpx.Response(200, json={"data": [{"embedding": [1.0]}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    provider = _sov_provider(config, handler)

    class Limiter:
        calls = 0

        async def acquire(self):
            self.calls += 1

    provider.rate_limiter = Limiter()

    async def exercise():
        await provider.chat([])
        await provider.embed(["public fixture"])
        await provider.close()

    asyncio.run(exercise())
    assert len(records) == provider.rate_limiter.calls == 3


def test_quota_rejection_is_terminal_and_does_not_echo_server_body(monkeypatch):
    config = _provider_config(monkeypatch)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(402, text="mock-sensitive-marker")

    provider = _sov_provider(config, handler)
    with pytest.raises(RuntimeError, match="^SovereignEG request rejected: HTTP 402$"):
        asyncio.run(provider.chat([]))
    assert len(calls) == 1


def test_benchmark_valid_id_needs_correct_observed_evidence():
    from eval.ai_benchmark import evaluate

    case = {"records": {"E1": "actual support", "E2": "routine unrelated note"},
            "expected": {"T1078": ["E1"]}}
    wrong = evaluate(case, '{"mappings":[{"technique_id":"T1078","record_ids":["E2"]}]}', {"T1078"})
    assert wrong["contract"] and wrong["labels_exact"] and not wrong["exact"]
    assert (wrong["tp"], wrong["fp"], wrong["fn"]) == (0, 1, 1)


def test_provider_caps_combined_chat_and_embedding_transport(monkeypatch):
    config = _provider_config(monkeypatch)
    active = peak = 0

    async def exercise():
        nonlocal active, peak
        two_entered = asyncio.Event()
        released = asyncio.Event()

        async def handler(request):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            if active == 2:
                two_entered.set()
            await released.wait()
            active -= 1
            if request.url.path.endswith("embeddings"):
                return httpx.Response(200, json={"data": [{"embedding": [1.0]}]})
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        provider = _sov_provider(config, handler)
        try:
            batch = [asyncio.create_task(provider.chat([])),
                     asyncio.create_task(provider.embed(["fixture"])),
                     asyncio.create_task(provider.chat([]))]
            await asyncio.wait_for(two_entered.wait(), 2)
            assert peak == 2 and not any(task.done() for task in batch)
            released.set()
            await asyncio.wait_for(asyncio.gather(*batch), 2)
            assert peak == 2
        finally:
            await provider.close()

    asyncio.run(exercise())


def test_ollama_uses_requested_json_schema():
    from ai.providers.ollama import OllamaProvider

    config = load_config(load_env=False).get_provider("ollama")
    schema = {"type": "object", "properties": {"mappings": {"type": "array"}}}

    def handler(request):
        assert json.loads(request.content)["format"] == schema
        return httpx.Response(200, json={"message": {"content": '{"mappings":[]}'}})

    async def exercise():
        provider = OllamaProvider(config)
        await provider.close()
        provider._client = httpx.AsyncClient(base_url=config.base_url, transport=httpx.MockTransport(handler))
        try:
            response = await provider.chat([], response_format={"type": "json_schema", "json_schema": {"schema": schema}})
            assert json.loads(response.content) == {"mappings": []}
        finally:
            await provider.close()

    asyncio.run(exercise())


def test_sovereign_refuses_alternate_host_before_reading_key(monkeypatch):
    from ai.providers.sovereign import SovereignEGProvider

    config = _provider_config(monkeypatch, base_url="https://unapproved.invalid/v1")
    with pytest.raises(ValueError, match="destination"):
        SovereignEGProvider(config)
