"""Agent persistence: canonical five seats, no fake employee rows."""

from __future__ import annotations

from app.agents import AGENT_SEEDS
from app.models import Agent, AgentKind

CANONICAL_IDS = ("ceo", "employee", "manager", "operations", "sales")


def test_seed_inserts_five_agents(seeded_session):
    agents = seeded_session.query(Agent).all()
    assert len(agents) == 5
    assert tuple(sorted(a.id for a in agents)) == CANONICAL_IDS


def test_agent_kinds_match_frontend_contract(seeded_session):
    manager = seeded_session.get(Agent, "manager")
    ceo = seeded_session.get(Agent, "ceo")
    assert manager.kind is AgentKind.AI
    assert ceo.kind is AgentKind.HUMAN


def test_agent_capabilities_and_restrictions_persist(seeded_session):
    sales = seeded_session.get(Agent, "sales")
    assert "prepare quotations" in sales.capabilities
    assert any("Cannot finalise" in r for r in sales.restrictions)


def test_agent_seed_is_idempotent(seeded_session):
    from app.db.seed import seed_agents

    assert seed_agents(seeded_session) == 0
    assert seeded_session.query(Agent).count() == 5


def test_agents_api_lists_five_agents(client):
    response = client.get("/api/agents")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 5
    assert {a["id"] for a in body} == set(CANONICAL_IDS)


def test_agents_api_serialises_camel_case(client):
    body = client.get("/api/agents").json()
    agent = next(a for a in body if a["id"] == "manager")
    assert "kind" in agent
    assert "capabilities" in agent
    assert agent["kind"] == "ai"


def test_agents_api_get_one_and_404(client):
    assert client.get("/api/agents/ceo").json()["role"] == "Chief Executive Officer"
    assert client.get("/api/agents/nobody").status_code == 404


def test_external_sender_is_not_an_agent(client):
    """``ext:supplier`` must not exist as an employee record."""
    ids = {a["id"] for a in client.get("/api/agents").json()}
    assert "ext:supplier" not in ids


def test_seed_profiles_match_agent_seed_count():
    assert len(AGENT_SEEDS) == 5