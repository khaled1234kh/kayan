"""The run_comparison command: acceptance, gating, idempotency, concurrency."""

from __future__ import annotations

import json

import pytest

from app.models import CommandRequest, Experiment, WorkflowRun
from app.schemas.commands import parse_command

COMMAND = {
    "kind": "command",
    "command": "run_comparison",
    "requestId": "req-cmp",
    "orderId": "1042",
    "seed": "KAYAN-DEMO-1042",
    "runsPerCondition": 2,
}


def wait_for_experiment(session, request_id: str, timeout: float = 60.0) -> Experiment:
    """Block until the comparison started by this request reaches a terminal state."""
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        session.expire_all()
        found = session.query(Experiment).filter(Experiment.request_id == request_id).first()
        if found is not None and found.status.value in (
            "completed",
            "partially_failed",
            "failed",
        ):
            return found
        time.sleep(0.1)
    raise AssertionError(f"comparison for {request_id} did not finish in {timeout}s")


# -- validation ------------------------------------------------------------


def test_valid_comparison_is_parsed():
    command = parse_command(json.dumps(COMMAND))
    assert not hasattr(command, "code")
    assert command.command == "run_comparison"
    assert command.request_id == "req-cmp"
    assert command.order_id == "1042"
    assert command.seed == "KAYAN-DEMO-1042"
    assert command.runs_per_condition == 2


def test_comparison_defaults():
    command = parse_command(json.dumps({"kind": "command", "command": "run_comparison", "requestId": "r"}))
    assert command.seed == "KAYAN-DEMO-1042"
    assert command.runs_per_condition == 10
    assert command.order_id == "1042"


def test_out_of_range_runs_are_rejected():
    for value in (0, -1, 51, 999):
        result = parse_command(json.dumps({**COMMAND, "runsPerCondition": value}))
        assert hasattr(result, "code"), value
        assert result.code == "invalid_command"


def test_missing_seed_is_rejected():
    result = parse_command(
        json.dumps({"kind": "command", "command": "run_comparison", "requestId": "r", "seed": ""})
    )
    assert result.code == "invalid_command"


def test_extra_fields_are_rejected():
    result = parse_command(json.dumps({**COMMAND, "baselineOnly": True}))
    assert result.code == "invalid_command"


def test_request_order_still_works():
    """The new command does not change the existing one."""
    command = parse_command(json.dumps({"kind": "command", "command": "request_order", "requestId": "r"}))
    assert command.command == "request_order"
    assert not hasattr(command, "runs_per_condition")


# -- gating ----------------------------------------------------------------


def test_comparison_is_refused_when_experiments_are_disabled(client, session, monkeypatch):
    """Opt-in capability, and never enabled in production."""
    monkeypatch.setenv("ENABLE_EXPERIMENTS", "false")
    monkeypatch.setenv("APP_ENV", "development")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        assert get_settings().experiments_allowed is False
        with client.websocket_connect("/ws/events?stream=cmp-test") as websocket:
            websocket.send_json(COMMAND)
            ack = websocket.receive_json()
    finally:
        get_settings.cache_clear()

    assert ack["kind"] == "command_ack"
    assert ack["accepted"] is False
    assert ack["reason"] == "experiments_disabled"
    # Nothing was created for it.
    assert session.query(Experiment).count() == 0


def test_comparison_is_refused_in_production(client, session, monkeypatch):
    """Even with the flag set, production never runs experiments."""
    monkeypatch.setenv("ENABLE_EXPERIMENTS", "true")
    monkeypatch.setenv("APP_ENV", "production")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        assert get_settings().experiments_allowed is False
        with client.websocket_connect("/ws/events?stream=cmp-test") as websocket:
            websocket.send_json(COMMAND)
            ack = websocket.receive_json()
    finally:
        get_settings.cache_clear()

    assert ack["accepted"] is False
    assert ack["reason"] == "experiments_disabled"


# -- accepted path ---------------------------------------------------------


@pytest.fixture()
def experiments_enabled(monkeypatch):
    monkeypatch.setenv("ENABLE_EXPERIMENTS", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_comparison_is_accepted_and_returns_an_experiment_id(
    client, session, experiments_enabled
):
    with client.websocket_connect("/ws/events?stream=cmp-test") as websocket:
        websocket.send_json(COMMAND)
        ack = websocket.receive_json()
        assert ack["accepted"] is True, json.dumps(ack)
        experiment_id = ack["experimentId"]
        assert experiment_id

        # The ack means accepted, not finished.
        running = client.get(f"/api/experiments/{experiment_id}").json()
        assert running["experiment"]["seed"] == "KAYAN-DEMO-1042"

        experiment = wait_for_experiment(session, "req-cmp")

    assert experiment.status.value == "completed"
    assert experiment.runs_per_condition == 2

    # Both conditions ran, with their own runs and events.
    runs = session.query(WorkflowRun).filter(WorkflowRun.experiment_id == experiment.id).all()
    assert len(runs) == 4
    assert {r.condition.value for r in runs} == {"baseline", "enforced"}
    assert all(r.completed for r in runs)


def test_duplicate_request_id_does_not_start_a_second_comparison(
    client, session, experiments_enabled
):
    with client.websocket_connect("/ws/events?stream=cmp-test") as websocket:
        websocket.send_json(COMMAND)
        first = websocket.receive_json()
        websocket.send_json(COMMAND)
        second = websocket.receive_json()
        wait_for_experiment(session, "req-cmp")

    assert first["accepted"] is True
    assert second["accepted"] is False
    assert second["reason"] == "duplicate_request"
    # Still exactly one experiment for that request.
    assert len(session.query(Experiment).all()) == 1


def test_concurrent_comparison_for_the_same_order_is_refused(
    client, session, experiments_enabled
):
    """Only one active comparison for this deterministic order."""
    first = start_slow_comparison(client, session, "req-a")
    with client.websocket_connect("/ws/events?stream=cmp-test") as websocket:
        websocket.send_json({**COMMAND, "requestId": "req-b"})
        ack = websocket.receive_json()
        wait_for_experiment(session, "req-a")

    assert ack["accepted"] is False
    assert ack["reason"] == "comparison_already_running"
    assert ack["experimentId"] == first


def start_slow_comparison(client, session, request_id: str) -> str:
    """Send one comparison and return its experiment id without waiting."""
    with client.websocket_connect("/ws/events?stream=cmp-test") as websocket:
        websocket.send_json({**COMMAND, "requestId": request_id, "runsPerCondition": 5})
        ack = websocket.receive_json()
    assert ack["accepted"] is True, json.dumps(ack)
    return ack["experimentId"]


def test_unknown_order_is_refused(client, session, experiments_enabled):
    with client.websocket_connect("/ws/events?stream=cmp-test") as websocket:
        websocket.send_json({**COMMAND, "requestId": "req-order", "orderId": "9999"})
        ack = websocket.receive_json()
    assert ack["accepted"] is False
    assert ack["reason"] == "unknown_order"


def test_malformed_comparison_frame_is_refused(client, session):
    with client.websocket_connect("/ws/events?stream=cmp-test") as websocket:
        websocket.send_json({**COMMAND, "runsPerCondition": 0})
        error = websocket.receive_json()
    assert error["kind"] == "command_error"
    assert error["code"] == "invalid_command"


def test_refused_comparison_is_recorded(client, session, experiments_enabled):
    with client.websocket_connect("/ws/events?stream=cmp-test") as websocket:
        websocket.send_json({**COMMAND, "requestId": "req-x", "orderId": "9999"})
        websocket.receive_json()
    record = session.get(CommandRequest, "req-x")
    assert record is not None
    assert record.accepted is False
    assert record.reason == "unknown_order"


def test_ordinary_order_run_is_never_labelled_as_a_trial(client, session, experiments_enabled):
    """request_order stays a plain enforced run with no condition."""
    with client.websocket_connect("/ws/events?stream=cmp-test") as websocket:
        websocket.send_json({"kind": "command", "command": "request_order", "requestId": "req-order-1"})
        ack = websocket.receive_json()
        assert ack["accepted"] is True
        assert "experimentId" not in ack
        wait_for_order(session, "req-order-1")

    run = session.query(WorkflowRun).filter(WorkflowRun.request_id == "req-order-1").one()
    assert run.condition is None
    assert run.experiment_id is None
    assert run.denial_count == 1


def wait_for_order(session, request_id: str, timeout: float = 30.0) -> WorkflowRun:
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        session.expire_all()
        run = session.query(WorkflowRun).filter(WorkflowRun.request_id == request_id).first()
        if run is not None and run.status.value in ("completed", "failed"):
            return run
        time.sleep(0.05)
    raise AssertionError(f"order run for {request_id} did not finish in {timeout}s")