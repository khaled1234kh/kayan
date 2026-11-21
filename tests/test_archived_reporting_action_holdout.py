import json
from pathlib import Path

from eval.archived_reporting_action_coverage_ablation import add_observed_actions
from eval.archived_reporting_action_holdout import LOCK, SPEC, TRACE, decide, evaluate
from eval.archived_reporting_local_ranking import prepare
from pentagi.agents.archived_reporting import compose


def test_holdout_plan_is_frozen_and_distinct_from_development():
    _, _, development = prepare()
    spec, cases, holdout = prepare(SPEC)
    assert holdout == json.loads(LOCK.read_bytes())
    assert len(cases) == 8
    assert {row["archive_sha256"] for row in holdout["cases"]}.isdisjoint(
        {row["archive_sha256"] for row in development["cases"]}
    )
    assert sum(payload is not None for _, payload in cases) == 7
    for case, (report, payload) in zip(spec["cases"], cases, strict=True):
        if case["group"] == "benign":
            assert not report["findings"] and len(report["withheld"]) == 1 and payload is None
        if case["group"] == "capacity":
            assert len(report["findings"]) == 9
            assert len(case["full_cap_selection"]["highlights"]) == 8


def test_good_coverage_cannot_override_precision_regression_or_missing_order_evidence():
    spec = json.loads(SPEC.read_bytes())
    original = {
        "highlights": {"matching": 9, "returned": 10, "ordered_pairs": 2, "comparable_pairs": 3},
        "coverage": {"admitted_occurrences": 8, "action_covered_occurrences": 2},
    }
    augmented = {
        "highlights": {"matching": 10, "returned": 16, "ordered_pairs": 1, "comparable_pairs": 1},
        "coverage": {"admitted_occurrences": 8, "action_covered_occurrences": 8},
    }
    verdict = decide(original, augmented, 6, spec["decision"], integrity=True, capacity_ok=True)
    assert verdict["checks"]["action_coverage_improves_and_meets_floor"]
    assert not verdict["checks"]["preferred_reference_precision_within_budget"]
    assert not verdict["checks"]["comparable_pair_order_within_budget"]
    assert not verdict["passes_predeclared_gate"]


def test_recorded_holdout_reproduces_and_keeps_the_eight_excerpt_cap():
    expected = Path("eval/reports/archived_reporting_action_holdout_v1_summary.json")
    actual = evaluate()
    assert actual == json.loads(expected.read_bytes())
    assert sum(row["attempts"] for row in actual["case_statuses"]) == 7
    assert actual["decision"]["checks"]["unchanged_findings_controls_and_attempt_scope"]
    assert actual["decision"]["checks"]["full_cap_behavior"]
    assert actual["capacity"]["authored_full_cap_reply"]["published_coverage"] == {
        "admitted_occurrences": 9, "covered_occurrences": 8, "action_covered_occurrences": 0,
    }


def test_production_supplement_matches_frozen_holdout_and_marks_only_additions():
    _, cases, _ = prepare(SPEC)
    _, *rows = map(json.loads, TRACE.read_bytes().splitlines())
    for (report, _), row in zip(cases, rows, strict=True):
        if row["status"] != "selected":
            continue
        selection = json.loads(row["raw_reply"])["message"]["content"]
        expected, added = add_observed_actions(report, selection)
        actual = compose(report, selection, supplement_actions=True)
        extra = actual.pop("summary_additional_actions", [])
        original = compose(report, selection)
        assert actual["summary"][:len(original["summary"])] == original["summary"]
        assert len(actual["summary"]) <= 8
        assert len(actual["summary"]) - len(original["summary"]) == len(added)
        for item in actual["summary"][len(original["summary"]):]:
            assert item.pop("selection_origin") == "verified_action_supplement"
            assert "mechanic" in item["roles"]
        coverage = actual["summary_coverage"]
        assert len(extra) == coverage["admitted_occurrences"] - coverage["action_covered_occurrences"]
        assert actual == expected, row["id"]
