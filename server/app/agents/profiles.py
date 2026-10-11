"""Canonical agent definitions.

These mirror ``kayan-3d/src/agents/agentProfiles.ts`` — the same five seats with
the same ids. They are the seed for the backend, not a competing definition: a
test asserts parity with the frontend file so the two cannot drift.

Capabilities and restrictions are descriptive metadata only. They are **not** an
authorization mechanism; TrustGate is the enforcement point and still lives in
the frontend during this migration phase.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentSeed:
    """Minimum persistent projection of an agent profile."""

    id: str
    name: str
    role: str
    kind: str
    objective: str
    capabilities: list[str] = field(default_factory=list)
    restrictions: list[str] = field(default_factory=list)


#: The five KAYAN seats, in floor order.
AGENT_SEEDS: tuple[AgentSeed, ...] = (
    AgentSeed(
        id="ceo",
        name="Nadia Farouk",
        role="Chief Executive Officer",
        kind="human",
        objective="Accountable for the final business decision on every order.",
        capabilities=["review final result", "approve final action", "reject final action"],
        restrictions=["Cannot be delegated approval authority"],
    ),
    AgentSeed(
        id="employee",
        name="Tarek Mansour",
        role="Human Employee",
        kind="human",
        objective="Resolve operational ambiguity that the agents cannot settle alone.",
        capabilities=[
            "provide missing information",
            "resolve operational ambiguity",
            "confirm business decision",
        ],
        restrictions=["Sees only assigned task context"],
    ),
    AgentSeed(
        id="manager",
        name="AI Manager",
        role="Coordinator",
        kind="ai",
        objective="Decompose the business goal and drive it to a decision.",
        capabilities=[
            "decompose business goal",
            "assign tasks",
            "request information",
            "review subordinate results",
            "request approval",
        ],
        restrictions=["Cannot raise its own permissions", "Cannot approve final business action"],
    ),
    AgentSeed(
        id="sales",
        name="AI Sales",
        role="Sales Agent",
        kind="ai",
        objective="Produce an accurate customer quotation from available data.",
        capabilities=[
            "prepare quotations",
            "inspect order details",
            "request inventory information",
            "revise quotation",
        ],
        restrictions=[
            "Cannot finalise without CEO approval",
            "Cannot access customer records",
        ],
    ),
    AgentSeed(
        id="operations",
        name="AI Operations",
        role="Operations Agent",
        kind="ai",
        objective="Establish what can actually be fulfilled, and report conflicts honestly.",
        capabilities=[
            "inspect inventory",
            "validate availability",
            "report inventory conflicts",
            "request clarification",
        ],
        restrictions=["Cannot modify pricing", "Cannot access customer records"],
    ),
)

#: External senders are not agents; they have no seat and no mailbox.
EXTERNAL_SENDER_LABELS: dict[str, str] = {"ext:supplier": "External Supplier"}


def agent_seed_ids() -> tuple[str, ...]:
    return tuple(seed.id for seed in AGENT_SEEDS)