from copy import deepcopy
from dataclasses import replace
import json

import pytest

from eval import attack_evidence_custody_v1 as custody
from eval.attack_evidence_admission_v2 import evaluate_in_custody, issue_source_attestations
from eval.attack_fact_registry_v1 import bytes_digest
from eval.fixtures.ai.attack_admission_v2 import case_fixture, issue
from eval.fixtures.ai.attack_fact_registry_v1.demo import proposal, seal_fixture, slate

ENCRYPTION = ("E1.1", "E2.1")
RECOVERY = ("E1.1", "E3.1", "E4.1")
SLATE = proposal(T1486=ENCRYPTION, T1490=RECOVERY)


def assert_result(result, state, eligible, withheld=None):
    assert result["batch_state"] == state
    assert [item["technique"] for item in result["review_items"]] == eligible
    assert {row["technique"]: row["reasons"] for row in result["claims"]
            if row["disposition"] == "withheld"} == (withheld or {})


def check(case, data, raw_proposal=SLATE, **options):
    raw, authority = issue(case, **options)
    return evaluate_in_custody(raw_proposal, raw, data, authority=authority)


def add_process_link(case):
    action = next(row for row in case["assertions"] if row["id"] == "archive-encryption-mechanic")
    action["process"] = "P7"
    link = {**action, "id": "link", "role": "process_session", "value": "linked",
            "receipt": {"id": "link", "revision": 1}}
    case["assertions"].append(link)
    return link


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("cited", [False, True])
@pytest.mark.parametrize("adverse", ["unlinked", "unresolved", "other-session", "other-process"])
def test_reviewed_process_link_semantics(reverse, cited, adverse):
    case, data = case_fixture()
    link = add_process_link(case)
    assert_result(check(case, data), "all_eligible", ["T1486", "T1490"])
    statement = next(row for row in case["statements"] if row["id"] == "E2.1")
    case["statements"].append({**statement, "id": "competing", "cite": "E8.1"})
    competing = {**link, "id": "competing", "statements": ["competing"],
                 "receipt": {"id": "competing", "revision": 1}}
    if adverse == "other-session":
        competing["scope"] = {**link["scope"], "session": "other-session"}
    elif adverse == "other-process":
        competing.update(process="P8", value="unlinked")
    else:
        competing["value"] = adverse
    case["assertions"].append(competing)
    if reverse:
        case["assertions"].reverse()
    cites = (*ENCRYPTION, "E8.1") if cited else ENCRYPTION
    out = check(case, data, proposal(T1486=cites, T1490=RECOVERY))
    if adverse == "other-process" and not cited:
        assert_result(out, "all_eligible", ["T1486", "T1490"])
        return
    if adverse == "other-process":
        reasons = ["extraneous_citation", "source_or_event_mismatch"]
    elif adverse == "other-session":
        reasons = ["process_session_unverified"]
    else:
        reasons = ["conflicting_or_superseded_evidence"]
    if cited and adverse != "other-process":
        reasons = sorted([*reasons, "extraneous_citation"])
    assert_result(out, "mixed", ["T1490"], {"T1486": reasons})


@pytest.mark.parametrize("value", ["unlinked", "unresolved", "unspecified"])
def test_nonaffirmative_link_cannot_supply_proof(value):
    case, data = case_fixture()
    add_process_link(case)["value"] = value
    result = check(case, data)
    if value == "unspecified":
        assert_result(result, "invalid", [])
        assert result["error"] == "unsupported process/session value for 'link': 'unspecified'"
    else:
        assert_result(result, "mixed", ["T1490"], {
            "T1486": ["conflicting_or_superseded_evidence", "process_session_unverified"],
        })


@pytest.mark.parametrize("field", ["session_generation", "generation", "principal", "identity"])
@pytest.mark.parametrize("reverse", [False, True])
def test_uncertainty_requires_exact_fields(field, reverse):
    case, data = case_fixture()
    event = next(row for row in case["events"] if row["id"] == "archive-encryption")
    event["unresolved"] = {field: "two reviewed interpretations"}
    if reverse:
        case["events"].reverse()
        case["assertions"].reverse()
    raw, authority = issue(case)
    result = evaluate_in_custody(SLATE, raw, data, authority=authority)
    assert json.loads(raw)["events"][int(reverse)]["unresolved"] == event["unresolved"]
    if field in {"generation", "identity"}:
        assert_result(result, "invalid", [])
        assert result["error"] == f"unsupported uncertainty fields for 'archive-encryption': ['{field}']"
    else:
        assert_result(result, "mixed", ["T1490"], {
            "T1486": ["ambiguous_or_missing_action", "mechanic_or_objective_unverified"],
        })


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("variant", ["separate", "omitted", "unattested", "changed-attestation",
                                    "shared", "upstream", "independent-upstream", "unattested-upstream",
                                    "conflicting-alias", "incomplete-alias", "missing-parent"])
def test_ancestry_is_explicit_and_externally_attested(reverse, variant):
    case, data = case_fixture()
    sources = {source["id"]: source for source in case["sources"]}
    backup = sources["backup-service"]
    original_catalogue = deepcopy(case["sources"])
    options = {}
    if variant == "omitted":
        del backup["upstream"]
    elif variant == "unattested":
        options["external_sources"] = [row for row in case["sources"] if row is not backup]
    elif variant == "changed-attestation":
        backup["attestation_ref"] = "replacement-catalogue"
        options["external_sources"] = original_catalogue
    elif variant == "shared":
        backup["family"] = sources["incident-response"]["family"]
    elif variant == "upstream":
        backup["upstream"] = ["incident-response"]
    elif variant in {"independent-upstream", "unattested-upstream"}:
        backup["upstream"] = ["backup-inventory"]
        if variant == "unattested-upstream":
            options["external_sources"] = [
                row for row in case["sources"] if row["id"] != "backup-inventory"
            ]
    elif variant in {"conflicting-alias", "incomplete-alias"}:
        alias = {**backup, "id": "backup-alias", "alias": "backup-alias"}
        if variant == "incomplete-alias":
            del alias["upstream"]
        else:
            alias["upstream"] = ["incident-response"]
        case["sources"].append(alias)
    elif variant == "missing-parent":
        backup["upstream"] = ["unknown-collector"]
    if reverse:
        case["sources"].reverse()
    out = check(case, data, **options)
    if variant in {"separate", "independent-upstream"}:
        assert_result(out, "all_eligible", ["T1486", "T1490"])
    elif variant == "missing-parent":
        assert_result(out, "invalid", [])
        assert out["error"] == "invalid upstream lineage"
    else:
        assert_result(out, "mixed", ["T1486"], {"T1490": ["independent_attribution_missing"]})


def test_v2_requires_version_and_external_source_authority():
    current, data = case_fixture()
    _, authority = issue(current)
    historical, _ = slate()
    raw, pin, _ = seal_fixture(historical)
    wrong_version = replace(authority, current=replace(authority.current, snapshot_sha256=pin))
    out = evaluate_in_custody(SLATE, raw, data, authority=wrong_version)
    assert_result(out, "invalid", [])
    assert out["error"] == "custody_invalid_snapshot"
    assert_result(check(current, data, attestations=frozenset()), "none_eligible", [], {
        "T1486": ["independent_attribution_missing"],
        "T1490": ["independent_attribution_missing"],
    })


def test_v2_suggestions_cannot_enter_trusted_snapshot():
    case, data = case_fixture()
    raw, authority = issue(case)
    case = json.loads(raw)
    case["suggestions"] = [{"status": "unverified", "value": "linked"}]
    raw = json.dumps(case).encode()
    authority = replace(authority, current=replace(authority.current, snapshot_sha256=bytes_digest(raw)))
    out = evaluate_in_custody(SLATE, raw, data, authority=authority)
    assert_result(out, "invalid", [])
    assert out["error"] == "custody_invalid_snapshot"


def test_v2_mismatched_bytes_fail_before_parse(monkeypatch):
    case, data = case_fixture()
    raw, authority = issue(case)

    def unexpected_parse(_raw):
        pytest.fail("custody parsed a snapshot with mismatched bytes")

    monkeypatch.setattr(custody, "parse", unexpected_parse)
    out = evaluate_in_custody(SLATE, raw + b" ", data, authority=authority)
    assert_result(out, "invalid", [])
    assert out["error"] == "custody_snapshot_mismatch"


def test_v2_repinned_successor_still_requires_predecessor_history():
    case, data = case_fixture()
    original, authority = issue(case)
    successor = json.loads(original)
    raw, newer = issue(successor, previous=authority.current)
    # Reusing a previous manifest verbatim is a rollback even with a new sequence.
    assert raw == original
    out = evaluate_in_custody(SLATE, raw, data, authority=newer)
    assert_result(out, "invalid", [])
    assert out["error"] == "custody_rollback"
    raw += b" "
    newer = replace(newer, current=replace(newer.current, snapshot_sha256=bytes_digest(raw)))
    newer = replace(newer, attested_sources=issue_source_attestations(case["sources"], head=newer.current))
    assert_result(evaluate_in_custody(SLATE, raw, data, authority=newer),
                  "all_eligible", ["T1486", "T1490"])
    out = evaluate_in_custody(SLATE, original, data, authority=newer)
    assert_result(out, "invalid", [])
    assert out["error"] == "custody_rollback"
    case["assertions"].pop()
    out = check(case, data, previous=authority.current)
    assert_result(out, "invalid", [])
    assert out["error"] == "custody_history_rewrite"


def test_source_attestations_do_not_authorize_unapproved_process_review():
    case, data = case_fixture()
    add_process_link(case)
    raw, authority = issue(case)
    out = evaluate_in_custody(SLATE, raw, data, authority=replace(authority, approved_receipts={}))
    assert_result(out, "invalid", [])
    assert out["error"] == "untrusted, expired or stale review receipt"


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("side", ["neither", "external", "submitted", "shared", "external-conflict"])
def test_independent_catalogue_ancestry(reverse, side):
    case, data = case_fixture()
    external = deepcopy(case["sources"])
    submitted_backup = next(row for row in case["sources"] if row["id"] == "backup-service")
    external_backup = next(row for row in external if row["id"] == "backup-service")
    if side == "external":
        del external_backup["upstream"]
    elif side == "submitted":
        del submitted_backup["upstream"]
    elif side == "shared":
        submitted_backup["upstream"] = external_backup["upstream"] = ["incident-response"]
    elif side == "external-conflict":
        external.append({**external_backup, "id": "other-backup", "alias": "other-backup",
                         "upstream": ["incident-response"]})
    if reverse:
        external.reverse()
        case["sources"].reverse()
    out = check(case, data, external_sources=external)
    if side == "neither":
        assert_result(out, "all_eligible", ["T1486", "T1490"])
    else:
        assert_result(out, "mixed", ["T1486"], {"T1490": ["independent_attribution_missing"]})


@pytest.mark.parametrize("field", ["case_id", "snapshot_sha256", "sequence", "previous_snapshot_sha256"])
def test_attestation_commitment_cannot_be_reused_for_another_head(field):
    case, data = case_fixture()
    raw, authority = issue(case)
    other_value = authority.current.sequence + 1 if field == "sequence" else "a" * 64
    other_head = replace(authority.current, **{field: other_value})
    approvals = issue_source_attestations(case["sources"], head=other_head)
    assert not (approvals & authority.attested_sources)
    out = evaluate_in_custody(SLATE, raw, data, authority=replace(authority, attested_sources=approvals))
    assert_result(out, "none_eligible", [], {
        "T1486": ["independent_attribution_missing"], "T1490": ["independent_attribution_missing"],
    })


def test_issuer_refuses_malformed_external_ancestry():
    case, _ = case_fixture()
    _, authority = issue(case)
    case["sources"][0]["upstream"] = None
    with pytest.raises(ValueError, match="upstream"):
        issue_source_attestations(case["sources"], head=authority.current)


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("cited", [False, True])
@pytest.mark.parametrize("denied", ["same", "distinct", "unknown", "other-authority"])
def test_denial_is_scoped_to_process_and_session(reverse, cited, denied):
    case, data = case_fixture()
    link = add_process_link(case)
    assert_result(check(case, data), "all_eligible", ["T1486", "T1490"])
    statement = next(row for row in case["statements"] if row["id"] == "E2.1")
    case["statements"].append({**statement, "id": "denial", "cite": "E8.1"})
    denied_scope = dict(link["scope"])
    if denied != "same":
        denied_scope["session"] = "separate-session"
    if denied == "other-authority":
        denied_scope["authority"] = "separate-authority"
    denial = {**link, "id": "denial", "value": "unlinked", "statements": ["denial"],
              "scope": None if denied == "unknown" else denied_scope,
              "receipt": {"id": "denial", "revision": 1}}
    case["assertions"].append(denial)
    if reverse:
        case["assertions"].reverse()
    cites = (*ENCRYPTION, "E8.1") if cited else ENCRYPTION
    out = check(case, data, proposal(T1486=cites, T1490=RECOVERY))
    if denied == "distinct":
        if cited:
            assert_result(out, "mixed", ["T1490"], {
                "T1486": ["extraneous_citation", "source_or_event_mismatch"],
            })
        else:
            assert_result(out, "all_eligible", ["T1486", "T1490"])
        return
    reasons = ["conflicting_or_superseded_evidence"]
    if cited:
        reasons.append("extraneous_citation")
    assert_result(out, "mixed", ["T1490"], {"T1486": reasons})
