"""Company, workforce, contract and budget models (P0.1).

Design decisions that come from review, recorded here so they are not relitigated:

**Configuration-only identity.** ``CompanyEmployee`` is deliberately a separate
table from ``Agent``. P0 does not insert configured employees into the canonical
``agents`` table, and it never reuses the canonical demo ids (``manager``,
``sales``, ``operations``, ``employee``, ``ceo``). Configured employees therefore
carry their own id prefix and cannot collide with the demo workforce. The
``CompanyEmployee`` -> active contract -> runtime execution mapping belongs to the
next runtime phase, not here.

**Money.** All monetary values are ``Numeric(18, 6)`` mapped to ``Decimal``.
Floating point is never used for authorisation. One currency per company for P0;
a mismatched currency is rejected rather than converted.

**Contract immutability.** Substantive terms are frozen once ``activated_at`` is
set. Lifecycle transitions (draft -> active -> superseded) remain possible, and
deletion of an activated contract is refused. The database trigger created in the
migration compares only the material-term columns, so it permits a status change
while rejecting an edit to the terms themselves.

**One active company.** Multiple drafts may exist; a partial unique index permits
at most one ``active`` company. The ownership boundary is revisited with auth.

**Logical workflow offsets.** Persisted events always carry a real UTC timestamp.
Deterministic workflow offsets are preserved separately in ``clock_offset_ms`` and
are used only for experiment timing, so the feed is real-time while logical
durations stay reproducible.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.models import JSONVariant, TaskStatus, enum_column

#: Money scale shared by every monetary column.
MONEY = Numeric(18, 6)

#: Configured-employee id prefix. Guarantees a configured employee can never be
#: mistaken for a canonical demo agent.
EMPLOYEE_ID_PREFIX = "emp_"

#: Company id prefix, for the same collision reason.
COMPANY_ID_PREFIX = "cmp_"


def new_company_id() -> str:
    """A company id that cannot collide with a demo or legacy id."""
    return f"{COMPANY_ID_PREFIX}{uuid.uuid4().hex[:12]}"

#: ISO 4217. One currency per company for P0; no FX conversion.
SUPPORTED_CURRENCIES = (
    "USD",
    "EUR",
    "GBP",
    "EGP",
    "AED",
    "SAR",
    "JPY",
    "CNY",
    "INR",
    "CAD",
    "AUD",
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_employee_id(suffix: str) -> str:
    """A configured-employee id that can never collide with a demo agent id."""
    return f"{EMPLOYEE_ID_PREFIX}{suffix}"


def new_employee_id_for_new_seat() -> str:
    """A fresh configured-employee id for a seat the client has not seen yet."""
    return new_employee_id(uuid.uuid4().hex[:12])


class CompanyStatus(str, enum.Enum):
    """P0 lifecycle. Permanent deactivation/archival is deferred."""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"


class EmployeeStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    RETIRED = "retired"


class ContractStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class BudgetReservationStatus(str, enum.Enum):
    ACTIVE = "active"
    SETTLED = "settled"
    RELEASED = "released"


class BudgetLedgerCategory(str, enum.Enum):
    """Ledger entry kinds.

    Sign convention: ``amount`` is signed, and only ``ACTUAL_COST_CHARGED`` and
    ``REFUND_OR_ADJUSTMENT`` contribute to actual spend. ``RESERVATION_CREATED`` and
    ``RESERVATION_RELEASED`` are commitments, not costs — counting them as spend as
    well would deduct the same money twice, once as a commitment and once as a cost.
    """

    #: Funds committed. Recorded for the audit trail; excluded from actual spend.
    RESERVATION_CREATED = "reservation_created"
    #: Commitment returned unused. Negative of the released amount; excluded from spend.
    RESERVATION_RELEASED = "reservation_released"
    #: The real cost of executed work. This is what counts as spend.
    ACTUAL_COST_CHARGED = "actual_cost_charged"
    #: A correction. Negative to refund, positive to charge.
    REFUND_OR_ADJUSTMENT = "refund_or_adjustment"
    #: A ceiling was changed. The amount is signed: positive when raised, negative
    #: when lowered. It does not count as spend — money committed to employees is
    #: authorised capacity, not money spent.
    BUDGET_INCREASED = "budget_increased"
    BUDGET_LIMIT_REACHED = "budget_limit_reached"
    #: A reservation that was refused. No money moved; recorded so the refusal is
    #: auditable rather than invisible.
    RESERVATION_DENIED = "reservation_denied"

    @property
    def counts_as_spend(self) -> bool:
        """Whether entries of this kind contribute to actual committed spend."""
        return self in (BudgetLedgerCategory.ACTUAL_COST_CHARGED, BudgetLedgerCategory.REFUND_OR_ADJUSTMENT)


class CostCategory(str, enum.Enum):
    """What a metered cost is for.

    A message and the model call that produced it are the same billable operation,
    so both are recorded but charged once.
    """

    LLM_INPUT_TOKENS = "llm_input_tokens"
    LLM_OUTPUT_TOKENS = "llm_output_tokens"
    TOOL_CALL = "tool_call"
    AGENT_MESSAGE = "agent_message"
    OTHER = "other"


class MeterSource(str, enum.Enum):
    """Where a metered figure came from.

    ``MOCK`` means simulated. It is never a provider invoice, and a mock cost is
    never presented as real money spent.
    """

    MOCK = "mock"
    PROVIDER = "provider"


class CompanyTask(Base):
    """A unit of company work that can be billed.

    P0.1 gave the reservation and ledger a ``task_id`` with no table behind it,
    because the only task concept then was the demo workflow's order. Budget
    enforcement needs a task the company owns: the per-task ceiling has to be
    aggregated over work belonging to one employee of one company, and the
    association has to be verifiable rather than a free-form string.

    ``category`` is checked against the assigned employee's contract task scope, so
    the task is drawn from the same vocabulary the contract permits.
    """

    __tablename__ = "company_tasks"
    __table_args__ = (
        Index("ix_company_tasks_company_status", "company_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("company_employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    #: Must appear in the assigned employee's contract ``task_scope``.
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        enum_column(TaskStatus), default=TaskStatus.OPEN, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<CompanyTask {self.id} {self.category} {self.status.value}>"


def new_company_task_id() -> str:
    return f"tsk_{uuid.uuid4().hex[:12]}"


def new_reservation_id() -> str:
    return f"res_{uuid.uuid4().hex[:12]}"


def new_ledger_entry_id() -> str:
    return f"led_{uuid.uuid4().hex[:12]}"


class Company(Base):
    """The configured business. Holds a measurable target, not just prose."""

    __tablename__ = "companies"
    __table_args__ = (
        # Multiple drafts may exist; at most one company may be active. Written as
        # a partial unique index so the constraint only applies to active rows.
        Index(
            "uq_one_active_company",
            text("status"),
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
        CheckConstraint("length(currency) = 3", name="ck_company_currency_iso"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(120))
    #: Which catalogue template the configuration was based on.
    template_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    #: Human-readable objective, kept alongside the structured target so the
    #: owner can read what the machine-readable target means.
    target_description: Mapped[str | None] = mapped_column(Text)
    target_metric: Mapped[str | None] = mapped_column(String(64))
    target_value: Mapped[Decimal | None] = mapped_column(MONEY)
    target_unit: Mapped[str | None] = mapped_column(String(32))
    target_period: Mapped[str | None] = mapped_column(String(32))
    #: Budget currency. One per company for P0.
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[CompanyStatus] = mapped_column(
        enum_column(CompanyStatus, 16), default=CompanyStatus.DRAFT, nullable=False, index=True
    )
    #: Bumped on every configuration change; the roster projection sent with
    #: ``company_activated`` carries it so clients can detect staleness.
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
        nullable=False,
    )

    employees: Mapped[list["CompanyEmployee"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Company {self.id} {self.status.value}>"


class RoleTemplate(Base):
    """Reusable role definition, maintained as versioned seed data.

    Deliberately not a template-management product: rows are seeded and versioned
    with ``config_version``.
    """

    __tablename__ = "role_templates"
    __table_args__ = (
        # Versioned catalogue rows: a new definition creates a new version rather
        # than overwriting the one an existing contract was generated from.
        CheckConstraint("config_version >= 1", name="ck_role_template_version_positive"),
    )

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    config_version: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    #: Human or AI seat.
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    responsibilities: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    task_categories: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    default_data_scope: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    default_tool_scope: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    default_restrictions: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    #: Company templates this role is offered for.
    template_keys: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    #: Bumped when the definition changes, so an existing contract stays
    #: explainable against the version that produced it.
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<RoleTemplate {self.key} v{self.config_version}>"


class CompanyEmployee(Base):
    """An employee configured for a company.

    Configuration only in P0: this row does not grant execution authority. The
    runtime mapping (employee -> active contract -> agent execution) is the next
    phase.
    """

    __tablename__ = "company_employees"
    __table_args__ = (
        CheckConstraint("reports_to_id <> id", name="ck_employee_not_self_reports"),
        Index("ix_company_employees_company", "company_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    #: Display name. Never an identifier: names change, ids do not.
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    role_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    #: User-defined role description, when the role is not a catalogue role.
    custom_role: Mapped[str | None] = mapped_column(Text)
    objective: Mapped[str | None] = mapped_column(Text)
    #: Draft responsibilities. Empty means "inherit the role template's default",
    #: which is resolved when a contract is generated in P0.4 — the contract, not
    #: this row, becomes authoritative once a company is activated.
    responsibilities: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    status: Mapped[EmployeeStatus] = mapped_column(
        enum_column(EmployeeStatus, 16), default=EmployeeStatus.DRAFT, nullable=False
    )
    reports_to_id: Mapped[str | None] = mapped_column(
        ForeignKey("company_employees.id", ondelete="SET NULL"), index=True
    )
    #: Currently effective contract version. ``use_alter`` breaks the cycle with
    #: ``contracts.employee_id`` so both tables can be created in one pass.
    active_contract_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "contracts.id",
            name="fk_company_employees_active_contract",
            ondelete="SET NULL",
            use_alter=True,
        ),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )

    company: Mapped[Company] = relationship(back_populates="employees")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<CompanyEmployee {self.id} {self.status.value}>"


class Contract(Base):
    """Versioned contract: the formal boundary for an employee's authority.

    Substantive terms are frozen once ``activated_at`` is set. Only lifecycle
    columns may change afterwards, and an activated contract is never deleted.
    """

    __tablename__ = "contracts"
    __table_args__ = (
        UniqueConstraint("employee_id", "version_number", name="uq_contract_version"),
        CheckConstraint("version_number >= 1", name="ck_contract_version_positive"),
        CheckConstraint("budget_per_month >= 0", name="ck_contract_budget_non_negative"),
        CheckConstraint("budget_per_task >= 0", name="ck_contract_task_budget_non_negative"),
        CheckConstraint(
            "reports_to_employee_id <> employee_id", name="ck_contract_not_self_reports"
        ),
        # An employee has at most one effective contract; a supersession inserts
        # the next version rather than reactivating an old one.
        Index(
            "uq_contract_active_per_employee",
            "employee_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_contracts_company_status", "company_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("company_employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ContractStatus] = mapped_column(
        enum_column(ContractStatus, 16), default=ContractStatus.DRAFT, nullable=False
    )

    # -- material terms (frozen at activation) ---------------------------
    role: Mapped[str] = mapped_column(String(160), nullable=False)
    #: The exact catalogue version these terms were derived from. Recorded so the
    #: contract stays explainable after the role is revised, and so terms hashed
    #: against one definition cannot be mistaken for terms of another.
    role_config_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    objective: Mapped[str | None] = mapped_column(Text)
    responsibilities: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    #: Structured, validated scope: [{resource, operations}]
    data_scope: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    #: Structured scope: [{tool, actions}]
    tool_scope: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    restrictions: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    task_scope: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    #: {allow: [...], broadcast: bool, max_rounds: int, ...}
    communication_policy: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    #: [{action, requiredApprover, ...}]
    approval_rules: Mapped[list] = mapped_column(JSONVariant, default=list, nullable=False)
    budget_per_task: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    budget_per_month: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    reports_to_employee_id: Mapped[str | None] = mapped_column(
        ForeignKey("company_employees.id", ondelete="SET NULL"), index=True
    )
    #: True when this seat must hand a decision to a human rather than act. A seat
    #: with no human escalation and no approval rule may complete its own work, which
    #: is why this is a term of the contract rather than a UI preference.
    requires_human_escalation: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # -- lifecycle ---------------------------------------------------------
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_id: Mapped[str | None] = mapped_column(
        ForeignKey("contracts.id", ondelete="SET NULL")
    )
    #: SHA-256 over every material term, budgets and reporting line included.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Labels the origin of the terms: generated from a role template, proposed
    #: by a recommendation, or edited by the owner.
    source: Mapped[str] = mapped_column(String(32), default="template", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Contract {self.id} v{self.version_number} {self.status.value}>"


class BudgetAccount(Base):
    """The company's ceiling for one accounting period.

    Available = monthly_limit - actual_spend - outstanding_reservations, all
    computed from the ledger and active reservations rather than stored.
    """

    __tablename__ = "budget_accounts"
    __table_args__ = (
        UniqueConstraint("company_id", "period_start", name="uq_budget_account_period"),
        CheckConstraint("monthly_limit >= 0", name="ck_budget_limit_non_negative"),
        CheckConstraint("length(currency) = 3", name="ck_budget_currency_iso"),
        CheckConstraint("period_end > period_start", name="ck_budget_period_ordered"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    monthly_limit: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    #: Bumped by every owner adjustment, so an increase is traceable.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )

    reservations: Mapped[list["BudgetReservation"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<BudgetAccount {self.id} {self.currency} {self.monthly_limit}>"


class BudgetReservation(Base):
    """Funds held for work that has not settled yet.

    A billable operation may not begin until a reservation exists at the company,
    employee and task ceilings. Settling or releasing makes the row terminal.
    """

    __tablename__ = "budget_reservations"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_reservation_idempotency"),
        CheckConstraint("amount > 0", name="ck_reservation_positive"),
        Index("ix_reservations_account_status", "account_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("budget_accounts.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[str | None] = mapped_column(
        ForeignKey("company_employees.id", ondelete="SET NULL"), index=True
    )
    task_id: Mapped[str | None] = mapped_column(
        ForeignKey("company_tasks.id", ondelete="SET NULL"), index=True
    )
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="SET NULL"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[BudgetReservationStatus] = mapped_column(
        enum_column(BudgetReservationStatus, 16),
        default=BudgetReservationStatus.ACTIVE,
        nullable=False,
    )
    #: Makes a redelivered reserve/settle/release a no-op.
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    #: Groups the ledger entries charged for one real-world operation, so a
    #: message and the model call that produced it are not billed twice.
    billable_operation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    account: Mapped[BudgetAccount] = relationship(back_populates="reservations")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<BudgetReservation {self.id} {self.amount} {self.status.value}>"


class BudgetLedgerEntry(Base):
    """Append-only financial history.

    Entries are never modified or deleted; a mistake is corrected with an
    explicit adjustment entry.
    """

    __tablename__ = "budget_ledger_entries"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ledger_idempotency"),
        Index("ix_ledger_company_created", "company_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[str | None] = mapped_column(
        ForeignKey("budget_accounts.id", ondelete="SET NULL"), index=True
    )
    reservation_id: Mapped[str | None] = mapped_column(
        ForeignKey("budget_reservations.id", ondelete="SET NULL"), index=True
    )
    employee_id: Mapped[str | None] = mapped_column(
        ForeignKey("company_employees.id", ondelete="SET NULL"), index=True
    )
    task_id: Mapped[str | None] = mapped_column(
        ForeignKey("company_tasks.id", ondelete="SET NULL"), index=True
    )
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="SET NULL"), index=True
    )
    category: Mapped[BudgetLedgerCategory] = mapped_column(
        enum_column(BudgetLedgerCategory, 32), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    #: Running available balance after this entry, for cheap reconciliation.
    balance_after: Mapped[Decimal | None] = mapped_column(MONEY)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    billable_operation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<BudgetLedgerEntry {self.id} {self.category.value} {self.amount}>"


class RecommendationStatus(str, enum.Enum):
    """Lifecycle of a recommendation.

    ``proposed`` is the only status a generated recommendation gets. ``accepted`` is
    reserved for an explicit owner confirmation in a later integration stage, so the
    existence of a proposal never implies that anyone adopted it.
    """

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Recommendation(Base):
    """A workforce proposal, kept as a historical record.

    A recommendation is a *proposal*, not a configuration: generating one never
    creates an employee, a contract, or a budget movement. The row exists so the
    exact proposal that was shown to the owner can be retrieved and audited later.

    The proposal is stored as a self-contained snapshot rather than as references
    into the role catalogue. A catalogue entry may be revised in a later
    ``config_version``; a historical record must still say what was actually
    recommended at the time, so it stores the roles, scopes and explanations
    verbatim alongside the version they came from.
    """

    __tablename__ = "recommendations"
    __table_args__ = (
        CheckConstraint("proposed_employee_count >= 1", name="ck_recommendation_has_employee"),
        Index("ix_recommendations_company_created", "company_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: ``template`` or ``model``. Recorded so a proposal is never later mistaken for
    #: the other: a fallback must not be presented as a model result.
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    #: Provider and model identifiers when the source is a model, else null.
    provider_name: Mapped[str | None] = mapped_column(String(64))
    model_name: Mapped[str | None] = mapped_column(String(128))
    #: The request as received, so the input is auditable without re-deriving it.
    preferences: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    #: Version of the role catalogue the proposal was built against.
    role_catalog_version: Mapped[int] = mapped_column(Integer, nullable=False)
    #: The validated proposal, snapshotted in full.
    proposal: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    proposed_employee_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[RecommendationStatus] = mapped_column(
        enum_column(RecommendationStatus, 16),
        default=RecommendationStatus.PROPOSED,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Recommendation {self.id} {self.source} v{self.role_catalog_version}>"


def new_recommendation_id() -> str:
    return f"rec_{uuid.uuid4().hex[:12]}"