"""Message persistence, threading and external senders."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Message, MessageType
from app.services import get_message_service


def _message(**kwargs) -> Message:
    kwargs.setdefault("id", "msg-1")
    kwargs.setdefault("subject", "Order KAYAN-1042")
    kwargs.setdefault("type", MessageType.TASK)
    return Message(**kwargs)


def test_message_round_trip(seeded_session):
    get_message_service(seeded_session).add_message(
        _message(from_agent_id="manager", to_agent_id="sales", instructions="Draft it")
    )
    stored = seeded_session.get(Message, "msg-1")
    assert stored.from_agent_id == "manager"
    assert stored.to_agent_id == "sales"
    assert stored.instructions == "Draft it"


def test_external_sender_needs_no_agent_record(seeded_session):
    get_message_service(seeded_session).add_message(
        _message(id="msg-ext", from_agent_id=None, external_sender="ext:supplier", to_agent_id="employee")
    )
    stored = seeded_session.get(Message, "msg-ext")
    assert stored.external_sender == "ext:supplier"
    assert stored.from_agent_id is None


def test_message_requires_exactly_one_sender(seeded_session):
    """Both senders, or neither, is rejected by the database."""
    with pytest.raises(IntegrityError):
        get_message_service(seeded_session).add_message(
            _message(id="msg-both", from_agent_id="manager", external_sender="ext:supplier", to_agent_id="sales")
        )
        seeded_session.commit()


def test_message_threading_preserved(seeded_session):
    service = get_message_service(seeded_session)
    service.add_message(_message(id="msg-root", from_agent_id="manager", to_agent_id="sales"))
    service.add_message(
        _message(
            id="msg-reply",
            from_agent_id="sales",
            to_agent_id="manager",
            reply_to_message_id="msg-root",
            type=MessageType.RESPONSE,
        )
    )

    reply = service.get_message("msg-reply")
    assert reply.reply_to_message_id == "msg-root"
    assert [r.id for r in reply.reply_to.replies] == ["msg-reply"]

    thread = service.thread_of(reply)
    assert [m.id for m in thread] == ["msg-root", "msg-reply"]


def test_message_context_is_structured_json(seeded_session):
    get_message_service(seeded_session).add_message(
        _message(
            id="msg-ctx",
            from_agent_id="operations",
            to_agent_id="manager",
            context={"available": 12, "required": 40, "taskId": "task-1"},
        )
    )
    stored = seeded_session.get(Message, "msg-ctx")
    assert stored.context["available"] == 12
    assert stored.context["required"] == 40


def test_messages_api_serialisation(client, session):
    from app.db.seed import seed_demo_order

    seed_demo_order(session)
    body = client.get("/api/messages").json()
    by_id = {m["id"]: m for m in body}

    assert by_id["msg-supplier-instruction"]["externalSender"] == "ext:supplier"
    assert by_id["msg-supplier-instruction"]["fromAgentId"] is None
    assert by_id["msg-sales-to-manager"]["replyToMessageId"] == "msg-manager-to-sales"
    # camelCase contract, matching the frontend event shape
    assert "createdAt" in by_id["msg-manager-to-sales"]


def test_messages_api_filters(client, session):
    from app.db.seed import seed_demo_order

    seed_demo_order(session)
    external = client.get("/api/messages", params={"external_sender": "ext:supplier"}).json()
    assert [m["id"] for m in external] == ["msg-supplier-instruction"]

    to_sales = client.get("/api/messages", params={"to_agent_id": "sales"}).json()
    assert [m["id"] for m in to_sales] == ["msg-manager-to-sales"]