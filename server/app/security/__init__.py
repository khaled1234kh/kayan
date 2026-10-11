"""Security module: the authoritative TrustGate.

The backend now owns enforcement. In backend mode this evaluator is the only thing
that decides whether an intent may proceed; the frontend's mock evaluator is
retained solely for local mock mode.

The flow it serves, and will keep serving as the single path:

    Agent intent -> TrustGate -> Event

A policy decision travels as structured event data (``policyDecision`` on
``policy_denied`` / ``policy_violation``, with the ``intent`` alongside) rather than
in its own table: the decision and the event announcing it are the same fact, and
two tables would create two answers to "what was decided".
"""

from app.security.trustgate import (
    ACTION_LABELS,
    CAPABILITY_CONTRACTS,
    PRIVATE_DATA_ACTIONS,
    SUBJECT_LABELS,
    AgentIntent,
    CapabilityContract,
    PolicyDecision,
    authorize_intent,
    evaluate_policy,
    matches,
    simulated_allow,
)

__all__ = [
    "ACTION_LABELS",
    "CAPABILITY_CONTRACTS",
    "PRIVATE_DATA_ACTIONS",
    "SUBJECT_LABELS",
    "AgentIntent",
    "CapabilityContract",
    "PolicyDecision",
    "authorize_intent",
    "evaluate_policy",
    "matches",
    "simulated_allow",
]