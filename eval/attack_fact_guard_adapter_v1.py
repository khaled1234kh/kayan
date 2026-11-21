"""Project reviewed assertions into v4 and expose per-claim dispositions."""
from collections import defaultdict
from json import JSONDecodeError

from eval.attack_evidence_guard_v3 import Event, Fact
from eval.attack_evidence_guard_v4 import review
from eval.attack_evidence_v2 import Response, parse
from eval.attack_fact_registry_v1 import verify
from eval.attack_windows_event_normalizer_v1 import utc_ns

SCOPE_FIELDS = ("tenant", "asset", "authority", "principal", "session", "session_generation")


def _invalid(reason):
    return {"batch_state": "invalid", "claims": [], "review_items": [], "error": reason}


def _applies(assertion, event, mechanic, *, strict_links=False):
    scope = {field: None if field in event.unresolved else getattr(event, field)
             for field in SCOPE_FIELDS}
    if assertion.scope is None:
        return "unknown"
    if any(value is None for value in scope.values()):
        return "unknown"
    if assertion.role == "process_session":
        if any(getattr(assertion.scope, field) != scope[field]
               for field in ("tenant", "asset", "session_generation")):
            return "different"
        if (assertion.scope.session == scope["session"]
                and (assertion.scope.principal != scope["principal"]
                     or assertion.scope.authority != scope["authority"])):
            return "unknown"
        if (strict_links and assertion.value == "unlinked"
                and assertion.scope.session != scope["session"]):
            if (assertion.scope.principal != scope["principal"]
                    or assertion.scope.authority != scope["authority"]):
                return "unknown"
            return "different"
    elif assertion.scope.model_dump() != scope:
        return "different"
    authorization = assertion.authorization
    if authorization is None:
        return "match"
    if mechanic is None:
        return "unknown"
    if authorization.action != mechanic:
        return "different"
    interval = event.time.interval() if event.time and "time" not in event.unresolved else None
    if interval is None:
        return "unknown"
    start, end = utc_ns(authorization.start)[0], utc_ns(authorization.end)[0]
    if interval[1] <= start or end <= interval[0]:
        return "different"
    return "match" if start <= interval[0] and interval[1] <= end else "unknown"


def _project(case, *, strict_links=False):
    events = {(e.id, e.revision): e for e in case.snapshot.events}
    receipts = {(r.id, r.revision): r for r in case.snapshot.receipts}
    by_event = defaultdict(list)
    for assertion in case.active:
        by_event[assertion.event.id, assertion.event.revision].append(assertion)

    def supported(assertion):
        for sid in assertion.statements:
            record = case.trace[sid]["observation"]
            normalized = case.normalized.get((record["id"], record["revision"]))
            if normalized is not None and normalized["state"] != "normalized":
                return False
        return True

    facts, reverse = [], defaultdict(list)
    for key, assertions in by_event.items():
        incident = events[key]
        event = Event(incident.tenant, incident.asset, incident.id)
        mechanics = [a for a in assertions if a.role == "mechanic" and a.state == "asserted"
                     and supported(a) and _applies(a, incident, None) == "match"]
        mechanic = mechanics[0].value if len(mechanics) == 1 else None
        action_support = [case.trace[s] for a in mechanics for s in a.statements]
        action_origins = {origin for item in action_support for origin in item["origin_families"]}
        action_digests = {item["observation"]["sha256"] for item in action_support}
        action_lineage_resolved = all(item["lineage_resolved"] for item in action_support)
        action_processes = {a.process for a in mechanics if a.process is not None}

        for assertion in assertions:
            if assertion.role == "process_session" and assertion.process not in action_processes:
                continue
            support = [case.trace[s] for s in assertion.statements]
            primary = support[0]
            source = primary["source"]["family"]
            cite = primary["statement"]["cite"]
            applicability = _applies(assertion, incident, mechanic, strict_links=strict_links)
            kind, value = assertion.role, assertion.value
            if not supported(assertion):
                applicability = "unknown"
            if assertion.state == "withdrawn" or kind == "veto":
                kind, value = "veto", "retracted" if assertion.state == "withdrawn" else value
            elif applicability == "different":
                continue
            elif applicability == "unknown":
                adverse = ((kind == "authorization" and value != "unauthorized")
                           or (kind == "actor" and value != "adversary")
                           or (kind == "outcome" and value != "completed")
                           or kind == "process_session")
                if not adverse:
                    continue
                kind, value = "veto", "unresolved"
            elif strict_links and kind == "process_session" and value != "linked":
                kind, value = "veto", "contradiction" if value == "unlinked" else "unresolved"
            elif kind == "actor" and value == "adversary":
                overlaps = any(
                    not item["lineage_resolved"]
                    or action_origins.intersection(item["origin_families"])
                    or item["observation"]["sha256"] in action_digests
                    for item in support
                )
                if overlaps or not action_lineage_resolved:
                    continue
            session = assertion.scope.session if kind == "process_session" else (incident.session or "")
            fact = Fact(cite, source, event, kind, value, session, assertion.process or "")
            facts.append(fact)
            receipt = receipts[assertion.receipt.id, assertion.receipt.revision]
            reverse[event, cite].append({
                "reviewed_event": incident.model_dump(mode="json"),
                "assertion": assertion.model_dump(mode="json"),
                "review_receipt": receipt.model_dump(mode="json"),
                "source_statements": support,
            })
    return tuple(facts), reverse


def _claims(raw_proposal):
    proposal = Response.model_validate(parse(raw_proposal))
    by_technique = defaultdict(set)
    for row in proposal.mappings:
        if row.cite in by_technique[row.technique]:
            raise ValueError("duplicate citation")
        by_technique[row.technique].add(row.cite)
    return by_technique


def _result(result, requested, reverse, case_id):
    if result["status"] in {"invalid_proposal", "invalid_reviewed_case"}:
        return _invalid(result["status"])
    eligible = {}
    for finding in result["findings"]:
        technique = finding["technique"]
        if (technique in eligible or technique not in requested or finding["case_id"] != case_id
                or len(finding["citations"]) != len(requested[technique])
                or set(finding["citations"]) != requested[technique]):
            return _invalid("inconsistent guard result")
        try:
            event = Event(**finding["event"])
            provenance = {cite: reverse[event, cite] for cite in finding["citations"]}
        except (TypeError, ValueError, KeyError):
            return _invalid("missing guard provenance")
        if not all(provenance.values()):
            return _invalid("missing guard provenance")
        eligible[technique] = {
            **finding, "disposition": "eligible_for_analyst_review", "provenance": provenance,
        }
    rejected = result["rejected"]
    if eligible.keys() & rejected.keys() or (eligible.keys() | rejected.keys()) != requested.keys():
        return _invalid("inconsistent guard result")
    claims = [
        eligible[tid] if tid in eligible else
        {"technique": tid, "disposition": "withheld", "reasons": rejected[tid]}
        for tid in requested
    ]
    if not claims:
        state = "abstained"
    elif not eligible:
        state = "none_eligible"
    elif rejected:
        state = "mixed"
    else:
        state = "all_eligible"
    return {"batch_state": state, "claims": claims, "review_items": list(eligible.values())}


def evaluate(raw_proposal, raw_manifest, payloads, *, expected_sha256, approved_receipts, at):
    """Verify the supplied snapshot first, then review one flat proposal offline."""
    return _evaluate(raw_proposal, raw_manifest, payloads, expected_sha256=expected_sha256,
                     approved_receipts=approved_receipts, at=at)


def _evaluate(raw_proposal, raw_manifest, payloads, *, expected_sha256, approved_receipts, at,
              verifier=verify, strict_links=False):
    try:
        requested = _claims(raw_proposal)
    except (TypeError, ValueError, RecursionError):
        return _invalid("invalid_proposal")
    try:
        case = verifier(raw_manifest, payloads, expected_sha256=expected_sha256,
                        approved_receipts=approved_receipts, at=at)
    except (TypeError, ValueError, RecursionError) as exc:
        reason = "malformed registry JSON" if isinstance(exc, JSONDecodeError) else str(exc).splitlines()[0]
        return _invalid(reason)
    facts, reverse = _project(case, strict_links=strict_links)
    case_id = case.snapshot.case_id
    result = review(raw_proposal, case_id=case_id, reviewed_cases={case_id: facts})
    return _result(result, requested, reverse, case_id)
