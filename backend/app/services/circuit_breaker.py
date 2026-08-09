"""Generic circuit breaker for external provider calls.

States
------
  CLOSED  — normal operation; requests pass through.
  OPEN    — too many consecutive failures; requests fail fast.
  HALF_OPEN — cooldown elapsed; one probe request allowed to test recovery.

Usage
-----
    from .services.circuit_breaker import CircuitBreaker

    _cb = CircuitBreaker(name="elevenlabs", failure_threshold=3, cooldown_seconds=60)

    async def call_elevenlabs():
        if not _cb.allow_request():
            raise RuntimeError("ElevenLabs circuit open — skipping")
        try:
            result = await _actual_call()
            _cb.record_success()
            return result
        except Exception as e:
            _cb.record_failure()
            raise
"""
from __future__ import annotations

import logging
import time
from enum import Enum

log = logging.getLogger("genie.circuit_breaker")


class CBState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Thread-safe (GIL-protected) per-provider circuit breaker."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds

        self._state: CBState = CBState.CLOSED
        self._failures: int = 0
        self._opened_at: float = 0.0
        self._current_cooldown: float = cooldown_seconds

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def state(self) -> CBState:
        self._maybe_transition_to_half_open()
        return self._state

    def allow_request(self) -> bool:
        """Return True if a request is allowed through right now."""
        self._maybe_transition_to_half_open()
        if self._state == CBState.CLOSED:
            return True
        if self._state == CBState.HALF_OPEN:
            return True   # one probe allowed
        # OPEN
        return False

    def record_success(self) -> None:
        """Call after a successful external call; resets failure counter."""
        if self._state != CBState.CLOSED:
            log.info("[%s] Circuit recovering → CLOSED (success probe)", self.name)
        self._failures = 0
        self._state = CBState.CLOSED
        self._current_cooldown = self.cooldown_seconds

    def record_failure(self) -> None:
        """Call after a failed external call; may trip the circuit."""
        self._failures += 1
        self._current_cooldown = self.cooldown_seconds
        if self._state == CBState.HALF_OPEN:
            # Probe failed → stay open, reset cooldown
            self._state = CBState.OPEN
            self._opened_at = time.monotonic()
            log.warning("[%s] Probe failed → OPEN (cooldown reset)", self.name)
            return
        if self._failures >= self.failure_threshold:
            self._state = CBState.OPEN
            self._opened_at = time.monotonic()
            log.warning(
                "[%s] Circuit tripped → OPEN after %d failures",
                self.name,
                self._failures,
            )

    def force_open(self, cooldown_seconds: float) -> None:
        """Manually trip the circuit with a specific cooldown (e.g. Retry-After)."""
        self._state = CBState.OPEN
        self._opened_at = time.monotonic()
        self._current_cooldown = cooldown_seconds
        self._failures = self.failure_threshold
        log.warning("[%s] Circuit forced OPEN for %s seconds", self.name, cooldown_seconds)

    def status_dict(self) -> dict:
        """Serializable status for the /apis/status endpoint."""
        return {
            "circuit": self.name,
            "state": self.state.value,
            "failures": self._failures,
            "threshold": self.failure_threshold,
            "cooldown_seconds": self._current_cooldown,
            "seconds_until_probe": max(
                0,
                self._current_cooldown - (time.monotonic() - self._opened_at)
            ) if self._state == CBState.OPEN else 0,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _maybe_transition_to_half_open(self) -> None:
        if self._state == CBState.OPEN:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self._current_cooldown:
                self._state = CBState.HALF_OPEN
                log.info(
                    "[%s] Cooldown elapsed → HALF_OPEN (sending probe)",
                    self.name,
                )


# ------------------------------------------------------------------
# Module-level singletons for each provider
# ------------------------------------------------------------------

_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 3,
    cooldown_seconds: float = 60.0,
) -> CircuitBreaker:
    """Return the named circuit breaker, creating it if needed."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            cooldown_seconds=cooldown_seconds,
        )
    return _circuit_breakers[name]


def all_circuit_breaker_statuses() -> list[dict]:
    """Snapshot of all breaker states for the health/status endpoint."""
    return [cb.status_dict() for cb in _circuit_breakers.values()]


# Pre-instantiated subsystem circuit breakers for error recovery parity
stt_circuit_breaker = get_circuit_breaker("stt_service", failure_threshold=3, cooldown_seconds=30.0)
tts_circuit_breaker = get_circuit_breaker("tts_service", failure_threshold=3, cooldown_seconds=30.0)
tool_circuit_breaker = get_circuit_breaker("tool_execution", failure_threshold=4, cooldown_seconds=45.0)
