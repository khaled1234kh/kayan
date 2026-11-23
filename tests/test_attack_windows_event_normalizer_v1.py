from dataclasses import replace

import pytest

from eval.attack_windows_event_normalizer_v1 import normalize, normalize_observation, session_candidate
from eval.fixtures.ai.attack_fact_registry_v1.demo import HERE, WINDOW, session_inputs


def test_exact_fields_and_target_roles():
    clear, logon = session_inputs()
    obs = logon.observation
    assert clear.observation["reported_outcome"] == "completed_clear"
    assert obs["sid"] == clear.observation["sid"]
    assert obs["original_fields"]["logon_id"] == "0x0055CD1D"
    assert obs["logon_id"] == clear.observation["logon_id"] == 0x55CD1D
    assert obs["locators"]["sid"]["path"][-1][-1] == "TargetUserSid"
    assert obs["precision_ns"] == 1
    assert obs["reported_at_ns"] % 10**9 == 1
    assert obs == normalize((HERE / "logon.xml").read_bytes())
    assert session_candidate(clear, [logon], window_ns=WINDOW) == {
        "state": "candidate", "record_ref": "logon.xml",
    }


@pytest.mark.parametrize("mutation", [
    lambda raw: b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///should-not-open">]>' + raw,
    lambda raw: raw[:30],
    lambda raw: b" " * 65537,
    lambda raw: b"<child>" * 13 + b"</child>" * 13,
    lambda raw: raw.replace(b"<Version>0</Version>", b"<Version>0</Version><Version>0</Version>"),
    lambda raw: raw.replace(b"Microsoft-Windows-Eventlog", b"Other"),
    lambda raw: raw.replace(b"<Channel>Security", b"<Channel>System"),
    lambda raw: raw.replace(b"http://schemas.microsoft.com/win/2004/08/events/event", b"urn:other"),
    lambda raw: raw.replace(b"SubjectUserSid>", b"InvalidSidField>"),
    lambda raw: raw.replace(b"000000001Z", b"000000001"),
])
def test_reject_unsafe_or_invalid_xml(mutation):
    with pytest.raises(ValueError):
        normalize(mutation((HERE / "clear.xml").read_bytes()))


def test_unsupported_profile_has_diagnostic_only():
    raw = (HERE / "clear.xml").read_bytes().replace(b"<Version>0", b"<Version>7")
    assert normalize_observation(raw) == {"state": "unsupported", "reason": "unsupported event/profile version"}


@pytest.mark.parametrize("scope", [
    {"tenant": "red"}, {"asset": "other-host"}, {"authority": "different-domain"},
    {"generation": None}, {"generation": "other-boot"}, {"generation_window_ns": None},
    {"clock_error_ns": None}, {"clock_error_ns": WINDOW},
])
def test_same_name_and_native_token_do_not_establish_scope(scope):
    clear, logon = session_inputs()
    assert session_candidate(clear, [replace(logon, **scope)], window_ns=WINDOW)["state"] == "unresolved"


@pytest.mark.parametrize("change", [
    {"sid": "S-1-5-21-100-200-300-1105"}, {"logon_id": 0}, {"logon_id": None},
])
def test_missing_or_different_native_identity(change):
    clear, logon = session_inputs()
    logon = replace(logon, observation={**logon.observation, **change})
    assert session_candidate(clear, [logon], window_ns=WINDOW)["state"] == "unresolved"


def test_overlapping_reversed_outside_window_and_duplicate_candidates():
    clear, logon = session_inputs()
    for offset in (0, 100, -WINDOW - 10):
        changed = replace(logon, observation={
            **logon.observation, "reported_at_ns": clear.observation["reported_at_ns"] + offset,
        })
        assert session_candidate(clear, [changed], window_ns=WINDOW)["state"] == "unresolved"
    other = replace(logon, record_ref="second-logon")
    assert session_candidate(clear, [logon, other], window_ns=WINDOW)["state"] == "unresolved"
    assert session_candidate(clear, [], window_ns=WINDOW)["state"] == "unresolved"


@pytest.mark.parametrize("reverse", [False, True])
def test_incomplete_competing_logon_prevents_unique_candidate(reverse):
    clear, logon = session_inputs()
    other = replace(logon, record_ref="other-logon", observation={**logon.observation, "sid": None})
    pair = [other, logon] if reverse else [logon, other]
    assert session_candidate(clear, pair, window_ns=WINDOW)["state"] == "unresolved"


def test_out_of_range_sid_cannot_join():
    clear, logon = session_inputs()
    invalid = "S-1-5-21-100-200-300-4294967296"
    observations = [
        normalize((HERE / record.record_ref).read_bytes()
                  .replace(record.observation["sid"].encode(), invalid.encode()))
        for record in (clear, logon)
    ]
    for obs in observations:
        assert obs["original_fields"]["sid"] == invalid
        assert obs["sid"] is None
        assert "unresolved_sid" in obs["diagnostics"]
    assert session_candidate(clear, [replace(logon, observation=observations[1])],
                             window_ns=WINDOW)["state"] == "unresolved"


@pytest.mark.parametrize("changes", [
    {"sid": "S-1-5-21-100-200-300-1105"},
    {"logon_id": 99},
])
def test_known_incompatible_competitor_does_not_block(changes):
    clear, logon = session_inputs()
    other = replace(logon, record_ref="different", observation={**logon.observation, **changes})
    assert session_candidate(clear, [other, logon], window_ns=WINDOW)["state"] == "candidate"


@pytest.mark.parametrize("boundary", ["case_id", "tenant", "asset", "generation", "time"])
def test_incomplete_competitor_outside_known_boundaries_is_excluded(boundary):
    clear, logon = session_inputs()
    obs = {**logon.observation, "sid": None}
    if boundary == "time":
        obs["reported_at_ns"] = clear.observation["reported_at_ns"] + 1
    changes = {} if boundary == "time" else {boundary: "different"}
    other = replace(logon, record_ref="out-of-scope", observation=obs, **changes)
    assert session_candidate(clear, [other, logon], window_ns=WINDOW)["state"] == "candidate"


def test_duplicate_reference_alone_does_not_prove_same_record():
    clear, logon = session_inputs()
    assert session_candidate(clear, [logon, logon], window_ns=WINDOW)["state"] == "unresolved"


@pytest.mark.parametrize(("raw_sid", "expected"), [
    ("S-1-5-0", "S-1-5-0"),
    ("S-1-4294967295-4294967295", "S-1-4294967295-4294967295"),
    ("S-1-0x000100000000-1", "S-1-0x000100000000-1"),
    ("S-1-0xffffffffffff-1", "S-1-0xFFFFFFFFFFFF-1"),
    ("S-1-5" + "-0" * 15, "S-1-5" + "-0" * 15),
    ("S-1-5" + "-0" * 16, None),
    ("S-1-5", None),
    ("S-2-5-1", None),
    ("S-1-4294967296-1", None),
    ("S-1-0x0000FFFFFFFF-1", None),
    ("S-1-0x1000000000000-1", None),
    ("S-1-05-1", None),
    ("S-1-5-01", None),
    ("S-1-0-0", None),
    ("S-1", None),
])
def test_sid_profile_bounds(raw_sid, expected):
    raw = (HERE / "clear.xml").read_bytes()
    obs = normalize(raw.replace(b"S-1-5-21-100-200-300-1104", raw_sid.encode()))
    assert obs["sid"] == expected
    assert obs["original_fields"]["sid"] == raw_sid
    assert ("unresolved_sid" in obs["diagnostics"]) == (expected is None)
