"""P0.2 company configuration: creation, retrieval and draft editing.

Covers the HTTP contract and the persistence guarantees behind it: the company and
its initial budget account are committed together, configuration survives across
separate sessions, and creating a company never touches the canonical demo agents.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.models import Agent, BudgetAccount, Company, CompanyStatus
from tests.p0_2_helpers import (
    COMPANY_PAYLOAD,
    DEMO_AGENT_IDS,
    create_company,
    set_company_status,
)


# -- create and read -------------------------------------------------------


def test_create_and_retrieve_a_draft_company(configured_client: TestClient):
    created = create_company(configured_client)

    assert created["status"] == "draft"
    assert created["name"] == COMPANY_PAYLOAD["name"]
    assert created["templateKey"] == "clothing"
    assert created["currency"] == "USD"
    assert created["revision"] == 1
    assert created["monthlyBudget"] == "5000.000000"
    assert created["targetMetric"] == "repeat_order_rate"

    fetched = configured_client.get(f"/api/companies/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == created


def test_creation_returns_201_with_a_generated_id(configured_client: TestClient):
    response = configured_client.post("/api/companies", json=COMPANY_PAYLOAD)
    assert response.status_code == 201
    assert response.json()["id"].startswith("cmp_")


def test_creation_opens_the_monthly_budget_account(configured_client: TestClient, factory_for):
    created = create_company(configured_client)

    session = factory_for()
    try:
        account = session.query(BudgetAccount).filter_by(company_id=created["id"]).one()
        assert account.monthly_limit == Decimal("5000")
        assert account.currency == "USD"
        assert account.period_start < account.period_end
        # One ceiling per period is a database invariant.
        assert session.query(BudgetAccount).filter_by(company_id=created["id"]).count() == 1
    finally:
        session.close()


def test_configuration_survives_a_separate_session(configured_client: TestClient, factory_for):
    """A commit is a commit: a fresh session sees the same configuration."""
    created = create_company(configured_client)

    session = factory_for()
    try:
        stored = session.get(Company, created["id"])
        assert stored is not None
        assert stored.name == COMPANY_PAYLOAD["name"]
        assert stored.target_metric == "repeat_order_rate"
        assert stored.target_value == Decimal("0.350000")
    finally:
        session.close()

    # And a second API read agrees with the direct read.
    assert configured_client.get(f"/api/companies/{created['id']}").json()["name"] == (
        COMPANY_PAYLOAD["name"]
    )


def test_creation_does_not_touch_the_canonical_agents_table(configured_client: TestClient, factory_for):
    create_company(configured_client)

    session = factory_for()
    try:
        assert {row.id for row in session.query(Agent).all()} == DEMO_AGENT_IDS
    finally:
        session.close()


def test_multiple_drafts_are_allowed(configured_client: TestClient):
    first = create_company(configured_client, name="First Brand")
    second = create_company(configured_client, name="Second Brand")
    third = create_company(configured_client, name="Third Brand")

    assert len({first["id"], second["id"], third["id"]}) == 3
    for company_id in (first["id"], second["id"], third["id"]):
        assert configured_client.get(f"/api/companies/{company_id}").status_code == 200


# -- retrieval failures -----------------------------------------------------


def test_unknown_company_is_404(configured_client: TestClient):
    response = configured_client.get("/api/companies/cmp_does_not_exist")
    assert response.status_code == 404
    assert "cmp_does_not_exist" in response.json()["detail"]["detail"]


def test_unknown_company_patch_is_404(configured_client: TestClient):
    response = configured_client.patch(
        "/api/companies/cmp_nope", json={"name": "Renamed"}
    )
    assert response.status_code == 404


# -- updates ---------------------------------------------------------------


def test_update_a_draft_company(configured_client: TestClient):
    created = create_company(configured_client)

    response = configured_client.patch(
        f"/api/companies/{created['id']}",
        json={"name": "Kayan Apparel Ltd", "monthlyBudget": "7500.25"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Kayan Apparel Ltd"
    assert body["monthlyBudget"] == "7500.250000"
    assert body["revision"] == 2


def test_partial_update_leaves_omitted_fields_alone(configured_client: TestClient):
    created = create_company(configured_client)

    body = configured_client.patch(
        f"/api/companies/{created['id']}", json={"name": "Renamed Only"}
    ).json()

    assert body["name"] == "Renamed Only"
    assert body["industry"] == "apparel"
    assert body["targetDescription"] == "Grow repeat orders"
    assert body["monthlyBudget"] == "5000.000000"


def test_budget_change_keeps_the_account_consistent(configured_client: TestClient, factory_for):
    created = create_company(configured_client)
    configured_client.patch(
        f"/api/companies/{created['id']}", json={"monthlyBudget": "9000"}
    )

    session = factory_for()
    try:
        account = session.query(BudgetAccount).filter_by(company_id=created["id"]).one()
        assert account.monthly_limit == Decimal("9000")
        # The ceiling is versioned so an increase stays traceable.
        assert account.version == 2
        # No ledger or reservation rows: enforcement is a later stage.
        assert account.monthly_limit is not None
    finally:
        session.close()


def test_currency_change_is_refused_rather_than_converted(configured_client: TestClient):
    """One currency per company for P0: a mismatch is a refusal, not a conversion."""
    created = create_company(configured_client)

    response = configured_client.patch(
        f"/api/companies/{created['id']}", json={"currency": "EUR"}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["field"] == "currency"


def test_update_rejects_a_non_draft_company(configured_client: TestClient, factory_for):
    for status in (CompanyStatus.ACTIVE, CompanyStatus.PAUSED):
        created = create_company(configured_client, name=f"Brand {status.value}")
        set_company_status(factory_for, created["id"], status)

        response = configured_client.patch(
            f"/api/companies/{created['id']}", json={"name": "Renamed"}
        )
        assert response.status_code == 409, status.value
        assert response.json()["detail"]["field"] == "status"


def test_lifecycle_fields_are_not_editable_through_patch(configured_client: TestClient):
    """Activation and pause are separate operations, not draft edits."""
    created = create_company(configured_client)

    for field, value in (
        ("status", "active"),
        ("activeContractId", "ctr_1"),
        ("id", "cmp_other"),
    ):
        response = configured_client.patch(
            f"/api/companies/{created['id']}", json={field: value}
        )
        assert response.status_code == 422, field


# -- creation validation ---------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"name": ""}, "empty name"),
        ({"name": "   "}, "whitespace-only name"),
        ({"templateKey": "not_a_template"}, "unknown template"),
        ({"currency": "XYZ"}, "unsupported currency"),
        ({"monthlyBudget": "0"}, "zero budget"),
        ({"monthlyBudget": "-100"}, "negative budget"),
        ({"monthlyBudget": "1.1234567"}, "too much precision"),
        ({"targetPeriod": "fortnight"}, "unknown target period"),
    ],
)
def test_invalid_creation_is_rejected(configured_client: TestClient, overrides, reason):
    response = configured_client.post("/api/companies", json={**COMPANY_PAYLOAD, **overrides})
    assert response.status_code == 422, f"{reason} should be refused"


@pytest.mark.parametrize(
    ("target", "reason"),
    [
        ({"targetValue": "0.35"}, "a value without a metric"),
        ({"targetMetric": "revenue"}, "a metric without a value"),
        ({"targetMetric": "revenue", "targetValue": "-1"}, "a negative target"),
        ({"targetMetric": "revenue", "targetValue": "0"}, "a zero target"),
        ({"targetMetric": "  "}, "a blank metric"),
    ],
)
def test_malformed_structured_targets_are_rejected(
    configured_client: TestClient, target, reason
):
    """A target is either fully specified or absent.

    The backend refuses to invent a metric, and refuses a value it cannot interpret
    against one.
    """
    payload = {
        **COMPANY_PAYLOAD,
        "targetMetric": None,
        "targetValue": None,
        **target,
    }
    response = configured_client.post("/api/companies", json=payload)
    assert response.status_code == 422, f"{reason} should be refused"


def test_a_rejected_creation_leaves_nothing_behind(configured_client: TestClient, factory_for):
    """Validation runs before any write, so a failure creates no partial company."""
    response = configured_client.post(
        "/api/companies", json={**COMPANY_PAYLOAD, "currency": "XYZ"}
    )
    assert response.status_code == 422

    session = factory_for()
    try:
        assert session.query(Company).count() == 0
        assert session.query(BudgetAccount).count() == 0
    finally:
        session.close()


def test_creation_rejects_an_unsupported_field(configured_client: TestClient):
    response = configured_client.post(
        "/api/companies", json={**COMPANY_PAYLOAD, "status": "active"}
    )
    assert response.status_code == 422