"""Agent queries."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Agent


class AgentService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_agents(self, *, active: bool | None = None, limit: int = 100, offset: int = 0) -> list[Agent]:
        stmt = select(Agent).order_by(Agent.id)
        if active is not None:
            stmt = stmt.where(Agent.active.is_(active))
        stmt = stmt.limit(limit).offset(offset)
        return list(self._session.execute(stmt).scalars())

    def get_agent(self, agent_id: str) -> Agent | None:
        return self._session.get(Agent, agent_id)

    def upsert_agent(self, agent: Agent) -> Agent:
        """Insert or update by id (seed idempotency)."""
        merged = self._session.merge(agent)
        self._session.commit()
        self._session.refresh(merged)
        return merged


def get_agent_service(session: Session) -> AgentService:
    return AgentService(session)