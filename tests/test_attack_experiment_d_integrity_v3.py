from hashlib import sha256

import pytest

from eval.attack_experiment_d_integrity_v3 import encoded, prove_lineage


def fixture():
    canonical = {"materialization_source_sha256": sha256(b"source\n").hexdigest(),
                 "requests": [{"sequence": 1, "request": {"prompt": "frozen prompt"}}]}
    original = encoded(canonical)
    digest = sha256(original).hexdigest()
    stamp = canonical["materialization_source_sha256"].encode()
    offset = original.index(stamp) + 17
    inserted = next(c for c in b"abcdef" if c not in original[offset-1:offset+1])
    saved = original[:offset] + bytes([inserted]) + original[offset:]
    return canonical, original, digest, saved, offset


def test_one_byte_source_stamp_corruption_reproduces_both_preflight_failures():
    canonical, original, authorized, saved, offset = fixture()
    # These are the original exact-byte audit and the independent file-hash gate.
    assert saved != encoded(canonical)
    assert sha256(saved).hexdigest() != authorized
    audit = prove_lineage(saved, canonical, authorized)
    assert audit["prior_saved_manifest_sha256"] == sha256(saved).hexdigest()
    assert audit["inserted_byte_offset_zero_based"] == offset
    assert saved[:offset] + saved[offset+1:] == original


@pytest.mark.parametrize("additional_change", [
    lambda raw: raw.replace(b"frozen prompt", b"changed prompt"),
    lambda raw: raw + b"\n",
    lambda raw: raw.replace(b'"sequence": 1', b'"sequence": 2'),
])
def test_reject_other_edits_even_with_a_corrupted_stamp(additional_change):
    canonical, _, authorized, saved, _ = fixture()
    with pytest.raises(ValueError, match="uniquely recover"):
        prove_lineage(additional_change(saved), canonical, authorized)


def test_reject_valid_looking_source_drift_or_wrong_authorization():
    canonical, _, authorized, saved, _ = fixture()
    with pytest.raises(ValueError, match="original authorized"):
        prove_lineage(saved, {**canonical, "materialization_source_sha256": "0"*64}, authorized)
    with pytest.raises(ValueError, match="original authorized"):
        prove_lineage(saved, canonical, "0"*64)
