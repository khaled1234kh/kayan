"""Company lifecycle: activation, pause and resume.

**Activation is one transaction or nothing.** Every check runs first; then contracts
are activated, employees are pointed at their effective contract, and the company
becomes active — all committed together with the events, which are published only
afterwards. A failure at any step rolls back the lot, including the staged event
rows, so no client ever sees an event for a company that was not activated.

**Activation re-verifies rather than trusts.** The contract hash is recomputed and
compared with the value stored at write time, and the whole workforce, role
catalogue, reporting graph, scopes and budget allocation are validated again. A
contract edited behind the service's back, or a catalogue revised since generation,
is caught here rather than becoming live authority.

**Pause and resume preserve history.** Pausing changes one status field; it deletes
nothing and mutates no activated terms. Resuming revalidates, and may bring reviewed
draft successors into effect atomically with superseding their predecessors.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.company.contract_terms import compute_content_hash
from app.company.contract_validation import ContractValidationContext, validate_contract
from app.company.errors import ConfigurationError, ConflictError, NotFoundError
from app.models import (
    Agent,
    BudgetAccount,
    Company,
    CompanyEmployee,
    CompanyStatus,
    Contract,
    ContractStatus,
    EmployeeStatus,
)
from app.schemas.contract import ActivationOut, ResumeRequest
from app.services.companies import STREAM_ID, CompanyService
from app.services.contracts import ContractService
from app.services.events import EventService
from app.services.workforce import WorkforceService

logger = logging.getLogger(__name__)

#: The employee ids the canonical demo owns. A configured employee may never be one
#: of these: they are the demo workforce, not this company's.
DEMO_AGENT_IDS = frozenset({"ceo", "employee", "manager", "sales", "operations"})


class CompanyLifecycleService:
    def __init__(self, session: Session, events: EventService | None = None) -> None:
        self._session = session
        self._events = events or EventService(session)
        self._companies = CompanyService(session, self._events)
        self._contracts = ContractService(session, self._events)
        self._workforce = WorkforceService(session, self._events)

    # -- activation --------------------------------------------------------

    def activate(self, company_id: str) -> ActivationOut:
        """Activate a draft company and every contract its employees need."""
        company = self._companies.get_company(company_id)
        if company.status is CompanyStatus.DRAFT:
            pass
        elif company.status is CompanyStatus.ACTIVE:
            raise ConflictError(
                f"Company '{company_id}' is already active", field="status"
            )
        else:
            raise ConflictError(
                f"Company '{company_id}' is {company.status.value}; a paused company is "
                "resumed, not activated",
                field="status",
            )

        employees, contracts, context = self._validate_for_activation(company)
        moment = datetime.now(timezone.utc)

        try:
            # -- everything below is one transaction
            activated_ids: list[str] = []
            for employee in employees:
                contract = contracts[employee.id]
                contract.status = ContractStatus.ACTIVE
                contract.activated_at = moment
                contract.effective_at = moment
                employee.active_contract_id = contract.id
                employee.status = EmployeeStatus.ACTIVE
                activated_ids.append(contract.id)

            company.status = CompanyStatus.ACTIVE
            company.revision += 1
            self._session.flush()

            staged = []
            for contract in (contracts[employee.id] for employee in employees):
                staged.append(
                    self._events.stage(
                        event_type="contract_activated",
                        stream_id=STREAM_ID,
                        target_id=contract.id,
                        payload={
                            "companyId": company.id,
                            "contractId": contract.id,
                            "employeeId": contract.employee_id,
                            "versionNumber": contract.version_number,
                            "contentHash": contract.content_hash,
                        },
                    )
                )
            staged.append(
                self._events.stage(
                    event_type="company_activated",
                    stream_id=STREAM_ID,
                    target_id=company.id,
                    payload={
                        "companyId": company.id,
                        "revision": company.revision,
                        "employeeIds": sorted(employee.id for employee in employees),
                        "contractIds": sorted(activated_ids),
                        "activatedAt": moment.isoformat(),
                    },
                )
            )

            # The partial unique indexes on companies and contracts are the final
            # arbiters: if another writer won the race, this commit fails here and
            # nothing is published.
            self._events.commit_and_publish(staged)
        except IntegrityError as error:
            self._session.rollback()
            raise ConflictError(
                f"Another company is already active, or an employee already has an active "
                f"contract; '{company.id}' was not activated",
                field="status",
            ) from error

        self._session.refresh(company)
        logger.info(
            "activated company %s with %d contract(s)", company.id, len(activated_ids)
        )
        return ActivationOut(
            company_id=company.id,
            status=company.status.value,
            revision=company.revision,
            employee_count=len(employees),
            contract_ids=sorted(activated_ids),
            activated_at=moment,
        )

    # -- pause -------------------------------------------------------------

    def pause(self, company_id: str) -> ActivationOut:
        """Pause an active company. Changes a status; deletes nothing."""
        company = self._companies.get_company(company_id)
        if company.status is not CompanyStatus.ACTIVE:
            raise ConflictError(
                f"Company '{company_id}' is {company.status.value}; only an active company "
                "can be paused",
                field="status",
            )

        company.status = CompanyStatus.PAUSED
        company.revision += 1
        self._session.flush()

        event = self._events.stage(
            event_type="company_paused",
            stream_id=STREAM_ID,
            target_id=company.id,
            payload={
                "companyId": company.id,
                "revision": company.revision,
                "status": company.status.value,
            },
        )
        self._events.commit_and_publish([event])
        self._session.refresh(company)
        logger.info("paused company %s", company.id)
        return ActivationOut(
            company_id=company.id,
            status=company.status.value,
            revision=company.revision,
            employee_count=0,
            contract_ids=[],
            activated_at=datetime.now(timezone.utc),
        )

    # -- resume ------------------------------------------------------------

    def resume(self, company_id: str, payload: ResumeRequest | None = None) -> ActivationOut:
        """Resume a paused company, optionally activating reviewed successors."""
        payload = payload or ResumeRequest()
        company = self._companies.get_company(company_id)
        if company.status is not CompanyStatus.PAUSED:
            raise ConflictError(
                f"Company '{company_id}' is {company.status.value}; only a paused company "
                "can be resumed",
                field="status",
            )

        employees = self._workforce.list_employees(company_id)
        if not employees:
            raise ConfigurationError(
                f"Company '{company_id}' has no configured workforce", field="employees"
            )
        self._validate_company_state(company)

        catalogue = self._contracts.catalogue()
        account = self._companies.get_budget_account(company_id)
        selected = self._resolve_successors(company, employees, payload)
        effective = self._effective_contracts(company.id, employees, selected)

        context = ContractValidationContext(
            catalogue=catalogue,
            employee_ids={employee.id for employee in employees},
            reporting_lines={employee.id: employee.reports_to_id for employee in employees},
            monthly_ceiling=account.monthly_limit if account else None,
            allocated_totals={
                employee.id: effective[employee.id].budget_per_month for employee in employees
            },
        )
        for contract in effective.values():
            self._verify_hash(contract)
            validate_contract(contract, context)

        moment = datetime.now(timezone.utc)
        superseded_ids: list[str] = []
        staged: list = []

        # -- one transaction
        #
        # Two flushes, one commit. The partial unique index on active contracts is
        # evaluated per statement, so a predecessor must actually be superseded in the
        # database before its successor becomes active — otherwise the intermediate
        # state has two active contracts for one employee and the statement fails.
        # Atomicity comes from the single commit, not from a single flush.
        try:
            for employee in employees:
                contract = effective[employee.id]
                if contract.status is not ContractStatus.DRAFT:
                    continue
                predecessor_id = contract.supersedes_id
                if not predecessor_id:
                    continue
                predecessor = self._session.get(Contract, predecessor_id)
                if predecessor is None or predecessor.status is not ContractStatus.ACTIVE:
                    continue
                predecessor.status = ContractStatus.SUPERSEDED
                predecessor.superseded_at = moment
                superseded_ids.append(predecessor.id)
            self._session.flush()

            for employee in employees:
                contract = effective[employee.id]
                if contract.status is ContractStatus.DRAFT:
                    contract.status = ContractStatus.ACTIVE
                    contract.activated_at = moment
                    contract.effective_at = moment
                    staged.append(
                        self._events.stage(
                            event_type="contract_superseded",
                            stream_id=STREAM_ID,
                            target_id=contract.supersedes_id,
                            payload={
                                "companyId": company.id,
                                "contractId": contract.id,
                                "predecessorContractId": contract.supersedes_id,
                                "employeeId": employee.id,
                                "versionNumber": contract.version_number,
                            },
                        )
                    )
                employee.active_contract_id = contract.id
                employee.status = EmployeeStatus.ACTIVE

            company.status = CompanyStatus.ACTIVE
            company.revision += 1
            self._session.flush()

            newly_activated = {contract.id for contract in selected.values()}
            for employee in employees:
                contract = effective[employee.id]
                if contract.id not in newly_activated:
                    continue
                staged.append(
                    self._events.stage(
                        event_type="contract_activated",
                        stream_id=STREAM_ID,
                        target_id=contract.id,
                        payload={
                            "companyId": company.id,
                            "contractId": contract.id,
                            "employeeId": employee.id,
                            "versionNumber": contract.version_number,
                            "contentHash": contract.content_hash,
                        },
                    )
                )
            staged.append(
                self._events.stage(
                    event_type="company_resumed",
                    stream_id=STREAM_ID,
                    target_id=company.id,
                    payload={
                        "companyId": company.id,
                        "revision": company.revision,
                        "employeeIds": sorted(employee.id for employee in employees),
                        "activatedContractIds": sorted(selected),
                        "supersededContractIds": sorted(superseded_ids),
                    },
                )
            )

            self._events.commit_and_publish(staged)
        except IntegrityError as error:
            self._session.rollback()
            raise ConflictError(
                f"Another company is already active, or an employee already has an active "
                f"contract; '{company.id}' was not resumed",
                field="status",
            ) from error

        self._session.refresh(company)
        logger.info(
            "resumed company %s (%d successor(s) activated)",
            company.id,
            len(selected),
        )
        return ActivationOut(
            company_id=company.id,
            status=company.status.value,
            revision=company.revision,
            employee_count=len(employees),
            contract_ids=sorted(contract.id for contract in effective.values()),
            activated_at=moment,
            superseded_contract_ids=sorted(superseded_ids),
        )

    # -- validation --------------------------------------------------------

    def _validate_for_activation(
        self, company: Company
    ) -> tuple[list[CompanyEmployee], dict[str, Contract], ContractValidationContext]:
        """Everything activation depends on, checked before anything is written."""
        employees = self._workforce.list_employees(company.id)
        if not employees:
            raise ConfigurationError(
                f"Company '{company.id}' has no configured workforce", field="employees"
            )
        self._validate_company_state(company)

        # A configured employee must never have leaked into the demo workforce.
        leaked = sorted(
            employee.id for employee in employees if employee.id in DEMO_AGENT_IDS
        )
        if leaked:
            raise ConfigurationError(
                f"Configured employees must not use demo agent ids: {', '.join(leaked)}",
                field="employees",
            )
        demo_ids = {row.id for row in self._session.query(Agent).all()}
        collisions = sorted({employee.id for employee in employees} & demo_ids)
        if collisions:
            raise ConfigurationError(
                f"Configured employees collide with the canonical agents table: "
                f"{', '.join(collisions)}",
                field="employees",
            )

        catalogue = self._contracts.catalogue()
        for employee in employees:
            if employee.role_key not in catalogue:
                raise ConfigurationError(
                    f"Employee '{employee.id}' has role '{employee.role_key}', which is not "
                    "in the role catalogue",
                    field="employees",
                )

        drafts = self._contracts.list_for_company(company.id)
        by_employee: dict[str, list[Contract]] = {}
        for contract in drafts:
            by_employee.setdefault(contract.employee_id, []).append(contract)

        chosen: dict[str, Contract] = {}
        for employee in employees:
            candidates = [
                contract
                for contract in by_employee.get(employee.id, [])
                if contract.status is ContractStatus.DRAFT
            ]
            if not candidates:
                raise ConfigurationError(
                    f"Employee '{employee.id}' has no draft contract ready for activation",
                    field="contracts",
                )
            if len(candidates) > 1:
                raise ConfigurationError(
                    f"Employee '{employee.id}' has {len(candidates)} draft contracts; exactly "
                    "one must be ready for activation",
                    field="contracts",
                )
            chosen[employee.id] = candidates[0]

        already_active = [
            employee.id
            for employee in employees
            if any(
                contract.status is ContractStatus.ACTIVE
                for contract in by_employee.get(employee.id, [])
            )
        ]
        if already_active:
            raise ConflictError(
                f"Employees already have an activated contract: {', '.join(already_active)}",
                field="contracts",
            )

        account = self._companies.get_budget_account(company.id)
        context = ContractValidationContext(
            catalogue=catalogue,
            employee_ids={employee.id for employee in employees},
            reporting_lines={employee.id: employee.reports_to_id for employee in employees},
            monthly_ceiling=account.monthly_limit if account else None,
            allocated_totals={
                employee.id: chosen[employee.id].budget_per_month for employee in employees
            },
        )
        for contract in chosen.values():
            self._verify_hash(contract)
            validate_contract(contract, context)
        return employees, chosen, context

    def _validate_company_state(self, company: Company) -> None:
        """Company-level preconditions, re-checked on every lifecycle transition."""
        if not company.name.strip():
            raise ConfigurationError(
                f"Company '{company.id}' has no name", field="name"
            )
        if company.target_metric and company.target_value is None:
            raise ConfigurationError(
                f"Company '{company.id}' declares a target metric without a target value",
                field="targetMetric",
            )
        if company.target_value is not None and not company.target_metric:
            raise ConfigurationError(
                f"Company '{company.id}' declares a target value without a target metric",
                field="targetValue",
            )
        account = self._companies.get_budget_account(company.id)
        if account is None:
            raise ConfigurationError(
                f"Company '{company.id}' has no budget account", field="budgetAccount"
            )
        if account.currency != company.currency:
            raise ConfigurationError(
                f"Company '{company.id}' is configured in {company.currency} but its budget "
                f"account is in {account.currency}",
                field="currency",
            )
        if account.monthly_limit < 0:
            raise ConfigurationError(
                f"Company '{company.id}' has a negative monthly limit",
                field="monthlyBudget",
            )

    def _verify_hash(self, contract: Contract) -> None:
        """Refuse a contract whose terms no longer match its recorded hash."""
        expected = compute_content_hash(contract)
        if contract.content_hash != expected:
            raise ConfigurationError(
                f"Contract '{contract.id}' failed its integrity check: its stored hash does "
                "not match its terms. Regenerate or edit the contract before activating.",
                field="contentHash",
            )

    def _resolve_successors(
        self, company: Company, employees: list[CompanyEmployee], payload: ResumeRequest
    ) -> dict[str, Contract]:
        """Validate the requested successor versions and tie them to their employees."""
        requested = list(payload.activate_contract_ids or [])
        if not requested:
            return {}

        company_ids = {contract.id for contract in self._contracts.list_for_company(company.id)}
        unknown = sorted(set(requested) - company_ids)
        if unknown:
            raise NotFoundError(
                f"Contracts not found for company '{company.id}': {', '.join(unknown)}",
                field="activateContractIds",
            )

        selected: dict[str, Contract] = {}
        for contract_id in requested:
            contract = self._contracts.get(contract_id)
            if contract.status is not ContractStatus.DRAFT:
                raise ConflictError(
                    f"Contract '{contract_id}' is {contract.status.value}; only a draft "
                    "successor can be activated on resume",
                    field="activateContractIds",
                )
            if contract.supersedes_id is None:
                raise ConfigurationError(
                    f"Contract '{contract_id}' is not a successor version and cannot be "
                    "activated on resume",
                    field="activateContractIds",
                )
            predecessor = self._session.get(Contract, contract.supersedes_id)
            if predecessor is None or predecessor.employee_id != contract.employee_id:
                raise ConfigurationError(
                    f"Contract '{contract_id}' does not supersede a contract of the same "
                    "employee",
                    field="activateContractIds",
                )
            if predecessor.company_id != company.id:
                raise ConfigurationError(
                    f"Contract '{contract_id}' links to a contract from another company",
                    field="activateContractIds",
                )
            if contract.employee_id in selected:
                raise ConfigurationError(
                    f"More than one successor supplied for employee '{contract.employee_id}'",
                    field="activateContractIds",
                )
            selected[contract.employee_id] = contract
        return selected

    def _effective_contracts(
        self,
        company_id: str,
        employees: list[CompanyEmployee],
        selected: dict[str, Contract],
    ) -> dict[str, Contract]:
        """Which contract governs each employee after the resume."""
        by_employee: dict[str, Contract] = {}
        for contract in self._contracts.list_for_company(company_id):
            if contract.status is ContractStatus.ACTIVE:
                by_employee[contract.employee_id] = contract

        effective: dict[str, Contract] = {}
        for employee in employees:
            chosen = selected.get(employee.id) or by_employee.get(employee.id)
            if chosen is None:
                raise ConfigurationError(
                    f"Employee '{employee.id}' has no active contract to resume on",
                    field="contracts",
                )
            effective[employee.id] = chosen
        return effective


def get_lifecycle_service(session: Session) -> CompanyLifecycleService:
    return CompanyLifecycleService(session)


__all__ = ["CompanyLifecycleService", "get_lifecycle_service"]