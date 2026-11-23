import json
from dataclasses import replace

import pytest

from eval.attack_evidence_guard_v3 import Event, Fact, review
from eval.attack_diagnostic_metrics_v3 import multi_record_candidates, summarise_scores
from eval.attack_evidence_v2 import score, summarise

EVENT = Event("north", "asset-1", "window-1/event-01")
ENC = "T1486"
CLEAR = "T1685.005"


def chain(event=EVENT, mechanic="availability_impact_encryption"):
    return (
        Fact("E1.1", "host-journal", event, "mechanic", mechanic, process="P7"),
        Fact("E2.1", "session-table", event, "process_session", "", "S9", "P7"),
        Fact("E3.1", "outcome-log", event, "outcome", "completed", "S9"),
        Fact("E4.1", "session-investigator", event, "actor", "adversary", "S9"),
        Fact("E4.2", "session-investigator", event, "authorization", "unauthorized", "S9"),
    )


def proposal(tid, facts):
    return json.dumps({"mappings":[{"technique":tid,"cite":f.cite} for f in facts]})


def test_support_and_valid_abstention():
    facts = chain()
    assert review(proposal(ENC, facts), facts)["status"] == "eligible_for_analyst_review"
    assert review('{"mappings":[]}', facts)["status"] == "abstained"
    assert review("broken", facts)["status"] == "invalid_proposal"


@pytest.mark.parametrize(("index", "reason"), [
    (1, "process_session_unverified"),
    (2, "completion_unverified"),
    (3, "independent_attribution_missing"),
    (4, "authorization_unverified"),
])
def test_partial_chain_withholds(index, reason):
    facts = chain()
    output = review(proposal(ENC, facts[:index] + facts[index+1:]), facts)
    assert output["findings"] == [] and reason in output["rejected"][ENC]


@pytest.mark.parametrize("change", [
    {"session":"other-session"}, {"process":"P8"},
    {"event":replace(EVENT, asset="other-host")},
    {"event":replace(EVENT, occurrence="different-window")},
    {"event":replace(EVENT, tenant="other-tenant")},
])
def test_wrong_process_session_host_or_time(change):
    facts = chain()
    supplied = (facts[0], replace(facts[1], **change), *facts[2:])
    assert review(proposal(ENC, supplied), supplied)["status"] == "withheld"


@pytest.mark.parametrize(("kind","value"), [
    ("outcome","failed"), ("authorization","authorized"), ("actor","unresolved"),
    ("veto","retracted"), ("veto","contradiction"),
])
def test_omitted_disconfirming_evidence_vetoes_release(kind, value):
    facts = chain()
    contrary = Fact("E5.1", "reviewer", EVENT, kind, value, "S9")
    assert review(proposal(ENC, facts), (*facts, contrary))["status"] == "withheld"


def test_uncited_conflicting_links_block_and_duplicate_pairs_are_invalid():
    facts = chain()
    conflict = Fact("E5.1", "alternate-session-table", EVENT, "process_session", "", "S8", "P7")
    assert review(proposal(ENC, facts), (*facts, conflict))["status"] == "withheld"
    assert review(proposal(ENC, (*facts, facts[0])), facts)["status"] == "invalid_proposal"


def test_wrong_objective_and_unrelated_reference():
    facts = chain(mechanic="encrypt_staged_payload")
    assert review(proposal(ENC, facts), facts)["status"] == "withheld"
    assert review(proposal("T1027.013", facts), facts)["status"] == "withheld"
    unrelated = Fact("E5.1", "other", replace(EVENT, asset="asset-2"), "actor", "adversary", "S9")
    facts = chain()
    assert review(proposal(ENC, (*facts, unrelated)), (*facts, unrelated))["status"] == "withheld"


def test_two_independent_techniques_and_extra_unsupported_claim():
    other = Event("north", "asset-2", "window-2/event-02")
    # Ten proposal pairs would exceed the v2 contract. Direct session binding and
    # collocated reviewed roles use three unique pointers in the second claim.
    facts = chain() + (
        Fact("E5.1", "journal", other, "mechanic", "windows_event_log_clear", "S10"),
        Fact("E5.2", "audit", other, "outcome", "completed", "S10"),
        Fact("E6.1", "identity", other, "actor", "adversary", "S10"),
        Fact("E6.1", "identity", other, "authorization", "unauthorized", "S10"),
    )
    good = json.loads(proposal(ENC,facts[:5]))["mappings"] + json.loads(proposal(CLEAR,facts[5:8]))["mappings"]
    out = review(json.dumps({"mappings":good}), facts)
    assert {f["technique"] for f in out["findings"]} == {ENC, CLEAR}
    first = good[:5]
    first.append({"technique":"T1027.013","cite":"E1.1"})
    out = review(json.dumps({"mappings":first}),facts)
    assert {f["technique"] for f in out["findings"]} == {ENC}
    assert "T1027.013" in out["rejected"]


def test_metadata_leak_reproduced_then_eliminated_from_summary():
    verdict = score({"E1":["Source"]},{"disposition":"benign","targets":{},"exceptions":{}},
                    '{"mappings":[]}',set())
    envelope = dict(verdict, **{"pass":2,"latency_ms":47})
    old = summarise([envelope])
    assert old["counts"]["pass"] == 2 and old["counts"]["latency_ms"] == 47
    assert summarise_scores([envelope]) == summarise([verdict])


def test_structural_screen_keeps_cross_record_claim_but_supplies_no_support():
    trace = [{"technique":ENC,"cite":r,"text":"untrusted source statement"} for r in ("E1.1","E1.2")]
    assert multi_record_candidates(trace) == []
    trace.append({"technique":ENC,"cite":"E2.1","text":None})
    assert multi_record_candidates(trace) == []
    trace[-1]["text"] = "unrelated but resolvable statement"
    assert multi_record_candidates(trace) == [ENC]
