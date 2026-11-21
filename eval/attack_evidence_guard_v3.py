"""Offline evidence checks over analyst-reviewed normalized facts and v2-shaped proposals."""
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from eval.attack_evidence_v2 import Response, parse

# Enterprise 20.1. Names describe normalized observations, never execution instructions.
MECHANICS = {
    "T1685.005": "windows_event_log_clear",
    "T1098.003": "cloud_role_grant",
    "T1114.003": "mail_forwarding_rule",
    "T1113": "desktop_capture",
    "T1490": "recovery_inhibition",
    "T1486": "availability_impact_encryption",
}
Kind = Literal["mechanic", "outcome", "authorization", "actor", "process_session", "veto"]


@dataclass(frozen=True)
class Event:
    tenant: str
    asset: str
    occurrence: str  # Analyst-correlated event ID, unique across revisions and time windows.


@dataclass(frozen=True)
class Fact:
    cite: str
    source: str  # Independent upstream source, not a model-assigned record ID.
    event: Event
    kind: Kind
    value: str
    session: str = ""
    process: str = ""


def review(raw: str, reviewed_facts: tuple[Fact, ...]) -> dict:
    """Return offline analyst-review candidates. Fact provenance is the caller's trust boundary.

    Keep reviewed facts outside the proposal payload. A veto records an unresolved
    contradiction or a superseded event and applies even when it was omitted in the proposal.
    """
    try:
        proposal = Response.model_validate(parse(raw))
        pairs = [(x.technique, x.cite) for x in proposal.mappings]
        if len(pairs) != len(set(pairs)):
            raise ValueError("duplicate_citation")
    except (TypeError, ValueError, ValidationError):
        return {"status": "invalid_proposal", "findings": [], "rejected": {}}

    by_address = defaultdict(list)
    by_technique = defaultdict(set)
    for fact in reviewed_facts:
        by_address[fact.cite].append(fact)
    for tid, cite in pairs:
        by_technique[tid].add(cite)
    findings, rejected = [], {}
    for tid, addresses in by_technique.items():
        facts = [f for address in addresses for f in by_address[address]]
        causes = set()
        events = {f.event for f in facts}
        if tid not in MECHANICS or not any(f.kind == "mechanic" and f.value == MECHANICS[tid] for f in facts):
            causes.add("mechanic_or_objective_unverified")
        if len(events) != 1 or addresses - by_address.keys() or any(not f.source for f in facts):
            causes.add("source_or_event_mismatch")
        actions = [f for f in facts if f.kind == "mechanic"]
        if len(actions) != 1:
            causes.add("ambiguous_or_missing_action")
        else:
            action = actions[0]
            if not all((action.event.tenant, action.event.asset, action.event.occurrence)):
                causes.add("incomplete_event_identity")
            session = action.session
            if action.process:
                linked = {f.session for f in facts if f.kind == "process_session"
                          and f.process == action.process and f.session}
                all_links = {f.session for f in reviewed_facts if f.event == action.event
                             and f.kind == "process_session" and f.process == action.process}
                if len(linked) != 1 or all_links != linked or (session and session not in linked):
                    causes.add("process_session_unverified")
                else:
                    session = next(iter(linked))
            bound = [f for f in facts if f.session == session and session]
            if not any(f.kind == "outcome" and f.value == "completed" for f in bound):
                causes.add("completion_unverified")
            actors = [f for f in bound if f.kind == "actor" and f.value == "adversary"]
            if not any(f.source != action.source for f in actors):
                causes.add("independent_attribution_missing")
            if not any(f.kind == "authorization" and f.value == "unauthorized" for f in bound):
                causes.add("authorization_unverified")
            superseding = any(
                f.event == action.event and (
                    f.kind == "veto" or (
                        (not f.session or f.session == session) and
                        ((f.kind == "authorization" and f.value != "unauthorized") or
                         (f.kind == "actor" and f.value != "adversary") or
                         (f.kind == "outcome" and f.value != "completed"))
                    )
                ) for f in reviewed_facts
            )
            if superseding:
                causes.add("conflicting_or_superseded_evidence")
            usable = {action.cite, *(f.cite for f in bound if
                      (f.kind,f.value) in {("outcome","completed"),("actor","adversary"),
                                           ("authorization","unauthorized")} or
                      (f.kind=="process_session" and f.process and f.process==action.process))}
            if addresses - usable:
                causes.add("extraneous_citation")
        if causes:
            rejected[tid] = sorted(causes)
        else:
            findings.append({"technique":tid, "citations":sorted(addresses)})
    status = "eligible_for_analyst_review" if findings else ("withheld" if pairs else "abstained")
    return {"status":status, "findings":findings, "rejected":rejected}
