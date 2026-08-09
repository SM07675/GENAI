"""
Response Streamer.

Bridges the AI token stream to two simultaneous consumers:
  1. WebSocket partial_response events (text)
  2. TTSEngine.speak() calls (audio)

The key challenge is that TTS works best with complete sentences, but we
want to minimise first-audio latency. The ResponseStreamer solves this by:

  - Collecting tokens into a sentence buffer.
  - Flushing the buffer to TTS as soon as it detects a sentence boundary
    (period, question mark, exclamation mark, newline) OR the buffer
    exceeds a character threshold.
  - Sending every token to the WebSocket immediately (no buffering for text).

This produces sub-500ms first audio latency while still feeding TTS
natural complete phrases rather than single words.
"""

from __future__ import annotations

import asyncio
import re
from typing import AsyncIterator, Callable, Awaitable

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Sentence boundary pattern: end-of-sentence punctuation followed by whitespace
# or end-of-string.  Handles: "Hello." / "Ready?" / "Go!\n" / "Wait..."
_SENTENCE_END = re.compile(r"[.!?…]\s+|[.!?…]$|\n")

TextCallback = Callable[[str], Awaitable[None]]   # called per token
AudioSpeakCallback = Callable[[str], Awaitable[None]]  # called per sentence chunk


class ResponseStreamer:
    """Streams AI response tokens to text (WebSocket) and TTS simultaneously.

    Args:
        session_id: Logging context.
        on_text: Async callback invoked immediately for each text token.
        on_speak: Async callback invoked for each sentence-sized TTS chunk.
        sentence_buffer_chars: Max chars to buffer before forcing a TTS flush.
                               Larger = fewer TTS calls but higher latency.

    Usage::

        streamer = ResponseStreamer(
            session_id="abc",
            on_text=send_partial_response,
            on_speak=tts_engine.speak,
            sentence_buffer_chars=120,
        )

        full_text = await streamer.stream(ai_token_iterator, interrupt_event)
    """

    def __init__(
        self,
        session_id: str,
        on_text: TextCallback,
        on_speak: AudioSpeakCallback,
        sentence_buffer_chars: int = 120,
    ) -> None:
        self._session_id = session_id
        self._on_text = on_text
        self._on_speak = on_speak
        self._sentence_buffer_chars = sentence_buffer_chars
        self._sentence_buffer: list[str] = []

    async def stream(
        self,
        token_stream: AsyncIterator,
        interrupt_event: asyncio.Event,
    ) -> tuple[str, bool]:
        """Consume an AI token stream and drive text + audio output.

        Args:
            token_stream: Async iterator yielding StreamChunk objects from AIGateway.
            interrupt_event: asyncio.Event set by InterruptManager on barge-in.

        Returns:
            Tuple of (full_response_text, was_interrupted).
        """
        full_response = ""
        was_interrupted = False

        try:
            async for chunk in token_stream:
                # Check for barge-in between tokens
                if interrupt_event.is_set():
                    was_interrupted = True
                    logger.info(
                        "AI stream interrupted",
                        session_id=self._session_id,
                        chars_generated=len(full_response),
                    )
                    break

                token = chunk.content
                if not token:
                    continue

                full_response += token

                # Send text token to WebSocket immediately
                await self._on_text(token)

                # Accumulate in sentence buffer
                self._sentence_buffer.append(token)

                # Check for flush conditions
                buffered_text = "".join(self._sentence_buffer)
                should_flush = (
                    _SENTENCE_END.search(token) is not None
                    or len(buffered_text) >= self._sentence_buffer_chars
                )

                if should_flush:
                    await self._flush_tts(buffered_text)

        except asyncio.CancelledError:
            was_interrupted = True
            logger.debug("ResponseStreamer cancelled", session_id=self._session_id)

        # Flush any remaining buffered text
        remaining = "".join(self._sentence_buffer)
        if remaining.strip() and not was_interrupted:
            await self._flush_tts(remaining)

        return full_response, was_interrupted

    async def _flush_tts(self, text: str) -> None:
        """Send buffered text to TTS and clear the buffer."""
        text = text.strip()
        if text:
            logger.debug(
                "Flushing TTS chunk",
                session_id=self._session_id,
                chars=len(text),
                preview=text[:60],
            )
            self._sentence_buffer.clear()
            try:
                # TTS runs concurrently — create a task so we don't block
                # the token stream while TTS is producing audio
                asyncio.create_task(
                    self._on_speak(text),
                    name=f"tts-speak-{self._session_id}",
                )
            except Exception as exc:
                logger.warning(
                    "TTS flush error",
                    session_id=self._session_id,
                    error=str(exc),
                )
        else:
            self._sentence_buffer.clear()
