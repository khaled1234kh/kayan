"""Synthetic admission fixture issuer. Supplies no operational attestations."""
from copy import deepcopy

from eval.attack_evidence_admission_v2 import (
    AdmissionAuthority, AdmissionSnapshot, VERSION, issue_source_attestations,
)
from eval.attack_evidence_custody_v1 import CustodyHead, active_roster, revision_history
from eval.fixtures.ai.attack_fact_registry_v1.demo import AT, seal_fixture, slate


def case_fixture():
    case, payloads = slate()
    case["schema_version"] = VERSION
    for source in case["sources"]:
        source["upstream"] = []
    return case, payloads


def issue(case, *, attestations=None, previous=None, external_sources=None):
    raw, pin, approvals = seal_fixture(deepcopy(case))
    snapshot = AdmissionSnapshot.model_validate_json(raw)
    head = CustodyHead(
        case_id=snapshot.case_id, sequence=previous.sequence + 1 if previous else 1,
        snapshot_sha256=pin, previous_snapshot_sha256=previous.snapshot_sha256 if previous else None,
        assertion_roster=active_roster(snapshot.assertions),
        assertion_history=revision_history(snapshot.assertions),
        receipt_history=revision_history(snapshot.receipts),
    )
    if attestations is None:
        catalogue = case["sources"] if external_sources is None else external_sources
        attestations = issue_source_attestations(catalogue, head=head)
    authority = AdmissionAuthority(
        head.case_id, head, previous, {key: frozenset(rows) for key, rows in approvals.items()},
        AT, attestations,
    )
    return raw, authority
