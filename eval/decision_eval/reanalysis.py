"""Offline re-analysis of saved outputs. No inference and no network calls.

The frozen scorer is re-run against stored raw responses and the stored scores
are verified. Exact case-level pass rate is kept separate from multiclass
confusion matrices and from the disjoint error taxonomy.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import AGENTS, CANONICAL_CLASSES, RUBRIC_VERSION
from .confusion import abstention_metrics, classification_report, distinct_error_counts
from .scoring import canonical_pairs, frozen_modules, score_saved_attempt
from .statistics import mcnemar_exact, paired_bootstrap, wilson_interval

ERROR_KEYS = (
    "invalid_output", "unsupported_affirmative", "false_abstention", "missed_abstention",
    "missed_finding", "incorrect_admission", "incorrect_withholding", "bad_citation",
    "wrong_attribution", "incomplete_chain", "missing_items", "duplicate_items", "unknown_items",
)


def _tokens(attempt: dict[str, Any]) -> tuple[int, int]:
    envelope = attempt.get("ollama") or {}
    if not isinstance(envelope, dict):
        return 0, 0
    prompt = envelope.get("prompt_eval_count", envelope.get("prompt_tokens", 0))
    completion = envelope.get("eval_count", envelope.get("completion_tokens", 0))
    try:
        return int(prompt or 0), int(completion or 0)
    except (TypeError, ValueError):
        return 0, 0


def load_saved_arm(path: Path, fixtures: dict[str, dict], label: str) -> list[dict[str, Any]]:
    """Load and integrity-check one saved 80-case arm."""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        case = fixtures[row["case_id"]]
        if row.get("role") != case["role"] or row.get("family") != case["family"]:
            raise ValueError(f"{label}: metadata mismatch for {row['case_id']}")
        attempts = row.get("attempts", [])
        if not 1 <= len(attempts) <= 2:
            raise ValueError(f"{label}: bad attempt count for {row['case_id']}")
        scored = score_saved_attempt(case, attempts[-1])
        frozen = scored["frozen"]
        pairs = canonical_pairs(
            case, attempts[-1].get("parsed") if not attempts[-1].get("error") else None
        )
        prompt_tokens, completion_tokens = _tokens(attempts[-1])
        rows.append({
            "case_id": row["case_id"], "role": row["role"], "family": row["family"],
            "exact_pass": bool(frozen["passed"]), "invalid_output": bool(frozen["invalid_output"]),
            "frozen": frozen, "diagnostics": scored["diagnostics_v1"], "pairs": pairs,
            "elapsed_ms": float(attempts[-1].get("elapsed_ms", 0)),
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
            "attempts": len(attempts),
        })
    if len(rows) != 80 or len({row["case_id"] for row in rows}) != 80:
        raise ValueError(f"{label}: expected 80 unique saved cases")
    return rows


def arm_report(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    passes = sum(row["exact_pass"] for row in rows)
    truth = [t for row in rows for t, _ in row["pairs"]]
    predicted = [p for row in rows for _, p in row["pairs"]]
    by_agent: dict[str, Any] = {}
    for agent in AGENTS:
        subset = [row for row in rows if row["role"] == agent]
        if not subset:
            continue
        sub_truth = [t for row in subset for t, _ in row["pairs"]]
        sub_pred = [p for row in subset for _, p in row["pairs"]]
        by_agent[agent] = {
            "exact_pass": sum(row["exact_pass"] for row in subset),
            "cases": len(subset),
            "classification": classification_report(sub_truth, sub_pred),
            "abstention": abstention_metrics(sub_truth, sub_pred),
        }
    low, high = wilson_interval(passes, len(rows))
    return {
        "arm": label,
        "rubric_version": RUBRIC_VERSION,
        "exact": {
            "passes": passes, "cases": len(rows), "rate": round(passes / len(rows), 6),
            "wilson_ci95": [round(low, 6), round(high, 6)],
            "note": "Exact role-contract pass. Separate from confusion-matrix metrics.",
        },
        "classification_overall": classification_report(truth, predicted),
        "abstention_overall": abstention_metrics(truth, predicted),
        "error_cases": distinct_error_counts([row["diagnostics"] for row in rows], ERROR_KEYS),
        "invalid_outputs": sum(row["invalid_output"] for row in rows),
        "tokens": {
            "prompt": sum(row["prompt_tokens"] for row in rows),
            "completion": sum(row["completion_tokens"] for row in rows),
        },
        "attempts": sum(row["attempts"] for row in rows),
        "latency_ms": {
            "p50": _percentile([row["elapsed_ms"] for row in rows], 0.5),
            "p90": _percentile([row["elapsed_ms"] for row in rows], 0.9),
            "p95": _percentile([row["elapsed_ms"] for row in rows], 0.95),
            "note": "Cloud and local endpoint times are not comparable; reported, never used for ranking.",
        },
        "by_agent": by_agent,
    }


def _percentile(values: list[float], fraction: float) -> float:
    from .statistics import percentile
    return round(percentile(values, fraction), 3)


def compare_arms(candidate: list[dict[str, Any]], reference: list[dict[str, Any]]) -> dict[str, Any]:
    if [row["case_id"] for row in candidate] != [row["case_id"] for row in reference]:
        raise ValueError("Paired arms must use the same case order")
    diff = [float(a["exact_pass"]) - float(b["exact_pass"]) for a, b in zip(candidate, reference, strict=True)]
    clusters = [row["family"] for row in candidate]
    return {
        "exact_pass_difference": paired_bootstrap(diff, replicates=5000, seed=20261123),
        "family_clustered_exact_pass_difference": paired_bootstrap(
            diff, replicates=5000, seed=20261123, cluster=clusters
        ),
        "mcnemar": mcnemar_exact(
            [row["exact_pass"] for row in candidate], [row["exact_pass"] for row in reference]
        ),
    }


def markdown_summary(result: dict[str, Any]) -> str:
    lines = [
        "# Offline re-analysis of saved outputs",
        "",
        "No new inference or paid call was made. Stored raw responses were re-scored with the "
        "untouched frozen scorer and stored scores were verified.",
        "",
        f"Rubric: `{result['rubric_version']}`. Manifest: `{result['manifest_sha256']}`.",
        "",
        "## Exact case-level accuracy (historical baseline)",
        "",
        "| Arm | Passes | Rate | Wilson 95% CI | Invalid |",
        "| --- | ---: | ---: | --- | ---: |",
    ]
    for arm in result["arms"]:
        exact = arm["exact"]
        lines.append(
            f"| {arm['arm']} | {exact['passes']}/80 | {100 * exact['rate']:.2f}% | "
            f"[{100 * exact['wilson_ci95'][0]:.2f}, {100 * exact['wilson_ci95'][1]:.2f}]% | "
            f"{arm['invalid_outputs']} |"
        )
    lines += ["", "## Canonical decision confusion (rows=truth, columns=prediction)", ""]
    for arm in result["arms"]:
        cm = arm["classification_overall"]["confusion"]
        lines += [f"### {arm['arm']}", "", "label | " + " | ".join(cm["labels"]), "--- | " + " | ".join("---:" for _ in cm["labels"])]
        for label, row in zip(cm["labels"], cm["matrix"], strict=True):
            lines.append(f"{label} | " + " | ".join(str(value) for value in row))
        metrics = arm["classification_overall"]
        lines += [
            "",
            f"macro F1 `{metrics['macro_f1']}`, weighted F1 `{metrics['weighted_f1']}`, "
            f"balanced accuracy `{metrics['balanced_accuracy']}`.",
            "",
        ]
    lines += ["## Paired uncertainty and error categories", ""]
    for pair in result["comparisons"]:
        diff = pair["exact_pass_difference"]
        clustered = pair["family_clustered_exact_pass_difference"]
        lines.append(
            f"- **{pair['candidate']} − {pair['reference']}**: {100 * diff['estimate']:.2f} pp "
            f"(case 95% CI {100 * diff['ci95'][0]:.2f} to {100 * diff['ci95'][1]:.2f}; "
            f"family-cluster 95% CI {100 * clustered['ci95'][0]:.2f} to {100 * clustered['ci95'][1]:.2f}); "
            f"McNemar p={pair['mcnemar']['p_two_sided']}."
        )
    cloud = result["arms"][0]
    lines += ["", f"Distinct error-bearing cases in {cloud['arm']}:", ""]
    for key, value in cloud["error_cases"].items():
        lines.append(f"- `{key}`: {value}")
    lines += [
        "",
        "Repeats and agents are not independent cases. These numbers describe the saved "
        "retrospective cohort only; they are not a fresh blinded holdout or a production estimate.",
        "",
    ]
    return "\n".join(lines)
