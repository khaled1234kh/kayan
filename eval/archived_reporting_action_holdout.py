"""Score the frozen Reporting action supplement on a distinct synthetic cohort."""

import argparse
import json
from fractions import Fraction
from hashlib import sha256
from pathlib import Path

from eval.archived_reporting_action_coverage_ablation import MAX_HIGHLIGHTS, add_observed_actions, compare_trace
from eval.archived_reporting_local_ranking import FIXTURES, prepare
from eval.archived_reporting_selection import selection_metrics
from pentagi.agents.archived_reporting import compose


SPEC = FIXTURES / "archived_reporting_action_holdout_v1.json"
LOCK = FIXTURES / "archived_reporting_action_holdout_v1.lock.json"
TRACE = Path(__file__).with_name("reports") / "archived_reporting_action_holdout_v1.jsonl"


def aggregate(scores):
    totals = {}
    for field in ("highlights", "recommendations"):
        totals[field] = {
            key: sum(score[field][key] for score in scores)
            for key in ("matching", "returned", "desired", "exact", "ordered_pairs", "comparable_pairs")
        }
    totals["coverage"] = {
        key: sum(score["published_coverage"][key] for score in scores)
        for key in ("admitted_occurrences", "covered_occurrences", "action_covered_occurrences")
    }
    return totals


def decide(before, after, selected, bounds, *, integrity, capacity_ok):
    raw_h, augmented_h = before["highlights"], after["highlights"]
    raw_c, augmented_c = before["coverage"], after["coverage"]
    least_pairs = bounds["minimum_comparable_pairs_per_arm"]
    order_measured = min(raw_h["comparable_pairs"], augmented_h["comparable_pairs"]) >= least_pairs
    coverage_measured = min(raw_c["admitted_occurrences"], augmented_c["admitted_occurrences"]) > 0
    precision_measured = min(raw_h["returned"], augmented_h["returned"]) > 0
    checks = {
        "unchanged_findings_controls_and_attempt_scope": integrity,
        "full_cap_behavior": capacity_ok,
        "enough_selected_primary_cases": selected >= bounds["minimum_selected_primary_cases"],
        "action_coverage_improves_and_meets_floor": coverage_measured and (
            Fraction(augmented_c["action_covered_occurrences"], augmented_c["admitted_occurrences"])
            > Fraction(raw_c["action_covered_occurrences"], raw_c["admitted_occurrences"])
            and 100 * Fraction(augmented_c["action_covered_occurrences"], augmented_c["admitted_occurrences"])
            >= bounds["minimum_action_coverage_percent"]
        ),
        "preferred_reference_precision_within_budget": precision_measured and (
            100 * (Fraction(raw_h["matching"], raw_h["returned"]) - Fraction(augmented_h["matching"], augmented_h["returned"]))
            <= bounds["maximum_precision_loss_points"]
        ),
        "comparable_pair_order_within_budget": order_measured and (
            100 * (Fraction(raw_h["ordered_pairs"], raw_h["comparable_pairs"])
                   - Fraction(augmented_h["ordered_pairs"], augmented_h["comparable_pairs"]))
            <= bounds["maximum_order_loss_points"]
        ),
    }
    return {"checks": checks, "passes_predeclared_gate": all(checks.values())}


def evaluate(path=TRACE):
    spec, prepared, _ = prepare(SPEC)
    raw = path.read_bytes()
    _, *rows = map(json.loads, raw.splitlines())
    replay = compare_trace(path, spec_path=SPEC, lock_path=LOCK)
    if sha256(raw).hexdigest() != replay["trace_sha256"]:
        raise ValueError("Trace changed while scoring")
    cases = {case["id"]: case for case in spec["cases"]}
    reports = {case["id"]: report for case, (report, _) in zip(spec["cases"], prepared, strict=True)}
    observed = {row["id"]: row for row in rows}
    primary = [item for item in replay["cases"] if cases[item["id"]]["group"] == "primary"]
    capacity, = [case for case in spec["cases"] if case["group"] == "capacity"]
    capacity_replay = next((item for item in replay["cases"] if item["id"] == capacity["id"]), None)
    report = reports[capacity["id"]]
    selection = json.dumps(capacity["full_cap_selection"])
    unchanged = compose(report, selection)
    bounded, added = add_observed_actions(report, selection)
    cap_ok = (bounded == unchanged and not added and len(bounded["summary"]) == MAX_HIGHLIGHTS
              < bounded["summary_coverage"]["admitted_occurrences"])
    integrity = all(row["findings_unchanged"] and (
        row["status"] == "blocked" and row["attempts"] == 0 and row["raw_reply"] is None
        if cases[row["id"]]["group"] == "benign"
        else row["attempts"] == 1 and row["status"] in {"selected", "fallback"}
    ) for row in rows) and all(item["findings_and_controls_unchanged"] for item in replay["cases"])
    local = aggregate([observed[item["id"]]["local"] for item in primary])
    before = aggregate([item["raw"] for item in primary])
    after = aggregate([item["augmented"] for item in primary])
    return {
        "protocol": spec["protocol"], "fixture_sha256": sha256(SPEC.read_bytes()).hexdigest(),
        "trace_sha256": replay["trace_sha256"], "decision_thresholds": spec["decision"],
        "primary_selected": len(primary), "primary_cases": sum(case["group"] == "primary" for case in spec["cases"]),
        "totals_on_selected_primary_cases": {"deterministic": local, "raw_model": before, "supplemented": after},
        "decision": decide(before, after, len(primary), spec["decision"], integrity=integrity, capacity_ok=cap_ok),
        "case_statuses": [{"id": row["id"], "status": row["status"], "attempts": row["attempts"]} for row in rows],
        "primary": primary,
        "capacity": {"real_reply": capacity_replay, "authored_full_cap_reply": selection_metrics(bounded, capacity)},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, default=TRACE)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.trace), indent=2, ensure_ascii=True))
