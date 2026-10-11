"""P0.3 recommendation behaviour, through the API.

Organised around the claims the feature makes: a proposal is derived from the
company's saved configuration, it is deterministic, it fits inside the budget it was
given, it never becomes a configuration change, and it is only ever announced after
it has been stored.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.company.templates import CLOTHING, CUSTOM, CUSTOMIZED_GIFTS
from app.models import (
    Agent,
    BudgetAccount,
    Company,
    CompanyEmployee,
    CompanyStatus,
    Contract,
    Recommendation,
)
from tests.p0_2_helpers import COMPANY_PAYLOAD, DEMO_AGENT_IDS, create_company

RECOMMEND = "/api/setup/recommendations"


def recommend(client: TestClient, company_id: str, **preferences):
    body: dict = {"companyId": company_id}
    if preferences:
        body["preferences"] = preferences
    response = client.post(RECOMMEND, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def roles_of(proposal: dict) -> list[str]:
    return [employee["roleKey"] for employee in proposal["employees"]]


# -- template coverage ------------------------------------------------------


@pytest.mark.parametrize(
    ("template", "expected_ceiling_roles"),
    [
        (CLOTHING, {"ceo", "manager", "sales", "operations", "hr", "support"}),
        (CUSTOMIZED_GIFTS, {"ceo", "manager", "sales", "operations", "hr", "support"}),
        (CUSTOM, {"ceo", "manager", "hr", "support"}),
    ],
)
def test_recommendations_only_use_roles_the_template_offers(
    configured_client: TestClient, template, expected_ceiling_roles
):
    company = create_company(configured_client, templateKey=template)

    proposal = recommend(configured_client, company["id"], desiredEmployeeCount=6)["proposal"]

    assert set(roles_of(proposal)) <= expected_ceiling_roles
    assert proposal["source"] == "template"


def test_custom_template_stays_inside_its_smaller_catalogue(configured_client: TestClient):
    """The custom template does not offer sales or operations, and must not invent them."""
    company = create_company(configured_client, templateKey=CUSTOM)

    proposal = recommend(configured_client, company["id"], desiredEmployeeCount=20)["proposal"]

    assert set(roles_of(proposal)) <= {"ceo", "manager", "hr", "support"}
    assert any("no further roles" in warning for warning in proposal["warnings"])


def test_every_proposed_role_is_a_seeded_catalogue_role(configured_client: TestClient):
    company = create_company(configured_client)
    available = {role["key"] for role in configured_client.get("/api/setup/roles").json()}

    proposal = recommend(configured_client, company["id"], desiredEmployeeCount=6)["proposal"]

    assert set(roles_of(proposal)) <= available


# -- determinism ------------------------------------------------------------


def test_identical_input_yields_an_identical_proposal(configured_client: TestClient):
    company = create_company(configured_client)

    first = recommend(configured_client, company["id"], desiredEmployeeCount=4)["proposal"]
    second = recommend(configured_client, company["id"], desiredEmployeeCount=4)["proposal"]

    assert first == second


def test_identical_input_across_companies_yields_the_same_shape(configured_client: TestClient):
    """Same catalogue, same preferences: the proposal differs only by company id."""
    one = create_company(configured_client, name="Brand One")
    two = create_company(configured_client, name="Brand Two")

    first = recommend(configured_client, one["id"], desiredEmployeeCount=5)["proposal"]
    second = recommend(configured_client, two["id"], desiredEmployeeCount=5)["proposal"]

    assert first["roleCatalogVersion"] == second["roleCatalogVersion"]
    assert roles_of(first) == roles_of(second)
    assert first["budget"] == second["budget"]


# -- preferences ------------------------------------------------------------


def test_requested_count_is_respected_when_the_template_allows_it(configured_client: TestClient):
    company = create_company(configured_client)

    for count in (2, 3, 4, 5, 6):
        proposal = recommend(
            configured_client, company["id"], desiredEmployeeCount=count
        )["proposal"]
        assert len(proposal["employees"]) == count


def test_a_small_request_keeps_the_decision_makers(configured_client: TestClient):
    """Trimming a small roster must not remove the seat that authorises anything."""
    company = create_company(configured_client)

    proposal = recommend(configured_client, company["id"], desiredEmployeeCount=2)["proposal"]

    assert roles_of(proposal) == ["ceo", "manager"]


def test_omitting_the_human_seat_is_honoured_and_flagged(configured_client: TestClient):
    company = create_company(configured_client)

    proposal = recommend(
        configured_client, company["id"], includeHumanEmployee=False
    )["proposal"]

    assert "ceo" not in roles_of(proposal)
    assert any("human decision-maker" in warning for warning in proposal["warnings"])


def test_omitting_hr_is_honoured_and_flagged(configured_client: TestClient):
    company = create_company(configured_client)

    proposal = recommend(configured_client, company["id"], includeHR=False)["proposal"]

    assert "hr" not in roles_of(proposal)
    assert any("HR role omitted" in warning for warning in proposal["warnings"])


def test_more_seats_are_not_automatically_better(configured_client: TestClient):
    """Asking for 20 yields the 6 distinct roles, and says why it stopped there."""
    company = create_company(configured_client)

    proposal = recommend(configured_client, company["id"], desiredEmployeeCount=20)["proposal"]

    assert len(proposal["employees"]) == 6
    assert len({role for role in roles_of(proposal)}) == len(proposal["employees"])
    assert any("repeat existing work" in warning for warning in proposal["warnings"])


def test_notes_are_recorded_in_the_snapshot(configured_client: TestClient):
    company = create_company(configured_client)

    result = recommend(
        configured_client,
        company["id"],
        notes="Prioritise order fulfilment and customer service.",
    )

    assert result["preferences"]["notes"] == "Prioritise order fulfilment and customer service."


# -- preference validation --------------------------------------------------


@pytest.mark.parametrize(
    "preferences",
    [
        {"desiredEmployeeCount": 0},
        {"desiredEmployeeCount": -3},
        {"desiredEmployeeCount": 10_000},
        {"desiredEmployeeCount": "many"},
        {"notes": ""},
        {"unknownPreference": True},
    ],
)
def test_invalid_preferences_are_refused(configured_client: TestClient, preferences):
    company = create_company(configured_client)

    response = configured_client.post(
        RECOMMEND, json={"companyId": company["id"], "preferences": preferences}
    )
    assert response.status_code == 422


def test_oversized_notes_are_refused(configured_client: TestClient):
    company = create_company(configured_client)

    response = configured_client.post(
        RECOMMEND,
        json={"companyId": company["id"], "preferences": {"notes": "x" * 2001}},
    )
    assert response.status_code == 422


def test_a_company_missing_from_the_request_is_refused(configured_client: TestClient):
    assert configured_client.post(RECOMMEND, json={}).status_code == 422


def test_duplicated_company_configuration_in_the_request_is_refused(configured_client: TestClient):
    """Budget and template belong to the company; restating them invites a stale copy."""
    company = create_company(configured_client)

    response = configured_client.post(
        RECOMMEND,
        json={
            "companyId": company["id"],
            "monthlyBudget": "999999",
            "preferences": {"desiredEmployeeCount": 4},
        },
    )
    assert response.status_code == 422


# -- lifecycle --------------------------------------------------------------


def test_an_unknown_company_is_404(configured_client: TestClient):
    response = configured_client.post(RECOMMEND, json={"companyId": "cmp_missing"})
    assert response.status_code == 404


def test_a_non_draft_company_is_409(configured_client: TestClient, factory_for):
    company = create_company(configured_client)

    session = factory_for()
    try:
        stored = session.get(Company, company["id"])
        stored.status = CompanyStatus.ACTIVE
        session.commit()
    finally:
        session.close()

    response = configured_client.post(RECOMMEND, json={"companyId": company["id"]})
    assert response.status_code == 409
    assert response.json()["detail"]["field"] == "status"


def test_an_unknown_recommendation_is_404(configured_client: TestClient):
    assert configured_client.get(f"{RECOMMEND}/rec_missing").status_code == 404


# -- reporting and structure ------------------------------------------------


def test_reporting_lines_form_a_valid_hierarchy(configured_client: TestClient):
    company = create_company(configured_client)

    proposal = recommend(configured_client, company["id"], desiredEmployeeCount=6)["proposal"]

    employees = proposal["employees"]
    keys = {employee["key"] for employee in employees}
    top = [employee for employee in employees if employee["reportsToKey"] is None]
    assert len(top) == 1, "exactly one seat reports to nobody"
    for employee in employees:
        if employee["reportsToKey"] is not None:
            assert employee["reportsToKey"] in keys
        # A seat never supervises itself.
        assert employee["reportsToKey"] != employee["key"]


def test_specialists_report_to_the_manager(configured_client: TestClient):
    company = create_company(configured_client)

    employees = recommend(
        configured_client, company["id"], desiredEmployeeCount=6
    )["proposal"]["employees"]

    manager = next(employee for employee in employees if employee["roleKey"] == "manager")
    for employee in employees:
        if employee["roleKey"] not in {"ceo", "manager"}:
            assert employee["reportsToKey"] == manager["key"]


def test_proposal_keys_are_stable_and_never_display_names(configured_client: TestClient):
    company = create_company(configured_client)

    employees = recommend(
        configured_client, company["id"], desiredEmployeeCount=6
    )["proposal"]["employees"]

    keys = [employee["key"] for employee in employees]
    assert keys == [f"proposal-employee-{index + 1}" for index in range(len(keys))]
    labels = {employee["displayName"] for employee in employees}
    assert not (set(keys) & labels)


def test_communication_is_targeted_and_broadcast_is_reserved(configured_client: TestClient):
    """Least privilege: only the most senior seat may broadcast."""
    company = create_company(configured_client)

    employees = recommend(
        configured_client, company["id"], desiredEmployeeCount=6
    )["proposal"]["employees"]

    broadcasters = [employee for employee in employees if employee["communication"]["broadcast"]]
    assert len(broadcasters) == 1
    assert broadcasters[0]["reportsToKey"] is None
    for employee in employees:
        if employee is not broadcasters[0]:
            assert employee["communication"]["broadcast"] is False
            # Every targeted channel resolves to a proposed seat.
            assert employee["communication"]["allow"]


def test_scopes_and_restrictions_are_carried_from_the_catalogue(configured_client: TestClient):
    company = create_company(configured_client)

    employees = recommend(
        configured_client, company["id"], desiredEmployeeCount=6
    )["proposal"]["employees"]

    manager = next(employee for employee in employees if employee["roleKey"] == "manager")
    assert manager["restrictions"], "a manager role carries restrictions in the catalogue"
    assert manager["dataScope"]
    assert manager["toolScope"]
    assert manager["roleConfigVersion"] == 1
    for employee in employees:
        for entry in employee["dataScope"]:
            assert entry["resource"] and entry["operations"]


def test_every_seat_explains_itself(configured_client: TestClient):
    company = create_company(configured_client)

    employees = recommend(
        configured_client, company["id"], desiredEmployeeCount=6
    )["proposal"]["employees"]

    for employee in employees:
        assert employee["rationale"].strip()
        assert employee["objective"].strip()
        assert employee["responsibilities"]
        assert str(employee["suggestedMonthlyBudget"]) in employee["rationale"]


# -- budget -----------------------------------------------------------------


def test_allocations_never_exceed_the_company_ceiling(configured_client: TestClient, factory_for):
    company = create_company(configured_client, monthlyBudget="1234.567891")

    proposal = recommend(configured_client, company["id"], desiredEmployeeCount=6)["proposal"]

    total = sum(
        (Decimal(employee["suggestedMonthlyBudget"]) for employee in proposal["employees"]),
        Decimal("0"),
    )
    ceiling = Decimal(proposal["budget"]["companyMonthlyCeiling"])
    assert total <= ceiling
    assert total == Decimal(proposal["budget"]["totalSuggestedMonthly"])
    assert proposal["budget"]["unallocatedMonthly"] == str(ceiling - total)


def test_per_task_ceiling_never_exceeds_the_monthly_allocation(configured_client: TestClient):
    company = create_company(configured_client)

    employees = recommend(
        configured_client, company["id"], desiredEmployeeCount=6
    )["proposal"]["employees"]

    for employee in employees:
        assert Decimal(employee["suggestedPerTaskBudget"]) <= Decimal(
            employee["suggestedMonthlyBudget"]
        )


def test_decimal_precision_is_preserved_end_to_end(configured_client: TestClient):
    """Money must not become a float anywhere in the round trip."""
    company = create_company(configured_client, monthlyBudget="1000.000001")

    result = recommend(configured_client, company["id"], desiredEmployeeCount=4)

    assert result["proposal"]["budget"]["companyMonthlyCeiling"] == "1000.000001"
    stored = configured_client.get(f"{RECOMMEND}/{result['id']}")
    assert stored.json()["proposal"]["budget"] == result["proposal"]["budget"]
    for employee in result["proposal"]["employees"]:
        assert Decimal(employee["suggestedMonthlyBudget"]) == Decimal(
            employee["suggestedMonthlyBudget"]
        )


def test_allocation_adapts_to_a_very_small_ceiling(configured_client: TestClient):
    company = create_company(configured_client, monthlyBudget="0.000006")

    proposal = recommend(configured_client, company["id"], desiredEmployeeCount=6)["proposal"]

    total = sum(
        (Decimal(employee["suggestedMonthlyBudget"]) for employee in proposal["employees"]),
        Decimal("0"),
    )
    assert total <= Decimal("0.000006")


def test_a_recommendation_does_not_move_any_budget_record(
    configured_client: TestClient, factory_for
):
    """A proposal allocates; it never spends, reserves or charges."""
    company = create_company(configured_client, monthlyBudget="4000")

    before = configured_client.get(f"/api/companies/{company['id']}").json()["monthlyBudget"]
    recommend(configured_client, company["id"], desiredEmployeeCount=6)

    session = factory_for()
    try:
        account = session.query(BudgetAccount).filter_by(company_id=company["id"]).one()
        assert Decimal(str(account.monthly_limit)) == Decimal("4000")
        assert account.version == 1
        assert session.query(Contract).filter_by(company_id=company["id"]).count() == 0
    finally:
        session.close()
    assert configured_client.get(f"/api/companies/{company['id']}").json()["monthlyBudget"] == before