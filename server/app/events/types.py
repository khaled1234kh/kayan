"""The KAYAN event vocabulary.

Mirrors ``kayan-3d/src/types/events.ts``. The frontend remains the prototype's
reference copy until the backend becomes authoritative; this module is the
server-side mirror used for persistence and validation, not a second definition
with independent semantics.
"""

from __future__ import annotations

import enum


class EventType(str, enum.Enum):
    """Every event name the system can persist."""

    ORDER_RECEIVED = "order_received"
    PLAN_PROPOSED = "plan_proposed"
    PLAN_VALIDATED = "plan_validated"
    TASK_ASSIGNED = "task_assigned"
    TASK_STARTED = "task_started"
    AWAITING_INFO = "awaiting_info"
    INFORMATION_PROVIDED = "information_provided"
    POLICY_DENIED = "policy_denied"
    POLICY_VIOLATION = "policy_violation"
    BLOCKED = "blocked"
    ARTIFACT_CREATED = "artifact_created"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    TASK_COMPLETED = "task_completed"
    COST_METERED = "cost_metered"

    AGENT_MESSAGE_SENT = "agent_message_sent"
    AGENT_MESSAGE_RECEIVED = "agent_message_received"
    TASK_DELEGATED = "task_delegated"
    TASK_ACCEPTED = "task_accepted"
    TASK_HANDOFF = "task_handoff"
    INFORMATION_REQUESTED = "information_requested"
    AGENT_QUESTION = "agent_question"
    AGENT_RESPONSE = "agent_response"
    APPROVAL_RESPONSE = "approval_response"

    # -- company / workforce (P0) ----------------------------------------
    COMPANY_CREATED = "company_created"
    COMPANY_UPDATED = "company_updated"
    WORKFORCE_CONFIGURED = "workforce_configured"
    RECOMMENDATION_GENERATED = "recommendation_generated"
    RECOMMENDATION_ACCEPTED = "recommendation_accepted"
    CONTRACT_GENERATED = "contract_generated"
    CONTRACT_UPDATED = "contract_updated"
    CONTRACT_VERSION_CREATED = "contract_version_created"
    CONTRACT_ACTIVATED = "contract_activated"
    CONTRACT_SUPERSEDED = "contract_superseded"
    # -- budget (P0) ------------------------------------------------------
    BUDGET_ADJUSTED = "budget_adjusted"
    BUDGET_RESERVED = "budget_reserved"
    BUDGET_RELEASED = "budget_released"
    BUDGET_CHARGED = "budget_charged"
    BUDGET_RESERVATION_DENIED = "budget_reservation_denied"
    BUDGET_LIMIT_REACHED = "budget_limit_reached"
    # -- company lifecycle ------------------------------------------------
    COMPANY_ACTIVATED = "company_activated"
    COMPANY_PAUSED = "company_paused"
    COMPANY_RESUMED = "company_resumed"
    # -- company tasks ----------------------------------------------------
    COMPANY_TASK_CREATED = "company_task_created"
    COMPANY_TASK_UPDATED = "company_task_updated"


class EventCategory(str, enum.Enum):
    """Filter buckets used by the audit view."""

    TASK = "task"
    COLLABORATION = "collaboration"
    SECURITY = "security"
    APPROVAL = "approval"
    #: Company, workforce, contract and budget governance (P0).
    GOVERNANCE = "governance"


#: Static metadata mirroring ``EVENT_DEFS`` in the frontend catalogue. Used for
#: category filtering server-side; presentation stays in the client.
EVENT_CATALOGUE: dict[EventType, EventCategory] = {
    EventType.ORDER_RECEIVED: EventCategory.TASK,
    EventType.PLAN_PROPOSED: EventCategory.TASK,
    EventType.PLAN_VALIDATED: EventCategory.TASK,
    EventType.TASK_ASSIGNED: EventCategory.TASK,
    EventType.TASK_STARTED: EventCategory.TASK,
    EventType.AWAITING_INFO: EventCategory.TASK,
    EventType.INFORMATION_PROVIDED: EventCategory.COLLABORATION,
    EventType.POLICY_DENIED: EventCategory.SECURITY,
    EventType.POLICY_VIOLATION: EventCategory.SECURITY,
    EventType.BLOCKED: EventCategory.SECURITY,
    EventType.ARTIFACT_CREATED: EventCategory.TASK,
    EventType.APPROVAL_REQUESTED: EventCategory.APPROVAL,
    EventType.APPROVED: EventCategory.APPROVAL,
    EventType.REJECTED: EventCategory.APPROVAL,
    EventType.TASK_COMPLETED: EventCategory.TASK,
    EventType.COST_METERED: EventCategory.TASK,
    EventType.AGENT_MESSAGE_SENT: EventCategory.COLLABORATION,
    EventType.AGENT_MESSAGE_RECEIVED: EventCategory.COLLABORATION,
    EventType.TASK_DELEGATED: EventCategory.COLLABORATION,
    EventType.TASK_ACCEPTED: EventCategory.COLLABORATION,
    EventType.TASK_HANDOFF: EventCategory.COLLABORATION,
    EventType.INFORMATION_REQUESTED: EventCategory.COLLABORATION,
    EventType.AGENT_QUESTION: EventCategory.SECURITY,
    EventType.AGENT_RESPONSE: EventCategory.COLLABORATION,
    EventType.APPROVAL_RESPONSE: EventCategory.APPROVAL,
    # Company / workforce
    EventType.COMPANY_CREATED: EventCategory.GOVERNANCE,
    EventType.COMPANY_UPDATED: EventCategory.GOVERNANCE,
    EventType.WORKFORCE_CONFIGURED: EventCategory.GOVERNANCE,
    EventType.RECOMMENDATION_GENERATED: EventCategory.GOVERNANCE,
    EventType.RECOMMENDATION_ACCEPTED: EventCategory.GOVERNANCE,
    EventType.CONTRACT_GENERATED: EventCategory.GOVERNANCE,
    EventType.CONTRACT_UPDATED: EventCategory.GOVERNANCE,
    EventType.CONTRACT_VERSION_CREATED: EventCategory.GOVERNANCE,
    EventType.CONTRACT_ACTIVATED: EventCategory.GOVERNANCE,
    EventType.CONTRACT_SUPERSEDED: EventCategory.GOVERNANCE,
    # Budget
    EventType.BUDGET_ADJUSTED: EventCategory.GOVERNANCE,
    EventType.BUDGET_RESERVED: EventCategory.GOVERNANCE,
    EventType.BUDGET_RELEASED: EventCategory.GOVERNANCE,
    EventType.BUDGET_CHARGED: EventCategory.GOVERNANCE,
    EventType.BUDGET_RESERVATION_DENIED: EventCategory.GOVERNANCE,
    EventType.BUDGET_LIMIT_REACHED: EventCategory.GOVERNANCE,
    # Lifecycle
    EventType.COMPANY_ACTIVATED: EventCategory.GOVERNANCE,
    EventType.COMPANY_PAUSED: EventCategory.GOVERNANCE,
    EventType.COMPANY_RESUMED: EventCategory.GOVERNANCE,
    # Company tasks
    EventType.COMPANY_TASK_CREATED: EventCategory.GOVERNANCE,
    EventType.COMPANY_TASK_UPDATED: EventCategory.GOVERNANCE,
}

#: External participants. They are senders, not agents: no seat, no mailbox,
#: no employee record.
EXTERNAL_SENDERS: dict[str, str] = {
    "ext:supplier": "External Supplier",
}

#: Prefix identifying a non-seat sender id.
EXTERNAL_PREFIX = "ext:"


def is_external_sender(sender_id: str) -> bool:
    return sender_id.startswith(EXTERNAL_PREFIX)


def category_of(event_type: str | EventType) -> EventCategory | None:
    try:
        return EVENT_CATALOGUE[EventType(event_type)]
    except ValueError:
        return None