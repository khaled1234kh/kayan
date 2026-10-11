"""Company configuration endpoints.

Routes stay thin: validate the request shape, call the service, translate domain
errors to HTTP. Every business rule — lifecycle, budget consistency, reporting
lines — lives in the service, so it holds for every caller rather than only this
one.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import DbSession, to_http
from app.company.errors import DomainError
from app.models import Company
from app.schemas.contract import ActivationOut, ResumeRequest
from app.schemas import (
    CompanyCreate,
    CompanyOut,
    CompanyTaskCreate,
    CompanyTaskOut,
    CompanyTaskUpdate,
    CompanyUpdate,
    EmployeeOut,
    WorkforceOut,
    WorkforceReplace,
)
from app.services.companies import CompanyService
from app.services.company_tasks import CompanyTaskService
from app.services.lifecycle import CompanyLifecycleService
from app.services.workforce import WorkforceService

router = APIRouter(prefix="/companies", tags=["companies"])


def _to_out(company: Company, service: CompanyService) -> CompanyOut:
    """Build the response, sourcing the monthly ceiling from the budget account."""
    account = service.get_budget_account(company.id)
    return CompanyOut(
        id=company.id,
        name=company.name,
        industry=company.industry,
        template_key=company.template_key,
        status=company.status.value,
        currency=company.currency,
        revision=company.revision,
        monthly_budget=account.monthly_limit if account else None,
        budget_period_start=account.period_start if account else None,
        budget_period_end=account.period_end if account else None,
        target_description=company.target_description,
        target_metric=company.target_metric,
        target_value=company.target_value,
        target_unit=company.target_unit,
        target_period=company.target_period,
        created_at=company.created_at,
        updated_at=company.updated_at,
    )


@router.post(
    "",
    response_model=CompanyOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft company",
)
def create_company(payload: CompanyCreate, session: DbSession) -> CompanyOut:
    service = CompanyService(session)
    try:
        company = service.create_company(payload)
    except DomainError as error:
        raise to_http(error)
    return _to_out(company, service)


@router.get(
    "/{company_id}", response_model=CompanyOut, summary="Get company configuration"
)
def get_company(company_id: str, session: DbSession) -> CompanyOut:
    service = CompanyService(session)
    try:
        company = service.get_company(company_id)
    except DomainError as error:
        raise to_http(error)
    return _to_out(company, service)


@router.patch(
    "/{company_id}", response_model=CompanyOut, summary="Update a draft company"
)
def update_company(
    company_id: str, payload: CompanyUpdate, session: DbSession
) -> CompanyOut:
    """Partial update. A PATCH that changes nothing is a read, and emits no event."""
    service = CompanyService(session)
    try:
        company, _changed = service.update_company(company_id, payload)
    except DomainError as error:
        raise to_http(error)
    return _to_out(company, service)


@router.get(
    "/{company_id}/employees",
    response_model=list[EmployeeOut],
    summary="List a company's configured employees",
)
def list_employees(company_id: str, session: DbSession) -> list[EmployeeOut]:
    service = WorkforceService(session)
    try:
        employees = service.list_employees(company_id)
    except DomainError as error:
        raise to_http(error)
    return [EmployeeOut.model_validate(row) for row in employees]


@router.put(
    "/{company_id}/workforce",
    response_model=WorkforceOut,
    summary="Replace the company's draft workforce",
)
def replace_workforce(
    company_id: str, payload: WorkforceReplace, session: DbSession
) -> WorkforceOut:
    """The request states the complete desired workforce; omitted employees are removed."""
    service = WorkforceService(session)
    try:
        return service.replace_workforce(company_id, payload)
    except DomainError as error:
        raise to_http(error)


@router.post(
    "/{company_id}/tasks",
    response_model=CompanyTaskOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task for a company employee",
)
def create_task(
    company_id: str, payload: CompanyTaskCreate, session: DbSession
) -> CompanyTaskOut:
    """Create a task assigned to one of the company's configured employees.

    The category must fall inside the employee's contract task scope when they
    have an active contract.
    """
    service = CompanyTaskService(session)
    try:
        task = service.create(company_id, payload)
    except DomainError as error:
        raise to_http(error)
    return CompanyTaskOut.model_validate(task)


@router.get(
    "/{company_id}/tasks",
    response_model=list[CompanyTaskOut],
    summary="List a company's tasks",
)
def list_tasks(company_id: str, session: DbSession) -> list[CompanyTaskOut]:
    """Every task belonging to the company, ordered by creation."""
    service = CompanyTaskService(session)
    try:
        tasks = service.list_for_company(company_id)
    except DomainError as error:
        raise to_http(error)
    return [CompanyTaskOut.model_validate(task) for task in tasks]


@router.post(
    "/{company_id}/activate",
    response_model=ActivationOut,
    summary="Activate a draft company and its contracts",
)
def activate_company(company_id: str, session: DbSession) -> ActivationOut:
    """One transaction: contracts, employee pointers, company status and events.

    Nothing is published and no success is returned unless the whole activation
    commits. A company that already holds the single active slot cannot take another.
    """
    try:
        return CompanyLifecycleService(session).activate(company_id)
    except DomainError as error:
        raise to_http(error)


@router.post(
    "/{company_id}/pause",
    response_model=ActivationOut,
    summary="Pause an active company",
)
def pause_company(company_id: str, session: DbSession) -> ActivationOut:
    """Changes a status only: no employee, contract, ledger row or run is removed."""
    try:
        return CompanyLifecycleService(session).pause(company_id)
    except DomainError as error:
        raise to_http(error)


@router.post(
    "/{company_id}/resume",
    response_model=ActivationOut,
    summary="Resume a paused company",
)
def resume_company(
    company_id: str, session: DbSession, payload: ResumeRequest | None = None
) -> ActivationOut:
    """Revalidates, then optionally activates reviewed successor versions atomically.

    A draft contract is never activated merely because it exists.
    """
    try:
        return CompanyLifecycleService(session).resume(company_id, payload)
    except DomainError as error:
        raise to_http(error)