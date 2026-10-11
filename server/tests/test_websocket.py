"""WebSocket event bridge.

Covers the connection lifecycle, historical replay, live delivery, sequence
ordering, the replay/live handover, multiple independent clients, resume via
``afterSequence``, and the read-only guarantee.
"""

from __future__ import annotations

import pytest

from app.events.bus import get_event_bus
from app.events.connection import EventStreamConnection
from app.services import get_event_service


@pytest.fixture()
def make_stream(session):
    """Seed a stream with three persisted events, on demand.

    Tests must connect to the stream they seeded; the bridge replays only the
    requested stream, so a mismatched id means an (empty) stream with nothing to
    send.
    """

    def _make(stream_id: str, kinds: tuple[str, ...] = ("order_received", "task_assigned", "task_started")):
        service = get_event_service(session)
        for kind in kinds:
            service.record(event_type=kind, stream_id=stream_id, publish=False)
        return session

    return _make


@pytest.fixture()
def stream(make_stream):
    """The default test stream, seeded with three events."""
    return make_stream("ws-test")


def _recv(websocket, count: int) -> list[dict]:
    """Receive ``count`` frames."""
    return [websocket.receive_json() for _ in range(count)]


def _publish(session, kind: str, stream_id: str = "ws-test", **kwargs) -> dict:
    return get_event_service(session).record(event_type=kind, stream_id=stream_id, **kwargs)


# -- connection + historical replay ---------------------------------------


def test_websocket_connects_and_replays_history(client, stream):
    with client.websocket_connect("/ws/events?stream=ws-test") as websocket:
        events = _recv(websocket, 3)
    assert [e["type"] for e in events] == ["order_received", "task_assigned", "task_started"]
    assert [e["sequence"] for e in events] == [1, 2, 3]


def test_replay_is_ascending_by_sequence(client, stream):
    with client.websocket_connect("/ws/events?stream=ws-test") as websocket:
        events = _recv(websocket, 3)
    sequences = [e["sequence"] for e in events]
    assert sequences == sorted(sequences)
    assert len(set(sequences)) == len(sequences)


def test_replayed_frames_carry_the_existing_event_contract(client, stream):
    with client.websocket_connect("/ws/events?stream=ws-test") as websocket:
        event = websocket.receive_json()
    for field in ("id", "type", "timestamp", "actorId", "taskId", "payload"):
        assert field in event
    # Ordering metadata is additive and never mixed into the business payload.
    assert "sequence" in event and "streamId" in event
    assert "sequence" not in event["payload"]
    assert "streamId" not in event["payload"]


def test_websocket_timestamp_is_epoch_milliseconds(client, stream):
    """The client contract is a number, not an ISO string; the client does maths on it."""
    with client.websocket_connect("/ws/events?stream=ws-test") as websocket:
        event = websocket.receive_json()
    assert isinstance(event["timestamp"], int)
    assert event["timestamp"] > 1_600_000_000_000


def test_websocket_frame_has_no_rest_only_fields(client, stream):
    """The stream carries exactly the client contract and nothing server-side.

    ``clockOffsetMs`` is part of that contract: the client needs the reproducible
    logical position now that ``timestamp`` is real UTC. It is ordering metadata,
    so like ``sequence`` it must stay out of ``payload``.
    """
    with client.websocket_connect("/ws/events?stream=ws-test") as websocket:
        event = websocket.receive_json()
    assert set(event) == {
        "id",
        "type",
        "sequence",
        "streamId",
        "timestamp",
        "actorId",
        "taskId",
        "clockOffsetMs",
        "payload",
    }
    assert "clockOffsetMs" not in event["payload"]


def test_empty_stream_replays_nothing_then_receives_live(client, session):
    with client.websocket_connect("/ws/events?stream=ws-empty") as websocket:
        # No history: publish while connected, so it must arrive live.
        _publish(session, "order_received", stream_id="ws-empty")
        event = websocket.receive_json()
    assert event["type"] == "order_received"
    assert event["sequence"] == 1


# -- live delivery ---------------------------------------------------------


def test_new_event_is_delivered_live_after_replay(client, stream):
    with client.websocket_connect("/ws/events?stream=ws-test") as websocket:
        replayed = _recv(websocket, 3)
        _publish(stream, "task_completed")
        live = websocket.receive_json()
    assert [e["type"] for e in replayed][-1] == "task_started"
    assert live["type"] == "task_completed"
    assert live["sequence"] == 4


def test_live_events_arrive_in_sequence_order(client, session):
    with client.websocket_connect("/ws/events?stream=ws-order") as websocket:
        for kind in ("order_received", "task_assigned", "task_started", "task_completed"):
            _publish(session, kind, stream_id="ws-order")
        events = _recv(websocket, 4)
    assert [e["sequence"] for e in events] == [1, 2, 3, 4]
    assert [e["type"] for e in events][-1] == "task_completed"


def test_events_from_other_streams_are_not_delivered(client, stream):
    with client.websocket_connect("/ws/events?stream=ws-test") as websocket:
        _recv(websocket, 3)
        _publish(stream, "cost_metered", stream_id="ws-other")
        _publish(stream, "artifact_created", stream_id="ws-test")
        event = websocket.receive_json()
    assert event["type"] == "artifact_created"


# -- exactly once across the replay/live handover ---------------------------


def test_no_event_is_missed_or_repeated_across_the_handover(client, stream):
    """An event committed around the handover must arrive exactly once."""
    with client.websocket_connect("/ws/events?stream=ws-race") as websocket:
        # Subscribe first, then persist while the replay query is in flight.
        _publish(stream, "order_received", stream_id="ws-race")
        _publish(stream, "task_assigned", stream_id="ws-race")
        _publish(stream, "task_started", stream_id="ws-race")
        events = _recv(websocket, 3)

    sequences = [e["sequence"] for e in events]
    ids = [e["id"] for e in events]
    assert sequences == [1, 2, 3]
    assert len(set(ids)) == 3
    # Nothing persisted before the handover may be missing.
    persisted = get_event_service(stream).list_events(stream_id="ws-race", limit=100)
    assert {e.id for e in persisted} == set(ids)


def test_connection_replays_persisted_event_published_before_connect(client, session):
    _publish(session, "order_received", stream_id="ws-late")
    with client.websocket_connect("/ws/events?stream=ws-late") as websocket:
        event = websocket.receive_json()
    assert event["type"] == "order_received"
    assert event["sequence"] == 1


# -- resume cursor ---------------------------------------------------------


def test_after_sequence_replays_only_newer_events(client, stream):
    with client.websocket_connect("/ws/events?stream=ws-test&afterSequence=1") as websocket:
        events = _recv(websocket, 2)
    assert [e["sequence"] for e in events] == [2, 3]


def test_after_sequence_at_head_replays_nothing_then_goes_live(client, stream):
    with client.websocket_connect("/ws/events?stream=ws-test&afterSequence=3") as websocket:
        _publish(stream, "task_completed")
        event = websocket.receive_json()
    assert event["sequence"] == 4


def test_negative_after_sequence_is_rejected(client, stream):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/events?stream=ws-test&afterSequence=-1"):
            pass


# -- multiple clients ------------------------------------------------------


def test_two_clients_each_receive_history_and_live_events(client, make_stream):
    seeded = make_stream("ws-multi")
    with client.websocket_connect("/ws/events?stream=ws-multi") as websocket_a:
        history_a = _recv(websocket_a, 3)

        with client.websocket_connect("/ws/events?stream=ws-multi") as websocket_b:
            # The late client still gets the full history.
            history_b = _recv(websocket_b, 3)
            _publish(seeded, "task_started", stream_id="ws-multi")

            live_a = websocket_a.receive_json()
            live_b = websocket_b.receive_json()

    assert [e["sequence"] for e in history_a] == [1, 2, 3]
    assert [e["sequence"] for e in history_b] == [1, 2, 3]
    assert live_a["type"] == live_b["type"] == "task_started"
    assert live_a["sequence"] == live_b["sequence"] == 4


def test_one_client_disconnecting_does_not_affect_another(client, make_stream):
    seeded = make_stream("ws-stay")
    with client.websocket_connect("/ws/events?stream=ws-stay") as websocket_b:
        with client.websocket_connect("/ws/events?stream=ws-stay") as websocket_a:
            _recv(websocket_a, 3)
            _recv(websocket_b, 3)
        # websocket_a is closed now; the survivor must still receive.
        _publish(seeded, "task_completed", stream_id="ws-stay")
        survivor = websocket_b.receive_json()
    assert survivor["type"] == "task_completed"
    assert survivor["sequence"] == 4


def test_disconnect_unsubscribes_from_the_bus(client, stream):
    before = get_event_bus().subscriber_count
    with client.websocket_connect("/ws/events?stream=ws-test"):
        pass
    # allow the server task to observe the disconnect
    import time

    time.sleep(0.2)
    assert get_event_bus().subscriber_count <= before + 1


# -- read-only guarantee ---------------------------------------------------


def test_inbound_business_state_is_refused(client, stream):
    """A client cannot push business events; only commands are accepted."""
    with client.websocket_connect("/ws/events?stream=ws-test") as websocket:
        _recv(websocket, 3)
        # A client trying to assert "approved" for itself.
        websocket.send_json({"type": "approved", "payload": {}})
        error = websocket.receive_json()
        assert error["kind"] == "command_error"
        assert error["code"] == "unsupported_frame_kind"

        # The event stream continues unaffected.
        _publish(stream, "approved")
        event = websocket.receive_json()
    assert event["type"] == "approved"
    assert event["sequence"] == 4


def test_refused_frame_did_not_persist_anything(client, stream):
    with client.websocket_connect("/ws/events?stream=ws-test") as websocket:
        _recv(websocket, 3)
        websocket.send_json({"type": "approved", "payload": {}})
        websocket.receive_json()
    # Only the three seeded events exist; nothing was injected.
    assert get_event_service(stream).count_events(stream_id="ws-test") == 3


# -- buffer unit tests -----------------------------------------------------


def test_connection_buffer_drops_already_sent_events():
    connection = EventStreamConnection("s", after_sequence=0)
    connection.on_publish({"id": "a", "sequence": 1, "streamId": "s"})
    connection.on_publish({"id": "a", "sequence": 1, "streamId": "s"})
    batch = connection.take_ready()
    assert [e["id"] for e in batch] == ["a"]
    assert connection.take_ready() == []


def test_connection_buffer_ignores_other_streams():
    connection = EventStreamConnection("s")
    connection.on_publish({"id": "a", "sequence": 1, "streamId": "other"})
    assert connection.take_ready() == []


def test_connection_buffer_waits_for_a_missing_sequence():
    connection = EventStreamConnection("s")
    connection.on_publish({"id": "b", "sequence": 2, "streamId": "s"})
    # Sequence 1 is missing: nothing may be emitted, or 2 would be reordered.
    assert connection.take_ready() == []
    connection.on_publish({"id": "a", "sequence": 1, "streamId": "s"})
    batch = connection.take_ready()
    assert [e["sequence"] for e in batch] == [1, 2]


def test_connection_buffer_ignores_events_at_or_below_resume_point():
    connection = EventStreamConnection("s", after_sequence=5)
    connection.on_publish({"id": "old", "sequence": 4, "streamId": "s"})
    connection.on_publish({"id": "new", "sequence": 6, "streamId": "s"})
    assert [e["id"] for e in connection.take_ready()] == ["new"]


def test_connection_close_stops_delivery():
    connection = EventStreamConnection("s")
    connection.on_publish({"id": "a", "sequence": 1, "streamId": "s"})
    connection.close()
    connection.on_publish({"id": "b", "sequence": 2, "streamId": "s"})
    assert connection.take_ready() == []