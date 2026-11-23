"""Validate pinned, case-scoped evidence snapshots for the offline guard."""
from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from eval.attack_evidence_v2 import parse
from eval.attack_windows_event_normalizer_v1 import normalize_observation, parse_xml, resolve_xml, utc_ns

VERSION = "kayan.offline-evidence/1"
Key = Annotated[str, Field(min_length=1, max_length=128)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Revision = Annotated[int, Field(ge=1)]


class Row(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class Ref(Row):
    id: Key
    revision: Revision


class Versioned(Ref):
    supersedes: Revision | None = None


class Source(Row):
    id: Key
    alias: Key
    collector: Key
    family: Key
    upstream: list[Key] = Field(default_factory=list)
    attestation_ref: Key


class Observation(Versioned):
    source: Key
    native_ref: Key
    media_type: Literal["application/xml", "text/plain"]
    sha256: Digest
    byte_length: Annotated[int, Field(gt=0, le=65536)]
    collected_at: str


class XmlStep(Row):
    namespace: str
    name: Key
    data_name: str | None = None


class Statement(Row):
    id: Key
    cite: Annotated[str, Field(pattern=r"^E[1-9][0-9]*\.[1-9][0-9]*$")]
    record: Ref
    sha256: Digest
    span: list[int] | None = None
    xml_path: list[XmlStep] | None = None
    attribute: Key | None = None


class Time(Row):
    source_time: str
    basis: Literal["UTC"]
    precision_ns: Annotated[int, Field(gt=0)]
    clock_error_ns: Annotated[int, Field(ge=0)] | None = None
    bounds_provenance: Key | None = None

    def interval(self):
        start, precision = utc_ns(self.source_time)
        if precision != self.precision_ns:
            raise ValueError("timestamp precision mismatch")
        if self.clock_error_ns is None or self.bounds_provenance is None:
            return None
        return start - self.clock_error_ns, start + precision + self.clock_error_ns


class Incident(Versioned):
    tenant: Key
    asset: Key
    authority: Key | None = None
    principal: Key | None = None
    session: Key | None = None
    session_generation: Key | None = None
    time: Time | None = None
    unresolved: dict[str, Key] = Field(default_factory=dict)


class Scope(Row):
    tenant: Key
    asset: Key
    authority: Key
    principal: Key
    session: Key
    session_generation: Key


class Authorization(Row):
    action: Key
    start: str
    end: str


ROLES = {
    "mechanic": None, "outcome": {"completed", "failed", "unresolved"},
    "actor": {"adversary", "benign", "unresolved"},
    "authorization": {"authorized", "unauthorized", "unresolved"},
    "process_session": None, "veto": {"contradiction", "retracted", "superseded", "unresolved"},
}


class Assertion(Versioned):
    event: Ref
    role: Key
    value: Key
    state: Literal["asserted", "withdrawn"]
    scope: Scope | None = None
    process: Key | None = None
    authorization: Authorization | None = None
    statements: Annotated[list[Key], Field(min_length=1)]
    receipt: Ref


class Receipt(Versioned):
    reviewer: Key
    decision: Literal["approved", "revoked"]
    reviewed_at: str
    expires_at: str
    rationale: Key
    snapshot_sha256: Digest
    assertion_sha256: Digest


class Snapshot(Row):
    schema_version: Literal["kayan.offline-evidence/1"]
    case_id: Key
    sources: list[Source]
    records: list[Observation]
    statements: list[Statement]
    events: list[Incident]
    assertions: list[Assertion]
    receipts: list[Receipt]


class UnverifiedSuggestion(Row):
    id: Key
    case_id: Key
    producer: Key
    value: Key
    statement_ids: list[Key]
    status: Literal["unverified"]


def parse_suggestions(raw):
    """Read a separate suggestion collection for inspection only."""
    return tuple(_index(UnverifiedSuggestion.model_validate(row) for row in parse(raw)).values())


@dataclass(frozen=True)
class VerifiedCase:
    snapshot: Snapshot
    active: tuple[Assertion, ...]
    trace: dict
    normalized: dict


def bytes_digest(raw):
    return sha256(raw).hexdigest()


def digest(value):
    return bytes_digest(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                   ensure_ascii=True, allow_nan=False).encode("ascii"))


def evidence_digest(snapshot):
    return digest({key: val for key, val in snapshot.items() if key not in {"assertions", "receipts"}})


def assertion_digest(assertion):
    return digest(assertion.model_dump(mode="json", exclude={"receipt"}))


def _index(rows):
    by_id = {}
    for row in rows:
        if row.id in by_id:
            raise ValueError("duplicate identifier")
        by_id[row.id] = row
    return by_id


def _history(rows):
    by_id = defaultdict(dict)
    for row in rows:
        revisions = by_id[row.id]
        if row.revision in revisions:
            raise ValueError("duplicate revision")
        revisions[row.revision] = row
    history, heads = {}, {}
    for key, revisions in by_id.items():
        for number, row in sorted(revisions.items()):
            previous = number - 1 or None
            if row.supersedes != previous or (previous is not None and previous not in revisions):
                raise ValueError("inconsistent revision history")
            history[key, number] = row
        heads[key] = max(revisions)
    return history, heads


def _origins(sources, *, source_is_attested=None, allow_missing_parents=False):
    collectors, aliases, ancestry = {}, {}, defaultdict(set)
    unverified = set()
    for source in sources.values():
        if collectors.setdefault(source.collector, source.family) != source.family:
            raise ValueError("inconsistent collector lineage")
        if aliases.setdefault(source.alias.casefold(), source.collector) != source.collector:
            raise ValueError("ambiguous collector alias")
        if any(parent not in sources for parent in source.upstream):
            if not allow_missing_parents:
                raise ValueError("invalid upstream lineage")
            unverified.add(source.collector)
        ancestry[source.collector].add(frozenset(
            sources[parent].collector for parent in source.upstream if parent in sources
        ))
        if source_is_attested is not None and not source_is_attested(source):
            unverified.add(source.collector)

    # Keep all declared edges for cycle checks. An inconsistent description
    # makes this collector and its descendants unusable as independent proof.
    parents = {collector: frozenset().union(*variants) for collector, variants in ancestry.items()}
    resolved = {}

    def resolve(key, visiting):
        if key in visiting:
            raise ValueError("invalid upstream lineage")
        if key not in resolved:
            families = {collectors[key]}
            consistent = len(ancestry[key]) == 1 and key not in unverified
            for upstream in parents[key]:
                upstream_families, upstream_consistent = resolve(upstream, visiting | {key})
                families.update(upstream_families)
                consistent &= upstream_consistent
            resolved[key] = frozenset(families), consistent
        return resolved[key]

    return {key: resolve(source.collector, set()) for key, source in sources.items()}


def _statement_value(statement, record, raw, roots):
    if statement.sha256 != record.sha256:
        raise ValueError("statement digest mismatch")
    if record.media_type == "text/plain":
        if statement.xml_path is not None or statement.attribute is not None or statement.span is None:
            raise ValueError("invalid text locator")
        if len(statement.span) != 2:
            raise ValueError("invalid text span")
        start, end = statement.span
        if not 0 <= start < end <= len(raw):
            raise ValueError("invalid text span")
        return raw[start:end].decode("utf-8")
    if not statement.xml_path or statement.span is not None:
        raise ValueError("invalid XML locator")
    if record.sha256 not in roots:
        roots[record.sha256] = parse_xml(raw)
    path = [(s.namespace, s.name, s.data_name) for s in statement.xml_path]
    return resolve_xml(roots[record.sha256], path, statement.attribute)


def _ref(ref):
    return ref.id, ref.revision


def verify(raw_manifest, payloads, *, expected_sha256, approved_receipts, at):
    """Verify against caller-pinned manifest and separate enrolled reviewer receipt digests.

    payloads maps (record ID, revision) to exact bytes. approved_receipts is
    a caller-controlled mapping from enrolled identity to approved receipt
    digests. No ancestry or review authority is taken from model suggestions.
    """
    return _verify(raw_manifest, payloads, expected_sha256=expected_sha256,
                   approved_receipts=approved_receipts, at=at)


def _verify(raw_manifest, payloads, *, expected_sha256, approved_receipts, at,
            snapshot_type=Snapshot, source_is_attested=None):
    if bytes_digest(raw_manifest) != expected_sha256:
        raise ValueError("snapshot digest mismatch")
    raw = parse(raw_manifest)
    snapshot = snapshot_type.model_validate(raw)
    evidence_sha = evidence_digest(raw)
    now = utc_ns(at)[0]
    sources = _index(snapshot.sources)
    origins = _origins(sources, source_is_attested=source_is_attested)
    records, record_heads = _history(snapshot.records)
    events, event_heads = _history(snapshot.events)
    assertions, assertion_heads = _history(snapshot.assertions)
    receipts, receipt_heads = _history(snapshot.receipts)
    statements = _index(snapshot.statements)
    if len({s.cite for s in statements.values()}) != len(statements):
        raise ValueError("duplicate citation address")
    if set(payloads) != set(records):
        raise ValueError("missing or unexpected observation bytes")
    normalized = {}
    for key, record in records.items():
        body = payloads[key]
        if record.source not in sources or len(body) != record.byte_length or bytes_digest(body) != record.sha256:
            raise ValueError("record provenance or bytes mismatch")
        utc_ns(record.collected_at)
        if record.media_type == "application/xml":
            normalized[key] = normalize_observation(body)
        if record.supersedes is not None:
            prior = records[record.id, record.supersedes]
            if (prior.source, prior.native_ref, prior.media_type) != (record.source, record.native_ref, record.media_type):
                raise ValueError("record revision changes source identity")
    for event in events.values():
        if event.time is not None:
            event.time.interval()
    roots, trace = {}, {}
    for statement in statements.values():
        key = _ref(statement.record)
        if key not in records:
            raise ValueError("unknown statement record")
        record = records[key]
        trace[statement.id] = {
            "statement": statement.model_dump(mode="json"),
            "observation": record.model_dump(mode="json"),
            "source": sources[record.source].model_dump(mode="json"),
            "origin_families": sorted(origins[record.source][0]),
            "lineage_resolved": origins[record.source][1],
            "exact_value": _statement_value(statement, record, payloads[key], roots),
        }

    active = []
    for (aid, revision), assertion in assertions.items():
        if (_ref(assertion.event) not in events or _ref(assertion.receipt) not in receipts
                or len(set(assertion.statements)) != len(assertion.statements)
                or any(sid not in trace for sid in assertion.statements)):
            raise ValueError("unresolved assertion reference")
        allowed = ROLES.get(assertion.role)
        if assertion.role not in ROLES or (allowed is not None and assertion.value not in allowed):
            raise ValueError("invalid assertion role or value")
        if assertion.role == "authorization":
            auth = assertion.authorization
            if auth is None or utc_ns(auth.start)[0] >= utc_ns(auth.end)[0]:
                raise ValueError("invalid authorization interval")
        elif assertion.authorization is not None:
            raise ValueError("authorization scope on incompatible role")
        if assertion.role == "process_session" and assertion.process is None:
            raise ValueError("missing process identifier")
        if assertion.supersedes is not None:
            prior = assertions[aid, assertion.supersedes]
            if prior.event.id != assertion.event.id or prior.role != assertion.role:
                raise ValueError("assertion revision retargets event or role")
        if assertion_heads[aid] == revision:
            active.append(assertion)

    for assertion in active:
        receipt = receipts[_ref(assertion.receipt)]
        receipt_digest = digest(receipt.model_dump(mode="json"))
        if (receipt_heads[receipt.id] != receipt.revision or receipt.decision != "approved"
                or receipt_digest not in approved_receipts.get(receipt.reviewer, ())
                or not utc_ns(receipt.reviewed_at)[0] <= now < utc_ns(receipt.expires_at)[0]
                or receipt.snapshot_sha256 != evidence_sha
                or receipt.assertion_sha256 != assertion_digest(assertion)):
            raise ValueError("untrusted, expired or stale review receipt")
        if (event_heads[assertion.event.id] != assertion.event.revision
                or any(record_heads[statements[sid].record.id] != statements[sid].record.revision
                       for sid in assertion.statements)):
            raise ValueError("active assertion references superseded evidence")
    return VerifiedCase(snapshot, tuple(active), trace, normalized)
