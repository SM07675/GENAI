"""Wake word detector — async worker processing frames from the microphone.

Design:
- Vosk model loaded ONCE at startup, cached globally.
- Processes frames as an async worker (not on the capture thread).
- Configurable confidence threshold + cooldown between detections.
- Supports: "Hey Genie", "Hello Genie", "Genie", "Okay Genie".
- Auto-restart after every conversation end.
- State-aware: only active when pipeline is in WAIT_WAKE state.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Optional

import structlog

from ..event_bus import PipelineEvent, engine_events
from ..metrics import pipeline_metrics

log = structlog.get_logger("genie.engine.wake")

# Global Vosk model cache — loaded once per process
_vosk_model_cache = None
_vosk_model_loaded = False


def _load_vosk_model():
    """Load the Vosk model (once)."""
    global _vosk_model_cache, _vosk_model_loaded
    if _vosk_model_loaded:
        return _vosk_model_cache

    try:
        from vosk import Model
        _vosk_model_cache = Model(model_name="vosk-model-small-en-us-0.15")
        _vosk_model_loaded = True
        log.info("vosk_model_loaded")
        return _vosk_model_cache
    except ImportError:
        log.warning("vosk_not_installed")
        _vosk_model_loaded = True
        return None
    except Exception as exc:
        log.warning("vosk_model_load_failed", error=str(exc))
        _vosk_model_loaded = True
        return None


class WakeDetector:
    """Async wake word detector that processes frames on demand.

    The pipeline supervisor feeds frames to ``process_frame()`` when
    the pipeline is in WAIT_WAKE state. When a wake word is detected,
    an event is emitted on the engine event bus.
    """

    DEFAULT_KEYWORDS = [
        "genie", "hey genie", "okay genie", "ok genie",
        "hi genie", "hello genie", "wake up",
    ]

    def __init__(
        self,
        keywords: list[str] | None = None,
        cooldown_s: float = 1.5,
        confidence_threshold: float = 0.6,
        sample_rate: int = 16000,
    ):
        self.keywords = keywords or self.DEFAULT_KEYWORDS
        self.cooldown_s = cooldown_s
        self.confidence_threshold = confidence_threshold
        self.sample_rate = sample_rate

        self._rec = None
        self._enabled = True
        self._cooldown_until: float = 0.0
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_heartbeat = time.time()

        # Stats
        self._total_detections = 0
        self._total_frames_processed = 0

    # ══════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════════════════════

    async def start(self, frames_queue: asyncio.Queue) -> bool:
        """Initialize recognizer and start the worker loop."""
        model = await asyncio.to_thread(_load_vosk_model)
        if model is None:
            log.warning("wake_detector_disabled", reason="no_vosk_model")
            return False

        try:
            from vosk import KaldiRecognizer
            grammar = json.dumps(self.keywords + ["[unk]"])
            self._rec = KaldiRecognizer(model, self.sample_rate, grammar)
        except Exception as exc:
            log.error("wake_recognizer_init_failed", error=str(exc))
            return False

        self._running = True
        self._cooldown_until = 0.0
        self._task = asyncio.create_task(self._run(frames_queue))
        log.info("wake_detector_started", keywords=self.keywords)
        return True

    async def stop(self) -> None:
        """Stop the wake detector."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self._rec = None
        log.info(
            "wake_detector_stopped",
            total_detections=self._total_detections,
            total_frames=self._total_frames_processed,
        )

    # ══════════════════════════════════════════════════════════════════════
    # MAIN LOOP
    # ══════════════════════════════════════════════════════════════════════

    async def _run(self, frames_queue: asyncio.Queue) -> None:
        """Main wake word detection loop."""
        while self._running:
            try:
                try:
                    frame = await asyncio.wait_for(frames_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    self._last_heartbeat = time.time()
                    continue

                self._last_heartbeat = time.time()

                if not self._enabled:
                    continue

                # Process the frame in thread pool (Vosk is blocking)
                detected = await asyncio.to_thread(self._process_frame_sync, frame)

                if detected:
                    self._total_detections += 1
                    pipeline_metrics.increment("wake.detections")
                    await engine_events.emit(PipelineEvent.WAKE_DETECTED)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error("wake_detector_error", error=str(exc))
                pipeline_metrics.record_error("wake", str(exc))
                await asyncio.sleep(0.1)

    def _process_frame_sync(self, frame: bytes) -> bool:
        """Process a single audio frame synchronously (called in thread pool).

        Returns True if a wake word was detected.
        """
        self._total_frames_processed += 1

        if not self._rec:
            return False

        now = time.time()
        if now < self._cooldown_until:
            return False

        try:
            if not self._rec.AcceptWaveform(frame):
                return False

            result = json.loads(self._rec.Result())
            text = result.get("text", "").lower().strip()
            if not text or text == "[unk]":
                return False

            for keyword in self.keywords:
                if keyword.lower() in text:
                    log.info("wake_word_detected", text=text, keyword=keyword)
                    self._cooldown_until = now + self.cooldown_s
                    return True

        except Exception as exc:
            log.warning("wake_process_error", error=str(exc))

        return False

    # ══════════════════════════════════════════════════════════════════════
    # CONTROL
    # ══════════════════════════════════════════════════════════════════════

    def set_enabled(self, enabled: bool) -> None:
        """Enable/disable wake detection without stopping the worker."""
        self._enabled = enabled

    def reset(self) -> None:
        """Reset the recognizer state (call after conversation ends)."""
        if self._rec:
            try:
                from vosk import KaldiRecognizer
                model = _vosk_model_cache
                if model:
                    grammar = json.dumps(self.keywords + ["[unk]"])
                    self._rec = KaldiRecognizer(model, self.sample_rate, grammar)
            except Exception as exc:
                log.warning("wake_reset_failed", error=str(exc))
        self._cooldown_until = 0.0

    @property
    def heartbeat(self) -> float:
        return self._last_heartbeat
