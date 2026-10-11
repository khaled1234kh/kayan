"""Experiment commands and background execution.

``run_comparison`` is accepted only when experiments are enabled in configuration,
and never in production. It is refused with ``experiments_disabled`` otherwise,
so the capability cannot be switched on by accident.

The comparison runs in a worker thread under the same task-tracking convention
as ``request_order``, so the socket is never held open for the duration.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import CommandRequest, Experiment, ExperimentStatus
from app.runtime.experiments import MAX_RUNS_PER_CONDITION, run_comparison, start_experiment
from app.runtime.workflow import UnknownOrder, scenario_for
from app.schemas.commands import CommandAck, RunComparisonCommand

logger = logging.getLogger(__name__)


def experiments_enabled() -> bool:
    return get_settings().experiments_allowed


def active_experiment_for(session: Session, order_id: str) -> Experiment | None:
    """An in-flight comparison for this order, if any."""
    return session.execute(
        select(Experiment)
        .where(Experiment.order_id == order_id, Experiment.status == ExperimentStatus.RUNNING)
        .order_by(Experiment.started_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def accept_comparison(
    session: Session,
    command: RunComparisonCommand,
    *,
    claim: Callable[..., tuple[bool, str | None, CommandRequest | None]],
) -> tuple[CommandAck, Experiment | None]:
    """Validate, guard and create the experiment. Returns the ack to send.

    Idempotency, the enable gate and the one-active-comparison rule are all
    enforced before anything starts running.
    """
    if not experiments_enabled():
        claim(
            session,
            request_id=command.request_id,
            command=command.command,
            order_id=command.order_id,
        )
        logger.info("run_comparison refused: experiments are disabled")
        return (
            CommandAck(
                request_id=command.request_id,
                command=command.command,
                accepted=False,
                reason="experiments_disabled",
            ),
            None,
        )

    fresh, reason, existing = claim(
        session,
        request_id=command.request_id,
        command=command.command,
        order_id=command.order_id,
    )
    if not fresh:
        experiment_id = None
        if existing is not None:
            found = session.execute(
                select(Experiment).where(Experiment.request_id == command.request_id)
            ).scalar_one_or_none()
            experiment_id = found.id if found else None
        return (
            CommandAck(
                request_id=command.request_id,
                command=command.command,
                accepted=False,
                reason=reason,
                experiment_id=experiment_id,
            ),
            None,
        )

    active = active_experiment_for(session, command.order_id)
    if active is not None:
        from app.runtime.runtime import RuntimeGuard

        RuntimeGuard.mark_rejected(session, request_id=command.request_id, reason="comparison_already_running")
        return (
            CommandAck(
                request_id=command.request_id,
                command=command.command,
                accepted=False,
                reason="comparison_already_running",
                experiment_id=active.id,
            ),
            None,
        )

    # An unsupported order is refused up front, exactly as request_order does, so
    # a comparison is never created for a scenario the runtime cannot execute.
    try:
        scenario_for(command.order_id)
    except UnknownOrder:
        from app.runtime.runtime import RuntimeGuard

        RuntimeGuard.mark_rejected(session, request_id=command.request_id, reason="unknown_order")
        return (
            CommandAck(
                request_id=command.request_id,
                command=command.command,
                accepted=False,
                reason="unknown_order",
            ),
            None,
        )

    experiment = start_experiment(
        session,
        request_id=command.request_id,
        order_id=command.order_id,
        seed=command.seed,
        runs_per_condition=min(command.runs_per_condition, MAX_RUNS_PER_CONDITION),
    )
    return (
        CommandAck(
            request_id=command.request_id,
            command=command.command,
            accepted=True,
            experiment_id=experiment.id,
        ),
        experiment,
    )


async def execute_comparison(
    *,
    session_factory: Callable[[], Session],
    experiment_id: str,
) -> Experiment:
    """Run a comparison to completion in a worker thread."""

    def work() -> Experiment:
        session = session_factory()
        try:
            experiment = session.get(Experiment, experiment_id)
            if experiment is None:
                raise LookupError(f"Unknown experiment: {experiment_id}")
            return run_comparison(session, experiment)
        finally:
            session.close()

    return await asyncio.to_thread(work)