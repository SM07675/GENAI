"""Voice Activity Detection worker for the audio pipeline.

Design:
- Loads Silero VAD model ONCE at startup, reuses for all frames.
- Runs as an async worker consuming frames from the microphone queue.
- Emits SPEECH_START, SPEECH_END, SILENCE_TIMEOUT events via the event bus.
- NEVER runs on the audio capture thread (unlike the old implementation).
- Configurable thresholds, cooldowns, and minimum speech duration.
- Pre-roll awareness: signals microphone to start speech recording.
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

import numpy as np
import structlog

from ..event_bus import PipelineEvent, engine_events
from ..metrics import pipeline_metrics

log = structlog.get_logger("genie.engine.audio.vad")

# Cached Silero VAD model — loaded ONCE per process
_vad_model = None
_vad_model_loaded = False

# Terminal-sounding words that suggest the user has finished speaking
# (simple heuristic for two-tier endpointing — no transcript required)
_TERMINAL_WORDS = frozenset([
    "okay", "ok", "please", "thanks", "right", "yes", "no", "sure",
    "done", "stop", "pause", "now", "time", "today", "tomorrow",
    "morning", "night", "afternoon", "evening", "that", "this", "it",
])


def _load_silero_vad():
    """Load Silero VAD model (once)."""
    global _vad_model, _vad_model_loaded
    if _vad_model_loaded:
        return _vad_model

    try:
        import torch
        model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=True,
        )
        _vad_model = model
        _vad_model_loaded = True
        log.info("silero_vad_loaded")
        return model
    except Exception as exc:
        log.warning("silero_vad_load_failed", error=str(exc))
        _vad_model_loaded = True  # don't retry
        return None


class VADWorker:
    """Async VAD worker that processes frames from the microphone.

    Consumes raw PCM frames from an async queue, runs Silero VAD,
    and emits speech boundary events to the engine event bus.

    State: tracks whether speech is currently detected, handles
    silence timeouts and minimum speech duration filtering.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_size: int = 512,
        vad_threshold: float = 0.4,
        echo_threshold_multiplier: float = 1.0,
        silence_timeout: float = 0.9,
        initial_silence_timeout: float = 5.0,
        minimum_speech_duration: float = 0.3,
        maximum_speech_duration: float = 45.0,
        echo_canceller = None,
    ):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.vad_threshold = vad_threshold
        self.silence_timeout = silence_timeout
        self.initial_silence_timeout = initial_silence_timeout
        self.minimum_speech_duration = minimum_speech_duration
        self.maximum_speech_duration = maximum_speech_duration

        # v12 two-tier endpointing — configurable via settings
        from ...config import get_settings
        _s = get_settings()
        self._silence_short_s: float = _s.vad_endpointing_short_ms / 1000.0
        self._silence_long_s: float = _s.vad_endpointing_long_ms / 1000.0

        # State
        self._speech_active = False
        self._speech_start_time = 0.0
        self._last_speech_time = 0.0
        self._session_start_time = 0.0
        self._listening_active = False
        self._last_speech_energy: float = 0.0  # track energy for terminal heuristic

        # Echo suppression multiplier (set externally or via injected canceller)
        self._echo_canceller = echo_canceller
        self._echo_multiplier = 1.0

        # Energy fallback
        self._baseline_rms: float = 0.0
        self._noise_alpha: float = 0.05
        self._noise_initialized = False
        self._noise_init_count = 0

        # Worker task
        self._task: Optional[asyncio.Task] = None
        self._running = False

        # Heartbeat
        self._last_heartbeat = time.time()

    # ══════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════════════════════

    async def start(self, frames_queue: asyncio.Queue) -> None:
        """Start the VAD worker consuming from the frames queue."""
        # Load VAD model in thread pool
        model = await asyncio.to_thread(_load_silero_vad)
        if model:
            log.info("vad_worker_started_silero")
        else:
            log.warning("vad_worker_started_energy_fallback")

        self._running = True
        self._task = asyncio.create_task(self._run(frames_queue))

    async def stop(self) -> None:
        """Stop the VAD worker."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        log.info("vad_worker_stopped")

    # ══════════════════════════════════════════════════════════════════════
    # MAIN LOOP
    # ══════════════════════════════════════════════════════════════════════

    async def _run(self, frames_queue: asyncio.Queue) -> None:
        """Main VAD processing loop."""
        while self._running:
            try:
                # Wait for a frame with timeout (allows periodic housekeeping)
                try:
                    frame = await asyncio.wait_for(frames_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    self._last_heartbeat = time.time()
                    continue

                self._last_heartbeat = time.time()

                if not self._listening_active:
                    # Still process frames to keep queue drained, but don't analyze
                    continue

                await self._process_frame(frame)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error("vad_worker_error", error=str(exc), exc_info=True)
                pipeline_metrics.record_error("vad", str(exc))
                await asyncio.sleep(0.1)

    async def _process_frame(self, frame: bytes) -> None:
        """Process a single audio frame through VAD."""
        is_speech = self._detect_speech(frame)

        now = time.time()

        if not self._speech_active:
            # Not currently in speech
            if is_speech:
                # Speech started!
                self._speech_active = True
                self._speech_start_time = now
                self._last_speech_time = now

                await engine_events.emit(PipelineEvent.SPEECH_START)
                pipeline_metrics.increment("vad.speech_starts")

            elif self._session_start_time > 0:
                # Check initial silence timeout
                elapsed = now - self._session_start_time
                if elapsed > self.initial_silence_timeout:
                    await engine_events.emit(PipelineEvent.SILENCE_TIMEOUT)
                    self._session_start_time = 0  # prevent repeat
                    pipeline_metrics.increment("vad.silence_timeouts")
        else:
            # Currently in speech
            if is_speech:
                self._last_speech_time = now

            silence_elapsed = now - self._last_speech_time
            speech_duration = now - self._speech_start_time

            # v12 two-tier endpointing:
            # Use the short timeout when the speech segment is brief (likely
            # a crisp command) and the long timeout for longer utterances
            # (possibly trailing thoughts). This avoids clipping while
            # also reducing dead air after quick replies.
            _is_short_utterance = (now - self._speech_start_time) < 2.5
            _active_timeout = self._silence_short_s if _is_short_utterance else self._silence_long_s

            if silence_elapsed > _active_timeout:
                # Silence after speech
                if speech_duration >= self.minimum_speech_duration:
                    await engine_events.emit(
                        PipelineEvent.SPEECH_END,
                        duration=speech_duration,
                    )
                    pipeline_metrics.increment("vad.speech_ends")
                    pipeline_metrics.record_latency("vad.speech_duration", speech_duration * 1000)
                else:
                    # Too short — noise blip
                    pipeline_metrics.increment("vad.noise_blips")

                self._speech_active = False
                self._speech_start_time = 0.0
                self._last_speech_time = 0.0

            elif speech_duration > self.maximum_speech_duration:
                # Max duration exceeded
                await engine_events.emit(PipelineEvent.MAX_DURATION)
                self._speech_active = False
                self._speech_start_time = 0.0
                pipeline_metrics.increment("vad.max_duration_hits")

    def _detect_speech(self, frame: bytes) -> bool:
        """Run VAD on a single frame. Returns True if speech detected."""
        data = np.frombuffer(frame, dtype=np.int16)
        if len(data) == 0:
            return False

        # Try Silero VAD first
        if _vad_model is not None:
            try:
                import torch
                audio_float = data.astype(np.float32) / 32768.0
                tensor = torch.from_numpy(audio_float)

                # Silero VAD requires exactly 512 samples for 16kHz
                if len(tensor) == 512:
                    conf = _vad_model(tensor, self.sample_rate).item()
                else:
                    # Split into 512-sample chunks, take max confidence
                    chunks = torch.split(tensor, 512)
                    max_conf = 0.0
                    for c in chunks:
                        if len(c) == 512:
                            conf = _vad_model(c, self.sample_rate).item()
                            if conf > max_conf:
                                max_conf = conf
                    conf = max_conf

                multiplier = self._echo_canceller.get_vad_threshold_multiplier() if self._echo_canceller else self._echo_multiplier
                threshold = self.vad_threshold * multiplier
                return conf > threshold

            except Exception as e:
                log.warning("silero_vad_error", error=str(e))

        # Fallback: energy-based VAD
        energy = float(np.abs(data).mean())
        self._update_noise_baseline(energy)

        multiplier = self._echo_canceller.get_vad_threshold_multiplier() if self._echo_canceller else self._echo_multiplier
        threshold = max(200.0, self._baseline_rms * 1.5 + 100)
        threshold *= multiplier
        return energy > threshold

    def _update_noise_baseline(self, energy: float) -> None:
        """Update noise baseline for energy fallback VAD."""
        if not self._noise_initialized:
            self._noise_init_count += 1
            self._baseline_rms = (
                (self._baseline_rms * (self._noise_init_count - 1) + energy)
                / self._noise_init_count
            )
            if self._noise_init_count >= 20:
                self._noise_initialized = True
        else:
            if energy < self._baseline_rms * 3.0:
                self._baseline_rms = (
                    self._noise_alpha * energy
                    + (1 - self._noise_alpha) * self._baseline_rms
                )

    # ══════════════════════════════════════════════════════════════════════
    # CONTROL (called by pipeline supervisor)
    # ══════════════════════════════════════════════════════════════════════

    def start_listening_session(self) -> None:
        """Begin a new listening session — enables VAD and resets timers."""
        self._listening_active = True
        self._session_start_time = time.time()
        self._speech_active = False
        self._speech_start_time = 0.0
        self._last_speech_time = 0.0

    def stop_listening_session(self) -> None:
        """Stop the listening session — disables VAD processing."""
        self._listening_active = False
        self._speech_active = False

    def set_echo_suppression(self, multiplier: float) -> None:
        """Set the echo suppression threshold multiplier."""
        self._echo_multiplier = max(1.0, multiplier)

    @property
    def is_speech_active(self) -> bool:
        return self._speech_active

    @property
    def heartbeat(self) -> float:
        return self._last_heartbeat
