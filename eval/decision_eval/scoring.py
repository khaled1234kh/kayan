"""Deterministic scoring adapter.

The frozen role-contract scorer is loaded verbatim and never modified. Its
``passed`` flag remains the historical exact-pass baseline. The versioned
``diagnostics-v1`` rubric adds an error taxonomy and canonical class mapping
without changing that baseline.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from . import RUBRIC_VERSION

FROZEN_BUNDLE = Path(__file__).resolve().parent.parent / "sovereign-80-matched"
FROZEN_REFERENCE = FROZEN_BUNDLE / "reference"

CANONICAL = ("supported", "contradicted", "abstain")
_ROLE_CANONICAL = {
    "Planner": {"ready": "supported", "blocked": "contradicted"},
    "Recon": {"confirmed": "supported", "contradicted": "contradicted", "insufficient": "abstain"},
    "Web-App": {"supported": "supported", "contradicted": "contradicted", "insufficient": "abstain"},
    "Network": {"confirmed": "supported", "contradicted": "contradicted", "insufficient": "abstain"},
    "Reporting": {"include": "supported", "omit": "contradicted", "abstain": "abstain"},
}


def frozen_modules() -> tuple[Any, Any]:
    """Import the published frozen scorer and helper module exactly once."""
    if str(FROZEN_REFERENCE) not in sys.path:
        sys.path.insert(0, str(FROZEN_REFERENCE))
    import role_cases  # type: ignore
    import analyze_models  # type: ignore
    return role_cases, analyze_models


def canonical_label(role: str, label: str) -> str:
    mapping = _ROLE_CANONICAL[role]
    if label not in mapping:
        raise ValueError(f"Unknown label {label!r} for {role}")
    return mapping[label]


def canonical_classes_for(role: str) -> tuple[str, ...]:
    present = {canonical_label(role, label) for label in _ROLE_CANONICAL[role]}
    return tuple(cls for cls in CANONICAL if cls in present)


def parse_output(content: str | dict | None) -> tuple[dict | None, str | None]:
    """Strict JSON parse matching the frozen runner (duplicate keys rejected)."""
    _, helper = frozen_modules()
    if content is None:
        return None, "missing_output"
    if isinstance(content, dict):
        parsed, error = helper.role_cases._parse_output(_dummy_case_for_parse(), content)
        return (parsed, error)
    try:
        value = helper.strict_json(content)
    except (ValueError, TypeError, RecursionError):
        return None, "invalid_json"
    return value, None


def _dummy_case_for_parse() -> dict:
    # Only used for the dict branch to avoid duplicating parse logic; callers
    # that need semantic validation should always use score_case().
    role_cases, _ = frozen_modules()
    return {"role": "Recon", "expected": {"decisions": []}}


def score_case(case: dict, content: str | dict | None) -> dict[str, Any]:
    """Score one case with both the frozen baseline and versioned diagnostics."""
    role_cases, helper = frozen_modules()
    parsed, parse_error = parse_output(content)
    # The frozen scorer performs its own strict parse and shape validation.
    frozen = role_cases.score(case, parsed if parse_error is None else None)
    if parse_error == "invalid_json":
        frozen = {**frozen, "error": "invalid_json", "invalid_output": True}
    return {
        "rubric_version": RUBRIC_VERSION,
        "legacy_exact_pass": frozen["passed"],
        "frozen": frozen,
        "diagnostics_v1": error_taxonomy(case, parsed, frozen),
    }


def _decisions(parsed: dict | None) -> list[dict]:
    return [] if not isinstance(parsed, dict) else list(parsed.get("decisions", []))


def expected_decisions(case: dict) -> list[dict]:
    """Return ground truth in either the frozen or versioned case shape."""
    if "expected" in case:
        return list(case["expected"]["decisions"])
    return list(case["ground_truth"]["decisions"])


def item_maps(case: dict, parsed: dict | None) -> tuple[dict[str, dict], dict[str, dict]]:
    """Return truth and prediction maps keyed by item_id."""
    truth = {row["item_id"]: row for row in expected_decisions(case)}
    pred = {row["item_id"]: row for row in _decisions(parsed)
            if isinstance(row, dict) and isinstance(row.get("item_id"), str)}
    return truth, pred


def canonical_pairs(case: dict, parsed: dict | None) -> list[tuple[str, str]]:
    """Per-item (truth, prediction) pairs in canonical classes.

    Invalid outputs and items without a valid prediction are excluded here and
    reported separately as distinct errors; they are never silently converted
    into a 'contradicted' prediction to inflate the matrix.
    """
    truth, pred = item_maps(case, parsed)
    pairs = []
    for item_id, expected_row in truth.items():
        row = pred.get(item_id)
        if not isinstance(row, dict) or row.get("label") not in _ROLE_CANONICAL[case["role"]]:
            continue
        pairs.append((canonical_label(case["role"], expected_row["label"]),
                      canonical_label(case["role"], row["label"])))
    return pairs


def error_taxonomy(case: dict, parsed: dict | None, frozen: dict) -> dict[str, int]:
    """Disjoint-by-design error counters; one response may trigger several."""
    truth, pred = item_maps(case, parsed)
    truth_evidence = {
        (row["item_id"], row["label"], ref)
        for row in expected_decisions(case) for ref in row["evidence_ids"]
    }
    pred_evidence = {
        (row["item_id"], row.get("label"), ref)
        for row in _decisions(parsed) if isinstance(row.get("evidence_ids"), list)
        for ref in row["evidence_ids"] if isinstance(ref, str)
    }
    truth_ref_owner = {}
    for row in expected_decisions(case):
        for ref in row["evidence_ids"]:
            truth_ref_owner.setdefault(ref, set()).add(row["item_id"])
    wrong_attribution = sum(
        1 for item, label, ref in pred_evidence - truth_evidence
        if ref in truth_ref_owner and item not in truth_ref_owner[ref]
    )
    unsupported = sum(
        1 for row in _decisions(parsed)
        if row.get("label") and canonical_label(case["role"], row["label"]) == "supported"
        and (not row.get("evidence_ids") or any(
            (row["item_id"], row["label"], ref) not in truth_evidence
            for ref in row["evidence_ids"] if isinstance(ref, str)
        ))
    )
    incorrect_admission = incorrect_withholding = false_abstention = missed_abstention = 0
    for item_id, row in pred.items():
        label = row.get("label")
        if label not in _ROLE_CANONICAL[case["role"]] or item_id not in truth:
            continue
        t = canonical_label(case["role"], truth[item_id]["label"])
        p = canonical_label(case["role"], label)
        if p == "supported" and t != "supported":
            incorrect_admission += 1
        if t == "supported" and p in ("contradicted", "abstain"):
            incorrect_withholding += 1
        if p == "abstain" and t != "abstain":
            false_abstention += 1
        if t == "abstain" and p != "abstain":
            missed_abstention += 1
    counts = Counter({
        "invalid_output": int(bool(frozen.get("invalid_output"))),
        "unsupported_affirmative": unsupported,
        "false_abstention": false_abstention,
        "missed_abstention": missed_abstention,
        "missed_finding": int(frozen.get("label_fn", 0)),
        "incorrect_admission": incorrect_admission,
        "incorrect_withholding": incorrect_withholding,
        "bad_citation": int(frozen.get("evidence_fp", 0)),
        "wrong_attribution": wrong_attribution,
        "incomplete_chain": int(frozen.get("evidence_fn", 0))
        + int(frozen.get("dependency_violations") or 0),
        "missing_items": int(frozen.get("missing_items", 0)),
        "duplicate_items": int(frozen.get("duplicate_items", 0)),
        "unknown_items": int(frozen.get("unsupported_items", 0)),
    })
    return {key: counts[key] for key in sorted(counts)}


def score_saved_attempt(case: dict, attempt: dict) -> dict[str, Any]:
    """Re-score a saved raw attempt and verify its stored score still matches."""
    _, helper = frozen_modules()
    checked = helper.checked_attempt(case, dict(attempt))
    return score_case(case, checked["content"] if not checked["error"] else None)
