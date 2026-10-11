"""Per-client event stream buffer.

The hard part of a WebSocket bridge is the handover between "replay history" and
"tail live events". Doing this naively —

    1. query history
    2. subscribe to the bus

— loses any event committed between those two steps.

This module uses the safe ordering instead:

    1. subscribe to the bus immediately, buffering everything it publishes
    2. read the historical cutoff (highest committed sequence)
    3. send persisted events up to the cutoff
    4. flush buffered events after the cutoff
    5. keep draining the buffer

Two invariants make this safe:

* **No loss.** An event published before step 2 is either already in the step-3
  replay or buffered in step 1, so it is sent exactly once.
* **No reordering.** Sending only advances to ``last_sent + 1``. If the buffer
  holds sequence 15 while 14 is still in flight, the connection waits for 14
  instead of emitting 15 first.

Because ``sequence`` is allocated inside the insert transaction and published only
after commit, gaps cannot persist; the gap timeout is a defensive backstop, not a
normal path.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

#: How long to wait for a missing sequence before sending out of order anyway.
GAP_TIMEOUT_SECONDS = 5.0


class EventStreamConnection:
    """Buffered, order-preserving view of one stream for one client."""

    def __init__(self, stream_id: str, after_sequence: int = 0) -> None:
        self.stream_id = stream_id
        self.last_sent = max(0, after_sequence)
        self._lock = threading.Lock()
        self._pending: list[dict[str, Any]] = []
        self._pending_ids: set[str] = set()
        self._wake: asyncio.Event | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._closed = False

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    # -- wiring ----------------------------------------------------------

    def attach_wakeup(self, wake: asyncio.Event) -> None:
        """Register the event the sender task waits on."""
        self._wake = wake

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._pending.clear()
            self._pending_ids.clear()

    @property
    def closed(self) -> bool:
        return self._closed

    # -- bus callback (synchronous, may run on any thread) -----------------

    def on_publish(self, wire: dict[str, Any]) -> None:
        """Bus subscriber. Buffers events belonging to this client's stream."""
        if wire.get("streamId") != self.stream_id:
            return
        sequence = int(wire.get("sequence") or 0)
        with self._lock:
            if self._closed or sequence <= self.last_sent:
                # Already delivered by the replay; exactly-once is preserved.
                return
            event_id = str(wire.get("id"))
            if event_id in self._pending_ids:
                return
            self._pending.append(wire)
            self._pending_ids.add(event_id)
        self._signal()

    def _signal(self) -> None:
        wake = self._wake
        if wake is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # Called from a worker thread: hand the wakeup to the loop thread.
            loop = self._loop
            if loop is None:
                return
            loop.call_soon_threadsafe(wake.set)
        else:
            wake.set()

    # -- sender side ------------------------------------------------------

    def take_ready(self, *, allow_gap: bool = False) -> list[dict[str, Any]]:
        """Pop the next contiguous run of events, ascending by sequence."""
        with self._lock:
            if not self._pending:
                return []
            self._pending.sort(key=lambda e: int(e.get("sequence") or 0))
            batch: list[dict[str, Any]] = []
            while self._pending:
                head = int(self._pending[0].get("sequence") or 0)
                if head > self.last_sent + 1 and not allow_gap:
                    if not batch:
                        return []
                    break
                if head <= self.last_sent:
                    self._pending_ids.discard(str(self._pending[0].get("id")))
                    self._pending.pop(0)
                    continue
                event = self._pending.pop(0)
                self._pending_ids.discard(str(event.get("id")))
                self.last_sent = int(event.get("sequence") or self.last_sent)
                batch.append(event)
            return batch

    def has_pending(self) -> bool:
        with self._lock:
            return bool(self._pending)

    async def _wait_signal(self, timeout: float) -> None:
        """Block until a publish arrives or ``timeout`` elapses."""
        wake = self._wake
        if wake is None:
            await asyncio.sleep(timeout)
            return
        try:
            await asyncio.wait_for(wake.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return
        finally:
            wake.clear()

    async def wait_until_data(self, timeout: float = 1.0) -> None:
        """Wait for the buffer to become non-empty."""
        if self.has_pending():
            return
        await self._wait_signal(timeout)

    async def wait_for_gap_fill(self, timeout: float) -> None:
        """Wait for the missing sequence while a gap is outstanding."""
        await self._wait_signal(max(0.0, min(timeout, 1.0)))

    async def next_batch(self) -> list[dict[str, Any]]:
        """Await the next contiguous batch, resolving gaps after a timeout."""
        gap_deadline: float | None = None
        while not self.closed:
            batch = self.take_ready()
            if batch:
                return batch

            if not self.has_pending():
                # Nothing buffered: block until the next publish.
                gap_deadline = None
                await self.wait_until_data(timeout=1.0)
                continue

            # Buffered, but the next sequence is missing. Waiting (rather than
            # emitting) is what keeps the stream strictly ascending.
            now = asyncio.get_running_loop().time()
            if gap_deadline is None:
                gap_deadline = now + GAP_TIMEOUT_SECONDS
            remaining = gap_deadline - now
            if remaining <= 0:
                forced = self.take_ready(allow_gap=True)
                if forced:
                    logger.warning(
                        "stream %s gap timeout: sending sequence %s after %d",
                        self.stream_id,
                        forced[0].get("sequence"),
                        self.last_sent,
                    )
                    return forced
                gap_deadline = None
                continue
            await self.wait_for_gap_fill(remaining)
        return []