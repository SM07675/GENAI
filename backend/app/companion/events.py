"""EventManager — typed event catalog for Companion Mode.

Receives ContextDelta objects from ContextEngine (the reflex layer) and
produces structured CompanionEvent objects ready for CompanionBrain.

Event catalog covers all modes per spec §7:
  Gaming:  ENEMY_DETECTED, MULTIPLE_ENEMIES, PLAYER_KILL, PLAYER_DEATH,
           LOW_HEALTH, BOSS_DETECTED, OBJECTIVE, OBJECTIVE_COMPLETED,
           ROUND_START, ROUND_WIN, ROUND_LOSS, CLUTCH, IMPORTANT_CHANGE
  Coding:  CODE_ERROR, RUNTIME_ERROR, BUILD_FAILURE, TEST_FAILURE,
           TEST_SUCCESS, REPEATED_ERROR, CODE_FIXED
  Writing: SPELLING_ERROR, GRAMMAR_ERROR, TYPO, CLARITY_PROBLEM
  General: APP_CHANGED, LONG_SESSION, MILESTONE
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import structlog

from .context_engine import ContextDelta

log = structlog.get_logger("genie.companion.events")


class EventType(str, Enum):
    # Gaming
    ENEMY_DETECTED = "ENEMY_DETECTED"
    MULTIPLE_ENEMIES = "MULTIPLE_ENEMIES"
    ENEMY_ELIMINATED = "ENEMY_ELIMINATED"
    PLAYER_KILL = "PLAYER_KILL"
    PLAYER_DEATH = "PLAYER_DEATH"
    LOW_HEALTH = "LOW_HEALTH"
    BOSS_DETECTED = "BOSS_DETECTED"
    BOSS_ELIMINATED = "BOSS_ELIMINATED"
    OBJECTIVE = "OBJECTIVE"
    OBJECTIVE_COMPLETED = "OBJECTIVE_COMPLETED"
    ROUND_START = "ROUND_START"
    ROUND_WIN = "ROUND_WIN"
    ROUND_LOSS = "ROUND_LOSS"
    CLUTCH = "CLUTCH"
    IMPORTANT_CHANGE = "IMPORTANT_CHANGE"
    # Coding
    CODE_ERROR = "CODE_ERROR"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    BUILD_FAILURE = "BUILD_FAILURE"
    TEST_FAILURE = "TEST_FAILURE"
    TEST_SUCCESS = "TEST_SUCCESS"
    REPEATED_ERROR = "REPEATED_ERROR"
    CODE_FIXED = "CODE_FIXED"
    # Writing
    SPELLING_ERROR = "SPELLING_ERROR"
    GRAMMAR_ERROR = "GRAMMAR_ERROR"
    TYPO = "TYPO"
    CLARITY_PROBLEM = "CLARITY_PROBLEM"
    # General
    APP_CHANGED = "APP_CHANGED"
    LONG_SESSION = "LONG_SESSION"
    MILESTONE = "MILESTONE"
    UNKNOWN = "UNKNOWN"


@dataclass
class CompanionEvent:
    """A processed event ready for the CompanionBrain."""
    event_type: EventType
    importance: str          # low | medium | high | critical
    mode: str                # gaming | coding | writing | general
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)
    fired_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type.value,
            "importance": self.importance,
            "mode": self.mode,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


# ── Importance overrides (some events always override the vision model's importance) ─
_IMPORTANCE_OVERRIDES: dict[EventType, str] = {
    EventType.PLAYER_DEATH: "high",
    EventType.BOSS_DETECTED: "high",
    EventType.LOW_HEALTH: "high",
    EventType.CLUTCH: "critical",
    EventType.ROUND_WIN: "high",
    EventType.ROUND_LOSS: "high",
    EventType.BUILD_FAILURE: "high",
    EventType.REPEATED_ERROR: "high",
    EventType.CODE_FIXED: "medium",
    EventType.TEST_SUCCESS: "medium",
    EventType.PLAYER_KILL: "high",
    EventType.ENEMY_DETECTED: "high",
}


class EventManager:
    """Converts ContextDelta objects into typed CompanionEvents.

    Also maintains per-session error counters for REPEATED_ERROR detection.
    """

    def __init__(self) -> None:
        self._error_count: dict[str, int] = {}  # error_key → occurrence count
        self._last_error_key: Optional[str] = None
        self._events_fired: list[CompanionEvent] = []  # rolling history (max 50)

    def process_deltas(self, deltas: list[ContextDelta]) -> list[CompanionEvent]:
        """Convert a list of ContextDelta → CompanionEvent list.

        Applies importance overrides and REPEATED_ERROR escalation.
        """
        events: list[CompanionEvent] = []

        for delta in deltas:
            event = self._delta_to_event(delta)
            if event is None:
                continue
            events.append(event)

        # Keep rolling history
        self._events_fired = (self._events_fired + events)[-50:]
        return events

    def _delta_to_event(self, delta: ContextDelta) -> Optional[CompanionEvent]:
        """Convert one delta to a CompanionEvent."""
        try:
            event_type = EventType(delta.event_type)
        except ValueError:
            event_type = EventType.UNKNOWN

        if event_type == EventType.UNKNOWN:
            log.debug("unknown_event_type", raw=delta.event_type)
            return None

        # Importance override
        importance = _IMPORTANCE_OVERRIDES.get(event_type, delta.importance)

        # REPEATED_ERROR escalation for coding mode
        if event_type in (EventType.CODE_ERROR, EventType.RUNTIME_ERROR,
                           EventType.BUILD_FAILURE, EventType.TEST_FAILURE):
            error_key = f"{event_type.value}:{delta.mode}"
            self._error_count[error_key] = self._error_count.get(error_key, 0) + 1
            if self._last_error_key == error_key and self._error_count[error_key] >= 3:
                # Escalate to REPEATED_ERROR
                event_type = EventType.REPEATED_ERROR
                importance = "high"
            self._last_error_key = error_key
        elif event_type == EventType.CODE_FIXED:
            # Reset error counters when code is fixed
            self._error_count.clear()
            self._last_error_key = None

        return CompanionEvent(
            event_type=event_type,
            importance=importance,
            mode=delta.mode,
            confidence=delta.confidence,
            metadata=delta.metadata or (
                delta.current_value if isinstance(delta.current_value, dict) else {}
            ),
        )

    def reset_session_counters(self) -> None:
        """Reset per-session state (call on companion start)."""
        self._error_count.clear()
        self._last_error_key = None
        self._events_fired.clear()

    def recent_event_types(self, last_n: int = 10) -> list[str]:
        """Return event type strings from recent history."""
        return [e.event_type.value for e in self._events_fired[-last_n:]]
