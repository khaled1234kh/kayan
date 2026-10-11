"""Query and persistence services.

Services own all database access for their domain. Routes call services; services
call the ORM. No raw SQL and no ORM calls leak into route handlers.
"""

from app.services.agents import AgentService, get_agent_service
from app.services.catalog import SetupCatalogService, get_setup_catalog_service
from app.services.companies import CompanyService, get_company_service
from app.services.budget import BudgetService, get_budget_service
from app.services.contracts import ContractService, get_contract_service
from app.services.events import EventService, get_event_service
from app.services.handoffs import HandoffService, get_handoff_service
from app.services.lifecycle import CompanyLifecycleService, get_lifecycle_service
from app.services.messages import MessageService, get_message_service
from app.services.recommendations import RecommendationService, get_recommendation_service
from app.services.runs import RunService, get_run_service
from app.services.tasks import TaskService, get_task_service
from app.services.workforce import WorkforceService, get_workforce_service

__all__ = [
    "AgentService",
    "BudgetService",
    "CompanyService",
    "EventService",
    "HandoffService",
    "MessageService",
    "RecommendationService",
    "RunService",
    "SetupCatalogService",
    "TaskService",
    "WorkforceService",
    "get_agent_service",
    "get_budget_service",
    "get_company_service",
    "get_event_service",
    "get_handoff_service",
    "get_message_service",
    "get_recommendation_service",
    "get_run_service",
    "get_setup_catalog_service",
    "get_task_service",
    "get_workforce_service",
]