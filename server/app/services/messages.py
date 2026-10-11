"""Message queries, including threading."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Message


class MessageService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_messages(
        self,
        *,
        from_agent_id: str | None = None,
        to_agent_id: str | None = None,
        external_sender: str | None = None,
        task_id: str | None = None,
        type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Message]:
        stmt = select(Message).options(selectinload(Message.from_agent)).order_by(
            Message.created_at, Message.id
        )
        if from_agent_id is not None:
            stmt = stmt.where(Message.from_agent_id == from_agent_id)
        if to_agent_id is not None:
            stmt = stmt.where(Message.to_agent_id == to_agent_id)
        if external_sender is not None:
            stmt = stmt.where(Message.external_sender == external_sender)
        if task_id is not None:
            stmt = stmt.where(Message.task_id == task_id)
        if type is not None:
            stmt = stmt.where(Message.type == type)
        stmt = stmt.limit(limit).offset(offset)
        return list(self._session.execute(stmt).scalars())

    def get_message(self, message_id: str) -> Message | None:
        stmt = (
            select(Message)
            .options(selectinload(Message.reply_to), selectinload(Message.replies))
            .where(Message.id == message_id)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def add_message(self, message: Message) -> Message:
        self._session.add(message)
        self._session.commit()
        self._session.refresh(message)
        return message

    def thread_of(self, message: Message) -> list[Message]:
        """Walk up a reply chain, oldest first.

        Threading is preserved by ``reply_to_message_id``; the walk is bounded so
        a malformed cycle cannot hang a request.
        """
        chain: list[Message] = []
        current: Message | None = message
        while current is not None and len(chain) < 100:
            chain.append(current)
            current = current.reply_to
        chain.reverse()
        return chain


def get_message_service(session: Session) -> MessageService:
    return MessageService(session)