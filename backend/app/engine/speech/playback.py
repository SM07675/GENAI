"""Playback tracker — tracks audio chunks sent to the frontend.

Design:
- Actually counts chunks sent (fixing bug #33 from the audit).
- Per-turn playback state tracking.
- Timeout protection: force-complete after 60s.
- Supports interruption signaling.
"""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Optional

import structlog

from ..event_bus import PipelineEvent, engine_events
from ..metrics import pipeline_metrics

log = structlog.get_logger("genie.engine.speech.playback")


class PlaybackTracker:
    """Tracks playback state for a single turn.

    The pipeline supervisor creates a new PlaybackTracker for each turn.
    The tracker:
    - Counts audio chunks sent to the frontend
    - Waits for the frontend's playback_complete message
    - Handles timeout if the frontend doesn't respond
    - Signals interruption
    """

    def __init__(self, playback_timeout: float = 60.0):
        self._playback_timeout = playback_timeout
        self._chunks_sent = 0
        self._bytes_sent = 0
        self._playback_started_at = 0.0
        self._playback_complete = asyncio.Event()
        self._interrupted = False
        self._last_heartbeat = time.time()

    # ── Chunk Tracking ────────────────────────────────────────────────────

    def record_chunk_sent(self, size_bytes: int = 0) -> None:
        """Record that an audio chunk was sent to the frontend.

        IMPORTANT: This method MUST be called for every chunk sent.
        (Fixing audit bug #33 where chunks_sent was always 0.)
        """
        self._chunks_sent += 1
        self._bytes_sent += size_bytes
        if self._chunks_sent == 1:
            self._playback_started_at = time.time()
        self._last_heartbeat = time.time()

    @property
    def chunks_sent(self) -> int:
        return self._chunks_sent

    @property
    def has_audio(self) -> bool:
        """True if any audio was sent for this turn."""
        return self._chunks_sent > 0

    # ── Playback Complete ─────────────────────────────────────────────────

    def mark_playback_complete(self) -> None:
        """Called when the frontend reports playback is done."""
        self._playback_complete.set()
        if self._playback_started_at > 0:
            duration = time.time() - self._playback_started_at
            pipeline_metrics.record_latency(
                "playback.duration", duration * 1000,
                chunks=self._chunks_sent,
            )

    async def wait_for_playback(self) -> bool:
        """Wait for the frontend to report playback complete.

        Returns True if playback completed normally, False if timed out
        or was interrupted.
        """
        if not self.has_audio:
            return True

        try:
            await asyncio.wait_for(
                self._playback_complete.wait(),
                timeout=self._playback_timeout,
            )
            return not self._interrupted
        except asyncio.TimeoutError:
            log.warning(
                "playback_timeout",
                chunks_sent=self._chunks_sent,
                timeout=self._playback_timeout,
            )
            pipeline_metrics.increment("playback.timeouts")
            return False

    # ── Interruption ──────────────────────────────────────────────────────

    def interrupt(self) -> None:
        """Interrupt playback (barge-in)."""
        self._interrupted = True
        self._playback_complete.set()  # unblock any waiter
        pipeline_metrics.increment("playback.interruptions")

    @property
    def is_interrupted(self) -> bool:
        return self._interrupted

    @property
    def is_complete(self) -> bool:
        return self._playback_complete.is_set()

    # ── Diagnostics ───────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        return {
            "chunks_sent": self._chunks_sent,
            "bytes_sent": self._bytes_sent,
            "interrupted": self._interrupted,
            "complete": self._playback_complete.is_set(),
        }

    @property
    def heartbeat(self) -> float:
        return self._last_heartbeat
