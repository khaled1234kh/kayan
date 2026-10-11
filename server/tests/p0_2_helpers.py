"""Payload builders shared by the P0.2 tests.

Kept out of ``conftest.py`` on purpose: these are values a test sends, not
fixtures, and a test that builds its own payload is clearer than one that inherits it.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.models import Company, CompanyStatus

#: A complete, valid company creation payload.
COMPANY_PAYLOAD: dict[str, Any] = {
    "name": "Kayan Apparel",
    "templateKey": "clothing",
    "monthlyBudget": "5000.00",
    "currency": "USD",
    "industry": "apparel",
    "targetDescription": "Grow repeat orders",
    "targetMetric": "repeat_order_rate",
    "targetValue": "0.35",
    "targetUnit": "ratio",
    "targetPeriod": "quarter",
}

#: The canonical demo workforce ids. Configuration must never touch these.
DEMO_AGENT_IDS = {"ceo", "employee", "manager", "sales", "operations"}


def seat(display_name: str, role_key: str = "sales", **extra: Any) -> dict[str, Any]:
    """One workforce entry with sensible defaults."""
    return {"displayName": display_name, "kind": "ai", "roleKey": role_key, **extra}


def workforce(*seats: dict[str, Any]) -> dict[str, Any]:
    return {"employees": list(seats)}


def create_company(client: TestClient, **overrides: Any) -> dict[str, Any]:
    response = client.post("/api/companies", json={**COMPANY_PAYLOAD, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def set_company_status(
    factory: sessionmaker[Session], company_id: str, status: CompanyStatus
) -> None:
    """Move a company out of draft.

    Activation is a later stage, so a lifecycle guard has to be exercised by writing
    the status directly rather than through an endpoint that does not exist yet.
    """
    session = factory()
    try:
        company = session.get(Company, company_id)
        assert company is not None
        company.status = status
        session.commit()
    finally:
        session.close()


def events_of_type(client: TestClient, event_type: str) -> list[dict[str, Any]]:
    response = client.get("/api/events", params={"stream_id": "main", "limit": 500})
    assert response.status_code == 200, response.text
    return [event for event in response.json() if event["type"] == event_type]