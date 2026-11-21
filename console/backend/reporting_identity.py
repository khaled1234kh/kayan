"""Externally managed enrollment for loopback evidence workflows."""

from hashlib import sha256
from hmac import compare_digest
import json
import os
from pathlib import Path
import re

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_ .-]{0,79}")
SHA = re.compile(r"[0-9a-f]{64}")


def enrolment():
    location = os.environ.get("KAYAN_REPORTING_REVIEWERS_FILE")
    if not location:
        raise LookupError("No independent reviewer assignments configured")
    path = Path(location).resolve(strict=True)
    if path.is_relative_to(ROOT):
        raise ValueError("Enrollment must be managed outside the checkout")
    raw = path.read_bytes()
    if not compare_digest(sha256(raw).hexdigest(), os.environ.get("KAYAN_REPORTING_REVIEWERS_SHA256", "")):
        raise ValueError("Enrollment pin did not match")
    entries = json.loads(raw)
    if not isinstance(entries, list):
        raise ValueError("Expected an enrollment list")
    people, tokens, keys, fingerprints = {}, set(), set(), set()
    for row in entries:
        identity = row["reviewer_id"]
        token = row["token_sha256"]
        role = row.get("role", "reviewer")
        active = row.get("active", True)
        test_only = row.get("test_only", False)
        cases = row["assessment_ids"]
        if (not ID.fullmatch(identity) or identity.casefold() in people or not SHA.fullmatch(token)
                or token in tokens or role not in {"reviewer", "custodian"} or type(active) is not bool
                or type(test_only) is not bool or not isinstance(cases, list) or any(not isinstance(case, str) for case in cases)):
            raise ValueError("Invalid or conflicting role assignment")
        if role == "custodian":
            key_id = row.get("key_id", "")
            fingerprint = row.get("public_key_sha256", "")
            if (not ID.fullmatch(key_id) or not SHA.fullmatch(fingerprint)
                    or key_id in keys or fingerprint in fingerprints or not isinstance(row.get("public_key_file"), str)):
                raise ValueError("Invalid or duplicate custodian key")
            keys.add(key_id)
            fingerprints.add(fingerprint)
        people[identity.casefold()] = {**row, "role": role, "active": active, "test_only": test_only}
        tokens.add(token)
    return people


def authenticate(request, assessment_id, roles):
    loopback = ("127.0.0.1", "::1", "localhost")
    if request.url.hostname not in loopback or not request.client or request.client.host not in loopback:
        raise HTTPException(403, "Review requires the loopback console")
    try:
        people = enrolment()
    except (LookupError, ValueError, OSError, TypeError):
        raise HTTPException(503, "Independent reviewer enrollment is unavailable or invalid") from None
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme != "Bearer" or not token:
        raise HTTPException(403, "An assigned reviewer or custodian token is required")
    token_hash = sha256(token.encode()).hexdigest()
    for row in people.values():
        if (compare_digest(token_hash, row["token_sha256"]) and row["active"] and row["role"] in roles
                and assessment_id in row["assessment_ids"]):
            return row
    raise HTTPException(403, "Identity is not assigned to this assessment and action")

