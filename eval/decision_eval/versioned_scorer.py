"""Versioned deterministic scorer for decision-eval dataset cases.

This is the ``diagnostics-v1`` rubric applied consistently to all arms on the
new versioned dataset. It deliberately does NOT call or modify the frozen
80-case role-contract scorer: that scorer remains the untouched historical
baseline. The versioned dataset supports features the frozen shape cannot
express (multiple evidence records per item, cross-session and attribution
cases), so it needs its own scorer with the same scoring semantics.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from . import RUBRIC_VERSION
from .scoring import _ROLE_CANONICAL, canonical_label


def role_of(case: dict) -> str:
    return case.get("role", case.get("agent"))


def affirmative_label(role: str) -> str:
    return next(label for label, canon in _ROLE_CANONICAL[role].items() if canon == "supported")


def abstention_label(role: str) -> str | None:
    return next((label for label, canon in _ROLE_CANONICAL[role].items() if canon == "abstain"), None)


def validate_shape(case: dict, parsed: Any) -> tuple[list[dict], str | None]:
    """Validate the output contract, mirroring the frozen scorer's checks."""
    role = role_of(case)
    if not isinstance(parsed, dict):
        return [], "invalid_shape"
    required = {"decisions"}
    if role == "Planner":
        required.add("execution_order")
    if set(parsed) != required:
        return [], "invalid_shape"
    decisions = parsed["decisions"]
    if not isinstance(decisions, list) or len(decisions) > 12:
        return [], "invalid_decisions"
    labels = set(_ROLE_CANONICAL[role])
    for row in decisions:
        if not isinstance(row, dict) or set(row) != {"item_id", "label", "evidence_ids"}:
            return [], "invalid_decision_shape"
        item, label, evidence = row["item_id"], row["label"], row["evidence_ids"]
        if not isinstance(item, str) or not 0 < len(item) <= 96:
            return [], "invalid_item_id"
        if label not in labels:
            return [], "invalid_label"
        if (not isinstance(evidence, list) or len(evidence) > 8
                or not all(isinstance(ref, str) and 0 < len(ref) <= 96 for ref in evidence)):
            return [], "invalid_evidence_ids"
    if role == "Planner":
        order = parsed["execution_order"]
        if (not isinstance(order, list) or len(order) > 12
                or not all(isinstance(value, str) and 0 < len(value) <= 96 for value in order)):
            return [], "invalid_execution_order"
    return decisions, None


def _counter_metrics(truth: Counter, prediction: Counter) -> tuple[int, int, int]:
    return (
        sum((truth & prediction).values()),
        sum((prediction - truth).values()),
        sum((truth - prediction).values()),
    )


def versioned_metrics(case: dict, parsed: Any) -> dict[str, Any]:
    """Compute all deterministic metrics without any judge or network call."""
    role = role_of(case)
    decisions, error = validate_shape(case, parsed)
    truth = case["ground_truth"]["decisions"]

    expected_ids = {row["item_id"] for row in truth}
    item_counts = Counter(row["item_id"] for row in decisions)
    duplicates = sum(n - 1 for n in item_counts.values() if n > 1)
    unknown_items = sum(n for key, n in item_counts.items() if key not in expected_ids)
    missing_items = len(expected_ids - item_counts.keys())

    truth_labels = Counter((row["item_id"], row["label"]) for row in truth)
    pred_labels = Counter((row["item_id"], row["label"]) for row in decisions)
    label_tp, label_fp, label_fn = _counter_metrics(truth_labels, pred_labels)

    truth_ev = Counter(
        (row["item_id"], row["label"], ref) for row in truth for ref in row["evidence_ids"]
    )
    pred_ev = Counter(
        (row["item_id"], row["label"], ref) for row in decisions for ref in row["evidence_ids"]
    )
    ev_tp, ev_fp, ev_fn = _counter_metrics(truth_ev, pred_ev)
    true_ev = set(truth_ev)

    affirmative = affirmative_label(role)
    abstain = abstention_label(role)
    unsupported = sum(
        1 for row in decisions
        if row["label"] == affirmative and (
            not row["evidence_ids"]
            or any((row["item_id"], row["label"], ref) not in true_ev
                   for ref in row["evidence_ids"])
        )
    )

    truth_ref_owner: dict[str, set[str]] = {}
    for row in truth:
        for ref in row["evidence_ids"]:
            truth_ref_owner.setdefault(ref, set()).add(row["item_id"])
    wrong_attribution = sum(
        1 for row in decisions for ref in row["evidence_ids"]
        if ref in truth_ref_owner and row["item_id"] not in truth_ref_owner[ref]
    )

    pred_by_id = {row["item_id"]: row for row in decisions}
    truth_by_id = {row["item_id"]: row for row in truth}
    incorrect_admission = incorrect_withholding = false_abstention = missed_abstention = 0
    pairs: list[tuple[str, str]] = []
    for item_id, expected_row in truth_by_id.items():
        predicted = pred_by_id.get(item_id)
        if predicted is None or predicted["label"] not in _ROLE_CANONICAL[role]:
            continue
        t = canonical_label(role, expected_row["label"])
        p = canonical_label(role, predicted["label"])
        pairs.append((t, p))
        if p == "supported" and t != "supported":
            incorrect_admission += 1
        if t == "supported" and p != "supported":
            incorrect_withholding += 1
        if p == "abstain" and t != "abstain":
            false_abstention += 1
        if t == "abstain" and p != "abstain":
            missed_abstention += 1
    _ = abstain

    order_valid = True
    dependency_violations = 0
    if role == "Planner":
        order = parsed.get("execution_order", []) if isinstance(parsed, dict) else []
        positions = {key: index for index, key in enumerate(order)}
        dependencies = case["ground_truth"]["dependencies"]
        dependency_violations = sum(
            dep not in positions or positions[dep] >= positions[key]
            for key in order if key in dependencies for dep in dependencies[key]
        )
        ready = {row["item_id"] for row in truth if row["label"] == affirmative}
        order_valid = (
            error is None and len(positions) == len(order)
            and set(order) == ready and dependency_violations == 0
        )

    exact_pass = (
        error is None
        and not any((label_fp, label_fn, ev_fp, ev_fn))
        and duplicates == 0 and missing_items == 0 and unknown_items == 0
        and unsupported == 0 and order_valid
    )

    return {
        "error": error,
        "exact_pass": exact_pass,
        "pairs": pairs,
        "label_tp": label_tp, "label_fp": label_fp, "label_fn": label_fn,
        "evidence_tp": ev_tp, "evidence_fp": ev_fp, "evidence_fn": ev_fn,
        "missing_items": missing_items, "duplicate_items": duplicates,
        "unknown_items": unknown_items,
        "dependency_violations": dependency_violations,
        "errors": {
            "invalid_output": int(error is not None),
            "unsupported_affirmative": unsupported,
            "false_abstention": false_abstention,
            "missed_abstention": missed_abstention,
            "missed_finding": label_fn,
            "incorrect_admission": incorrect_admission,
            "incorrect_withholding": incorrect_withholding,
            "bad_citation": ev_fp,
            "wrong_attribution": wrong_attribution,
            "incomplete_chain": ev_fn + dependency_violations,
            "missing_items": missing_items,
            "duplicate_items": duplicates,
            "unknown_items": unknown_items,
        },
    }


def score_versioned_case(case: dict, parsed: Any) -> dict[str, Any]:
    metrics = versioned_metrics(case, parsed)
    return {
        "rubric_version": RUBRIC_VERSION,
        "exact_pass": metrics["exact_pass"],
        "metrics": metrics,
        "diagnostics_v1": metrics["errors"],
        "pairs": metrics["pairs"],
    }
