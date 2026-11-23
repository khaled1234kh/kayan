import json

import pytest

from eval.attack_fact_registry_v1 import bytes_digest, parse_suggestions, verify
from eval.fixtures.ai.attack_fact_registry_v1.demo import AT, HERE, seal_fixture, windows


def verify_win(case, data):
    raw, pin, approvals = seal_fixture(case)
    return verify(raw, data, expected_sha256=pin, approved_receipts=approvals, at=AT)


def test_pinned_windows_snapshot_trace_matches_exact_values_and_receipts():
    case, data = windows()
    pins = json.loads((HERE / "fixture-pins.json").read_bytes())["windows"]
    raw = (HERE / "windows-manifest.json").read_bytes()
    assert seal_fixture(case)[0] == raw
    result = verify(raw, data, expected_sha256=pins["manifest_sha256"],
                    approved_receipts=pins["review_receipts"], at=AT)
    assert result.trace["clear"]["exact_value"] == "1102"
    assert result.trace["logon"]["exact_value"] == "0x0055CD1D"
    assert result.normalized["clear", 1]["fields"]["precision_ns"] == 1
    assert len(result.active) == 4


def test_exact_bytes_and_missing_records():
    case, data = windows()
    original = data["clear", 1]
    data["clear", 1] = original.replace(b"operator", b"operat0r")
    with pytest.raises(ValueError, match="bytes mismatch"):
        verify_win(case, data)
    del data["clear", 1]
    with pytest.raises(ValueError, match="observation bytes"):
        verify_win(case, data)


@pytest.mark.parametrize(("mutate", "reason"), [
    (lambda c: c.update(schema_version="other"), "schema_version"),
    (lambda c: c["records"].append(c["records"][0]), "duplicate revision"),
    (lambda c: c["statements"].append(c["statements"][0]), "duplicate identifier"),
    (lambda c: c["statements"][0].update(sha256="0"*64), "statement digest"),
    (lambda c: c["statements"][0]["record"].update(revision=8), "unknown statement record"),
    (lambda c: c["statements"][0]["xml_path"][0].update(namespace="urn:else"), "XML field"),
    (lambda c: c["statements"][2].update(span=[-1, 5]), "text span"),
    (lambda c: c["sources"][0].update(upstream=["missing"]), "upstream lineage"),
    (lambda c: c["sources"][0].update(upstream=["audit-origin"]), "upstream lineage"),
    (lambda c: c["sources"][0].update(alias="custody-origin"), "collector alias"),
    (lambda c: c["events"][0].update(revision=2, supersedes=1), "revision history"),
    (lambda c: c["assertions"][0].update(statements=["unknown"]), "assertion reference"),
])
def test_malformed_manifest_graph_fails_closed(mutate, reason):
    case, data = windows()
    mutate(case)
    with pytest.raises(ValueError, match=reason):
        verify_win(case, data)


def test_superseded_record_cannot_prove_active_assertion():
    case, data = windows()
    case["records"].append({**case["records"][0], "revision": 2, "supersedes": 1})
    data["clear", 2] = data["clear", 1]
    with pytest.raises(ValueError, match="superseded evidence"):
        verify_win(case, data)


def test_revision_keeps_native_record_identity():
    case, data = windows()
    case["records"].append({**case["records"][0], "revision": 2, "supersedes": 1, "native_ref": "other"})
    data["clear", 2] = data["clear", 1]
    with pytest.raises(ValueError, match="changes source identity"):
        verify_win(case, data)


@pytest.mark.parametrize("mode", ["untrusted", "expired", "tampered", "stale", "revoked", "outer_pin"])
def test_review_authority_expiry_and_snapshot_binding(mode):
    case, data = windows()
    raw, pinned, approvals = seal_fixture(case)
    when = AT
    if mode == "untrusted":
        approvals = {}
    elif mode == "expired":
        when = "2026-11-21T00:00:00Z"
    elif mode == "outer_pin":
        raw += b" "
    else:
        if mode == "tampered":
            case["assertions"][2]["value"] = "benign"
        elif mode == "stale":
            case["sources"][0]["attestation_ref"] = "changed"
        else:
            case["receipts"].append({**case["receipts"][0], "revision": 2,
                                     "supersedes": 1, "decision": "revoked"})
        raw = json.dumps(case).encode()
        pinned = bytes_digest(raw)
    with pytest.raises(ValueError, match="review receipt|snapshot digest"):
        verify(raw, data, expected_sha256=pinned, approved_receipts=approvals, at=when)


def test_unverified_suggestions_are_separate_and_cannot_declare_review_authority():
    suggestion = {"id": "s", "case_id": "windows-fixture", "producer": "mock-model",
                  "value": "adversary", "statement_ids": ["clear"], "status": "unverified"}
    assert parse_suggestions(json.dumps([suggestion]))[0].status == "unverified"
    with pytest.raises(ValueError):
        parse_suggestions(json.dumps([{**suggestion, "reviewed": True}]))
    case, data = windows()
    case["suggestions"] = [suggestion]
    with pytest.raises(ValueError, match="suggestions"):
        verify_win(case, data)
