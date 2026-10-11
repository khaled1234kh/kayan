"""Company and workforce API contracts.

Money is ``Decimal`` end to end. A float never reaches the database: JSON numbers
are converted through their decimal string form, and anything with more precision
than ``Numeric(18, 6)`` can hold is rejected rather than rounded. ``NaN`` and
infinities are refused outright — a budget or target that is not a finite amount is
not a configuration, it is a bug in the caller.

Outbound models read ORM attributes; inbound models are strict (``extra="forbid"``)
so a client sending an unsupported field — an active contract, a status transition —
is told plainly, instead of having it silently ignored.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import AfterValidator, BeforeValidator, Field, field_validator, model_validator

from app.models.company import SUPPORTED_CURRENCIES
from app.models.models import TaskStatus
from app.schemas.common import ApiCreate, ApiSchema

#: Human or AI seat.
EMPLOYEE_KINDS = ("human", "ai")

#: Documented target periods. A free-form period string is not measurable, so the
#: accepted set is closed rather than open.
TARGET_PERIODS = ("total", "month", "quarter", "year")

#: Employees a single company may configure. P0.2 must support at least 20; the cap
#: exists only so one request cannot carry an unbounded payload.
MAX_WORKFORCE_SIZE = 200


def _as_decimal_string(value: Any) -> Any:
    """Convert a JSON number via its string form, never its binary expansion.

    ``Decimal(0.1)`` is not ``Decimal("0.1")``; going through ``str`` keeps a
    client's ``1000.10`` meaning ten hundred and ten, not a rounding artefact.
    """
    return str(value) if isinstance(value, float) else value


def _must_be_finite(value: Decimal) -> Decimal:
    """Reject NaN and infinity.

    A budget or target that is not a finite amount is not a configuration, it is a
    bug in the caller — and ``Decimal('NaN') <= 0`` raises rather than returning a
    bool, so this has to be checked before any comparison.
    """
    if not value.is_finite():
        raise ValueError("must be a finite amount, not NaN or infinity")
    return value


#: A monetary amount or target value: finite, and sized to the ``Numeric(18, 6)``
#: columns. More precision than the column holds is refused, never rounded.
Money = Annotated[
    Decimal,
    BeforeValidator(_as_decimal_string),
    AfterValidator(_must_be_finite),
    Field(max_digits=18, decimal_places=6),
]


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------


class CompanyCreate(ApiCreate):
    """``POST /api/companies`` body."""

    name: str = Field(min_length=1, max_length=160)
    template_key: str = Field(alias="templateKey")
    #: Monthly ceiling for the company. Opened as a ``BudgetAccount`` on create.
    #: Must be positive: a company cannot authorise spending from nothing or from a
    #: negative ceiling.
    monthly_budget: Money = Field(alias="monthlyBudget", gt=0)
    currency: str = Field(min_length=3, max_length=3)
    industry: str | None = Field(default=None, max_length=120)
    target_description: str | None = Field(default=None, max_length=2000)
    target_metric: str | None = Field(default=None, max_length=64)
    target_value: Money | None = Field(default=None)
    target_unit: str | None = Field(default=None, max_length=32)
    target_period: str | None = Field(default=None, max_length=32)

    model_config = ApiCreate.model_config | {"extra": "forbid"}

    @field_validator("currency")
    @classmethod
    def _known_currency(cls, value: str) -> str:
        code = value.upper()
        if code not in SUPPORTED_CURRENCIES:
            raise ValueError(
                f"currency '{value}' is not supported; use one of {', '.join(SUPPORTED_CURRENCIES)}"
            )
        return code

    @field_validator("target_period")
    @classmethod
    def _known_period(cls, value: str | None) -> str | None:
        if value is not None and value not in TARGET_PERIODS:
            raise ValueError(f"targetPeriod must be one of {', '.join(TARGET_PERIODS)}")
        return value

    @model_validator(mode="after")
    def _target_is_coherent(self) -> "CompanyCreate":
        validate_target_fields(
            metric=self.target_metric,
            value=self.target_value,
            unit=self.target_unit,
            period=self.target_period,
        )
        return self


class CompanyUpdate(ApiCreate):
    """``PATCH /api/companies/{id}`` body. Every field is optional.

    Only fields that are actually sent are changed, so an omitted field is never
    reset to a default. Lifecycle fields are absent by design: activation, pause
    and contract assignment are not draft edits and belong to later stages.
    """

    name: str | None = Field(default=None, min_length=1, max_length=160)
    industry: str | None = Field(default=None, max_length=120)
    template_key: str | None = Field(default=None)
    monthly_budget: Money | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    target_description: str | None = Field(default=None, max_length=2000)
    target_metric: str | None = Field(default=None, max_length=64)
    target_value: Money | None = Field(default=None)
    target_unit: str | None = Field(default=None, max_length=32)
    target_period: str | None = Field(default=None, max_length=32)

    model_config = ApiCreate.model_config | {"extra": "forbid"}

    @field_validator("currency")
    @classmethod
    def _known_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        code = value.upper()
        if code not in SUPPORTED_CURRENCIES:
            raise ValueError(
                f"currency '{value}' is not supported; use one of {', '.join(SUPPORTED_CURRENCIES)}"
            )
        return code

    @field_validator("target_period")
    @classmethod
    def _known_period(cls, value: str | None) -> str | None:
        if value is not None and value not in TARGET_PERIODS:
            raise ValueError(f"targetPeriod must be one of {', '.join(TARGET_PERIODS)}")
        return value

    @model_validator(mode="after")
    def _target_is_coherent(self) -> "CompanyUpdate":
        if self.target_metric is not None or self.target_value is not None:
            validate_target_fields(
                metric=self.target_metric,
                value=self.target_value,
                unit=self.target_unit,
                period=self.target_period,
            )
        return self


def validate_target_fields(
    *,
    metric: str | None,
    value: Decimal | None,
    unit: str | None,
    period: str | None,
) -> None:
    """A structured target is either fully specified or absent.

    A metric without a value states an aspiration rather than a target, and a
    value without a metric cannot be interpreted. The backend refuses both instead
    of inventing a metric on the owner's behalf.
    """
    if metric is not None and value is None:
        raise ValueError("targetValue is required when targetMetric is set")
    if value is not None and metric is None:
        raise ValueError("targetMetric is required when targetValue is set")
    if value is not None and value <= 0:
        raise ValueError("targetValue must be greater than zero")
    if metric is not None and not metric.strip():
        raise ValueError("targetMetric must not be blank")


# ---------------------------------------------------------------------------
# Workforce
# ---------------------------------------------------------------------------


class EmployeeIn(ApiCreate):
    """One seat in a workforce replacement.

    ``id`` is omitted for a new seat and supplied to edit an existing one. Names are
    display data and are never used as identifiers.
    """

    display_name: str = Field(alias="displayName", min_length=1, max_length=160)
    kind: str
    #: Catalogue role key, or ``custom`` with ``custom_role`` supplied.
    role_key: str = Field(alias="roleKey")
    custom_role: str | None = Field(default=None, alias="customRole", max_length=160)
    objective: str | None = Field(default=None, max_length=2000)
    responsibilities: list[str] = Field(default_factory=list, max_length=50)
    reports_to_id: str | None = Field(default=None, alias="reportsToId")
    #: Only for editing a seat that already exists in this company.
    id: str | None = Field(default=None, max_length=64)

    # -- accepted on input so a client can read a workforce and send it straight back
    status: str | None = Field(default=None, description="Read-only; must be 'draft'.")
    company_id: str | None = Field(
        default=None, alias="companyId", description="Read-only; must match the target company."
    )

    model_config = ApiCreate.model_config | {"extra": "forbid"}

    @field_validator("status")
    @classmethod
    def _draft_only(cls, value: str | None) -> str | None:
        """Refuse a status other than draft, with a reason.

        Accepting it silently would let a caller believe an employee was activated.
        """
        if value is None:
            return None
        if value != "draft":
            raise ValueError(
                "employee status cannot be set here; only 'draft' is valid and employee "
                "activation is a later stage"
            )
        return value

    @field_validator("kind")
    @classmethod
    def _known_kind(cls, value: str) -> str:
        kind = value.lower()
        if kind not in EMPLOYEE_KINDS:
            raise ValueError(f"kind must be one of {', '.join(EMPLOYEE_KINDS)}")
        return kind

    @field_validator("responsibilities")
    @classmethod
    def _no_blank_responsibilities(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("responsibilities must not contain blank entries")
        return cleaned


class WorkforceReplace(ApiCreate):
    """``PUT /api/companies/{id}/workforce`` body: the complete desired workforce."""

    employees: list[EmployeeIn] = Field(min_length=1, max_length=MAX_WORKFORCE_SIZE)

    model_config = ApiCreate.model_config | {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class CompanyOut(ApiSchema):
    """Company configuration as the API exposes it."""

    id: str
    name: str
    industry: str | None
    template_key: str
    status: str
    currency: str
    revision: int
    #: Current monthly ceiling, sourced from the company's budget account.
    monthly_budget: Decimal | None
    budget_period_start: datetime | None
    budget_period_end: datetime | None
    target_description: str | None
    target_metric: str | None
    target_value: Decimal | None
    target_unit: str | None
    target_period: str | None
    created_at: datetime
    updated_at: datetime


class EmployeeOut(ApiSchema):
    id: str
    company_id: str
    display_name: str
    kind: str
    role_key: str
    custom_role: str | None
    objective: str | None
    responsibilities: list[str]
    reports_to_id: str | None
    status: str


class WorkforceOut(ApiSchema):
    company_id: str
    #: The company's configuration revision, so a client can detect staleness.
    revision: int
    employee_count: int
    employees: list[EmployeeOut]


# ---------------------------------------------------------------------------
# Company tasks
# ---------------------------------------------------------------------------


class CompanyTaskCreate(ApiCreate):
    """``POST /api/companies/{id}/tasks`` body."""

    title: str = Field(min_length=1, max_length=200)
    #: Must appear in the assigned employee's contract ``task_scope``.
    category: str = Field(min_length=1, max_length=64)
    employee_id: str = Field(alias="employeeId", min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=2000)

    model_config = ApiCreate.model_config | {"extra": "forbid"}


class CompanyTaskUpdate(ApiCreate):
    """``PATCH /api/tasks/{id}`` body. Every field is optional."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=64)
    status: str | None = Field(default=None)
    description: str | None = Field(default=None, max_length=2000)

    model_config = ApiCreate.model_config | {"extra": "forbid"}

    @field_validator("status")
    @classmethod
    def _known_status(cls, value: str | None) -> str | None:
        allowed = tuple(status.value for status in TaskStatus)
        if value is not None and value not in allowed:
            raise ValueError(f"status must be one of {', '.join(repr(s) for s in allowed)}")
        return value


class CompanyTaskOut(ApiSchema):
    id: str
    company_id: str
    employee_id: str
    title: str
    category: str
    status: str
    description: str | None
    created_at: datetime


class TemplateOut(ApiSchema):
    """One company template offered by the setup catalogue."""

    key: str
    label: str
    summary: str
    industries: list[str]
    role_keys: list[str]
    task_categories: list[str]


class RoleOut(ApiSchema):
    """One versioned role definition, read from the seeded catalogue."""

    key: str
    label: str
    kind: str
    summary: str | None
    responsibilities: list[str]
    task_categories: list[str]
    default_data_scope: list[dict[str, Any]]
    default_tool_scope: list[dict[str, Any]]
    default_restrictions: list[str]
    template_keys: list[str]
    config_version: int


__all__ = [
    "CompanyCreate",
    "CompanyOut",
    "CompanyTaskCreate",
    "CompanyTaskOut",
    "CompanyTaskUpdate",
    "CompanyUpdate",
    "EmployeeIn",
    "EmployeeOut",
    "MAX_WORKFORCE_SIZE",
    "Money",
    "RoleOut",
    "TARGET_PERIODS",
    "TemplateOut",
    "WorkforceOut",
    "WorkforceReplace",
]