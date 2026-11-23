import json
from pathlib import Path

import httpx
import pytest

from eval.archived_reporting_action_coverage_ablation import add_observed_actions, compare_trace
from eval.archived_reporting_local_ranking import LOCK, evaluate_case, preflight, prepare, prepare_case


def test_local_ranking_fixture_and_requests_match_frozen_plan():
    spec, cases, plan = prepare()
    assert plan == json.loads(LOCK.read_bytes())
    assert len(cases) == 7
    assert sum(payload is not None for _, payload in cases) == 6
    for case, (report, payload) in zip(spec["cases"], cases, strict=True):
        preferred = {ref[-1] for ref in case["highlights"]}
        assert preferred <= {source["id"] for item in report["findings"] for source in item["sources"]}
        if payload:
            assert payload["options"] == spec["runtime"]["options"]
            assert "tools" not in payload
            packet = json.loads(payload["messages"][-1]["content"])
            submitted = {excerpt for row in packet["admitted"] for excerpt in row["text"]}
            assert not submitted & {event["outcome"] for event in case["events"] if event.get("authorized")}
        else:
            assert not report["findings"] and case["id"] == "approved-mail-transition"


def test_preflight_refuses_model_digest_mismatch():
    spec, _, _ = prepare()
    runtime = spec["runtime"]

    def respond(request):
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": runtime["version"]})
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{
            "name": runtime["model"], "digest": "0" * 64,
            "details": {"quantization_level": runtime["quantization"]},
        }]})

    with httpx.Client(base_url="http://127.0.0.1", transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(ValueError, match="identity mismatch"):
            preflight(client, runtime)


def test_local_ranking_rejects_incomplete_reply_and_skips_empty_admission():
    spec, cases, _ = prepare()
    runtime = spec["runtime"]
    sent = []

    def respond(request):
        sent.append(request.url.path)
        return httpx.Response(200, json={"model": runtime["model"], "done": True, "done_reason": "length",
                                         "message": {"role": "assistant", "content": "incomplete"}})

    with httpx.Client(base_url="http://127.0.0.1", transport=httpx.MockTransport(respond)) as client:
        first = evaluate_case(client, spec["cases"][0], *cases[0], runtime)
        skipped = evaluate_case(client, spec["cases"][-1], *cases[-1], runtime)
    assert first["status"] == "fallback" and first["attempts"] == 1 and first["findings_unchanged"]
    assert first["raw_reply"] and first["selected"] is None
    assert skipped["status"] == "blocked" and skipped["attempts"] == 0 and skipped["findings_unchanged"]
    assert sent == ["/api/chat"]


def test_saved_local_replies_reproduce_the_action_coverage_ablation():
    expected = Path("eval/reports/archived_reporting_action_coverage_ablation_v1.json")
    report = compare_trace()
    assert report == json.loads(expected.read_bytes())
    cases = report["cases"]
    assert len(cases) == 6 and all(case["findings_and_controls_unchanged"] for case in cases)
    assert sum(case["raw"]["published_coverage"]["action_covered_occurrences"] for case in cases) == 2
    assert sum(case["augmented"]["published_coverage"]["action_covered_occurrences"] for case in cases) == 8


def test_action_supplement_preserves_the_existing_selection_limit():
    spec, _, _ = prepare()
    original = next(case for case in spec["cases"] if case["id"] == "paired-design-archives")
    case = {**original, "events": [*original["events"], {
        "technique": "T1486", "action": "The synthetic archive ledger showed encryption of a third file set.",
        "outcome": "The reviewer confirmed the third file set was temporarily unavailable.",
    }]}
    review, _ = prepare_case(case, spec["runtime"])
    selection = {
        "highlights": [f"F{group}/S{source}" for group in (1, 2) for source in range(1, 5)],
        "recommendations": ["T1486-1"],
        "emphasis": "observed_impact",
    }
    augmented, added = add_observed_actions(review, json.dumps(selection))
    assert not added and len(augmented["summary"]) == 8
    assert augmented["summary_coverage"]["action_covered_occurrences"] == 2
    assert augmented["summary_coverage"]["admitted_occurrences"] == 3
