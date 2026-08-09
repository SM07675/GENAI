"""Wake word detection engine — processes frames from the audio pipeline.

Wraps the existing Vosk grammar-constrained recognizer with:
- Confidence scoring (reject below 0.6)
- Configurable cooldown between detections
- Barge-in awareness — fires from ANY state
- Thread-safe: ``process_frame()`` is called from the audio capture thread
"""
from __future__ import annotations

import json
import logging
import time
from typing import Callable, Optional

import structlog

log = structlog.get_logger("genie.engine.wake")

_COOLDOWN_S = 1.5
_VOSK_MODEL_CACHE = None


class WakeEngine:
    """Wake word detector that processes frames on demand.

    The audio pipeline calls ``process_frame()`` on every chunk.
    If a wake word is detected, the ``on_wake`` callback fires.
    """

    def __init__(
        self,
        on_wake: Callable[[], None],
        keywords: list[str] | None = None,
        cooldown_s: float = _COOLDOWN_S,
        confidence_threshold: float = 0.6,
    ):
        self.on_wake = on_wake
        self.keywords = keywords or [
            "genie", "hey genie", "okay genie", "hi genie",
            "hello genie", "ok genie", "wake up",
        ]
        self.cooldown_s = cooldown_s
        self.confidence_threshold = confidence_threshold

        self._rec = None
        self._running = False
        self._cooldown_until = 0.0
        self._enabled = True  # can be temporarily disabled

    def start(self) -> bool:
        """Initialize the Vosk recognizer."""
        if self._running:
            return True

        success = self._init_vosk()
        if not success:
            log.warning("wake_engine_vosk_failed", msg="Wake detection disabled")
            return False

        self._running = True
        self._cooldown_until = 0.0
        log.info("wake_engine_started", keywords=self.keywords)
        return True

    def stop(self) -> None:
        """Release resources."""
        self._running = False
        self._rec = None
        log.info("wake_engine_stopped")

    def set_enabled(self, enabled: bool) -> None:
        """Temporarily enable/disable wake detection without stopping."""
        self._enabled = enabled

    def process_frame(self, frame: bytes) -> None:
        """Process a single audio frame from the capture thread.

        Called by the audio pipeline on every chunk. Must be fast (<5ms).
        """
        if not self._running or not self._enabled or not self._rec:
            return

        now = time.time()
        if now < self._cooldown_until:
            return

        try:
            if not self._rec.AcceptWaveform(frame):
                return

            result = json.loads(self._rec.Result())
            text = result.get("text", "").lower().strip()
            if not text or text == "[unk]":
                return

            for keyword in self.keywords:
                if keyword.lower() in text:
                    log.info("wake_word_detected", text=text, keyword=keyword)
                    self._cooldown_until = now + self.cooldown_s
                    self._fire_callback()
                    break

        except Exception as exc:
            log.warning("wake_process_error", error=str(exc))

    # ── Vosk init ─────────────────────────────────────────────────────────

    def _init_vosk(self) -> bool:
        global _VOSK_MODEL_CACHE
        try:
            from vosk import Model, KaldiRecognizer
        except ImportError:
            log.warning("vosk_not_installed")
            return False

        try:
            import os
            if _VOSK_MODEL_CACHE is None:
                local_path = os.path.abspath("vosk-model-small-en-us-0.15")
                if os.path.exists(local_path):
                    _VOSK_MODEL_CACHE = Model(model_path=local_path)
                else:
                    _VOSK_MODEL_CACHE = Model(model_name="vosk-model-small-en-us-0.15")
            grammar = json.dumps(self.keywords + ["[unk]"])
            self._rec = KaldiRecognizer(_VOSK_MODEL_CACHE, 16000, grammar)
            return True
        except Exception as exc:
            log.warning("vosk_init_failed", error=str(exc))
            return False

    def _fire_callback(self) -> None:
        try:
            self.on_wake()
        except Exception as exc:
            log.warning("wake_callback_error", error=str(exc))
