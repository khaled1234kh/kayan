from copy import deepcopy
import json

import pytest

from eval import attack_fact_guard_adapter_v1 as adapter
from eval.attack_fact_registry_v1 import bytes_digest
from eval.fixtures.ai.attack_fact_registry_v1.demo import AT, proposal, seal_fixture, slate, windows

CLEAR = proposal(**{"T1685.005": ("E1.1", "E2.1", "E3.1")})
SLATE = proposal(**{"T1486": ("E1.1", "E2.1"), "T1490": ("E1.1", "E3.1", "E4.1")})


def evaluate(case, data, raw_proposal=CLEAR):
    manifest, pin, approvals = seal_fixture(case)
    return adapter.evaluate(raw_proposal, manifest, data, expected_sha256=pin,
                            approved_receipts=approvals, at=AT)


def test_reviewed_windows_verdict_and_reverse_provenance():
    out = evaluate(*windows())
    assert out["batch_state"] == "all_eligible"
    item, = out["review_items"]
    assert item == out["claims"][0]
    mechanic = next(p for p in item["provenance"]["E1.1"] if p["assertion"]["role"] == "mechanic")
    assert [s["exact_value"] for s in mechanic["source_statements"]] == ["1102", "0x0055CD1D"]
    assert mechanic["review_receipt"]["reviewer"] == "synthetic-reviewer"
    assert mechanic["reviewed_event"]["session_generation"] == "boot-fixture-1"


@pytest.mark.parametrize(("role", "replacement", "reason"), [
    ("authorization", "authorized", "conflicting_or_superseded_evidence"),
    ("authorization", "unresolved", "authorization_unverified"),
    ("outcome", "failed", "completion_unverified"),
    ("outcome", "unresolved", "completion_unverified"),
    ("actor", "unresolved", "independent_attribution_missing"),
])
def test_negative_assertions_withhold(role, replacement, reason):
    case, data = windows()
    next(a for a in case["assertions"] if a["role"] == role)["value"] = replacement
    out = evaluate(case, data)
    assert out["batch_state"] == "none_eligible"
    assert out["review_items"] == []
    assert reason in out["claims"][0]["reasons"]


@pytest.mark.parametrize("mutation", [
    lambda c: c["assertions"][-1]["authorization"].update(start="2026-11-20T09:12:00Z"),
    lambda c: c["events"][0]["time"].update(clock_error_ns=None),
    lambda c: c["events"][0]["time"].update(clock_error_ns=400*10**9),
    lambda c: c["events"][0].update(session_generation=None, unresolved={"session_generation": "missing"}),
    lambda c: c["assertions"][-1]["scope"].update(principal="same-display-name-different-id"),
])
def test_incompatible_or_unknown_authority_never_defaults_to_unauthorized(mutation):
    case, data = windows()
    case = deepcopy(case)
    mutation(case)
    assert evaluate(case, data)["batch_state"] == "none_eligible"


def test_clear_without_reviewed_actors_and_authority_never_eligible():
    case, data = windows()
    case["assertions"] = []
    assert evaluate(case, data)["batch_state"] == "none_eligible"


def test_unsupported_xml_retained_but_cannot_anchor_review():
    case, data = windows()
    record = case["records"][0]
    raw = data["clear", 1].replace(b"<Version>0", b"<Version>7")
    record.update(sha256=bytes_digest(raw), byte_length=len(raw))
    data["clear", 1] = raw
    case["statements"][0]["sha256"] = record["sha256"]
    assert evaluate(case, data)["batch_state"] == "none_eligible"


@pytest.mark.parametrize("lineage", [
    {"collector": "audit-origin", "family": "audit-origin"},
    {"upstream": ["audit-origin"]},
])
def test_same_origin_through_alias_or_relay_is_not_independent(lineage):
    case, data = windows()
    case["sources"][1].update(lineage)
    out = evaluate(case, data)
    assert out["batch_state"] == "none_eligible"
    assert "independent_attribution_missing" in out["claims"][0]["reasons"]


def test_active_withdrawal_supersedes_older_positive_review():
    case, data = windows()
    actor = case["assertions"][2]
    case["assertions"].append({**actor, "revision": 2, "supersedes": 1, "state": "withdrawn",
                               "receipt": {"id": "withdrawal", "revision": 1}})
    out = evaluate(case, data)
    assert out["batch_state"] == "none_eligible"
    assert "conflicting_or_superseded_evidence" in out["claims"][0]["reasons"]


def test_uncited_contradiction_withholds_only_its_event():
    case, data = slate()
    recovery_actor = next(a for a in case["assertions"] if a["id"] == "snapshot-purge-Z-actor")
    adverse = deepcopy(recovery_actor)
    adverse.update(id="adverse", receipt={"id": "adverse", "revision": 1},
                   role="veto", value="contradiction", statements=["E4.1"])
    # Omit the veto address entirely by putting it on a new record/citation.
    record = next(r for r in case["records"] if r["id"] == "E4.1")
    case["records"].append({**record, "id": "extra"})
    data["extra", 1] = data["E4.1", 1]
    statement = next(s for s in case["statements"] if s["id"] == "E4.1")
    case["statements"].append({**statement, "id": "extra", "cite": "E9.1",
                               "record": {"id": "extra", "revision": 1}})
    adverse["statements"] = ["extra"]
    case["assertions"].append(adverse)
    out = evaluate(case, data, SLATE)
    assert out["batch_state"] == "mixed"
    assert [r["technique"] for r in out["review_items"]] == ["T1486"]
    assert out["claims"][1]["reasons"] == ["conflicting_or_superseded_evidence"]


@pytest.mark.parametrize(("removed", "state"), [(False, "all_eligible"), (True, "mixed")])
def test_shared_statement_has_distinct_event_associations(removed, state):
    case, data = slate(withhold=removed)
    out = evaluate(case, data, SLATE)
    assert out["batch_state"] == state
    assert len(out["claims"]) == 2
    assert len(out["review_items"]) == (1 if removed else 2)
    if removed:
        assert out["claims"][1]["disposition"] == "withheld"
    else:
        refs = [item["provenance"]["E1.1"][0] for item in out["review_items"]]
        assert [x["assertion"]["event"]["id"] for x in refs] == ["archive-encryption", "snapshot-purge-Z"]
        assert refs[0]["source_statements"] == refs[1]["source_statements"]


@pytest.mark.parametrize(("raw", "state"), [
    ('{"mappings":[]}', "abstained"),
    ('{broken', "invalid"),
    (proposal(**{"T1685.005": ("E1.1", "E1.1")}), "invalid"),
    (proposal(**{"T1685.005": ("E9.1",)}), "none_eligible"),
    ('{"mappings":[],"facts":[{"reviewed":true}]}', "invalid"),
])
def test_proposal_envelopes(raw, state):
    out = evaluate(*windows(), raw)
    assert out["batch_state"] == state
    assert out["review_items"] == []


@pytest.mark.parametrize("mode", ["missing", "duplicate", "both"])
def test_adapter_rejects_inconsistent_guard_partition(monkeypatch, mode):
    original = adapter.review

    def inconsistent(*args, **kwargs):
        result = original(*args, **kwargs)
        if mode == "missing":
            result["findings"].clear()
        elif mode == "duplicate":
            result["findings"].extend(result["findings"][:])
        else:
            result["rejected"]["T1685.005"] = ["contradiction"]
        return result

    monkeypatch.setattr(adapter, "review", inconsistent)
    assert evaluate(*windows())["batch_state"] == "invalid"


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("cite_conflict", [False, True])
def test_conflicting_reviewed_process_binding_reaches_v4(monkeypatch, reverse, cite_conflict):
    case, data = slate()
    action = next(a for a in case["assertions"] if a["id"] == "archive-encryption-mechanic")
    action["process"] = "P7"
    alternate = {**case["statements"][0], "id": "competing-link", "cite": "E8.1"}
    case["statements"].append(alternate)
    # Use E2.1 for the consistent link and a distinct address for the competing review.
    consistent = {**action, "id": "link-P7", "role": "process_session", "value": "linked",
                  "receipt": {"id": "link-P7", "revision": 1}}
    competing = {**consistent, "id": "competing-P7", "statements": [alternate["id"]],
                 "scope": {**consistent["scope"], "session": "0x99"},
                 "receipt": {"id": "competing-P7", "revision": 1}}
    case["assertions"].append(consistent)
    assert evaluate(case, data, SLATE)["batch_state"] == "all_eligible"
    case["assertions"].append(competing)
    if reverse:
        case["assertions"].reverse()
    captured = {}
    original = adapter.review

    def capture(*args, **kwargs):
        captured.update(original(*args, **kwargs))
        return captured

    monkeypatch.setattr(adapter, "review", capture)
    cites = ("E1.1", "E2.1", "E8.1") if cite_conflict else ("E1.1", "E2.1")
    out = evaluate(case, data, proposal(T1486=cites, T1490=("E1.1", "E3.1", "E4.1")))
    assert out["batch_state"] == "mixed"
    assert [item["technique"] for item in out["review_items"]] == ["T1490"]
    assert out["claims"][0]["reasons"] == captured["rejected"]["T1486"]
    assert "process_session_unverified" in out["claims"][0]["reasons"]

    for change in ({"asset": "other"}, {"session_generation": "other"}, {"tenant": "other"}):
        competing["scope"].update(change)
        assert evaluate(case, data, SLATE)["batch_state"] == "all_eligible"
        for field in change:
            competing["scope"][field] = consistent["scope"][field]
    competing["process"] = "P8"
    assert evaluate(case, data, SLATE)["batch_state"] == "all_eligible"
    competing["event"] = {"id": "snapshot-purge-Z", "revision": 1}
    competing["process"] = "P7"
    assert evaluate(case, data, SLATE)["batch_state"] == "all_eligible"


def test_windows_p7_conflict_from_independent_review():
    case, data = windows()
    mechanic = case["assertions"][0]
    mechanic["process"] = "P7"
    link = {**mechanic, "id": "link-P7", "role": "process_session", "value": "linked",
            "statements": ["logon"], "receipt": {"id": "link-P7", "revision": 1}}
    case["assertions"].append(link)
    proposed = proposal(**{"T1685.005": ("E1.1", "E1.2", "E2.1", "E3.1")})
    assert evaluate(case, data, proposed)["batch_state"] == "all_eligible"
    case["assertions"].append({**link, "id": "other-P7", "scope": {**link["scope"], "session": "0x99"},
                               "receipt": {"id": "other-P7", "revision": 1}})
    result = evaluate(case, data, proposed)
    assert result["batch_state"] == "none_eligible"
    assert result["claims"][0]["reasons"] == ["process_session_unverified"]


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("omit_parent", [False, True])
def test_alias_ancestry_cannot_manufacture_independence(reverse, omit_parent):
    case, data = windows()
    origin, custody = case["sources"][:2]
    relay = {**origin, "id": "relay", "alias": "relay", "collector": "relay", "family": "relay",
             "upstream": [origin["id"]]}
    custody["upstream"] = [relay["id"]]
    case["sources"].append(relay)
    assert evaluate(case, data)["batch_state"] == "none_eligible"
    alias = {**custody, "id": "custody-alias", "alias": "custody-alias",
             "upstream": [] if omit_parent else [relay["id"]]}
    case["sources"].append(alias)
    case["records"][2]["source"] = alias["id"]
    if reverse:
        case["sources"].reverse()
    out = evaluate(case, data)
    assert out["batch_state"] == "none_eligible"
    assert "independent_attribution_missing" in out["claims"][0]["reasons"]


def test_disputed_lineage_leaves_independent_sibling_eligible():
    case, data = slate()
    origin = next(source for source in case["sources"] if source["id"] == "backup-service")
    relay = {**origin, "id": "relay", "alias": "relay", "collector": "relay", "family": "relay",
             "upstream": [origin["id"]]}
    origin_alias = {**origin, "id": "backup-alias", "alias": "backup-alias", "upstream": [relay["id"]]}
    # The alias describes an additional independent upstream, with no cycle.
    relay["upstream"] = ["incident-response"]
    case["sources"].extend((relay, origin_alias))
    out = evaluate(case, data, SLATE)
    assert out["batch_state"] == "mixed"
    assert [item["technique"] for item in out["review_items"]] == ["T1486"]


@pytest.mark.parametrize("field", ["principal", "authority", "session", "session_generation", "time"])
@pytest.mark.parametrize("reverse", [False, True])
def test_explicit_dispute_takes_precedence_over_populated_candidate(field, reverse):
    case, data = windows()
    assert evaluate(case, data)["batch_state"] == "all_eligible"
    event = case["events"][0]
    event["unresolved"] = {field: "competing reviewed interpretations"}
    if reverse:
        case["events"][0] = dict(reversed(list(event.items())))
        case["assertions"].reverse()
    out = evaluate(case, data)
    assert out["batch_state"] == "none_eligible"
    assert out["review_items"] == []
    expected = "authorization_unverified" if field == "time" else "ambiguous_or_missing_action"
    assert expected in out["claims"][0]["reasons"]
