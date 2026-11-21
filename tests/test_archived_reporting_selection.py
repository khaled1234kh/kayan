from collections import Counter

from eval.archived_reporting_selection import run_replays


def test_frozen_selection_replays_preserve_findings_and_explain_coverage():
    cases = run_replays()["cases"]
    assert Counter(case["status"] for case in cases) == {"selected": 7, "degraded": 6, "blocked": 1}
    for case in cases:
        assert case["status"] == case["expected_status"], case["id"]
        assert case["findings_unchanged"] and case["withheld_unchanged"], case["id"]
        if case["status"] == "blocked":
            assert case["attempts"] == 0
        else:
            assert case["attempts"] == 1 and case["export_matches"], case["id"]
        if case["status"] == "degraded":
            assert case["fallback_matches_local"], case["id"]
        for mode in ("local", "selected"):
            measured = case[mode]
            if measured is None:
                continue
            count = measured["covered_occurrences"]
            assert measured["published_coverage"] == {
                "admitted_occurrences": measured["admitted_occurrences"],
                "covered_occurrences": count,
                "action_covered_occurrences": 0 if mode == "selected" and case["id"] == "repeated-weak-relevance" else count,
            }, case["id"]
    by_id = {case["id"]: case for case in cases}
    assert by_id["repeated-ranked"]["selected"]["highlights"]["exact"]
    reversed_order = by_id["repeated-reversed"]["selected"]["highlights"]
    assert reversed_order["matching"] == reversed_order["desired"] == 2
    assert reversed_order["ordered_pairs"] == 0 and reversed_order["comparable_pairs"] == 1
    weak = by_id["repeated-weak-relevance"]["selected"]
    assert weak["covered_occurrences"] == 2 and weak["highlights"]["matching"] == 0
    assert by_id["repeated-partial"]["selected"]["covered_occurrences"] == 1
