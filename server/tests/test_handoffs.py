"""Handoff persistence and lifecycle."""

from __future__ import annotations

from app.models import Handoff, HandoffStatus, Message, MessageType, Task
from app.services import get_handoff_service, get_message_service, get_task_service


def _seed_context(session):
    from app.db.seed import seed_agents

    seed_agents(session)
    get_task_service(session).add_task(
        Task(id="task-1", title="Order", assigned_agent_id="manager")
    )
    get_message_service(session).add_message(
        Message(
            id="msg-1",
            from_agent_id="manager",
            to_agent_id="sales",
            subject="Draft quotation",
            type=MessageType.TASK,
            task_id="task-1",
        )
    )


def test_handoff_round_trip(seeded_session):
    _seed_context(seeded_session)
    get_handoff_service(seeded_session).add_handoff(
        Handoff(
            id="h-1",
            from_agent_id="manager",
            to_agent_id="sales",
            task_id="task-1",
            objective="Draft the quotation.",
            context={"orderId": "KAYAN-1042"},
            constraints=["Do not access customer records"],
            expected_output="Draft quotation.",
            status=HandoffStatus.SENT,
            source_message_id="msg-1",
        )
    )
    stored = seeded_session.get(Handoff, "h-1")
    assert stored.from_agent.id == "manager"
    assert stored.to_agent.id == "sales"
    assert stored.constraints == ["Do not access customer records"]
    assert stored.source_message_id == "msg-1"


def test_handoff_relationship_to_task_and_message(seeded_session):
    _seed_context(seeded_session)
    get_handoff_service(seeded_session).add_handoff(
        Handoff(
            id="h-1",
            from_agent_id="manager",
            to_agent_id="sales",
            task_id="task-1",
            objective="Draft the quotation.",
            expected_output="Draft quotation.",
            source_message_id="msg-1",
        )
    )
    handoff = get_handoff_service(seeded_session).get_handoff("h-1")
    assert handoff.task_id == "task-1"
    assert handoff.source_message.subject == "Draft quotation"


def test_handoff_status_lifecycle(seeded_session):
    _seed_context(seeded_session)
    service = get_handoff_service(seeded_session)
    handoff = service.add_handoff(
        Handoff(
            id="h-1",
            from_agent_id="manager",
            to_agent_id="sales",
            task_id="task-1",
            objective="Draft the quotation.",
            expected_output="Draft quotation.",
            status=HandoffStatus.SENT,
        )
    )
    for status in (HandoffStatus.ACCEPTED, HandoffStatus.COMPLETED):
        service.set_status(handoff, status)
        assert seeded_session.get(Handoff, "h-1").status == status


def test_handoff_rejection_is_representable(seeded_session):
    _seed_context(seeded_session)
    service = get_handoff_service(seeded_session)
    handoff = service.add_handoff(
        Handoff(
            id="h-2",
            from_agent_id="sales",
            to_agent_id="operations",
            task_id="task-1",
            objective="Check stock.",
            expected_output="Availability.",
            status=HandoffStatus.REJECTED,
        )
    )
    assert handoff.status == HandoffStatus.REJECTED


def test_handoffs_api(client, session):
    from app.db.seed import seed_demo_order

    seed_demo_order(session)
    body = client.get("/api/handoffs").json()
    assert len(body) == 1
    handoff = body[0]
    assert handoff["id"] == "handoff-quote-1042"
    assert handoff["status"] == "completed"
    assert handoff["sourceMessageId"] == "msg-manager-to-sales"
    assert handoff["fromAgentId"] == "manager"
    assert handoff["toAgentId"] == "sales"