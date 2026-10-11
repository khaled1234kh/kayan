"""Shared setup for the P0.5 budget tests.

A company that can actually spend money: active, with activated contracts and a
company task. The allocations are small and explicit so a ceiling test can spend
precisely the amount it means to.
"""

from __future__ import annotations

from decimal import Decimal

from app.models import Company, CompanyEmployee, CompanyTask, TaskStatus, new_company_task_id
from app.schemas.company import EmployeeIn, WorkforceReplace
from app.schemas.contract import ContractGenerateRequest, EmployeeAllocation
from app.services.companies import CompanyService
from app.services.contracts import ContractService
from app.services.lifecycle import CompanyLifecycleService
from app.services.workforce import WorkforceService


class BudgetFixture:
    """A ready-to-spend company plus the ids a test needs."""

    def __init__(self, session, company: Company, seller: CompanyEmployee) -> None:
        self.session = session
        self.company = company
        self.seller = seller
        self.owner = next(
            row
            for row in session.query(CompanyEmployee).filter_by(company_id=company.id).all()
            if row.id != seller.id
        )
        self.task = self.make_task(seller.id, "quotation")
        self.other_task = self.make_task(seller.id, "quotation")

    @property
    def company_id(self) -> str:
        return self.company.id

    @property
    def seller_id(self) -> str:
        return self.seller.id

    def make_task(
        self, employee_id: str, category: str, *, title: str = "Task"
    ) -> CompanyTask:
        task = CompanyTask(
            id=new_company_task_id(),
            company_id=self.company_id,
            employee_id=employee_id,
            title=title,
            category=category,
            status=TaskStatus.OPEN,
        )
        self.session.add(task)
        self.session.commit()
        return task

    def contract_for(self, employee_id: str):
        from app.models import Contract

        employee = self.session.get(CompanyEmployee, employee_id)
        return self.session.get(Contract, employee.active_contract_id)


def make_spendable_company(
    session,
    *,
    ceiling: str = "1000",
    seller_monthly: str = "400",
    seller_per_task: str = "100",
    owner_monthly: str = "100",
    activate: bool = True,
) -> BudgetFixture:
    """Company -> workforce -> contracts -> (optionally) activation.

    Every ceiling the budget service reads comes from these activated contracts, so
    the numbers here are the numbers the tests reason about.
    """
    company = CompanyService(session).create_company(
        __import__("app.schemas.company", fromlist=["CompanyCreate"]).CompanyCreate(
            name="P0.5 Brand",
            templateKey="clothing",
            monthlyBudget=Decimal(ceiling),
            currency="USD",
            targetMetric="revenue",
            targetValue=Decimal("50000"),
        )
    )

    workforce = WorkforceService(session)
    owner = workforce.replace_workforce(
        company.id,
        WorkforceReplace(employees=[EmployeeIn(displayName="Owner", kind="human", roleKey="ceo")]),
    ).employees[0]
    result = workforce.replace_workforce(
        company.id,
        WorkforceReplace(
            employees=[
                EmployeeIn(id=owner.id, displayName="Owner", kind="human", roleKey="ceo"),
                EmployeeIn(
                    displayName="Seller", kind="ai", roleKey="sales", reportsToId=owner.id
                ),
            ]
        ),
    )
    allocations = [
        EmployeeAllocation(
            employeeId=row.id,
            budgetPerMonth=seller_monthly if row.id != owner.id else owner_monthly,
            budgetPerTask=seller_per_task if row.id != owner.id else "10",
        )
        for row in result.employees
    ]
    ContractService(session).generate(
        company.id, ContractGenerateRequest(allocations=allocations)
    )
    if activate:
        CompanyLifecycleService(session).activate(company.id)

    session.refresh(company)
    seller = next(row for row in result.employees if row.role_key == "sales")
    stored_seller = session.get(CompanyEmployee, seller.id)
    return BudgetFixture(session, company, stored_seller)


def reserve_request(
    company_id: str,
    employee_id: str,
    task_id: str,
    amount: str,
    key: str,
    operation: str | None = None,
    **extra,
):
    """A reservation request; ceilings are never part of it, by design."""
    from app.schemas.budget import BudgetReservationRequest

    return BudgetReservationRequest(
        companyId=company_id,
        employeeId=employee_id,
        taskId=task_id,
        maximumAmount=amount,
        idempotencyKey=key,
        billableOperationId=operation or f"op-{key}",
        **extra,
    )


def settle_request(company_id: str, reservation_id: str, amount: str, key: str, **extra):
    from app.schemas.budget import BudgetSettlementRequest

    return BudgetSettlementRequest(
        companyId=company_id,
        reservationId=reservation_id,
        actualAmount=amount,
        idempotencyKey=key,
        **extra,
    )