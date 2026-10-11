"""Task API contract."""

from __future__ import annotations

from datetime import datetime

from app.schemas.common import ApiSchema


class TaskOut(ApiSchema):
    """A unit of work."""

    id: str
    title: str
    objective: str | None = None
    status: str
    assigned_agent_id: str | None = None
    #: Supports Manager -> subordinate delegation chains.
    parent_task_id: str | None = None
    #: Defaults are applied at flush time, so an unsaved instance has no value yet.
    created_at: datetime | None = None
    updated_at: datetime | None = None