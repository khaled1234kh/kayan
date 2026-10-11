"""Event read endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession, not_found
from app.schemas import EventOut
from app.services import get_event_service

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventOut], summary="List events")
def list_events(
    session: DbSession,
    stream_id: str | None = None,
    run_id: str | None = None,
    task_id: str | None = None,
    event_type: str | None = None,
    actor_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[EventOut]:
    """Events ordered by ``sequence`` within a stream."""
    events = get_event_service(session).list_events(
        stream_id=stream_id,
        run_id=run_id,
        task_id=task_id,
        event_type=event_type,
        actor_id=actor_id,
        limit=limit,
        offset=offset,
    )
    return [EventOut.model_validate(event) for event in events]


@router.get("/{event_id}", response_model=EventOut, summary="Get one event")
def get_event(event_id: str, session: DbSession) -> EventOut:
    event = get_event_service(session).get_event(event_id)
    if event is None:
        raise not_found("Event", event_id)
    return EventOut.model_validate(event)