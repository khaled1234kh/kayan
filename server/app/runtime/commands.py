"""The WebSocket command handler.

Kept apart from the endpoint itself so the protocol rules are testable without a
socket. Two commands exist:

* ``request_order`` — run one order under the enforced TrustGate
* ``run_comparison`` — run one coordinated baseline-vs-enforced experiment

    CLIENT -> SERVER   {"kind":"command", ...}
    SERVER -> CLIENT   {"kind":"command_ack", ...} then business events

The acknowledgement says only whether the command was accepted. For a comparison
it carries the ``experimentId`` to poll; it does not mean the experiment has
finished. The business outcome is the persisted event stream, which the client
already receives on the same socket.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from sqlalchemy.orm import Session

from app.db.session import new_session
from app.models import Company, CompanyStatus, WorkflowRunStatus
from app.runtime.autonomous import (
    get_active_company,
    run_until_target_or_budget,
)
from app.runtime.experiment_commands import accept_comparison, execute_comparison
from app.runtime.runtime import KayanRuntime, RuntimeGuard
from app.runtime.workflow import DEFAULT_ORDER_ID, UnknownOrder, scenario_for
from app.schemas.commands import (
    CommandAck,
    ProtocolError,
    RequestOrderCommand,
    RunAutonomousCommand,
    RunComparisonCommand,
    parse_command,
)

logger = logging.getLogger(__name__)

#: Called with the finished run or experiment, for logging/observability.
RunObserver = Callable[[Any], Awaitable[None]]

#: Runtime tasks in flight. Tracked so a graceful shutdown can wait for them
#: instead of dropping a half-executed workflow on the floor.
_ACTIVE_RUNS: set[asyncio.Task] = set()


def track_run(task: asyncio.Task) -> asyncio.Task:
    """Register a background task until it finishes."""
    _ACTIVE_RUNS.add(task)
    task.add_done_callback(_ACTIVE_RUNS.discard)
    return task


async def drain_active_runs(timeout: float = 120.0) -> None:
    """Wait for in-flight work, bounded. Called on application shutdown."""
    pending = [task for task in _ACTIVE_RUNS if not task.done()]
    if not pending:
        return
    logger.info("waiting for %d in-flight workflow/experiment task(s)", len(pending))
    _done, still_pending = await asyncio.wait(pending, timeout=timeout)
    for task in still_pending:
        logger.warning("background task still in flight after %.0fs; cancelling", timeout)
        task.cancel()


async def run_order_in_background(
    *,
    session_factory: Callable[[], Session],
    command: RequestOrderCommand,
    on_finished: RunObserver | None = None,
) -> None:
    """Execute a requested order off the event loop and dispose the session.

    The workflow is synchronous database work, so it runs in a worker thread:
    one slow run must not stall other WebSocket clients. An ordinary order always
    uses the enforced evaluator.
    """

    def work() -> Any:
        session = session_factory()
        try:
            return KayanRuntime(mode="enforced").request_order(
                session,
                order_id=command.order_id,
                request_id=command.request_id,
            )
        finally:
            session.close()

    run = await asyncio.to_thread(work)
    if on_finished is not None:
        await on_finished(run)


async def run_autonomous_in_background(
    *,
    session_factory: Callable[[], Session],
    company_id: str,
    max_iterations: int,
    on_finished: RunObserver | None = None,
) -> Any:
    """Work one company's board off the event loop and dispose the session.

    Task events are persisted through ``EventService`` as the loop works, so
    the socket's live tail streams them to the client exactly like any other
    business event. One slow board must not stall other WebSocket clients,
    hence the worker thread.
    """

    def work() -> Any:
        session = session_factory()
        try:
            return run_until_target_or_budget(
                session, company_id, max_iterations=max_iterations
            )
        finally:
            session.close()

    result = await asyncio.to_thread(work)
    if on_finished is not None:
        await on_finished(result)
    return result


def _refuse(
    command: Any, reason: str, *, experiment_id: str | None = None, run_id: str | None = None
) -> CommandAck:
    return CommandAck(
        request_id=command.request_id,
        command=command.command,
        accepted=False,
        reason=reason,
        experiment_id=experiment_id,
        run_id=run_id,
    )


async def handle_command_frame(
    raw: str | dict[str, Any],
    *,
    session: Session,
    session_factory: Callable[[], Session],
    stream_id: str,
    send: Callable[[dict[str, Any]], Awaitable[None]],
    guard: RuntimeGuard,
    on_finished: RunObserver | None = None,
) -> CommandAck | ProtocolError:
    """Validate and dispatch one inbound command frame.

    Returns the frame that was sent to the client. Malformed, unknown, disabled
    and conflicting commands all produce an explicit protocol response; none of
    them reach the workflow.
    """
    parsed = parse_command(raw)
    if isinstance(parsed, ProtocolError):
        await send(parsed.to_frame())
        return parsed

    command = parsed
    session.expire_all()

    if isinstance(command, RunComparisonCommand):
        return await _handle_comparison(
            command,
            session=session,
            session_factory=session_factory,
            send=send,
            guard=guard,
            on_finished=on_finished,
        )

    if isinstance(command, RunAutonomousCommand):
        return await _handle_autonomous(
            command,
            session=session,
            session_factory=session_factory,
            send=send,
            guard=guard,
            on_finished=on_finished,
        )

    # Idempotency: the same requestId must never start a second run.
    fresh, reason, record = guard.claim_request(
        session,
        request_id=command.request_id,
        command=command.command,
        order_id=command.order_id,
    )
    if not fresh:
        logger.info("command %s rejected: duplicate requestId %s", command.command, command.request_id)
        await send(
            _refuse(
                command,
                reason or "duplicate_request",
                run_id=record.run_id if record else None,
            ).to_frame()
        )
        return _refuse(command, reason or "duplicate_request", run_id=record.run_id if record else None)

    # Unknown order: refuse before creating anything.
    try:
        scenario_for(command.order_id)
    except UnknownOrder:
        guard.mark_rejected(session, request_id=command.request_id, reason="unknown_order")
        ack = _refuse(command, "unknown_order")
        await send(ack.to_frame())
        return ack

    # One active workflow per order.
    active = guard.active_run_for(session, command.order_id)
    if active is not None:
        guard.mark_rejected(session, request_id=command.request_id, reason="order_already_running")
        logger.info("command rejected: order %s already running as %s", command.order_id, active.id)
        ack = _refuse(command, "order_already_running", run_id=active.id)
        await send(ack.to_frame())
        return ack

    ack = CommandAck(request_id=command.request_id, command=command.command, accepted=True)
    await send(ack.to_frame())

    async def finished(run: Any) -> None:
        if on_finished is not None:
            await on_finished(run)
        _link_request_to_run(session_factory, command.request_id, run.id)
        logger.info(
            "workflow run %s finished: order=%s status=%s events=%s",
            run.id,
            run.order_id,
            run.status.value,
            run.event_count,
        )

    # The runtime owns the work; the socket stays free for events and acks.
    track_run(
        asyncio.create_task(
            run_order_in_background(
                session_factory=session_factory,
                command=command,
                on_finished=finished,
            )
        )
    )
    return ack


async def _handle_comparison(
    command: RunComparisonCommand,
    *,
    session: Session,
    session_factory: Callable[[], Session],
    send: Callable[[dict[str, Any]], Awaitable[None]],
    guard: RuntimeGuard,
    on_finished: RunObserver | None = None,
) -> CommandAck:
    """Validate, acknowledge, then run the comparison in the background."""
    ack, experiment = accept_comparison(session, command, claim=guard.claim_request)
    await send(ack.to_frame())

    if experiment is None or not ack.accepted:
        return ack

    async def run_and_report() -> None:
        result = await execute_comparison(
            session_factory=session_factory,
            experiment_id=experiment.id,
        )
        if on_finished is not None:
            await on_finished(result)
        logger.info(
            "experiment %s finished: status=%s",
            result.id,
            result.status.value,
        )

    track_run(asyncio.create_task(run_and_report()))
    return ack


async def _handle_autonomous(
    command: RunAutonomousCommand,
    *,
    session: Session,
    session_factory: Callable[[], Session],
    send: Callable[[dict[str, Any]], Awaitable[None]],
    guard: RuntimeGuard,
    on_finished: RunObserver | None = None,
) -> CommandAck:
    """Validate, acknowledge, then work the company's board in the background.

    The acknowledgement says only that the loop was accepted. The business
    outcome is the persisted task events, which the client already receives on
    the same socket's live tail. Existing ``request_order`` / ``run_comparison``
    paths are untouched.
    """
    fresh, reason, record = guard.claim_request(
        session,
        request_id=command.request_id,
        command=command.command,
        order_id=command.company_id or "autonomous",
    )
    if not fresh:
        logger.info(
            "command %s rejected: duplicate requestId %s", command.command, command.request_id
        )
        await send(
            _refuse(
                command,
                reason or "duplicate_request",
                run_id=record.run_id if record else None,
            ).to_frame()
        )
        return _refuse(command, reason or "duplicate_request", run_id=record.run_id if record else None)

    if command.company_id is not None:
        company = session.get(Company, command.company_id)
        if company is None:
            guard.mark_rejected(session, request_id=command.request_id, reason="unknown_company")
            ack = _refuse(command, "unknown_company")
            await send(ack.to_frame())
            return ack
        company_id = company.id
    else:
        active = get_active_company(session)
        if active is None:
            guard.mark_rejected(session, request_id=command.request_id, reason="no_active_company")
            ack = _refuse(command, "no_active_company")
            await send(ack.to_frame())
            return ack
        company = active
        company_id = active.id

    if company.status is not CompanyStatus.ACTIVE:
        guard.mark_rejected(session, request_id=command.request_id, reason="company_not_active")
        ack = _refuse(command, "company_not_active")
        await send(ack.to_frame())
        return ack

    ack = CommandAck(request_id=command.request_id, command=command.command, accepted=True)
    await send(ack.to_frame())

    async def run_and_report() -> None:
        result = await run_autonomous_in_background(
            session_factory=session_factory,
            company_id=company_id,
            max_iterations=command.max_iterations,
            on_finished=on_finished,
        )
        _link_request_to_run(session_factory, command.request_id, f"autonomous-{company_id}")
        logger.info(
            "autonomous run for %s finished: stop=%s cycles=%s completed=%s",
            company_id,
            result.stop_reason,
            result.cycles,
            result.completed,
        )

    track_run(asyncio.create_task(run_and_report()))
    return ack


def _link_request_to_run(
    session_factory: Callable[[], Session], request_id: str, run_id: str
) -> None:
    """Persist the linkage so a duplicate requestId can report the run it made."""
    from app.models import CommandRequest

    try:
        session = session_factory()
        try:
            stored = session.get(CommandRequest, request_id)
            if stored is not None:
                stored.run_id = run_id
                session.commit()
        finally:
            session.close()
    except Exception:  # pragma: no cover - bookkeeping only
        logger.exception("could not record run id for request %s", request_id)


__all__ = [
    "CommandAck",
    "DEFAULT_ORDER_ID",
    "ProtocolError",
    "RequestOrderCommand",
    "RunAutonomousCommand",
    "RunComparisonCommand",
    "WorkflowRunStatus",
    "drain_active_runs",
    "execute_comparison",
    "handle_command_frame",
    "new_session",
    "parse_command",
    "run_autonomous_in_background",
    "run_order_in_background",
    "track_run",
]