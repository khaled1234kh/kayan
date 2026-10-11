"""Wire projections for events.

The database stores messages and handoffs in its own column names
(``to_agent_id``, ``expected_output``, ...). The frontend event contract expects
the camelCase object shapes defined in ``kayan-3d/src/agents/agentMessages.ts`` and
``kayan-3d/src/agents/handoffs.ts``, and the existing reducer reads them from the
event payload under ``agentMessage`` / ``handoff``.

These functions are the single adapter between the two. They are not a second
event model: they project one stored row into the one shape the client already
understands, so the reducer needs no adapter of its own.

Payload conventions preserved here:

- ``payload.message``  — human-readable feed headline (string)
- ``payload.agentMessage`` — the structured message object
- ``payload.handoff``  — the structured handoff object

The headline and the object are never collapsed into each other.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.events.types import EXTERNAL_PREFIX


def epoch_ms(value: datetime | None) -> int:
    """Datetime -> epoch milliseconds, the frontend's timestamp unit."""
    if value is None:
        return 0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1000)


def message_to_wire(message: Any) -> dict[str, Any]:
    """Project a persisted ``Message`` row into the frontend ``AgentMessage`` shape.

    An external sender (``ext:supplier``) is reported as the sender id so the
    transcript can label it, while keeping the fact that it is not a seated
    agent.
    """
    return {
        "id": message.id,
        "fromAgentId": message.external_sender or message.from_agent_id,
        "toAgentId": message.to_agent_id,
        "type": message.type,
        "subject": message.subject,
        "instructions": message.instructions,
        "context": message.context or {},
        "expectedOutput": message.expected_output,
        "replyToMessageId": message.reply_to_message_id,
        "timestamp": epoch_ms(message.created_at),
        "delivered": bool(message.delivered),
        # Informational: lets a client distinguish an outside sender from a seat
        # without maintaining its own external-sender table.
        "external": bool(message.external_sender)
        or str(message.external_sender or message.from_agent_id or "").startswith(EXTERNAL_PREFIX),
    }


def handoff_to_wire(handoff: Any) -> dict[str, Any]:
    """Project a persisted ``Handoff`` row into the frontend ``AgentHandoff`` shape."""
    return {
        "id": handoff.id,
        "fromAgentId": handoff.from_agent_id,
        "toAgentId": handoff.to_agent_id,
        "taskId": handoff.task_id,
        "objective": handoff.objective,
        "context": handoff.context or {},
        "constraints": handoff.constraints or [],
        "expectedOutput": handoff.expected_output,
        "status": handoff.status,
        "sourceMessageId": handoff.source_message_id,
        "timestamp": epoch_ms(handoff.created_at),
    }


def payload_with_message(payload: dict[str, Any], message: Any) -> dict[str, Any]:
    """Attach a structured message to an event payload, keeping the headline."""
    enriched = dict(payload)
    enriched["agentMessage"] = message_to_wire(message)
    return enriched


def payload_with_handoff(payload: dict[str, Any], handoff: Any) -> dict[str, Any]:
    """Attach a structured handoff to an event payload, keeping the headline."""
    enriched = dict(payload)
    enriched["handoff"] = handoff_to_wire(handoff)
    return enriched