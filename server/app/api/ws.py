"""Read-only WebSocket event bridge.

    GET /ws/events?stream=main[&afterSequence=13]

On connect a client receives every persisted event for the stream in ascending
``sequence`` order, then continues to receive events as they are published. There
are no inbound command handlers: this bridge moves events from the backend to the
client and nothing else.

Frame format is the existing client event contract, unmodified::

    {"id","type","sequence","streamId","timestamp","actorId","taskId","payload"}

``timestamp`` is epoch milliseconds, exactly as the client contract defines it.
``sequence`` and ``streamId`` are additive ordering fields the client needs for
deduplication and the resume cursor; protocol metadata is never mixed into
``payload``.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import new_session
from app.events.bus import get_event_bus
from app.events.connection import EventStreamConnection
from app.models import Event
from app.runtime.commands import handle_command_frame
from app.runtime.runtime import RuntimeGuard
from app.services.events import EventService

logger = logging.getLogger(__name__)

router = APIRouter()

#: The prototype uses a single explicit stream.
DEFAULT_STREAM = "main"


def _fetch_history(stream_id: str, after_sequence: int) -> tuple[list[Event], int]:
    """Load persisted events after ``after_sequence`` plus the stream's cutoff."""
    session = new_session()
    try:
        cutoff = int(
            session.execute(
                select(Event.sequence)
                .where(Event.stream_id == stream_id)
                .order_by(Event.sequence.desc())
                .limit(1)
            ).scalar_one_or_none()
            or 0
        )
        rows = list(
            session.execute(
                select(Event)
                .where(Event.stream_id == stream_id, Event.sequence > after_sequence)
                .order_by(Event.sequence, Event.id)
            ).scalars()
        )
        return rows, cutoff
    finally:
        session.close()


@router.websocket("/ws/events")
async def stream_events(
    websocket: WebSocket,
    stream: str = Query(default=DEFAULT_STREAM),
    afterSequence: int | None = Query(default=None, ge=0),
) -> None:
    """Replay the stream, then tail it live, and accept commands.

    Read-only with respect to business state: the client may ask for work, but
    every state change is made by the runtime and persisted before publication.
    """
    await websocket.accept()
    after = afterSequence or 0

    connection = EventStreamConnection(stream_id=stream, after_sequence=after)
    connection.bind_loop(asyncio.get_running_loop())
    wake = asyncio.Event()
    connection.attach_wakeup(wake)
    guard = RuntimeGuard()

    # One session for this connection's command handling, closed on teardown.
    command_db = new_session()

    # 1. Subscribe BEFORE reading history, so anything committed while the
    #    replay query runs is buffered rather than lost.
    bus = get_event_bus()
    unsubscribe = bus.subscribe(connection.on_publish)
    logger.info("ws connected: stream=%s after_sequence=%d", stream, after)

    async def pump() -> None:
        """Owns the socket: replay first, then live batches, always ascending."""
        rows, cutoff = _fetch_history(stream, after)
        for row in rows:
            if row.sequence <= connection.last_sent:
                continue
            await websocket.send_json(EventService.to_client_event(row))
            connection.last_sent = row.sequence
        logger.info(
            "ws replay complete: stream=%s sent %d event(s) up to sequence %d (cutoff %d)",
            stream,
            len(rows),
            connection.last_sent,
            cutoff,
        )

        # 2. Drain whatever arrived during the replay, then stream live.
        while True:
            batch = connection.take_ready()
            if not batch:
                batch = await connection.next_batch()
            for event in batch:
                await websocket.send_json(event)

    async def receive_loop() -> None:
        """Handle inbound frames.

        Protocol frames (``{"kind":"command", ...}``) are validated and dispatched
        to the backend runtime. Anything else is refused with a protocol error, so
        a client can never push business state directly.
        """
        try:
            while True:
                frame = await websocket.receive_text()
                await handle_command_frame(
                    frame,
                    session=command_db,
                    session_factory=new_session,
                    stream_id=stream,
                    send=websocket.send_json,
                    guard=guard,
                )
        except WebSocketDisconnect:
            pass
        except RuntimeError:
            # Starlette raises when the socket closes while awaiting receive.
            pass
        finally:
            command_db.close()

    pump_task = asyncio.create_task(pump())
    receive_task = asyncio.create_task(receive_loop())
    try:
        # Whichever finishes first ends the connection: the client went away, or
        # the sender failed. A sender failure must reach the client instead of
        # leaving it waiting on a stream that will never produce another frame.
        done, _ = await asyncio.wait(
            {pump_task, receive_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            error = task.exception()
            if error is not None:
                logger.error(
                    "ws stream failed (stream=%s, task=%s): %r",
                    stream,
                    task.get_name(),
                    error,
                    exc_info=error,
                )
    finally:
        connection.close()
        unsubscribe()
        for task in (pump_task, receive_task):
            task.cancel()
        # Teardown must never block on a task that ignores cancellation.
        await asyncio.wait({pump_task, receive_task}, timeout=2.0)
        logger.info(
            "ws disconnected: stream=%s after sequence %d", stream, connection.last_sent
        )
        try:
            await websocket.close()
        except RuntimeError:
            pass