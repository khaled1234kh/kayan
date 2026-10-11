"""Draft workforce replacement.

``PUT /api/companies/{id}/workforce`` states the *complete desired workforce*. It
is a replacement, not a merge: an employee absent from the request is removed.

The safety properties this module is built around:

* **Atomic.** Every validation runs before any write is committed, and the writes
  plus the ``workforce_configured`` event share one transaction. A rejected request
  leaves the previous workforce exactly as it was — never partially replaced.
* **Scoped to one company.** Supplied ids must already belong to this company. A
  request can therefore never update or delete another company's employee.
* **Reporting lines are resolved against the desired workforce.** Employees may
  reference each other regardless of their order in the request, and self-reporting,
  missing targets, cross-company targets and cycles are all rejected before
  anything is written.
* **Configuration only.** Employees are created in ``draft`` status and are never
  inserted into the canonical ``agents`` table; the ``emp_`` id space keeps them
  from colliding with the demo workforce.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.company.errors import ConfigurationError, ConflictError
from app.company.reporting import ReportingLine, validate_reporting_lines
from app.company.templates import CUSTOM, template_by_key
from app.models import (
    Company,
    CompanyEmployee,
    CompanyStatus,
    EmployeeStatus,
    RoleTemplate,
    new_employee_id_for_new_seat,
)
from app.schemas.company import EmployeeIn, EmployeeOut, WorkforceOut, WorkforceReplace
from app.services.companies import STREAM_ID, CompanyService
from app.services.events import EventService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Seat:
    """A validated incoming employee, before it is written."""

    employee_id: str
    display_name: str
    kind: str
    role_key: str
    custom_role: str | None
    objective: str | None
    responsibilities: list[str]
    reports_to_id: str | None
    #: False for a seat the client invented (no id supplied), True when editing.
    existing: bool


class WorkforceService:
    def __init__(self, session: Session, events: EventService | None = None) -> None:
        self._session = session
        self._events = events or EventService(session)
        self._companies = CompanyService(session, self._events)

    # -- reads -------------------------------------------------------------

    def list_employees(self, company_id: str) -> list[CompanyEmployee]:
        """A company's employees, ordered deterministically by id."""
        self._companies.get_company(company_id)
        stmt = (
            select(CompanyEmployee)
            .where(CompanyEmployee.company_id == company_id)
            .order_by(CompanyEmployee.created_at, CompanyEmployee.id)
        )
        return list(self._session.execute(stmt).scalars())

    def get_workforce(self, company_id: str) -> WorkforceOut:
        company = self._companies.get_company(company_id)
        employees = self.list_employees(company_id)
        return WorkforceOut(
            company_id=company_id,
            revision=company.revision,
            employee_count=len(employees),
            employees=[EmployeeOut.model_validate(row) for row in employees],
        )

    # -- replacement -------------------------------------------------------

    def replace_workforce(self, company_id: str, payload: WorkforceReplace) -> WorkforceOut:
        company = self._companies.get_company(company_id)
        if company.status is not CompanyStatus.DRAFT:
            # Contract-aware workforce changes come with activation; until then a
            # non-draft company's roster is not editable through this endpoint.
            raise ConflictError(
                f"Company '{company_id}' is {company.status.value}; its workforce cannot be "
                "replaced. Contract-aware workforce changes are a later stage.",
                field="status",
            )

        current = self.list_employees(company_id)
        seats = self._resolve_seats(company, payload.employees, current)
        validate_reporting_lines(
            [
                ReportingLine(
                    employee_id=seat.employee_id,
                    reports_to_id=seat.reports_to_id,
                    company_id=company_id,
                )
                for seat in seats
            ],
            foreign_employee_companies=self._foreign_employee_companies(company_id, seats),
        )

        previous_ids = {row.id for row in current}
        # Reporting lines are applied after every seat exists, so a seat may report
        # to another seat that is created in this same request.
        self._session.flush()
        for seat in seats:
            seat_row = self._session.get(CompanyEmployee, seat.employee_id)
            if seat_row is None:
                seat_row = CompanyEmployee(
                    id=seat.employee_id,
                    company_id=company_id,
                    status=EmployeeStatus.DRAFT,
                    reports_to_id=None,
                )
                self._session.add(seat_row)
            seat_row.display_name = seat.display_name
            seat_row.kind = seat.kind
            seat_row.role_key = seat.role_key
            seat_row.custom_role = seat.custom_role
            seat_row.objective = seat.objective
            seat_row.responsibilities = list(seat.responsibilities)
            seat_row.active_contract_id = None
        self._session.flush()

        # Second pass: reporting relationships, now that every seat has an id.
        for seat in seats:
            self._session.get(CompanyEmployee, seat.employee_id).reports_to_id = seat.reports_to_id

        removed = sorted(previous_ids - {seat.employee_id for seat in seats})
        for employee_id in removed:
            row = self._session.get(CompanyEmployee, employee_id)
            if row is not None and row.company_id == company_id:
                self._session.delete(row)

        company.revision += 1
        self._session.flush()

        added = sorted({seat.employee_id for seat in seats} - previous_ids)
        updated = sorted({seat.employee_id for seat in seats} & previous_ids)
        event = self._events.stage(
            event_type="workforce_configured",
            stream_id=STREAM_ID,
            target_id=company_id,
            payload={
                "companyId": company_id,
                "revision": company.revision,
                "employeeCount": len(seats),
                "addedEmployeeIds": added,
                "updatedEmployeeIds": updated,
                "removedEmployeeIds": removed,
            },
        )
        self._events.commit_and_publish([event])
        self._session.refresh(company)
        logger.info(
            "replaced workforce for %s: %d seats (+%d ~%d -%d)",
            company_id,
            len(seats),
            len(added),
            len(updated),
            len(removed),
        )
        return WorkforceOut(
            company_id=company_id,
            revision=company.revision,
            employee_count=len(seats),
            employees=[EmployeeOut.model_validate(row) for row in self.list_employees(company_id)],
        )

    # -- validation --------------------------------------------------------

    def _resolve_seats(
        self,
        company: Company,
        incoming: list[EmployeeIn],
        current: list[CompanyEmployee],
    ) -> list[_Seat]:
        """Validate every incoming employee and assign ids.

        Raises :class:`ConfigurationError` on the first problem, so a request with
        several mistakes reports the same one it would have reported with just that
        mistake — the client fixes issues one round trip at a time.
        """
        company_id = company.id
        if not incoming:
            raise ConfigurationError(
                "A workforce must contain at least one employee", field="employees"
            )

        current_by_id = {row.id: row for row in current}
        requested_ids = [entry.id for entry in incoming if entry.id is not None]
        if len(requested_ids) != len(set(requested_ids)):
            duplicates = sorted({value for value in requested_ids if requested_ids.count(value) > 1})
            raise ConfigurationError(
                f"Employee ids appear more than once in the request: {', '.join(duplicates)}",
                field="employees",
            )

        seats: list[_Seat] = []
        for entry in incoming:
            if entry.company_id is not None and entry.company_id != company_id:
                raise ConfigurationError(
                    f"Employee '{entry.display_name}' claims companyId '{entry.company_id}' "
                    f"but was submitted for '{company_id}'",
                    field="employees",
                )
            employee_id = entry.id or new_employee_id_for_new_seat()
            if entry.id is not None:
                existing = current_by_id.get(entry.id)
                if existing is None:
                    owner = self._owner_of_employee(entry.id)
                    if owner is not None:
                        raise ConfigurationError(
                            f"Employee '{entry.id}' belongs to another company and cannot be "
                            "edited through this request",
                            field="employees",
                            details={"employeeId": entry.id, "belongsTo": owner},
                        )
                    raise ConfigurationError(
                        f"Employee '{entry.id}' does not belong to company '{company_id}'",
                        field="employees",
                        details={"employeeId": entry.id},
                    )
                if existing.company_id != company_id:  # pragma: no cover - defensive
                    raise ConfigurationError(
                        f"Employee '{entry.id}' does not belong to company '{company_id}'",
                        field="employees",
                    )

            role_key = self._resolve_role(company, entry)
            seats.append(
                _Seat(
                    employee_id=employee_id,
                    display_name=entry.display_name,
                    kind=entry.kind,
                    role_key=role_key,
                    custom_role=entry.custom_role,
                    objective=entry.objective,
                    responsibilities=list(entry.responsibilities),
                    reports_to_id=entry.reports_to_id,
                    existing=entry.id is not None,
                )
            )
        return seats

    def _resolve_role(self, company: Company, entry: EmployeeIn) -> str:
        """Validate one seat's role against the versioned catalogue and template.

        A catalogue role must exist and be offered by the company's template. The
        ``custom`` role is always allowed and must carry its own description, which
        is what makes a bespoke seat possible without a template change.
        """
        role_key = entry.role_key

        if role_key == CUSTOM:
            if not entry.custom_role:
                raise ConfigurationError(
                    f"Employee '{entry.display_name}' uses the custom role and must supply "
                    "customRole",
                    field="employees",
                )
            return CUSTOM

        template = self._active_role(role_key)
        if template is None:
            raise ConfigurationError(
                f"roleKey '{role_key}' is not a known role; use '{CUSTOM}' with a customRole "
                "for a bespoke seat",
                field="employees",
            )

        company_template = template_by_key(company.template_key)
        offered = (company_template or {}).get("role_keys", [])
        if offered and role_key not in offered:
            raise ConfigurationError(
                f"Role '{role_key}' is not available for template '{company.template_key}'; "
                f"offered roles are {', '.join(offered)}",
                field="employees",
            )
        return role_key

    def _active_role(self, role_key: str) -> RoleTemplate | None:
        """The current version of a role, read from the seeded catalogue.

        Ordered by ``config_version`` descending so a redefined role resolves to its
        newest definition; the database is the source of truth, not a second list
        in this service.
        """
        stmt = (
            select(RoleTemplate)
            .where(RoleTemplate.key == role_key)
            .order_by(RoleTemplate.config_version.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def _owner_of_employee(self, employee_id: str) -> str | None:
        """The company owning an id, used to explain a cross-company rejection."""
        row = self._session.get(CompanyEmployee, employee_id)
        return None if row is None else row.company_id

    def _foreign_employee_companies(
        self, company_id: str, seats: list[_Seat]
    ) -> dict[str, str]:
        """Map referenced manager ids to their real owning companies.

        An id that exists but belongs to another company is reported as a
        cross-company reference rather than as merely "unknown", because the two
        mean different things to whoever is fixing the request. Ids that do not
        exist at all are left out, so the validator reports them as missing.
        """
        referenced = {seat.reports_to_id for seat in seats if seat.reports_to_id}
        if not referenced:
            return {}
        stmt = select(CompanyEmployee.id, CompanyEmployee.company_id).where(
            CompanyEmployee.id.in_(referenced)
        )
        return {
            employee_id: owner
            for employee_id, owner in self._session.execute(stmt).all()
            if owner != company_id
        }


def get_workforce_service(session: Session) -> WorkforceService:
    return WorkforceService(session)


__all__ = ["WorkforceService", "get_workforce_service"]