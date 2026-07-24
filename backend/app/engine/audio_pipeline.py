"""Audio pipeline — persistent microphone capture with Silero VAD.

Design:
- Opens PyAudio once on ``start()``; stays open until ``stop()``.
- Maintains a **ring buffer** of raw PCM frames (last ~30s).
- Runs **Silero VAD** on every frame (~2ms per frame) to detect speech.
- Produces events: SPEECH_START, SPEECH_END, SILENCE_TIMEOUT, VAD_FRAME.
- Frame routing is state-driven: the conversation engine tells the pipeline
  whether frames should go to the wake detector, speech buffer, or both.

Thread model:
- ``_capture_loop()`` runs on a dedicated daemon thread.
- It calls ``self._on_frame(data)`` which posts events to an asyncio queue.
- The conversation engine consumes from the queue on the event loop.
"""
from __future__ import annotations

import asyncio
import collections
import logging
import threading
import time
from enum import Enum
from typing import Callable, Optional

import numpy as np
import structlog

log = structlog.get_logger("genie.engine.audio")


class AudioEvent(str, Enum):
    """Events produced by the audio pipeline."""
    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"
    SILENCE_TIMEOUT = "silence_timeout"
    INITIAL_SILENCE_TIMEOUT = "initial_silence_timeout"
    MAX_DURATION = "max_duration"
    FRAME = "frame"


class AudioPipeline:
    """Persistent microphone capture with neural VAD.

    The mic opens once and stays open. Frame routing (wake detector vs
    speech capture) is controlled by the conversation engine via
    ``set_mode()``.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_size: int = 512,       # Silero wants 512 samples @ 16kHz (32ms)
        ring_buffer_seconds: float = 30.0,
        silence_timeout: float = 0.9,
        speech_start_timeout: float = 5.0,
        minimum_speech_duration: float = 0.3,
        maximum_command_duration: float = 45.0,
        pre_roll_ms: int = 500,
    ):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.silence_timeout = silence_timeout
        self.speech_start_timeout = speech_start_timeout
        self.minimum_speech_duration = minimum_speech_duration
        self.maximum_command_duration = maximum_command_duration
        self.pre_roll_ms = pre_roll_ms

        # Ring buffer: stores raw PCM frames
        max_frames = int(ring_buffer_seconds * sample_rate / chunk_size)
        self._ring_buffer: collections.deque[bytes] = collections.deque(maxlen=max_frames)

        # Pre-roll buffer: captures audio just before speech starts
        max_pre_roll = max(1, int((pre_roll_ms / 1000.0) * sample_rate / chunk_size))
        self._pre_roll: collections.deque[bytes] = collections.deque(maxlen=max_pre_roll)

        # Speech capture buffer
        self._speech_buffer: list[bytes] = []
        self._speech_started = False
        self._speech_start_time = 0.0
        self._last_speech_time = 0.0
        self._session_start_time = 0.0

        # VAD model (lazy-loaded)
        self._vad_model = None
        self._vad_ready = False

        # Echo suppression: increase VAD threshold when TTS is playing
        self._echo_suppression = False

        # Event queue → conversation engine
        self._event_queue: Optional[asyncio.Queue] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Frame callback: additional consumer (wake detector)
        self._frame_callback: Optional[Callable[[bytes], None]] = None

        # Noise baseline (EMA)
        self._baseline_rms = 0.0
        self._noise_alpha = 0.05
        self._noise_initialized = False
        self._noise_init_count = 0

        # Threading
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pyaudio = None
        self._stream = None
        self._restart_count = 0
        self._lock = threading.Lock()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self, event_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop) -> bool:
        """Open the microphone and start capturing.

        Args:
            event_queue: Async queue where audio events are posted.
            loop: The running asyncio event loop (for thread-safe posting).
        """
        if self._running:
            return True

        self._event_queue = event_queue
        self._loop = loop

        # Load Silero VAD model
        if not self._load_vad():
            log.warning("silero_vad_unavailable", msg="Falling back to energy VAD")

        # Open PyAudio
        try:
            import pyaudio
            self._pyaudio = pyaudio.PyAudio()

            self._stream = self._pyaudio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
            )
            log.info("audio_pipeline_started", rate=self.sample_rate, chunk=self.chunk_size)
        except Exception as exc:
            log.error("audio_pipeline_init_failed", error=str(exc))
            self._cleanup_pyaudio()
            return False

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._capture_loop,
            name="AudioPipeline",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        """Stop the capture loop and release audio resources."""
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._cleanup_pyaudio()
        log.info("audio_pipeline_stopped")

    def _cleanup_pyaudio(self) -> None:
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._pyaudio:
            try:
                self._pyaudio.terminate()
            except Exception:
                pass
            self._pyaudio = None

    # ── VAD ───────────────────────────────────────────────────────────────

    def _load_vad(self) -> bool:
        """Load Silero VAD model."""
        try:
            import torch
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=True,
            )
            self._vad_model = model
            self._vad_ready = True
            log.info("silero_vad_loaded")
            return True
        except Exception as exc:
            log.warning("silero_vad_load_failed", error=str(exc))
            self._vad_ready = False
            return False

    def _is_speech_frame(self, frame: bytes) -> bool:
        """Run VAD on a single frame. Returns True if speech detected."""
        data = np.frombuffer(frame, dtype=np.int16)
        if len(data) == 0:
            return False

        if self._vad_ready and self._vad_model is not None:
            try:
                import torch
                audio_float = data.astype(np.float32) / 32768.0
                tensor = torch.from_numpy(audio_float)
                
                # Silero VAD requires exactly 512 samples for 16000Hz.
                # Our chunk is 4000, so we split it into 512 chunks and take max confidence.
                chunks = torch.split(tensor, 512)
                max_conf = 0.0
                for c in chunks:
                    if len(c) == 512:
                        conf = self._vad_model(c, self.sample_rate).item()
                        if conf > max_conf:
                            max_conf = conf
                            
                threshold = 0.7 if self._echo_suppression else 0.4
                return max_conf > threshold
            except Exception as e:
                log.warning("silero_vad_error", error=str(e))

        # Fallback: energy-based VAD
        energy = float(np.abs(data).mean())
        threshold = max(200.0, self._baseline_rms * 1.5 + 100)
        if self._echo_suppression:
            threshold *= 2.5
        return energy > threshold

    def _update_noise_baseline(self, frame: bytes) -> None:
        """Update the noise baseline EMA for energy fallback VAD."""
        data = np.frombuffer(frame, dtype=np.int16)
        if len(data) == 0:
            return
        energy = float(np.abs(data).mean())

        if not self._noise_initialized:
            self._noise_init_count += 1
            self._baseline_rms = (
                (self._baseline_rms * (self._noise_init_count - 1) + energy)
                / self._noise_init_count
            )
            if self._noise_init_count >= 20:
                self._noise_initialized = True
        else:
            if self._baseline_rms > 0 and energy > self._baseline_rms * 3.0:
                return  # outlier
            self._baseline_rms = (
                self._noise_alpha * energy
                + (1 - self._noise_alpha) * self._baseline_rms
            )

    # ── Capture Loop ──────────────────────────────────────────────────────

    def _capture_loop(self) -> None:
        """Read audio frames continuously on a dedicated thread."""
        consecutive_errors = 0
        max_errors = 10

        while self._running and not self._stop_event.is_set():
            if not self._stream:
                break
            try:
                data = self._stream.read(self.chunk_size, exception_on_overflow=False)
                consecutive_errors = 0
                self._on_frame(data)
            except IOError:
                pass  # overflow — harmless
            except Exception as exc:
                consecutive_errors += 1
                log.error("audio_read_error", error=str(exc), count=consecutive_errors)
                if consecutive_errors >= max_errors:
                    log.error("audio_fatal_error")
                    self._running = False
                    threading.Thread(
                        target=self._auto_restart,
                        daemon=True,
                    ).start()
                    break

    def _on_frame(self, frame: bytes) -> None:
        """Process a single audio frame (called from capture thread)."""
        # Always store in ring buffer
        self._ring_buffer.append(frame)

        # Always call frame callback (wake detector)
        if self._frame_callback:
            try:
                self._frame_callback(frame)
            except Exception as e:
                log.error("frame_callback_error", error=str(e), exc_info=True)

        # Update noise baseline when not recording
        if not self._speech_started:
            self._update_noise_baseline(frame)

        # Run VAD
        is_speech = self._is_speech_frame(frame)

        if not self._speech_started:
            # Pre-roll buffer
            self._pre_roll.append(frame)

            if is_speech:
                # Speech started!
                self._speech_started = True
                self._speech_start_time = time.time()
                self._last_speech_time = time.time()
                self._speech_buffer = list(self._pre_roll)
                self._speech_buffer.append(frame)
                self._post_event(AudioEvent.SPEECH_START, {})
            else:
                # Check initial silence timeout
                if self._session_start_time > 0:
                    elapsed = time.time() - self._session_start_time
                    if elapsed > self.speech_start_timeout:
                        self._post_event(AudioEvent.INITIAL_SILENCE_TIMEOUT, {})
                        self._session_start_time = 0  # prevent repeat
        else:
            # Recording speech
            self._speech_buffer.append(frame)

            if is_speech:
                self._last_speech_time = time.time()

            silence_elapsed = time.time() - self._last_speech_time
            if silence_elapsed > self.silence_timeout:
                duration = time.time() - self._speech_start_time
                if duration >= self.minimum_speech_duration:
                    self._post_event(AudioEvent.SPEECH_END, {
                        "duration": duration,
                    })
                else:
                    # Too short — noise blip, reset
                    self.reset_speech()

            # Max duration
            if time.time() - self._speech_start_time > self.maximum_command_duration:
                self._post_event(AudioEvent.MAX_DURATION, {})

    def _post_event(self, event: AudioEvent, data: dict) -> None:
        """Post an event to the async queue from the capture thread."""
        if self._event_queue is None or self._loop is None:
            return
        try:
            self._loop.call_soon_threadsafe(
                self._event_queue.put_nowait,
                {"event": event, **data},
            )
        except RuntimeError:
            pass  # loop is closed

    def _auto_restart(self) -> None:
        """Auto-restart after fatal capture error."""
        time.sleep(1.0)
        self._restart_count += 1
        if self._restart_count > 5:
            log.error("audio_restart_limit_exceeded")
            return
        self._cleanup_pyaudio()
        time.sleep(0.5)
        if self._event_queue and self._loop:
            self.start(self._event_queue, self._loop)

    # ── Public API ────────────────────────────────────────────────────────

    def set_frame_callback(self, callback: Optional[Callable[[bytes], None]]) -> None:
        """Set the wake-word frame callback."""
        self._frame_callback = callback

    def set_echo_suppression(self, enabled: bool) -> None:
        """Enable/disable echo suppression during TTS playback."""
        self._echo_suppression = enabled

    def start_listening_session(self) -> None:
        """Begin a new listening session (resets timers)."""
        self._session_start_time = time.time()
        self.reset_speech()

    def reset_speech(self) -> None:
        """Reset speech detection state without stopping the mic."""
        self._speech_started = False
        self._speech_start_time = 0.0
        self._last_speech_time = 0.0
        self._speech_buffer.clear()
        self._pre_roll.clear()

    def get_speech_audio(self) -> bytes:
        """Return the captured speech audio and reset the buffer."""
        audio = b"".join(self._speech_buffer)
        self.reset_speech()
        return audio

    def get_ring_buffer_audio(self, last_seconds: float = 5.0) -> bytes:
        """Return the last N seconds from the ring buffer."""
        frames_needed = int(last_seconds * self.sample_rate / self.chunk_size)
        frames = list(self._ring_buffer)[-frames_needed:]
        return b"".join(frames)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def speech_detected(self) -> bool:
        return self._speech_started
