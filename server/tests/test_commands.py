"""Command protocol: validation, acknowledgement, idempotency, conflicts.

These tests drive the real handler over a real WebSocket, so the protocol is
exercised end to end rather than at the parser only.
"""

from __future__ import annotations

import json

import pytest

from app.models import CommandRequest, WorkflowRun
from app.schemas.commands import CommandAck, ProtocolError, parse_command

COMMAND = {"kind": "command", "command": "request_order", "requestId": "req-1"}


def _frame(**overrides) -> dict:
    return {**COMMAND, **overrides}


def wait_for_run(session, request_id: str, timeout: float = 20.0) -> str | None:
    """Block until the run started by a command has reached a terminal state.

    The acknowledgement returns immediately, so a test that accepted a command
    must wait for the runtime to finish before tearing the schema down.
    """
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        session.expire_all()
        record = session.get(CommandRequest, request_id)
        if record is not None and record.run_id:
            run = session.get(WorkflowRun, record.run_id)
            if run is not None and run.status.value in ("completed", "failed"):
                return run.id
        time.sleep(0.05)
    raise AssertionError(f"workflow run for {request_id} did not finish in {timeout}s")


# -- validation, before anything reaches the runtime ------------------------


def test_valid_request_order_is_parsed():
    command = parse_command(json.dumps(_frame()))
    assert not isinstance(command, ProtocolError)
    assert command.command == "request_order"
    assert command.request_id == "req-1"
    assert command.order_id == "1042"


def test_unknown_command_is_rejected():
    result = parse_command(json.dumps(_frame(command="send_message")))
    assert isinstance(result, ProtocolError)
    assert result.code == "unknown_command"
    assert "send_message" in result.message


def test_arbitrary_command_name_never_reaches_the_runtime():
    for name in ("approve", "reject", "create_agent", "tool_call", ""):
        result = parse_command(json.dumps(_frame(command=name)))
        assert isinstance(result, ProtocolError), name
        assert result.code == "unknown_command"


def test_malformed_json_is_rejected():
    result = parse_command("{not json")
    assert isinstance(result, ProtocolError)
    assert result.code == "malformed_frame"


def test_non_command_frame_kind_is_rejected():
    result = parse_command(json.dumps({"kind": "event", "type": "task_completed"}))
    assert isinstance(result, ProtocolError)
    assert result.code == "unsupported_frame_kind"


def test_missing_request_id_is_rejected():
    payload = {"kind": "command", "command": "request_order"}
    result = parse_command(json.dumps(payload))
    assert isinstance(result, ProtocolError)
    assert result.code == "invalid_command"
    assert "requestId" in result.message


def test_empty_request_id_is_rejected():
    result = parse_command(json.dumps(_frame(requestId="")))
    assert isinstance(result, ProtocolError)
    assert result.code == "invalid_command"


def test_unknown_extra_field_is_rejected():
    """No smuggling extra business fields into the command."""
    result = parse_command(json.dumps(_frame(actorId="ceo", approved=True)))
    assert isinstance(result, ProtocolError)
    assert result.code == "invalid_command"


def test_command_frame_uses_the_envelope_shape():
    command = parse_command(json.dumps(_frame()))
    frame = command.to_frame()
    assert frame["kind"] == "command"
    assert frame["command"] == "request_order"
    assert "requestId" in frame
    # Protocol metadata is not a business event.
    assert "payload" not in frame
    assert "type" not in frame


# -- over the wire ---------------------------------------------------------


def test_websocket_accepts_command_and_acknowledges(client, session):
    with client.websocket_connect("/ws/events?stream=cmd-test") as websocket:
        websocket.send_json(_frame(requestId="ws-accept"))
        ack = websocket.receive_json()
        # The ack is protocol only; wait for the business result on the stream
        # side while the client is still connected.
        run_id = wait_for_run(session, "ws-accept")
    assert ack["kind"] == "command_ack"
    assert ack["requestId"] == "ws-accept"
    assert ack["accepted"] is True
    assert session.get(WorkflowRun, run_id).status.value == "completed"


def test_websocket_rejects_unknown_command_with_protocol_error(client, session):
    with client.websocket_connect("/ws/events?stream=cmd-test") as websocket:
        websocket.send_json(_frame(command="drop_database", requestId="ws-bad"))
        error = websocket.receive_json()
    assert error["kind"] == "command_error"
    assert error["code"] == "unknown_command"
    assert error["requestId"] == "ws-bad"


def test_websocket_rejects_malformed_frame(client, session):
    with client.websocket_connect("/ws/events?stream=cmd-test") as websocket:
        websocket.send_text("not json at all")
        error = websocket.receive_json()
    assert error["kind"] == "command_error"
    assert error["code"] == "malformed_frame"


def test_websocket_rejects_unknown_order(client, session):
    with client.websocket_connect("/ws/events?stream=cmd-test") as websocket:
        websocket.send_json(_frame(requestId="ws-order", orderId="9999"))
        ack = websocket.receive_json()
    assert ack["kind"] == "command_ack"
    assert ack["accepted"] is False
    assert ack["reason"] == "unknown_order"


def test_duplicate_request_id_is_refused(client, session):
    """A redelivered command must not start a second run."""
    with client.websocket_connect("/ws/events?stream=cmd-test") as websocket:
        websocket.send_json(_frame(requestId="ws-dup"))
        first = websocket.receive_json()
        websocket.send_json(_frame(requestId="ws-dup"))
        second = websocket.receive_json()
        run_id = wait_for_run(session, "ws-dup")

    assert first["accepted"] is True
    assert second["accepted"] is False
    assert second["reason"] == "duplicate_request"

    # Exactly one run exists for the duplicated request.
    session.expire_all()
    matching = [r for r in session.query(WorkflowRun).all() if r.request_id == "ws-dup"]
    assert [r.id for r in matching] == [run_id]


def test_command_request_record_is_persisted(client, session):
    with client.websocket_connect("/ws/events?stream=cmd-test") as websocket:
        websocket.send_json(_frame(requestId="ws-persist"))
        websocket.receive_json()
        wait_for_run(session, "ws-persist")

    session.expire_all()
    record = session.get(CommandRequest, "ws-persist")
    assert record is not None
    assert record.command == "request_order"
    assert record.accepted is True
    # and it is linked to the run it started
    assert record.run_id is not None


def test_refused_command_is_recorded(client, session):
    with client.websocket_connect("/ws/events?stream=cmd-test") as websocket:
        websocket.send_json(_frame(requestId="ws-refused", orderId="0000"))
        websocket.receive_json()
    record = session.get(CommandRequest, "ws-refused")
    assert record is not None
    assert record.accepted is False
    assert record.reason == "unknown_order"


def test_active_order_blocks_a_second_concurrent_run(client, session):
    """One active workflow per order."""
    from app.models import WorkflowRunStatus

    session.add(
        WorkflowRun(
            id="run_inflight",
            request_id="inflight",
            order_id="1042",
            status=WorkflowRunStatus.RUNNING,
            run_index=1,
        )
    )
    session.commit()

    with client.websocket_connect("/ws/events?stream=cmd-test") as websocket:
        websocket.send_json(_frame(requestId="ws-conflict", orderId="1042"))
        ack = websocket.receive_json()

    assert ack["accepted"] is False
    assert ack["reason"] == "order_already_running"
    assert ack["runId"] == "run_inflight"


def test_ack_is_protocol_only_and_carries_no_business_result(client, session):
    with client.websocket_connect("/ws/events?stream=cmd-test") as websocket:
        websocket.send_json(_frame(requestId="ws-shape"))
        ack = websocket.receive_json()
        wait_for_run(session, "ws-shape")
    # Exactly the documented acknowledgement fields, nothing more.
    assert set(ack) <= {"kind", "requestId", "command", "accepted", "reason", "runId"}
    assert ack["kind"] == "command_ack"


def test_command_ack_shape_round_trips():
    ack = CommandAck(request_id="x", command="request_order", accepted=True)
    frame = ack.to_frame()
    assert frame == {
        "kind": "command_ack",
        "requestId": "x",
        "command": "request_order",
        "accepted": True,
    }