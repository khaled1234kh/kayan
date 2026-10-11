"""P0.2 workforce replacement.

``PUT`` states the complete desired workforce, so the tests here are written as
transitions between whole states rather than as single-call checks: create, edit by
stable id, add, remove, and — most importantly — prove that a rejected request
leaves the previous workforce untouched.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.models import Agent, CompanyEmployee, CompanyStatus, EmployeeStatus
from tests.p0_2_helpers import (
    DEMO_AGENT_IDS,
    create_company,
    seat,
    set_company_status,
    workforce,
)


def put_workforce(client: TestClient, company_id: str, *seats):
    return client.put(f"/api/companies/{company_id}/workforce", json=workforce(*seats))


def employees_of(client: TestClient, company_id: str) -> list[dict]:
    response = client.get(f"/api/companies/{company_id}/employees")
    assert response.status_code == 200, response.text
    return response.json()


# -- creation --------------------------------------------------------------


def test_create_a_workforce_with_one_employee(configured_client: TestClient):
    company = create_company(configured_client)

    response = put_workforce(configured_client, company["id"], seat("Alex Manager", "manager"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["employeeCount"] == 1
    assert body["companyId"] == company["id"]

    employee = body["employees"][0]
    assert employee["displayName"] == "Alex Manager"
    assert employee["roleKey"] == "manager"
    assert employee["kind"] == "ai"
    assert employee["status"] == "draft"
    assert employee["id"].startswith("emp_")


def test_create_and_retrieve_at_least_twenty_employees(configured_client: TestClient):
    """P0.2 must not retain the five-actor demo limit."""
    company = create_company(configured_client)

    response = put_workforce(
        configured_client,
        company["id"],
        *[seat(f"Agent {index:02d}", "sales") for index in range(25)],
    )
    assert response.status_code == 200, response.text
    assert response.json()["employeeCount"] == 25

    stored = employees_of(configured_client, company["id"])
    assert len(stored) == 25
    assert len({row["id"] for row in stored}) == 25


def test_employee_ids_are_generated_and_names_are_never_ids(configured_client: TestClient):
    company = create_company(configured_client)

    put_workforce(
        configured_client,
        company["id"],
        seat("Alex", "sales"),
        seat("Alex", "manager"),
    )
    stored = employees_of(configured_client, company["id"])
    ids = {row["id"] for row in stored}

    assert len(ids) == 2
    # Two employees share a display name; their identities must not.
    assert "Alex" not in ids


def test_workforce_never_inserts_into_the_canonical_agents_table(
    configured_client: TestClient, factory_for
):
    company = create_company(configured_client)
    put_workforce(
        configured_client,
        company["id"],
        *[seat(f"Agent {index}", "sales") for index in range(5)],
    )

    session = factory_for()
    try:
        assert {row.id for row in session.query(Agent).all()} == DEMO_AGENT_IDS
    finally:
        session.close()


# -- editing and replacement semantics --------------------------------------


def test_edit_an_existing_employee_by_its_stable_id(configured_client: TestClient):
    company = create_company(configured_client)
    first = put_workforce(
        configured_client, company["id"], seat("Alex", "sales"), seat("Sam", "operations")
    ).json()
    # Look seats up by name rather than by position: the listing is ordered by
    # creation, not by the order the seats happened to appear in the request.
    alex = next(row for row in first["employees"] if row["displayName"] == "Alex")
    sam = next(row for row in first["employees"] if row["displayName"] == "Sam")

    response = put_workforce(
        configured_client,
        company["id"],
        {**seat("Alex Renamed", "sales"), "id": alex["id"], "objective": "Close more orders"},
        sam,
    )
    assert response.status_code == 200, response.text

    stored = {row["id"]: row for row in employees_of(configured_client, company["id"])}
    assert len(stored) == 2, "editing must not create a second seat"
    assert stored[alex["id"]]["displayName"] == "Alex Renamed"
    assert stored[alex["id"]]["objective"] == "Close more orders"


def test_omitted_employees_are_removed(configured_client: TestClient, factory_for):
    """Replacement, not merge: what is absent from the request is gone."""
    company = create_company(configured_client)
    first = put_workforce(
        configured_client,
        company["id"],
        seat("Alex", "sales"),
        seat("Sam", "operations"),
        seat("Robin", "hr"),
    ).json()
    keep = first["employees"][0]["id"]

    response = put_workforce(configured_client, company["id"], first["employees"][0])
    assert response.status_code == 200, response.text
    assert response.json()["employeeCount"] == 1

    stored = employees_of(configured_client, company["id"])
    assert [row["id"] for row in stored] == [keep]

    session = factory_for()
    try:
        assert session.query(CompanyEmployee).filter_by(company_id=company["id"]).count() == 1
    finally:
        session.close()


def test_adding_and_removing_in_one_request(configured_client: TestClient):
    company = create_company(configured_client)
    first = put_workforce(
        configured_client, company["id"], seat("Alex", "sales"), seat("Sam", "operations")
    ).json()
    alex = next(row for row in first["employees"] if row["displayName"] == "Alex")
    sam = next(row for row in first["employees"] if row["displayName"] == "Sam")

    response = put_workforce(
        configured_client,
        company["id"],
        alex,  # kept
        seat("New Hire", "support"),  # added
        seat("Another", "hr"),  # added
    )
    assert response.status_code == 200, response.text

    stored = employees_of(configured_client, company["id"])
    names = {row["displayName"] for row in stored}
    assert names == {"Alex", "New Hire", "Another"}
    assert sam["id"] not in {row["id"] for row in stored}


def test_responsibilities_default_to_empty_and_may_be_overridden(configured_client: TestClient):
    company = create_company(configured_client)

    response = put_workforce(
        configured_client,
        company["id"],
        seat("Plain", "sales"),
        seat("Specific", "sales", responsibilities=["Answer calls", "Prepare quotes"]),
    )
    assert response.status_code == 200, response.text

    stored = {row["displayName"]: row for row in employees_of(configured_client, company["id"])}
    assert stored["Plain"]["responsibilities"] == []
    assert stored["Specific"]["responsibilities"] == ["Answer calls", "Prepare quotes"]


def test_custom_role_requires_a_description(configured_client: TestClient):
    company = create_company(configured_client)

    ok = put_workforce(
        configured_client, company["id"], seat("Bespoke", "custom", customRole="Head of Things")
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["employees"][0]["customRole"] == "Head of Things"

    missing = put_workforce(configured_client, company["id"], seat("Bespoke", "custom"))
    assert missing.status_code == 422


# -- validation ------------------------------------------------------------


def test_duplicate_employee_ids_are_rejected(configured_client: TestClient):
    company = create_company(configured_client)

    response = put_workforce(
        configured_client,
        company["id"],
        {"id": "emp_fixed", **seat("Alex", "sales")},
        {"id": "emp_fixed", **seat("Sam", "sales")},
    )
    assert response.status_code == 422
    assert "more than once" in response.json()["detail"]["detail"]


def test_an_id_from_another_company_is_rejected(configured_client: TestClient):
    first = create_company(configured_client, name="First")
    second = create_company(configured_client, name="Second")

    created = put_workforce(configured_client, first["id"], seat("Alex", "sales")).json()
    intruder_id = created["employees"][0]["id"]

    response = put_workforce(
        configured_client,
        second["id"],
        {"id": intruder_id, **seat("Mallory", "sales")},
    )
    assert response.status_code == 422
    assert "another company" in response.json()["detail"]["detail"]

    # The other company's roster is untouched.
    assert len(employees_of(configured_client, first["id"])) == 1


def test_an_unknown_employee_id_is_rejected(configured_client: TestClient):
    company = create_company(configured_client)

    response = put_workforce(
        configured_client, company["id"], {"id": "emp_nonexistent", **seat("Ghost", "sales")}
    )
    assert response.status_code == 422


def test_an_unknown_role_is_rejected(configured_client: TestClient):
    company = create_company(configured_client)

    response = put_workforce(configured_client, company["id"], seat("Alex", "wizard"))
    assert response.status_code == 422
    assert "not a known role" in response.json()["detail"]["detail"]


def test_a_role_outside_the_company_template_is_rejected(configured_client: TestClient):
    """The custom template does not offer every role, and the API must say so."""
    company = create_company(configured_client, templateKey="custom")

    refused = put_workforce(configured_client, company["id"], seat("Alex", "sales"))
    assert refused.status_code == 422
    assert "not available for template" in refused.json()["detail"]["detail"]

    allowed = put_workforce(configured_client, company["id"], seat("Alex", "manager"))
    assert allowed.status_code == 200, allowed.text


def test_workforce_replacement_is_refused_once_the_company_is_not_draft(
    configured_client: TestClient, factory_for
):
    for status in (CompanyStatus.ACTIVE, CompanyStatus.PAUSED):
        company = create_company(configured_client, name=f"Brand {status.value}")
        put_workforce(configured_client, company["id"], seat("Alex", "sales"))
        set_company_status(factory_for, company["id"], status)

        response = put_workforce(
            configured_client, company["id"], seat("Alex", "sales"), seat("Sam", "manager")
        )
        assert response.status_code == 409, status.value


def test_workforce_for_an_unknown_company_is_404(configured_client: TestClient):
    response = put_workforce(configured_client, "cmp_missing", seat("Alex", "sales"))
    assert response.status_code == 404


def test_employees_for_an_unknown_company_is_404(configured_client: TestClient):
    assert configured_client.get("/api/companies/cmp_missing/employees").status_code == 404


def test_an_empty_workforce_is_rejected(configured_client: TestClient):
    company = create_company(configured_client)

    response = configured_client.put(
        f"/api/companies/{company['id']}/workforce", json={"employees": []}
    )
    assert response.status_code == 422


# -- atomicity -------------------------------------------------------------


def test_a_failed_replacement_leaves_the_original_workforce_intact(configured_client: TestClient):
    """The whole point of validating before writing."""
    company = create_company(configured_client)
    original = put_workforce(
        configured_client,
        company["id"],
        seat("Alex", "sales"),
        seat("Sam", "operations"),
    ).json()
    before = employees_of(configured_client, company["id"])

    # Valid seats, but the last one reports to itself.
    response = put_workforce(
        configured_client,
        company["id"],
        original["employees"][0],
        {**seat("Loop", "manager"), "id": "emp_loop", "reportsToId": "emp_loop"},
        {**seat("Sam", "operations"), "id": original["employees"][1]["id"]},
    )
    assert response.status_code == 422

    after = employees_of(configured_client, company["id"])
    assert [(row["id"], row["displayName"]) for row in after] == [
        (row["id"], row["displayName"]) for row in before
    ]


def test_a_failed_replacement_does_not_remove_employees(configured_client: TestClient):
    """Even seats the request never mentioned must survive a rejected request."""
    company = create_company(configured_client)
    original = put_workforce(
        configured_client,
        company["id"],
        seat("Alex", "sales"),
        seat("Sam", "operations"),
        seat("Robin", "hr"),
    ).json()
    before = {row["id"] for row in employees_of(configured_client, company["id"])}

    response = put_workforce(
        configured_client,
        company["id"],
        original["employees"][0],  # omits Sam and Robin...
        {**seat("Loop", "manager"), "id": "emp_loop", "reportsToId": "emp_loop"},
    )
    assert response.status_code == 422

    after = {row["id"] for row in employees_of(configured_client, company["id"])}
    assert after == before


def test_no_employee_row_is_left_behalf_written(configured_client: TestClient, factory_for):
    """A rejected request must not persist partial seat data either."""
    company = create_company(configured_client)

    response = put_workforce(
        configured_client,
        company["id"],
        seat("Valid", "sales"),
        {**seat("Bad", "manager"), "id": "emp_bad", "reportsToId": "emp_bad"},
    )
    assert response.status_code == 422

    session = factory_for()
    try:
        assert session.query(CompanyEmployee).filter_by(company_id=company["id"]).count() == 0
    finally:
        session.close()


# -- persistence -----------------------------------------------------------


def test_workforce_persists_across_sessions(configured_client: TestClient, factory_for):
    company = create_company(configured_client)
    created = put_workforce(configured_client, company["id"], seat("Alex", "sales")).json()

    session = factory_for()
    try:
        row = session.get(CompanyEmployee, created["employees"][0]["id"])
        assert row is not None
        assert row.display_name == "Alex"
        assert row.company_id == company["id"]
        assert row.status is EmployeeStatus.DRAFT
    finally:
        session.close()


def test_employees_stay_in_the_configured_employee_id_space(configured_client: TestClient):
    company = create_company(configured_client)
    put_workforce(configured_client, company["id"], *[seat(f"A{i}", "sales") for i in range(3)])

    for row in employees_of(configured_client, company["id"]):
        assert row["id"].startswith("emp_")
        assert row["id"] not in DEMO_AGENT_IDS