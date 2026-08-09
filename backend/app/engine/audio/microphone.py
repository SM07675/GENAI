"""Singleton microphone service with ring buffer.

Design:
- Opens PyAudio ONCE. Never closes until shutdown.
- Dedicated daemon thread reads frames continuously.
- Frames are posted to a bounded asyncio.Queue (backpressure).
- Ring buffer stores the last ~30s for retrospective access.
- Thread-safe speech buffer with lock.
- Auto-reconnect on failure with exponential backoff.
- No VAD, no wake detection — just raw frame capture and routing.
"""
from __future__ import annotations

import asyncio
import collections
import threading
import time
from typing import Optional

import numpy as np
import structlog

log = structlog.get_logger("genie.engine.audio.microphone")

# Maximum retries before giving up on auto-reconnect
_MAX_RESTART_ATTEMPTS = 5
_RESTART_BASE_DELAY_S = 1.0


class MicrophoneService:
    """Persistent microphone capture service.

    Opens the mic once and keeps it open. The capture loop runs on a
    dedicated daemon thread and posts raw PCM frames to a bounded
    async queue for downstream workers.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_size: int = 512,               # Silero VAD wants 512 @ 16kHz
        ring_buffer_seconds: float = 30.0,
        frames_queue_maxsize: int = 200,
    ):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size

        # Ring buffer: stores raw PCM frames (last ~30s)
        max_frames = int(ring_buffer_seconds * sample_rate / chunk_size)
        self._ring_buffer: collections.deque[bytes] = collections.deque(maxlen=max_frames)

        # Speech capture buffer (thread-safe)
        self._speech_lock = threading.Lock()
        self._speech_buffer: list[bytes] = []
        self._speech_recording = False

        # Pre-roll buffer: audio just before speech starts
        pre_roll_frames = max(1, int(0.5 * sample_rate / chunk_size))  # 500ms
        self._pre_roll: collections.deque[bytes] = collections.deque(maxlen=pre_roll_frames)

        # Frame output queues → async workers (fanout to ALL subscribers)
        self._subscriber_queues: list[asyncio.Queue] = []
        self._frames_queue_maxsize = frames_queue_maxsize
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # PyAudio resources
        self._pyaudio = None
        self._stream = None

        # Threading
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Recovery
        self._restart_count = 0
        self._total_frames_captured = 0
        self._dropped_frames = 0

    # ══════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════════════════════

    def start(self, loop: asyncio.AbstractEventLoop) -> bool:
        """Open the microphone and start capturing.

        Args:
            loop: The running asyncio event loop for thread-safe posting.

        Returns:
            True if microphone opened successfully.
        """
        if self._running:
            log.info("mic_already_running")
            return True

        self._loop = loop

        if not self._open_audio():
            return False

        self._running = True
        self._stop_event.clear()
        self._restart_count = 0

        self._thread = threading.Thread(
            target=self._capture_loop,
            name="MicrophoneCapture",
            daemon=True,
        )
        self._thread.start()
        log.info(
            "microphone_started",
            rate=self.sample_rate,
            chunk=self.chunk_size,
            queue_max=self._frames_queue_maxsize,
        )
        return True

    def stop(self) -> None:
        """Stop capture and release audio resources. Called once at shutdown."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

        self._close_audio()
        log.info(
            "microphone_stopped",
            total_frames=self._total_frames_captured,
            dropped_frames=self._dropped_frames,
        )

    def _open_audio(self) -> bool:
        """Open audio stream via PyAudio or sounddevice fallback."""
        # 1. Try PyAudio
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
            self._backend_type = "pyaudio"
            log.info("microphone_opened", engine="pyaudio")
            return True
        except Exception as exc:
            log.warning("pyaudio_unavailable_trying_sounddevice", error=str(exc))
            self._close_audio()

        # 2. Fallback to sounddevice (prebuilt PortAudio included)
        try:
            import sounddevice as sd
            self._stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                channels=1,
                dtype="int16",
            )
            self._stream.start()
            self._backend_type = "sounddevice"
            log.info("microphone_opened", engine="sounddevice")
            return True
        except Exception as exc:
            log.error("microphone_open_failed", error=str(exc))
            self._close_audio()
            return False

    def _close_audio(self) -> None:
        """Release audio resources safely."""
        if self._stream:
            try:
                if getattr(self, "_backend_type", "pyaudio") == "sounddevice":
                    self._stream.stop()
                    self._stream.close()
                else:
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

    # ══════════════════════════════════════════════════════════════════════
    # CAPTURE LOOP
    # ══════════════════════════════════════════════════════════════════════

    def _capture_loop(self) -> None:
        """Read audio frames continuously on a dedicated thread.

        Never exits unless stop() is called or unrecoverable error occurs.
        Auto-reconnects on transient failures.
        """
        consecutive_errors = 0
        max_consecutive_errors = 20
        is_sd = getattr(self, "_backend_type", "pyaudio") == "sounddevice"

        while self._running and not self._stop_event.is_set():
            if not self._stream:
                # Try to reconnect
                if not self._auto_reconnect():
                    break
                continue

            try:
                if is_sd:
                    data_buf, overflow = self._stream.read(self.chunk_size)
                    data = bytes(data_buf)
                else:
                    data = self._stream.read(self.chunk_size, exception_on_overflow=False)

                consecutive_errors = 0
                self._total_frames_captured += 1
                self._process_frame(data)

            except IOError as e:
                # IOError can mean overflow (harmless) or disconnect (fatal)
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    log.error(
                        "microphone_io_errors",
                        count=consecutive_errors,
                        error=str(e),
                    )
                    if not self._auto_reconnect():
                        break

            except Exception as exc:
                consecutive_errors += 1
                log.error("microphone_read_error", error=str(exc), count=consecutive_errors)
                if consecutive_errors >= max_consecutive_errors:
                    if not self._auto_reconnect():
                        break
                        break

    def _process_frame(self, frame: bytes) -> None:
        """Route a captured frame to consumers."""
        # Always store in ring buffer
        self._ring_buffer.append(frame)

        # Store in speech buffer if recording
        with self._speech_lock:
            if self._speech_recording:
                self._speech_buffer.append(frame)
            else:
                self._pre_roll.append(frame)

        # Broadcast to ALL subscriber queues (fanout)
        if self._subscriber_queues and self._loop is not None:
            try:
                self._loop.call_soon_threadsafe(
                    self._enqueue_frame_nowait, frame
                )
            except RuntimeError:
                pass  # loop closed

    def _enqueue_frame_nowait(self, frame: bytes) -> None:
        """Broadcast a frame to ALL subscriber queues. Drop if full."""
        for q in self._subscriber_queues:
            try:
                q.put_nowait(frame)
            except asyncio.QueueFull:
                self._dropped_frames += 1
                # Drop oldest frame and add new one
                try:
                    q.get_nowait()
                    q.put_nowait(frame)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

    # ══════════════════════════════════════════════════════════════════════
    # AUTO-RECONNECT
    # ══════════════════════════════════════════════════════════════════════

    def _auto_reconnect(self) -> bool:
        """Attempt to reconnect the microphone. Returns True on success."""
        self._restart_count += 1
        if self._restart_count > _MAX_RESTART_ATTEMPTS:
            log.error(
                "microphone_reconnect_limit",
                attempts=self._restart_count,
            )
            self._running = False
            return False

        delay = _RESTART_BASE_DELAY_S * (2 ** (self._restart_count - 1))
        delay = min(delay, 10.0)  # cap at 10s
        log.warning(
            "microphone_reconnecting",
            attempt=self._restart_count,
            delay=delay,
        )

        self._close_audio()
        self._stop_event.wait(timeout=delay)

        if not self._running or self._stop_event.is_set():
            return False

        if self._open_audio():
            log.info("microphone_reconnected", attempt=self._restart_count)
            self._restart_count = 0  # reset on success
            return True

        return self._auto_reconnect()  # retry

    # ══════════════════════════════════════════════════════════════════════
    # PUBLIC API (called from async workers)
    # ══════════════════════════════════════════════════════════════════════

    def create_subscriber_queue(self, maxsize: int = 0) -> asyncio.Queue:
        """Create a new subscriber queue that receives ALL captured frames.
        
        Each subscriber gets its own independent copy of every frame.
        This enables VAD, Wake, and any other consumer to run concurrently
        without stealing frames from each other.
        """
        if maxsize <= 0:
            maxsize = self._frames_queue_maxsize
        q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._subscriber_queues.append(q)
        log.info("mic_subscriber_added", total_subscribers=len(self._subscriber_queues))
        return q

    @property
    def frames_queue(self) -> Optional[asyncio.Queue]:
        """Legacy: return the first subscriber queue (or None)."""
        return self._subscriber_queues[0] if self._subscriber_queues else None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def stats(self) -> dict:
        return {
            "running": self._running,
            "total_frames": self._total_frames_captured,
            "dropped_frames": self._dropped_frames,
            "ring_buffer_size": len(self._ring_buffer),
            "speech_buffer_size": len(self._speech_buffer),
            "restart_count": self._restart_count,
        }

    # ── Speech buffer control ─────────────────────────────────────────────

    def start_speech_recording(self) -> None:
        """Begin capturing speech audio. Includes pre-roll."""
        with self._speech_lock:
            self._speech_recording = True
            # Include pre-roll audio (audio just before speech started)
            self._speech_buffer = list(self._pre_roll)
            self._pre_roll.clear()

    def stop_speech_recording(self) -> None:
        """Stop capturing speech audio."""
        with self._speech_lock:
            self._speech_recording = False

    def get_speech_audio(self) -> bytes:
        """Return captured speech audio and reset the buffer. Thread-safe."""
        with self._speech_lock:
            audio = b"".join(self._speech_buffer)
            self._speech_buffer.clear()
            self._speech_recording = False
            return audio

    def reset_speech_buffer(self) -> None:
        """Clear the speech buffer without returning audio."""
        with self._speech_lock:
            self._speech_buffer.clear()
            self._speech_recording = False
            self._pre_roll.clear()

    def get_ring_buffer_audio(self, last_seconds: float = 5.0) -> bytes:
        """Return the last N seconds from the ring buffer."""
        frames_needed = int(last_seconds * self.sample_rate / self.chunk_size)
        frames = list(self._ring_buffer)[-frames_needed:]
        return b"".join(frames)
