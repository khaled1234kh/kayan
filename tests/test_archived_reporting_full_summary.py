import json
from pathlib import Path

from eval.archived_reporting_full_summary import FIXTURE, case_input, evaluate
from eval.archived_reporting_selection import replay
from pentagi.agents.archived_reporting import compose, request_for


def test_frozen_swap_comparison_rejects_preference_loss_in_one_case():
    results = evaluate()
    saved = Path("eval/reports/archived_reporting_full_summary_v1.json")
    assert results == json.loads(saved.read_bytes())
    assert not results["candidate_qualifies"]
    assert [name for name, passed in results["decision"].items() if not passed] == [
        "no_case_exceeds_preference_loss_budget",
    ]
    tradeoff = next(row for row in results["cases"] if row["group"] == "tradeoff")
    assert (tradeoff["action_gain"], tradeoff["preference_loss"]) == (2, 2)


def test_full_summary_preserves_selection_and_exposes_only_admitted_missing_actions():
    case = next(row for row in json.loads(FIXTURE.read_bytes())["cases"] if row.get("authorized"))
    report, selection, _ = case_input(case)
    original = compose(report, json.dumps(selection))
    presented = compose(report, json.dumps(selection), supplement_actions=True)
    references = presented.pop("summary_additional_actions")
    assert presented == original
    assert presented["summary_coverage"]["action_covered_occurrences"] == 1
    assert references == [
        {"technique": "T1486", "occurrence": f"event-{event}", "source_id": f"E{event}.1"}
        for event in range(2, 9)
    ]
    assert report["withheld"][0]["occurrence"] == "event-9"
    assert "summary_additional_actions" not in compose(report)


def test_full_summary_references_are_saved_and_downloaded_by_reporting_api():
    case = json.loads(FIXTURE.read_bytes())["cases"][1]
    report, selection, _ = case_input(case)
    _, cloud, attempts, exact_download = replay(
        selection, report, request_for(report)[2], supplement_actions=True,
    )
    assert cloud["status"] == "selected" and attempts == 1 and exact_download
    assert cloud["summary"] == compose(report, json.dumps(selection))["summary"]
    assert cloud["summary_coverage"] == {
        "admitted_occurrences": 9, "covered_occurrences": 6, "action_covered_occurrences": 0,
    }
    assert len(cloud["summary_additional_actions"]) == 9
