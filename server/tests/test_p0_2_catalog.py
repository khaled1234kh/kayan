"""P0.2 setup catalogue: templates and versioned roles.

The roles endpoint must serve what is *in the database*, not a list compiled into
the handler — otherwise the seeded catalogue and the API could quietly disagree.
These tests assert the shape, the ordering, the filtering, and that only the current
version of a redefined role is exposed.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.company.templates import TEMPLATE_KEYS
from app.models import RoleTemplate


def test_templates_are_listed_with_the_expected_shape(configured_client: TestClient):
    response = configured_client.get("/api/setup/templates")
    assert response.status_code == 200

    templates = response.json()
    assert [row["key"] for row in templates] == list(TEMPLATE_KEYS)
    for template in templates:
        assert template["label"]
        assert template["summary"]
        assert isinstance(template["roleKeys"], list) and template["roleKeys"]
        assert isinstance(template["taskCategories"], list) and template["taskCategories"]
        assert isinstance(template["industries"], list)


def test_template_listing_is_stable_across_calls(configured_client: TestClient):
    first = configured_client.get("/api/setup/templates").json()
    second = configured_client.get("/api/setup/templates").json()
    assert first == second


def test_roles_are_listed_with_the_expected_shape(configured_client: TestClient):
    response = configured_client.get("/api/setup/roles")
    assert response.status_code == 200

    roles = response.json()
    keys = {row["key"] for row in roles}
    assert {"ceo", "manager", "sales", "operations", "hr", "support"} <= keys

    sales = next(row for row in roles if row["key"] == "sales")
    assert sales["label"]
    assert sales["kind"] == "ai"
    assert sales["responsibilities"]
    assert sales["defaultDataScope"]
    assert sales["defaultToolScope"]
    assert sales["defaultRestrictions"]
    assert "clothing" in sales["templateKeys"]
    assert sales["configVersion"] == 1


def test_roles_come_from_the_database(configured_client: TestClient, factory_for):
    """A role edited in the database is what the endpoint serves."""
    session = factory_for()
    try:
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

    roles = configured_client.get("/api/setup/roles").json()
    sales_versions = [row for row in roles if row["key"] == "sales"]
    assert len(sales_versions) == 1, "only the current version may be exposed"
    assert sales_versions[0]["configVersion"] == 2
    assert sales_versions[0]["label"] == "Sales (revised)"


def test_roles_can_be_filtered_by_template(configured_client: TestClient):
    clothing = configured_client.get("/api/setup/roles", params={"template_key": "clothing"})
    assert clothing.status_code == 200

    roles = clothing.json()
    assert {row["key"] for row in roles} == {
        "ceo",
        "manager",
        "sales",
        "operations",
        "hr",
        "support",
    }
    assert all("clothing" in row["templateKeys"] for row in roles)


def test_template_filtering_narrows_the_result(configured_client: TestClient):
    """The custom template offers fewer roles, and the filter must show that."""
    custom = configured_client.get("/api/setup/roles", params={"template_key": "custom"})
    assert custom.status_code == 200
    assert {row["key"] for row in custom.json()} == {"ceo", "manager", "hr", "support"}


def test_an_unknown_template_filter_is_refused(configured_client: TestClient):
    response = configured_client.get("/api/setup/roles", params={"template_key": "nope"})
    assert response.status_code == 422
    assert response.json()["detail"]["field"] == "templateKey"
    assert "not a supported template" in response.json()["detail"]["detail"]


def test_role_ordering_is_deterministic(configured_client: TestClient):
    first = configured_client.get("/api/setup/roles").json()
    second = configured_client.get("/api/setup/roles").json()

    assert [row["key"] for row in first] == [row["key"] for row in second]
    assert [row["key"] for row in first] == sorted(row["key"] for row in first)