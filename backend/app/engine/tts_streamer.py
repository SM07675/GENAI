"""TTS Streamer — streaming text-to-speech with sentence-level pipelining.

Accumulates LLM text tokens until a sentence boundary, then fires TTS
synthesis for that sentence immediately while the LLM continues generating.

Uses the existing Chatterbox TTS engine from ``app.tts``.
"""
from __future__ import annotations

import asyncio
import base64
import re
from typing import Awaitable, Callable, Optional

import structlog

from ..config import Settings, get_settings
from .. import tts as tts_module
from .cancellation import CancellationToken

log = structlog.get_logger("genie.engine.tts_streamer")

Emitter = Callable[[dict], Awaitable[None]]

# Sentence boundary regex
_SENTENCE_END_RE = re.compile(r'([.?!।]\s+|\n+)')


# Delivery cue regex (from orchestrator)
_CUE_RE = re.compile(r'\[\[(neutral|warm|cheerful|empathetic|apologetic|urgent|focused|reassuring)\]\]')

# Cue → orb gesture mapping
CUE_TO_GESTURE: dict[str, dict] = {
    "neutral":     {"color": "#06b6d4", "pulse": "slow",   "intensity": 0.5},
    "warm":        {"color": "#f59e0b", "pulse": "gentle", "intensity": 0.6},
    "cheerful":    {"color": "#14b8a6", "pulse": "quick",  "intensity": 0.8},
    "empathetic":  {"color": "#8b5cf6", "pulse": "slow",   "intensity": 0.4},
    "apologetic":  {"color": "#d97706", "pulse": "slow",   "intensity": 0.3},
    "urgent":      {"color": "#ef4444", "pulse": "fast",   "intensity": 0.9},
    "focused":     {"color": "#f8fafc", "pulse": "steady", "intensity": 0.5},
    "reassuring":  {"color": "#22c55e", "pulse": "slow",   "intensity": 0.5},
}


def _strip_markdown_for_tts(text: str) -> str:
    """Strip markdown artifacts and emotion tags before TTS."""
    s = text
    s = re.sub(r'\[\[[^\]]*\]\]', '', s)
    s = re.sub(r'\[\s*(neutral|warm|cheerful|empathetic|apologetic|urgent|focused|reassuring)\s*\]', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^#{1,6}\s+', '', s, flags=re.MULTILINE)
    s = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', s)
    s = re.sub(r'_{1,3}([^_]+)_{1,3}', r'\1', s)
    s = re.sub(r'^[\s]*[-*]\s+', '', s, flags=re.MULTILINE)
    s = re.sub(r'^\s*\d+\.\s+', '', s, flags=re.MULTILINE)
    s = re.sub(r'```[^`]*```', '', s, flags=re.DOTALL)
    s = re.sub(r'`([^`]+)`', r'\1', s)
    s = re.sub(r'https?://\S+', '', s)
    s = re.sub(r'\n{2,}', '. ', s)
    s = re.sub(r'\s{2,}', ' ', s)
    return s.strip()


def _extract_cue(text: str) -> tuple[str, str]:
    """Extract [[cue]] tag from text. Returns (cue, clean_text)."""
    cue = "neutral"
    for m in _CUE_RE.finditer(text):
        cue = m.group(1)
    clean = _CUE_RE.sub("", text)
    clean = re.sub(r'\[\s*(neutral|warm|cheerful|empathetic|apologetic|urgent|focused|reassuring)\s*\]', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\[\[?[^\]]*\]?\]?', '', clean)
    clean = re.sub(r'\s{2,}', ' ', clean).strip()
    return cue, clean


class TTSStreamer:
    """Streams TTS synthesis sentence-by-sentence.

    Feed it LLM text deltas via ``add_text()``. It accumulates tokens
    until a sentence boundary, then synthesizes and emits the audio
    for that sentence immediately.
    """

    def __init__(
        self,
        emit: Emitter,
        cancel_token: Optional[CancellationToken] = None,
        settings: Optional[Settings] = None,
    ):
        self._emit = emit
        self._cancel_token = cancel_token
        self._settings = settings or get_settings()

        self._buffer = ""
        self._sentence_seq = 0
        self._current_cue = "neutral"
        self._first_audio_emitted = False

        # Background tasks for parallel TTS synthesis
        self._tts_queue: asyncio.Queue = asyncio.Queue()
        self._consumer_task: Optional[asyncio.Task] = None
        self._background_tasks: set[asyncio.Task] = set()

        # Cache settings for this turn
        self._turn_settings = self._settings.model_copy()

    async def start(self) -> None:
        """Start the TTS consumer task."""
        self._consumer_task = asyncio.create_task(self._tts_consumer())

    async def add_text(self, delta: str) -> None:
        """Add a text delta from the LLM. Flushes complete sentences to TTS."""
        if self._cancel_token and self._cancel_token.is_cancelled:
            return

        self._buffer += delta

        # Check for sentence boundaries
        match = _SENTENCE_END_RE.search(self._buffer)
        while match:
            split_idx = match.end()
            raw_sentence = self._buffer[:split_idx].strip()

            if raw_sentence:
                cue, clean = _extract_cue(raw_sentence)
                if cue != "neutral":
                    self._current_cue = cue

                if clean:
                    await self._enqueue_sentence(clean, self._current_cue)

            self._buffer = self._buffer[split_idx:]
            match = _SENTENCE_END_RE.search(self._buffer)

    async def flush(self) -> None:
        """Flush any remaining text in the buffer as a final sentence."""
        if self._cancel_token and self._cancel_token.is_cancelled:
            await self._shutdown()
            return

        remaining = self._buffer.strip()
        if remaining:
            cue, clean = _extract_cue(remaining)
            if cue != "neutral":
                self._current_cue = cue
            if clean:
                await self._enqueue_sentence(clean, self._current_cue)

        self._buffer = ""

        # Signal consumer to stop
        await self._tts_queue.put(None)

        # Wait for all TTS to complete
        if self._consumer_task:
            try:
                await asyncio.wait_for(self._consumer_task, timeout=60.0)
            except asyncio.TimeoutError:
                log.error("tts_consumer_timeout")
                self._consumer_task.cancel()

        # Emit final signals
        if self._first_audio_emitted:
            await self._emit({"type": "assistant_audio_end"})
        await self._emit({"type": "tts_done"})

    async def cancel(self) -> None:
        """Cancel all pending TTS work."""
        log.info("tts_streamer_cancelled")
        await self._shutdown()
        await self._emit({"type": "tts_done"})

    async def _shutdown(self) -> None:
        """Clean up resources."""
        # Cancel all background synthesis tasks
        for t in self._background_tasks:
            t.cancel()
        self._background_tasks.clear()

        # Drain the queue
        while not self._tts_queue.empty():
            try:
                self._tts_queue.get_nowait()
                self._tts_queue.task_done()
            except asyncio.QueueEmpty:
                break

        # Stop consumer
        if self._consumer_task and not self._consumer_task.done():
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except (asyncio.CancelledError, Exception):
                pass

    async def _enqueue_sentence(self, text: str, cue: str) -> None:
        """Create a TTS synthesis task and enqueue it."""
        task = asyncio.create_task(self._synthesize(text, cue))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        await self._tts_queue.put((task, self._sentence_seq, cue))
        self._sentence_seq += 1

    async def _synthesize(self, text: str, cue: str) -> tuple[bytes, str, list]:
        """Run TTS synthesis for a single sentence."""
        cleaned = _strip_markdown_for_tts(text)
        if not cleaned.strip():
            return b"", "audio/wav", []
        return await tts_module.synthesize_with_mime(cleaned, self._turn_settings, cue=cue)

    async def _tts_consumer(self) -> None:
        """Consume TTS results from the queue and emit audio chunks."""
        while True:
            try:
                item = await asyncio.wait_for(self._tts_queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                log.error("tts_consumer_queue_timeout")
                break

            if item is None:
                self._tts_queue.task_done()
                break

            if self._cancel_token and self._cancel_token.is_cancelled:
                self._tts_queue.task_done()
                continue  # drain remaining items

            try:
                tts_task, seq, cue = item
                try:
                    audio, mime, word_timings = await asyncio.wait_for(tts_task, timeout=30.0)
                except asyncio.TimeoutError:
                    log.warning("tts_synthesis_timeout", seq=seq)
                    continue

                if audio:
                    if not self._first_audio_emitted:
                        await self._emit({"type": "orb_state", "state": "speaking"})
                        await self._emit({"type": "tts_playing"})
                        self._first_audio_emitted = True

                    # Send orb gesture
                    gesture = CUE_TO_GESTURE.get(cue, CUE_TO_GESTURE["neutral"])
                    await self._emit({
                        "type": "orb_gesture",
                        "cue": cue,
                        "gesture": gesture,
                    })

                    # Send audio chunk
                    await self._emit({
                        "type": "assistant_audio_chunk",
                        "audio": base64.b64encode(audio).decode("ascii"),
                        "mime": mime,
                        "seq": seq,
                    })

                    # Send word timings if available
                    if word_timings:
                        await self._emit({
                            "type": "word_timing",
                            "seq": seq,
                            "words": word_timings,
                        })

            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.warning("tts_chunk_error", error=str(exc))
            finally:
                self._tts_queue.task_done()
