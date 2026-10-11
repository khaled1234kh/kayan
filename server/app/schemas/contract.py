"""Contract API contracts.

Inbound documents are strict. A contract grants authority, so an unrecognised field
is not something to shrug at: it may be a typo for a real permission, or an attempt
to set something that is not editable here.

``versionNumber`` and ``status`` are excluded from the editable set on purpose. A
version number is assigned by the system when a successor is created, and a status is
a lifecycle transition with its own endpoint.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BeforeValidator, Field, field_validator

from app.company.permissions import SUPPORTED_OPERATIONS
from app.schemas.common import ApiCreate, ApiSchema
from app.schemas.company import _as_decimal_string, _must_be_finite

#: A contract budget amount: finite, non-negative, sized to ``Numeric(18, 6)``.
BudgetAmount = Annotated[
    Decimal,
    BeforeValidator(_as_decimal_string),
    AfterValidator(_must_be_finite),
    Field(ge=0, max_digits=18, decimal_places=6),
]


class DataScopeIn(ApiCreate):
    """``{resource, operations}`` — never a sentence describing access."""

    resource: str = Field(min_length=1, max_length=120)
    operations: list[str] = Field(min_length=1, max_length=20)

    @field_validator("operations")
    @classmethod
    def _known_operations(cls, values: list[str]) -> list[str]:
        unknown = sorted(set(values) - SUPPORTED_OPERATIONS)
        if unknown:
            raise ValueError(f"unsupported operations: {', '.join(unknown)}")
        return values


class ToolScopeIn(ApiCreate):
    """``{tool, actions}``."""

    tool: str = Field(min_length=1, max_length=120)
    actions: list[str] = Field(min_length=1, max_length=20)


class CommunicationPolicyIn(ApiCreate):
    """Who this seat may talk to, and whether it may broadcast."""

    allow: list[str] = Field(default_factory=list, max_length=50)
    broadcast: bool = False
    max_rounds: int = Field(default=3, alias="maxRounds", ge=1, le=20)

    model_config = ApiCreate.model_config | {"extra": "forbid"}


class ApprovalRuleIn(ApiCreate):
    """``{action, requiredApprover}`` — an unmeetable rule is a configuration bug."""

    action: str = Field(min_length=1, max_length=120)
    required_approver: str = Field(alias="requiredApprover", min_length=1, max_length=64)

    model_config = ApiCreate.model_config | {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class EmployeeAllocation(ApiCreate):
    """The owner's budget allocation for one employee.

    ``CompanyEmployee`` does not retain a draft allocation, so generation asks for
    one explicitly rather than inventing one.
    """

    employee_id: str = Field(alias="employeeId", min_length=1, max_length=64)
    budget_per_month: BudgetAmount = Field(alias="budgetPerMonth")
    budget_per_task: BudgetAmount = Field(alias="budgetPerTask")

    model_config = ApiCreate.model_config | {"extra": "forbid"}


class ContractGenerateRequest(ApiCreate):
    """``POST /api/companies/{id}/contracts/generate`` body."""

    allocations: list[EmployeeAllocation] = Field(min_length=1, max_length=200)
    #: When true, existing unactivated drafts are replaced rather than duplicated.
    replace_existing: bool = Field(default=True, alias="replaceExisting")

    model_config = ApiCreate.model_config | {"extra": "forbid"}


class ContractPatch(ApiCreate):
    """``PATCH /api/contracts/{id}`` — draft terms only.

    Every field is optional; an omitted field keeps its current value.
    """

    role: str | None = Field(default=None, max_length=160)
    role_config_version: int | None = Field(default=None, alias="roleConfigVersion", ge=1)
    objective: str | None = Field(default=None, max_length=2000)
    responsibilities: list[str] | None = Field(default=None, max_length=50)
    data_scope: list[DataScopeIn] | None = Field(default=None, alias="dataScope", max_length=50)
    tool_scope: list[ToolScopeIn] | None = Field(default=None, alias="toolScope", max_length=50)
    restrictions: list[str] | None = Field(default=None, max_length=50)
    task_scope: list[str] | None = Field(default=None, alias="taskScope", max_length=50)
    communication_policy: CommunicationPolicyIn | None = Field(
        default=None, alias="communicationPolicy"
    )
    approval_rules: list[ApprovalRuleIn] | None = Field(default=None, alias="approvalRules")
    budget_per_task: BudgetAmount | None = Field(default=None, alias="budgetPerTask")
    budget_per_month: BudgetAmount | None = Field(default=None, alias="budgetPerMonth")
    reports_to_employee_id: str | None = Field(default=None, alias="reportsToEmployeeId")
    requires_human_escalation: bool | None = Field(
        default=None, alias="requiresHumanEscalation"
    )

    model_config = ApiCreate.model_config | {"extra": "forbid"}


class ContractVersionRequest(ApiCreate):
    """``POST /api/contracts/{id}/versions`` body.

    Terms may be adjusted while copying; a successor with no changes is still a new
    version, which is the point of a version.
    """

    patch: ContractPatch | None = None
    reason: str | None = Field(default=None, max_length=1000)

    model_config = ApiCreate.model_config | {"extra": "forbid"}


class ResumeRequest(ApiCreate):
    """``POST /api/companies/{id}/resume`` body.

    ``activateContractIds`` are reviewed draft successors to bring into effect during
    the resume. Omit them to resume on the existing active contracts.
    """

    activate_contract_ids: list[str] | None = Field(
        default=None, alias="activateContractIds", max_length=200
    )

    model_config = ApiCreate.model_config | {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class ContractOut(ApiSchema):
    """One contract version, with the terms and its integrity hash."""

    id: str
    company_id: str
    employee_id: str
    version_number: int
    status: str
    role: str
    role_config_version: int
    objective: str | None
    responsibilities: list[str]
    data_scope: list[dict[str, Any]]
    tool_scope: list[dict[str, Any]]
    restrictions: list[str]
    task_scope: list[str]
    communication_policy: dict[str, Any]
    approval_rules: list[dict[str, Any]]
    budget_per_task: Decimal
    budget_per_month: Decimal
    reports_to_employee_id: str | None
    requires_human_escalation: bool
    content_hash: str
    source: str
    supersedes_id: str | None
    effective_at: datetime | None
    activated_at: datetime | None
    superseded_at: datetime | None
    created_at: datetime


class ContractSummaryOut(ApiSchema):
    """List view: identity and version metadata, not the whole document."""

    id: str
    employee_id: str
    version_number: int
    status: str
    role: str
    role_config_version: int
    content_hash: str
    supersedes_id: str | None
    activated_at: datetime | None
    created_at: datetime


class ContractGenerationOut(ApiSchema):
    """Result of generating a draft contract set."""

    company_id: str
    #: Draft contract ids created by this run, in employee order.
    contract_ids: list[str]
    employee_count: int
    #: Draft ids replaced by a regeneration, if any.
    replaced_contract_ids: list[str]
    total_monthly_allocation: Decimal
    currency: str
    warnings: list[str] = []


class ActivationOut(ApiSchema):
    """Result of activating a company and its contracts."""

    company_id: str
    status: str
    revision: int
    employee_count: int
    contract_ids: list[str]
    activated_at: datetime
    #: Contracts superseded during the same transaction, for a resume.
    superseded_contract_ids: list[str] = []


CompanyStatusLiteral = Literal["draft", "active", "paused"]


__all__ = [
    "ActivationOut",
    "ApprovalRuleIn",
    "BudgetAmount",
    "CommunicationPolicyIn",
    "ContractGenerateRequest",
    "ContractGenerationOut",
    "ContractOut",
    "ContractPatch",
    "ContractSummaryOut",
    "ContractVersionRequest",
    "DataScopeIn",
    "EmployeeAllocation",
    "ResumeRequest",
    "ToolScopeIn",
]