"""
Audio Stream Handler.

Receives raw PCM audio frames from the WebSocket and buffers them into
an asyncio.Queue for downstream consumers (VAD, STT).

Audio format contract (must match what the browser sends):
  - Sample rate : 16 000 Hz
  - Bit depth   : 16-bit signed little-endian (PCM)
  - Channels    : 1 (mono)
  - Frame size  : VAD_FRAME_MS × sample_rate / 1000 samples
                  e.g. 30 ms → 480 samples → 960 bytes

The browser resamples from its native rate to 16kHz before sending.
"""

from __future__ import annotations

import asyncio
from collections import deque
from typing import AsyncIterator

from app.core.logging_config import get_logger

logger = get_logger(__name__)

SAMPLE_RATE = 16_000          # Hz
BYTES_PER_SAMPLE = 2          # 16-bit PCM
MAX_QUEUE_SIZE = 512          # frames (~15s of 30ms frames); drop oldest when full


class AudioStreamHandler:
    """Receives raw PCM bytes and exposes them as an async iterator of frames.

    Usage::

        handler = AudioStreamHandler(session_id="abc", frame_ms=30)

        # Feed bytes received from WebSocket:
        await handler.feed(raw_bytes)

        # Consume frames in VAD / STT:
        async for frame in handler.frames():
            process(frame)

        # When done:
        await handler.close()
    """

    def __init__(self, session_id: str, frame_ms: int = 30) -> None:
        self._session_id = session_id
        self._frame_ms = frame_ms
        # Expected bytes per frame
        self._frame_bytes = int(SAMPLE_RATE * frame_ms / 1000) * BYTES_PER_SAMPLE
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        self._buffer = bytearray()
        self._closed = False
        self._bytes_received = 0
        self._frames_emitted = 0
        self._overflow_count = 0

    # ── Input ─────────────────────────────────────────────────────

    async def feed(self, data: bytes) -> None:
        """Feed raw PCM bytes from the WebSocket into the internal buffer.

        Bytes are accumulated until a full frame boundary is reached, then
        each complete frame is placed on the output queue.
        """
        if self._closed:
            return

        self._bytes_received += len(data)
        self._buffer.extend(data)

        # Drain complete frames from the buffer
        while len(self._buffer) >= self._frame_bytes:
            frame = bytes(self._buffer[: self._frame_bytes])
            self._buffer = self._buffer[self._frame_bytes :]
            await self._enqueue(frame)

    async def _enqueue(self, frame: bytes) -> None:
        """Place a frame on the queue, dropping the oldest if full."""
        if self._queue.full():
            try:
                self._queue.get_nowait()  # drop oldest
                self._overflow_count += 1
                if self._overflow_count % 50 == 1:
                    logger.warning(
                        "Audio queue overflow – dropping oldest frame",
                        session_id=self._session_id,
                        overflow_count=self._overflow_count,
                    )
            except asyncio.QueueEmpty:
                pass
        await self._queue.put(frame)
        self._frames_emitted += 1

    # ── Output ────────────────────────────────────────────────────

    async def frames(self) -> AsyncIterator[bytes]:
        """Async generator that yields PCM frames as they arrive.

        Exits when ``close()`` is called.
        """
        while True:
            frame = await self._queue.get()
            if frame is None:  # sentinel – stream closed
                break
            yield frame

    # ── Lifecycle ─────────────────────────────────────────────────

    async def close(self) -> None:
        """Signal end of stream. Outstanding `frames()` consumers will exit."""
        if not self._closed:
            self._closed = True
            await self._queue.put(None)  # sentinel
            logger.info(
                "AudioStreamHandler closed",
                session_id=self._session_id,
                bytes_received=self._bytes_received,
                frames_emitted=self._frames_emitted,
                overflow_frames=self._overflow_count,
            )

    # ── Properties ────────────────────────────────────────────────

    @property
    def frame_bytes(self) -> int:
        """Number of bytes in one audio frame."""
        return self._frame_bytes

    @property
    def frame_ms(self) -> int:
        """Duration of one audio frame in milliseconds."""
        return self._frame_ms

    @property
    def stats(self) -> dict:
        """Runtime statistics for monitoring."""
        return {
            "bytes_received": self._bytes_received,
            "frames_emitted": self._frames_emitted,
            "queue_size": self._queue.qsize(),
            "overflow_frames": self._overflow_count,
            "closed": self._closed,
        }
