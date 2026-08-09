"""ContextEngine — AIRI-style reflex layer for Companion Mode.

The context engine is cheap and deterministic — no LLM calls here.
It owns three things:
  1. App/window identification via Win32 (zero API cost).
  2. Semantic context state (current_activity, current_mode, screen_context).
  3. Context Diff — compares previous vs current context and emits semantic
     deltas. Identical scenes produce zero events (the key spam-prevention gate).

Only genuinely interesting state changes escalate to CompanionBrain (the slow,
expensive conscious layer). This is the reflex→conscious split from AIRI.

Memory persistence
------------------
Only durable *preferences* are persisted to SQLite (`data/genie_memory.db`).
Raw captures and raw context objects are NEVER written to any storage tier.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

import structlog

from ..config import Settings, get_settings
from .capture import AppInfo

log = structlog.get_logger("genie.companion.context")


@dataclass
class ScreenContext:
    """Structured representation of what's on screen right now."""
    app_name: str = "unknown"
    app_category: str = "general"          # game | ide | browser | writing | general
    window_title: str = ""
    activity: str = "idle"
    vision_context: Optional[dict] = None  # raw VisionContext dict (in-memory only)
    confidence: float = 0.0
    captured_at: float = field(default_factory=time.time)


@dataclass
class ContextState:
    """Full context state snapshot held by ContextEngine."""
    application: AppInfo = field(default_factory=lambda: AppInfo(
        process_name="unknown", process_name_stem="unknown",
        window_title="", category="general"
    ))
    screen: ScreenContext = field(default_factory=ScreenContext)
    current_mode: str = "general"          # general | gaming | coding | writing
    recent_events: list[dict] = field(default_factory=list)  # last N events
    last_companion_response: str = ""
    last_response_at: float = 0.0
    # Typing activity (for coding gate: don't interrupt active typing)
    last_keypress_at: float = 0.0
    session_start: float = field(default_factory=time.time)

    def is_user_actively_typing(self, window_seconds: float = 3.0) -> bool:
        """True if the user typed something within the last N seconds."""
        return time.time() - self.last_keypress_at < window_seconds


# ── Context Diff ──────────────────────────────────────────────────────────────

@dataclass
class ContextDelta:
    """A semantic change between two ContextState snapshots."""
    event_type: str               # e.g. "ENEMY_DETECTED", "CODE_ERROR"
    importance: str = "medium"    # low | medium | high | critical
    previous_value: Any = None
    current_value: Any = None
    mode: str = "general"
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)


def compute_context_diff(
    previous: Optional[ContextState],
    current: ContextState,
) -> list[ContextDelta]:
    """Compare two context states and return semantic deltas.

    This is the reflex layer — cheap, deterministic, no LLM.
    Identical scenes (same app, same vision entities, same activity)
    produce an EMPTY list → CompanionBrain is never called.
    """
    if previous is None:
        return []  # First observation — no meaningful diff yet

    deltas: list[ContextDelta] = []
    mode = current.current_mode
    prev_vision = previous.screen.vision_context if isinstance(previous.screen.vision_context, dict) else {}
    curr_vision = current.screen.vision_context if isinstance(current.screen.vision_context, dict) else {}

    # ── App change ────────────────────────────────────────────────────────────
    if (previous.application.process_name_stem != current.application.process_name_stem
            and current.application.process_name_stem != "unknown"):
        deltas.append(ContextDelta(
            event_type="APP_CHANGED",
            importance="medium",
            previous_value=previous.application.process_name_stem,
            current_value=current.application.process_name_stem,
            mode=mode,
        ))

    # ── Vision-based diffs (mode-specific) ────────────────────────────────────
    if not curr_vision:
        return deltas  # no vision context — only app-level diffs

    raw_prev_ents = prev_vision.get("entities", [])
    raw_curr_ents = curr_vision.get("entities", [])
    raw_prev_evts = prev_vision.get("events", [])
    raw_curr_evts = curr_vision.get("events", [])

    prev_entities = {e.get("type", ""): e for e in raw_prev_ents if isinstance(e, dict) and e.get("type")}
    curr_entities = {e.get("type", ""): e for e in raw_curr_ents if isinstance(e, dict) and e.get("type")}
    curr_events = [e for e in raw_curr_evts if isinstance(e, dict)]
    prev_event_types = {e.get("type") for e in raw_prev_evts if isinstance(e, dict) and e.get("type")}

    # ── Gaming diffs ──────────────────────────────────────────────────────────
    if mode == "gaming":
        for evt in curr_events:
            etype = evt.get("type", "")
            importance = evt.get("importance", "medium")
            if not etype:
                continue

            # Only emit if not already in previous events list
            if etype not in prev_event_types:
                deltas.append(ContextDelta(
                    event_type=_normalize_event_type(etype),
                    importance=importance,
                    current_value=evt,
                    mode=mode,
                    confidence=curr_vision.get("confidence", 0.5),
                ))

        # Entity transitions (appeared/disappeared)
        for ent_type, ent in curr_entities.items():
            if ent_type not in prev_entities and ent.get("confidence", 0) > 0.7:
                deltas.append(ContextDelta(
                    event_type=_entity_to_event(ent_type, appeared=True),
                    importance="high" if ent_type in ("enemy", "boss") else "medium",
                    current_value=ent,
                    mode=mode,
                    confidence=ent.get("confidence", 0.5),
                ))

        for ent_type in prev_entities:
            if ent_type not in curr_entities:
                deltas.append(ContextDelta(
                    event_type=_entity_to_event(ent_type, appeared=False),
                    importance="medium",
                    mode=mode,
                ))

    # ── Coding diffs ──────────────────────────────────────────────────────────
    elif mode == "coding":
        for evt in curr_events:
            etype = evt.get("type", "")
            if not etype:
                continue
            if etype not in prev_event_types:
                deltas.append(ContextDelta(
                    event_type=_normalize_event_type(etype),
                    importance=evt.get("importance", "medium"),
                    current_value=evt,
                    mode=mode,
                    confidence=curr_vision.get("confidence", 0.5),
                ))

    # ── Writing diffs ─────────────────────────────────────────────────────────
    elif mode == "writing":
        for evt in curr_events:
            etype = evt.get("type", "")
            if not etype:
                continue
            if etype not in prev_event_types:
                deltas.append(ContextDelta(
                    event_type=_normalize_event_type(etype),
                    importance="low",  # writing corrections are low-importance nudges
                    current_value=evt,
                    mode=mode,
                    confidence=curr_vision.get("confidence", 0.5),
                ))

    # ── General diffs ─────────────────────────────────────────────────────────
    else:
        for evt in curr_events:
            etype = evt.get("type", "")
            importance = evt.get("importance", "low")
            if importance in ("high", "critical") and etype:
                if etype not in prev_event_types:
                    deltas.append(ContextDelta(
                        event_type=_normalize_event_type(etype),
                        importance=importance,
                        current_value=evt,
                        mode=mode,
                    ))

    return deltas


def _normalize_event_type(raw: str) -> str:
    """Normalize vision model event type strings to our canonical event catalog."""
    mapping = {
        "enemy": "ENEMY_DETECTED",
        "enemy_detected": "ENEMY_DETECTED",
        "multiple_enemies": "MULTIPLE_ENEMIES",
        "player_killed": "PLAYER_KILL",
        "player_kill": "PLAYER_KILL",
        "player_death": "PLAYER_DEATH",
        "player_died": "PLAYER_DEATH",
        "low_health": "LOW_HEALTH",
        "health_low": "LOW_HEALTH",
        "boss": "BOSS_DETECTED",
        "boss_detected": "BOSS_DETECTED",
        "objective": "OBJECTIVE",
        "objective_completed": "OBJECTIVE_COMPLETED",
        "round_start": "ROUND_START",
        "round_win": "ROUND_WIN",
        "round_loss": "ROUND_LOSS",
        "clutch": "CLUTCH",
        "code_error": "CODE_ERROR",
        "error": "CODE_ERROR",
        "runtime_error": "RUNTIME_ERROR",
        "build_failure": "BUILD_FAILURE",
        "test_failure": "TEST_FAILURE",
        "test_success": "TEST_SUCCESS",
        "spelling_error": "SPELLING_ERROR",
        "grammar_error": "GRAMMAR_ERROR",
        "typo": "TYPO",
    }
    return mapping.get(raw.lower(), raw.upper().replace(" ", "_"))


def _entity_to_event(entity_type: str, appeared: bool) -> str:
    """Convert an entity type + transition direction to an event type."""
    if appeared:
        mapping = {
            "enemy": "ENEMY_DETECTED",
            "enemies": "MULTIPLE_ENEMIES",
            "boss": "BOSS_DETECTED",
            "health": "LOW_HEALTH",
        }
    else:
        mapping = {
            "enemy": "ENEMY_ELIMINATED",
            "boss": "BOSS_ELIMINATED",
        }
    return mapping.get(entity_type.lower(), f"{entity_type.upper()}_{'APPEARED' if appeared else 'GONE'}")


# ── ContextEngine ─────────────────────────────────────────────────────────────

class ContextEngine:
    """Owns the current context state and produces context diffs.

    Thread-safe: all state updates happen from the single observation loop task.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._current: Optional[ContextState] = None
        self._previous: Optional[ContextState] = None

    def get_current(self) -> Optional[ContextState]:
        return self._current

    def update(
        self,
        app_info: AppInfo,
        vision_context: Optional[dict],
        mode: str = "general",
    ) -> list[ContextDelta]:
        """Update context with new observation data and return semantic deltas.

        This is the reflex layer: cheap, deterministic, no LLM.
        """
        self._previous = self._current

        screen = ScreenContext(
            app_name=app_info.process_name_stem,
            app_category=app_info.category,
            window_title=app_info.window_title,
            activity=_infer_activity(app_info, vision_context),
            vision_context=vision_context,
            confidence=(vision_context or {}).get("confidence", 0.0),
        )

        new_state = ContextState(
            application=app_info,
            screen=screen,
            current_mode=mode,
            recent_events=(self._current.recent_events if self._current else []),
            last_companion_response=(
                self._current.last_companion_response if self._current else ""
            ),
            last_response_at=(self._current.last_response_at if self._current else 0.0),
        )

        self._current = new_state

        deltas = compute_context_diff(self._previous, self._current)
        return deltas

    def record_companion_response(self, text: str) -> None:
        """Record what the companion just said (for duplicate detection)."""
        if self._current:
            self._current.last_companion_response = text
            self._current.last_response_at = time.time()

    def record_event(self, event: dict) -> None:
        """Append to recent_events rolling buffer (max 20)."""
        if self._current:
            self._current.recent_events = (
                self._current.recent_events + [event]
            )[-20:]

    def snapshot(self) -> dict:
        """Diagnostic snapshot (no raw frame data)."""
        if not self._current:
            return {"status": "no_context"}
        return {
            "app": self._current.application.process_name_stem,
            "category": self._current.application.app_category,
            "mode": self._current.current_mode,
            "activity": self._current.screen.activity,
            "vision_confidence": self._current.screen.confidence,
        }


def _infer_activity(app_info: AppInfo, vision_context: Optional[dict]) -> str:
    """Infer a short activity string from app + vision data."""
    if vision_context and isinstance(vision_context, dict):
        scene = vision_context.get("scene", {})
        if isinstance(scene, dict):
            activity = scene.get("activity", "")
            if isinstance(activity, str) and activity and activity != "unknown":
                return activity
        elif isinstance(scene, str) and scene and scene != "unknown":
            return scene

    cat = app_info.category
    if cat == "game":
        return "playing"
    elif cat == "ide":
        return "coding"
    elif cat == "writing":
        return "writing"
    elif cat == "browser":
        return "browsing"
    return "working"
