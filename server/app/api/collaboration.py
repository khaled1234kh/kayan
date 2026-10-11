"""Message and handoff read endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession, not_found
from app.schemas import HandoffOut, MessageOut
from app.services import get_handoff_service, get_message_service

router = APIRouter(tags=["collaboration"])


# -- messages -----------------------------------------------------------


@router.get("/messages", response_model=list[MessageOut], summary="List messages")
def list_messages(
    session: DbSession,
    from_agent_id: str | None = None,
    to_agent_id: str | None = None,
    external_sender: str | None = None,
    task_id: str | None = None,
    type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[MessageOut]:
    messages = get_message_service(session).list_messages(
        from_agent_id=from_agent_id,
        to_agent_id=to_agent_id,
        external_sender=external_sender,
        task_id=task_id,
        type=type,
        limit=limit,
        offset=offset,
    )
    return [MessageOut.model_validate(message) for message in messages]


@router.get("/messages/{message_id}", response_model=MessageOut, summary="Get one message")
def get_message(message_id: str, session: DbSession) -> MessageOut:
    message = get_message_service(session).get_message(message_id)
    if message is None:
        raise not_found("Message", message_id)
    return MessageOut.model_validate(message)


# -- handoffs -----------------------------------------------------------


@router.get("/handoffs", response_model=list[HandoffOut], summary="List handoffs")
def list_handoffs(
    session: DbSession,
    from_agent_id: str | None = None,
    to_agent_id: str | None = None,
    task_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[HandoffOut]:
    handoffs = get_handoff_service(session).list_handoffs(
        from_agent_id=from_agent_id,
        to_agent_id=to_agent_id,
        task_id=task_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [HandoffOut.model_validate(handoff) for handoff in handoffs]


@router.get("/handoffs/{handoff_id}", response_model=HandoffOut, summary="Get one handoff")
def get_handoff(handoff_id: str, session: DbSession) -> HandoffOut:
    handoff = get_handoff_service(session).get_handoff(handoff_id)
    if handoff is None:
        raise not_found("Handoff", handoff_id)
    return HandoffOut.model_validate(handoff)