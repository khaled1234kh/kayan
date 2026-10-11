"""P0.3 persistence, audit and the provider seam.

Two claims carry the most weight here:

* **A proposal is inert.** Generating one must leave the company exactly as it was:
  no employees, no contracts, no budget movement, no status change, and the
  canonical demo agents untouched.
* **A proposal is announced only once it exists.** The record is committed before
  ``recommendation_generated`` is published, and a generation that fails produces
  neither a record nor an event.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.company.providers import (
    RecommendationContext,
    available_providers,
    get_provider,
    register_provider,
    resolve_provider,
)
from app.company.recommendation_validation import validate_proposal
from app.core.config import Settings
from app.events.bus import get_event_bus
from app.models import (
    Agent,
    BudgetAccount,
    Company,
    CompanyEmployee,
    CompanyStatus,
    Contract,
    Recommendation,
    RecommendationStatus,
)
from app.schemas.recommendation import RecommendationProposal, RecommendationRequest
from app.services.recommendations import RecommendationService
from tests.p0_2_helpers import DEMO_AGENT_IDS, create_company

RECOMMEND = "/api/setup/recommendations"

#: Captured before any monkeypatching, so a stand-in provider can build a genuine
#: proposal and then corrupt one specific part of it.
from app.company.recommendation_providers import TemplateProvider as _TemplateProvider

ORIGINAL_RECOMMEND = _TemplateProvider.recommend


def recommend(client: TestClient, company_id: str, **preferences):
    body: dict = {"companyId": company_id}
    if preferences:
        body["preferences"] = preferences
    response = client.post(RECOMMEND, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def stream_events(client: TestClient, event_type: str) -> list[dict]:
    response = client.get("/api/events", params={"stream_id": "main", "limit": 5000})
    assert response.status_code == 200, response.text
    return [event for event in response.json() if event["type"] == event_type]


# -- persistence ------------------------------------------------------------


def test_a_recommendation_can_be_retrieved_by_id(configured_client: TestClient):
    company = create_company(configured_client)
    created = recommend(configured_client, company["id"], desiredEmployeeCount=5)

    fetched = configured_client.get(f"{RECOMMEND}/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == created


def test_the_response_survives_a_new_session(configured_client: TestClient, factory_for):
    company = create_company(configured_client)
    created = recommend(configured_client, company["id"], desiredEmployeeCount=4)

    session = factory_for()
    try:
        record = session.get(Recommendation, created["id"])
        assert record is not None
        assert record.company_id == company["id"]
        assert record.source == "template"
        assert record.proposed_employee_count == 4
        assert record.status is RecommendationStatus.PROPOSED
        assert record.role_catalog_version == 1
    finally:
        session.close()


def test_the_snapshot_reconstructs_the_proposal_without_the_catalogue(
    configured_client: TestClient, factory_for
):
    """The stored document stands alone: a later catalogue revision cannot alter it."""
    company = create_company(configured_client)
    created = recommend(configured_client, company["id"], desiredEmployeeCount=6)

    session = factory_for()
    try:
        record = session.get(Recommendation, created["id"])
        snapshot = record.proposal
        # Revise the role in the catalogue afterwards.
        from app.models import RoleTemplate

        session.add(
            RoleTemplate(
                key="sales",
                config_version=2,
                label="Sales (revised)",
                kind="ai",
                summary="Revised",
                responsibilities=["Only quotations"],
                task_categories=["quotation"],
                default_data_scope=[{"resource": "catalog", "operations": ["read"]}],
                default_tool_scope=[],
                default_restrictions=[],
                template_keys=["clothing"],
            )
        )
        session.commit()
    finally:
        session.close()

    after = configured_client.get(f"{RECOMMEND}/{created['id']}").json()
    assert after["proposal"] == created["proposal"]
    sales = next(e for e in after["proposal"]["employees"] if e["roleKey"] == "sales")
    assert sales["roleConfigVersion"] == 1
    assert sales["rationale"]


def test_the_snapshot_stores_money_as_exact_decimals(configured_client: TestClient, factory_for):
    company = create_company(configured_client, monthlyBudget="1000.123456")
    created = recommend(configured_client, company["id"], desiredEmployeeCount=3)

    session = factory_for()
    try:
        record = session.get(Recommendation, created["id"])
        stored = record.proposal["budget"]["companyMonthlyCeiling"]
        assert isinstance(stored, str), "money is persisted as a decimal string, never a float"
        assert stored == "1000.123456"
    finally:
        session.close()


def test_repeated_recommendations_accumulate_as_history(configured_client: TestClient):
    company = create_company(configured_client)

    first = recommend(configured_client, company["id"], desiredEmployeeCount=3)
    second = recommend(configured_client, company["id"], desiredEmployeeCount=5)

    assert first["id"] != second["id"]
    assert first["status"] == "proposed"
    assert second["status"] == "proposed"
    assert len(first["proposal"]["employees"]) == 3
    assert len(second["proposal"]["employees"]) == 5


def test_a_recommendation_starts_as_proposed_not_accepted(configured_client: TestClient):
    """Generating a proposal is not the owner accepting it."""
    company = create_company(configured_client)

    created = recommend(configured_client, company["id"])

    assert created["status"] == "proposed"
    assert stream_events(configured_client, "recommendation_accepted") == []


# -- audit ------------------------------------------------------------------


def test_generation_emits_recommendation_generated(configured_client: TestClient):
    company = create_company(configured_client)

    created = recommend(configured_client, company["id"], desiredEmployeeCount=5)

    events = stream_events(configured_client, "recommendation_generated")
    assert len(events) == 1
    payload = events[0]["payload"]
    assert payload["companyId"] == company["id"]
    assert payload["recommendationId"] == created["id"]
    assert payload["source"] == "template"
    assert payload["proposedEmployeeCount"] == 5
    assert payload["roleCatalogVersion"] == 1
    assert Decimal_check(payload["totalSuggestedMonthly"])


def Decimal_check(value) -> bool:
    from decimal import Decimal

    return Decimal(value) >= 0


def test_the_event_payload_carries_no_prompts_or_private_content(configured_client: TestClient):
    company = create_company(configured_client)
    recommend(configured_client, company["id"], notes="internal preference detail")

    event = stream_events(configured_client, "recommendation_generated")[0]
    assert set(event["payload"]) == {
        "companyId",
        "recommendationId",
        "source",
        "proposedEmployeeCount",
        "totalSuggestedMonthly",
        "roleCatalogVersion",
    }
    serialised = str(event["payload"]).lower()
    assert "internal preference detail" not in serialised


def test_configuration_events_use_real_time_and_no_workflow_offset(
    configured_client: TestClient,
):
    company = create_company(configured_client)
    recommend(configured_client, company["id"])

    event = stream_events(configured_client, "recommendation_generated")[0]
    assert event["runId"] is None
    assert event["taskId"] is None
    assert event["clockOffsetMs"] is None
    assert event["timestamp"]


def test_the_event_is_published_only_after_the_record_exists(
    configured_client: TestClient, factory_for
):
    """A subscriber reading at publication time must find the recommendation stored."""
    seen: list[str | None] = []
    probe = factory_for()

    def check_persisted(event: dict) -> None:
        if event["type"] != "recommendation_generated":
            return
        recommendation_id = event["payload"]["recommendationId"]
        probe.rollback()
        seen.append(
            recommendation_id if probe.get(Recommendation, recommendation_id) is not None else None
        )

    unsubscribe = get_event_bus().subscribe(check_persisted)
    try:
        company = create_company(configured_client)
        created = recommend(configured_client, company["id"])
    finally:
        unsubscribe()
        probe.close()

    assert seen == [created["id"]]


def test_a_failed_generation_publishes_no_success_event(configured_client: TestClient, monkeypatch):
    """A provider that blows up must not leave a phantom recommendation behind."""
    company = create_company(configured_client)

    def explode(self, request, roles, context):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(
        "app.company.recommendation_providers.TemplateProvider.recommend", explode
    )

    response = configured_client.post(RECOMMEND, json={"companyId": company["id"]})
    assert response.status_code == 422
    assert stream_events(configured_client, "recommendation_generated") == []


def test_an_invalid_provider_proposal_is_rejected_and_not_persisted(
    configured_client: TestClient, monkeypatch, factory_for
):
    """A provider claiming a role that does not exist gets nowhere near the database."""
    company = create_company(configured_client)

    def rogue(self, request, roles, context):
        return RecommendationProposal(
            company_id=context.company_id,
            source="template",
            role_catalog_version=1,
            employees=[
                {
                    "key": "proposal-employee-1",
                    "displayName": "Wizard",
                    "kind": "ai",
                    "roleKey": "wizard",  # not in the catalogue
                    "roleConfigVersion": 1,
                    "responsibilities": ["Cast spells"],
                    "rationale": "because",
                    "suggestedMonthlyBudget": "10",
                    "suggestedPerTaskBudget": "1",
                }
            ],
            budget={
                "companyMonthlyCeiling": str(context.monthly_ceiling),
                "currency": context.currency,
                "totalSuggestedMonthly": "10",
                "unallocatedMonthly": "0",
            },
        )

    monkeypatch.setattr(
        "app.company.recommendation_providers.TemplateProvider.recommend", rogue
    )

    response = configured_client.post(RECOMMEND, json={"companyId": company["id"]})
    assert response.status_code == 422
    assert "wizard" in response.json()["detail"]["detail"]
    assert stream_events(configured_client, "recommendation_generated") == []

    session = factory_for()
    try:
        assert session.query(Recommendation).filter_by(company_id=company["id"]).count() == 0
    finally:
        session.close()


def test_a_proposal_exceeding_the_ceiling_is_rejected(configured_client: TestClient, monkeypatch):
    """The ceiling is a hard rule, not a hint."""
    company = create_company(configured_client, monthlyBudget="100")

    def overspending(self, request, roles, context):
        proposal = ORIGINAL_RECOMMEND(self, request, roles, context)
        employees = [
            employee.model_copy(
                update={
                    "suggested_monthly_budget": employee.suggested_monthly_budget * 10,
                    "suggested_per_task_budget": employee.suggested_per_task_budget * 10,
                }
            )
            for employee in proposal.employees
        ]
        total = sum(
            (employee.suggested_monthly_budget for employee in employees), start=__import__(
                "decimal"
            ).Decimal("0")
        )
        return proposal.model_copy(
            update={
                "employees": employees,
                "budget": proposal.budget.model_copy(
                    update={
                        "total_suggested_monthly": total,
                        "unallocated_monthly": proposal.budget.company_monthly_ceiling - total,
                    }
                ),
            }
        )

    monkeypatch.setattr(
        "app.company.recommendation_providers.TemplateProvider.recommend", overspending
    )

    response = configured_client.post(RECOMMEND, json={"companyId": company["id"]})
    assert response.status_code == 422
    assert "exceeds the company ceiling" in response.json()["detail"]["detail"]


# -- no side effects --------------------------------------------------------


def test_generation_creates_no_employees(configured_client: TestClient, factory_for):
    company = create_company(configured_client)

    recommend(configured_client, company["id"], desiredEmployeeCount=6)

    session = factory_for()
    try:
        assert session.query(CompanyEmployee).filter_by(company_id=company["id"]).count() == 0
    finally:
        session.close()
    assert configured_client.get(f"/api/companies/{company['id']}/employees").json() == []


def test_generation_creates_no_contracts_and_does_not_activate(configured_client: TestClient, factory_for):
    company = create_company(configured_client)

    recommend(configured_client, company["id"], desiredEmployeeCount=6)

    session = factory_for()
    try:
        assert session.query(Contract).filter_by(company_id=company["id"]).count() == 0
        stored = session.get(Company, company["id"])
        assert stored.status is CompanyStatus.DRAFT
        assert stored.revision == 1, "recommending is not a configuration change"
    finally:
        session.close()


def test_generation_does_not_touch_the_canonical_agents(configured_client: TestClient, factory_for):
    company = create_company(configured_client)

    recommend(configured_client, company["id"], desiredEmployeeCount=6)

    session = factory_for()
    try:
        assert {row.id for row in session.query(Agent).all()} == DEMO_AGENT_IDS
    finally:
        session.close()


def test_generation_does_not_move_the_budget_account(configured_client: TestClient, factory_for):
    company = create_company(configured_client, monthlyBudget="2500")

    recommend(configured_client, company["id"], desiredEmployeeCount=6)

    session = factory_for()
    try:
        account = session.query(BudgetAccount).filter_by(company_id=company["id"]).one()
        assert account.monthly_limit == 2500
        assert account.version == 1
    finally:
        session.close()


# -- provider seam ----------------------------------------------------------


def test_the_template_provider_is_registered_and_needs_no_credentials(configured_client: TestClient):
    assert "template" in available_providers()

    provider = get_provider("template")
    assert provider.source == "template"
    # A template proposal names no provider and no model.
    assert provider.identify() == (None, None)


def test_a_missing_company_works_without_any_credential_configured(configured_client: TestClient):
    """A 404 proves the request reached the service at all."""
    assert configured_client.post(RECOMMEND, json={"companyId": "cmp_none"}).status_code == 404


def test_requesting_a_model_provider_falls_back_and_says_so(configured_client: TestClient, factory_for):
    """The fallback is labelled as the template, never as a model result."""
    company = create_company(configured_client)

    service = RecommendationService(factory_for())
    try:
        provider, fell_back = resolve_provider(
            service._session,
            settings=Settings(RECOMMENDATION_PROVIDER="model"),
            build=service._build_model_provider,
        )
    finally:
        service._session.close()

    assert fell_back is True
    assert provider.name == "template"
    assert provider.source == "template"


def test_requesting_a_model_provider_marks_the_response_as_fallback(configured_client: TestClient, monkeypatch):
    company = create_company(configured_client)
    monkeypatch.setenv("RECOMMENDATION_PROVIDER", "model")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        created = recommend(configured_client, company["id"], desiredEmployeeCount=4)
    finally:
        get_settings.cache_clear()

    assert created["proposal"]["source"] == "template"
    assert created["proposal"]["providerName"] is None
    assert created["proposal"]["modelName"] is None
    assert any(
        "template fallback" in warning for warning in created["proposal"]["warnings"]
    )


def test_a_template_result_is_never_labelled_as_a_model(configured_client: TestClient):
    company = create_company(configured_client)

    proposal = recommend(configured_client, company["id"])["proposal"]

    assert proposal["source"] == "template"
    assert proposal["providerName"] is None
    assert proposal["modelName"] is None


def test_a_provider_cannot_grant_a_role_the_template_does_not_offer(configured_client: TestClient, monkeypatch):
    """The validator is the authority on what a proposal may contain."""
    company = create_company(configured_client, templateKey="custom")

    def rogue(self, request, roles, context):
        base = ORIGINAL_RECOMMEND(self, request, roles, context)
        # Force in a role the custom template does not offer.
        employee = base.employees[-1].model_copy(
            update={"role_key": "sales", "role_config_version": 1}
        )
        return base.model_copy(update={"employees": [*base.employees[:-1], employee]})

    monkeypatch.setattr(
        "app.company.recommendation_providers.TemplateProvider.recommend", rogue
    )

    response = configured_client.post(RECOMMEND, json={"companyId": company["id"]})
    assert response.status_code == 422
    assert "not offered" in response.json()["detail"]["detail"]


def test_a_provider_cannot_introduce_a_reporting_cycle(configured_client: TestClient, monkeypatch):
    company = create_company(configured_client)

    def cyclic(self, request, roles, context):
        base = ORIGINAL_RECOMMEND(self, request, roles, context)
        employees = list(base.employees)
        # Make the top seat report to a subordinate: a cycle.
        employees[0] = employees[0].model_copy(
            update={"reports_to_key": employees[-1].key}
        )
        return base.model_copy(update={"employees": employees})

    monkeypatch.setattr(
        "app.company.recommendation_providers.TemplateProvider.recommend", cyclic
    )

    response = configured_client.post(RECOMMEND, json={"companyId": company["id"]})
    assert response.status_code == 422
    assert "cycle" in response.json()["detail"]["detail"]


def test_validator_refuses_a_proposal_that_contradicts_its_own_totals(configured_client: TestClient, factory_for):
    """Totals are checked against the parts, not merely reported."""
    company = create_company(configured_client)
    service = RecommendationService(factory_for())
    try:
        loaded = service._companies.get_company(company["id"])
        ceiling = service._current_ceiling(loaded)
        catalogue = {role.key: role for role in service._catalogue()}
        proposal = RecommendationProposal(
            company_id=company["id"],
            source="template",
            role_catalog_version=1,
            employees=[
                {
                    "key": "proposal-employee-1",
                    "displayName": "Owner",
                    "kind": "human",
                    "roleKey": "ceo",
                    "roleConfigVersion": 1,
                    "responsibilities": ["Decide"],
                    "rationale": "because",
                    "suggestedMonthlyBudget": "10",
                    "suggestedPerTaskBudget": "5",
                }
            ],
            budget={
                "companyMonthlyCeiling": str(ceiling),
                "currency": "USD",
                # Deliberately inconsistent with the single 10 allocation.
                "totalSuggestedMonthly": "999",
                "unallocatedMonthly": "0",
            },
        )
        with pytest.raises(Exception) as caught:
            validate_proposal(
                proposal,
                catalogue=catalogue,
                offered_role_keys=["ceo", "manager", "hr", "support"],
                monthly_ceiling=ceiling,
                currency="USD",
            )
        assert "does not match" in str(caught.value)
    finally:
        service._session.close()