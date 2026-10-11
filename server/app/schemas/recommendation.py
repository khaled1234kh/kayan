"""Recommendation request and proposal contracts.

Two directions, with different rules:

* **Inbound** — what the owner asked for. Strict, because an unrecognised field in
  a preference is a client bug worth reporting rather than silently ignoring.
* **Outbound** — what a provider proposed. Strict *and* validated against the role
  catalogue, because this document describes the permissions a future contract
  would grant. Free-form output that reached this point unexamined would become
  executable authority nobody reviewed.

Money is ``Decimal`` throughout, finite and sized to ``Numeric(18, 6)``, matching
the rest of the company API.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator

from app.schemas.common import ApiCreate, ApiSchema

#: A proposal-local employee key. Stable within a proposal so reporting
#: relationships can be expressed before permanent ids exist, and never a display
#: name: names change, keys must not.
ProposalKey = Annotated[
    str, Field(pattern=r"^proposal-employee-\d+$", max_length=64)
]

#: Upper bound on a recommended workforce. Matches the P0.2 replacement limit so a
#: proposal can always be submitted back as a workforce.
MAX_RECOMMENDED_EMPLOYEES = 200
MIN_RECOMMENDED_EMPLOYEES = 1

RecommendationSource = Literal["template", "model"]


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class RecommendationPreferences(ApiCreate):
    """What the owner wants from the recommendation.

    Every field is optional with a defined default, so an empty preferences object
    is a valid request: it means "use the template's own sensible default".
    """

    desired_employee_count: int | None = Field(
        default=None,
        alias="desiredEmployeeCount",
        ge=MIN_RECOMMENDED_EMPLOYEES,
        le=MAX_RECOMMENDED_EMPLOYEES,
    )
    #: Include one human decision-maker. Templates always include a human owner;
    #: this is how a caller asks for a fully automated roster.
    include_human_employee: bool = Field(default=True, alias="includeHumanEmployee")
    #: Offer the HR role when the template supports it.
    include_hr: bool = Field(default=True, alias="includeHR")
    notes: str | None = Field(default=None, max_length=2000)

    model_config = ApiCreate.model_config | {"extra": "forbid"}

    @field_validator("notes")
    @classmethod
    def _notes_are_useful(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("notes must not be blank; omit it instead")
        return value


class RecommendationRequest(ApiCreate):
    """``POST /api/setup/recommendations`` body.

    Only the company id identifies the request. Budget, currency, template and
    target are read from the saved company: duplicating them here would invite a
    recommendation built on values the company does not actually have.
    """

    company_id: str = Field(alias="companyId", min_length=1, max_length=64)
    preferences: RecommendationPreferences = Field(default_factory=RecommendationPreferences)

    model_config = ApiCreate.model_config | {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Proposal
# ---------------------------------------------------------------------------


class DataScopeEntry(ApiSchema):
    """One structured read/write grant: ``{resource, operations}``."""

    resource: str = Field(min_length=1, max_length=120)
    operations: list[str] = Field(min_length=1, max_length=20)

    @field_validator("operations")
    @classmethod
    def _operations_are_known(cls, values: list[str]) -> list[str]:
        allowed = {"read", "write"}
        unknown = sorted({value for value in values if value not in allowed})
        if unknown:
            raise ValueError(f"unknown operations: {', '.join(unknown)}")
        return values


class ToolScopeEntry(ApiSchema):
    """One structured tool grant: ``{tool, actions}``."""

    tool: str = Field(min_length=1, max_length=120)
    actions: list[str] = Field(min_length=1, max_length=20)


class CommunicationPermissions(ApiSchema):
    """Who a seat may talk to, and whether it may broadcast.

    Targeted communication plus a restricted broadcast flag is the default posture;
    an open broadcast is something a proposal has to justify, not assume.
    """

    allow: list[str] = Field(default_factory=list, max_length=50)
    broadcast: bool = False
    max_rounds: int = Field(default=3, ge=1, le=20)


class ProposedEmployee(ApiSchema):
    """One proposed seat, addressed by a proposal-local key."""

    key: ProposalKey
    display_name: str = Field(min_length=1, max_length=160)
    #: ``human`` or ``ai``, matching the seat kinds P0.2 supports.
    kind: Literal["human", "ai"]
    #: Catalogue role this seat draws its defaults from.
    role_key: str = Field(min_length=1, max_length=64)
    #: The catalogue version the defaults were taken from, so the snapshot explains
    #: itself even after the role is revised.
    role_config_version: int = Field(ge=1)
    objective: str | None = Field(default=None, max_length=2000)
    responsibilities: list[str] = Field(default_factory=list, max_length=50)
    data_scope: list[DataScopeEntry] = Field(default_factory=list, max_length=50)
    tool_scope: list[ToolScopeEntry] = Field(default_factory=list, max_length=50)
    restrictions: list[str] = Field(default_factory=list, max_length=50)
    communication: CommunicationPermissions = Field(
        default_factory=CommunicationPermissions
    )
    reports_to_key: ProposalKey | None = None
    suggested_monthly_budget: Decimal = Field(
        alias="suggestedMonthlyBudget", ge=0, max_digits=18, decimal_places=6
    )
    suggested_per_task_budget: Decimal = Field(
        alias="suggestedPerTaskBudget", ge=0, max_digits=18, decimal_places=6
    )
    #: Why this role exists for this company, and why this allocation.
    rationale: str = Field(min_length=1, max_length=1000)


class ProposedAllocation(ApiSchema):
    """A seat's money, kept together so the rule is stated once."""

    key: ProposalKey
    suggested_monthly_budget: Decimal = Field(
        alias="suggestedMonthlyBudget", ge=0, max_digits=18, decimal_places=6
    )
    suggested_per_task_budget: Decimal = Field(
        alias="suggestedPerTaskBudget", ge=0, max_digits=18, decimal_places=6
    )


class BudgetSummary(ApiSchema):
    """Totals for the proposal, with the remainder stated explicitly."""

    company_monthly_ceiling: Decimal = Field(
        alias="companyMonthlyCeiling", ge=0, max_digits=18, decimal_places=6
    )
    currency: str = Field(min_length=3, max_length=3)
    total_suggested_monthly: Decimal = Field(
        alias="totalSuggestedMonthly", ge=0, max_digits=18, decimal_places=6
    )
    #: What is deliberately not allocated. Naming it stops a reader assuming the
    #: whole ceiling was committed.
    unallocated_monthly: Decimal = Field(
        alias="unallocatedMonthly", ge=0, max_digits=18, decimal_places=6
    )


class RecommendationProposal(ApiSchema):
    """A validated workforce proposal."""

    company_id: str = Field(alias="companyId", min_length=1, max_length=64)
    source: RecommendationSource
    #: Identifiers for a model-backed proposal; null for a template one, so the two
    #: can never be confused after the fact.
    provider_name: str | None = Field(default=None, alias="providerName", max_length=64)
    model_name: str | None = Field(default=None, alias="modelName", max_length=128)
    role_catalog_version: int = Field(
        alias="roleCatalogVersion", ge=1
    )
    employees: list[ProposedEmployee] = Field(min_length=1, max_length=MAX_RECOMMENDED_EMPLOYEES)
    budget: BudgetSummary
    #: Non-fatal observations: a trimmed roster, a role that does not match the
    #: company's stated priority, and so on. A proposal that needed no repair still
    #: returns an empty list rather than omitting the field.
    warnings: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("employees")
    @classmethod
    def _keys_are_unique(cls, employees: list[ProposedEmployee]) -> list[ProposedEmployee]:
        keys = [employee.key for employee in employees]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise ValueError(f"duplicate proposal keys: {', '.join(duplicates)}")
        return employees


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class RecommendationOut(ApiSchema):
    """``POST`` / ``GET`` recommendation response.

    Wraps the proposal with its identity and lifecycle status, so a client can tell
    a stored proposal from a freshly generated one and knows not to treat it as
    adopted.
    """

    id: str
    company_id: str
    status: str
    created_at: datetime
    preferences: dict[str, Any]
    proposal: RecommendationProposal


__all__ = [
    "BudgetSummary",
    "CommunicationPermissions",
    "DataScopeEntry",
    "MAX_RECOMMENDED_EMPLOYEES",
    "MIN_RECOMMENDED_EMPLOYEES",
    "ProposedAllocation",
    "ProposedEmployee",
    "RecommendationOut",
    "RecommendationPreferences",
    "RecommendationProposal",
    "RecommendationRequest",
    "RecommendationSource",
    "ToolScopeEntry",
]