"""In-process publication point for persisted events.

This is the seam the WebSocket bridge will subscribe to in a later task. It is
deliberately transport-free: subscribers receive already-persisted events and
never influence durability.

Contract: :meth:`EventBus.publish` is only ever called *after* the event has been
committed to the database (see ``services.events.EventService.record``), so no
client can observe state the backend failed to record.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

Subscriber = Callable[[dict[str, Any]], None]


class EventBus:
    """Minimal synchronous fan-out of persisted events."""

    def __init__(self) -> None:
        self._subscribers: list[Subscriber] = []

    def subscribe(self, subscriber: Subscriber) -> Callable[[], None]:
        """Register a subscriber; returns an unsubscribe callable."""
        self._subscribers.append(subscriber)

        def unsubscribe() -> None:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)

        return unsubscribe

    def publish(self, event: dict[str, Any]) -> None:
        """Deliver a persisted event to subscribers.

        One failing subscriber must not stop the others or affect persistence.
        """
        for subscriber in list(self._subscribers):
            try:
                subscriber(event)
            except Exception:  # pragma: no cover - defensive
                logger.exception("Event subscriber failed for %s", event.get("id"))

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


_bus = EventBus()


def get_event_bus() -> EventBus:
    """Process-wide bus."""
    return _bus