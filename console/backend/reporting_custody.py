"""Verify operational catalogue bytes under an independently provisioned public key."""

import base64
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def verify_catalogue(raw, *, checkout):
    key_file = os.environ.get("KAYAN_REPORTING_CUSTODY_PUBLIC_KEY")
    signature_file = os.environ.get("KAYAN_REPORTING_CUSTODY_SIGNATURE")
    if not key_file and not signature_file:
        return False
    if not key_file or not signature_file:
        raise ValueError("Independent signing settings are incomplete")
    key_path, signature_path = (Path(file).resolve(strict=True) for file in (key_file, signature_file))
    if any(path.is_relative_to(checkout) for path in (key_path, signature_path)):
        raise ValueError("Custodian material must be outside the checkout")
    key = load_pem_public_key(key_path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("Custodian key is not Ed25519")
    try:
        key.verify(base64.b64decode(signature_path.read_bytes().strip(), validate=True), raw)
    except (InvalidSignature, ValueError) as error:
        raise ValueError("Independent catalogue signature is invalid") from error
    return True

