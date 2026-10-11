"""Deterministic event sequence allocation.

The frontend reducer depends on an ordered stream, so ordering cannot rely on
wall-clock timestamps alone (identical millisecond timestamps are common in a
tight scripted run). Each stream gets a monotonically increasing ``sequence``,
allocated inside the same transaction as the insert.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Event

#: Sentinel returned for a stream with no events yet.
FIRST_SEQUENCE = 1


def current_sequence(session: Session, stream_id: str) -> int:
    """Highest sequence currently stored for ``stream_id`` (0 if none)."""
    stmt = select(func.max(Event.sequence)).where(Event.stream_id == stream_id)
    return int(session.execute(stmt).scalar_one() or 0)


def next_sequence(session: Session, stream_id: str) -> int:
    """Next sequence for ``stream_id``.

    The unique constraint ``uq_event_stream_sequence`` is the final arbiter: if
    two writers race, one insert fails rather than producing a duplicate order
    key.
    """
    return current_sequence(session, stream_id) + FIRST_SEQUENCE