"""Event envelope and in-memory event log for Genie OS."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class EventEnvelope:
    """Append-only event record used by the OS kernel."""

    type: str
    source: str
    payload: dict[str, Any] = field(default_factory=dict)
    task_id: str | None = None
    trace_id: str | None = None
    privacy: str = "local"
    event_id: str = field(default_factory=lambda: f"evt_{uuid4().hex}")
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "type": self.type,
            "source": self.source,
            "task_id": self.task_id,
            "trace_id": self.trace_id,
            "privacy": self.privacy,
            "payload": self.payload,
            "created_at": self.created_at,
        }


class EventLog:
    """Bounded in-memory event log.

    This is Phase 1 infrastructure. A durable event store can replace it behind
    the same methods once the schema migration is approved.
    """

    def __init__(self, max_events: int = 1000):
        self.max_events = max_events
        self._events: list[EventEnvelope] = []

    def append(self, event: EventEnvelope) -> EventEnvelope:
        self._events.append(event)
        if len(self._events) > self.max_events:
            self._events = self._events[-self.max_events :]
        return event

    def recent(self, limit: int = 50) -> list[EventEnvelope]:
        return self._events[-limit:]

    def for_task(self, task_id: str) -> list[EventEnvelope]:
        return [event for event in self._events if event.task_id == task_id]
