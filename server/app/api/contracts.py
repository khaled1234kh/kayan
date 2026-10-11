"""Contract endpoints.

Thin routes, as everywhere else: validate the request shape, call the service,
translate domain errors to HTTP. The lifecycle rules — what a draft may become, when
terms are frozen, which version supersedes which — belong to the service so they
hold for every caller.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import DbSession, to_http
from app.company.errors import DomainError
from app.schemas.contract import (
    ContractGenerateRequest,
    ContractOut,
    ContractPatch,
    ContractSummaryOut,
    ContractVersionRequest,
)
from app.services.contracts import ContractService

router = APIRouter(tags=["contracts"])


def _to_summary(contract) -> ContractSummaryOut:
    return ContractSummaryOut.model_validate(contract)


@router.post(
    "/companies/{company_id}/contracts/generate",
    response_model=list[ContractSummaryOut],
    status_code=status.HTTP_201_CREATED,
    summary="Generate draft contracts for the whole draft workforce",
)
def generate_contracts(
    company_id: str, payload: ContractGenerateRequest, session: DbSession
) -> list[ContractSummaryOut]:
    """One draft contract per configured employee, persisted atomically.

    Budget allocations are supplied explicitly for every employee; none is invented.
    """
    try:
        contracts = ContractService(session).generate(company_id, payload)
    except DomainError as error:
        raise to_http(error)
    return [_to_summary(contract) for contract in contracts]


@router.get(
    "/companies/{company_id}/contracts",
    response_model=list[ContractSummaryOut],
    summary="List a company's contract versions",
)
def list_contracts(company_id: str, session: DbSession) -> list[ContractSummaryOut]:
    """Every version, ordered by employee then version number."""
    try:
        contracts = ContractService(session).list_for_company(company_id)
    except DomainError as error:
        raise to_http(error)
    return [_to_summary(contract) for contract in contracts]


@router.get(
    "/contracts/{contract_id}",
    response_model=ContractOut,
    summary="Retrieve a contract and its version metadata",
)
def get_contract(contract_id: str, session: DbSession) -> ContractOut:
    try:
        contract = ContractService(session).get(contract_id)
    except DomainError as error:
        raise to_http(error)
    return ContractOut.model_validate(contract)


@router.patch(
    "/contracts/{contract_id}",
    response_model=ContractOut,
    summary="Edit a draft contract",
)
def patch_contract(
    contract_id: str, payload: ContractPatch, session: DbSession
) -> ContractOut:
    """Draft only. An activated contract needs a successor version instead."""
    try:
        contract, _changed = ContractService(session).patch(contract_id, payload)
    except DomainError as error:
        raise to_http(error)
    return ContractOut.model_validate(contract)


@router.post(
    "/contracts/{contract_id}/versions",
    response_model=ContractOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft successor to an activated contract",
)
def create_contract_version(
    contract_id: str, payload: ContractVersionRequest, session: DbSession
) -> ContractOut:
    """The predecessor stays active and untouched until a later resume."""
    try:
        successor = ContractService(session).create_successor(contract_id, payload)
    except DomainError as error:
        raise to_http(error)
    return ContractOut.model_validate(successor)