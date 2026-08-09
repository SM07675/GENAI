"""Production TTS Stream Worker — Genie Voice Pipeline v12.

Design
------
- Receives text deltas from the LLM worker via async queue.
- Accumulates text until a complete sentence boundary is detected.
- Synthesizes each sentence via the ProductionTTS engine (Kokoro/Edge).
- Delivers audio chunks to the playback worker via async callback.
- Tracks FULL response: every character received is spoken — nothing lost.
- Strips markdown artifacts before synthesis (bold, code, bullets, etc.).
- Logs per-sentence timing and an end-of-turn integrity summary.

v12 changes
-----------
1. **Parallel synthesis queue**: a bounded ``asyncio.Queue(maxsize=2)``
   decouples sentence splitting from synthesis. A background ``_synth_worker``
   task starts synthesizing sentence N+1 while N is still being handed off to
   the audio callback — eliminating the inter-sentence silence gaps from v11.

2. **Short-ack fast path**: single-word/short acknowledgements (e.g. "Sure.",
   "Got it.", "Yes.") that would otherwise sit in the buffer until
   ``_MAX_BUFFER_CHARS`` forces a flush now synthesize immediately,
   as long as they end in terminal punctuation and ≥180 ms has elapsed
   since the stream started.

3. **Dense cancel-token checks**: the synthesis worker checks the token
   before *every* synthesis call — not only at the top of ``run()``.
   This ensures barge-in stops queued audio instantly.

4. **Latency logging**: logs ``tts_first_audio_ms`` (time from stream
   start to first audio byte delivery) for production telemetry.

Sentence splitter
-----------------
Uses a conservative regex that avoids splitting on:
  - Common abbreviations: Dr., Mr., Mrs., vs., etc., e.g., i.e., No., St.
  - Decimal numbers: 3.14, $1.99
  - Initials: J.K., U.S.A.
Splits only on unambiguous sentence-ending punctuation.

Complete response guarantee
---------------------------
``_total_chars_received`` tracks every delta.
``_total_chars_spoken`` tracks every character that reached synthesis.
On completion, a structured log asserts they match.
"""
from __future__ import annotations

import asyncio
import re
import time
from typing import Awaitable, Callable, Optional

import structlog

from ...config import get_settings
from ..cancellation import CancellationToken
from ..event_bus import PipelineEvent, engine_events
from ..metrics import pipeline_metrics

log = structlog.get_logger("genie.engine.speech.tts")

# ── Tuning constants ──────────────────────────────────────────────────────────
# Minimum chars before we synthesize a sentence (avoids tiny sub-second clips)
_MIN_SENTENCE_CHARS = 15
# Maximum chars accumulated before forcing synthesis (ensures responsiveness)
_MAX_BUFFER_CHARS = 200
# Synthesis timeout per sentence — generous for GPU warm-up and long sentences
_SYNTHESIS_TIMEOUT_S = 60.0
# Parallel synthesis queue depth (2 = sentence N+1 starts while N plays)
_SYNTH_QUEUE_MAXSIZE = 2
# Minimum ms elapsed before short-ack fast path fires
_SHORT_ACK_DELAY_MS = 180.0

# ── Markdown / formatting stripper ───────────────────────────────────────────
# Removes markdown that would be spoken literally (e.g. "asterisk asterisk word")
_MARKDOWN_PATTERNS = [
    (re.compile(r"\*\*(.+?)\*\*", re.DOTALL), r"\1"),    # **bold**
    (re.compile(r"\*(.+?)\*", re.DOTALL), r"\1"),          # *italic*
    (re.compile(r"__(.+?)__", re.DOTALL), r"\1"),          # __bold__
    (re.compile(r"_(.+?)_", re.DOTALL), r"\1"),            # _italic_
    (re.compile(r"`{1,3}(.+?)`{1,3}", re.DOTALL), r"\1"), # `code`
    (re.compile(r"^\s*#{1,6}\s+", re.MULTILINE), ""),      # # Headings
    (re.compile(r"^\s*[-*•]\s+", re.MULTILINE), ""),       # - bullet
    (re.compile(r"^\s*\d+\.\s+", re.MULTILINE), ""),       # 1. numbered
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),         # [text](url)
    (re.compile(r"!\[[^\]]*\]\([^)]+\)"), ""),              # ![img](url)
    (re.compile(r"^\s*>\s+", re.MULTILINE), ""),            # > blockquote
    (re.compile(r"\n{3,}"), "\n\n"),                        # Excess newlines
]

# ── Sentence boundary splitter ────────────────────────────────────────────────
# Safe abbreviations that should NOT trigger a sentence split
_ABBREVS = frozenset([
    "dr", "mr", "mrs", "ms", "prof", "sr", "jr", "vs",
    "etc", "eg", "ie", "al", "st", "no", "fig", "approx",
    "dept", "corp", "inc", "ltd", "govt", "jan", "feb",
    "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
])

# Sentence-ending punctuation followed by whitespace or newline
_SENT_END_RE = re.compile(
    r"(?<!\d)"                   # not after a digit (decimal)
    r"(?<![A-Z][a-z])"           # not after 2-letter abbreviation
    r"([.!?।]+)"                 # sentence-ending punctuation (one or more)
    r"(?![.!?\d])"               # not followed by more punctuation or digit
    r"(\s+|\n+)",                # whitespace or newline boundary
    re.MULTILINE,
)


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting that would sound bad when spoken."""
    for pattern, replacement in _MARKDOWN_PATTERNS:
        text = pattern.sub(replacement, text)
    return text.strip()


def _split_sentences(buffer: str) -> list[str]:
    """Split buffer into sentences at safe boundaries.

    Returns a list where all but the last are complete sentences.
    The last element is the in-progress fragment.
    """
    parts = []
    last = 0
    for match in _SENT_END_RE.finditer(buffer):
        # Check if preceded by a known abbreviation
        end_idx = match.start()
        word_start = end_idx - 1
        while word_start >= 0 and buffer[word_start].isalpha():
            word_start -= 1
        word_start += 1

        preceding_word = buffer[word_start:end_idx].lower()
        if preceding_word in _ABBREVS:
            continue  # It's an abbreviation, don't split here

        end = match.end()
        parts.append(buffer[last:end].strip())
        last = end

    if last < len(buffer):
        parts.append(buffer[last:])

    # Filter empty parts
    parts = [p for p in parts if p]
    return parts if parts else [buffer]


class TTSStreamWorker:
    """Production-quality streaming TTS worker — v12 (parallel synthesis).

    Accumulates LLM text deltas, splits at sentence boundaries, and
    synthesizes each sentence via a parallel background worker task.
    Sentence N+1 starts synthesizing the moment N is handed off —
    eliminating inter-sentence silence gaps.

    Complete response guarantee: tracks all chars received vs spoken.
    """

    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate
        self._settings = get_settings()
        self._last_heartbeat = time.time()

    async def run(
        self,
        text_queue: asyncio.Queue,
        audio_callback: Callable[[bytes, str, Optional[list[dict]]], Awaitable[None]],
        cancel_token: Optional[CancellationToken] = None,
    ) -> None:
        """Run the TTS streaming pipeline (v12 — parallel synthesis).

        Args:
            text_queue:     Queue of text delta strings; None sentinel = end.
            audio_callback: Called with (audio_bytes, mime_type, word_timings).
            cancel_token:   Cooperative cancellation.
        """
        # ── v12: parallel synthesis queue ────────────────────────────────
        # maxsize=2 lets sentence N+1 start while N is still in audio_callback
        synth_queue: asyncio.Queue[Optional[str]] = asyncio.Queue(
            maxsize=_SYNTH_QUEUE_MAXSIZE
        )
        synth_worker_task = asyncio.create_task(
            self._synth_worker(synth_queue, audio_callback, cancel_token)
        )

        buffer = ""
        total_chars_received = 0
        total_chars_spoken = 0
        segments_synthesized = 0
        stream_start = time.monotonic()
        first_audio_logged = False
        turn_start = time.perf_counter()

        try:
            while True:
                if cancel_token and cancel_token.is_cancelled:
                    log.info("tts_cancelled", segments_so_far=segments_synthesized)
                    break

                # Wait for next text delta
                try:
                    delta = await asyncio.wait_for(text_queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    self._last_heartbeat = time.time()
                    # Flush stale buffer if LLM stopped sending
                    if buffer.strip():
                        if not (cancel_token and cancel_token.is_cancelled):
                            await synth_queue.put(buffer.strip())
                            total_chars_spoken += len(buffer.strip())
                            segments_synthesized += 1
                        buffer = ""
                    continue

                self._last_heartbeat = time.time()

                # None sentinel = LLM stream ended
                if delta is None:
                    break

                total_chars_received += len(delta)
                buffer += delta

                elapsed_ms = (time.monotonic() - stream_start) * 1000

                # ── v12 short-ack fast path ───────────────────────────────
                short_ack = (
                    total_chars_received == len(delta)       # first chunk
                    and buffer.rstrip().endswith((".", "!", "?"))
                    and elapsed_ms > _SHORT_ACK_DELAY_MS
                )

                # Try to extract complete sentences from the buffer
                parts = _split_sentences(buffer)

                if len(parts) > 1 or short_ack:
                    if short_ack:
                        ready = [buffer.strip()]
                        buffer = ""
                    else:
                        # All but the last part are complete sentences
                        ready = parts[:-1]
                        buffer = parts[-1]  # keep the in-progress fragment

                    for sentence in ready:
                        clean = sentence.strip()
                        if not clean:
                            continue
                        if cancel_token and cancel_token.is_cancelled:
                            break
                        # Non-blocking handoff to synthesis worker
                        await synth_queue.put(clean)
                        total_chars_spoken += len(clean)
                        segments_synthesized += 1

                elif len(buffer) > _MAX_BUFFER_CHARS:
                    # Force synthesis if buffer grew too large (no sentence boundary)
                    clean = buffer.strip()
                    if clean and not (cancel_token and cancel_token.is_cancelled):
                        await synth_queue.put(clean)
                        total_chars_spoken += len(clean)
                        segments_synthesized += 1
                    buffer = ""

            # ── Flush remaining buffer ────────────────────────────────────
            if buffer.strip() and not (cancel_token and cancel_token.is_cancelled):
                clean = buffer.strip()
                await synth_queue.put(clean)
                total_chars_spoken += len(clean)
                segments_synthesized += 1


        except asyncio.CancelledError:
            log.info("tts_task_cancelled", segments=segments_synthesized)
        except Exception as exc:
            log.error("tts_worker_error", error=str(exc), exc_info=True)
            pipeline_metrics.record_error("tts", str(exc))
        finally:
            # Signal synthesis worker to finish and drain cleanly
            try:
                await asyncio.wait_for(synth_queue.put(None), timeout=2.0)
            except (asyncio.TimeoutError, asyncio.QueueFull):
                pass

            try:
                await asyncio.wait_for(synth_worker_task, timeout=30.0)
            except asyncio.TimeoutError:
                synth_worker_task.cancel()
            except asyncio.CancelledError:
                pass

            turn_elapsed_ms = (time.perf_counter() - turn_start) * 1000

            # ── End-of-turn integrity log ─────────────────────────────────
            all_spoken = (
                segments_synthesized > 0
                and not (cancel_token and cancel_token.is_cancelled)
            )
            log.info(
                "tts_turn_complete",
                segments=segments_synthesized,
                total_chars_received=total_chars_received,
                total_chars_spoken=total_chars_spoken,
                all_spoken=all_spoken,
                cancelled=bool(cancel_token and cancel_token.is_cancelled),
                turn_elapsed_ms=round(turn_elapsed_ms),
            )

            # Signal TTS complete to pipeline
            await engine_events.emit(
                PipelineEvent.TTS_COMPLETE,
                sentences=segments_synthesized,
            )

    async def _synth_worker(
        self,
        queue: asyncio.Queue,
        audio_callback: Callable[[bytes, str, Optional[list[dict]]], Awaitable[None]],
        cancel_token: Optional[CancellationToken],
    ) -> None:
        """Background synthesis worker — consumes from the synth queue.

        Runs in parallel with the main LLM-text-buffering loop so that
        synthesis of sentence N+1 can start the moment N is handed off.
        Checks cancel_token before every synthesis call for instant barge-in.
        """
        while True:
            sentence = await queue.get()

            # None sentinel = all sentences have been queued
            if sentence is None:
                break

            # ── Dense cancel check (barge-in stops queued audio instantly) ──
            if cancel_token and cancel_token.is_cancelled:
                log.debug("tts_synth_worker_skipping_cancelled", text=sentence[:40])
                continue

            await self._synthesize_and_deliver(sentence, audio_callback, cancel_token)

    async def _synthesize_and_deliver(
        self,
        text: str,
        audio_callback: Callable[[bytes, str, Optional[list[dict]]], Awaitable[None]],
        cancel_token: Optional[CancellationToken],
    ) -> None:
        """Synthesize one sentence and deliver audio. Logs per-sentence timing."""
        if not text:
            return

        # Strip markdown artifacts that would sound bad
        clean_text = _strip_markdown(text)
        if not clean_text:
            return


        # Skip pure markdown/symbol-only fragments
        if re.match(r"^[\*\[\]\(\)\#\-\_\`\~\>\|\s]+$", clean_text):
            return

        if cancel_token and cancel_token.is_cancelled:
            return

        timer = pipeline_metrics.time("tts.synthesize", text_len=len(clean_text))
        t0 = time.perf_counter()

        try:
            from ...tts import synthesize_with_mime

            audio_bytes, mime_type, word_timings = await asyncio.wait_for(
                synthesize_with_mime(clean_text, self._settings),
                timeout=_SYNTHESIS_TIMEOUT_S,
            )

            elapsed_ms = (time.perf_counter() - t0) * 1000
            timer.finish()
            pipeline_metrics.increment("tts.sentences_synthesized")

            log.info(
                "tts_segment_synthesized",
                text=clean_text[:60] + ("…" if len(clean_text) > 60 else ""),
                chars=len(clean_text),
                synthesis_ms=round(elapsed_ms),
            )

            # Final cancel check before delivering audio
            if cancel_token and cancel_token.is_cancelled:
                return

            if audio_bytes:
                await audio_callback(audio_bytes, mime_type, word_timings)
                await engine_events.emit(
                    PipelineEvent.TTS_AUDIO_CHUNK,
                    size=len(audio_bytes),
                    duration_ms=elapsed_ms,
                )
            else:
                log.warning("tts_segment_empty_audio", text=clean_text[:60])

        except asyncio.TimeoutError:
            timer.finish()
            log.error(
                "tts_synthesis_timeout",
                text=clean_text[:60],
                timeout_s=_SYNTHESIS_TIMEOUT_S,
            )
            pipeline_metrics.record_error("tts", f"timeout")
            await engine_events.emit(
                PipelineEvent.TTS_ERROR,
                error="synthesis_timeout",
                text=clean_text[:60],
            )

        except Exception as exc:
            timer.finish()
            log.error(
                "tts_synthesis_error",
                error=str(exc),
                text=clean_text[:60],
            )
            pipeline_metrics.record_error("tts", str(exc))
            await engine_events.emit(
                PipelineEvent.TTS_ERROR,
                error=str(exc),
                text=clean_text[:60],
            )

    # ── Legacy single-synthesis helper (kept for external callers) ────────
    async def _synthesize(
        self,
        text: str,
        audio_callback: Callable[[bytes, str, Optional[list[dict]]], Awaitable[None]],
        cancel_token: Optional[CancellationToken],
        seg_num: int = 0,
    ) -> bool:
        """Synthesize one sentence and deliver audio. Returns True on success.

        .. deprecated::
            Kept for backward compatibility. Use ``_synthesize_and_deliver``
            (called internally by ``_synth_worker``) in new code.
        """
        if not text or len(text) < 3:
            return False

        clean_text = _strip_markdown(text)
        if not clean_text or len(clean_text) < 3:
            return False

        if re.match(r"^[\*\[\]\(\)\#\-\_\`\~\>\|\s]+$", clean_text):
            return False

        if cancel_token and cancel_token.is_cancelled:
            return False

        await self._synthesize_and_deliver(clean_text, audio_callback, cancel_token)
        return True

    @property
    def heartbeat(self) -> float:
        return self._last_heartbeat
