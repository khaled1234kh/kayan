"""The backend runtime: workflow execution, collaboration, TrustGate, persistence.

Every test here runs the runtime directly, with no browser, no React and no
WebSocket. That is the point of Task 09: the backend owns the business process.
"""

from __future__ import annotations

import pytest

from app.models import (
    Handoff,
    HandoffStatus,
    Message,
    Task,
    TaskStatus,
    WorkflowRun,
    WorkflowRunStatus,
)
from app.runtime import KayanRuntime, UnknownOrder, step_signature
from app.security.trustgate import AgentIntent, authorize_intent
from app.services.events import EventService


@pytest.fixture()
def runtime_run(session):
    """One executed order, shared by the assertions below."""
    from app.db.seed import seed_agents

    seed_agents(session)
    run = KayanRuntime().request_order(session, order_id="1042", request_id="req-runtime-1")
    events = EventService(session).list_events(run_id=run.id, limit=500)
    return run, events


def types_of(events) -> list[str]:
    return [e.event_type for e in events]


# -- the run completes with no frontend ------------------------------------


def test_request_order_completes_without_any_frontend(runtime_run):
    run, events = runtime_run
    assert run.status is WorkflowRunStatus.COMPLETED
    assert run.error is None
    assert types_of(events)[-1] == "task_completed"
    assert run.event_count == len(events) == 43


def test_each_execution_gets_a_distinct_run_id(session):
    from app.db.seed import seed_agents

    seed_agents(session)
    first = KayanRuntime().request_order(session, request_id="r1")
    second = KayanRuntime().request_order(session, request_id="r2")
    assert first.id != second.id
    assert second.run_index == first.run_index + 1

    # Events are attributed to their own run.
    first_events = EventService(session).list_events(run_id=first.id, limit=500)
    second_events = EventService(session).list_events(run_id=second.id, limit=500)
    assert {e.run_id for e in first_events} == {first.id}
    assert {e.run_id for e in second_events} == {second.id}


def test_all_events_carry_the_run_id(runtime_run):
    run, events = runtime_run
    assert all(e.run_id == run.id for e in events)


def test_events_use_the_main_stream_and_strict_ordering(runtime_run):
    _, events = runtime_run
    assert {e.stream_id for e in events} == {"main"}
    assert [e.sequence for e in events] == sorted(e.sequence for e in events)


def test_workflow_signature_is_stable():
    assert step_signature() == [
        "event", "event", "event", "delegate", "accept", "send", "receive", "event",
        "send", "receive", "intent", "intent", "send", "receive", "send", "receive",
        "send", "receive", "complete", "send", "receive", "send", "receive", "send",
        "receive", "event", "event", "event",
    ]


def test_unknown_order_is_refused(session):
    from app.db.seed import seed_agents

    seed_agents(session)
    with pytest.raises(UnknownOrder):
        KayanRuntime().request_order(session, order_id="7777")
    assert session.query(WorkflowRun).count() == 0


# -- collaboration ---------------------------------------------------------


def test_collaboration_directions(runtime_run):
    """Manager->Sales, Sales->Ops, Ops->Sales, Sales->Human, Sales->Manager, Manager->CEO."""
    _, events = runtime_run
    sent = [e for e in events if e.event_type == "agent_message_sent"]
    pairs = {(m.payload["agentMessage"]["fromAgentId"], m.payload["agentMessage"]["toAgentId"]) for m in sent}
    assert ("manager", "sales") in pairs       # delegation message
    assert ("sales", "operations") in pairs    # inventory request
    assert ("operations", "sales") in pairs    # inventory shortfall report
    assert ("sales", "employee") in pairs      # fulfilment decision request
    assert ("employee", "sales") in pairs      # partial fulfilment
    assert ("sales", "manager") in pairs       # quotation returned
    assert ("manager", "ceo") in pairs         # approval request
    assert ("ceo", "manager") in pairs         # approval granted
    assert ("ext:supplier", "operations") in pairs


def test_messages_are_persisted_as_rows(session, runtime_run):
    _, events = runtime_run
    messages = session.query(Message).all()
    assert len(messages) == len([e for e in events if e.event_type == "agent_message_sent"])

    supervisor = next(m for m in messages if m.external_sender == "ext:supplier")
    assert supervisor.from_agent_id is None
    assert supervisor.to_agent_id == "operations"
    assert supervisor.instructions and "8841" in supervisor.instructions

    # Structured context survived, not flattened to a string.
    inventory = next(m for m in messages if m.from_agent_id == "operations" and m.to_agent_id == "sales")
    assert inventory.context["available"] == 42
    assert inventory.context["required"] == 50


def test_handoff_is_created_and_completed(session, runtime_run):
    _, events = runtime_run
    handoffs = session.query(Handoff).all()
    assert len(handoffs) == 1

    handoff = handoffs[0]
    assert handoff.from_agent_id == "manager"
    assert handoff.to_agent_id == "sales"
    assert handoff.status is HandoffStatus.COMPLETED
    assert handoff.objective == "Prepare quotation for Order #1042"
    assert handoff.expected_output == "Draft quotation"
    assert "CEO approval required before finalisation" in handoff.constraints
    assert handoff.source_message_id is not None
    assert session.get(Message, handoff.source_message_id) is not None

    # And it is carried on the events the client rebuilds it from.
    delegated = next(e for e in events if e.event_type == "task_delegated")
    assert delegated.payload["handoff"]["id"] == handoff.id
    accepted = next(e for e in events if e.event_type == "task_accepted")
    assert accepted.payload["handoff"]["status"] == "accepted"
    closed = [e for e in events if e.event_type == "task_completed" and "handoff" in e.payload]
    assert closed[0].payload["handoff"]["status"] == "completed"


def test_delivery_and_acceptance_events(runtime_run):
    _, events = runtime_run
    kinds = types_of(events)
    assert kinds.count("agent_message_received") == 9
    assert "task_accepted" in kinds
    assert "task_delegated" in kinds
    assert kinds.count("task_handoff") == 2


def test_task_row_transitions(runtime_run, session):
    run, events = runtime_run
    task = session.get(Task, run_events_task_id(events))
    assert task is not None
    assert task.assigned_agent_id == "manager"
    assert task.status is TaskStatus.COMPLETED


def run_events_task_id(events) -> str:
    return next(e.task_id for e in events if e.task_id)


# -- TrustGate -------------------------------------------------------------


def test_unauthorized_intent_is_denied_and_blocks(runtime_run):
    _, events = runtime_run
    kinds = types_of(events)

    denial = next(e for e in events if e.event_type == "policy_denied")
    decision = denial.payload["policyDecision"]
    assert decision["decision"] == "deny"
    assert decision["policy"] == "Customer Data Scope"
    # the decision carries the human label; the raw action is on the intent
    assert decision["action"] == "Read customer record"
    assert decision["resource"] == "customer/8841"
    assert decision["subject"] == "AI Operations"
    assert denial.actor_id == "operations"
    assert denial.payload["intent"]["action"] == "customer_data.read"
    assert denial.payload["intent"]["source"] == "untrusted"

    blocked = next(e for e in events if e.event_type == "blocked")
    assert blocked.actor_id == "operations"
    # Denied then blocked, in that order.
    assert kinds.index("policy_denied") < kinds.index("blocked")


def test_authorized_recovery_after_the_denial(runtime_run):
    run, events = runtime_run
    kinds = types_of(events)
    blocked_at = kinds.index("blocked")
    resumed = [
        e
        for e in events[blocked_at + 1 :]
        if e.event_type == "task_started" and e.actor_id == "operations"
    ]
    assert resumed, "the blocked agent must resume with its authorized action"
    assert "policyDecision" in resumed[0].payload
    assert resumed[0].payload["policyDecision"]["decision"] == "allow"
    assert run.recovery_count == 1
    assert run.denial_count == 1
    assert run.blocked_count == 1


def test_backend_evaluator_reproduces_the_verified_scenario():
    denied = authorize_intent(
        AgentIntent("operations", "customer_data.read", "customer/8841", "untrusted")
    )
    assert denied.decision == "deny"
    assert denied.policy == "Customer Data Scope"

    allowed = authorize_intent(
        AgentIntent("operations", "inventory.read", "inventory/50-shirts", "trusted")
    )
    assert allowed.decision == "allow"
    assert allowed.policy == "Capability Contract"


def test_ceo_may_not_be_simulated_away_from_the_gate():
    """The gate is the only decision point: an out-of-scope intent still denies."""
    decision = authorize_intent(AgentIntent("sales", "customer_data.read", "customer/9", "trusted"))
    assert decision.decision == "deny"
    assert decision.policy == "Customer Data Scope"


def test_unknown_agent_is_denied_not_crashed():
    decision = authorize_intent(AgentIntent("ghost", "inventory.read", "inventory/1", "trusted"))
    assert decision.decision == "deny"
    assert "No capability contract" in decision.reason


# -- persistence -----------------------------------------------------------


def test_everything_is_queryable_after_the_run(session, runtime_run):
    from app.models import Agent

    run, events = runtime_run
    assert session.query(Agent).count() == 5
    assert session.query(Task).filter(Task.id == run_events_task_id(events)).count() == 1
    assert session.query(Message).count() == 9
    assert session.query(Handoff).count() == 1
    assert len(events) == 43
    assert session.get(WorkflowRun, run.id) is not None


def test_workflow_run_api_exposes_the_run(client, runtime_run):
    run, _ = runtime_run
    listed = client.get(f"/api/runs/workflow/orders/1042").json()
    assert any(r["runId"] == run.id for r in listed)

    detail = client.get(f"/api/runs/{run.id}").json()
    assert detail["status"] == "completed"
    # An ordinary request_order is not an experimental trial, so it carries no
    # condition: that label exists only for trials of a comparison.
    assert detail["condition"] is None
    assert detail["orderId"] == "1042"  # order identity
    assert detail["eventCount"] == 43
    assert detail["denialCount"] == 1
    assert detail["error"] is None


def test_client_can_read_the_run_events(session, runtime_run, client):
    run, _ = runtime_run
    body = client.get("/api/events", params={"run_id": run.id}).json()
    assert len(body) == 43
    assert body[0]["type"] == "order_received"
    assert body[-1]["type"] == "task_completed"


def test_payload_convention_preserved(runtime_run):
    """payload.message stays the headline; the object lives beside it."""
    _, events = runtime_run
    asked = next(
        e
        for e in events
        if e.event_type == "agent_message_sent"
        and e.payload["agentMessage"]["toAgentId"] == "operations"
    )
    # A draft headline stays a string; the structured object sits beside it.
    assert isinstance(asked.payload["message"], str)
    assert isinstance(asked.payload["agentMessage"], dict)
    assert asked.payload["agentMessage"]["id"].startswith("msg-")

    # The handoff message carries no draft headline, exactly as in the frontend;
    # the step headline rides on the explicit task_handoff instead.
    handoff_sent = next(
        e
        for e in events
        if e.event_type == "agent_message_sent"
        and e.payload["agentMessage"]["type"] == "handoff"
    )
    assert handoff_sent.payload.get("message") is None
    handoff_event = next(
        e for e in events if e.event_type == "task_handoff" and "handoff" in e.payload
    )
    assert handoff_event.payload["message"] == "Manager delegated quotation task to AI Sales"


# -- failure handling ------------------------------------------------------


def test_a_failing_step_marks_the_run_failed_without_faking_completion(session, monkeypatch):
    from app.db.seed import seed_agents
    import app.runtime.runtime as runtime_module

    seed_agents(session)
    runtime = KayanRuntime()

    def boom(*args, **kwargs):
        raise RuntimeError("step exploded")

    # Break the collaboration layer after the first few events.
    original = runtime_module.AgentCollaboration.send_message
    calls = {"n": 0}

    def flaky(self, draft):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("step exploded")
        return original(self, draft)

    monkeypatch.setattr(runtime_module.AgentCollaboration, "send_message", flaky)

    run = runtime.request_order(session, request_id="req-fail")

    assert run.status is WorkflowRunStatus.FAILED
    assert run.error is not None and "step exploded" in run.error
    # No fabricated success.
    events = EventService(session).list_events(run_id=run.id, limit=500)
    assert "task_completed" not in types_of(events)
    task_id = next((e.task_id for e in events if e.task_id), None)
    assert session.get(Task, task_id).status is not TaskStatus.COMPLETED