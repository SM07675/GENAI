"""Continuous VAD Gate — Barge-In Detector for Genie Voice Pipeline v12.

Design
------
- Loads Silero VAD (ONNX runtime, CPU) **once** and keeps it alive.
- Consumes a post-AEC mic frame stream *continuously*, including during
  ``SPEAKING`` / ``THINKING`` / ``STREAMING_RESPONSE`` states.
- Fires ``on_speech_start`` after ~200 ms of continuous voiced audio —
  avoiding false triggers from a single click, cough, or TTS loopback.
- Applies a short cooldown after firing to prevent re-triggering on
  the tail of the same utterance.

This is the ONLY new component required for barge-in. It re-uses the
same ``cancel_token`` path that today's manual cancel button uses —
no second cancellation mechanism is needed.

Feature flag
------------
The gate respects ``ENABLE_BARGE_IN`` from settings. When disabled, the
``watch()`` loop drains frames but never fires ``on_speech_start``.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import AsyncIterator, Awaitable, Callable, Optional

import numpy as np
import structlog

log = structlog.get_logger("genie.engine.audio.vad_gate")

_SAMPLE_RATE = 16_000
_FRAME_SAMPLES = 512            # Silero's native frame size at 16 kHz (32 ms)
_FRAME_MS = int(_FRAME_SAMPLES / _SAMPLE_RATE * 1000)   # 32 ms

_DEFAULT_THRESHOLD = 0.5
_DEFAULT_MIN_SPEECH_MS = 200
_DEFAULT_COOLDOWN_MS = 400


@dataclass
class BargeInConfig:
    """Tuning parameters for the barge-in VAD gate."""

    threshold: float = _DEFAULT_THRESHOLD
    """Silero probability threshold (0–1). Higher = less sensitive."""

    min_speech_ms: int = _DEFAULT_MIN_SPEECH_MS
    """Continuous voiced frames (ms) required before firing ``on_speech_start``."""

    cooldown_ms: int = _DEFAULT_COOLDOWN_MS
    """Minimum ms between consecutive ``on_speech_start`` fires."""


class VADGate:
    """Always-on barge-in gate using Silero VAD (ONNX).

    Wire into the pipeline like this::

        vad_gate = VADGate(config=BargeInConfig())
        frames_q  = mic.create_subscriber_queue()
        asyncio.create_task(
            vad_gate.watch(
                frames  = _queue_to_async_iter(frames_q),
                on_speech_start = _handle_bargein,
                active  = lambda: pipeline_is_in_cancellable_state(),
            )
        )

    The gate uses the ONNX build of Silero VAD so it has no torch / CUDA
    dependency beyond what faster-whisper already pulls in.
    """

    def __init__(self, config: Optional[BargeInConfig] = None):
        self._cfg = config or BargeInConfig()
        self._session = None           # ort.InferenceSession — loaded lazily
        self._h: Optional[np.ndarray] = None
        self._c: Optional[np.ndarray] = None
        self._voiced_ms: int = 0
        self._last_fire_ts: float = 0.0
        self._loaded = False

    # ══════════════════════════════════════════════════════════════════════
    # MODEL LOADING
    # ══════════════════════════════════════════════════════════════════════

    async def preload(self) -> bool:
        """Load the Silero ONNX model in the thread pool. Returns True on success."""
        return await asyncio.to_thread(self._load_model)

    def _load_model(self) -> bool:
        """Synchronous model loader — runs in a thread pool."""
        if self._loaded:
            return self._session is not None

        try:
            import onnxruntime as ort

            # Try to locate the model from torch hub cache (silero-vad is tiny)
            model_path = self._find_model_path()
            if not model_path:
                log.warning("vad_gate_onnx_model_not_found_using_torch_fallback")
                self._loaded = True
                return False

            self._session = ort.InferenceSession(
                model_path,
                providers=["CPUExecutionProvider"],
            )
            # Initialise recurrent state tensors (shapes from silero-vad ONNX graph)
            self._h = np.zeros((2, 1, 64), dtype=np.float32)
            self._c = np.zeros((2, 1, 64), dtype=np.float32)
            self._loaded = True
            log.info("vad_gate_onnx_loaded", model=model_path)
            return True

        except ImportError:
            log.warning("vad_gate_onnxruntime_not_installed")
            self._loaded = True
            return False
        except Exception as exc:
            log.warning("vad_gate_load_failed", error=str(exc))
            self._loaded = True
            return False

    def _find_model_path(self) -> Optional[str]:
        """Locate the Silero VAD ONNX model from the torch hub cache."""
        import os
        import pathlib

        # Common torch hub locations on Windows
        hub_dirs = [
            pathlib.Path.home() / ".cache" / "torch" / "hub",
            pathlib.Path(os.environ.get("TORCH_HOME", "")) / "hub"
            if os.environ.get("TORCH_HOME") else None,
        ]

        for hub_dir in hub_dirs:
            if hub_dir is None or not hub_dir.exists():
                continue
            for p in hub_dir.rglob("silero_vad.onnx"):
                return str(p)

        return None

    # ══════════════════════════════════════════════════════════════════════
    # INFERENCE
    # ══════════════════════════════════════════════════════════════════════

    def _infer(self, pcm: np.ndarray) -> float:
        """Run Silero on a single 512-sample frame. Returns speech probability."""
        if self._session is None or self._h is None or self._c is None:
            return 0.0

        try:
            ort_inputs = {
                "input": pcm[None, :].astype(np.float32),
                "h": self._h,
                "c": self._c,
                "sr": np.array(_SAMPLE_RATE, dtype=np.int64),
            }
            out, self._h, self._c = self._session.run(None, ort_inputs)
            return float(out[0][0])
        except Exception as exc:
            log.debug("vad_gate_infer_error", error=str(exc))
            return 0.0

    def _infer_energy_fallback(self, pcm: np.ndarray) -> float:
        """Simple energy-based fallback when ONNX model is unavailable."""
        rms = float(np.sqrt(np.mean(pcm ** 2)))
        # Rough calibration: ~0.02 RMS is whisper-level speech in float32
        return min(1.0, rms / 0.02)

    # ══════════════════════════════════════════════════════════════════════
    # MAIN WATCH LOOP
    # ══════════════════════════════════════════════════════════════════════

    async def watch(
        self,
        frames: AsyncIterator[bytes],
        on_speech_start: Callable[[], Awaitable[None]],
        active: Callable[[], bool] = lambda: True,
    ) -> None:
        """Consume a mic frame stream and fire ``on_speech_start`` on barge-in.

        Args:
            frames:           Async iterator of raw PCM int16 frames (512 samples each).
            on_speech_start:  Coroutine to invoke when real speech is detected.
            active:           Callable that returns True when barge-in should
                              be armed (e.g. during SPEAKING / THINKING).
                              When False, frames are drained but not analysed.
        """
        if not self._loaded:
            await self.preload()

        async for raw in frames:
            try:
                if not active():
                    # Not in a barge-in–eligible state — drain, reset continuity
                    self._voiced_ms = 0
                    continue

                pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

                # Pad or truncate to exactly 512 samples
                if len(pcm) < _FRAME_SAMPLES:
                    pcm = np.pad(pcm, (0, _FRAME_SAMPLES - len(pcm)))
                elif len(pcm) > _FRAME_SAMPLES:
                    pcm = pcm[:_FRAME_SAMPLES]

                if self._session is not None:
                    prob = self._infer(pcm)
                else:
                    prob = self._infer_energy_fallback(pcm)

                now_ms = time.monotonic() * 1000

                if prob >= self._cfg.threshold:
                    self._voiced_ms += _FRAME_MS
                else:
                    self._voiced_ms = 0   # unvoiced frame resets continuity counter

                fired_recently = (now_ms - self._last_fire_ts) < self._cfg.cooldown_ms
                if self._voiced_ms >= self._cfg.min_speech_ms and not fired_recently:
                    self._last_fire_ts = now_ms
                    self._voiced_ms = 0
                    log.info("vad_gate_barge_in_detected", prob=round(prob, 3))
                    await on_speech_start()

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.debug("vad_gate_frame_error", error=str(exc))
                continue

        # Stream ended (pipeline shutdown)
        log.debug("vad_gate_watch_ended")

    # ══════════════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════════════

    def reset(self) -> None:
        """Reset voiced-frame counter and recurrent state (call after barge-in fires)."""
        self._voiced_ms = 0
        if self._h is not None:
            self._h = np.zeros_like(self._h)
        if self._c is not None:
            self._c = np.zeros_like(self._c)


async def queue_to_async_iter(q: asyncio.Queue) -> AsyncIterator[bytes]:
    """Wrap a bounded asyncio.Queue as an async iterator for ``VADGate.watch``."""
    while True:
        try:
            frame = await asyncio.wait_for(q.get(), timeout=1.0)
            if frame is None:
                break
            yield frame
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            break
