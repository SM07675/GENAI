"""
Session-level Metrics.

Collects real-time latency and quality metrics for a single voice session.
Used by the test page and future monitoring dashboards.

Tracked metrics per turn
------------------------
stt_latency_ms           – Time from speech_ended to final transcript
first_token_latency_ms   – Time from transcript to first AI token
first_audio_latency_ms   – Time from transcript to first TTS audio chunk
total_turn_ms            – End-to-end turn duration
interrupt_count          – Barge-in interruptions in this session
error_count              – Total errors (STT/TTS/AI/WebSocket)
turns_completed          – Completed (non-interrupted) AI turns
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TurnMetrics:
    """Latency measurements for a single voice turn."""
    turn_id: int
    stt_start: float = 0.0
    stt_end: float = 0.0
    first_token: float = 0.0
    first_audio: float = 0.0
    turn_end: float = 0.0
    was_interrupted: bool = False

    @property
    def stt_latency_ms(self) -> float:
        if self.stt_end and self.stt_start:
            return (self.stt_end - self.stt_start) * 1000
        return 0.0

    @property
    def first_token_latency_ms(self) -> float:
        if self.first_token and self.stt_end:
            return (self.first_token - self.stt_end) * 1000
        return 0.0

    @property
    def first_audio_latency_ms(self) -> float:
        if self.first_audio and self.stt_end:
            return (self.first_audio - self.stt_end) * 1000
        return 0.0

    @property
    def total_turn_ms(self) -> float:
        if self.turn_end and self.stt_start:
            return (self.turn_end - self.stt_start) * 1000
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "stt_latency_ms": round(self.stt_latency_ms, 1),
            "first_token_latency_ms": round(self.first_token_latency_ms, 1),
            "first_audio_latency_ms": round(self.first_audio_latency_ms, 1),
            "total_turn_ms": round(self.total_turn_ms, 1),
            "was_interrupted": self.was_interrupted,
        }


class CommunicationMetrics:
    """Session-level metrics collector.

    Usage::

        metrics = CommunicationMetrics(session_id="abc")

        # At speech_ended:
        metrics.start_stt()

        # At transcript ready:
        metrics.end_stt()

        # At first AI token:
        metrics.record_first_token()

        # At first TTS audio:
        metrics.record_first_audio()

        # At turn complete:
        metrics.end_turn(interrupted=False)

        # Get current snapshot:
        data = metrics.snapshot()
    """

    def __init__(self, session_id: str) -> None:
        self._session_id = session_id
        self._turn_id = 0
        self._current: TurnMetrics | None = None
        self._history: list[TurnMetrics] = []
        self._interrupt_count = 0
        self._error_count = 0
        self._session_start = time.monotonic()

    # ── Turn lifecycle ────────────────────────────────────────────

    def start_stt(self) -> None:
        """Mark the start of STT processing (speech_ended event)."""
        self._turn_id += 1
        self._current = TurnMetrics(turn_id=self._turn_id, stt_start=time.monotonic())

    def end_stt(self) -> None:
        """Mark the end of STT (transcript ready)."""
        if self._current:
            self._current.stt_end = time.monotonic()

    def record_first_token(self) -> None:
        """Mark arrival of the first AI response token."""
        if self._current and not self._current.first_token:
            self._current.first_token = time.monotonic()

    def record_first_audio(self) -> None:
        """Mark dispatch of the first TTS audio chunk."""
        if self._current and not self._current.first_audio:
            self._current.first_audio = time.monotonic()

    def end_turn(self, interrupted: bool = False) -> None:
        """Mark end of a full turn and archive the metrics."""
        if self._current:
            self._current.turn_end = time.monotonic()
            self._current.was_interrupted = interrupted
            self._history.append(self._current)
            self._current = None

    def record_interrupt(self) -> None:
        self._interrupt_count += 1

    def record_error(self) -> None:
        self._error_count += 1

    # ── Snapshot ──────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """Return current session metrics as a dict."""
        session_duration_s = time.monotonic() - self._session_start

        last_turn = self._history[-1].to_dict() if self._history else {}

        avg_stt = 0.0
        avg_first_token = 0.0
        avg_first_audio = 0.0
        if self._history:
            n = len(self._history)
            avg_stt = sum(t.stt_latency_ms for t in self._history) / n
            avg_first_token = sum(t.first_token_latency_ms for t in self._history) / n
            avg_first_audio = sum(t.first_audio_latency_ms for t in self._history) / n

        return {
            "session_id": self._session_id,
            "session_duration_s": round(session_duration_s, 1),
            "turns_completed": len(self._history),
            "interrupt_count": self._interrupt_count,
            "error_count": self._error_count,
            "current_turn": self._current.to_dict() if self._current else None,
            "last_turn": last_turn,
            "avg_stt_latency_ms": round(avg_stt, 1),
            "avg_first_token_latency_ms": round(avg_first_token, 1),
            "avg_first_audio_latency_ms": round(avg_first_audio, 1),
        }
