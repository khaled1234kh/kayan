"""Human review and versioned adjudication for defensive ATT&CK evidence."""

from collections import Counter
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from eval.ai_mapping_review import DISPOSITIONS, agreement, validate

RUBRIC = "attack-evidence-sets-v1"
SHA = r"^[a-f0-9]{64}$"


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class Reviewer(Document):
    slot: str
    identity: str = Field(min_length=2)
    qualification: str = Field(min_length=3)
    completed_on: str
    returned_sha256: str = Field(pattern=SHA)
    issued_form_sha256: str = Field(pattern=SHA)
    independently_reviewed_without_labels_or_model_outputs: bool


class ReviewReceipt(Document):
    packet_sha256: str = Field(pattern=SHA)
    taxonomy_sha256: str = Field(pattern=SHA)
    coordinator: str = Field(min_length=2)
    originals_and_independence_verified: bool
    reviewers: list[Reviewer] = Field(min_length=2, max_length=2)


class AdjudicatedCase(Document):
    id: str
    disposition: str
    resolution: str
    evidence_sets: dict[str, list[list[str]]]
    rationale: str = Field(min_length=8)


class Adjudication(Document):
    rubric: str
    label_version: str = Field(min_length=1)
    packet_sha256: str = Field(pattern=SHA)
    agreement_sha256: str = Field(pattern=SHA)
    adjudicator: str = Field(min_length=2)
    adjudicated_on: str
    cases: list[AdjudicatedCase] = Field(min_length=1)


class Approval(Document):
    rubric: str
    comparison: str
    stakeholder: str = Field(min_length=2)
    approved_on: str
    adjudications_sha256: dict[str, str]
    protocol_sha256: str = Field(pattern=SHA)
    unsupported_pair_weight: float = Field(gt=0, allow_inf_nan=False)
    missed_pair_weight: float = Field(gt=0, allow_inf_nan=False)
    min_weighted_improvement_per_case: float = Field(gt=0, allow_inf_nan=False)
    max_negative_specificity_loss: float = Field(ge=0, le=1, allow_inf_nan=False)
    interval_requirement: str
    rationale: str = Field(min_length=8)


def metadata_date(value):
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Dates must use YYYY-MM-DD")
    return parsed


def resolve_receipt(receipt, packet_hash, taxonomy_hash, submissions, blank_hashes):
    reviewers = {entry.slot: entry for entry in receipt.reviewers}
    if (receipt.packet_sha256 != packet_hash or receipt.taxonomy_sha256 != taxonomy_hash
            or reviewers.keys() != {"A", "B"} or not receipt.originals_and_independence_verified):
        raise ValueError("Coordinator has not verified two genuine returns for this packet and taxonomy")
    identities = {item.identity.casefold() for item in reviewers.values()}
    if len(identities) != 2:
        raise ValueError("Reviewer identities must be distinct")
    if len(set(submissions.values())) != 2:
        raise ValueError("Two different original submissions are required")
    for slot, entry in reviewers.items():
        metadata_date(entry.completed_on)
        if (not entry.independently_reviewed_without_labels_or_model_outputs
                or entry.returned_sha256 != submissions[slot]
                or entry.issued_form_sha256 != blank_hashes[slot]):
            raise ValueError(f"Missing independent review or mismatched original for reviewer {slot}")
    return reviewers


def compare_reviews(first, second, packet, active_ids):
    result = agreement(first, second, packet, active_ids)
    paired = list(zip(*(sorted(validate(sheet, packet, active_ids).values(), key=lambda row: row["id"])
                        for sheet in (first, second)), strict=True))
    for metric, select in (
        ("disposition", lambda row: row["disposition"]),
        ("any_mapping", lambda row: bool(row["mappings"])),
        ("exact_technique_set", lambda row: set(row["mappings"])),
        ("exact_technique_record_pairs", lambda row: {
            (technique, rid) for technique, ids in row["mappings"].items() for rid in ids}),
    ):
        left, right = zip(*[(select(a), select(b)) for a, b in paired], strict=True)
        report = result["metrics"][metric]
        if metric.startswith("exact"):
            report.update(cohens_kappa=None, kappa_reason="Set-valued labels",
                          macro_jaccard=sum(len(a & b) / len(a | b) if a | b else 1
                                           for a, b in zip(left, right, strict=True)) / len(left))
        elif len(Counter(left)) < 2 or len(Counter(right)) < 2:
            report.update(cohens_kappa=None, kappa_reason="At least one reviewer has no category variation")
    return result


def validate_adjudication(labels, observations, active_ids, *, packet_hash, agreement_hash, after_date):
    if (labels.rubric != RUBRIC or labels.packet_sha256 != packet_hash
            or labels.agreement_sha256 != agreement_hash
            or metadata_date(labels.adjudicated_on) < after_date):
        raise ValueError("Adjudication does not bind the completed review, rubric and packet")
    rows = {row.id: row for row in labels.cases}
    if rows.keys() != observations.keys() or len(rows) != len(labels.cases):
        raise ValueError("Adjudication must cover every case exactly once")
    for cid, row in rows.items():
        if row.disposition not in DISPOSITIONS or row.resolution not in {"score", "exclude_ambiguous"}:
            raise ValueError(f"Invalid disposition or unresolved adjudication in {cid}")
        if row.evidence_sets and (row.resolution != "score" or row.disposition != "confirmed_adversary"):
            raise ValueError(f"Only scored confirmed behavior can carry evidence groups in {cid}")
        for tid, groups in row.evidence_sets.items():
            evidence_sets = {frozenset(group) for group in groups}
            if (tid not in active_ids or not groups or len(evidence_sets) != len(groups)
                    or any(not group or len(set(group)) != len(group) or not set(group) <= observations[cid].keys()
                           for group in groups)
                    or any(left < right for left in evidence_sets for right in evidence_sets)):
                raise ValueError(f"Evidence groups must be distinct, minimal and grounded in {cid}/{tid}")
    return rows
