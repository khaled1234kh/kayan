import json

import httpx
import pytest
from fastapi.testclient import TestClient

from console.backend import main as console
from integration.trustgate_client import AuthorizationResult
from pentagi.agents.base_agent import BaseAgent
from pentagi.orchestrator import EngagementOrchestrator


class Gate:
    def __init__(self, allowed=True):
        self.allowed = allowed

    def authorize(self, **kwargs):
        return AuthorizationResult(self.allowed, "ALLOW" if self.allowed else "DENY",
                                   "test decision", "test-policy", "audit-id")

    def load_roe(self, roe):
        return {"rules_compiled": 6}

    def close(self):
        pass


class Agent(BaseAgent):
    def run(self, target):
        return []


def test_denial_is_captured_and_never_executes_tool():
    agent = Agent("agent", "recon_agent", "engagement", Gate(False))
    observed = []
    agent.event_sink = lambda *args: observed.append(args)
    executed = []
    result = agent.execute_tool("scan", {}, "127.0.0.1", "recon",
                                executor_fn=lambda args: executed.append(args))
    assert result["allowed"] is False and executed == []
    assert [e[1] for e in observed if e[1] != "context_prepared"] == ["authorization_requested", "authorization_decision", "tool_denied"]
    assert observed[-1][-1]["audit_entry_id"] == "audit-id"
    assert len(agent.denied_actions) == 1


def test_actual_tool_output_is_captured_and_marked_when_truncated():
    agent = Agent("agent", "recon_agent", "engagement", Gate())
    observed = []
    agent.event_sink = lambda *args: observed.append(args)
    agent.execute_tool("scan", {}, "127.0.0.1", "recon", executor_fn=lambda args: {"output": "x" * 5000})
    assert observed[-1][1] == "tool_result"
    assert observed[-1][-1]["truncated"] is True
    assert observed[-1][3].endswith("[truncated]")
    assert len(agent.allowed_actions) == 1


def test_execution_error_is_observed_without_fabricating_a_result():
    agent = Agent("agent", "recon_agent", "engagement", Gate())
    observed = []
    agent.event_sink = lambda *args: observed.append(args)
    def fail(args):
        raise RuntimeError("tool failed")
    result = agent.execute_tool("scan", {}, "127.0.0.1", "recon", executor_fn=fail)
    assert result["result"] == {"error": "tool failed"}
    assert observed[-1][-1]["error"] is True


@pytest.fixture
def client(monkeypatch, tmp_path):
    from console.backend.session_store import SessionStore
    monkeypatch.setattr(console, "session_store", SessionStore(tmp_path / "sessions"))
    console._engagement_state.clear()
    console._revision = 0
    with TestClient(console.app) as client:
        yield client
    console._engagement_state.clear()


def test_late_subscriber_and_reconnect_recover_full_transcript(client):
    entry = {"id": "event1", "timestamp": 123, "agent_id": "recon1",
             "agent_role": "recon_agent", "kind": "tool_started", "content": "Executing scan"}
    update = {"engagement_id": "one", "status": "active", "transcript": [entry],
              "agents": [{"agent_id": "recon1", "role": "recon_agent", "current_task": "scan"}]}
    assert client.post("/engagement/update", json=update).status_code == 200
    with client.websocket_connect("/ws") as socket:
        initial = socket.receive_json()["data"]
        assert initial["transcript"] == [{**entry, "seq": 1}]
        assert initial["agents"][0]["current_task"] == "scan"
        update["transcript"].append({**entry, "id": "event2", "kind": "tool_result", "content": "actual output"})
        client.post("/engagement/update", json=update)
        newer = socket.receive_json()["data"]
        assert newer["revision"] > initial["revision"]
    with client.websocket_connect("/ws") as socket:
        recovered = socket.receive_json()["data"]
        assert recovered == newer == client.get("/engagement").json()


def test_new_engagement_cannot_inherit_previous_transcript(client):
    client.post("/engagement/update", json={"engagement_id": "old", "target": "old-target", "findings": [{"type": "old"}]})
    client.post("/engagement/update", json={"engagement_id": "new", "status": "ready"})
    state = client.get("/engagement").json()
    assert state["engagement_id"] == "new"
    assert "target" not in state and "findings" not in state


def test_malformed_transcript_is_rejected(client):
    response = client.post("/engagement/update", json={"engagement_id": "bad", "transcript": [{"id": "missing-fields"}]})
    assert response.status_code == 422
    assert client.get("/engagement").json()["status"] == "waiting"


def test_orchestrator_publishes_all_agents_actual_roe_tasks_and_final_state(monkeypatch, tmp_path):
    orch = EngagementOrchestrator()
    orch.trustgate.close()
    orch.trustgate = Gate()
    captured = []
    orch._console.close()
    def capture(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"status": "ok"})
    orch._console = httpx.Client(transport=httpx.MockTransport(capture))
    monkeypatch.chdir(tmp_path)
    try:
        orch.create_engagement("actual-operator", ["lab.local"], ["recon", "web-app"])
        for agent in orch.agents:
            def run(target, a=agent):
                a.execute_tool("probe", {}, "lab.local", "recon", executor_fn=lambda args: {"observed": "fixture"})
                a.findings = [{"type": "fixture", "agent": a.role, "data": {"observed": "fixture"}}]
                return a.findings
            agent.run = run
        orch.run("http://lab.local:8888")
        final = captured[-1]
        assert len(final["agents"]) == 3  # Two selected agents and reporting.
        assert final["roe"]["targets"] == ["lab.local"]
        assert final["roe"]["authorized_by"] == "actual-operator"
        assert final["status"] == "completed" and len(final["findings"]) == 2
        assert all(a["current_task"] is None and a["status"] == "completed" for a in final["agents"])
        working = next(s for s in captured if any(a["current_task"] == "probe" for a in s["agents"]))
        assert len(working["agents"]) == 3
        assert any(t["kind"] == "tool_result" and "fixture" in t["content"] for t in final["transcript"])
    finally:
        orch.close()


def test_console_outage_does_not_bypass_denial():
    orch = EngagementOrchestrator()
    orch.trustgate.close()
    orch.trustgate = Gate(False)
    orch._console.close()
    def offline(request):
        raise httpx.ConnectError("console offline", request=request)
    orch._console = httpx.Client(transport=httpx.MockTransport(offline))
    try:
        orch.create_engagement("operator", ["127.0.0.1"], ["recon"])
        executed = []
        result = orch.agents[0].execute_tool("scan", {}, "127.0.0.1", "recon", executor_fn=lambda args: executed.append(args))
        assert not result["allowed"] and not executed
        assert orch.agent_states[orch.agents[0].agent_id]["current_task"] is None
        assert orch.last_console_error is not None
    finally:
        orch.close()
