"""Event persistence and publication.

Architectural rule enforced here:

    event -> persist -> publish

:meth:`EventService.record` writes and **commits** the event before it is handed
to the event bus. If the commit fails, nothing is published, so a client can
never observe state the backend failed to record. Publishing is a side effect of
successful persistence, never a substitute for it.

Ordering is assigned by :mod:`app.events.ordering` inside the same transaction as
the insert, so the stream order is deterministic even when several events share a
timestamp.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.events.bus import EventBus, get_event_bus
from app.events.ordering import FIRST_SEQUENCE, current_sequence, next_sequence
from app.models import Event

logger = logging.getLogger(__name__)


def new_event_id() -> str:
    return f"evt_{uuid.uuid4().hex[:12]}"


class EventService:
    def __init__(self, session: Session, bus: EventBus | None = None) -> None:
        self._session = session
        self._bus = bus or get_event_bus()
        # Highest sequence handed out per stream *within this instance*. Staged
        # events are not yet in the database, so asking the database for the next
        # sequence twice in one transaction would hand out the same number twice and
        # violate ``uq_event_stream_sequence``. A lifecycle operation stages several
        # events at once, which is exactly when that happens.
        self._staged_high: dict[str, int] = {}

    # -- write path -------------------------------------------------------

    def _next_sequence(self, stream_id: str) -> int:
        """Next sequence for a stream, counting events already staged here."""
        if stream_id not in self._staged_high:
            self._staged_high[stream_id] = current_sequence(self._session, stream_id)
        self._staged_high[stream_id] += FIRST_SEQUENCE
        return self._staged_high[stream_id]

    def stage(
        self,
        *,
        event_type: str,
        stream_id: str,
        actor_id: str | None = None,
        target_id: str | None = None,
        task_id: str | None = None,
        run_id: str | None = None,
        payload: dict[str, Any] | None = None,
        event_id: str | None = None,
        timestamp: datetime | None = None,
        clock_offset_ms: int | None = None,
    ) -> Event:
        """Add an event to the current transaction without committing it.

        For changes where the state mutation and its audit event must land
        together: the caller stages the event alongside its domain writes, then
        calls :meth:`commit_and_publish`. If the commit fails, neither is
        persisted and nothing is published — the same guarantee ``record`` gives,
        extended across tables.

        The sequence is allocated here rather than by the caller so ordering
        cannot be bypassed.
        """
        event = Event(
            id=event_id or new_event_id(),
            event_type=event_type,
            sequence=self._next_sequence(stream_id),
            stream_id=stream_id,
            timestamp=timestamp or datetime.now(timezone.utc),
            actor_id=actor_id,
            target_id=target_id,
            task_id=task_id,
            run_id=run_id,
            payload=payload or {},
            clock_offset_ms=clock_offset_ms,
        )
        self._session.add(event)
        return event

    def commit_and_publish(self, events: Iterable[Event]) -> list[Event]:
        """Commit the staged events together with the caller's writes, then publish.

        Publication happens strictly after the commit, so a subscriber can never
        observe an event whose transaction was rolled back.
        """
        staged = list(events)
        self._session.commit()
        for event in staged:
            self._session.refresh(event)
        # The committed rows are now the truth; re-read rather than trust the cache.
        self._staged_high.clear()
        self.publish(staged)
        return staged

    def record(
        self,
        *,
        event_type: str,
        stream_id: str,
        actor_id: str | None = None,
        target_id: str | None = None,
        task_id: str | None = None,
        run_id: str | None = None,
        payload: dict[str, Any] | None = None,
        event_id: str | None = None,
        timestamp: datetime | None = None,
        clock_offset_ms: int | None = None,
        publish: bool = True,
    ) -> Event:
        """Persist one event, then publish it.

        The sequence is allocated here rather than by the caller so ordering
        cannot be bypassed.
        """
        event = self.stage(
            event_type=event_type,
            stream_id=stream_id,
            actor_id=actor_id,
            target_id=target_id,
            task_id=task_id,
            run_id=run_id,
            payload=payload,
            event_id=event_id,
            timestamp=timestamp,
            clock_offset_ms=clock_offset_ms,
        )
        # Durability first. A failure here propagates and nothing is published.
        self._session.commit()
        self._session.refresh(event)

        if publish:
            self.publish([event])
        return event

    def record_many(
        self,
        events: Iterable[dict[str, Any]],
        *,
        stream_id: str,
        run_id: str | None = None,
    ) -> list[Event]:
        """Persist a batch in order, publishing only after the whole batch commits.

        Used for replaying a recorded stream: clients must never see a partially
        imported run.
        """
        recorded: list[Event] = []
        for spec in events:
            recorded.append(
                self.record(
                    event_type=spec["event_type"],
                    stream_id=spec.get("stream_id") or stream_id,
                    actor_id=spec.get("actor_id"),
                    target_id=spec.get("target_id"),
                    task_id=spec.get("task_id"),
                    run_id=spec.get("run_id") or run_id,
                    payload=spec.get("payload") or {},
                    event_id=spec.get("id"),
                    timestamp=spec.get("timestamp"),
                    publish=False,
                )
            )
        self.publish(recorded)
        return recorded

    def publish(self, events: Iterable[Event]) -> None:
        """Fan out already-persisted events to subscribers.

        Subscribers are the WebSocket bridge, so they receive the client event
        shape (epoch-millisecond timestamps) rather than the REST shape.
        """
        for event in events:
            self._bus.publish(self.to_client_event(event))

    # -- read path --------------------------------------------------------

    @staticmethod
    def to_wire(event: Event) -> dict[str, Any]:
        """Serialise an event for the HTTP API (ISO-8601 timestamp)."""
        return {
            "id": event.id,
            "type": event.event_type,
            "sequence": event.sequence,
            "streamId": event.stream_id,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "actorId": event.actor_id,
            "targetId": event.target_id,
            "taskId": event.task_id,
            "runId": event.run_id,
            "clockOffsetMs": event.clock_offset_ms,
            "payload": event.payload or {},
        }

    @staticmethod
    def to_client_event(event: Event) -> dict[str, Any]:
        """Serialise an event for the WebSocket bridge.

        Matches the existing client event contract
        (``kayan-3d/src/types/events.ts``) exactly: ``timestamp`` is epoch
        milliseconds, not an ISO string, because the client does arithmetic on it.
        ``sequence`` and ``streamId`` are additive ordering fields used for
        deduplication and the resume cursor; nothing else is added, and protocol
        metadata never enters ``payload``.
        """
        timestamp = event.timestamp
        if timestamp is not None and timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return {
            "id": event.id,
            "type": event.event_type,
            "sequence": event.sequence,
            "streamId": event.stream_id,
            "timestamp": int(timestamp.timestamp() * 1000) if timestamp else 0,
            "actorId": event.actor_id,
            "taskId": event.task_id,
            "clockOffsetMs": event.clock_offset_ms,
            "payload": event.payload or {},
        }

    def list_events(
        self,
        *,
        stream_id: str | None = None,
        run_id: str | None = None,
        task_id: str | None = None,
        event_type: str | None = None,
        actor_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Event]:
        """Ordered by ``sequence`` within a stream — never by timestamp alone."""
        stmt = select(Event)
        if stream_id is not None:
            stmt = stmt.where(Event.stream_id == stream_id)
        if run_id is not None:
            stmt = stmt.where(Event.run_id == run_id)
        if task_id is not None:
            stmt = stmt.where(Event.task_id == task_id)
        if event_type is not None:
            stmt = stmt.where(Event.event_type == event_type)
        if actor_id is not None:
            stmt = stmt.where(Event.actor_id == actor_id)
        # Sequence is the ordering key; id breaks ties deterministically.
        stmt = stmt.order_by(Event.stream_id, Event.sequence, Event.id).limit(limit).offset(offset)
        return list(self._session.execute(stmt).scalars())

    def get_event(self, event_id: str) -> Event | None:
        return self._session.get(Event, event_id)

    def count_events(self, *, stream_id: str | None = None, run_id: str | None = None) -> int:
        stmt = select(func.count()).select_from(Event)
        if stream_id is not None:
            stmt = stmt.where(Event.stream_id == stream_id)
        if run_id is not None:
            stmt = stmt.where(Event.run_id == run_id)
        return int(self._session.execute(stmt).scalar_one() or 0)


def get_event_service(session: Session) -> EventService:
    return EventService(session)