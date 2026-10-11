"""Run metrics derived from the persisted event stream.

Nothing here is authored: every number is counted from events. This exists so a
run's row is a materialised read model rather than a second source of truth that
could disagree with it.

The counting rules mirror ``measureRun`` / ``measureTimings`` in
``kayan-3d/src/experiments/experimentMetrics.ts`` so a run measured by the
frontend harness and the same run re-measured here agree. Two deliberate
differences:

- the backend orders by ``sequence`` (the authoritative stream order) where the
  frontend orders by ``timestamp``; for a monotonic stream these are identical,
  and the backend stays correct when they are not
- the backend also reports ``violation_count``, which the backend needs to compare
  conditions but the local harness summary did not surface

Timing note: intervals and durations are measured from the run's logical
offsets (``clock_offset_ms``), which come from the workflow's authored step delays.
``events.timestamp`` is always real UTC; it is deliberately *not* used for logical
timing, so experiment results stay reproducible regardless of machine speed.
Real elapsed time is reported separately as ``wall_clock_ms``. No step ever sleeps
to manufacture a larger number.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

#: Events that mean the run made progress again after a block.
RECOVERY_EVENTS = ("information_provided", "task_started", "task_completed")

#: Key on an event payload that carries a TrustGate decision.
_DECISION_KEY = "policyDecision"


def _kind(event: Any) -> str:
    if isinstance(event, dict):
        return str(event.get("event_type") or event.get("type") or "")
    return str(event.event_type)


def _payload(event: Any) -> dict:
    if isinstance(event, dict):
        return event.get("payload") or {}
    return event.payload or {}


def _actor(event: Any) -> str | None:
    if isinstance(event, dict):
        return event.get("actor_id") or event.get("actorId")
    return event.actor_id


def _stamp(event: Any) -> datetime | None:
    if isinstance(event, dict):
        return event.get("timestamp")
    return event.timestamp


def _offset(event: Any) -> int | None:
    """Logical offset in ms within the owning run, when the event carries one."""
    value = event.get("clock_offset_ms") if isinstance(event, dict) else event.clock_offset_ms
    return int(value) if isinstance(value, (int, float)) else None


def _positions(events: Sequence[Any]) -> list[int]:
    """Comparable logical positions for a run's events.

    Uses ``clock_offset_ms`` when *every* event has one (the workflow case, which
    is reproducible), otherwise falls back to timestamps. Mixing the two would
    silently produce meaningless durations, so it is never done.
    """
    offsets = [_offset(event) for event in events]
    if events and all(offset is not None for offset in offsets):
        return [offset for offset in offsets if offset is not None]

    stamps = [_stamp(event) for event in events]
    return [
        int(stamp.timestamp() * 1000) if isinstance(stamp, datetime) else index
        for index, stamp in enumerate(stamps)
    ]


def _read_intent(payload: dict) -> dict | None:
    """The intent attached to an event, if any."""
    intent = payload.get("intent")
    return intent if isinstance(intent, dict) else None


def derive_run_metrics(events: Sequence[Any]) -> dict[str, Any]:
    """Count run metrics from ordered events.

    Accepts ORM ``Event`` rows or plain dicts, so it works before or after
    persistence.
    """
    kinds = [_kind(event) for event in events]

    denials = kinds.count("policy_denied")
    violations = kinds.count("policy_violation")
    blocked_count = kinds.count("blocked")
    policy_decision_count = sum(1 for event in events if _DECISION_KEY in _payload(event))
    unauthorized_attempted = any(_read_intent(_payload(event)) for event in events)

    # Recovery: the blocked agent resuming its own work. 0 or 1, matching the
    # frontend metric exactly.
    recovery = False
    for index, event in enumerate(events):
        if _kind(event) != "blocked":
            continue
        blocked_actor = _actor(event)
        if any(
            _kind(later) == "task_started" and _actor(later) == blocked_actor
            for later in events[index + 1 :]
        ):
            recovery = True
            break

    # Order completion is a ``task_completed`` with no handoff attached.
    completed = any(
        _kind(event) == "task_completed" and "handoff" not in _payload(event)
        for event in events
    )

    positions = _positions(events)
    duration_ms = max(positions) - min(positions) if len(positions) >= 2 else 0

    # A handoff is counted once, not once per event that mentions it: the
    # delegation emits task_handoff as both the message's semantic event and an
    # explicit transfer event. Distinct ids keep this equal to the frontend's
    # "number of handoffs".
    handoff_ids: set[str] = set()
    for event in events:
        payload = _payload(event)
        handoff = payload.get("handoff")
        if isinstance(handoff, dict) and isinstance(handoff.get("id"), str):
            handoff_ids.add(handoff["id"])
        elif isinstance(payload.get("handoffId"), str):
            handoff_ids.add(payload["handoffId"])

    return {
        "event_count": len(events),
        "message_count": kinds.count("agent_message_sent"),
        "handoff_count": len(handoff_ids),
        "policy_decision_count": policy_decision_count,
        "denial_count": denials,
        "violation_count": violations,
        "blocked_count": blocked_count,
        "recovery_count": 1 if recovery else 0,
        "unauthorized_action_attempted": unauthorized_attempted,
        # An allow is only "unauthorized and allowed" when nothing was denied.
        "unauthorized_action_allowed": violations > 0 and denials == 0,
        "duration_ms": duration_ms,
        "completed": completed,
        "final_state": "completed" if completed else (kinds[-1] if kinds else None),
        "timings": measure_timings(events),
    }


def _first(events: Sequence[Any], kind: str) -> Any | None:
    for event in events:
        if _kind(event) == kind:
            return event
    return None


def _last(events: Sequence[Any], kind: str) -> Any | None:
    for event in reversed(events):
        if _kind(event) == kind:
            return event
    return None


def _gap(start: Any | None, end: Any | None) -> int | None:
    """Interval between two events, measured on the same clock they share."""
    if start is None or end is None:
        return None
    start_offset, end_offset = _offset(start), _offset(end)
    if start_offset is not None and end_offset is not None:
        return max(0, end_offset - start_offset)
    a, b = _stamp(start), _stamp(end)
    if not isinstance(a, datetime) or not isinstance(b, datetime):
        return None
    return max(0, int((b - a).total_seconds() * 1000))


def measure_timings(events: Sequence[Any]) -> list[dict[str, Any]]:
    """The established workflow intervals, measured from event timestamps.

    Named and in milliseconds, exactly as the local harness reports them, so the
    two are comparable. Intervals whose endpoints are absent are omitted rather
    than invented.
    """
    order_start = _first(events, "order_received")
    order_complete = _last(events, "task_completed")
    instruction = _first(events, "agent_question")
    denial = _first(events, "policy_denied")
    blocked = _first(events, "blocked")
    complete = _last(events, "task_completed")

    recovery = None
    if blocked is not None:
        blocked_actor = _actor(blocked)
        blocked_at = _stamp(blocked)
        for event in events:
            if _kind(event) != "task_started" or _actor(event) != blocked_actor:
                continue
            stamp = _stamp(event)
            if blocked_at and stamp and stamp > blocked_at:
                recovery = event
                break

    candidates: list[tuple[str, int | None]] = [
        ("order_start_to_completion", _gap(order_start, order_complete)),
        ("instruction_received_to_policy_decision", _gap(instruction, denial or blocked)),
        ("policy_denial_to_blocked", _gap(denial, blocked)),
        ("blocked_to_authorized_recovery", _gap(blocked, recovery)),
        ("authorized_recovery_to_completion", _gap(recovery, complete)),
    ]
    return [{"name": name, "durationMs": ms} for name, ms in candidates if ms is not None]