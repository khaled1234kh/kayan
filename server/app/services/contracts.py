"""Contract generation, editing and versioning.

**Generation** derives one draft contract per configured employee from the versioned
role catalogue, applies the owner's explicit budget allocations, validates the
resulting set, and persists every contract in one transaction. Nothing is published
until that commit succeeds.

Budget allocations are requested, never invented. ``CompanyEmployee`` does not retain
a draft allocation, so ``generate`` takes one per employee and refuses the request if
the set does not exactly cover the workforce. Silently deriving a budget would put
money in a contract that nobody chose.

**Editing** applies to drafts only, and always validates the *complete* resulting
contract rather than the fields the request mentioned. An activated contract is
immutable — the database enforces it, and the service refuses first.

**Versioning** creates a draft successor from an activated contract. The predecessor
is untouched: it stays active until a later resume brings the successor into effect.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.company.contract_terms import MATERIAL_COLUMNS, compute_content_hash
from app.company.contract_validation import ContractValidationContext, validate_contract
from app.company.errors import ConfigurationError, ConflictError, NotFoundError
from app.models import (
    Company,
    CompanyEmployee,
    CompanyStatus,
    Contract,
    ContractStatus,
    RoleTemplate,
    utcnow,
)
from app.schemas.contract import (
    ContractGenerateRequest,
    ContractPatch,
    ContractVersionRequest,
)
from app.services.companies import STREAM_ID, CompanyService
from app.services.events import EventService
from app.services.workforce import WorkforceService

logger = logging.getLogger(__name__)

#: Where generated terms came from. Recorded so a later reader can tell a generated
#: contract from an owner-authored one without diffing content.
SOURCE_GENERATED = "generated"
SOURCE_SUCCESSOR = "successor"


def new_contract_id() -> str:
    return f"ctr_{uuid.uuid4().hex[:12]}"


class ContractService:
    def __init__(self, session: Session, events: EventService | None = None) -> None:
        self._session = session
        self._events = events or EventService(session)
        self._companies = CompanyService(session, self._events)
        self._workforce = WorkforceService(session, self._events)

    # -- catalogue ---------------------------------------------------------

    def catalogue(self) -> dict[str, RoleTemplate]:
        """Current version of every seeded role, keyed by role key."""
        newest = (
            select(
                RoleTemplate.key.label("key"),
                func.max(RoleTemplate.config_version).label("version"),
            )
            .group_by(RoleTemplate.key)
            .subquery()
        )
        stmt = (
            select(RoleTemplate)
            .join(
                newest,
                and_(
                    newest.c.key == RoleTemplate.key,
                    newest.c.version == RoleTemplate.config_version,
                ),
            )
            .order_by(RoleTemplate.key)
        )
        return {role.key: role for role in self._session.execute(stmt).scalars()}

    # -- reads -------------------------------------------------------------

    def get(self, contract_id: str) -> Contract:
        contract = self._session.get(Contract, contract_id)
        if contract is None:
            raise NotFoundError(
                f"Contract '{contract_id}' not found", field="contractId"
            )
        return contract

    def list_for_company(self, company_id: str) -> list[Contract]:
        self._companies.get_company(company_id)
        stmt = (
            select(Contract)
            .where(Contract.company_id == company_id)
            .order_by(Contract.employee_id, Contract.version_number)
        )
        return list(self._session.execute(stmt).scalars())

    # -- generation --------------------------------------------------------

    def generate(self, company_id: str, payload: ContractGenerateRequest) -> list[Contract]:
        """Create one draft contract per employee, atomically.

        Regeneration replaces unactivated drafts and never touches an activated one.
        """
        company = self._companies.get_company(company_id)
        if company.status is not CompanyStatus.DRAFT:
            raise ConflictError(
                f"Company '{company_id}' is {company.status.value}; contracts are generated "
                "while the company is still a draft",
                field="status",
            )

        employees = self._workforce.list_employees(company_id)
        if not employees:
            raise ConfigurationError(
                f"Company '{company_id}' has no configured workforce to write contracts for",
                field="employees",
            )

        allocations = self._resolve_allocations(company, employees, payload)
        catalogue = self.catalogue()
        totals = {
            employee_id: entry["budgetPerMonth"] for employee_id, entry in allocations.items()
        }
        context = self._context(company, employees, catalogue, totals)

        existing = self.list_for_company(company_id)
        activated = [row for row in existing if row.status is ContractStatus.ACTIVE]
        if activated:
            raise ConflictError(
                f"Company '{company_id}' already has {len(activated)} activated contract(s); "
                "activated terms are never regenerated",
                field="status",
            )
        drafts = [row for row in existing if row.status is ContractStatus.DRAFT]
        if drafts and not payload.replace_existing:
            raise ConflictError(
                f"Company '{company_id}' already has {len(drafts)} draft contract(s); "
                "send replaceExisting to regenerate",
                field="replaceExisting",
            )

        created: list[Contract] = []
        for employee in employees:
            allocation = allocations[employee.id]
            # Regeneration supersedes the previous drafts rather than replacing them,
            # so the new set takes the next version number: (employee, version) is
            # unique, and history is never rewritten.
            next_version = 1 + max(
                (
                    contract.version_number
                    for contract in existing
                    if contract.employee_id == employee.id
                ),
                default=0,
            )
            contract = Contract(
                id=new_contract_id(),
                company_id=company_id,
                employee_id=employee.id,
                version_number=next_version,
                status=ContractStatus.DRAFT,
                source=SOURCE_GENERATED,
            )
            self._apply_role_defaults(contract, employee, catalogue, context)
            contract.reports_to_employee_id = employee.reports_to_id
            contract.budget_per_month = allocation["budgetPerMonth"]
            contract.budget_per_task = allocation["budgetPerTask"]
            contract.content_hash = compute_content_hash(contract)
            self._session.add(contract)
            created.append(contract)

        # Validate as a set before anything is written to the database, so a failure
        # leaves the previous draft set exactly as it was.
        for contract in created:
            validate_contract(contract, context)

        # Drafts are superseded rather than deleted: history is append-only, and the
        # database refuses to delete an activated row anyway.
        self._session.flush()
        for stale in drafts:
            stale.status = ContractStatus.SUPERSEDED
            stale.superseded_at = utcnow()

        event = self._events.stage(
            event_type="contract_generated",
            stream_id=STREAM_ID,
            target_id=company_id,
            payload={
                "companyId": company_id,
                "contractIds": sorted(row.id for row in created),
                "employeeIds": sorted(employee.id for employee in employees),
                "replacedContractIds": sorted(row.id for row in drafts),
                "source": SOURCE_GENERATED,
            },
        )
        self._events.commit_and_publish([event])
        self._session.refresh(created[0])
        logger.info(
            "generated %d draft contract(s) for company %s", len(created), company_id
        )
        return created

    # -- editing -----------------------------------------------------------

    def patch(self, contract_id: str, payload: ContractPatch) -> tuple[Contract, bool]:
        """Edit a draft contract. Returns the contract and whether it changed."""
        contract = self.get(contract_id)
        if contract.status is not ContractStatus.DRAFT or contract.activated_at is not None:
            raise ConflictError(
                f"Contract '{contract_id}' is {contract.status.value}; only a draft contract "
                "can be edited. A change to an active contract requires a successor version.",
                field="status",
            )

        changes = payload.model_dump(exclude_unset=True, by_alias=True)
        if not changes:
            return contract, False

        before = compute_content_hash(contract)
        self._apply_changes(contract, changes)

        # Validate the complete resulting contract, not just the changed fields.
        company = self._companies.get_company(contract.company_id)
        employees = self._workforce.list_employees(contract.company_id)
        context = self._context(
            company, employees, self.catalogue(), self._existing_allocations(employees)
        )
        validate_contract(contract, context)

        after = compute_content_hash(contract)
        if after == before:
            # The request changed nothing material, so the audit trail says nothing.
            return contract, False

        contract.content_hash = after
        self._session.flush()
        event = self._events.stage(
            event_type="contract_updated",
            stream_id=STREAM_ID,
            target_id=contract.id,
            payload={
                "companyId": contract.company_id,
                "contractId": contract.id,
                "employeeId": contract.employee_id,
                "versionNumber": contract.version_number,
                "changedFields": sorted(changes),
                "contentHash": contract.content_hash,
            },
        )
        self._events.commit_and_publish([event])
        self._session.refresh(contract)
        return contract, True

    # -- versioning --------------------------------------------------------

    def create_successor(
        self, contract_id: str, payload: ContractVersionRequest
    ) -> Contract:
        """Create a draft successor to an activated contract.

        The predecessor is left active and untouched. The successor takes effect only
        when it is explicitly activated, which for P0.4 means during a resume.
        """
        source = self.get(contract_id)
        if source.status is not ContractStatus.ACTIVE:
            raise ConflictError(
                f"Contract '{contract_id}' is {source.status.value}; only an activated "
                "contract can be superseded by a new version",
                field="status",
            )

        company = self._companies.get_company(source.company_id)
        existing_versions = [
            row.version_number
            for row in self.list_for_company(source.company_id)
            if row.employee_id == source.employee_id
        ]
        next_version = max(existing_versions, default=source.version_number) + 1

        successor = Contract(
            id=new_contract_id(),
            company_id=source.company_id,
            employee_id=source.employee_id,
            version_number=next_version,
            status=ContractStatus.DRAFT,
            role=source.role,
            role_config_version=source.role_config_version,
            objective=source.objective,
            responsibilities=list(source.responsibilities or []),
            data_scope=list(source.data_scope or []),
            tool_scope=list(source.tool_scope or []),
            restrictions=list(source.restrictions or []),
            task_scope=list(source.task_scope or []),
            communication_policy=dict(source.communication_policy or {}),
            approval_rules=list(source.approval_rules or []),
            budget_per_task=Decimal(source.budget_per_task),
            budget_per_month=Decimal(source.budget_per_month),
            reports_to_employee_id=source.reports_to_employee_id,
            requires_human_escalation=source.requires_human_escalation,
            supersedes_id=source.id,
            source=SOURCE_SUCCESSOR,
        )
        if payload.patch is not None:
            changes = payload.patch.model_dump(exclude_unset=True, by_alias=True)
            if changes:
                self._apply_changes(successor, changes)
        successor.content_hash = compute_content_hash(successor)

        employees = self._workforce.list_employees(source.company_id)
        context = self._context(
            company, employees, self.catalogue(), self._existing_allocations(employees)
        )
        # Validate before inserting so an invalid successor is never persisted.
        validate_contract(successor, context)

        self._session.add(successor)
        self._session.flush()

        event = self._events.stage(
            event_type="contract_version_created",
            stream_id=STREAM_ID,
            target_id=successor.id,
            payload={
                "companyId": successor.company_id,
                "contractId": successor.id,
                "predecessorContractId": source.id,
                "employeeId": successor.employee_id,
                "versionNumber": successor.version_number,
                "reason": payload.reason,
            },
        )
        self._events.commit_and_publish([event])
        self._session.refresh(successor)
        logger.info(
            "created successor %s (v%d) for contract %s",
            successor.id,
            successor.version_number,
            source.id,
        )
        return successor

    # -- internals ---------------------------------------------------------

    def _apply_role_defaults(
        self,
        contract: Contract,
        employee: CompanyEmployee,
        catalogue: dict[str, RoleTemplate],
        context: ContractValidationContext,
    ) -> None:
        """Least-privilege defaults: the role's own scopes, narrowed to what the seat needs."""
        role = catalogue.get(employee.role_key)
        if role is None:
            raise ConfigurationError(
                f"Employee '{employee.id}' has role '{employee.role_key}', which is not in "
                "the role catalogue",
                field="employees",
            )

        # The role *key*, not its label: the key is the stable identifier the catalogue is
        # keyed by, while a label is display text that may be reworded. Validation
        # resolves this value back to a catalogue entry.
        contract.role = role.key
        contract.role_config_version = role.config_version
        contract.objective = employee.objective or (role.summary or role.label)
        # An employee's own responsibilities override the role's only where they
        # supplied some; otherwise the catalogue's stand in.
        contract.responsibilities = list(
            employee.responsibilities or role.responsibilities or []
        )
        contract.data_scope = [dict(entry) for entry in (role.default_data_scope or [])]
        contract.tool_scope = [dict(entry) for entry in (role.default_tool_scope or [])]
        contract.restrictions = list(role.default_restrictions or [])
        contract.task_scope = list(role.task_categories or [])
        contract.requires_human_escalation = role.kind == "human"
        contract.communication_policy = _communication_for(employee, context)

        # A restriction in the catalogue that says this role may not finalise an
        # action without approval becomes an explicit approval rule, so the
        # requirement is executable rather than advisory.
        if "finalize_without_ceo_approval" in (role.default_restrictions or []):
            contract.approval_rules = [
                {"action": "finalize", "requiredApprover": "ceo"}
            ]
        else:
            contract.approval_rules = []

    def _apply_changes(self, contract: Contract, changes: dict) -> None:
        """Write a validated field set onto a contract.

        ``model_dump`` already lowers nested models to plain dicts, so both a model
        and a dict are accepted here rather than assuming one shape.
        """
        for field, value in changes.items():
            if field == "dataScope":
                contract.data_scope = [_as_dict(entry) for entry in value]
            elif field == "toolScope":
                contract.tool_scope = [_as_dict(entry) for entry in value]
            elif field == "communicationPolicy":
                contract.communication_policy = _as_dict(value)
            elif field == "approvalRules":
                contract.approval_rules = [_as_dict(rule) for rule in value]
            else:
                column = _CAMEL_TO_COLUMN.get(field)
                if column is None:  # pragma: no cover - schema rejects unknown fields
                    raise ConfigurationError(
                        f"'{field}' is not an editable contract term", field=field
                    )
                setattr(contract, column, value)

    def _resolve_allocations(
        self,
        company: Company,
        employees: list[CompanyEmployee],
        payload: ContractGenerateRequest,
    ) -> dict[str, dict[str, Decimal]]:
        """Match allocations to employees exactly, and fit them inside the ceiling.

        Precedence rule: allocations are always taken from the request. The employee
        model does not retain a draft allocation, so there is nothing persisted to
        fall back to, and deriving one would put unchosen money into a contract.
        """
        employee_ids = {employee.id for employee in employees}
        supplied = payload.allocations

        duplicates = sorted(
            {a.employee_id for a in supplied if [x.employee_id for x in supplied].count(a.employee_id) > 1}
        )
        if duplicates:
            raise ConfigurationError(
                f"Allocations supplied more than once for: {', '.join(duplicates)}",
                field="allocations",
            )

        unknown = sorted({a.employee_id for a in supplied} - employee_ids)
        if unknown:
            raise ConfigurationError(
                f"Allocations reference employees that are not in this company: "
                f"{', '.join(unknown)}",
                field="allocations",
            )
        missing = sorted(employee_ids - {a.employee_id for a in supplied})
        if missing:
            raise ConfigurationError(
                f"No budget allocation supplied for: {', '.join(missing)}. Every employee "
                "needs one; budgets are never invented.",
                field="allocations",
            )

        resolved: dict[str, dict[str, Decimal]] = {}
        for allocation in supplied:
            if allocation.budget_per_task > allocation.budget_per_month:
                raise ConfigurationError(
                    f"Per-task ceiling {allocation.budget_per_task} exceeds the monthly "
                    f"allocation {allocation.budget_per_month} for '{allocation.employee_id}'",
                    field="allocations",
                )
            resolved[allocation.employee_id] = {
                "budgetPerMonth": allocation.budget_per_month,
                "budgetPerTask": allocation.budget_per_task,
            }

        ceiling = self._companies.get_budget_account(company.id)
        if ceiling is None:
            raise ConfigurationError(
                f"Company '{company.id}' has no budget account, so contracts cannot be "
                "allocated against a ceiling",
                field="companyId",
            )
        total = sum(
            (entry["budgetPerMonth"] for entry in resolved.values()), Decimal("0")
        )
        if total > Decimal(ceiling.monthly_limit):
            raise ConfigurationError(
                f"Allocations total {total}, which exceeds the company ceiling of "
                f"{ceiling.monthly_limit}",
                field="allocations",
            )
        return resolved

    def _existing_allocations(
        self, employees: list[CompanyEmployee]
    ) -> dict[str, Decimal]:
        """Monthly allocation per employee, taken from this company's current contracts."""
        if not employees:
            return {}
        ids = [employee.id for employee in employees]
        stmt = select(Contract.employee_id, Contract.budget_per_month).where(
            Contract.employee_id.in_(ids)
        )
        totals: dict[str, Decimal] = {}
        for employee_id, amount in self._session.execute(stmt).all():
            totals[employee_id] = Decimal(amount)
        return totals

    def _context(
        self,
        company: Company,
        employees: list[CompanyEmployee],
        catalogue: dict[str, RoleTemplate],
        allocated_totals: dict[str, Decimal],
    ) -> ContractValidationContext:
        """Build the validation context from the current draft set."""
        account = self._companies.get_budget_account(company.id)
        return ContractValidationContext(
            catalogue=catalogue,
            employee_ids={employee.id for employee in employees},
            reporting_lines={
                employee.id: employee.reports_to_id for employee in employees
            },
            monthly_ceiling=Decimal(account.monthly_limit) if account else None,
            allocated_totals=allocated_totals,
        )


def _as_dict(value) -> dict:
    """Lower a Pydantic model or pass a dict through, so both shapes work."""
    if isinstance(value, dict):
        return dict(value)
    return value.model_dump(by_alias=True)


def _communication_for(
    employee: CompanyEmployee, context: ContractValidationContext
) -> dict:
    """Default communication: talk to your manager, and nobody else unsolicited."""
    manager = employee.reports_to_id
    return {
        "allow": [manager] if manager else [],
        "broadcast": False,
        "maxRounds": 3,
    }


#: Incoming camelCase field -> ORM column.
_CAMEL_TO_COLUMN = {
    "role": "role",
    "roleConfigVersion": "role_config_version",
    "objective": "objective",
    "responsibilities": "responsibilities",
    "restrictions": "restrictions",
    "taskScope": "task_scope",
    "budgetPerTask": "budget_per_task",
    "budgetPerMonth": "budget_per_month",
    "reportsToEmployeeId": "reports_to_employee_id",
    "requiresHumanEscalation": "requires_human_escalation",
}

#: Contract terms an owner may edit. Every one is a material column, so editing any
#: of them changes the integrity hash.
EDITABLE_COLUMNS = frozenset(_CAMEL_TO_COLUMN) | frozenset(
    {"dataScope", "toolScope", "communicationPolicy", "approvalRules"}
)


def get_contract_service(session: Session) -> ContractService:
    return ContractService(session)


__all__ = [
    "ContractService",
    "EDITABLE_COLUMNS",
    "MATERIAL_COLUMNS",
    "SOURCE_GENERATED",
    "SOURCE_SUCCESSOR",
    "get_contract_service",
    "new_contract_id",
]