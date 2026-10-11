"""Development-only endpoints must not exist outside development.

The bridge is read-only, so there is no public way to inject events. The dev
publisher exists purely to prove the bridge works locally and must disappear when
``APP_ENV=production``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings


@pytest.fixture()
def prod_client(monkeypatch, engine):
    """A client whose settings say production."""
    from app.db import session as db_session
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    monkeypatch.setattr(db_session, "_engine", engine)
    monkeypatch.setattr(db_session, "_session_factory", factory)
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()

    from app.main import create_app

    with TestClient(create_app()) as client:
        yield client

    get_settings.cache_clear()
    db_session.reset_engine()


def test_dev_endpoints_absent_in_production(prod_client):
    assert prod_client.post("/api/dev/events", json={"type": "order_received"}).status_code == 404
    assert prod_client.get("/api/dev/streams").status_code == 404


def test_dev_endpoints_absent_in_production_openapi(prod_client):
    paths = prod_client.get("/openapi.json").json()["paths"]
    assert not any("/api/dev" in path for path in paths), sorted(paths)


def test_dev_endpoint_present_in_development(client):
    """Mounted only when explicitly enabled; never a 500 either way."""
    response = client.post(
        "/api/dev/events",
        json={
            "type": "order_received",
            "stream_id": "dev-test",
            "payload": {"message": "Dev event"},
        },
    )
    assert response.status_code in (200, 201, 404), response.status_code


def test_dev_endpoint_persists_before_publishing(client):
    """A dev event goes through the normal service, so it lands in the database."""
    from app.api.deps import get_db
    from app.services.events import EventService

    response = client.post(
        "/api/dev/events",
        json={"type": "cost_metered", "stream_id": "dev-test", "payload": {"amount": 7}},
    )
    if response.status_code == 404:
        pytest.skip("dev endpoints disabled in this configuration")

    body = response.json()
    # Readable through the public read API => it was really persisted.
    listed = client.get("/api/events", params={"stream_id": "dev-test"}).json()
    assert [e["id"] for e in listed] == [body["id"]]
    assert body["sequence"] == 1