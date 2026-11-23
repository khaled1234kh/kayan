"""Versioned decision-case dataset schema, loader and manifest tooling."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import AGENTS, DATASET_REVISION, RUBRIC_VERSION
from .scoring import frozen_modules

REQUIRED_FIELDS = {
    "case_id", "dataset_revision", "scenario_family", "agent", "challenge_category",
    "evidence", "ground_truth", "citations", "abstention", "actions", "scope",
    "limitations", "rubric_version", "provenance", "annotation_status",
}
VALID_STATUS = {"provisional", "frozen"}
CHALLENGE_CATEGORIES = {
    "positive", "negative", "contradictory", "ambiguous", "incomplete",
    "benign", "similar_but_unrelated", "multi_record", "cross_session",
    "attack_ambiguous", "missing_link", "adversarial_instruction",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_case(case: dict[str, Any], *, require_frozen: bool = False) -> dict[str, Any]:
    missing = REQUIRED_FIELDS - set(case)
    if missing:
        raise ValueError(f"{case.get('case_id', '<unknown>')}: missing {sorted(missing)}")
    if case["agent"] not in AGENTS:
        raise ValueError(f"Unknown agent {case['agent']!r}")
    if case["challenge_category"] not in CHALLENGE_CATEGORIES:
        raise ValueError(f"Unknown challenge category {case['challenge_category']!r}")
    if case["annotation_status"] not in VALID_STATUS:
        raise ValueError(f"Unknown annotation status {case['annotation_status']!r}")
    if require_frozen and case["annotation_status"] != "frozen":
        raise ValueError(f"{case['case_id']}: labels are not frozen")
    role_cases, _ = frozen_modules()
    labels = role_cases.LABELS[case["agent"]]
    decisions = case["ground_truth"].get("decisions", [])
    if not decisions:
        raise ValueError(f"{case['case_id']}: no ground-truth decisions")
    item_ids = [row["item_id"] for row in decisions]
    if len(item_ids) != len(set(item_ids)):
        raise ValueError(f"{case['case_id']}: duplicate item ids")
    record_ids = {row["record_id"] for row in case["evidence"]}
    if len(record_ids) != len(case["evidence"]):
        raise ValueError(f"{case['case_id']}: duplicate evidence record ids")
    for row in decisions:
        if row["label"] not in labels:
            raise ValueError(f"{case['case_id']}: invalid label {row['label']!r}")
        unknown = set(row.get("evidence_ids", [])) - record_ids
        if unknown:
            raise ValueError(f"{case['case_id']}: unknown evidence ids {sorted(unknown)}")
    if case["agent"] != "Planner" and case["ground_truth"].get("dependencies") not in (None, {}):
        raise ValueError(f"{case['case_id']}: dependencies only apply to Planner cases")
    if case["agent"] == "Planner" and not case["ground_truth"].get("dependencies"):
        raise ValueError(f"{case['case_id']}: Planner case needs dependencies")
    if not case["scope"].get("authorized") or case["scope"].get("environment") != "synthetic":
        raise ValueError(f"{case['case_id']}: synthetic authorized scope is mandatory")
    if not case["limitations"]:
        raise ValueError(f"{case['case_id']}: limitations are mandatory")
    if case["rubric_version"] != RUBRIC_VERSION:
        raise ValueError(f"{case['case_id']}: unexpected rubric version")
    if case["dataset_revision"] != DATASET_REVISION:
        raise ValueError(f"{case['case_id']}: unexpected dataset revision")
    provenance = case["provenance"]
    if provenance.get("independent") is not False or not provenance.get("author"):
        raise ValueError(f"{case['case_id']}: provenance must be explicit and non-independent")
    return case


def load_dataset(path: Path, *, require_frozen: bool = False) -> list[dict[str, Any]]:
    cases = []
    seen = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        case = json.loads(line)
        if case["case_id"] in seen:
            raise ValueError(f"Duplicate case_id {case['case_id']} at line {number}")
        seen.add(case["case_id"])
        cases.append(validate_case(case, require_frozen=require_frozen))
    if not cases:
        raise ValueError("empty dataset")
    return cases


def write_manifest(paths: list[Path], output: Path) -> str:
    lines = [f"{sha256_file(path)}  {path.name}" for path in sorted(paths, key=lambda p: p.name)]
    text = "\n".join(lines) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return text


def verify_manifest(directory: Path, manifest_name: str = "SHA256SUMS.txt") -> dict[str, bool]:
    results = {}
    for line in (directory / manifest_name).read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        results[name] = sha256_file(directory / name) == expected
    if not results or not all(results.values()):
        raise ValueError(f"Manifest verification failed in {directory}")
    return results


LEGACY_REGISTRATION = Path(__file__).resolve().parent / "datasets" / "attack_v2_registration_reference.json"


def audit_legacy_cohort(registration: Path | None = None) -> dict[str, Any]:
    """Audit the historical 18-case extraction cohort without re-labelling it.

    The registration records an AI-authored synthetic key, nine positive and
    nine negative/ambiguous items, six families and two repeated passes over
    the same cases. It is development material, not a fresh blinded holdout.
    """
    source = registration or LEGACY_REGISTRATION
    data = json.loads(source.read_text(encoding="utf-8"))
    counts = data.get("counts", {})
    verdict = "development_only"
    return {
        "source": source.name,
        "study": data.get("study"),
        "label_source": data.get("label_source"),
        "cases": counts.get("cases"),
        "families": counts.get("families"),
        "positive_cases": counts.get("dispositions", {}).get("confirmed"),
        "negative_or_ambiguous_cases": sum(
            value for key, value in counts.get("dispositions", {}).items() if key != "confirmed"
        ),
        "repeats": data.get("repeats"),
        "independent_adjudication": False,
        "fresh_unseen_holdout": False,
        "verdict": verdict,
        "allowed_use": "pilot / calibration / failure-mode discovery only",
        "references": [
            "docs/ATTACK_ROOT_CAUSE_V3_2026-11-20.md#dataset-limits",
            "docs/ATTACK_EXPLORATORY_V2_RESULTS_2026-11-20.md",
        ],
        "reason": "Author-generated labels and repeated cases; no independent human review or frozen adjudication.",
    }
