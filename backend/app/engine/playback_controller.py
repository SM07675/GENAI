"""Playback Controller — tracks frontend audio state.

Manages the lifecycle of audio playback on the frontend:
- Tracks which chunks have been sent
- Handles interrupt signals (stops playback instantly)
- Waits for ``playback_complete`` from frontend before transitioning
- Timeout protection: force-transitions if frontend doesn't report completion
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional

import structlog

log = structlog.get_logger("genie.engine.playback")

Emitter = Callable[[dict], Awaitable[None]]

# Max time to wait for frontend's playback_complete before force-transitioning
PLAYBACK_TIMEOUT_S = 60.0


class PlaybackController:
    """Tracks frontend audio playback state.

    The conversation engine creates a PlaybackController for each turn
    that produces audio. The controller waits for the frontend to
    confirm playback is complete before the engine transitions to
    the next state.
    """

    def __init__(self, emit: Emitter):
        self._emit = emit
        self._playback_complete = asyncio.Event()
        self._interrupted = False
        self._chunks_sent = 0

    def record_chunk_sent(self) -> None:
        """Record that an audio chunk was sent to the frontend."""
        self._chunks_sent += 1

    async def interrupt(self) -> None:
        """Send interrupt signal to frontend — stops audio instantly."""
        self._interrupted = True
        self._playback_complete.set()
        await self._emit({"type": "interrupt"})
        log.info("playback_interrupted", chunks_sent=self._chunks_sent)

    def on_playback_complete(self) -> None:
        """Called when frontend reports playback is done."""
        self._playback_complete.set()
        log.info("playback_complete_received", chunks_sent=self._chunks_sent)

    async def wait_for_completion(self, timeout: float = PLAYBACK_TIMEOUT_S) -> bool:
        """Wait for frontend to confirm playback completion.

        Returns True if playback completed normally, False on timeout.
        """
        if self._chunks_sent == 0:
            return True

        try:
            await asyncio.wait_for(self._playback_complete.wait(), timeout=timeout)
            return not self._interrupted
        except asyncio.TimeoutError:
            log.warning("playback_timeout", timeout=timeout, chunks=self._chunks_sent)
            return False

    @property
    def was_interrupted(self) -> bool:
        return self._interrupted

    @property
    def chunks_sent(self) -> int:
        return self._chunks_sent
