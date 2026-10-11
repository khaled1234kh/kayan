"""Deterministic event ordering.

Ordering must come from ``sequence``, not wall-clock time: a scripted run emits
many events inside the same millisecond.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.events.ordering import current_sequence, next_sequence
from app.services import get_event_service

BASE = datetime(2026, 3, 14, 9, 0, 0, tzinfo=timezone.utc)


def test_sequence_starts_at_one(session):
    assert current_sequence(session, "s-new") == 0
    assert next_sequence(session, "s-new") == 1


def test_sequence_increments_monotonically(session):
    service = get_event_service(session)
    kinds = ["order_received", "task_assigned", "task_started", "task_completed"]
    recorded = [
        service.record(event_type=kind, stream_id="s-1", publish=False) for kind in kinds
    ]
    assert [e.sequence for e in recorded] == [1, 2, 3, 4]


def test_identical_timestamps_still_order_deterministically(session):
    """Same timestamp for every event: ordering must still be total."""
    service = get_event_service(session)
    for index in range(8):
        service.record(
            event_type="cost_metered",
            stream_id="s-same",
            payload={"n": index},
            timestamp=BASE,
            publish=False,
        )
    events = service.list_events(stream_id="s-same")
    assert [e.sequence for e in events] == list(range(1, 9))
    # and the payload order matches insertion order
    assert [e.payload["n"] for e in events] == list(range(8))


def test_sequence_is_scoped_per_stream(session):
    service = get_event_service(session)
    a1 = service.record(event_type="order_received", stream_id="stream-a", publish=False)
    b1 = service.record(event_type="order_received", stream_id="stream-b", publish=False)
    a2 = service.record(event_type="task_assigned", stream_id="stream-a", publish=False)
    assert (a1.sequence, b1.sequence, a2.sequence) == (1, 1, 2)


def test_out_of_order_timestamps_do_not_break_order(session):
    """A late-arriving earlier timestamp must not reorder the stream."""
    service = get_event_service(session)
    first = service.record(event_type="order_received", stream_id="s-1", timestamp=BASE, publish=False)
    # Deliberately earlier wall-clock time, appended later.
    second = service.record(event_type="task_completed", stream_id="s-1", timestamp=BASE - timedelta(hours=1), publish=False)

    events = service.list_events(stream_id="s-1")
    assert [e.id for e in events] == [first.id, second.id]
    assert events[0].sequence < events[1].sequence
    # timestamps really are out of order, proving ordering came from sequence
    assert events[0].timestamp > events[1].timestamp


def test_duplicate_sequence_in_stream_rejected(session):
    service = get_event_service(session)
    service.record(event_type="order_received", stream_id="s-dup", publish=False)
    conflict = EventRow(event_type="task_assigned", stream_id="s-dup", sequence=1)
    session.add(conflict)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_replay_preserves_order_of_recorded_stream(session):
    service = get_event_service(session)
    script = [
        ("order_received", None),
        ("task_assigned", "manager"),
        ("agent_message_sent", "manager"),
        ("policy_denied", "operations"),
        ("blocked", "operations"),
        ("information_requested", "operations"),
        ("information_provided", "employee"),
        ("task_started", "sales"),
        ("task_completed", "sales"),
    ]
    service.record_many(
        [{"event_type": kind, "actor_id": actor} for kind, actor in script],
        stream_id="replay-1",
    )
    events = service.list_events(stream_id="replay-1")
    assert [e.event_type for e in events] == [kind for kind, _ in script]
    assert [e.sequence for e in events] == list(range(1, len(script) + 1))


def EventRow(**kwargs):  # noqa: N802 - tiny factory used by the conflict test
    from app.models import Event

    base = {
        "id": "evt-conflict",
        "stream_id": "s-dup",
        "sequence": 1,
        "timestamp": BASE,
        "payload": {},
    }
    base.update(kwargs)
    return Event(**base)