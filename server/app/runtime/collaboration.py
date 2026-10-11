"""Agent collaboration, owned by the backend runtime.

This is the Python counterpart of the frontend ``MockAgentRuntime``: it decides
who talks to whom, what a handoff carries, and which events result. It knows
nothing about actor states, the reducer, Zustand or the 3D scene — it persists
domain facts and emits events, then stops.

Two rules hold here:

- every message and handoff is a **row** first, and the event payload is a
  projection of that row, so the client can rebuild collaboration state from the
  stream without inventing anything
- every event goes through ``EventService``, so persist -> commit -> publish
  ordering is preserved. No direct database writes from workflow code.

``payload.message`` stays the human headline and ``payload.agentMessage`` the
structured object; the two keys never collide.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.events.projection import handoff_to_wire, message_to_wire
from app.events.types import EXTERNAL_PREFIX, is_external_sender
from app.models import Handoff, HandoffStatus, Message, MessageType
from app.runtime.workflow import MESSAGE_EVENT
from app.security.trustgate import AgentIntent, PolicyDecision, authorize_intent, simulated_allow
from app.services.events import EventService


@dataclass
class RunContext:
    """Everything one execution needs to persist and emit."""

    run_id: str
    task_id: str
    order_id: str
    stream_id: str = "main"
    #: Short suffix so ids stay readable and unique across runs.
    short: str = ""
    #: Position on the workflow's virtual clock, advanced by the executor before
    #: each step. Every event this run emits uses it, so the whole stream shares
    #: one reproducible timeline.
    virtual_ms: int = 0
    message_count: int = 0
    handoff_count: int = 0
    intents: list[AgentIntent] = field(default_factory=list)
    denials: list[PolicyDecision] = field(default_factory=list)
    latest_message_id: str | None = None
    latest_handoff_id: str | None = None


class AgentCollaboration:
    """Message, handoff and intent creation for one run."""

    def __init__(self, session: Session, context: RunContext, mode: str = "enforced") -> None:
        self._session = session
        self._ctx = context
        #: 'enforced' consults TrustGate. 'baseline' is the experimental
        #: condition and may only *record* a simulated allow; it never changes
        #: what the workflow actually does or touches.
        self.mode = mode
        self.events = EventService(session)

    # -- identifiers -------------------------------------------------------

    def _next_message_id(self) -> str:
        self._ctx.message_count += 1
        return f"msg-{self._ctx.short}-{self._ctx.message_count:04d}"

    def _next_handoff_id(self) -> str:
        self._ctx.handoff_count += 1
        return f"hnd-{self._ctx.short}-{self._ctx.handoff_count:04d}"

    # -- emission ----------------------------------------------------------

    def _emit(
        self,
        event_type: str,
        actor_id: str | None,
        payload: dict[str, Any],
    ):
        # Real time for the feed; the logical offset for reproducible timing.
        return self.events.record(
            event_type=event_type,
            stream_id=self._ctx.stream_id,
            actor_id=actor_id,
            task_id=self._ctx.task_id,
            run_id=self._ctx.run_id,
            payload=payload,
            clock_offset_ms=self._ctx.virtual_ms,
        )

    # -- messages ----------------------------------------------------------

    def send_message(self, draft: dict[str, Any]) -> Message:
        """Persist a typed message, then emit the transport and semantic events.

        An external sender (``ext:supplier``) is stored as a sender string, never
        as an employee record.
        """
        from_agent_id = draft.get("fromAgentId")
        external = is_external_sender(from_agent_id) if isinstance(from_agent_id, str) else False
        context = dict(draft.get("context") or {})
        headline = context.get("message")

        message = Message(
            id=self._next_message_id(),
            from_agent_id=None if external else from_agent_id,
            external_sender=from_agent_id if external else None,
            to_agent_id=draft["toAgentId"],
            type=MessageType(draft["type"]),
            subject=draft["subject"],
            instructions=draft.get("instructions"),
            context=context,
            expected_output=draft.get("expectedOutput"),
            reply_to_message_id=draft.get("replyToMessageId"),
            task_id=context.get("taskId") or self._ctx.task_id,
            delivered=False,
        )
        self._session.add(message)
        # Commit before emitting: the event must never describe an unstored row.
        self._session.commit()
        self._session.refresh(message)

        wire = message_to_wire(message)
        self._ctx.latest_message_id = message.id

        # Transport event, then the semantic event for the message type.
        self._emit("agent_message_sent", message.external_sender or message.from_agent_id, {
            "message": headline,
            "agentMessage": wire,
        })
        self._emit(
            MESSAGE_EVENT[message.type.value],
            message.external_sender or message.from_agent_id,
            {**context, "agentMessage": wire},
        )
        return message

    def receive_message(self, message_id: str | None = None) -> None:
        """Mark a message delivered and record it. Defaults to the latest one."""
        target = message_id or self._ctx.latest_message_id
        if not target:
            return
        message = self._session.get(Message, target)
        if message is None or message.delivered:
            return
        message.delivered = True
        self._session.commit()
        self._ctx.latest_message_id = message.id
        self._emit("agent_message_received", message.to_agent_id, {"messageId": message.id})

    # -- handoffs ----------------------------------------------------------

    def create_handoff(self, draft: dict[str, Any]) -> Handoff:
        """Transfer an objective: handoff row, carrying message, delegation event."""
        handoff = Handoff(
            id=self._next_handoff_id(),
            from_agent_id=draft["fromAgentId"],
            to_agent_id=draft["toAgentId"],
            task_id=draft.get("taskId") or self._ctx.task_id,
            objective=draft["objective"],
            context=dict(draft.get("context") or {}),
            constraints=list(draft.get("constraints") or []),
            expected_output=draft["expectedOutput"],
            status=HandoffStatus.SENT,
            source_message_id=None,
        )
        self._session.add(handoff)
        self._session.commit()
        self._session.refresh(handoff)
        self._ctx.latest_handoff_id = handoff.id

        # The message that carries the handoff, exactly as the frontend runtime does.
        message = self.send_message(
            {
                "fromAgentId": handoff.from_agent_id,
                "toAgentId": handoff.to_agent_id,
                "type": "handoff",
                "subject": handoff.objective,
                "instructions": " ".join(handoff.constraints),
                "context": {
                    "handoffId": handoff.id,
                    "taskId": handoff.task_id,
                    "expectedOutput": handoff.expected_output,
                    **handoff.context,
                },
                "expectedOutput": handoff.expected_output,
            }
        )
        handoff.source_message_id = message.id
        self._session.commit()

        self._emit(
            "task_delegated",
            handoff.from_agent_id,
            {"handoff": handoff_to_wire(handoff), "taskId": handoff.task_id},
        )
        return handoff

    def accept_handoff(self) -> Handoff | None:
        if not self._ctx.latest_handoff_id:
            return None
        handoff = self._session.get(Handoff, self._ctx.latest_handoff_id)
        if handoff is None:
            return None
        handoff.status = HandoffStatus.ACCEPTED
        self._session.commit()
        self._session.refresh(handoff)
        self._emit(
            "task_accepted",
            handoff.to_agent_id,
            {"handoff": handoff_to_wire(handoff), "taskId": handoff.task_id},
        )
        return handoff

    def complete_handoff(self) -> Handoff | None:
        """Close the handoff and emit the handoff-level completion event."""
        if not self._ctx.latest_handoff_id:
            return None
        handoff = self._session.get(Handoff, self._ctx.latest_handoff_id)
        if handoff is None:
            return None
        handoff.status = HandoffStatus.COMPLETED
        self._session.commit()
        self._session.refresh(handoff)
        self._emit(
            "task_completed",
            handoff.to_agent_id,
            {"handoff": handoff_to_wire(handoff), "message": "Quotation handed back to the manager"},
        )
        return handoff

    # -- intents and TrustGate ---------------------------------------------

    def authorize(self, intent: AgentIntent) -> PolicyDecision:
        """Submit an intent to the authoritative backend TrustGate.

        The runtime forms the intent; the gate alone decides. It never evaluates
        policy itself and never assumes the outcome.

        Under the baseline condition the gate is replaced by a *simulated* allow
        for this experimental run only, so the difference between conditions is
        observable. Nothing is accessed either way.
        """
        self._ctx.intents.append(intent)
        if self.mode == "baseline":
            decision = simulated_allow(intent)
        else:
            decision = authorize_intent(intent)
        if not decision.allowed:
            self._ctx.denials.append(decision)
        return decision

    def emit_intent_outcome(
        self,
        intent: AgentIntent,
        decision: PolicyDecision,
        *,
        allowed: dict[str, str],
        denied_message: str,
        denied_follow_up: dict[str, str] | None = None,
    ) -> list[str]:
        """Emit the events that report the gate's verdict. Returns the event types."""
        emitted: list[str] = []
        intent_payload = intent.to_payload()
        decision_payload = decision.to_payload()
        actor = intent.agent_id

        if decision.allowed:
            if self.mode == "baseline" and denied_follow_up is not None:
                # This step is the one enforced mode would have denied. Record
                # that it was permitted in the experimental model, without
                # performing it. No denial and no block are emitted.
                self._emit("policy_violation", actor, {
                    "message": "Unauthorized action simulated as allowed (enforcement disabled)",
                    "policyDecision": decision_payload,
                    "intent": intent_payload,
                })
                emitted.append("policy_violation")
            self._emit(allowed["type"], actor, {
                "message": allowed["message"],
                "policyDecision": decision_payload,
            })
            emitted.append(allowed["type"])
            return emitted

        self._emit("policy_denied", actor, {
            "message": denied_message,
            "policyDecision": decision_payload,
            "intent": intent_payload,
        })
        emitted.append("policy_denied")

        if denied_follow_up:
            self._emit(denied_follow_up["type"], actor, {"message": denied_follow_up["message"]})
            emitted.append(denied_follow_up["type"])
        return emitted

    # -- plain events ------------------------------------------------------

    def emit_event(self, event_type: str, actor_id: str | None, payload: dict[str, Any]):
        return self._emit(event_type, actor_id, payload)

    def handoff_wire(self, handoff: Any) -> dict[str, Any]:
        """Wire projection of a handoff, for events the session emits."""
        return handoff_to_wire(handoff)
