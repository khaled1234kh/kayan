"""Reporting-line validation.

A pure, reusable validator over the **complete desired workforce**, so an employee
may report to another employee that appears later in the same request. Request
ordering is therefore irrelevant, which is what makes whole-workforce replacement
safe to express as a single PUT.

Rejected: self-reference, a reporting target that is not in the desired workforce,
a reporting target owned by another company, and cycles of any length. An employee
with no reporting manager is allowed — a flat structure is a legitimate choice.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.company.errors import RelationshipError

#: Upper bound on how long a reporting chain may be, so a pathological request
#: cannot turn validation into an unbounded walk. Real hierarchies are far shorter;
#: a company above this size or depth is configured in stages.
MAX_REPORTING_DEPTH = 64


@dataclass(frozen=True)
class ReportingLine:
    """One employee's reporting relationship, addressed by id (never a name)."""

    employee_id: str
    reports_to_id: str | None = None
    #: Company that owns this employee, used to catch cross-company references.
    company_id: str | None = None


def validate_reporting_lines(
    lines: Sequence[ReportingLine],
    *,
    foreign_employee_companies: Mapping[str, str] | None = None,
) -> None:
    """Validate a complete desired reporting hierarchy.

    Raises :class:`RelationshipError` on the first problem found, naming the
    employee and the relationship that is wrong.

    ``foreign_employee_companies`` maps ids that exist but belong to *another*
    company to their owner. It is what distinguishes "you referenced an employee
    that does not exist" from "you referenced an employee you do not own" — a
    distinction worth reporting precisely rather than collapsing both into a
    generic failure.
    """
    seen: dict[str, ReportingLine] = {}
    for line in lines:
        if line.employee_id in seen:
            raise RelationshipError(
                f"Employee '{line.employee_id}' appears more than once in the workforce",
                field="employees",
            )
        seen[line.employee_id] = line

    for line in lines:
        manager_id = line.reports_to_id
        if manager_id is None:
            continue  # A flat structure is allowed.

        if manager_id == line.employee_id:
            raise RelationshipError(
                f"Employee '{line.employee_id}' cannot report to itself",
                field=f"employees[{line.employee_id}].reportsToId",
            )

        if manager_id in seen:
            owner = seen[manager_id].company_id
            if owner is not None and line.company_id is not None and owner != line.company_id:
                raise RelationshipError(
                    f"Employee '{line.employee_id}' cannot report to '{manager_id}': "
                    "that employee belongs to another company",
                    field=f"employees[{line.employee_id}].reportsToId",
                )
            continue

        foreign_owner = (foreign_employee_companies or {}).get(manager_id)
        if foreign_owner is not None:
            raise RelationshipError(
                f"Employee '{line.employee_id}' cannot report to '{manager_id}': "
                "that employee belongs to another company",
                field=f"employees[{line.employee_id}].reportsToId",
            )

        raise RelationshipError(
            f"Employee '{line.employee_id}' reports to '{manager_id}', "
            "which is not part of this workforce",
            field=f"employees[{line.employee_id}].reportsToId",
        )

    _reject_cycles(seen)


def find_cycle(seen: Mapping[str, ReportingLine]) -> list[str] | None:
    """Return one reporting cycle as a path, or ``None`` when the graph is acyclic.

    Iterative depth-first search with an explicit stack: the workforce can be
    large enough that recursion is a needless risk, and the state is small
    (white/grey/black per node).
    """
    UNVISITED, ON_PATH, RESOLVED = 0, 1, 2
    state: dict[str, int] = {employee_id: UNVISITED for employee_id in seen}

    for root in seen:
        if state[root] != UNVISITED:
            continue
        path: list[str] = []
        # Each frame is (node, manager) so stepping to the parent never re-reads.
        stack: list[tuple[str, str | None]] = [(root, seen[root].reports_to_id)]
        state[root] = ON_PATH
        path.append(root)

        while stack:
            node, manager = stack[-1]
            if manager is None or manager not in seen:
                # Reached a root of this chain; everything on the path is resolved.
                for visited in path:
                    state[visited] = RESOLVED
                break
            if state[manager] == ON_PATH:
                # Walking into the current path is a cycle; report it from there.
                start = path.index(manager)
                return path[start:] + [manager]
            if state[manager] == RESOLVED:
                for visited in path:
                    state[visited] = RESOLVED
                break

            state[manager] = ON_PATH
            path.append(manager)
            if len(path) > MAX_REPORTING_DEPTH:
                raise RelationshipError(
                    f"Reporting chain for '{root}' exceeds {MAX_REPORTING_DEPTH} levels",
                    field="employees",
                )
            stack.append((manager, seen[manager].reports_to_id))

    return None


def _reject_cycles(seen: Mapping[str, ReportingLine]) -> None:
    cycle = find_cycle(seen)
    if cycle is not None:
        path = " -> ".join(cycle)
        raise RelationshipError(
            f"Reporting lines form a cycle: {path}",
            field="employees",
            details={"cycle": cycle},
        )