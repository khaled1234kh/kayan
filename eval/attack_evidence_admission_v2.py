"""Offline admission for independently reviewed evidence under a v2 custody pin."""
from dataclasses import dataclass
from functools import partial
from typing import Literal

from eval.attack_evidence_custody_v1 import CustodyAuthority, _evaluate_in_custody
from eval.attack_fact_guard_adapter_v1 import SCOPE_FIELDS, _evaluate
from eval.attack_fact_registry_v1 import Snapshot, Source, _index, _origins, _verify, digest

VERSION = "kayan.offline-evidence/2"
SOURCE_ATTESTATION_VERSION = "kayan.source-attestation/2"
UNCERTAINTY_FIELDS = frozenset((*SCOPE_FIELDS, "time"))
PROCESS_LINK_VALUES = frozenset(("linked", "unlinked", "unresolved"))


class AdmissionSnapshot(Snapshot):
    schema_version: Literal["kayan.offline-evidence/2"]


@dataclass(frozen=True)
class AdmissionAuthority(CustodyAuthority):
    """Caller-controlled digests of exact independently attested source rows."""

    attested_sources: frozenset[str]


def _declares_ancestry(source):
    return "upstream" in source.model_fields_set


def _source_commitment(source, head):
    if not _declares_ancestry(source):
        raise ValueError("source attestation requires explicit ancestry")
    return digest({
        "version": SOURCE_ATTESTATION_VERSION,
        "case_id": head.case_id,
        "snapshot_sha256": head.snapshot_sha256,
        "sequence": head.sequence,
        "previous_snapshot_sha256": head.previous_snapshot_sha256,
        "source": source.model_dump(mode="json"),
    })


def issue_source_attestations(external_sources, *, head):
    """Compute commitments from the independently reviewed catalogue for this head."""
    sources = _index(Source.model_validate(row) for row in external_sources)
    origins = _origins(sources, source_is_attested=_declares_ancestry, allow_missing_parents=True)
    return frozenset(
        _source_commitment(source, head)
        for source_id, source in sources.items()
        if origins[source_id][1]
    )


def _verify_admission(raw_manifest, payloads, *, authority, **verification):
    def source_is_attested(source):
        return (_declares_ancestry(source)
                and _source_commitment(source, authority.current) in authority.attested_sources)

    case = _verify(raw_manifest, payloads, snapshot_type=AdmissionSnapshot,
                   source_is_attested=source_is_attested, **verification)
    for event in case.snapshot.events:
        unknown = sorted(event.unresolved.keys() - UNCERTAINTY_FIELDS)
        if unknown:
            raise ValueError(f"unsupported uncertainty fields for {event.id!r}: {unknown!r}")
    for assertion in case.snapshot.assertions:
        if assertion.role == "process_session" and assertion.value not in PROCESS_LINK_VALUES:
            raise ValueError(f"unsupported process/session value for {assertion.id!r}: {assertion.value!r}")
    return case


def evaluate_in_custody(raw_proposal, raw_manifest, payloads, *, authority: AdmissionAuthority):
    """Evaluate v2 bytes with a separately delivered current custody authority."""
    if not isinstance(authority, AdmissionAuthority) or not isinstance(authority.attested_sources, frozenset):
        raise TypeError("v2 admission requires an external source-attestation set")
    evaluator = partial(
        _evaluate, verifier=partial(_verify_admission, authority=authority),
        strict_links=True,
    )
    return _evaluate_in_custody(raw_proposal, raw_manifest, payloads, authority=authority,
                                snapshot_type=AdmissionSnapshot, pin_first=True, evaluator=evaluator)
