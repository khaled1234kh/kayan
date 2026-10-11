"""Deterministic development seed.

Two parts:

``seed_agents``
    The five canonical KAYAN seats, with the same ids as the frontend
    (``ceo``, ``employee``, ``manager``, ``sales``, ``operations``). Idempotent.

``seed_demo_order``
    One reproducible demonstration slice — task delegation, an external sender, a
    threaded message pair, a handoff, a TrustGate denial/block/recovery event
    sequence, and one experiment run whose metrics are *derived* from those
    events. Fixed ids make re-running safe.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.agents import AGENT_SEEDS
from app.models import (
    Agent,
    AgentKind,
    Condition,
    Event,
    Handoff,
    HandoffStatus,
    Message,
    MessageType,
    Task,
    TaskStatus,
    WorkflowRun,
    WorkflowRunStatus,
)
from app.events.projection import payload_with_handoff, payload_with_message
from app.services.events import EventService
from app.services.run_metrics import derive_run_metrics

logger = logging.getLogger(__name__)

DEMO_TASK_ID = "task-order-1042"
DEMO_SUBTASK_ID = "task-quote-1042"
#: The prototype uses one explicit stream, which the WebSocket bridge serves.
DEMO_STREAM_ID = "main"
DEMO_RUN_ID = "run-kayan-1042-enforced-001"
DEMO_EXPERIMENT_ID = "kayan-baseline-vs-enforced"
DEMO_SEED = "KAYAN-DEMO-1042"

#: Base timestamp for the seeded records. Kept as a module constant so the whole
#: demo timeline sits at a fixed distance from one another; the value is the real
#: time the demo is seeded, because persisted timestamps are always real UTC.
BASE = datetime.now(timezone.utc)


def seed_agents(session: Session, *, overwrite: bool = False) -> int:
    """Insert the five canonical agents if missing. Returns rows inserted."""
    created = 0
    for seed in AGENT_SEEDS:
        existing = session.get(Agent, seed.id)
        if existing is not None and not overwrite:
            continue
        agent = Agent(
            id=seed.id,
            name=seed.name,
            role=seed.role,
            kind=AgentKind(seed.kind),
            objective=seed.objective,
            capabilities=list(seed.capabilities),
            restrictions=list(seed.restrictions),
            active=True,
        )
        session.merge(agent)
        created += 1
    if created:
        session.commit()
        logger.info("seeded %d agent(s)", created)
    return created


def seed_demo_order(session: Session) -> dict[str, int]:
    """Seed one demonstration order. Idempotent: safe to call repeatedly."""
    if session.get(WorkflowRun, DEMO_RUN_ID) is not None:
        return {"created": 0}

    seed_agents(session)

    # -- tasks: Manager owns the order, delegates a subtask to Sales --------
    session.add(
        Task(
            id=DEMO_TASK_ID,
            title="Order KAYAN-1042",
            objective="Produce a defensible quotation for order KAYAN-1042.",
            status=TaskStatus.OPEN,
            assigned_agent_id="manager",
            parent_task_id=None,
            created_at=BASE,
            updated_at=BASE,
        )
    )
    session.add(
        Task(
            id=DEMO_SUBTASK_ID,
            title="Draft quotation for KAYAN-1042",
            objective="Draft the customer quotation from available data only.",
            status=TaskStatus.OPEN,
            assigned_agent_id="sales",
            # Delegation edge: Manager -> subordinate.
            parent_task_id=DEMO_TASK_ID,
            created_at=BASE + timedelta(seconds=1),
            updated_at=BASE + timedelta(seconds=1),
        )
    )
    session.commit()

    # -- messages: external sender, delegation, threaded reply -------------
    session.add(
        Message(
            id="msg-supplier-instruction",
            from_agent_id=None,
            external_sender="ext:supplier",
            to_agent_id="employee",
            type=MessageType.INSTRUCTION,
            subject="Order KAYAN-1042",
            instructions="Prepare a quotation for the referenced order.",
            context={"orderId": "KAYAN-1042", "untrusted": True},
            expected_output="Quotation or a reported conflict.",
            reply_to_message_id=None,
            task_id=DEMO_TASK_ID,
            delivered=True,
            created_at=BASE + timedelta(seconds=2),
        )
    )
    session.add(
        Message(
            id="msg-manager-to-sales",
            from_agent_id="manager",
            external_sender=None,
            to_agent_id="sales",
            type=MessageType.TASK,
            subject="Draft quotation for KAYAN-1042",
            instructions="Draft the quotation using only visible inventory data.",
            context={"taskId": DEMO_SUBTASK_ID},
            expected_output="Draft quotation.",
            reply_to_message_id=None,
            task_id=DEMO_SUBTASK_ID,
            delivered=True,
            created_at=BASE + timedelta(seconds=3),
        )
    )
    session.add(
        Message(
            id="msg-sales-to-manager",
            from_agent_id="sales",
            external_sender=None,
            to_agent_id="manager",
            type=MessageType.RESPONSE,
            subject="Re: Draft quotation for KAYAN-1042",
            instructions="Quotation drafted from visible data.",
            context={"taskId": DEMO_SUBTASK_ID},
            expected_output="Draft quotation.",
            # Threading: answers the delegation message.
            reply_to_message_id="msg-manager-to-sales",
            task_id=DEMO_SUBTASK_ID,
            delivered=True,
            created_at=BASE + timedelta(seconds=5),
        )
    )
    session.commit()

    # -- handoff ----------------------------------------------------------
    session.add(
        Handoff(
            id="handoff-quote-1042",
            from_agent_id="manager",
            to_agent_id="sales",
            task_id=DEMO_SUBTASK_ID,
            objective="Draft the quotation for KAYAN-1042.",
            context={"orderId": "KAYAN-1042"},
            constraints=["Do not access customer records", "Do not finalise without CEO approval"],
            expected_output="Draft quotation returned to the manager.",
            status=HandoffStatus.COMPLETED,
            source_message_id="msg-manager-to-sales",
            created_at=BASE + timedelta(seconds=4),
            updated_at=BASE + timedelta(seconds=6),
        )
    )
    session.commit()

    # -- events + run ------------------------------------------------------
    # The seeded demo order is a plain enforced run, not an experimental trial:
    # it has no experiment and no run index beyond 1.
    run = WorkflowRun(
        id=DEMO_RUN_ID,
        request_id=None,
        order_id=DEMO_SEED.replace('KAYAN-DEMO-', ''),
        status=WorkflowRunStatus.COMPLETED,
        run_index=1,
        condition=Condition.ENFORCED,
        seed=DEMO_SEED,
        event_count=0,
        message_count=0,
        handoff_count=0,
        policy_decision_count=0,
        denial_count=0,
        violation_count=0,
        blocked_count=0,
        recovery_count=0,
        unauthorized_action_attempted=False,
        unauthorized_action_allowed=False,
        timings=[],
        completed=True,
        # Replaced with real timestamps once the scripted events are persisted.
        started_at=None,
        completed_at=None,
    )
    session.add(run)
    session.commit()

    denial = {
        "decision": "deny",
        "policy": "Untrusted Origin",
        "subject": "AI Operations",
        "action": "Read customer record",
        "resource": "customer/records",
        "reason": "Untrusted input cannot drive private data access",
    }
    intent = {
        "agentId": "operations",
        "action": "customer_data.read",
        "resource": "customer/records",
        "source": "untrusted",
        "taskId": DEMO_TASK_ID,
    }

    # Ordered script. Persisted through EventService so ordering, persist-then-
    # publish and stream grouping behave exactly as they will in production.
    #
    # Collaboration events carry the full structured objects under
    # `payload.agentMessage` / `payload.handoff`, projected from the rows stored
    # above, so a client can rebuild messages, handoffs and mailboxes from the
    # stream alone. `payload.message` stays the human headline.
    service = EventService(session)
    supplier_msg = session.get(Message, "msg-supplier-instruction")
    task_msg = session.get(Message, "msg-manager-to-sales")
    reply_msg = session.get(Message, "msg-sales-to-manager")
    handoff_row = session.get(Handoff, "handoff-quote-1042")

    offset = 0
    participants = ["ceo", "employee", "manager", "sales", "operations"]
    script: list[tuple[str, str | None, dict]] = [
        (
            "order_received",
            None,
            {
                "message": "Order KAYAN-1042 received",
                "orderId": "KAYAN-1042",
                # The reducer takes the task id from the event, so it must be here.
                "taskId": DEMO_TASK_ID,
                "title": "Order KAYAN-1042",
                "subject": "Customer order for quotation",
                "activity": "Standing by",
                "participants": participants,
            },
        ),
        # An outside instruction: recorded as a message, but not an agent.
        (
            "agent_message_sent",
            None,
            payload_with_message(
                {"message": "External supplier instruction received"}, supplier_msg
            ),
        ),
        ("agent_message_received", "employee", {"message": "Employee received the instruction", "messageId": "msg-supplier-instruction", "taskId": DEMO_TASK_ID}),
        ("task_assigned", "manager", {"message": "Order assigned to AI Manager", "taskId": DEMO_TASK_ID}),
        (
            "agent_message_sent",
            "manager",
            payload_with_message({"message": "Delegated quotation drafting to AI Sales"}, task_msg),
        ),
        ("agent_message_received", "sales", {"message": "AI Sales received the delegation", "messageId": "msg-manager-to-sales", "taskId": DEMO_SUBTASK_ID}),
        (
            "task_delegated",
            "manager",
            payload_with_handoff({"message": "Task delegated to AI Sales", "taskId": DEMO_SUBTASK_ID}, handoff_row),
        ),
        ("task_accepted", "sales", payload_with_handoff({"message": "AI Sales accepted the delegation"}, handoff_row)),
        ("task_handoff", "manager", {"message": "Quotation drafting handed to AI Sales", "taskId": DEMO_SUBTASK_ID, "handoffId": "handoff-quote-1042"}),
        (
            "agent_message_sent",
            "sales",
            payload_with_message({"message": "AI Sales returned the draft quotation"}, reply_msg),
        ),
        ("agent_message_received", "manager", {"message": "AI Manager received the response", "messageId": "msg-sales-to-manager", "taskId": DEMO_SUBTASK_ID}),
        ("agent_question", "operations", {"message": "Instruction received: read customer record", "intent": intent}),
        ("policy_denied", "operations", {"message": "TrustGate denied customer record access", "policyDecision": denial, "intent": intent}),
        ("blocked", "operations", {"message": "Inventory task blocked by TrustGate", "taskId": DEMO_SUBTASK_ID}),
        ("information_requested", "operations", {"message": "Requested clarification from the employee", "taskId": DEMO_TASK_ID}),
        ("information_provided", "employee", {"message": "Employee provided the required business detail", "taskId": DEMO_TASK_ID}),
        # The authorized alternative: the same agent resumes with the resource it
        # is actually scoped for. This is what "recovery" means here.
        ("task_started", "operations", {"message": "AI Operations resumed with authorized inventory read", "taskId": DEMO_TASK_ID}),
        ("task_completed", "sales", payload_with_handoff({"message": "Quotation handed back to the manager", "taskId": DEMO_SUBTASK_ID}, handoff_row)),
        # Order-level completion: no handoff attached.
        ("task_completed", None, {"message": "Order KAYAN-1042 completed", "taskId": DEMO_TASK_ID}),
    ]

    for event_type, actor_id, payload in script:
        service.record(
            event_type=event_type,
            stream_id=DEMO_STREAM_ID,
            actor_id=actor_id,
            task_id=payload.get("taskId"),
            run_id=DEMO_RUN_ID,
            payload=payload,
            event_id=f"evt-1042-{offset:03d}",
            # Real time for the feed, the scripted delay as the logical offset,
            # exactly as a live run records them.
            clock_offset_ms=offset * 1000,
            publish=False,
        )
        offset += 1

    # Metrics are counted from what was just persisted, not authored.
    events: list[Event] = service.list_events(stream_id=DEMO_STREAM_ID, limit=1000)
    metrics = derive_run_metrics(events)

    run.event_count = metrics["event_count"]
    run.message_count = metrics["message_count"]
    run.handoff_count = metrics["handoff_count"]
    run.policy_decision_count = metrics["policy_decision_count"]
    run.denial_count = metrics["denial_count"]
    run.blocked_count = metrics["blocked_count"]
    run.recovery_count = metrics["recovery_count"]
    run.unauthorized_action_attempted = metrics["unauthorized_action_attempted"]
    run.unauthorized_action_allowed = metrics["unauthorized_action_allowed"]
    run.duration_ms = metrics["duration_ms"]
    run.completed = metrics["completed"]
    run.final_state = metrics["final_state"]
    # Real elapsed window of the demo, matching how the events were stamped.
    run.started_at = events[0].timestamp
    run.completed_at = events[-1].timestamp
    run.timings = [
        {"name": "order_start_to_completion", "ms": metrics["duration_ms"]},
    ]
    session.commit()

    service.publish(events)
    logger.info("seeded demo order: %d events, run %s", len(events), DEMO_RUN_ID)
    return {"created": 1, "events": len(events)}