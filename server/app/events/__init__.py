"""Event contract, ordering and publication.

The event vocabulary is mirrored from the frontend contract
(``kayan-3d/src/types/events.ts``) so persisted events are directly consumable by
the existing visualization layer during the WebSocket migration.
"""

from app.events.bus import EventBus, get_event_bus
from app.events.ordering import next_sequence
from app.events.types import EVENT_CATALOGUE, EventCategory, EventType

__all__ = [
    "EVENT_CATALOGUE",
    "EventBus",
    "EventCategory",
    "EventType",
    "get_event_bus",
    "next_sequence",
]