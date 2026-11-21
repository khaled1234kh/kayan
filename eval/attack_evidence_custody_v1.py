"""Offline custody gate over an independently supplied case assignment and head."""
from collections.abc import Mapping
from dataclasses import dataclass

from eval.attack_evidence_v2 import parse
from eval.attack_fact_guard_adapter_v1 import evaluate
from eval.attack_fact_registry_v1 import Snapshot, bytes_digest, digest


def active_roster(rows):
    """Return exact digests of the latest revision for each assertion."""
    heads = {}
    for row in rows:
        if row.revision > getattr(heads.get(row.id), "revision", 0):
            heads[row.id] = row
    return frozenset(digest(row.model_dump(mode="json")) for row in heads.values())


def revision_history(rows):
    return frozenset(digest(row.model_dump(mode="json")) for row in rows)


@dataclass(frozen=True)
class CustodyHead:
    case_id: str
    sequence: int
    snapshot_sha256: str
    previous_snapshot_sha256: str | None
    assertion_roster: frozenset[str]
    assertion_history: frozenset[str]
    receipt_history: frozenset[str]


@dataclass(frozen=True)
class CustodyAuthority:
    """Inputs from the external custodian, including the current assigned head."""
    assigned_case_id: str
    current: CustodyHead
    previous: CustodyHead | None
    approved_receipts: Mapping[str, frozenset[str]]
    verification_time: str


def _check_snapshot(raw_manifest, authority, *, snapshot_type=Snapshot, pin_first=False):
    current, previous = authority.current, authority.previous
    snapshot_sha256 = bytes_digest(raw_manifest)
    if pin_first and snapshot_sha256 != current.snapshot_sha256:
        if previous is not None and snapshot_sha256 == previous.snapshot_sha256:
            raise ValueError("custody_rollback")
        raise ValueError("custody_snapshot_mismatch")
    snapshot = snapshot_type.model_validate(parse(raw_manifest))
    if not authority.assigned_case_id == current.case_id == snapshot.case_id:
        raise ValueError("custody_case_mismatch")
    if previous is None:
        if current.sequence != 1 or current.previous_snapshot_sha256 is not None:
            raise ValueError("custody_missing_predecessor")
    else:
        if (current.case_id != previous.case_id or current.sequence != previous.sequence + 1
                or current.previous_snapshot_sha256 != previous.snapshot_sha256):
            raise ValueError("custody_invalid_continuity")
        if snapshot_sha256 == previous.snapshot_sha256:
            raise ValueError("custody_rollback")
        if not (previous.assertion_history <= current.assertion_history
                and previous.receipt_history <= current.receipt_history):
            raise ValueError("custody_history_rewrite")

    if active_roster(snapshot.assertions) != current.assertion_roster:
        raise ValueError("custody_assertion_roster_mismatch")
    if (revision_history(snapshot.assertions) != current.assertion_history
            or revision_history(snapshot.receipts) != current.receipt_history):
        raise ValueError("custody_revision_history_mismatch")
    if snapshot_sha256 != current.snapshot_sha256:
        raise ValueError("custody_snapshot_mismatch")


def evaluate_in_custody(raw_proposal, raw_manifest, payloads, *, authority):
    """Check custody, then invoke the existing offline verifier and adapter.

    The submission supplies only proposal, manifest and evidence bytes. The
    caller must obtain the latest authority and its predecessor independently
    of the submission. The gate has no network, enrolment or persistent state.
    """
    return _evaluate_in_custody(raw_proposal, raw_manifest, payloads, authority=authority)


def _evaluate_in_custody(raw_proposal, raw_manifest, payloads, *, authority,
                         snapshot_type=Snapshot, pin_first=False, evaluator=evaluate):
    try:
        _check_snapshot(raw_manifest, authority, snapshot_type=snapshot_type, pin_first=pin_first)
    except (TypeError, ValueError, RecursionError) as exc:
        reason = str(exc)
        return {
            "batch_state": "invalid", "claims": [], "review_items": [],
            "error": reason if reason.startswith("custody_") else "custody_invalid_snapshot",
        }
    return evaluator(raw_proposal, raw_manifest, payloads,
                     expected_sha256=authority.current.snapshot_sha256,
                     approved_receipts=authority.approved_receipts,
                     at=authority.verification_time)
