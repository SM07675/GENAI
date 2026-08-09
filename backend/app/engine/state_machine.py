"""Typed finite state machine for the Genie voice pipeline.

Design:
- Exactly 8 states matching the production spec.
- Transitions are declarative — defined once, enforced everywhere.
- Async-safe writes via ``asyncio.Lock``.
- Thread-safe reads: ``state`` is an atomic enum read.
- Lock is RELEASED before callbacks fire (prevents re-entrant deadlock).
- Per-state timeout config for watchdog integration.
- Full circular history for diagnostics.
"""
from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Any, Awaitable, Callable, Optional

import structlog

log = structlog.get_logger("genie.engine.state_machine")


# ═══════════════════════════════════════════════════════════════════════════════
# STATES
# ═══════════════════════════════════════════════════════════════════════════════

class EngineState(str, Enum):
    """All possible states of the voice pipeline.

    The pipeline follows this cycle:
        IDLE → WAIT_WAKE → LISTENING → UNDERSTANDING → THINKING
             → STREAMING_RESPONSE → SPEAKING → RETURN_TO_LISTENING → WAIT_WAKE
    """
    IDLE = "idle"
    WAIT_WAKE = "wait_wake"
    LISTENING = "listening"
    UNDERSTANDING = "understanding"
    THINKING = "thinking"
    STREAMING_RESPONSE = "streaming_response"
    SPEAKING = "speaking"
    RETURN_TO_LISTENING = "return_to_listening"


# ═══════════════════════════════════════════════════════════════════════════════
# TRANSITIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Valid transitions: current_state → set of allowed next states.
TRANSITIONS: dict[EngineState, set[EngineState]] = {
    EngineState.IDLE: {
        EngineState.WAIT_WAKE,
        EngineState.LISTENING,
        EngineState.THINKING,
    },
    EngineState.WAIT_WAKE: {
        EngineState.LISTENING,       # wake word or manual wake
        EngineState.UNDERSTANDING,   # manual audio input
        EngineState.THINKING,        # text input / manual message submission
        EngineState.IDLE,            # shutdown
    },
    EngineState.LISTENING: {
        EngineState.UNDERSTANDING,   # speech captured
        EngineState.THINKING,        # text input while listening
        EngineState.WAIT_WAKE,       # silence timeout, no speech
        EngineState.IDLE,            # shutdown
    },
    EngineState.UNDERSTANDING: {
        EngineState.THINKING,        # transcript ready
        EngineState.LISTENING,       # empty/cancelled transcript → re-listen
        EngineState.WAIT_WAKE,       # cancelled, return to wake
        EngineState.IDLE,
    },
    EngineState.THINKING: {
        EngineState.STREAMING_RESPONSE,  # LLM starts generating
        EngineState.LISTENING,           # barge-in interrupt
        EngineState.WAIT_WAKE,           # error/cancel
        EngineState.IDLE,
    },
    EngineState.STREAMING_RESPONSE: {
        EngineState.SPEAKING,        # first audio chunk ready
        EngineState.LISTENING,       # barge-in interrupt
        EngineState.WAIT_WAKE,       # no TTS output (text-only response)
        EngineState.RETURN_TO_LISTENING,  # response done, no audio
        EngineState.IDLE,
    },
    EngineState.SPEAKING: {
        EngineState.RETURN_TO_LISTENING,  # playback complete
        EngineState.LISTENING,           # barge-in interrupt
        EngineState.WAIT_WAKE,           # error
        EngineState.IDLE,
    },
    EngineState.RETURN_TO_LISTENING: {
        EngineState.LISTENING,       # follow-up mode (immediate re-listen)
        EngineState.WAIT_WAKE,       # no follow-up, return to wake
        EngineState.IDLE,
    },
}

# Per-state maximum time (seconds) before watchdog forces recovery.
# States with None have no automatic timeout.
STATE_TIMEOUTS: dict[EngineState, Optional[float]] = {
    EngineState.IDLE: None,
    EngineState.WAIT_WAKE: None,           # can wait forever
    EngineState.LISTENING: 30.0,           # max 30s listening
    EngineState.UNDERSTANDING: 30.0,       # STT should finish in 30s
    EngineState.THINKING: 60.0,            # LLM should respond in 60s
    EngineState.STREAMING_RESPONSE: 90.0,  # streaming can take a while
    EngineState.SPEAKING: 120.0,           # long responses
    EngineState.RETURN_TO_LISTENING: 5.0,  # should transition quickly
}

# States where barge-in (interruption) is allowed.
BARGEIN_STATES: frozenset[EngineState] = frozenset({
    EngineState.THINKING,
    EngineState.STREAMING_RESPONSE,
    EngineState.SPEAKING,
})

# States where the mic should be feeding the wake detector.
WAKE_DETECTION_STATES: frozenset[EngineState] = frozenset({
    EngineState.WAIT_WAKE,
})

# States where VAD speech detection is active.
VAD_ACTIVE_STATES: frozenset[EngineState] = frozenset({
    EngineState.LISTENING,
    EngineState.SPEAKING,   # for barge-in detection
})

# States considered "active processing" (for diagnostics).
ACTIVE_STATES: frozenset[EngineState] = frozenset({
    EngineState.LISTENING,
    EngineState.UNDERSTANDING,
    EngineState.THINKING,
    EngineState.STREAMING_RESPONSE,
    EngineState.SPEAKING,
})


# ═══════════════════════════════════════════════════════════════════════════════
# CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════════

# Callback signature: (old_state, new_state, reason) → awaitable
StateCallback = Callable[[EngineState, EngineState, str], Awaitable[None]]


# ═══════════════════════════════════════════════════════════════════════════════
# STATE HISTORY
# ═══════════════════════════════════════════════════════════════════════════════

class StateHistory:
    """Circular buffer of recent state transitions for debugging."""

    __slots__ = ("_entries", "_max_size")

    def __init__(self, max_size: int = 200):
        self._entries: list[dict[str, Any]] = []
        self._max_size = max_size

    def record(self, old: EngineState, new: EngineState, reason: str, forced: bool = False) -> None:
        entry = {
            "from": old.value,
            "to": new.value,
            "reason": reason,
            "forced": forced,
            "ts": time.time(),
        }
        self._entries.append(entry)
        if len(self._entries) > self._max_size:
            # Keep the recent half
            self._entries = self._entries[-(self._max_size // 2):]

    @property
    def recent(self) -> list[dict[str, Any]]:
        return self._entries[-30:]

    @property
    def last(self) -> Optional[dict[str, Any]]:
        return self._entries[-1] if self._entries else None

    @property
    def all_entries(self) -> list[dict[str, Any]]:
        return list(self._entries)


# ═══════════════════════════════════════════════════════════════════════════════
# STATE MACHINE
# ═══════════════════════════════════════════════════════════════════════════════

class ConversationStateMachine:
    """Finite state machine for the voice pipeline.

    Thread-safe for reads (``state`` property is an atomic enum read).
    Async-safe for writes (``transition()`` acquires a lock, releases it
    BEFORE callbacks fire to prevent re-entrant deadlock).

    Created once. Never destroyed. Never recreated.
    """

    def __init__(self) -> None:
        self._state: EngineState = EngineState.IDLE
        self._lock = asyncio.Lock()
        self._history = StateHistory()

        # Callbacks
        self._on_enter: dict[EngineState, list[StateCallback]] = {}
        self._on_exit: dict[EngineState, list[StateCallback]] = {}
        self._on_any: list[StateCallback] = []

        # Timing
        self._state_entered_at: float = time.time()
        self._transition_count: int = 0

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def state(self) -> EngineState:
        """Current state — atomic enum read, safe from any thread."""
        return self._state

    @property
    def history(self) -> StateHistory:
        return self._history

    @property
    def time_in_state(self) -> float:
        """Seconds spent in the current state."""
        return time.time() - self._state_entered_at

    @property
    def state_entered_at(self) -> float:
        return self._state_entered_at

    @property
    def transition_count(self) -> int:
        return self._transition_count

    # ── Transition ────────────────────────────────────────────────────────

    async def transition(
        self,
        new_state: EngineState,
        reason: str = "",
    ) -> bool:
        """Attempt a validated state transition.

        Returns True if the transition was accepted, False if rejected.
        Callbacks fire AFTER the lock is released (no re-entrant deadlock).
        """
        callbacks_to_fire: list[tuple[StateCallback, EngineState, EngineState, str]] = []

        async with self._lock:
            old = self._state
            if new_state == old:
                return True  # no-op

            allowed = TRANSITIONS.get(old, set())
            if new_state not in allowed:
                log.warning(
                    "state_transition_rejected",
                    current=old.value,
                    requested=new_state.value,
                    reason=reason,
                    allowed=[s.value for s in allowed],
                )
                return False

            # Collect callbacks to fire
            callbacks_to_fire = self._collect_callbacks(old, new_state, reason)

            # Update state atomically
            self._state = new_state
            self._state_entered_at = time.time()
            self._transition_count += 1
            self._history.record(old, new_state, reason, forced=False)

            log.info(
                "state_transition",
                old=old.value,
                new=new_state.value,
                reason=reason,
            )

        # Fire callbacks OUTSIDE the lock
        await self._fire_callbacks(callbacks_to_fire)
        return True

    async def force_transition(
        self,
        new_state: EngineState,
        reason: str = "",
    ) -> None:
        """Force a transition regardless of validity (for recovery/barge-in).

        Use sparingly — only for error recovery and interrupts.
        """
        callbacks_to_fire: list[tuple[StateCallback, EngineState, EngineState, str]] = []

        async with self._lock:
            old = self._state
            if new_state == old:
                return

            callbacks_to_fire = self._collect_callbacks(old, new_state, reason)

            self._state = new_state
            self._state_entered_at = time.time()
            self._transition_count += 1
            self._history.record(old, new_state, reason, forced=True)

            log.warning(
                "state_transition_forced",
                old=old.value,
                new=new_state.value,
                reason=reason,
            )

        # Fire callbacks OUTSIDE the lock
        await self._fire_callbacks(callbacks_to_fire)

    def _collect_callbacks(
        self,
        old: EngineState,
        new: EngineState,
        reason: str,
    ) -> list[tuple[StateCallback, EngineState, EngineState, str]]:
        """Collect all callbacks that need to fire for this transition.

        Called while holding the lock. Returns a list of
        (callback, old_state, new_state, reason) tuples.
        """
        result: list[tuple[StateCallback, EngineState, EngineState, str]] = []
        for cb in self._on_exit.get(old, []):
            result.append((cb, old, new, reason))
        for cb in self._on_enter.get(new, []):
            result.append((cb, old, new, reason))
        for cb in self._on_any:
            result.append((cb, old, new, reason))
        return result

    async def _fire_callbacks(
        self,
        callbacks: list[tuple[StateCallback, EngineState, EngineState, str]],
    ) -> None:
        """Fire callbacks outside the lock. Each callback is isolated."""
        for cb, old, new, reason in callbacks:
            try:
                await cb(old, new, reason)
            except Exception as e:
                log.error(
                    "state_callback_error",
                    old=old.value,
                    new=new.value,
                    reason=reason,
                    error=str(e),
                    exc_info=True,
                )

    # ── Callback Registration ─────────────────────────────────────────────

    def on_enter(self, state: EngineState, callback: StateCallback) -> None:
        """Register a callback that fires when entering ``state``."""
        self._on_enter.setdefault(state, []).append(callback)

    def on_exit(self, state: EngineState, callback: StateCallback) -> None:
        """Register a callback that fires when exiting ``state``."""
        self._on_exit.setdefault(state, []).append(callback)

    def on_transition(self, callback: StateCallback) -> None:
        """Register a callback that fires on every transition."""
        self._on_any.append(callback)

    # ── Query helpers ─────────────────────────────────────────────────────

    def is_active(self) -> bool:
        """True if the engine is in an active processing state."""
        return self._state in ACTIVE_STATES

    def allows_bargein(self) -> bool:
        """True if the current state allows user interruption."""
        return self._state in BARGEIN_STATES

    def is_vad_active(self) -> bool:
        """True if VAD should be processing frames."""
        return self._state in VAD_ACTIVE_STATES

    def is_wake_active(self) -> bool:
        """True if wake word detection should be processing frames."""
        return self._state in WAKE_DETECTION_STATES

    def can_transition_to(self, target: EngineState) -> bool:
        """Check if a transition to ``target`` would be valid."""
        return target in TRANSITIONS.get(self._state, set())

    def get_state_timeout(self) -> Optional[float]:
        """Get the timeout for the current state (None = no timeout)."""
        return STATE_TIMEOUTS.get(self._state)

    # ── Diagnostics ───────────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """Return a diagnostic snapshot."""
        return {
            "state": self._state.value,
            "time_in_state": round(self.time_in_state, 2),
            "transition_count": self._transition_count,
            "recent_history": self._history.recent,
            "allows_bargein": self.allows_bargein(),
            "is_active": self.is_active(),
        }
