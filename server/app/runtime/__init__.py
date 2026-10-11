"""The backend-authoritative KAYAN runtime.

The runtime owns workflow execution, agent collaboration, intents, TrustGate
calls, event emission, task transitions, messages and handoffs. The client sends
one command and observes the resulting events; it never decides anything.

Modules:

``runtime``         KayanRuntime entry point + run bookkeeping + concurrency guard
``workflow``        the ported order workflow (interactions, not state)
``collaboration``   message / handoff / intent creation, persisted via services
"""

from app.runtime.autonomous import (
    BUDGET_EXHAUSTED,
    DEFAULT_MAX_ITERATIONS,
    MAX_ITERATIONS,
    NO_ACTIONABLE_TASKS,
    TARGET_REACHED,
    CycleResult,
    LoopResult,
    execute_task,
    get_active_company,
    run_cycle,
    run_until_target_or_budget,
)
from app.runtime.collaboration import AgentCollaboration, RunContext
from app.runtime.experiments import build_comparison, run_comparison, start_experiment
from app.runtime.manager import Manager, PickOutcome
from app.runtime.runtime import KayanRuntime, OrderAlreadyRunning, RuntimeGuard
from app.runtime.workflow import (
    DEFAULT_ORDER_ID,
    SUPPORTED_ORDERS,
    UnknownOrder,
    scenario_for,
    step_signature,
    steps_for_order,
)

__all__ = [
    "AgentCollaboration",
    "BUDGET_EXHAUSTED",
    "CycleResult",
    "DEFAULT_MAX_ITERATIONS",
    "LoopResult",
    "MAX_ITERATIONS",
    "Manager",
    "NO_ACTIONABLE_TASKS",
    "PickOutcome",
    "TARGET_REACHED",
    "build_comparison",
    "execute_task",
    "get_active_company",
    "run_comparison",
    "run_cycle",
    "run_until_target_or_budget",
    "start_experiment",
    "DEFAULT_ORDER_ID",
    "KayanRuntime",
    "OrderAlreadyRunning",
    "RunContext",
    "RuntimeGuard",
    "SUPPORTED_ORDERS",
    "UnknownOrder",
    "scenario_for",
    "step_signature",
    "steps_for_order",
]