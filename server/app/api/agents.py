"""Agent read endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession, not_found
from app.schemas import AgentOut
from app.services import get_agent_service

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentOut], summary="List agents")
def list_agents(session: DbSession, limit: int = 100, offset: int = 0) -> list[AgentOut]:
    agents = get_agent_service(session).list_agents(limit=limit, offset=offset)
    return [AgentOut.model_validate(agent) for agent in agents]


@router.get("/{agent_id}", response_model=AgentOut, summary="Get one agent")
def get_agent(agent_id: str, session: DbSession) -> AgentOut:
    agent = get_agent_service(session).get_agent(agent_id)
    if agent is None:
        raise not_found("Agent", agent_id)
    return AgentOut.model_validate(agent)