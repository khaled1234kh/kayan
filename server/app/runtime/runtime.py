"""The KAYAN runtime: the backend owns the business workflow.

    KayanRuntime.request_order(...)
        -> persist -> commit -> publish   (for every state change)
        -> clients observe over the WebSocket

This is the single authority for business transitions in backend mode. It decides
which agent works next, forms agent intents, calls TrustGate, creates messages
and handoffs, moves task status, and emits events. The client sends one command
and watches.

Entry points:

    runtime = KayanRuntime()
    runtime.request_order(order_id="1042", request_id="abc")

No browser, no React, no Zustand: a backend test can drive a complete order
through this class alone.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    CommandRequest,
    Condition,
    Task,
    TaskStatus,
    WorkflowRun,
    WorkflowRunStatus,
)
from app.runtime.collaboration import AgentCollaboration, RunContext
from app.runtime.workflow import (
    AcceptStep,
    CompleteStep,
    DEFAULT_ORDER_ID,
    DelegateStep,
    EventStep,
    IntentStep,
    ReceiveStep,
    SendStep,
    UnknownOrder,
    scenario_for,
    steps_for_order,
)
from app.security.trustgate import AgentIntent
from app.services.events import EventService
from app.services.execution import ContractGuard
from app.services.run_metrics import derive_run_metrics

logger = logging.getLogger(__name__)

#: Fixed origin for the workflow's virtual clock.
#:
#: Runs are stamped from the workflow's own authored step delays rather than the
#: wall clock, so a trial's logical duration and its intervals are identical on
#: every execution — which is what makes repeated trials comparable. Real elapsed
#: machine time is recorded separately in ``wall_clock_ms``.


class OrderAlreadyRunning(RuntimeError):
    """Raised when the same order already has an active workflow."""

    def __init__(self, order_id: str, run_id: str) -> None:
        super().__init__(f"Order {order_id} already has an active run: {run_id}")
        self.order_id = order_id
        self.run_id = run_id


class KayanRuntime:
    """Executes the KAYAN order workflow against the database."""

    def __init__(self, pace_ms: int | None = None, mode: str = "enforced") -> None:
        """
        ``pace_ms`` multiplies each step's authored delay so a run can be paced
        for watching. It defaults to 0 — the business workflow has no reason to
        sleep, and delays are a presentation concern, not domain logic.

        ``mode`` is 'enforced' (the default, and the only mode an ordinary
        ``request_order`` can use) or 'baseline', the experimental condition that
        records a *simulated* allow instead of consulting TrustGate.
        """
        self.pace_ms = get_settings().runtime_pace_ms if pace_ms is None else pace_ms
        self.mode = mode

    # -- entry point -------------------------------------------------------

    def request_order(
        self,
        session: Session,
        *,
        order_id: str = DEFAULT_ORDER_ID,
        request_id: str | None = None,
        condition: str | None = None,
        experiment_id: str | None = None,
        seed: str | None = None,
        employee_id: str | None = None,
        company_id: str | None = None,
    ) -> WorkflowRun:
        """Execute one complete order. Synchronous and browser-free.

        Creates a distinct run id, persists the task, executes every step, then
        finalises the run from the events it actually produced. On failure the
        run is marked ``failed`` and no completion event is fabricated.

        When ``employee_id`` and ``company_id`` are supplied, the runtime resolves
        the employee's active contract before any step executes (P0.7 foundation).
        The contract must be active and hash-verified; otherwise the run stops
        before any work begins.
        """
        scenario_for(order_id)  # raises UnknownOrder for an unsupported order

        if employee_id is not None and company_id is not None:
            ContractGuard(session).resolve_active_contract(company_id, employee_id)
            logger.info(
                "resolved active contract for employee %s before execution", employee_id
            )

        run_id = self._new_run_id()
        short = run_id.rsplit("_", 1)[-1]
        task_id = f"TASK-{short}-0001"
        started_wall = time.perf_counter()

        run = WorkflowRun(
            id=run_id,
            request_id=request_id,
            order_id=order_id,
            status=WorkflowRunStatus.RUNNING,
            run_index=self._next_run_index(session, order_id, condition, experiment_id),
            experiment_id=experiment_id,
            condition=Condition(condition) if condition else None,
            seed=seed,
        )
        session.add(run)
        session.commit()

        task = Task(
            id=task_id,
            title=scenario_for(order_id)["title"],
            objective=scenario_for(order_id)["title"],
            status=TaskStatus.OPEN,
            assigned_agent_id="manager",
            parent_task_id=None,
        )
        session.add(task)
        session.commit()

        context = RunContext(run_id=run_id, task_id=task_id, order_id=order_id, short=short)
        collaboration = AgentCollaboration(session, context, mode=self.mode)
        service = EventService(session)

        last_timestamp_ms = 0
        try:
            for step in steps_for_order(order_id, task_id):
                if self.pace_ms:
                    time.sleep(step.after_ms * self.pace_ms / 1000)

                before = service.count_events(run_id=run_id)
                # Advance the virtual clock by the step's authored delay.
                last_timestamp_ms += step.after_ms
                self._execute(collaboration, step, context, last_timestamp_ms)
                self._apply_task_progress(session, task, service, before, run_id)

            run.status = WorkflowRunStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
        except Exception as exc:  # noqa: BLE001 - recorded, never swallowed
            logger.exception("workflow run %s failed at step", run_id)
            self._fail(session, run, task, exc)

        run.wall_clock_ms = int((time.perf_counter() - started_wall) * 1000)
        self._finalise(session, run, task, service, run_id)
        session.refresh(run)
        return run

    # -- step execution ----------------------------------------------------

    def _execute(
        self,
        collaboration: AgentCollaboration,
        step: Any,
        context: RunContext,
        virtual_ms: int,
    ) -> None:
        """Run one step at logical offset ``virtual_ms``.

        The logical offset comes from the authored step delays, so it is total and
        reproducible. It is stored separately from the event's real timestamp;
        nothing here sleeps to produce a larger number.
        """
        context.virtual_ms = virtual_ms
        stamp = virtual_ms

        if isinstance(step, EventStep):
            self._emit(collaboration, step.emit, step.actor_id, {**step.payload, "message": step.message}, stamp)
        elif isinstance(step, DelegateStep):
            handoff = collaboration.create_handoff(step.handoff)
            # The session then reports the transfer and validates the plan.
            self._emit(
                collaboration,
                "task_handoff",
                handoff.from_agent_id,
                {"handoff": collaboration.handoff_wire(handoff), "message": step.message},
                stamp,
            )
            self._emit(
                collaboration,
                "plan_validated",
                handoff.from_agent_id,
                {"message": "Manager validated the plan"},
                stamp,
            )
        elif isinstance(step, AcceptStep):
            handoff = collaboration.accept_handoff()
            if handoff is not None and handoff.source_message_id:
                # The delegation message itself is delivered, then work starts.
                collaboration.receive_message(handoff.source_message_id)
                self._emit(
                    collaboration,
                    "task_started",
                    handoff.to_agent_id,
                    {"message": f"{handoff.to_agent_id} started work"},
                    stamp,
                )
        elif isinstance(step, SendStep):
            collaboration.send_message(step.draft)
        elif isinstance(step, ReceiveStep):
            collaboration.receive_message()
        elif isinstance(step, CompleteStep):
            collaboration.complete_handoff()
        elif isinstance(step, IntentStep):
            intent = AgentIntent(
                agent_id=step.agent_id,
                action=step.action,
                resource=step.resource,
                source=step.source,
                context={"taskId": context.task_id, "orderId": context.order_id},
            )
            decision = collaboration.authorize(intent)
            collaboration.emit_intent_outcome(
                intent,
                decision,
                allowed=step.allowed,
                denied_message=step.denied_message,
                denied_follow_up=step.denied_follow_up,
            )
        else:  # pragma: no cover - exhaustive over the step union
            raise TypeError(f"Unknown step type: {type(step).__name__}")

    def _emit(
        self,
        collaboration: AgentCollaboration,
        event_type: str,
        actor_id: str | None,
        payload: dict[str, Any],
        stamp_ms: int,
    ) -> None:
        """Emit with an explicit monotonic timestamp.

        ``EventService.record`` allocates the sequence and commits; the timestamp
        is passed so the feed order matches the sequence order.
        """
        collaboration.events.record(
            event_type=event_type,
            stream_id=collaboration._ctx.stream_id,
            actor_id=actor_id,
            task_id=collaboration._ctx.task_id,
            run_id=collaboration._ctx.run_id,
            payload=payload,
            clock_offset_ms=stamp_ms,
        )

    # -- task transitions --------------------------------------------------

    def _apply_task_progress(
        self,
        session: Session,
        task: Task,
        service: EventService,
        before_count: int,
        run_id: str,
    ) -> None:
        """Apply the same task rules the frontend reducer applies.

        `blocked` / `policy_denied` block the task, `task_started` reopens it, and
        an order-level `task_completed` completes it. Mirroring the reducer keeps
        the stored task and the client state from disagreeing.
        """
        events = service.list_events(run_id=run_id, limit=1000)
        new_events = events[-1:] if len(events) > before_count else []

        changed = False
        for event in new_events:
            if event.event_type in ("blocked", "policy_denied"):
                if task.status != TaskStatus.BLOCKED:
                    task.status = TaskStatus.BLOCKED
                    changed = True
            elif event.event_type == "task_started":
                if task.status == TaskStatus.BLOCKED:
                    task.status = TaskStatus.OPEN
                    changed = True
            elif event.event_type == "task_completed" and "handoff" not in (event.payload or {}):
                if task.status != TaskStatus.COMPLETED:
                    task.status = TaskStatus.COMPLETED
                    changed = True
        if changed:
            session.commit()

    # -- run bookkeeping ---------------------------------------------------

    def _finalise(
        self,
        session: Session,
        run: WorkflowRun,
        task: Task,
        service: EventService,
        run_id: str,
    ) -> None:
        """Derive the run's numbers from the events it actually produced."""
        events = service.list_events(run_id=run_id, limit=2000)
        metrics = derive_run_metrics(events)
        run.event_count = metrics["event_count"]
        run.message_count = metrics["message_count"]
        run.handoff_count = metrics["handoff_count"]
        run.policy_decision_count = metrics["policy_decision_count"]
        run.denial_count = metrics["denial_count"]
        run.violation_count = metrics["violation_count"]
        run.blocked_count = metrics["blocked_count"]
        run.recovery_count = metrics["recovery_count"]
        run.unauthorized_action_attempted = metrics["unauthorized_action_attempted"]
        run.unauthorized_action_allowed = metrics["unauthorized_action_allowed"]
        run.completed = metrics["completed"] and run.status == WorkflowRunStatus.COMPLETED
        run.duration_ms = metrics["duration_ms"]
        run.timings = metrics["timings"]
        # An order-level completion is the final state; a failed run reports its
        # own status rather than pretending to have finished.
        run.final_state = task.status.value
        if run.completed_at is None:
            run.completed_at = datetime.now(timezone.utc)
        session.commit()

    def _fail(self, session: Session, run: WorkflowRun, task: Task, exc: Exception) -> None:
        """Record the failure honestly. Never emit a success completion."""
        run.status = WorkflowRunStatus.FAILED
        run.error = f"{type(exc).__name__}: {exc}"
        run.completed_at = datetime.now(timezone.utc)
        if task.status != TaskStatus.COMPLETED:
            task.status = TaskStatus.BLOCKED
        session.commit()

    def _new_run_id(self) -> str:
        return f"run_{uuid.uuid4().hex[:12]}"

    def _next_run_index(
        self, session: Session, order_id: str, condition: str | None, experiment_id: str | None
    ) -> int:
        """Ordinal within the run's own series.

        An experimental trial is numbered within its condition of its experiment,
        so matched baseline/enforced pairs share an index. An ordinary order run
        is numbered against the order.
        """
        stmt = select(func.count()).select_from(WorkflowRun)
        if experiment_id is not None and condition is not None:
            stmt = stmt.where(
                WorkflowRun.experiment_id == experiment_id,
                WorkflowRun.condition == condition,
            )
        else:
            stmt = stmt.where(WorkflowRun.order_id == order_id)
        return int(session.execute(stmt).scalar_one()) + 1


class RuntimeGuard:
    """One active workflow per order, and at-most-once per requestId.

    Both checks are backed by the database rather than process memory, so they
    survive a restart; the in-process lock simply avoids starting work that is
    about to be rejected.
    """

    def __init__(self) -> None:
        self._locks: dict[str, Any] = {}

    def lock_for(self, order_id: str):
        """A per-order lock, created on demand."""
        import threading

        lock = self._locks.get(order_id)
        if lock is None:
            lock = threading.Lock()
            self._locks[order_id] = lock
        return lock

    @staticmethod
    def active_run_for(session: Session, order_id: str) -> WorkflowRun | None:
        return session.execute(
            select(WorkflowRun)
            .where(
                WorkflowRun.order_id == order_id,
                WorkflowRun.status == WorkflowRunStatus.RUNNING,
            )
            .order_by(WorkflowRun.started_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    @staticmethod
    def claim_request(
        session: Session,
        *,
        request_id: str,
        command: str,
        order_id: str,
    ) -> tuple[bool, str | None, CommandRequest | None]:
        """Record a requestId exactly once.

        Returns ``(fresh, reason, record)``. A duplicate requestId is detected by
        the primary key, so a redelivered command cannot start a second run.
        """
        existing = session.get(CommandRequest, request_id)
        if existing is not None:
            return False, "duplicate_request", existing

        record = CommandRequest(
            request_id=request_id,
            command=command,
            order_id=order_id,
            accepted=True,
        )
        session.add(record)
        try:
            session.commit()
        except Exception:  # unique violation: someone claimed it first
            session.rollback()
            existing = session.get(CommandRequest, request_id)
            return False, "duplicate_request", existing
        return True, None, record

    @staticmethod
    def mark_rejected(
        session: Session,
        *,
        request_id: str,
        reason: str,
    ) -> CommandRequest | None:
        """Record a refusal on the already-claimed requestId.

        The request was claimed before the conflict checks, so a refusal updates
        that row rather than inserting a second one with the same primary key.
        A rejected request stays on record and cannot be retried into success.
        """
        record = session.get(CommandRequest, request_id)
        if record is None:
            return None
        record.accepted = False
        record.reason = reason
        session.commit()
        return record
