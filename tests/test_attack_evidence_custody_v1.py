from dataclasses import replace
import json

import pytest

from eval.attack_evidence_custody_v1 import (
    CustodyAuthority, CustodyHead, active_roster, evaluate_in_custody, revision_history,
)
from eval.attack_fact_guard_adapter_v1 import evaluate
from eval.attack_fact_registry_v1 import Snapshot, bytes_digest
from eval.fixtures.ai.attack_fact_registry_v1.demo import AT, proposal, seal_fixture, windows

CLEAR = proposal(**{"T1685.005": ("E1.1", "E2.1", "E3.1")})


def issue(raw, approvals, previous=None, *, at=AT):
    """Synthetic external custodian. Issue only from authorized fixture data."""
    snapshot = Snapshot.model_validate_json(raw)
    head = CustodyHead(
        case_id=snapshot.case_id,
        sequence=1 if previous is None else previous.sequence + 1,
        snapshot_sha256=bytes_digest(raw),
        previous_snapshot_sha256=None if previous is None else previous.snapshot_sha256,
        assertion_roster=active_roster(snapshot.assertions),
        assertion_history=revision_history(snapshot.assertions),
        receipt_history=revision_history(snapshot.receipts),
    )
    return CustodyAuthority(snapshot.case_id, head, previous,
                            {key: frozenset(ids) for key, ids in approvals.items()}, at)


def encode(case):
    return json.dumps(case, sort_keys=True).encode()


def checked(raw, data, assigned):
    return evaluate_in_custody(CLEAR, raw, data, authority=assigned)


def legacy(raw, data, approvals, at=AT):
    return evaluate(CLEAR, raw, data, expected_sha256=bytes_digest(raw),
                    approved_receipts=approvals, at=at)


def adverse_successor():
    case, data = windows()
    prior, _, approvals = seal_fixture(case)
    predecessor = issue(prior, approvals)
    adverse = {**case["assertions"][-1], "id": "adverse", "value": "authorized",
               "receipt": {"id": "adverse", "revision": 1}}
    case["assertions"].append(adverse)
    raw, _, approvals = seal_fixture(case)
    return case, data, prior, raw, issue(raw, approvals, predecessor.current)


def test_consistent_genesis_and_adverse_successor():
    _, data, prior, raw, assigned = adverse_successor()
    assert checked(prior, data, issue(prior, assigned.approved_receipts))["batch_state"] == "all_eligible"
    result = checked(raw, data, assigned)
    assert result["batch_state"] == "none_eligible"
    assert "conflicting_or_superseded_evidence" in result["claims"][0]["reasons"]


def test_adverse_omission_with_replacement_pin_cannot_change_custodian_roster():
    case, data, _, _, assigned = adverse_successor()
    del case["assertions"][-1]
    stripped = encode(case)
    assert legacy(stripped, data, assigned.approved_receipts)["batch_state"] == "all_eligible"
    replaced_head = replace(assigned.current, snapshot_sha256=bytes_digest(stripped))
    assert checked(stripped, data, assigned)["error"] == "custody_assertion_roster_mismatch"
    assert checked(stripped, data, replace(assigned, current=replaced_head))["error"] == (
        "custody_assertion_roster_mismatch"
    )


@pytest.mark.parametrize("variant", ["missing", "wrong_head", "skipped_sequence", "other_case"])
def test_snapshot_replacement_requires_continuity(variant):
    _, data, _, raw, assigned = adverse_successor()
    assert legacy(raw, data, assigned.approved_receipts)["batch_state"] == "none_eligible"
    if variant == "missing":
        altered = replace(assigned, previous=None)
        reason = "custody_missing_predecessor"
    elif variant == "wrong_head":
        altered = replace(assigned, current=replace(assigned.current, previous_snapshot_sha256="0" * 64))
        reason = "custody_invalid_continuity"
    elif variant == "skipped_sequence":
        altered = replace(assigned, current=replace(assigned.current, sequence=3))
        reason = "custody_invalid_continuity"
    else:
        altered = replace(assigned, previous=replace(assigned.previous, case_id="wrong-case"))
        reason = "custody_invalid_continuity"
    assert checked(raw, data, altered)["error"] == reason


def test_bytes_outside_state_roster_are_still_exactly_pinned():
    _, data, _, raw, assigned = adverse_successor()
    assert checked(raw + b" ", data, assigned)["error"] == "custody_snapshot_mismatch"


def test_rollback_rejected_even_if_old_bytes_are_valid():
    _, data, prior, _, assigned = adverse_successor()
    assert legacy(prior, data, assigned.approved_receipts)["batch_state"] == "all_eligible"
    assert checked(prior, data, assigned)["error"] == "custody_rollback"


@pytest.mark.parametrize("change", ["revocation", "withdrawal", "supersession"])
def test_decision_history_cannot_be_omitted(change):
    case, data = windows()
    prior, _, approvals = seal_fixture(case)
    head = issue(prior, approvals).current
    if change == "revocation":
        first = case["receipts"][0]
        case["receipts"].append({**first, "revision": 2, "supersedes": 1, "decision": "revoked"})
        raw = encode(case)
        expected = "custody_revision_history_mismatch"
    else:
        assertion = case["assertions"][-1]
        case["assertions"].append({
            **assertion, "revision": 2, "supersedes": 1, "receipt": {"id": "new", "revision": 1},
            **({"state": "withdrawn"} if change == "withdrawal" else {"value": "authorized"}),
        })
        raw, _, approvals = seal_fixture(case)
        expected = "custody_assertion_roster_mismatch"
    assigned = issue(raw, approvals, head)
    assert checked(raw, data, assigned)["batch_state"] == (
        "invalid" if change == "revocation" else "none_eligible"
    )
    if change == "revocation":
        del case["receipts"][-1]
    else:
        del case["assertions"][-1]
    omitted = encode(case)
    assert legacy(omitted, data, approvals)["batch_state"] == "all_eligible"
    assert checked(omitted, data, assigned)["error"] == expected


def test_even_a_repinned_successor_cannot_erase_predecessor_history():
    case, data, _, adverse, assigned = adverse_successor()
    latest = assigned.current
    case["assertions"].pop()
    case["receipts"].pop()
    omitted = encode(case)
    reissued = issue(omitted, assigned.approved_receipts, latest)
    assert assigned.current.snapshot_sha256 == bytes_digest(adverse)
    assert checked(omitted, data, reissued)["error"] == "custody_history_rewrite"


def test_expired_receipt_uses_only_custodian_clock():
    case, data = windows()
    raw, _, approvals = seal_fixture(case)
    assert legacy(raw, data, approvals, at=AT)["batch_state"] == "all_eligible"
    assigned = issue(raw, approvals, at="2026-11-21T00:00:00Z")
    result = checked(raw, data, assigned)
    assert result["batch_state"] == "invalid"
    assert result["error"] == "untrusted, expired or stale review receipt"
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        evaluate_in_custody(CLEAR, raw, data, authority=assigned, at=AT)


def test_valid_pin_for_other_case_cannot_replace_assignment():
    case, data = windows()
    original_case = case["case_id"]
    case["case_id"] = "different-case"
    raw, _, approvals = seal_fixture(case)
    assigned = issue(raw, approvals)
    assert legacy(raw, data, approvals)["batch_state"] == "all_eligible"
    assert checked(raw, data, assigned)["batch_state"] == "all_eligible"
    tampered_assignment = replace(assigned, assigned_case_id=original_case)
    assert checked(raw, data, tampered_assignment)["error"] == "custody_case_mismatch"


def test_malformed_snapshot_is_invalid_before_review():
    _, data, _, _, assigned = adverse_successor()
    assert checked(b'{"case_id":', data, assigned)["error"] == "custody_invalid_snapshot"
