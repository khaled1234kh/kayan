import json
from dataclasses import asdict, replace

import pytest

from eval.attack_evidence_guard_v3 import Fact, review as review_v3
from eval.attack_evidence_guard_v4 import review
from eval.attack_experiment_d_guard_v3 import ANALYST_FACTS

ENCRYPTION = ANALYST_FACTS["slate_encryption"]
RECOVERY = ANALYST_FACTS["slate_recovery"]
SLATE_CITATIONS = {"T1486": ("E1.1", "E2.1"), "T1490": ("E1.1", "E3.1", "E4.1")}


def proposal(claims):
    return json.dumps({
        "mappings": [
            {"technique": technique, "cite": cite}
            for technique, citations in claims.items()
            for cite in citations
        ],
    })


def test_slate_shared_attribution_admits_both_findings():
    old = review_v3(proposal(SLATE_CITATIONS), ENCRYPTION + RECOVERY)
    assert old["status"] == "withheld"
    assert old["rejected"] == {
        technique: ["source_or_event_mismatch"] for technique in SLATE_CITATIONS
    }
    result = check(SLATE_CITATIONS, ENCRYPTION + RECOVERY)
    assert result["status"] == "eligible_for_analyst_review", result["rejected"]
    assert {f["technique"]: tuple(f["citations"]) for f in result["findings"]} == SLATE_CITATIONS
    assert [f["event"] for f in result["findings"]] == [
        asdict(ENCRYPTION[0].event), asdict(RECOVERY[0].event)
    ]
    assert all(f["case_id"] == "slate" for f in result["findings"])
    assert result["rejected"] == {}


def check(claims, facts):
    return review(proposal(claims), case_id="slate", reviewed_cases={"slate": facts})


@pytest.mark.parametrize("removed", ["T1486", "T1490"])
def test_removing_one_event_association_withholds_that_claim_only(removed):
    facts = ENCRYPTION + RECOVERY
    event = ENCRYPTION[0].event if removed == "T1486" else RECOVERY[0].event
    remaining = tuple(f for f in facts if not (f.event == event and f.cite == "E1.1"))
    out = check(SLATE_CITATIONS, remaining)
    assert {f["technique"] for f in out["findings"]} == set(SLATE_CITATIONS) - {removed}
    assert out["rejected"][removed] == [
        "authorization_unverified", "extraneous_citation",
        "independent_attribution_missing", "source_or_event_mismatch",
    ]


@pytest.mark.parametrize("pointers", [
    ("E1.1", "E2.1", "E3.1"),  # Other event's outcome.
    ("E1.1", "E2.1", "E9.1"),  # Unresolvable pointer.
    ("E1.1", "E2.1", "E8.1"),  # Address exists but has no proof role.
])
def test_wrong_only_unknown_and_irrelevant_citations_withhold(pointers):
    irrelevant = Fact("E8.1", "another-source", ENCRYPTION[0].event, "actor", "adversary", "B91")
    out = check({"T1486": pointers}, ENCRYPTION + RECOVERY + (irrelevant,))
    assert out["status"] == "withheld"
    assert "extraneous_citation" in out["rejected"]["T1486"]


def test_cites_cannot_combine_actions_and_outcomes_between_events():
    facts = tuple(f for f in ENCRYPTION if f.kind != "outcome") + RECOVERY
    out = check({"T1486": ("E1.1", "E2.1", "E3.1")}, facts)
    assert out["status"] == "withheld"
    assert "completion_unverified" in out["rejected"]["T1486"]


def test_competing_action_anchors_do_not_choose_first_match():
    competing = replace(ENCRYPTION[0], event=RECOVERY[0].event)
    out = check(SLATE_CITATIONS, ENCRYPTION + RECOVERY + (competing,))
    assert [f["technique"] for f in out["findings"]] == ["T1490"]
    assert out["rejected"] == {"T1486": ["ambiguous_or_missing_action"]}


@pytest.mark.parametrize("change", [
    {"source": ENCRYPTION[0].source},
    {"session": "B91"},
    {"value": "unresolved"},
    {"event": replace(ENCRYPTION[0].event, tenant="different")},
    {"event": replace(ENCRYPTION[0].event, asset="SE-3")},
    {"event": replace(ENCRYPTION[0].event, occurrence="separate-window")},
])
def test_attribution_must_be_independent_and_applicable(change):
    facts = tuple(replace(f, **change) if f.kind == "actor" else f for f in ENCRYPTION)
    out = check({"T1486": SLATE_CITATIONS["T1486"]}, facts)
    assert "independent_attribution_missing" in out["rejected"]["T1486"]


@pytest.mark.parametrize(("kind", "value"), [
    ("outcome", "failed"),
    ("outcome", "unconfirmed"),
    ("authorization", "authorized"),
    ("veto", "retracted"),
    ("veto", "contradiction"),
])
def test_uncited_applicable_adverse_evidence_is_event_scoped(kind, value):
    adverse = Fact("E9.1", "second-reviewer", ENCRYPTION[0].event, kind, value, "B19")
    out = check(SLATE_CITATIONS, ENCRYPTION + RECOVERY + (adverse,))
    assert [f["technique"] for f in out["findings"]] == ["T1490"]
    assert out["rejected"] == {"T1486": ["conflicting_or_superseded_evidence"]}


def test_process_session_link_still_required_and_uncited_conflict_blocks():
    action = replace(ENCRYPTION[0], session="", process="P7")
    facts = (action, *ENCRYPTION[1:])
    claims = {"T1486": SLATE_CITATIONS["T1486"]}
    lack_link = check(claims, facts)
    assert "process_session_unverified" in lack_link["rejected"]["T1486"]
    link = Fact("E5.1", "session-table", action.event, "process_session", "", "B19", "P7")
    claims = {"T1486": (*SLATE_CITATIONS["T1486"], link.cite)}
    assert check(claims, (*facts, link))["status"] == "eligible_for_analyst_review"
    conflict = replace(link, cite="E5.2", session="B91")
    for bank in ((*facts, replace(link, process="P8")), (*facts, link, conflict)):
        assert "process_session_unverified" in check(claims, bank)["rejected"]["T1486"]


@pytest.mark.parametrize("raw", [
    proposal({"T1486": ("E1.1", "E1.1")}),
    proposal({"T1486": ("E1",)}),
    '{"mappings":[{"technique":"T1486","cite":"E2.1","event":"archive-encryption"}]}',
    '{"mappings":[],"facts":[{"role":"actor","value":"adversary","citations":["E1.1"]}]}',
    "[" * 5000,
])
def test_invalid_proposal_and_untrusted_fields(raw):
    assert review(raw, case_id="slate", reviewed_cases={"slate": ENCRYPTION})["status"] == "invalid_proposal"


def test_review_channel_rejects_unverified_extraction_objects():
    raw = proposal({"T1486": SLATE_CITATIONS["T1486"]})
    extraction = {"role": "actor", "value": "adversary", "citations": ["E1.1"]}
    out = review(raw, case_id="slate", reviewed_cases={"slate": (*ENCRYPTION[:2], extraction)})
    assert out["status"] == "invalid_reviewed_case"


def test_cases_do_not_share_facts_with_identical_addresses_or_event_keys():
    raw = proposal({"T1486": SLATE_CITATIONS["T1486"]})
    cases = {"target": ENCRYPTION[:2], "other": ENCRYPTION}
    out = review(raw, case_id="target", reviewed_cases=cases)
    assert "independent_attribution_missing" in out["rejected"]["T1486"]
    assert review(raw, case_id="absent", reviewed_cases=cases)["status"] == "invalid_reviewed_case"
    assert review('{"mappings":[]}', case_id="target", reviewed_cases=cases)["status"] == "abstained"


def test_v4_requires_cited_matching_action():
    out = check({"T1486": ("E1.1",)}, ENCRYPTION)
    assert out["rejected"]["T1486"] == [
        "ambiguous_or_missing_action", "mechanic_or_objective_unverified",
    ]
    wrong_mechanic = (replace(ENCRYPTION[0], value="recovery_inhibition"), *ENCRYPTION[1:])
    assert check({"T1486": SLATE_CITATIONS["T1486"]}, wrong_mechanic)["status"] == "withheld"
