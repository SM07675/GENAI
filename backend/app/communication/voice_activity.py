"""
Voice Activity Detection (VAD).

Wraps Google's WebRTC VAD (webrtcvad) to detect speech vs. silence/noise
in a stream of 16kHz, 16-bit mono PCM audio frames.

Design decisions
----------------
• Frame smoothing via a ring buffer prevents single-frame false positives
  (keyboard click, HVAC spike, etc.) from triggering speech detection.
• A configurable silence threshold (default 800 ms) determines when to emit
  ``speech_ended`` after the last speech frame.
• The VAD operates on 30 ms frames by default (480 samples @ 16 kHz).
• Events are delivered through an asyncio.Queue to keep the VAD loop
  non-blocking.

VAD Events
----------
VADEvent.SPEECH_STARTED  – transition from silence to speech
VADEvent.SPEECH_ENDED    – silence exceeded threshold after speech
VADEvent.SILENCE         – continuous silence (no active speech)
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from typing import AsyncIterator

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# webrtcvad import is optional at module level so unit tests can import without it
try:
    import webrtcvad as _webrtcvad  # type: ignore[import-untyped]
    _WEBRTCVAD_AVAILABLE = True
except ImportError:
    _webrtcvad = None
    _WEBRTCVAD_AVAILABLE = False
    logger.warning("webrtcvad not installed — VAD will use energy-based fallback")


class VADEvent(Enum):
    """Events emitted by the VoiceActivityDetector."""
    SPEECH_STARTED = auto()
    SPEECH_ENDED = auto()
    SILENCE = auto()


@dataclass
class VADResult:
    """Result of processing a single audio frame."""
    event: VADEvent | None
    is_speech: bool
    timestamp_ms: float


class VoiceActivityDetector:
    """Detects speech start/end in a PCM audio stream.

    Args:
        session_id: Used for logging context.
        aggressiveness: WebRTC VAD aggressiveness 0–3 (higher = more aggressive
                        noise rejection; may cut quiet speech).
        silence_threshold_ms: Milliseconds of silence before ``SPEECH_ENDED`` fires.
        min_speech_ms: Minimum speech duration to be considered valid.
        frame_ms: Frame duration in milliseconds (10, 20, or 30).
        sample_rate: Must be 8000, 16000, 32000, or 48000 Hz.
        smoothing_frames: Number of frames used in the ring-buffer smoother.

    Usage::

        vad = VoiceActivityDetector(session_id="abc")
        async for result in vad.process(audio_handler.frames()):
            if result.event == VADEvent.SPEECH_STARTED:
                ...
    """

    SAMPLE_RATE = 16_000

    def __init__(
        self,
        session_id: str,
        aggressiveness: int = 2,
        silence_threshold_ms: int = 800,
        min_speech_ms: int = 250,
        frame_ms: int = 30,
        smoothing_frames: int = 5,
    ) -> None:
        self._session_id = session_id
        self._aggressiveness = aggressiveness
        self._silence_threshold_ms = silence_threshold_ms
        self._min_speech_ms = min_speech_ms
        self._frame_ms = frame_ms
        self._smoothing_frames = smoothing_frames

        # State
        self._in_speech = False
        self._speech_start_ms: float | None = None
        self._last_speech_ms: float | None = None
        self._ring: deque[bool] = deque(maxlen=smoothing_frames)
        self._frame_count = 0

        # Init VAD backend
        self._vad = self._create_vad(aggressiveness)

    def _create_vad(self, aggressiveness: int):  # type: ignore[return]
        """Initialise the VAD backend."""
        if _WEBRTCVAD_AVAILABLE:
            vad = _webrtcvad.Vad(aggressiveness)
            logger.info("WebRTC VAD initialised", aggressiveness=aggressiveness)
            return vad
        logger.info("Using energy-based VAD fallback")
        return None

    def _is_speech_frame(self, frame: bytes) -> bool:
        """Return True if the frame contains speech."""
        if self._vad is not None:
            try:
                return self._vad.is_speech(frame, self.SAMPLE_RATE)
            except Exception:
                pass  # fall through to energy fallback

        # Energy-based fallback: RMS above a simple threshold
        import struct
        samples = struct.unpack(f"{len(frame) // 2}h", frame)
        rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
        return rms > 300  # empirical threshold for 16-bit PCM

    async def process(
        self, frames: AsyncIterator[bytes]
    ) -> AsyncIterator[VADResult]:
        """Async generator that processes audio frames and emits VAD results.

        Yields a ``VADResult`` for every frame. Only frames with an event
        (SPEECH_STARTED, SPEECH_ENDED) have a non-None ``event`` field.
        """
        elapsed_ms = 0.0

        async for frame in frames:
            raw_speech = self._is_speech_frame(frame)
            self._ring.append(raw_speech)
            self._frame_count += 1
            elapsed_ms += self._frame_ms

            # Smooth: majority vote in ring buffer
            speech_votes = sum(self._ring)
            is_speech = speech_votes > (len(self._ring) / 2)

            now_ms = elapsed_ms
            event: VADEvent | None = None

            if is_speech:
                self._last_speech_ms = now_ms
                if not self._in_speech:
                    self._in_speech = True
                    self._speech_start_ms = now_ms
                    event = VADEvent.SPEECH_STARTED
                    logger.debug(
                        "Speech started",
                        session_id=self._session_id,
                        at_ms=round(now_ms, 1),
                    )
            else:
                if self._in_speech and self._last_speech_ms is not None:
                    silence_duration = now_ms - self._last_speech_ms
                    if silence_duration >= self._silence_threshold_ms:
                        speech_duration = (
                            self._last_speech_ms - (self._speech_start_ms or 0)
                        )
                        self._in_speech = False

                        if speech_duration >= self._min_speech_ms:
                            event = VADEvent.SPEECH_ENDED
                            logger.debug(
                                "Speech ended",
                                session_id=self._session_id,
                                speech_ms=round(speech_duration, 1),
                                silence_ms=round(silence_duration, 1),
                            )
                        else:
                            # Too short — treat as noise
                            logger.debug(
                                "Speech too short, ignoring",
                                session_id=self._session_id,
                                duration_ms=round(speech_duration, 1),
                            )
                        self._speech_start_ms = None
                        self._last_speech_ms = None
                else:
                    event = VADEvent.SILENCE

            yield VADResult(event=event, is_speech=is_speech, timestamp_ms=elapsed_ms)

    def reset(self) -> None:
        """Reset internal state (e.g. after an interruption)."""
        self._in_speech = False
        self._speech_start_ms = None
        self._last_speech_ms = None
        self._ring.clear()
        self._frame_count = 0

    @property
    def is_in_speech(self) -> bool:
        """True if currently inside a detected speech segment."""
        return self._in_speech
