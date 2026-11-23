"""Regression checks for offline retrieval, evidence scoring, and egress boundaries."""

from dataclasses import replace
import asyncio

import httpx
import pytest

from ai.config import load_config
from ai.mitre.ranking import BM25, FieldBM25, rank, rank_fusion
from ai.mitre.stix import MitreTechnique, parse_techniques
from ai.providers.ollama import OllamaProvider
from ai.providers.registry import ProviderRegistry
from ai.providers.sovereign import SovereignEGProvider
from ai.trustgate.client import AITrustGate
from eval.ai_retrieval_mapping import context_ids, score, summary


def test_bm25_returns_stable_ties_and_preserves_dotted_ids():
    model = BM25({"T0002": "clear Windows event log", "T0001": "clear Windows event log",
                  "T0003": "T1685.005", "T0004": "T1685.001"})
    assert [tid for tid, _ in rank(model.score("cleared Windows event logs"))] == ["T0001", "T0002"]
    assert set(model.score("T1685.005")) == {"T0003"}


def test_field_ranker_uses_detection_metadata_without_changing_baseline():
    doc = {"objects": [
        {"type": "attack-pattern", "id": "tech", "name": "Sample", "description": "Recorded behavior",
         "x_mitre_platforms": ["Windows"], "external_references": [
             {"source_name": "mitre-attack", "external_id": "T1234"}]},
        {"type": "x-mitre-detection-strategy", "id": "detect", "name": "Endpoint bluebird activity"},
        {"type": "relationship", "relationship_type": "detects", "source_ref": "detect", "target_ref": "tech"},
        {"type": "x-mitre-detection-strategy", "id": "old", "name": "Retired strategy", "revoked": True},
        {"type": "relationship", "relationship_type": "detects", "source_ref": "old", "target_ref": "tech"},
    ]}
    t, = parse_techniques(doc)
    assert t.detection_strategies == ("Endpoint bluebird activity",)
    assert t.platforms == ("Windows",) and "bluebird" not in t.raw_text
    unrelated = MitreTechnique("T9999", "Other", "Unrelated text", (), "", (), "")
    assert FieldBM25([t, unrelated])({"E1":"bluebird telemetry"})[0][0] == "T1234"
    assert rank_fusion([("T1234", 0.2), ("T9999", 0.1)], [("T1234", 0.9)])[0][0] == "T1234"


def test_oracle_inserts_gold_without_changing_negative_context():
    base = ["T0001", "T0002", "T0003", "T0004", "T0005"]
    universe = set(base + ["T0006", "T0007"])
    ordinary = context_ids(base, {}, universe, oracle=False, case_id="same")
    negative = context_ids(base, {}, universe, oracle=True, case_id="same")
    positive = context_ids(base, {"T0006": ["E1"]}, universe, oracle=True, case_id="same")
    assert ordinary == negative and len(positive) == len(negative) == 5
    assert set(positive) - set(negative) == {"T0006"}


def test_valid_json_with_wrong_quote_can_look_correct_until_binding():
    case = {"records": {"E1":"Exact evidence text", "E2":"Unrelated record"}, "expected":{"T1078":["E1"]}}
    raw = '{"mappings":[{"technique_id":"T1078","record_id":"E1","quote":"Unrelated record","justification":"Claims evidence in the right record"}]}'
    result = score(case, raw, {"T1078"})
    assert result["tp"] == 1 and result["released_tp"] == 0
    assert result["blocked"] == [["T1078","E1","quote_mismatch"]]


def test_strict_specificity_excludes_broken_output_and_rejects_retired_id():
    positive = {"records":{"E1":"Observed record"}, "expected":{"T1685.005":["E1"]}}
    negative = {"records":{"E1":"Approved operation"}, "expected":{}}
    raw = '{"mappings":[{"technique_id":"T1070.001","record_id":"E1","quote":"Observed record","justification":"Confirmed observation"}]}'
    scores = [score(positive, raw, {"T1685.005"}), score(negative, "not JSON", set()),
              score(negative, '{"mappings":[]}', set())]
    metrics = summary([{"score": s} for s in scores])
    assert scores[0]["blocked"] == [["T1070.001","E1","inactive_or_unknown_id"]]
    assert metrics["negative_specificity"] == .5 and metrics["abstention_rate"] == 1/3
    assert metrics["positive_case_recall"] == 0


def test_cloud_default_and_normal_http_transport_are_paused(monkeypatch):
    config = load_config(load_env=False)
    network = httpx.AsyncHTTPTransport()

    def fail(*args, **kwargs):
        pytest.fail("Paused provider tried to initialize HTTP")

    monkeypatch.setattr(httpx, "AsyncClient", fail)
    with pytest.raises(PermissionError, match="paused"):
        asyncio.run(ProviderRegistry(config).get())
    for transport in (None, network):
        with pytest.raises(PermissionError, match="paused"):
            SovereignEGProvider(config.primary, transport=transport)
    asyncio.run(network.aclose())


@pytest.mark.parametrize("base", ["https://unapproved.invalid", "http://localhost:11434",
                                  "http://127.0.0.1:11434/other", "http://user@127.0.0.1:11434"])
def test_experimental_clients_reject_nonlocal_or_ambiguous_endpoints(base):
    config = load_config(load_env=False)
    with pytest.raises(PermissionError, match="loopback"):
        OllamaProvider(replace(config.get_provider("ollama"), base_url=base))
    with pytest.raises(PermissionError, match="loopback"):
        AITrustGate(replace(config.trustgate, base_url=base))
