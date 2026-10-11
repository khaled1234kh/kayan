"""Contract terms: canonical form and integrity hash.

A contract's ``content_hash`` is the claim "these are the terms this employee
works under". It is only worth anything if it is:

* **complete** — covering every material term, including the budgets and the
  reporting line, not just the descriptive text;
* **canonical** — the same terms always produce the same digest, so two systems
  comparing hashes compare the terms;
* **reproducible** — a client can recompute it and get the same answer.

Canonical form here is JSON with sorted keys, no insignificant whitespace, and
``Decimal`` rendered as a plain decimal string. Floats are never involved: ``0.1``
has no single binary representation, and a hash that shifts with floating point is
not an integrity check.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

#: Every column whose value is part of the contract's substance. Kept in one place
#: so the hash, the validation and the database trigger are talking about the same
#: set; ``tests/test_p0_4_contracts.py`` asserts the trigger agrees with this list.
MATERIAL_COLUMNS: tuple[str, ...] = (
    "company_id",
    "employee_id",
    "version_number",
    "role",
    "role_config_version",
    "objective",
    "responsibilities",
    "data_scope",
    "tool_scope",
    "restrictions",
    "task_scope",
    "communication_policy",
    "approval_rules",
    "budget_per_task",
    "budget_per_month",
    "reports_to_employee_id",
    "requires_human_escalation",
)

#: Lifecycle columns are deliberately excluded: activation, supersession and id
#: change without changing what the employee is allowed to do.
LIFECYCLE_COLUMNS: tuple[str, ...] = (
    "id",
    "status",
    "effective_at",
    "activated_at",
    "superseded_at",
    "supersedes_id",
    "source",
    "created_at",
)


def canonical(value: Any) -> Any:
    """Convert a value into its canonical JSON form.

    ``Decimal`` becomes a normalised decimal string so ``5000.00`` and ``5000`` hash
    identically while no float ever enters the digest.
    """
    if isinstance(value, Decimal):
        normalised = value.normalize()
        # ``normalize()`` turns 100 into 1E+2; expand() keeps it readable.
        return format(normalised, "f")
    if isinstance(value, dict):
        return {str(key): canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(item) for item in value]
    return value


def contract_terms(contract) -> dict[str, Any]:
    """The material terms of a contract, in canonical form."""
    terms: dict[str, Any] = {}
    for column in MATERIAL_COLUMNS:
        terms[column] = canonical(getattr(contract, column))
    return terms


def serialise(terms: dict[str, Any]) -> str:
    """The exact string that is hashed: sorted keys, no incidental whitespace."""
    return json.dumps(terms, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_content_hash(contract) -> str:
    """SHA-256 over the canonical material terms of a contract."""
    return hashlib.sha256(serialise(contract_terms(contract)).encode("utf-8")).hexdigest()


def verify_content_hash(contract) -> bool:
    """True when the stored hash matches the terms actually on the row."""
    return contract.content_hash == compute_content_hash(contract)


__all__ = [
    "LIFECYCLE_COLUMNS",
    "MATERIAL_COLUMNS",
    "canonical",
    "compute_content_hash",
    "contract_terms",
    "serialise",
    "verify_content_hash",
]