"""Independent annotation support with no invented reviewers or adjudications.

The module issues blinded forms, compares two real returned sheets, records
disagreements, and only allows labels to become ``frozen`` after a bound
adjudication by a named adjudicator dated after both reviews.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from typing import Any

from .scoring import frozen_modules

PLACEHOLDERS = {"a", "b", "reviewer a", "reviewer b", "reviewer", "test", "anonymous", "tbd", "none", "n/a"}


def sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def parse_date(value: str) -> date:
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Dates must be YYYY-MM-DD")
    return parsed


def _real_identity(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) < 3 or cleaned.casefold() in PLACEHOLDERS:
        raise ValueError("A real, named reviewer/adjudicator identity is required")
    return cleaned


def cohens_kappa(first: list[str], second: list[str], categories: list[str]) -> float | None:
    """Unweighted Cohen's kappa for single categorical labels."""
    if len(first) != len(second) or not first:
        raise ValueError("Raters must cover the same nonempty items")
    n = len(first)
    observed = sum(a == b for a, b in zip(first, second, strict=True)) / n
    left, right = Counter(first), Counter(second)
    expected = sum((left[c] / n) * (right[c] / n) for c in categories)
    if expected >= 1:
        return None
    return round((observed - expected) / (1 - expected), 6)


def jaccard(set_a: set[str], set_b: set[str]) -> float:
    return len(set_a & set_b) / len(set_a | set_b) if set_a | set_b else 1.0


def issue_blind_forms(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Create two blank forms containing evidence only, in fixed case order.

    Ground truth, model output, provenance author and annotation status are
    removed. Nothing here constitutes a label.
    """
    forms: dict[str, list[dict[str, Any]]] = {"A": [], "B": []}
    for case in sorted(cases, key=lambda row: row["case_id"]):
        row = {
            "case_id": case["case_id"],
            "agent": case["agent"],
            "scenario_family": case["scenario_family"],
            "evidence": case["evidence"],
            "citations": case["citations"],
            "actions": case["actions"],
            "scope": case["scope"],
            "limitations": case["limitations"],
        }
        forms["A"].append(json.loads(json.dumps(row)))
        forms["B"].append(json.loads(json.dumps(row)))
    packet = {"rubric": "decision-label-rubric-v1", "cases": forms["A"]}
    packet["packet_sha256"] = sha256_json(packet)
    return {
        "rubric": packet["rubric"],
        "packet_sha256": packet["packet_sha256"],
        "forms": {
            slot: {"form_sha256": sha256_json({"packet_sha256": packet["packet_sha256"], "slot": slot,
                                               "cases": rows}),
                   "slot": slot, "cases": rows}
            for slot, rows in forms.items()
        },
    }


def validate_annotation(
    sheet: dict[str, Any], packet: dict[str, Any], *, slot: str, identity: str,
    qualification: str, completed_on: str, returned_sha256: str,
    independently_reviewed: bool,
) -> dict[str, Any]:
    """Bind a returned, independently produced annotation sheet to its form."""
    role_cases, _ = frozen_modules()
    if slot not in {"A", "B"}:
        raise ValueError("slot must be A or B")
    _real_identity(identity)
    if len(qualification.strip()) < 3:
        raise ValueError("A reviewer qualification is required")
    parse_date(completed_on)
    if not independently_reviewed:
        raise ValueError("Independence attestation is mandatory")
    form_hash = packet["forms"][slot]["form_sha256"]
    if returned_sha256 != sha256_json(sheet):
        raise ValueError("Returned sheet hash does not match the submitted bytes")
    if sheet.get("slot") != slot or sheet.get("issued_form_sha256") != form_hash:
        raise ValueError("Sheet does not bind the issued blinded form")
    expected_ids = [row["case_id"] for row in packet["forms"][slot]["cases"]]
    rows = sheet.get("decisions", [])
    got_ids = [row["case_id"] for row in rows]
    if sorted(got_ids) != sorted(expected_ids) or len(got_ids) != len(set(got_ids)):
        raise ValueError("Annotation must cover every case exactly once")
    by_id = {row["case_id"]: row for row in rows}
    for case in packet["forms"][slot]["cases"]:
        row = by_id[case["case_id"]]
        labels = role_cases.LABELS[case["agent"]]
        if row.get("label") not in labels:
            raise ValueError(f"Invalid label for {case['case_id']}")
        allowed = {record["record_id"] for record in case["evidence"]}
        if not set(row.get("evidence_ids", [])) <= allowed:
            raise ValueError(f"Evidence outside the blinded packet for {case['case_id']}")
        if len(row.get("rationale", "").strip()) < 12:
            raise ValueError(f"A written justification is required for {case['case_id']}")
    return {
        "slot": slot, "identity": _real_identity(identity), "qualification": qualification.strip(),
        "completed_on": completed_on, "returned_sha256": returned_sha256,
        "issued_form_sha256": form_hash, "independently_reviewed": True,
        "cases": len(rows),
    }


def compare_annotations(sheet_a: dict[str, Any], sheet_b: dict[str, Any], packet: dict[str, Any]) -> dict[str, Any]:
    """Compute agreement and explicit disagreement records for two reviewers."""
    left = {row["case_id"]: row for row in sheet_a["decisions"]}
    right = {row["case_id"]: row for row in sheet_b["decisions"]}
    if left.keys() != right.keys():
        raise ValueError("Reviewers annotated different case sets")
    role_by_id = {row["case_id"]: row["agent"] for row in packet["forms"]["A"]["cases"]}
    categories = sorted({row["label"] for row in left.values()} | {row["label"] for row in right.values()})
    label_a = [left[cid]["label"] for cid in sorted(left)]
    label_b = [right[cid]["label"] for cid in sorted(right)]
    disagreements = []
    evidence_jaccard = []
    for cid in sorted(left):
        a, b = left[cid], right[cid]
        set_a, set_b = set(a["evidence_ids"]), set(b["evidence_ids"])
        evidence_jaccard.append(jaccard(set_a, set_b))
        if a["label"] != b["label"] or set_a != set_b:
            disagreements.append({
                "case_id": cid,
                "agent": role_by_id[cid],
                "reviewer_a": {"label": a["label"], "evidence_ids": sorted(set_a)},
                "reviewer_b": {"label": b["label"], "evidence_ids": sorted(set_b)},
                "label_conflict": a["label"] != b["label"],
                "evidence_conflict": set_a != set_b,
                "resolution": "pending",
            })
    report = {
        "rubric": packet["rubric"],
        "packet_sha256": packet["packet_sha256"],
        "n_cases": len(left),
        "raw_label_agreement": round(sum(a == b for a, b in zip(label_a, label_b, strict=True)) / len(left), 6),
        "cohens_kappa_label": cohens_kappa(label_a, label_b, categories),
        "raw_evidence_set_agreement": round(sum(j == 1 for j in evidence_jaccard) / len(left), 6),
        "mean_evidence_jaccard": round(sum(evidence_jaccard) / len(left), 6),
        "disagreements": disagreements,
        "requires_adjudication": bool(disagreements),
    }
    report["agreement_sha256"] = sha256_json(report)
    return report


def validate_adjudication(
    adjudication: dict[str, Any], *,
    packet: dict[str, Any], agreement: dict[str, Any],
    reviewer_dates: list[str], cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """A frozen label set must bind the packet and completed disagreement report."""
    if adjudication.get("packet_sha256") != packet["packet_sha256"]:
        raise ValueError("Adjudication does not bind the blinded packet")
    if adjudication.get("agreement_sha256") != agreement["agreement_sha256"]:
        raise ValueError("Adjudication does not bind the completed agreement report")
    adjudicator = _real_identity(str(adjudication.get("adjudicator", "")))
    adjudicated_on = parse_date(adjudication.get("adjudicated_on", ""))
    if adjudicated_on < max(parse_date(value) for value in reviewer_dates):
        raise ValueError("Adjudication must follow both completed reviews")
    if not str(adjudication.get("label_version", "")).strip():
        raise ValueError("A label version is required")
    rows = {row["case_id"]: row for row in adjudication.get("cases", [])}
    expected_ids = [case["case_id"] for case in cases]
    if rows.keys() != set(expected_ids) or len(rows) != len(expected_ids):
        raise ValueError("Adjudication must cover every case exactly once")
    role_cases, _ = frozen_modules()
    for case in cases:
        row = rows[case["case_id"]]
        if row.get("label") not in role_cases.LABELS[case["agent"]]:
            raise ValueError(f"Invalid adjudicated label for {case['case_id']}")
        if row.get("resolution") not in {"score", "exclude_ambiguous"}:
            raise ValueError(f"Unresolved adjudication for {case['case_id']}")
        if len(row.get("rationale", "").strip()) < 12:
            raise ValueError(f"Adjudication rationale required for {case['case_id']}")
        if row.get("resolution") == "score" and not set(row.get("evidence_ids", [])):
            raise ValueError(f"Scored case needs frozen citations for {case['case_id']}")
    return {
        "adjudicator": adjudicator, "adjudicated_on": adjudicated_on.isoformat(),
        "label_version": adjudication["label_version"],
        "adjudication_sha256": sha256_json(adjudication),
        "cases": len(rows),
    }


def freeze_labels(cases: list[dict[str, Any]], adjudication: dict[str, Any]) -> list[dict[str, Any]]:
    """Apply bound adjudicated labels; never invent reviewer identities."""
    rows = {row["case_id"]: row for row in adjudication["cases"]}
    frozen = []
    for case in cases:
        row = rows[case["case_id"]]
        updated = json.loads(json.dumps(case))
        if row["resolution"] == "score":
            updated["ground_truth"]["decisions"] = [{
                "item_id": item["item_id"],
                "label": row["label"],
                "evidence_ids": row["evidence_ids"],
            } for item in case["ground_truth"]["decisions"]]
        updated["annotation_status"] = "frozen"
        updated["provenance"] = {
            **case["provenance"],
            "independent": True,
            "label_version": adjudication["label_version"],
            "adjudicator": adjudication["adjudicator"],
            "adjudication_sha256": sha256_json(adjudication),
        }
        frozen.append(updated)
    return frozen
