"""Reporting-line validation as a reusable unit.

Exercised directly against the validator rather than through HTTP, because it is a
service-level component: the same rules must hold for any caller that proposes a
workforce, and a unit test states them without a request in the way.
"""

from __future__ import annotations

import pytest

from app.company.errors import RelationshipError
from app.company.reporting import ReportingLine, find_cycle, validate_reporting_lines


def line(employee_id: str, reports_to_id: str | None = None, company_id: str | None = "cmp_1"):
    return ReportingLine(
        employee_id=employee_id, reports_to_id=reports_to_id, company_id=company_id
    )


# -- accepted hierarchies ---------------------------------------------------


def test_a_flat_workforce_is_valid():
    validate_reporting_lines([line("a"), line("b"), line("c")])


def test_a_single_chain_is_valid():
    validate_reporting_lines(
        [line("a", "b"), line("b", "c"), line("c", "d"), line("d")]
    )


def test_a_reference_forward_in_the_request_is_valid():
    """Employees may report to peers declared later in the same request.

    This is what makes whole-workforce replacement order-independent.
    """
    validate_reporting_lines([line("a", "b"), line("b")])


def test_a_diamond_is_valid_and_not_a_cycle():
    """Two managers reporting to one boss is a hierarchy, not a loop."""
    validate_reporting_lines(
        [line("a", "d"), line("b", "d"), line("c", "d"), line("d")]
    )
    assert find_cycle({node.employee_id: node for node in [
        line("a", "d"), line("b", "d"), line("c", "d"), line("d")
    ]}) is None


def test_a_deep_chain_is_valid():
    chain = [line(f"e{index}", f"e{index + 1}") for index in range(40)] + [line("e40")]
    validate_reporting_lines(chain)


# -- rejected hierarchies ---------------------------------------------------


def test_self_reference_is_rejected():
    with pytest.raises(RelationshipError, match="cannot report to itself"):
        validate_reporting_lines([line("a", "a")])


def test_a_missing_reporting_target_is_rejected():
    with pytest.raises(RelationshipError, match="not part of this workforce"):
        validate_reporting_lines([line("a", "ghost")])


def test_a_target_belonging_to_another_company_is_rejected():
    with pytest.raises(RelationshipError, match="another company"):
        validate_reporting_lines([line("a", "b", "cmp_1"), line("b", None, "cmp_2")])


def test_an_unknown_id_known_to_be_foreign_is_reported_as_cross_company():
    """The distinction that matters when fixing the request: foreign vs missing."""
    with pytest.raises(RelationshipError, match="another company"):
        validate_reporting_lines(
            [line("a", "b")],
            foreign_employee_companies={"b": "cmp_other"},
        )


def test_a_two_person_cycle_is_rejected():
    with pytest.raises(RelationshipError, match="cycle"):
        validate_reporting_lines([line("a", "b"), line("b", "a")])


def test_a_three_person_cycle_is_rejected():
    with pytest.raises(RelationshipError, match="cycle"):
        validate_reporting_lines([line("a", "b"), line("b", "c"), line("c", "a")])


def test_a_longer_cycle_is_rejected():
    with pytest.raises(RelationshipError, match="cycle"):
        validate_reporting_lines(
            [line("a", "b"), line("b", "c"), line("c", "d"), line("d", "b")]
        )


def test_a_cycle_hidden_behind_a_valid_prefix_is_rejected():
    """A cycle in the middle of an otherwise sound hierarchy is still a cycle."""
    with pytest.raises(RelationshipError, match="cycle"):
        validate_reporting_lines(
            [
                line("boss"),
                line("left", "loop_a"),
                line("right", "loop_b"),
                line("loop_a", "loop_b"),
                line("loop_b", "loop_a"),
            ]
        )


def test_the_reported_cycle_path_is_included_in_details():
    with pytest.raises(RelationshipError) as caught:
        validate_reporting_lines([line("a", "b"), line("b", "c"), line("c", "a")])
    assert caught.value.details["cycle"][0] == caught.value.details["cycle"][-1]


def test_a_repeated_employee_id_is_rejected():
    with pytest.raises(RelationshipError, match="more than once"):
        validate_reporting_lines([line("a"), line("a")])


def test_the_error_names_the_offending_relationship():
    with pytest.raises(RelationshipError) as caught:
        validate_reporting_lines([line("a", "b"), line("b", "ghost")])
    assert caught.value.field == "employees[b].reportsToId"