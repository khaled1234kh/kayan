"""TrustGate — the authoritative backend policy evaluator.

Ported from the verified mock evaluator in
``kayan-3d/src/security/trustGate.ts`` so the semantics are identical: same
capability contracts, same rule order, same policy names and reasons.

There is exactly **one** backend evaluator, and in backend mode it is the only
one that decides. The frontend copy remains the local mock's evaluator; it is
never consulted for an authoritative decision.

Rules are evaluated in a fixed order, so the same intent always produces the same
decision and the same reason:

1. explicit prohibition wins
2. the resource must be inside the actor's capability scope
3. private data may not be reached through an untrusted instruction
4. consequential actions need a human approval token
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

IntentSource = Literal["trusted", "untrusted"]
Decision = Literal["allow", "deny"]


@dataclass(frozen=True)
class CapabilityContract:
    """What a seat may do, and what it may never do on its own initiative."""

    agent_id: str
    scope: tuple[str, ...]
    forbidden: tuple[str, ...] = ()
    require_approval: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentIntent:
    """An agent's intent to act, formed *before* execution."""

    agent_id: str
    action: str
    resource: str
    source: IntentSource
    context: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        """Serialise for the ``intent`` key on an event payload."""
        return {
            "agentId": self.agent_id,
            "action": self.action,
            "resource": self.resource,
            "source": self.source,
            "context": self.context,
        }


@dataclass(frozen=True)
class PolicyDecision:
    """Structured outcome. Field names match the frontend contract exactly."""

    decision: Decision
    policy: str
    subject: str
    action: str
    resource: str
    reason: str

    @property
    def allowed(self) -> bool:
        return self.decision == "allow"

    def to_payload(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "policy": self.policy,
            "subject": self.subject,
            "action": self.action,
            "resource": self.resource,
            "reason": self.reason,
        }


#: Capability contracts, mirroring the authority lines in the actor inspector.
CAPABILITY_CONTRACTS: dict[str, CapabilityContract] = {
    contract.agent_id: contract
    for contract in (
        CapabilityContract("manager", ("task/*", "plan/*", "inventory/*"), ("customer/*", "hr/*"), ("quote.send",)),
        CapabilityContract("sales", ("catalog/*", "quote/*", "task/*"), ("customer/*", "hr/*"), ("quote.send",)),
        CapabilityContract("operations", ("inventory/*", "task/*"), ("customer/*", "hr/*"), ()),
        CapabilityContract("employee", ("task/*", "inventory/*"), ("customer/*", "hr/*"), ()),
        CapabilityContract("ceo", ("task/*", "customer/*", "hr/*"), (), ()),
    )
}

#: Actions that touch private records; these require a trusted origin.
PRIVATE_DATA_ACTIONS = ("customer_data.read", "customer_data.export")

SUBJECT_LABELS: dict[str, str] = {
    "manager": "AI Manager",
    "sales": "AI Sales",
    "operations": "AI Operations",
    "employee": "Human Employee",
    "ceo": "Nadia Farouk",
}

ACTION_LABELS: dict[str, str] = {
    "customer_data.read": "Read customer record",
    "customer_data.export": "Export customer data",
    "inventory.read": "Read authorized inventory information",
    "quote.draft": "Draft quotation",
}


def matches(pattern: str, resource: str) -> bool:
    """Glob matcher supporting a trailing ``*`` wildcard."""
    if pattern.endswith("/*"):
        return resource.startswith(pattern[:-1])
    if pattern.endswith("*"):
        return resource.startswith(pattern[:-1])
    return pattern == resource


def _deny(intent: AgentIntent, policy: str, reason: str) -> PolicyDecision:
    return PolicyDecision(
        decision="deny",
        policy=policy,
        subject=SUBJECT_LABELS.get(intent.agent_id, intent.agent_id),
        action=ACTION_LABELS.get(intent.action, intent.action),
        resource=intent.resource,
        reason=reason,
    )


def evaluate_policy(
    intent: AgentIntent,
    contract: CapabilityContract,
    *,
    human_approved: bool = False,
) -> PolicyDecision:
    """Evaluate one intent against one contract. Fixed rule order."""
    # 1. Explicit prohibition always wins.
    if any(matches(p, intent.resource) for p in contract.forbidden):
        return _deny(intent, "Customer Data Scope", "Resource outside actor authorization scope")

    # 2. The resource must be inside the actor's capability scope.
    if not any(matches(p, intent.resource) for p in contract.scope):
        return _deny(intent, "Capability Contract", "Action outside granted capability scope")

    # 3. Private data may not be reached through an untrusted instruction.
    if intent.source == "untrusted" and intent.action in PRIVATE_DATA_ACTIONS:
        return _deny(intent, "Untrusted Origin", "Untrusted input cannot drive private data access")

    # 4. Consequential actions require a human approval token.
    if intent.action in contract.require_approval and not human_approved:
        return _deny(intent, "Approval Gateway", "Human approval token required")

    return PolicyDecision(
        decision="allow",
        policy="Capability Contract",
        subject=SUBJECT_LABELS.get(intent.agent_id, intent.agent_id),
        action=ACTION_LABELS.get(intent.action, intent.action),
        resource=intent.resource,
        reason="Within granted capability scope",
    )


def authorize_intent(intent: AgentIntent, *, human_approved: bool = False) -> PolicyDecision:
    """TrustGate entry point: authorize exactly one intent.

    A missing contract is a denial, not a crash.
    """
    contract = CAPABILITY_CONTRACTS.get(intent.agent_id)
    if contract is None:
        return _deny(intent, "Capability Contract", "No capability contract for this actor")
    return evaluate_policy(intent, contract, human_approved=human_approved)


def simulated_allow(intent: AgentIntent) -> PolicyDecision:
    """Baseline decision for the simulated unauthorized action.

    Nothing is accessed. The action is *recorded as allowed* so the difference
    between conditions is observable: no ``policy_denied``, no ``blocked``, and
    no customer data touched. This exists only to measure the experimental
    condition and is never reachable from an ordinary ``request_order``.
    """
    return PolicyDecision(
        decision="allow",
        policy="Baseline · enforcement disabled",
        subject=intent.agent_id,
        action=intent.action,
        resource=intent.resource,
        reason="Unauthorized action simulated as allowed — enforcement disabled for this condition",
    )