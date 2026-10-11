"""The permission vocabulary a contract may draw on.

A contract grants authority, so what it may grant has to be a closed set. An
unfamiliar tool or resource is refused rather than widened: "the caller supplied a
value nobody recognises" is a reason to stop, not a reason to allow everything that
value might reach.

The supported resources and tools are **derived from the versioned role
catalogue** rather than restated here. That is deliberate: the catalogue is what
defines the vocabulary the product knows, so a second hand-written list could only
ever drift from it.
"""

from __future__ import annotations

from app.company.templates import ROLE_SEEDS

#: The only operations a grant may express.
SUPPORTED_OPERATIONS: frozenset[str] = frozenset({"read", "write"})

#: Restrictions a contract may carry. Also derived from the catalogue.
SUPPORTED_RESTRICTIONS: frozenset[str] = frozenset(
    restriction for role in ROLE_SEEDS for restriction in role.restrictions
)


def _catalogue_values(field: str) -> frozenset[str]:
    """Every distinct value the seeded roles grant for one scope kind."""
    values: set[str] = set()
    for role in ROLE_SEEDS:
        for entry in getattr(role, field):
            values.add(entry.get("resource") or entry.get("tool"))
    return frozenset(value for value in values if value)


#: Resources a contract may name, taken from the role catalogue.
SUPPORTED_RESOURCES: frozenset[str] = _catalogue_values("data_scope")

#: Tools a contract may name, taken from the role catalogue.
SUPPORTED_TOOLS: frozenset[str] = _catalogue_values("tool_scope")

#: Task categories a contract may scope work to.
SUPPORTED_TASK_CATEGORIES: frozenset[str] = frozenset(
    category for role in ROLE_SEEDS for category in role.task_categories
)


def unknown_in_scope(scope: list[dict], *, field: str) -> list[str]:
    """Names in ``scope`` that the supported vocabulary does not contain."""
    supported = SUPPORTED_RESOURCES if field == "resource" else SUPPORTED_TOOLS
    return sorted(
        {
            entry.get(field)
            for entry in scope
            if isinstance(entry, dict) and entry.get(field) not in supported
        }
    )


__all__ = [
    "SUPPORTED_OPERATIONS",
    "SUPPORTED_RESOURCES",
    "SUPPORTED_RESTRICTIONS",
    "SUPPORTED_TASK_CATEGORIES",
    "SUPPORTED_TOOLS",
    "unknown_in_scope",
]