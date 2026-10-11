"""Health endpoint and database connectivity."""

from __future__ import annotations

from sqlalchemy import text


def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_db_probe_reports_dialect(client):
    response = client.get("/api/health/db")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["dialect"] in {"postgresql", "sqlite"}


def test_database_connection_round_trip(session):
    assert session.execute(text("SELECT 1")).scalar_one() == 1


def test_openapi_document_is_generated(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    for expected in (
        "/api/health",
        "/api/agents",
        "/api/events",
        "/api/tasks",
        "/api/messages",
        "/api/handoffs",
        "/api/runs",
    ):
        assert expected in paths, f"missing endpoint {expected}"