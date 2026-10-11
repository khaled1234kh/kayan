"""Handoff API contract."""

from __future__ import annotations

from datetime import datetime

from app.schemas.common import ApiSchema


class HandoffOut(ApiSchema):
    """Transfer of an objective between agents.

    ``status`` covers sent / accepted / completed / rejected.
    """

    id: str
    from_agent_id: str
    to_agent_id: str
    task_id: str
    objective: str
    context: dict = {}
    constraints: list[str] = []
    expected_output: str
    status: str
    source_message_id: str | None = None
    created_at: datetime
    updated_at: datetime