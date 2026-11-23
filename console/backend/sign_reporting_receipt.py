"""Custodian-side tool. Run on the separate workstation that owns the key."""

import argparse
from base64 import b64encode
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from console.backend.reporting_exchange import Receipt, canonical, digest
from console.backend.reporting_identity import ROOT


def build_receipt(export, catalogue, key_id, private_key):
    package = export["package"]
    if digest(canonical(package)) != export["package_sha256"]:
        raise ValueError("Exported package digest is invalid")
    review_hashes = [row["sha256"] for row in package["reviews"]]
    if not review_hashes or any(digest(canonical(row["review"])) != row["sha256"] for row in package["reviews"]):
        raise ValueError("Review decisions are missing or modified")
    if (catalogue["assessment_id"] != package["assessment_id"]
            or catalogue["operational_evidence_sha256"] != package["source_sha256"]
            or set(catalogue["review_receipt_sha256"]) != set(review_hashes)):
        raise ValueError("Catalogue and review package do not match")
    head = export.get("head")
    receipt = Receipt(assessment_id=package["assessment_id"], key_id=key_id, package_sha256=export["package_sha256"],
                      sequence=head["sequence"] + 1 if head else 1,
                      previous_receipt_sha256=head["receipt_sha256"] if head else None,
                      catalogue=catalogue, signature="")
    return receipt.model_copy(update={"signature": b64encode(private_key.sign(receipt.signed_bytes())).decode("ascii")})


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--package", required=True, type=Path)
    cli.add_argument("--catalogue", required=True, type=Path)
    cli.add_argument("--key-id", required=True)
    cli.add_argument("--private-key", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    key_path = args.private_key.resolve(strict=True)
    if key_path.is_relative_to(ROOT):
        cli.error("Private signing key must be outside the checkout on the custodian's workstation")
    key = load_pem_private_key(key_path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        cli.error("Custody signing requires an Ed25519 key")
    receipt = build_receipt(json.loads(args.package.read_bytes()), json.loads(args.catalogue.read_bytes()),
                            args.key_id, key)
    with args.output.open("xb") as destination:
        destination.write(canonical(receipt.model_dump()))
    print(digest(canonical(receipt.model_dump())))


if __name__ == "__main__":
    main()

