"""Shared setup for the P0.4 contract lifecycle tests.

Building a company with a workforce and contracts is the same shape in every test,
so it lives here once. The helpers return ids rather than objects, because most
assertions are about what the *next* call sees.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from app.company.contract_terms import compute_content_hash
from app.models import Company, CompanyStatus, Contract, ContractStatus
from app.services.companies import CompanyService
from app.services.contracts import ContractService
from app.services.workforce import WorkforceService
from app.schemas.company import CompanyCreate, EmployeeIn, WorkforceReplace
from app.schemas.contract import (
    ContractGenerateRequest,
    EmployeeAllocation,
    ResumeRequest,
)

CEILING = "4000"


def make_company(session, **overrides) -> Company:
    values: dict[str, Any] = {
        "name": "P0.4 Brand",
        "template_key": "clothing",
        "monthly_budget": Decimal(CEILING),
        "currency": "USD",
        "target_metric": "revenue",
        "target_value": Decimal("100000"),
    }
    values.update(overrides)
    payload = {
        "name": values["name"],
        "templateKey": values["template_key"],
        "monthlyBudget": str(values["monthly_budget"]),
        "currency": values["currency"],
        "targetMetric": values.get("target_metric"),
        "targetValue": (
            None if values.get("target_value") is None else str(values["target_value"])
        ),
    }
    return CompanyService(session).create_company(CompanyCreate(**payload))


def make_workforce(session, company_id: str) -> list[str]:
    """A three-seat workforce: a human owner, a manager and a seller under them."""
    workforce = WorkforceService(session)
    owner = workforce.replace_workforce(
        company_id,
        WorkforceReplace(employees=[EmployeeIn(displayName="Owner", kind="human", roleKey="ceo")]),
    ).employees[0]
    result = workforce.replace_workforce(
        company_id,
        WorkforceReplace(
            employees=[
                EmployeeIn(id=owner.id, displayName="Owner", kind="human", roleKey="ceo"),
                EmployeeIn(displayName="Boss", kind="ai", roleKey="manager", reportsToId=owner.id),
                EmployeeIn(displayName="Seller", kind="ai", roleKey="sales", reportsToId=owner.id),
            ]
        ),
    )
    return [employee.id for employee in result.employees]


def allocations_for(session, company_id: str, monthly: str = "500", per_task: str = "100"):
    """One allocation per employee. Budgets are always supplied, never invented."""
    rows = WorkforceService(session).list_employees(company_id)
    return [
        EmployeeAllocation(
            employeeId=row.id, budgetPerMonth=monthly, budgetPerTask=per_task
        )
        for row in rows
    ]


def generate(session, company_id: str, allocations=None) -> list[Contract]:
    return ContractService(session).generate(
        company_id,
        ContractGenerateRequest(
            allocations=allocations if allocations is not None else allocations_for(session, company_id)
        ),
    )


def activate(session, company_id: str):
    from app.services.lifecycle import CompanyLifecycleService

    return CompanyLifecycleService(session).activate(company_id)


def pause_of(session, company_id: str):
    from app.services.lifecycle import CompanyLifecycleService

    return CompanyLifecycleService(session).pause(company_id)


def resume(session, company_id: str, contract_ids: list[str] | None = None):
    from app.services.lifecycle import CompanyLifecycleService

    payload = ResumeRequest(
        activateContractIds=contract_ids if contract_ids is not None else None
    )
    return CompanyLifecycleService(session).resume(company_id, payload)


def set_status(session, company_id: str, status: CompanyStatus) -> None:
    company = session.get(Company, company_id)
    company.status = status
    session.commit()


def contracts_of(session, company_id: str) -> list[Contract]:
    return ContractService(session).list_for_company(company_id)


def active_contracts(session, company_id: str) -> list[Contract]:
    return [
        contract
        for contract in contracts_of(session, company_id)
        if contract.status is ContractStatus.ACTIVE
    ]


def draft_contracts(session, company_id: str) -> list[Contract]:
    return [
        contract
        for contract in contracts_of(session, company_id)
        if contract.status is ContractStatus.DRAFT
    ]


def post_generate(client: TestClient, company_id: str, allocations: list[dict]) -> Any:
    return client.post(
        f"/api/companies/{company_id}/contracts/generate",
        json={"allocations": allocations},
    )


def allocation_bodies(session, company_id: str, monthly="500", per_task="100") -> list[dict]:
    return [
        {"employeeId": item.employee_id, "budgetPerMonth": monthly, "budgetPerTask": per_task}
        for item in allocations_for(session, company_id)
    ]


def api_company(client: TestClient, **overrides) -> str:
    """Create a draft company through the API. Returns its id."""
    payload = {
        "name": "P0.4 Brand",
        "templateKey": "clothing",
        "monthlyBudget": CEILING,
        "currency": "USD",
        "targetMetric": "revenue",
        "targetValue": "100000",
    }
    payload.update(overrides)
    response = client.post("/api/companies", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def api_workforce(client: TestClient, company_id: str) -> list[str]:
    """Create the three-seat workforce through the API. Returns employee ids.

    Two requests: the owner's id is generated server-side, so the manager and seller
    can only reference it once it exists.
    """
    first = client.put(
        f"/api/companies/{company_id}/workforce",
        json={"employees": [{"displayName": "Owner", "kind": "human", "roleKey": "ceo"}]},
    )
    assert first.status_code == 200, first.text
    owner = first.json()["employees"][0]["id"]

    second = client.put(
        f"/api/companies/{company_id}/workforce",
        json={
            "employees": [
                {"id": owner, "displayName": "Owner", "kind": "human", "roleKey": "ceo"},
                {
                    "displayName": "Boss",
                    "kind": "ai",
                    "roleKey": "manager",
                    "reportsToId": owner,
                },
                {
                    "displayName": "Seller",
                    "kind": "ai",
                    "roleKey": "sales",
                    "reportsToId": owner,
                },
            ]
        },
    )
    assert second.status_code == 200, second.text
    return [employee["id"] for employee in second.json()["employees"]]


def api_allocations(employee_ids: list[str], monthly="500", per_task="100") -> list[dict]:
    return [
        {"employeeId": employee_id, "budgetPerMonth": monthly, "budgetPerTask": per_task}
        for employee_id in employee_ids
    ]


def assert_hashes_match(session, company_id: str) -> None:
    """Every stored contract must still match its recorded digest."""
    for contract in contracts_of(session, company_id):
        assert contract.content_hash == compute_content_hash(contract), (
            f"contract {contract.id} hash does not match its terms"
        )