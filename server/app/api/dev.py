"""Development-only helpers for proving the bridge end to end.

This module is **not registered when ``APP_ENV=production``**. It exists so a
developer can persist one new event server-side and watch it travel

    PostgreSQL -> EventService -> EventBus -> WebSocket -> frontend

without building a business write API. There is deliberately no public event
injection endpoint.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import Field
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.models import Event
from app.schemas.common import ApiCreate
from app.services.events import EventService

router = APIRouter(prefix="/api/dev", tags=["development"])


class DevEventIn(ApiCreate):
    """A minimal event to persist. Development use only."""

    type: str = Field(description="Event type from the KAYAN catalogue")
    actor_id: str | None = None
    task_id: str | None = None
    stream_id: str = "main"
    payload: dict[str, Any] = Field(default_factory=dict)


class DevEventOut(ApiCreate):
    """The persisted event, in the same shape the WebSocket sends."""

    id: str
    type: str
    sequence: int
    stream_id: str


@router.post(
    "/events",
    response_model=DevEventOut,
    summary="Publish one event (development only)",
)
def publish_dev_event(body: DevEventIn, session: DbSession) -> DevEventOut:
    """Persist one event and publish it.

    Persist-before-publish is preserved: the event is committed to PostgreSQL
    before it reaches the bus, so a client can never see an unrecorded event.
    """
    event = EventService(session).record(
        event_type=body.type,
        stream_id=body.stream_id,
        actor_id=body.actor_id,
        task_id=body.task_id,
        payload=body.payload,
    )
    return DevEventOut(id=event.id, type=event.event_type, sequence=event.sequence, stream_id=event.stream_id)


@router.get("/streams", summary="List event streams present in the database")
def list_streams(session: DbSession) -> dict[str, Any]:
    rows = session.execute(
        select(Event.stream_id, func.count(), func.max(Event.sequence))
        .group_by(Event.stream_id)
        .order_by(Event.stream_id)
    ).all()
    return {
        "streams": [
            {"streamId": r[0], "eventCount": int(r[1]), "lastSequence": int(r[2] or 0)} for r in rows
        ]
    }