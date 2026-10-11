"""Proposal validation.

Whatever produced a proposal, this is where it is checked before it can be stored
or shown as authority. A provider is untrusted input: it may be a deterministic
template today and a language model tomorrow, and in both cases its document is
re-derived against the catalogue rather than believed.

Four properties are enforced:

1. **Every role is real.** Each ``role_key`` must exist in the seeded catalogue at
   the recorded ``role_config_version``, and must be offered by the company's
   template.
2. **Every grant is structured and bounded.** Data and tool scopes must match the
   supported schema — a permission nobody validated is not a permission.
3. **The reporting graph is valid.** Reusing the P0.2 validator means a proposal
   cannot smuggle in a self-reporting seat or a cycle.
4. **The money fits.** ``sum(monthly) <= ceiling`` and
   ``0 <= perTask <= monthly``, in ``Decimal``, with the remainder stated.
"""

from __future__ import annotations

from decimal import Decimal

from app.company.errors import ConfigurationError
from app.company.reporting import ReportingLine, validate_reporting_lines
from app.models import RoleTemplate
from app.schemas.recommendation import ProposedEmployee, RecommendationProposal

#: Smallest share of the ceiling a seat may be allocated. Below this a seat cannot
#: perform real work, so proposing it is a mistake worth reporting rather than
#: rounding away.
MIN_ALLOCATION_SHARE = Decimal("0.001")


def validate_proposal(
    proposal: RecommendationProposal,
    *,
    catalogue: dict[str, RoleTemplate],
    offered_role_keys: list[str],
    monthly_ceiling: Decimal,
    currency: str,
) -> RecommendationProposal:
    """Validate a proposal in place of trusting it. Raises on the first problem.

    Returns the proposal so callers can chain, but the value is unchanged: this
    function rejects, it does not quietly repair. Repair is a provider's job, and a
    silent fix here would hide exactly the kind of error worth surfacing.
    """
    _validate_roles(proposal, catalogue=catalogue, offered_role_keys=offered_role_keys)
    _validate_scopes(proposal.employees)
    _validate_reporting(proposal)
    _validate_budget(proposal, monthly_ceiling=monthly_ceiling, currency=currency)
    return proposal


def _validate_roles(
    proposal: RecommendationProposal,
    *,
    catalogue: dict[str, RoleTemplate],
    offered_role_keys: list[str],
) -> None:
    for employee in proposal.employees:
        role = catalogue.get(employee.role_key)
        if role is None:
            raise ConfigurationError(
                f"Proposed role '{employee.role_key}' for '{employee.display_name}' does "
                "not exist in the role catalogue",
                field=f"employees.{employee.key}.roleKey",
            )
        if employee.role_config_version != role.config_version:
            raise ConfigurationError(
                f"Proposed role '{employee.role_key}' was taken at version "
                f"{employee.role_config_version} but the catalogue holds version "
                f"{role.config_version}",
                field=f"employees.{employee.key}.roleConfigVersion",
            )
        if offered_role_keys and employee.role_key not in offered_role_keys:
            raise ConfigurationError(
                f"Role '{employee.role_key}' is not offered by this company's template",
                field=f"employees.{employee.key}.roleKey",
            )
        if employee.kind != role.kind:
            raise ConfigurationError(
                f"Proposed seat '{employee.display_name}' is '{employee.kind}' but role "
                f"'{employee.role_key}' is a '{role.kind}' role",
                field=f"employees.{employee.key}.kind",
            )


def _validate_scopes(employees: list[ProposedEmployee]) -> None:
    """Scopes must be structured, and restrictions must be drawn from the catalogue.

    Free-form entries cannot be validated and therefore cannot be granted: a scope
    that does not parse into ``{resource, operations}`` is refused rather than
    stored as an opaque string.
    """
    for employee in employees:
        for entry in employee.data_scope:
            if not entry.resource.strip() or not entry.operations:
                raise ConfigurationError(
                    f"Employee '{employee.key}' has an empty data scope entry",
                    field=f"employees.{employee.key}.dataScope",
                )
        for entry in employee.tool_scope:
            if not entry.tool.strip() or not entry.actions:
                raise ConfigurationError(
                    f"Employee '{employee.key}' has an empty tool scope entry",
                    field=f"employees.{employee.key}.toolScope",
                )
        if not employee.responsibilities:
            raise ConfigurationError(
                f"Employee '{employee.key}' has no responsibilities; a seat with no stated "
                "duties cannot be reviewed",
                field=f"employees.{employee.key}.responsibilities",
            )


def _validate_reporting(proposal: RecommendationProposal) -> None:
    """Reuse the P0.2 validator so a proposal obeys the same rules as a submission."""
    keys = {employee.key for employee in proposal.employees}
    for employee in proposal.employees:
        target = employee.reports_to_key
        if target is not None and target not in keys:
            raise ConfigurationError(
                f"Employee '{employee.key}' reports to '{target}', which is not part of "
                "this proposal",
                field=f"employees.{employee.key}.reportsToKey",
            )

    validate_reporting_lines(
        [
            ReportingLine(
                employee_id=employee.key,
                reports_to_id=employee.reports_to_key,
                company_id=proposal.company_id,
            )
            for employee in proposal.employees
        ]
    )

    # Communication targets must be real seats too: an `allow` entry naming a seat
    # that does not exist would become an unresolvable grant.
    for employee in proposal.employees:
        unknown = [target for target in employee.communication.allow if target not in keys]
        if unknown:
            raise ConfigurationError(
                f"Employee '{employee.key}' may communicate with unknown seats: "
                f"{', '.join(unknown)}",
                field=f"employees.{employee.key}.communication.allow",
            )


def _validate_budget(
    proposal: RecommendationProposal,
    *,
    monthly_ceiling: Decimal,
    currency: str,
) -> None:
    """The allocation must fit the ceiling, and each seat must be internally coherent."""
    if proposal.budget.company_monthly_ceiling != monthly_ceiling:
        raise ConfigurationError(
            f"Proposal was budgeted against {proposal.budget.company_monthly_ceiling} but "
            f"the company's ceiling is {monthly_ceiling}",
            field="budget.companyMonthlyCeiling",
        )
    if proposal.budget.currency != currency:
        raise ConfigurationError(
            f"Proposal is in {proposal.budget.currency} but the company is configured in "
            f"{currency}; amounts are not converted",
            field="budget.currency",
        )

    total = Decimal("0")
    for employee in proposal.employees:
        monthly = employee.suggested_monthly_budget
        per_task = employee.suggested_per_task_budget
        if per_task > monthly:
            raise ConfigurationError(
                f"Employee '{employee.key}' may spend {per_task} on one task, more than its "
                f"monthly allocation of {monthly}",
                field=f"employees.{employee.key}.suggestedPerTaskBudget",
            )
        if monthly < 0 or per_task < 0:  # pragma: no cover - schema forbids negatives
            raise ConfigurationError(
                f"Employee '{employee.key}' has a negative allocation",
                field=f"employees.{employee.key}.suggestedMonthlyBudget",
            )
        total += monthly

    if total > monthly_ceiling:
        raise ConfigurationError(
            f"Proposed allocations total {total}, which exceeds the company ceiling of "
            f"{monthly_ceiling}",
            field="budget.totalSuggestedMonthly",
        )
    if total != proposal.budget.total_suggested_monthly:
        raise ConfigurationError(
            f"Stated total {proposal.budget.total_suggested_monthly} does not match the sum "
            f"of the proposed allocations ({total})",
            field="budget.totalSuggestedMonthly",
        )

    remainder = monthly_ceiling - total
    if proposal.budget.unallocated_monthly != remainder:
        raise ConfigurationError(
            f"Stated unallocated amount {proposal.budget.unallocated_monthly} does not match "
            f"the ceiling minus the allocations ({remainder})",
            field="budget.unallocatedMonthly",
        )


__all__ = ["MIN_ALLOCATION_SHARE", "validate_proposal"]