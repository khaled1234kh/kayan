"""Explicit Pydantic schemas for API boundaries.

ORM models are never exposed directly: the wire contract is these schemas.
"""

from app.schemas.agent import AgentOut
from app.schemas.budget import (
    BudgetAdjustmentRequest,
    BudgetReservationRequest,
    BudgetSettlementRequest,
    BudgetSummary,
    LedgerEntryOut,
    LedgerPage,
    ReserveResult,
    SettlementResult,
)
from app.schemas.common import ApiCreate, ApiSchema, HealthResponse
from app.schemas.company import (
    CompanyCreate,
    CompanyOut,
    CompanyTaskCreate,
    CompanyTaskOut,
    CompanyTaskUpdate,
    CompanyUpdate,
    EmployeeIn,
    EmployeeOut,
    RoleOut,
    TemplateOut,
    WorkforceOut,
    WorkforceReplace,
)
from app.schemas.contract import (
    ActivationOut,
    ContractGenerateRequest,
    ContractGenerationOut,
    ContractOut,
    ContractPatch,
    ContractSummaryOut,
    ContractVersionRequest,
    EmployeeAllocation,
    ResumeRequest,
)
from app.schemas.event import EventOut, ExperimentOut, WorkflowRunOut
from app.schemas.handoff import HandoffOut
from app.schemas.message import MessageOut
from app.schemas.recommendation import (
    RecommendationOut,
    RecommendationPreferences,
    RecommendationProposal,
    RecommendationRequest,
)
from app.schemas.task import TaskOut

__all__ = [
    "AgentOut",
    "ApiCreate",
    "ApiSchema",
    "BudgetAdjustmentRequest",
    "BudgetReservationRequest",
    "BudgetSettlementRequest",
    "BudgetSummary",
    "CompanyCreate",
    "CompanyOut",
    "CompanyTaskCreate",
    "CompanyTaskOut",
    "CompanyTaskUpdate",
    "CompanyUpdate",
    "EmployeeIn",
    "EmployeeOut",
    "EventOut",
    "ExperimentOut",
    "HandoffOut",
    "LedgerEntryOut",
    "LedgerPage",
    "HealthResponse",
    "MessageOut",
    "RecommendationOut",
    "ReserveResult",
    "SettlementResult",
    "RecommendationPreferences",
    "RecommendationProposal",
    "RecommendationRequest",
    "RoleOut",
    "TaskOut",
    "TemplateOut",
    "WorkforceOut",
    "WorkforceReplace",
    "WorkflowRunOut",
]