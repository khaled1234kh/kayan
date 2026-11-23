"""Offline event-scoped review of flat ATT&CK proposals against reviewed facts."""
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import asdict

from eval.attack_evidence_guard_v3 import MECHANICS, Event, Fact
from eval.attack_evidence_guard_v3 import review as review_scoped
from eval.attack_evidence_v2 import Response, compact, parse


def review(
    raw: str, *, case_id: str, reviewed_cases: Mapping[str, tuple[Fact, ...]]
) -> dict:
    """Review proposals using a case selected by the trusted caller.

    Only independently reviewed inputs belong in reviewed_cases. Fact types
    distinguish the API channels but cannot attest their provenance. The flat
    proposal carries citations and technique IDs and cannot set case or event.
    """
    try:
        proposal = Response.model_validate(parse(raw))
        pairs = [(item.technique, item.cite) for item in proposal.mappings]
        if len(set(pairs)) != len(pairs):
            raise ValueError("duplicate_citation")
    except (TypeError, ValueError, RecursionError):
        return {"status": "invalid_proposal", "findings": [], "rejected": {}}

    reviewed = reviewed_cases.get(case_id)
    if not case_id or not isinstance(reviewed, tuple) or any(type(f) is not Fact for f in reviewed):
        return {"status": "invalid_reviewed_case", "findings": [], "rejected": {}}

    facts_by_event: dict[Event, list[Fact]] = defaultdict(list)
    actions_by_address: dict[str, list[Fact]] = defaultdict(list)
    for fact in reviewed:
        facts_by_event[fact.event].append(fact)
        if fact.kind == "mechanic":
            actions_by_address[fact.cite].append(fact)

    claims: dict[str, list[str]] = defaultdict(list)
    for technique, cite in pairs:
        claims[technique].append(cite)

    findings, rejected = [], {}
    for technique, addresses in claims.items():
        anchors = [
            fact
            for address in addresses
            for fact in actions_by_address[address]
            if technique in MECHANICS and fact.value == MECHANICS[technique]
        ]
        if len(anchors) != 1:
            rejected[technique] = (
                ["ambiguous_or_missing_action", "mechanic_or_objective_unverified"]
                if not anchors else ["ambiguous_or_missing_action"]
            )
            continue

        event = anchors[0].event
        event_facts = facts_by_event[event]
        # Pass every proposed address and the entire selected event. The v3
        # check resolves addresses inside that event and inspects uncited vetoes.
        scoped_proposal = compact({
            "mappings": [{"technique": technique, "cite": cite} for cite in addresses],
        })
        result = review_scoped(scoped_proposal, tuple(event_facts))
        reasons = set(result["rejected"].get(technique, ()))
        if set(addresses) - {fact.cite for fact in event_facts}:
            reasons.add("source_or_event_mismatch")
        if reasons:
            rejected[technique] = sorted(reasons)
        else:
            findings.append({**result["findings"][0], "case_id": case_id, "event": asdict(event)})

    status = "eligible_for_analyst_review" if findings else ("withheld" if claims else "abstained")
    return {"status": status, "findings": findings, "rejected": rejected}
