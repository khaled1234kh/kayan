"""DeepEval integration with deterministic metrics as the primary scorer.

DeepEval is pinned to a known compatible release. Judge metrics are inert
unless a real, explicitly configured judge and bounded authorization are
supplied. Offline mode imports nothing from DeepEval and makes no network call.
"""
from __future__ import annotations

import os
import re
from typing import Any

from . import RUBRIC_VERSION
from .statistics import judge_agreement

PINNED_DEEPEVAL_VERSION = "4.3.4"
PIN_SOURCE = "https://pypi.org/project/deepeval/4.3.4/"
DOCS = "https://deepeval.com/docs/metrics-llm-evals"
JUDGE_RUBRIC_VERSION = "judge-rubric-v1"
ATTACK_ID = re.compile(r"^T\d{4}(?:\.\d{3})?$")

JUDGE_METRIC_SPECS = (
    {
        "name": "KAYANDecisionCorrectness",
        "class": "GEval",
        "criteria": "Decide whether each item label and its cited record follow the supplied rules.",
        "evaluation_steps": [
            "Check each item has exactly one decision with a permitted label.",
            "Verify the cited record belongs to the item and supports the label.",
            "Treat unverified, missing, cross-session or contradictory records as requiring abstention.",
        ],
        "params": ["input", "actual_output", "expected_output", "context"],
        "threshold": 0.7,
        "judge_required": True,
    },
    {
        "name": "Faithfulness", "class": "FaithfulnessMetric", "threshold": 0.7,
        "note": "Grounding of claims in supplied retrieval context.", "judge_required": True,
    },
    {
        "name": "ContextualRelevancy", "class": "ContextualRelevancyMetric", "threshold": 0.7,
        "note": "Relevance of supplied evidence context to the task.", "judge_required": True,
    },
    {
        "name": "AnswerRelevancy", "class": "AnswerRelevancyMetric", "threshold": 0.7,
        "note": "Relevance of the output to the question.", "judge_required": True,
    },
    {
        "name": "TaskCompletion", "class": "TaskCompletionMetric", "threshold": 0.7,
        "note": "Whether the agent completed the scoped read-only task.", "judge_required": True,
    },
)

DETERMINISTIC_METRICS = (
    "attack_id_valid", "evidence_id_coverage", "citation_coverage",
    "authorization_attribution", "role_evidence_completeness", "dependency_order",
    "unsupported_claims", "abstention_discipline",
)


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 1.0


def deterministic_metrics(case: dict[str, Any], output: dict[str, Any] | None,
                          scored: dict[str, Any] | None = None) -> dict[str, float]:
    """Rule-based metrics computed locally from the versioned scorer.

    No judge and no network call. ``scored`` is accepted for API compatibility
    but the metrics are always recomputed from the versioned ground truth so
    they cannot be spoofed by a stale or caller-supplied score.
    """
    from .versioned_scorer import role_of, versioned_metrics

    _ = scored
    metrics = versioned_metrics(case, output)
    decisions = output.get("decisions", []) if isinstance(output, dict) else []
    expected_decisions = (
        case["expected"]["decisions"] if "expected" in case else case["ground_truth"]["decisions"]
    )
    expected_refs = {ref for row in expected_decisions for ref in row["evidence_ids"]}
    predicted_refs = [
        ref for row in decisions if isinstance(row, dict)
        for ref in row.get("evidence_ids", []) if isinstance(ref, str)
    ]

    attack_ids = [ref for ref in predicted_refs if ATTACK_ID.fullmatch(ref)]
    allowed = set(case.get("citations", {}).get("allowed_attack_ids", []))
    attack_valid = _ratio(sum(
        value in allowed for value in attack_ids
    ) if allowed else len(attack_ids), len(attack_ids))

    covered = sum(
        all(ref in row.get("evidence_ids", []) for ref in expected_decisions[index]["evidence_ids"])
        for index, row in enumerate(decisions) if isinstance(row, dict) and index < len(expected_decisions)
    )
    evidence_coverage = _ratio(covered, len(expected_decisions))
    citation_coverage = _ratio(len(expected_refs & set(predicted_refs)), len(expected_refs))

    order_ok = 1.0
    if role_of(case) == "Planner":
        order_ok = 1.0 if (
            not metrics["dependency_violations"] and metrics["missing_items"] == 0
            and metrics["exact_pass"]
        ) else 0.0

    errors = metrics["errors"]
    unsupported = _ratio(max(0, len(decisions) - errors["unsupported_affirmative"]), len(decisions))
    abstain_total = errors["false_abstention"] + errors["missed_abstention"]
    abstention = _ratio(max(0, len(expected_decisions) - abstain_total), len(expected_decisions))
    return {
        "attack_id_valid": round(attack_valid, 6),
        "evidence_id_coverage": round(evidence_coverage, 6),
        "citation_coverage": round(citation_coverage, 6),
        "authorization_attribution": _ratio(
            max(0, len(predicted_refs) - errors["wrong_attribution"]), len(predicted_refs)
        ),
        "role_evidence_completeness": round(evidence_coverage, 6),
        "dependency_order": order_ok,
        "unsupported_claims": round(unsupported, 6),
        "abstention_discipline": round(abstention, 6),
    }


def available(offline: bool = True) -> bool:
    if offline:
        return False
    try:
        from importlib.metadata import version  # noqa: PLC0415
        installed = version("deepeval")
    except Exception:
        return False
    if installed != PINNED_DEEPEVAL_VERSION:
        raise ValueError(
            f"DeepEval {installed} is not the pinned {PINNED_DEEPEVAL_VERSION}; refusing to run judge"
        )
    return True


def build_judge_metrics(
    *, allow_judge_calls: bool = False, judge_model_id: str | None = None,
    evaluated_model_id: str | None = None, offline: bool = True,
) -> dict[str, Any]:
    """Construct pinned judge metrics only after explicit authorization.

    Offline mode returns the frozen specification and constructed object count
    without importing DeepEval or contacting any provider.
    """
    spec = {
        "deepeval_version": PINNED_DEEPEVAL_VERSION,
        "source": PIN_SOURCE,
        "docs": DOCS,
        "judge_rubric_version": JUDGE_RUBRIC_VERSION,
        "judge_model_id": judge_model_id,
        "distinct_from_evaluated_model": None,
        "allow_judge_calls": bool(allow_judge_calls),
        "metrics": JUDGE_METRIC_SPECS,
        "deterministic_metrics": list(DETERMINISTIC_METRICS),
        "constructed": 0,
        "mode": "offline_spec_only",
        "warning": "Judge output is supplementary and is never ground truth.",
    }
    if not allow_judge_calls:
        return spec
    if offline:
        raise ValueError("Live judge requested while offline=true")
    if not judge_model_id or not evaluated_model_id:
        raise ValueError("Judge and evaluated model identities are both required")
    if judge_model_id == evaluated_model_id:
        raise ValueError("Self-grading is not permitted as sole authority")
    if not available(offline=False):
        raise ValueError(f"Pinned DeepEval {PINNED_DEEPEVAL_VERSION} is not installed")
    os.environ.setdefault("DEEPEVAL_DISABLE_DOTENV", "1")

    from deepeval.metrics import (  # type: ignore  # noqa: PLC0415
        AnswerRelevancyMetric, ContextualRelevancyMetric,
        FaithfulnessMetric, GEval, TaskCompletionMetric,
    )
    from deepeval.test_case import SingleTurnParams  # type: ignore  # noqa: PLC0415

    constructors = {
        "GEval": lambda row: GEval(
            name=row["name"], criteria=row["criteria"],
            evaluation_steps=row["evaluation_steps"],
            evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT,
                               SingleTurnParams.EXPECTED_OUTPUT],
            threshold=row["threshold"], model=judge_model_id,
        ),
        "FaithfulnessMetric": lambda row: FaithfulnessMetric(threshold=row["threshold"], model=judge_model_id),
        "ContextualRelevancyMetric": lambda row: ContextualRelevancyMetric(threshold=row["threshold"], model=judge_model_id),
        "AnswerRelevancyMetric": lambda row: AnswerRelevancyMetric(threshold=row["threshold"], model=judge_model_id),
        "TaskCompletionMetric": lambda row: TaskCompletionMetric(threshold=row["threshold"], model=judge_model_id),
    }
    built = [constructors[row["class"]](row) for row in JUDGE_METRIC_SPECS]
    return {
        **spec, "mode": "live_authorized", "constructed": len(built),
        "distinct_from_evaluated_model": True,
        "objects": built,
        "accounting": "Record judge tokens, latency and cost separately via ResourceLedger.",
    }


def mock_judge_binary(case_ids: list[str], seed: int = 20261123) -> dict[str, bool]:
    """Deterministic mock used only to exercise wiring in offline tests."""
    return {case_id: ((index * 2654435761 + seed) % 7) < 5
            for index, case_id in enumerate(sorted(case_ids))}


def judge_disagreement_report(
    judge_binary: dict[str, bool], reference_binary: dict[str, bool]
) -> dict[str, Any]:
    ids = sorted(judge_binary)
    if ids != sorted(reference_binary):
        raise ValueError("Judge and deterministic scorer must cover the same cases")
    result = judge_agreement([judge_binary[i] for i in ids], [reference_binary[i] for i in ids])
    result["disagreements"] = [i for i in ids if judge_binary[i] != reference_binary[i]]
    result["authority"] = "deterministic scorer; judge used only for bias and disagreement review"
    return result
