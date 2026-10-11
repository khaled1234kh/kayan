"""Deterministic workforce recommendation from the versioned catalogue.

Given the same company, the same preferences and the same catalogue version, this
returns the same proposal every time. That is the point: a recommendation the owner
cannot reproduce is not something they can review.

Design:

* **Roles come from the database**, never from a list compiled here. The provider
  reads the ``role_templates`` rows the catalogue seeded, so a revised role flows
  into the proposal without touching this file.
* **The template chooses the shape.** Each company template lists the roles it
  offers, in an order that reflects dependency: the human owner decides, the manager
  coordinates, the specialists do the work. A workforce is assembled along that
  spine and then filled to the requested size with roles that add distinct
  capability.
* **More seats is not automatically better.** The roster fills to the requested
  count, but each added seat must earn a place by covering a task category the
  roster does not already cover. If no distinct role remains, the proposal stops and
  says so in a warning rather than padding with duplicates.
* **Money is allocated, never invented.** Allocations are shares of the company's
  saved ceiling, weighted by role, with the remainder left unallocated and named.
"""

from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal

from app.company.providers import RecommendationContext
from app.company.templates import template_by_key
from app.models import RoleTemplate
from app.schemas.recommendation import (
    BudgetSummary,
    CommunicationPermissions,
    DataScopeEntry,
    ProposedEmployee,
    RecommendationProposal,
    RecommendationRequest,
    ToolScopeEntry,
)

PROVIDER_NAME = "template"

#: Relative monthly share per role, applied to the company's ceiling and then scaled
#: to the requested headcount. These are shares of the *allocated* budget, not
#: amounts: the company decides the total.
ROLE_MONTHLY_WEIGHTS: dict[str, Decimal] = {
    "ceo": Decimal("0.20"),
    "manager": Decimal("0.22"),
    "operations": Decimal("0.18"),
    "sales": Decimal("0.20"),
    "hr": Decimal("0.12"),
    "support": Decimal("0.10"),
    "employee": Decimal("0.15"),
}

#: Fallback weight for a role the catalogue defines but this provider has no weight
#: for, so an unfamiliar role still receives a defensible share.
DEFAULT_MONTHLY_WEIGHT = Decimal("0.15")

#: Largest share of a seat's monthly allocation that one task may consume. A seat
#: that could spend its whole monthly budget on a single task has no monthly ceiling
#: worth having.
MAX_PER_TASK_SHARE = Decimal("0.50")

#: Roles that are never duplicated: two managers do not coordinate twice, they
#: simply talk to each other less.
SINGLETON_ROLES = frozenset({"ceo", "manager"})

#: Role -> what it is for, phrased as the reason a business needs the seat. Used to
#: build the rationale so the explanation is specific rather than generic.
ROLE_PURPOSE: dict[str, str] = {
    "ceo": "holds the final decision and approves the outcome, so no action is "
    "finalised without an accountable human",
    "manager": "decomposes the goal, assigns work and reviews results, so the team "
    "acts in sequence rather than in parallel",
    "operations": "establishes what can actually be fulfilled from real inventory, "
    "so quotations are not promised against stock that does not exist",
    "sales": "prepares quotations from available data and handles the customer "
    "conversation, which is the direct route to revenue",
    "hr": "maintains workforce records and handles people operations, keeping "
    "employment matters out of the order flow",
    "support": "answers inbound customer questions and escalates blockers, so "
    "questions do not consume the people who close orders",
    "employee": "carries out the hands-on work a manager assigns",
}

#: Task categories a role claims. The catalogue is authoritative; this is only used
#: to explain coverage in the proposal's warnings.
COVERAGE_LABEL = "task coverage"


class TemplateProvider:
    """Builds a workforce proposal from the template and the role catalogue."""

    name = PROVIDER_NAME
    source = "template"

    def identify(self) -> tuple[str | None, str | None]:
        """A template proposal names no provider and no model, by design."""
        return None, None

    def recommend(
        self,
        request: RecommendationRequest,
        roles: list[RoleTemplate],
        context: RecommendationContext,
    ) -> RecommendationProposal:
        preferences = request.preferences
        warnings: list[str] = []

        catalogue = _catalogue_for(request, roles, context, warnings)
        if not catalogue:
            raise ValueError(
                f"template '{context.template_key}' offers no roles in the catalogue"
            )

        roster = self._select_roster(catalogue, preferences, context, warnings)
        catalog_version = max(role.config_version for role in catalogue)

        employees, budget = self._allocate(roster, context, catalog_version, warnings)

        return RecommendationProposal(
            company_id=context.company_id,
            source="template",
            provider_name=None,
            model_name=None,
            role_catalog_version=catalog_version,
            employees=employees,
            budget=budget,
            warnings=warnings,
        )

    # -- roster selection ---------------------------------------------------

    def _select_roster(
        self,
        catalogue: list[RoleTemplate],
        preferences,
        context: RecommendationContext,
        warnings: list[str],
    ) -> list[RoleTemplate]:
        """Choose the roles for this company, in reporting order.

        Order matters: the first entry is the seat that reports to nobody, and each
        later entry reports to the most senior seat before it.
        """
        by_key = {role.key: role for role in catalogue}
        desired = (
            preferences.desired_employee_count
            if preferences.desired_employee_count is not None
            else _default_headcount(by_key)
        )

        # The spine, in seniority order. A template without a human owner can still
        # run, but only when the caller explicitly asks for it.
        spine: list[RoleTemplate] = []
        if preferences.include_human_employee and "ceo" in by_key:
            spine.append(by_key["ceo"])
        elif not preferences.include_human_employee:
            warnings.append(
                "No human decision-maker proposed: every action still requires human "
                "approval, so nothing can be finalised without an owner."
            )
        for key in ("manager", "sales", "operations"):
            if key in by_key and key not in {role.key for role in spine}:
                spine.append(by_key[key])

        if preferences.include_hr and "hr" in by_key:
            spine.append(by_key["hr"])
        else:
            warnings.append(
                "HR role omitted by preference; workforce records will have no owner "
                "within the company."
            )

        # Fill the remaining seats with roles that add capability the roster lacks,
        # rather than duplicating a seat that is already represented.
        covered = {category for role in spine for category in (role.task_categories or [])}
        fillers = [
            role
            for role in catalogue
            if role.key not in {r.key for r in spine}
            and not (role.key in SINGLETON_ROLES)
            and not set(role.task_categories or []).issubset(covered)
        ]
        fillers.sort(key=lambda role: role.key)

        roster = list(spine)
        for role in fillers:
            if len(roster) >= desired:
                break
            roster.append(role)
            covered.update(role.task_categories or [])

        if len(roster) > desired:
            # Trim the least essential: specialists first, never the decision-makers.
            trimmed = _trim_to(roster, desired)
            dropped = sorted({role.key for role in roster} - {role.key for role in trimmed})
            if dropped:
                warnings.append(
                    f"Reduced to {desired} seats to match the request; trimmed "
                    f"{', '.join(dropped)}. Raise desiredEmployeeCount to keep them."
                )
            roster = trimmed

        if len(roster) < desired:
            warnings.append(
                f"Proposed {len(roster)} of {desired} requested seats: the template "
                "offers no further roles that add capability the roster lacks. More "
                "seats would repeat existing work rather than extend coverage."
            )
        return roster

    # -- money --------------------------------------------------------------

    def _allocate(
        self,
        roster: list[RoleTemplate],
        context: RecommendationContext,
        catalog_version: int,
        warnings: list[str],
    ) -> tuple[list[ProposedEmployee], BudgetSummary]:
        """Split the ceiling across the roster and build the proposal entries."""
        ceiling = Decimal(context.monthly_ceiling)
        currency = context.currency

        weights = [ROLE_MONTHLY_WEIGHTS.get(role.key, DEFAULT_MONTHLY_WEIGHT) for role in roster]
        total_weight = sum(weights, Decimal("0"))
        if total_weight == 0:  # pragma: no cover - defensive; weights are positive
            raise ValueError("role weights must not sum to zero")

        # Largest-remainder apportionment: every seat gets a share of the ceiling
        # that sums to at most the ceiling exactly, with no rounding drift and no
        # seat absorbing an arbitrary remainder.
        #
        # Shares are truncated (never rounded) so the parts can never exceed the
        # whole; the leftover is then handed out one unit at a time.
        unit = Decimal("0.000001")
        raw = [ceiling * weight / total_weight for weight in weights]
        floored = [amount.quantize(unit, rounding=ROUND_FLOOR) for amount in raw]
        remainder = ceiling - sum(floored, Decimal("0"))

        # Hand the rounding remainder to the largest fractional parts first, so the
        # tie-break is deterministic rather than dependent on iteration luck.
        order = sorted(
            range(len(roster)),
            key=lambda index: (-(raw[index] - floored[index]), index),
        )
        allocations = list(floored)
        position = 0
        while remainder >= unit and order:
            index = order[position % len(order)]
            allocations[index] += unit
            remainder -= unit
            position += 1

        total = sum(allocations, Decimal("0"))
        if total > ceiling:  # pragma: no cover - truncation makes this unreachable
            raise ValueError("allocation exceeded the company ceiling")

        employees: list[ProposedEmployee] = []
        # Specialists report to the manager rather than all to the top seat: a chain
        # of one manager keeps supervision unambiguous as the roster grows. Without a
        # manager in the roster, the most senior seat supervises.
        manager_index = next(
            (index for index, role in enumerate(roster) if role.key == "manager"), None
        )
        supervisor_key = (
            f"proposal-employee-{manager_index + 1}"
            if manager_index is not None and manager_index > 0
            else None
        )

        for index, role in enumerate(roster):
            key = f"proposal-employee-{index + 1}"
            monthly = allocations[index]
            if index == 0:
                # The most senior seat reports to nobody.
                reports_to = None
            elif supervisor_key is not None and index == manager_index:
                # The manager supervises everyone else and answers to the top seat.
                reports_to = "proposal-employee-1"
            else:
                reports_to = supervisor_key or "proposal-employee-1"

            employees.append(
                ProposedEmployee(
                    key=key,
                    display_name=role.label,
                    kind=role.kind,
                    role_key=role.key,
                    role_config_version=role.config_version,
                    objective=_objective_for(role, context),
                    responsibilities=list(role.responsibilities or []),
                    data_scope=[
                        DataScopeEntry.model_validate(entry)
                        for entry in (role.default_data_scope or [])
                    ],
                    tool_scope=[
                        ToolScopeEntry.model_validate(entry)
                        for entry in (role.default_tool_scope or [])
                    ],
                    restrictions=list(role.default_restrictions or []),
                    communication=_communication_for(index, reports_to),
                    reports_to_key=reports_to,
                    suggested_monthly_budget=monthly,
                    suggested_per_task_budget=_per_task_ceiling(monthly),
                    rationale=_rationale_for(role, monthly, context),
                )
            )

        return employees, BudgetSummary(
            company_monthly_ceiling=ceiling,
            currency=currency,
            total_suggested_monthly=total,
            unallocated_monthly=ceiling - total,
        )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _catalogue_for(
    request: RecommendationRequest,
    roles: list[RoleTemplate],
    context: RecommendationContext,
    warnings: list[str],
) -> list[RoleTemplate]:
    """The role rows this template may use, in catalogue seniority order.

    Filtered by the template's own offer list, which is the authority: the database
    says which roles exist, the template says which of them it offers.
    """
    template = template_by_key(context.template_key)
    if template is None:
        raise ValueError(f"unknown template '{context.template_key}'")
    offered = list(template.get("role_keys") or [])

    by_key = {role.key: role for role in roles}
    catalogue = [by_key[key] for key in offered if key in by_key]

    missing = [key for key in offered if key not in by_key]
    if missing:
        warnings.append(
            f"Catalogue has no seeded definition for {', '.join(missing)}; those roles "
            "were not proposed."
        )
    return catalogue


def _default_headcount(by_key: dict[str, RoleTemplate]) -> int:
    """A sensible size when the caller expressed no preference."""
    return 4 if "ceo" in by_key else 3


def _trim_to(roster: list[RoleTemplate], desired: int) -> list[RoleTemplate]:
    """Drop specialists before decision-makers when a roster must shrink."""
    keep = list(roster)
    while len(keep) > desired:
        # The last entry is the least senior of the spine; remove the latest
        # specialist that is not a decision-maker.
        for index in range(len(keep) - 1, -1, -1):
            if keep[index].key not in {"ceo", "manager"}:
                keep.pop(index)
                break
        else:  # pragma: no cover - only decision-makers remain
            keep.pop()
    return keep


def _per_task_ceiling(monthly: Decimal) -> Decimal:
    """Largest single task a seat may consume, as a share of its monthly budget."""
    return (monthly * MAX_PER_TASK_SHARE).quantize(Decimal("0.000001"))


def _objective_for(role: RoleTemplate, context: RecommendationContext) -> str:
    """A one-line objective tied to the company's own stated goal."""
    purpose = ROLE_PURPOSE.get(role.key)
    if purpose is None:
        return f"Contribute {role.label.lower()} capability to the company."
    return f"{purpose.capitalize()}."


def _communication_for(index: int, reports_to: str | None) -> CommunicationPermissions:
    """Targeted communication by default; broadcast only at the top.

    A seat may talk to the seat it reports to and no further, and a proposal should
    not grant an open channel to the whole company unless the seat genuinely needs
    one — so broadcasting is reserved for the most senior seat.
    """
    if index == 0:
        return CommunicationPermissions(allow=[], broadcast=True, max_rounds=4)
    return CommunicationPermissions(
        allow=[reports_to] if reports_to else [], broadcast=False, max_rounds=3
    )


def _rationale_for(role: RoleTemplate, monthly: Decimal, context: RecommendationContext) -> str:
    """Why this role, and why this share of the budget."""
    purpose = ROLE_PURPOSE.get(role.key, f"provides {role.label.lower()} capability")
    restrictions = role.default_restrictions or []
    constraint = (
        f" Scoped to {', '.join(restrictions)}."
        if restrictions
        else " No additional restrictions apply."
    )
    return (
        f"{role.label}: {purpose}. Supports {context.describe_target()}. "
        f"Allocation {monthly} {context.currency} per month.{constraint}"
    )