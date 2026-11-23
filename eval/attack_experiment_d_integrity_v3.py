"""Audit the proven Experiment D manifest byte discrepancy and its successor. Offline only."""
import argparse
import json
import re
from hashlib import sha256
from pathlib import Path

from eval.attack_experiment_d_v3 import MANIFEST, build_manifest
from eval.attack_experiment_v2 import dump, sha

REVISION = MANIFEST.with_name("incident-facts-first-manifest.r2.json")
STAMP_BYTES = re.compile(rb'"materialization_source_sha256": "([0-9a-f]+)"')
DIGEST = re.compile(r"[0-9a-f]{64}")


def encoded(manifest):
    """Use the frozen v2 writer representation, including one terminating LF."""
    return (json.dumps(manifest, ensure_ascii=True, indent=2) + "\n").encode("utf-8")


def prove_lineage(saved, canonical, authorized_digest):
    """Require exact byte recovery and prove that only the source stamp was affected."""
    if not DIGEST.fullmatch(authorized_digest):
        raise ValueError("Supply the original authorized SHA-256 as 64 lowercase hexadecimal digits")
    source_digest = canonical["materialization_source_sha256"]
    if not DIGEST.fullmatch(source_digest):
        raise ValueError("Current materialization source digest is malformed")
    expected = encoded(canonical)
    if sha256(expected).hexdigest() != authorized_digest:
        raise ValueError("Current canonical bytes do not reproduce the original authorized manifest")
    stamps = list(STAMP_BYTES.finditer(saved))
    if len(stamps) != 1:
        raise ValueError("Expected one materialization source stamp in the saved bytes")
    stamp = stamps[0]
    start, end = stamp.span(1)
    if end - start != 65:
        raise ValueError("Saved source stamp does not exhibit the one-byte integrity defect")
    offsets = [i for i in range(start, end) if saved[:i] + saved[i+1:] == expected]
    if len(offsets) != 1:
        raise ValueError("Could not uniquely recover the authorized bytes by removing one stamp byte")
    offset = offsets[0]
    return {
        "prior_authorized_manifest_sha256": authorized_digest,
        "prior_saved_manifest_sha256": sha256(saved).hexdigest(),
        "prior_saved_source_stamp": stamp[1].decode("ascii"),
        "materialization_source_sha256": source_digest,
        "inserted_byte_offset_zero_based": offset,
        "inserted_byte_hex": saved[offset:offset+1].hex(),
    }


def build_revision(authorized_digest):
    canonical, bounds = build_manifest()
    lineage = prove_lineage(MANIFEST.read_bytes(), canonical, authorized_digest)
    revision = {**canonical, "manifest_revision": 2, "integrity_lineage": lineage}
    return revision, bounds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "audit"))
    parser.add_argument("--prior-authorized-sha256", required=True)
    args = parser.parse_args()
    if not __debug__:
        raise RuntimeError("Assertions must be enabled for historical preflight checks")
    candidate, bounds = build_revision(args.prior_authorized_sha256)
    if args.operation == "prepare":
        dump(REVISION, candidate)
    if REVISION.read_bytes() != encoded(candidate):
        raise ValueError("Versioned manifest differs from verified canonical reconstruction")
    print(f"{len(candidate['requests'])} scheduled requests, manifest revision 2 SHA-256 {sha(REVISION)}")
    print(json.dumps(candidate["integrity_lineage"], indent=2))
    print(bounds)


if __name__ == "__main__":
    main()
