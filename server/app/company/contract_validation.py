"""Validation of contract terms.

A contract describes what an employee may do, so it is validated against the same
rules every time it is written — generated, edited, copied into a successor, or
checked again at activation. Validation always runs over the **complete resulting
contract**, never only the fields a request happened to mention: a PATCH that
corrects one field must still be refused if some other field is invalid.

The validator is pure. Everything it needs is passed in a
:class:`ContractValidationContext`, so the rules hold for every caller and can be
tested without a database or a request.

Reporting relationships are checked as a graph over the company's whole workforce,
which is how P0.2 checks a workforce submission, so a contract cannot express a
hierarchy the workforce API would reject.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.company.errors import ConfigurationError
from app.company.permissions import (
    SUPPORTED_OPERATIONS,
    SUPPORTED_RESTRICTIONS,
    SUPPORTED_TASK_CATEGORIES,
    unknown_in_scope,
)
from app.company.reporting import ReportingLine, validate_reporting_lines
from app.models import RoleTemplate

#: A contract naming a tool the product does not know is refused outright.
MAX_COMMUNICATION_ROUNDS = 20
DEFAULT_COMMUNICATION_ROUNDS = 3


@dataclass
class ContractValidationContext:
    """Everything a validator needs to judge one contract."""

    #: Current catalogue definitions by role key.
    catalogue: dict[str, RoleTemplate]
    #: Every employee of the company.
    employee_ids: set[str]
    #: Reporting line per employee, from the draft workforce.
    reporting_lines: dict[str, str | None] = field(default_factory=dict)
    #: The company's monthly ceiling, when the caller is validating a whole set.
    monthly_ceiling: Decimal | None = None
    #: Monthly allocation per employee across the whole set.
    allocated_totals: dict[str, Decimal] | None = None


def validate_contract(contract, context: ContractValidationContext) -> None:
    """Validate a complete contract. Raises on the first problem, naming the field."""
    _validate_identity(contract, context)
    _validate_role(contract, context)
    _validate_scopes(contract)
    _validate_reporting(contract, context)
    _validate_communication(contract, context)
    _validate_approval_rules(contract, context)
    _validate_budgets(contract, context)


def _validate_identity(contract, context: ContractValidationContext) -> None:
    if contract.employee_id not in context.employee_ids:
        raise ConfigurationError(
            f"Employee '{contract.employee_id}' does not belong to company "
            f"'{contract.company_id}'",
            field="employeeId",
        )


def _validate_role(contract, context: ContractValidationContext) -> None:
    role = context.catalogue.get(contract.role)
    if role is None:
        raise ConfigurationError(
            f"Contract role '{contract.role}' does not exist in the role catalogue",
            field="role",
        )
    if contract.role_config_version != role.config_version:
        raise ConfigurationError(
            f"Contract records role version {contract.role_config_version} but the "
            f"catalogue holds {role.key} at version {role.config_version}",
            field="roleConfigVersion",
        )


def _validate_scopes(contract) -> None:
    if not contract.responsibilities:
        raise ConfigurationError(
            "A contract must state at least one responsibility", field="responsibilities"
        )

    for entry in contract.data_scope:
        if not isinstance(entry, dict) or not entry.get("resource"):
            raise ConfigurationError(
                "Data scope entries must be {resource, operations} objects",
                field="dataScope",
            )
        operations = entry.get("operations") or []
        if not operations:
            raise ConfigurationError(
                f"Data scope for '{entry['resource']}' grants no operation",
                field="dataScope",
            )
        unsupported = sorted(set(operations) - SUPPORTED_OPERATIONS)
        if unsupported:
            raise ConfigurationError(
                f"Unsupported data operations: {', '.join(unsupported)}",
                field="dataScope",
            )
    unknown_resources = unknown_in_scope(contract.data_scope, field="resource")
    if unknown_resources:
        raise ConfigurationError(
            f"Unknown data resources: {', '.join(unknown_resources)}. A contract cannot "
            "grant access the product does not define.",
            field="dataScope",
        )

    for entry in contract.tool_scope:
        if not isinstance(entry, dict) or not entry.get("tool"):
            raise ConfigurationError(
                "Tool scope entries must be {tool, actions} objects", field="toolScope"
            )
        if not entry.get("actions"):
            raise ConfigurationError(
                f"Tool scope for '{entry['tool']}' grants no action", field="toolScope"
            )
    unknown_tools = unknown_in_scope(contract.tool_scope, field="tool")
    if unknown_tools:
        raise ConfigurationError(
            f"Unknown tools: {', '.join(unknown_tools)}. A contract cannot grant a tool "
            "the product does not define.",
            field="toolScope",
        )

    unknown_restrictions = sorted(set(contract.restrictions) - SUPPORTED_RESTRICTIONS)
    if unknown_restrictions:
        raise ConfigurationError(
            f"Unknown restrictions: {', '.join(unknown_restrictions)}", field="restrictions"
        )

    unknown_categories = sorted(set(contract.task_scope) - SUPPORTED_TASK_CATEGORIES)
    if unknown_categories:
        raise ConfigurationError(
            f"Unknown task categories: {', '.join(unknown_categories)}", field="taskScope"
        )


def _validate_reporting(contract, context: ContractValidationContext) -> None:
    """The whole workforce hierarchy, with this contract's line substituted in."""
    lines = dict(context.reporting_lines)
    lines[contract.employee_id] = contract.reports_to_employee_id
    validate_reporting_lines(
        [
            ReportingLine(
                employee_id=employee_id,
                reports_to_id=manager_id,
                company_id=contract.company_id,
            )
            for employee_id, manager_id in lines.items()
        ]
    )


def _validate_communication(contract, context: ContractValidationContext) -> None:
    policy = contract.communication_policy or {}
    allow = policy.get("allow") or []
    if not isinstance(allow, list):
        raise ConfigurationError(
            "Communication allow must be a list", field="communicationPolicy"
        )
    unknown = sorted({target for target in allow if target not in context.employee_ids})
    if unknown:
        raise ConfigurationError(
            f"Communication targets that are not employees of this company: "
            f"{', '.join(unknown)}",
            field="communicationPolicy",
        )
    rounds = policy.get("maxRounds", DEFAULT_COMMUNICATION_ROUNDS)
    if not isinstance(rounds, int) or isinstance(rounds, bool):
        raise ConfigurationError(
            "Communication rounds must be a whole number", field="communicationPolicy"
        )
    if not 1 <= rounds <= MAX_COMMUNICATION_ROUNDS:
        raise ConfigurationError(
            f"Communication rounds must be between 1 and {MAX_COMMUNICATION_ROUNDS}",
            field="communicationPolicy",
        )
    if "broadcast" not in policy:
        raise ConfigurationError(
            "Communication policy must state whether broadcasting is permitted",
            field="communicationPolicy",
        )


def _validate_approval_rules(contract, context: ContractValidationContext) -> None:
    for rule in contract.approval_rules or []:
        if not isinstance(rule, dict) or not rule.get("action"):
            raise ConfigurationError(
                "Approval rules must be {action, requiredApprover} objects",
                field="approvalRules",
            )
        approver = rule.get("requiredApprover")
        if approver is None:
            raise ConfigurationError(
                f"Approval rule for '{rule['action']}' names no required approver",
                field="approvalRules",
            )
        # An approver is either a seat in this company or a catalogue role that
        # exists; anything else would be an unmeetable requirement.
        if approver not in context.employee_ids and approver not in context.catalogue:
            raise ConfigurationError(
                f"Approval rule for '{rule['action']}' requires approval from "
                f"'{approver}', which is neither an employee of this company nor a "
                "catalogue role",
                field="approvalRules",
            )


def _validate_budgets(contract, context: ContractValidationContext) -> None:
    monthly = Decimal(contract.budget_per_month)
    per_task = Decimal(contract.budget_per_task)
    if monthly < 0 or per_task < 0:
        raise ConfigurationError(
            "Contract budgets must be non-negative", field="budgetPerMonth"
        )
    if per_task > monthly:
        raise ConfigurationError(
            f"Per-task ceiling {per_task} exceeds the monthly allocation {monthly}",
            field="budgetPerTask",
        )

    if context.monthly_ceiling is not None and context.allocated_totals:
        # The ceiling applies to the whole company, so it is checked against the full
        # allocation set rather than one contract in isolation.
        total = sum(context.allocated_totals.values(), Decimal("0"))
        if total > context.monthly_ceiling:
            raise ConfigurationError(
                f"Contract allocations total {total}, which exceeds the company ceiling "
                f"of {context.monthly_ceiling}",
                field="budgetPerMonth",
            )


__all__ = [
    "ContractValidationContext",
    "DEFAULT_COMMUNICATION_ROUNDS",
    "MAX_COMMUNICATION_ROUNDS",
    "validate_contract",
]