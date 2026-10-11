"""Handoff queries."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Handoff


class HandoffService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_handoffs(
        self,
        *,
        from_agent_id: str | None = None,
        to_agent_id: str | None = None,
        task_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Handoff]:
        stmt = (
            select(Handoff)
            .options(selectinload(Handoff.from_agent), selectinload(Handoff.to_agent))
            .order_by(Handoff.created_at, Handoff.id)
        )
        if from_agent_id is not None:
            stmt = stmt.where(Handoff.from_agent_id == from_agent_id)
        if to_agent_id is not None:
            stmt = stmt.where(Handoff.to_agent_id == to_agent_id)
        if task_id is not None:
            stmt = stmt.where(Handoff.task_id == task_id)
        if status is not None:
            stmt = stmt.where(Handoff.status == status)
        stmt = stmt.limit(limit).offset(offset)
        return list(self._session.execute(stmt).scalars())

    def get_handoff(self, handoff_id: str) -> Handoff | None:
        stmt = (
            select(Handoff)
            .options(
                selectinload(Handoff.from_agent),
                selectinload(Handoff.to_agent),
                selectinload(Handoff.source_message),
            )
            .where(Handoff.id == handoff_id)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def add_handoff(self, handoff: Handoff) -> Handoff:
        self._session.add(handoff)
        self._session.commit()
        self._session.refresh(handoff)
        return handoff

    def set_status(self, handoff: Handoff, status: str) -> Handoff:
        handoff.status = status
        self._session.commit()
        self._session.refresh(handoff)
        return handoff


def get_handoff_service(session: Session) -> HandoffService:
    return HandoffService(session)