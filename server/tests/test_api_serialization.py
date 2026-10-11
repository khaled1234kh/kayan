"""API boundary: schemas, not ORM models."""

from __future__ import annotations

from app.schemas import AgentOut, EventOut, ExperimentOut, HandoffOut, MessageOut, TaskOut


def test_orm_models_are_not_exposed_directly(client):
    """Every declared response model must be a Pydantic schema."""
    openapi = client.get("/openapi.json").json()
    components = openapi["components"]["schemas"]
    assert "AgentOut" in components
    assert "TaskOut" in components
    assert "MessageOut" in components
    assert "HandoffOut" in components
    assert "EventOut" in components
    assert "ExperimentOut" in components
    # No ORM class leaks into the contract.
    assert not any(name.endswith("Model") or name == "Agent" for name in components)


def test_agent_schema_validates_from_orm_row(seeded_session):
    from app.models import Agent

    agent = Agent(
        id="ceo",
        name="Nadia Farouk",
        role="Chief Executive Officer",
        kind="human",
        objective="Accountable for the final business decision on every order.",
        capabilities=["approve final action"],
        restrictions=["Cannot be delegated approval authority"],
        active=True,
    )
    payload = AgentOut.model_validate(agent).model_dump(by_alias=True)
    assert payload["capabilities"] == ["approve final action"]
    assert payload["role"] == "Chief Executive Officer"


def test_event_schema_exposes_sequence_and_frontend_keys(session):
    from app.services import get_event_service

    event = get_event_service(session).record(
        event_type="order_received", stream_id="s-1", actor_id="manager"
    )
    payload = EventOut.model_validate(event).model_dump(by_alias=True)
    assert payload["sequence"] == 1
    assert payload["actorId"] == "manager"
    assert payload["streamId"] == "s-1"
    assert payload["type"] == "order_received"


def test_task_schema_exposes_parent_task_id(seeded_session):
    from app.models import Task, TaskStatus

    task = Task(
        id="t-1",
        title="Order",
        objective="Produce a quotation",
        status=TaskStatus.OPEN,
        assigned_agent_id="manager",
        parent_task_id=None,
    )
    payload = TaskOut.model_validate(task).model_dump(by_alias=True)
    assert payload["assignedAgentId"] == "manager"
    assert payload["parentTaskId"] is None
    assert payload["status"] == "open"


def test_timestamps_are_iso8601(client, session):
    from app.db.seed import seed_demo_order

    seed_demo_order(session)
    agent = client.get("/api/agents/ceo").json()
    assert isinstance(agent["createdAt"], str)
    event = client.get("/api/events/evt-1042-000").json()
    assert event["timestamp"].startswith("20")


def test_ids_are_consistent_across_endpoints(client, session):
    """A run id referenced by an event must resolve through the runs API."""
    from app.db.seed import seed_demo_order

    seed_demo_order(session)
    events = client.get("/api/events", params={"run_id": "run-kayan-1042-enforced-001"}).json()
    assert events
    run_id = events[0]["runId"]
    assert client.get(f"/api/runs/{run_id}").status_code == 200


def test_unknown_ids_return_404(client):
    for path in ("agents", "tasks", "messages", "handoffs", "events", "runs"):
        assert client.get(f"/api/{path}/unknown-id").status_code == 404


def test_run_schema_contract(client, session):
    from app.db.seed import seed_demo_order

    seed_demo_order(session)
    run = client.get("/api/runs").json()[0]
    for field in (
        "experimentId",
        "seed",
        "condition",
        "startedAt",
        "completedAt",
        "durationMs",
        "completed",
        "eventCount",
        "messageCount",
        "handoffCount",
        "policyDecisionCount",
        "denialCount",
        "blockedCount",
        "recoveryCount",
        "unauthorizedActionAttempted",
        "unauthorizedActionAllowed",
        "finalState",
    ):
        assert field in run, f"missing contract field {field}"
    assert ExperimentOut is not None
    assert HandoffOut is not None
    assert MessageOut is not None