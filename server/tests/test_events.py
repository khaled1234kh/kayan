"""Event persistence, structured payloads, and the persist-then-publish rule."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.events.bus import EventBus
from app.models import Event
from app.services import get_event_service
from app.services.events import EventService


def test_event_persists_with_structured_payload(session):
    service = get_event_service(session)
    event = service.record(
        event_type="policy_denied",
        stream_id="s-1",
        actor_id="operations",
        task_id="task-1",
        payload={
            "message": "TrustGate denied customer record access",
            "policyDecision": {
                "decision": "deny",
                "policy": "Untrusted Origin",
                "subject": "AI Operations",
                "action": "Read customer record",
                "resource": "customer/records",
                "reason": "Untrusted input cannot drive private data access",
            },
            "intent": {"agentId": "operations", "action": "customer_data.read"},
        },
    )
    stored = session.get(Event, event.id)
    assert stored.event_type == "policy_denied"
    # Structured, not a text log.
    assert stored.payload["policyDecision"]["policy"] == "Untrusted Origin"
    assert stored.payload["intent"]["action"] == "customer_data.read"
    assert stored.actor_id == "operations"
    assert isinstance(stored.payload, dict)


def test_event_not_published_when_persistence_fails(session):
    """publish() must never fire for an event that failed to commit."""
    bus = EventBus()
    published: list[dict] = []
    bus.subscribe(published.append)
    service = get_event_service(session)

    class Boom(RuntimeError):
        pass

    original_add = session.add

    def exploding_add(obj):
        if isinstance(obj, Event):
            raise Boom("insert rejected")
        return original_add(obj)

    session.add = exploding_add  # type: ignore[method-assign]
    try:
        with pytest.raises(Boom):
            EventService(session, bus).record(event_type="order_received", stream_id="s-1")
        session.rollback()
    finally:
        session.add = original_add  # type: ignore[method-assign]

    assert published == []


def test_publish_only_after_commit(session):
    """A subscriber must be able to read the event from the database."""
    bus = EventBus()
    observed: list[tuple[dict, bool]] = []

    def subscriber(wire: dict) -> None:
        # Same session: if persist-then-publish holds, the row is already here.
        observed.append((wire, session.get(Event, wire["id"]) is not None))

    bus.subscribe(subscriber)
    EventService(session, bus).record(event_type="order_received", stream_id="s-1")
    assert observed and all(persisted for _, persisted in observed)


def test_batch_publishes_after_whole_batch_commits(session):
    bus = EventBus()
    seen: list[dict] = []
    bus.subscribe(seen.append)
    service = EventService(session, bus)
    service.record_many(
        [
            {"event_type": "order_received"},
            {"event_type": "task_assigned"},
            {"event_type": "task_completed"},
        ],
        stream_id="s-batch",
    )
    assert [e["type"] for e in seen] == ["order_received", "task_assigned", "task_completed"]


def test_event_run_relationship(session):
    from app.models import Condition, WorkflowRun, WorkflowRunStatus

    run = WorkflowRun(
        id="run-1",
        request_id="req-1",
        order_id="1042",
        status=WorkflowRunStatus.RUNNING,
        run_index=1,
        condition=Condition.ENFORCED,
        seed="KAYAN-DEMO-1042",
        completed=False,
    )
    session.add(run)
    session.commit()

    get_event_service(session).record(event_type="order_received", stream_id="s-1", run_id="run-1")
    assert session.get(WorkflowRun, "run-1").event_count == 0  # not derived yet
    assert get_event_service(session).count_events(run_id="run-1") == 1


def test_duplicate_event_id_rejected(session):
    service = get_event_service(session)
    service.record(event_type="order_received", stream_id="s-1", event_id="evt-dup")
    with pytest.raises(IntegrityError):
        service.record(event_type="order_received", stream_id="s-1", event_id="evt-dup")
        session.commit()
    session.rollback()


def test_events_api_sorts_and_serialises(client, session):
    from app.db.seed import seed_demo_order

    seed_demo_order(session)
    body = client.get("/api/events", params={"stream_id": "main"}).json()
    sequences = [e["sequence"] for e in body]
    assert sequences == sorted(sequences)
    assert sequences == list(range(1, len(body) + 1))
    # camelCase frontend contract
    assert "actorId" in body[0]
    assert body[0]["type"] == "order_received"


def test_events_api_single_and_404(client, session):
    from app.db.seed import seed_demo_order

    seed_demo_order(session)
    one = client.get("/api/events/evt-1042-000").json()
    assert one["type"] == "order_received"
    assert client.get("/api/events/missing").status_code == 404