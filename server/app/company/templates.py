"""Company and role template catalogue (P0.1).

Seed/configuration data, not a template-management product: these definitions are
versioned with ``config_version`` and shipped with the backend. The role set
starts from the existing canonical demo roles (manager, sales, operations,
employee, ceo) and adds the roles a configured workforce needs (hr, support).

Every role is offered with a default *structured* scope so contract generation
(P0.4) starts from validated terms rather than prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CLOTHING = "clothing"
CUSTOMIZED_GIFTS = "customized_gifts"
CUSTOM = "custom"

TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "key": CLOTHING,
        "label": "Clothing brand",
        "summary": "Product catalogue, stock-aware quotation, branded fulfilment.",
        "industries": ["apparel", "fashion", "retail"],
        "role_keys": ["ceo", "manager", "sales", "operations", "hr", "support"],
        "task_categories": ["quotation", "inventory", "fulfilment", "hr", "support"],
    },
    {
        "key": CUSTOMIZED_GIFTS,
        "label": "Customized gifts",
        "summary": "Made-to-order gifts with supplier coordination and approvals.",
        "industries": ["gifts", "wholesale", "ecommerce"],
        "role_keys": ["ceo", "manager", "sales", "operations", "hr", "support"],
        "task_categories": ["quotation", "sourcing", "inventory", "fulfilment", "support"],
    },
    {
        "key": CUSTOM,
        "label": "Custom business",
        "summary": "A business that does not fit a catalogue template.",
        "industries": [],
        "role_keys": ["ceo", "manager", "hr", "support"],
        "task_categories": ["operations", "hr", "support"],
    },
)

TEMPLATE_KEYS: tuple[str, ...] = tuple(t["key"] for t in TEMPLATES)


@dataclass(frozen=True)
class RoleSeed:
    key: str
    label: str
    kind: str
    summary: str
    responsibilities: list[str] = field(default_factory=list)
    task_categories: list[str] = field(default_factory=list)
    data_scope: list[dict[str, Any]] = field(default_factory=list)
    tool_scope: list[dict[str, Any]] = field(default_factory=list)
    restrictions: list[str] = field(default_factory=list)
    template_keys: list[str] = field(default_factory=list)


#: Role definitions reused by the configured workforce. ``ceo`` and the three
#: original demo roles keep the same responsibilities and restrictions as the
#: canonical profiles, so a configured company is a consistent extension of the demo.
ROLE_SEEDS: tuple[RoleSeed, ...] = (
    RoleSeed(
        key="ceo",
        label="Chief Executive Officer",
        kind="human",
        summary="Accountable for the final business decision.",
        responsibilities=["Review the final result", "Approve or reject the final business action"],
        task_categories=["approval", "review"],
        data_scope=[
            {"resource": "orders", "operations": ["read", "write"]},
            {"resource": "reports", "operations": ["read"]},
            {"resource": "budget", "operations": ["read"]},
        ],
        tool_scope=[{"tool": "approval", "actions": ["approve", "reject"]}],
        restrictions=[],
        template_keys=list(TEMPLATE_KEYS),
    ),
    RoleSeed(
        key="manager",
        label="Manager",
        kind="ai",
        summary="Decomposes goals and coordinates the team.",
        responsibilities=[
            "Decompose business goal",
            "Assign tasks",
            "Review subordinate results",
            "Request approval",
        ],
        task_categories=["quotation", "inventory", "fulfilment"],
        data_scope=[
            {"resource": "orders", "operations": ["read"]},
            {"resource": "tasks", "operations": ["read", "write"]},
            {"resource": "inventory", "operations": ["read"]},
        ],
        tool_scope=[{"tool": "task", "actions": ["assign", "review"]}],
        # Matches the canonical demo manager restrictions.
        restrictions=["cannot_self_grant_permissions", "cannot_approve_final_action"],
        template_keys=list(TEMPLATE_KEYS),
    ),
    RoleSeed(
        key="sales",
        label="Sales",
        kind="ai",
        summary="Prepares quotations from available data.",
        responsibilities=[
            "Prepare quotations",
            "Inspect order details",
            "Request inventory information",
            "Revise quotation",
        ],
        task_categories=["quotation"],
        data_scope=[
            {"resource": "orders.assigned", "operations": ["read"]},
            {"resource": "catalog", "operations": ["read"]},
            {"resource": "inventory", "operations": ["read"]},
        ],
        tool_scope=[{"tool": "inventory_lookup", "actions": ["check_availability"]}],
        restrictions=["customer_private_records", "finalize_without_ceo_approval"],
        template_keys=list(TEMPLATE_KEYS),
    ),
    RoleSeed(
        key="operations",
        label="Operations",
        kind="ai",
        summary="Establishes what can actually be fulfilled.",
        responsibilities=[
            "Inspect inventory",
            "Validate availability",
            "Report inventory conflicts",
        ],
        task_categories=["inventory", "fulfilment", "sourcing"],
        data_scope=[
            {"resource": "inventory", "operations": ["read"]},
            {"resource": "orders.assigned", "operations": ["read"]},
        ],
        tool_scope=[{"tool": "inventory_lookup", "actions": ["check_availability"]}],
        restrictions=["customer_private_records", "pricing_modification"],
        template_keys=list(TEMPLATE_KEYS),
    ),
    RoleSeed(
        key="hr",
        label="HR",
        kind="ai",
        summary="People operations and workforce records.",
        responsibilities=["Maintain workforce records", "Handle workforce requests"],
        task_categories=["hr"],
        data_scope=[
            {"resource": "workforce", "operations": ["read"]},
            {"resource": "contracts", "operations": ["read"]},
        ],
        tool_scope=[{"tool": "directory", "actions": ["lookup"]}],
        restrictions=["customer_private_records"],
        template_keys=list(TEMPLATE_KEYS),
    ),
    RoleSeed(
        key="support",
        label="Support",
        kind="ai",
        summary="Handles inbound customer questions.",
        responsibilities=["Answer customer questions", "Escalate blockers"],
        task_categories=["support"],
        data_scope=[{"resource": "orders.assigned", "operations": ["read"]}],
        tool_scope=[{"tool": "directory", "actions": ["lookup"]}],
        restrictions=["customer_private_records", "pricing_modification"],
        template_keys=[CLOTHING, CUSTOMIZED_GIFTS],
    ),
)

ROLE_KEYS: tuple[str, ...] = tuple(role.key for role in ROLE_SEEDS)


def _templates_offering(role_key: str) -> list[str]:
    """Templates that actually offer ``role_key``, in catalogue order."""
    return [t["key"] for t in TEMPLATES if role_key in t["role_keys"]]


def _align_template_keys() -> None:
    """Derive each role's compatible templates from the templates themselves.

    ``RoleTemplate.template_keys`` and a template's ``role_keys`` are two views of
    one fact. Authoring both by hand let them drift — a role could claim a template
    that does not offer it, which would make the setup endpoint advertise a role
    the workforce API then refuses. Deriving one from the other removes the
    possibility rather than fixing today's instance of it.
    """
    for role in ROLE_SEEDS:
        role.template_keys[:] = _templates_offering(role.key)


_align_template_keys()


def template_by_key(key: str) -> dict[str, Any] | None:
    return next((t for t in TEMPLATES if t["key"] == key), None)


def roles_for_template(template_key: str) -> list[RoleSeed]:
    """Roles offered for a template, in a deterministic order."""
    template = template_by_key(template_key)
    if template is None:
        return []
    offered = set(template["role_keys"])
    return [role for role in ROLE_SEEDS if role.key in offered]


def role_by_key(key: str) -> RoleSeed | None:
    return next((role for role in ROLE_SEEDS if role.key == key), None)