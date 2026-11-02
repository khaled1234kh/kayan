import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from console.backend import main as console
from console.backend.session_store import SessionStore
from grounding.retrieval import TechniqueIndex, local_index
from pentagi.agent_config import agent_config, ROOT
from pentagi.agents.base_agent import BaseAgent
from integration.trustgate_client import AuthorizationResult


def test_contracts_use_authorized_option_a_shared_local_qwen():
    expected = {"planner_agent": "A", "webapp_agent": "A", "reporting_agent": "B", "recon_agent": "B", "network_agent": "C"}
    runtime = json.loads((ROOT / "config/llm.json").read_text())
    assert runtime["architecture"] == "A" and runtime["concurrency"] == 1
    assert runtime["fallback_model"] == "qwen2.5:1.5b"
    for role, tier in expected.items():
        config = agent_config(role)
        assert config["model_tier"] == tier
        assert config["model_name"] == runtime["model"] == "qwen2.5:7b"
    assert set(json.loads((ROOT / "config/model_tiers.json").read_text())) == {"A", "B", "C"}


def test_local_sources_have_provenance_and_all_domains():
    index = local_index()
    assert index.metadata["sources"]
    assert all(len(s["sha256"]) == 64 and len(s["commit"]) == 40 for s in index.metadata["sources"])
    domains = {domain for e in index.entries for domain in e.get("domains", [])}
    assert domains == {"enterprise-attack", "mobile-attack", "ics-attack"}
    assert len([e for e in index.entries if e["framework"] == "owasp-top10"]) == 10


def test_keyword_retrieval_relevant_and_deterministic():
    index = local_index()
    query = "sql injection input validation web application"
    first = index.retrieve(query, "A")
    assert first == index.retrieve(query, "A")
    assert any(e["id"] == "A05:2025" for e in first)
    assert all("source_url" in entry for entry in first)
    assert index.retrieve("zzzzqqqqnotavocabularyword", "B") == []
    assert all(e.get("framework") != "mitre-attack" or "enterprise-attack" in e["domains"] for e in first)


def test_tier_depth_preserves_ranking_and_expands_context():
    index = local_index()
    results = [index.retrieve("port scanning network service discovery", tier) for tier in ("A", "B", "C")]
    assert [e["id"] for e in results[0]] == [e["id"] for e in results[2]]
    lengths = [sum(len(e["description"]) for e in result) for result in results]
    assert lengths[0] <= lengths[1] <= lengths[2]
    assert lengths[2] > lengths[0]
    with pytest.raises(ValueError):
        index.retrieve("test", "D")


def test_skill_packets_and_retrieval_reach_actual_executor():
    class Gate:
        def authorize(self, **kwargs):
            return AuthorizationResult(True, "ALLOW", "scope matches")
    class Agent(BaseAgent):
        def run(self, target):
            return []
    agent = Agent("webapp1", "webapp_agent", "eng", Gate())
    agent.grounding_enabled = True
    received = []
    agent.execute_tool("sql_injection_test", {"target": "http://127.0.0.1:8888"}, "127.0.0.1", "web-app",
                       executor_fn=lambda args: received.append(args["_kayan_context"]))
    assert received[0]["skill_packets"] and received[0]["grounding"]
    assert received[0]["model_tier"] == "A"
    agent.grounding_enabled = False
    agent.execute_tool("sql_injection_test", {}, "127.0.0.1", "web-app", executor_fn=lambda args: received.append(args["_kayan_context"]))
    assert received[-1]["grounding"] == [] and received[-1]["skill_packets"]


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(console, "session_store", SessionStore(tmp_path / "sessions"))
    console._engagement_state.clear()
    console._revision = 0
    with TestClient(console.app) as client:
        yield client
    console._engagement_state.clear()


def session_update(eid="eng1", entries=1):
    return {"engagement_id": eid, "status": "active", "agents": [{
        "agent_id": "web1", "role": "webapp_agent", "status": "working", "current_task": "sql_injection_test",
        "task_id": "tool1", "activity": "Executing SQL injection test", "model_tier": "A", "model_name": "UNRESOLVED_PENDING_BUDGET_CONFIRMATION"}],
        "transcript": [{"id": str(i), "seq": i + 1, "timestamp": i, "engagement_id": eid,
            "agent_id": "web1", "agent_role": "webapp_agent", "type": "tool_call", "kind": "tool_result", "content": "observed output",
            "model_tier": "A", "result": {"output": "x" * 6000}} for i in range(entries)],
        "findings": [{"id": "f1", "agent": "webapp_agent", "type": "xss", "mitre": "T1190"}]}


def test_session_endpoint_full_raw_transcript_and_prior_engagement(client):
    assert client.post("/engagement/update", json=session_update(entries=501)).status_code == 200
    current = client.get("/agents/web1/session?engagement_id=eng1").json()
    assert len(current["transcript"]) == 501  # No old 500-entry truncation.
    assert len(current["transcript"][0]["result"]["output"]) == 6000
    assert current["model_tier"] == "A" and current["findings"][0]["mitre"] == "T1190"
    client.post("/engagement/update", json=session_update("eng2"))
    console._engagement_state.clear()  # Simulate losing in-memory state.
    archived = client.get("/agents/webapp_agent/session?engagement_id=eng1")
    assert archived.status_code == 200 and len(archived.json()["transcript"]) == 501
    assert client.get("/agents/unknown/session?engagement_id=eng1").status_code == 404
    assert client.get("/agents/web1/session?engagement_id=missing").status_code == 404


def test_websocket_pushes_new_entry_without_reload(client):
    client.post("/engagement/update", json=session_update())
    with client.websocket_connect("/ws") as socket:
        initial = socket.receive_json()["data"]
        client.post("/engagement/update", json=session_update(entries=2))
        new = socket.receive_json()["data"]
        assert len(initial["transcript"]) == 1 and len(new["transcript"]) == 2
        assert new["transcript"][-1]["seq"] == 2
        assert new["revision"] > initial["revision"]


def test_session_filename_cannot_escape_directory(tmp_path):
    store = SessionStore(tmp_path / "sessions")
    identifier = "../../outside"
    store.save({"engagement_id": identifier})
    assert store.path(identifier).parent == tmp_path / "sessions"
    assert store.load(identifier)["engagement_id"] == identifier
