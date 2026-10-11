"""Budget read endpoints and the explicit adjustment endpoint.

Reserve, settle and release are intentionally absent. They are trusted backend
operations, and exposing them over HTTP would mean any client that can reach the API
can move a company's money.

The adjustment endpoint is a different case: it changes a configured ceiling, which
an owner does deliberately. It carries a dev-only header token
(``X-Budget-Adjustment-Token``) checked when ``BUDGET_ADJUSTMENT_TOKEN`` is set.
This is NOT production authentication — KAYAN has no auth in this phase.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DbSession, to_http, verify_budget_adjustment_token
from app.company.errors import DomainError
from app.models import BudgetLedgerCategory
from app.schemas.budget import (
    BudgetAdjustmentRequest,
    BudgetSummary,
    LedgerEntryOut,
    LedgerPage,
)
from app.services.budget import BudgetService

router = APIRouter(tags=["budget"])


@router.get(
    "/companies/{company_id}/budget",
    response_model=BudgetSummary,
    summary="Current budget position for a company",
)
def get_budget(company_id: str, session: DbSession) -> BudgetSummary:
    """Ceiling, actual spend, outstanding reservations, available and allocations.

    Every figure is derived from the account, the ledger, the reservation table and
    the active contracts. No balance is stored, so none can drift.
    """
    try:
        return BudgetService(session).summary(company_id)
    except DomainError as error:
        raise to_http(error)


@router.get(
    "/companies/{company_id}/budget/ledger",
    response_model=LedgerPage,
    summary="Paginated budget ledger history",
)
def get_ledger(
    company_id: str,
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    category: BudgetLedgerCategory | None = None,
    employee_id: str | None = None,
    task_id: str | None = None,
) -> LedgerPage:
    """Newest first, deterministically ordered, and paginated.

    A company that has run for months has thousands of rows; returning all of them
    to render a first page is not an option.
    """
    service = BudgetService(session)
    try:
        # One extra row tells us whether another page exists without a count query.
        entries = service.ledger(
            company_id,
            limit=limit + 1,
            offset=offset,
            category=category,
            employee_id=employee_id,
            task_id=task_id,
        )
        service._companies.get_company(company_id)
    except DomainError as error:
        raise to_http(error)

    has_more = len(entries) > limit
    page = entries[:limit]
    return LedgerPage(
        company_id=company_id,
        entries=[LedgerEntryOut.model_validate(entry) for entry in page],
        limit=limit,
        offset=offset,
        returned=len(page),
        has_more=has_more,
    )


@router.post(
    "/companies/{company_id}/budget/adjustments",
    response_model=BudgetSummary,
    summary="Change a company's monthly ceiling, with an audit trail",
    dependencies=[Depends(verify_budget_adjustment_token)],
)
def adjust_budget(
    company_id: str, payload: BudgetAdjustmentRequest, session: DbSession
) -> BudgetSummary:
    """Set the ceiling to an absolute new value.

    Refused if the new ceiling falls below committed spend plus outstanding
    reservations, or below the total of active contract allocations. Every change is
    recorded in the ledger and audited as ``budget_adjusted``.

    **Dev-only token.** When ``BUDGET_ADJUSTMENT_TOKEN`` is set, the request must
    carry a matching ``X-Budget-Adjustment-Token`` header. This is NOT production
    authentication — KAYAN has no auth in this phase.
    """
    try:
        return BudgetService(session).adjust_monthly_limit(company_id, payload)
    except DomainError as error:
        raise to_http(error)