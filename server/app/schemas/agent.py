"""Agent API contract."""

from __future__ import annotations

from datetime import datetime

from app.schemas.common import ApiSchema


class AgentOut(ApiSchema):
    """A seated agent."""

    id: str
    name: str
    role: str
    kind: str
    objective: str | None = None
    capabilities: list[str] = []
    restrictions: list[str] = []
    active: bool = True
    created_at: datetime | None = None