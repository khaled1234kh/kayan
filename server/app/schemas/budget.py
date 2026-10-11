"""Budget API and service contracts.

Money crosses this boundary as a decimal **string**, never as a binary float. A
summary that reported `available` as a float would show 0.1 as 0.1000000000000000055
to anyone who tried to reconcile it, and the ledger is the reconciliation surface.

Reserve, settle and release are deliberately *not* HTTP endpoints. They are
backend operations invoked by trusted code that is about to spend money; exposing
them to a browser would mean anyone who can reach the API can move a company's
budget. The read endpoints and the explicit adjustment endpoint are below.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import AfterValidator, BeforeValidator, Field, field_validator

from app.models import BudgetLedgerCategory, CostCategory, MeterSource
from app.schemas.common import ApiCreate, ApiSchema
from app.schemas.company import _as_decimal_string, _must_be_finite

#: A monetary amount: converted through its decimal string form, required to be
#: finite, and sized to the ``Numeric(18, 6)`` columns. Finiteness is checked *after*
#: coercion, because ``Decimal('NaN') <= 0`` raises rather than answering, and
#: ``Decimal(0.1)`` is not ``Decimal("0.1")``.
Amount = Annotated[
    Decimal,
    BeforeValidator(_as_decimal_string),
    AfterValidator(_must_be_finite),
    Field(max_digits=18, decimal_places=6),
]

#: An amount that must also be strictly positive.
PositiveAmount = Annotated[
    Decimal,
    BeforeValidator(_as_decimal_string),
    AfterValidator(_must_be_finite),
    Field(gt=0, max_digits=18, decimal_places=6),
]


class BudgetReservationRequest(ApiCreate):
    """Inputs to a reservation. Ceilings are *not* accepted from the caller."""

    company_id: str = Field(alias="companyId", min_length=1, max_length=64)
    employee_id: str = Field(alias="employeeId", min_length=1, max_length=64)
    task_id: str | None = Field(default=None, alias="taskId", max_length=64)
    #: The worst-case cost, committed before execution.
    maximum_amount: PositiveAmount = Field(alias="maximumAmount")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=128)
    billable_operation_id: str = Field(
        alias="billableOperationId", min_length=1, max_length=64
    )
    meter_source: MeterSource = Field(alias="meterSource", default=MeterSource.MOCK)
    run_id: str | None = Field(default=None, alias="runId", max_length=64)
    description: str | None = Field(default=None, max_length=500)

    model_config = ApiCreate.model_config | {"extra": "forbid"}



class BudgetSettlementRequest(ApiCreate):
    """Inputs to a settlement."""

    company_id: str = Field(alias="companyId", min_length=1, max_length=64)
    reservation_id: str = Field(alias="reservationId", min_length=1, max_length=64)
    actual_amount: Amount = Field(alias="actualAmount")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=128)
    meter_source: MeterSource = Field(alias="meterSource", default=MeterSource.MOCK)
    usage_metadata: str | None = Field(default=None, alias="usageMetadata", max_length=500)

    model_config = ApiCreate.model_config | {"extra": "forbid"}



class BudgetAdjustmentRequest(ApiCreate):
    """``POST /api/companies/{id}/budget/adjustments`` body.

    The canonical form is an **absolute** new ceiling. A delta would need a sign
    convention that callers get wrong; "the ceiling is now X" cannot be misread.
    """

    new_monthly_limit: PositiveAmount = Field(alias="newMonthlyLimit")
    currency: str = Field(min_length=3, max_length=3)
    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=128)

    model_config = ApiCreate.model_config | {"extra": "forbid"}


    @field_validator("currency")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class DeniedOut(ApiSchema):
    """Why a reservation was refused. Committed as evidence, not raised."""

    scope: str
    reason: str
    requested: Decimal
    available: Decimal
    limit: Decimal


class ReserveResult(ApiSchema):
    """The outcome of a reservation attempt. ``allowed`` is never inferred."""

    allowed: bool
    reservation_id: str | None = None
    reserved_amount: Decimal | None = None
    currency: str
    available_after: Decimal | None = None
    denied: DeniedOut | None = None
    #: True when an identical request had already been processed.
    replayed: bool = False


class SettlementResult(ApiSchema):
    """The outcome of a settlement or release."""

    reservation_id: str
    charged_amount: Decimal
    released_amount: Decimal
    currency: str
    available_after: Decimal | None = None
    replayed: bool = False


class EmployeeAllocationOut(ApiSchema):
    """One employee's position, derived from their active contract."""

    employee_id: str
    display_name: str
    role_key: str
    contract_id: str
    contract_version: int
    monthly_limit: Decimal
    monthly_spend: Decimal
    monthly_outstanding: Decimal
    monthly_available: Decimal
    per_task_limit: Decimal


class BudgetSummary(ApiSchema):
    """Derived company budget position. Nothing here is a stored balance."""

    company_id: str
    currency: str
    account_id: str
    period_start: datetime
    period_end: datetime
    monthly_limit: Decimal
    actual_spend: Decimal
    outstanding_reservations: Decimal
    available: Decimal
    account_version: int
    employee_allocations: list[EmployeeAllocationOut] = []


class LedgerEntryOut(ApiSchema):
    """One append-only accounting row."""

    id: str
    company_id: str
    account_id: str | None
    reservation_id: str | None
    employee_id: str | None
    task_id: str | None
    run_id: str | None
    category: str
    amount: Decimal
    currency: str
    idempotency_key: str
    billable_operation_id: str | None
    note: str | None
    created_at: datetime


class LedgerPage(ApiSchema):
    """A page of ledger history. Never the whole ledger."""

    company_id: str
    entries: list[LedgerEntryOut]
    limit: int
    offset: int
    returned: int
    has_more: bool


class MeteredUsageIn(ApiCreate):
    """One measured slice of a billable operation."""

    category: CostCategory
    units: int = Field(ge=0)
    billable_operation_id: str = Field(alias="billableOperationId", min_length=1, max_length=64)
    note: str | None = Field(default=None, max_length=200)

    model_config = ApiCreate.model_config | {"extra": "forbid"}


__all__ = [
    "Amount",
    "BudgetAdjustmentRequest",
    "BudgetReservationRequest",
    "BudgetSettlementRequest",
    "BudgetSummary",
    "DeniedOut",
    "EmployeeAllocationOut",
    "LedgerEntryOut",
    "LedgerPage",
    "MeteredUsageIn",
    "PositiveAmount",
    "ReserveResult",
    "SettlementResult",
]