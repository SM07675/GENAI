"""The conversation orchestrator: Gemini ReAct loop with tool calling.

Voice delivery pipeline
-----------------------
1. Gemini streams text deltas.
2. Sentence boundaries are detected (`. ` / `? ` / `! `).
3. **Delivery cue tags** ([[warm]], [[urgent]], etc.) are parsed per sentence.
4. Cue is stripped from the text delta sent to the client AND the text sent to TTS.
5. Cue drives: Edge TTS prosody (rate/volume), orb gesture color, and
   (optionally, Phase 2) ElevenLabs v3 audio tags.
6. TTS generates audio and word-timing events per sentence.
7. Audio chunks + word timings are emitted to the client as they complete,
   not after the full response — so the user hears sentence 1 while Gemini
   is generating sentence 3.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import secrets
from pathlib import Path
from typing import Any, Awaitable, Callable

import structlog

from . import tts as tts_module
from . import stt, llm_client
from .auth import Session
from .config import Settings, get_settings
from .tools import TOOL_SCHEMAS, execute_tool

_stdlib_log = logging.getLogger("genie.orchestrator")

Emitter = Callable[[dict], Awaitable[None]]

MAX_TOOL_ITERATIONS = 8

_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.md"
_SYSTEM_PROMPT_CACHE: str | None = None

# Keep only the last N user+assistant turns in history.
# ~6 exchanges — prompt governs how much the model references, not this cap.
MAX_HISTORY_TURNS = 12


def load_system_prompt() -> str:
    global _SYSTEM_PROMPT_CACHE
    if _SYSTEM_PROMPT_CACHE is not None:
        return _SYSTEM_PROMPT_CACHE
    try:
        _SYSTEM_PROMPT_CACHE = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        _stdlib_log.warning("system_prompt.md missing; using minimal prompt.")
        _SYSTEM_PROMPT_CACHE = "You are Genie, a helpful assistant."
    return _SYSTEM_PROMPT_CACHE


def _trim_history(history: list[dict]) -> list[dict]:
    ua = [m for m in history if m.get("role") in ("user", "assistant")]
    if len(ua) <= MAX_HISTORY_TURNS:
        return history
    cutoff_ua = ua[-(MAX_HISTORY_TURNS):]
    for i, m in enumerate(history):
        if m is cutoff_ua[0]:
            return history[i:]
    return history[-(MAX_HISTORY_TURNS * 3):]


# ── Delivery cue parsing ─────────────────────────────────────────────────────

# The LLM emits [[cue]] tags inline. We parse and strip them.
_CUE_RE = re.compile(r'\[\[(neutral|warm|cheerful|empathetic|apologetic|urgent|focused|reassuring)\]\]')

# Mapping from cue → orb gesture (sent to frontend for visual state)
CUE_TO_GESTURE: dict[str, dict[str, Any]] = {
    "neutral":     {"color": "#06b6d4", "pulse": "slow",   "intensity": 0.5},
    "warm":        {"color": "#f59e0b", "pulse": "gentle", "intensity": 0.6},
    "cheerful":    {"color": "#14b8a6", "pulse": "quick",  "intensity": 0.8},
    "empathetic":  {"color": "#8b5cf6", "pulse": "slow",   "intensity": 0.4},
    "apologetic":  {"color": "#d97706", "pulse": "slow",   "intensity": 0.3},
    "urgent":      {"color": "#ef4444", "pulse": "fast",   "intensity": 0.9},
    "focused":     {"color": "#f8fafc", "pulse": "steady", "intensity": 0.5},
    "reassuring":  {"color": "#22c55e", "pulse": "slow",   "intensity": 0.5},
}


def extract_cue(text: str) -> tuple[str, str]:
    """Extract the last [[cue]] from text and return (cue, clean_text).

    If no cue is found, returns ("neutral", text).
    """
    cue = "neutral"
    for m in _CUE_RE.finditer(text):
        cue = m.group(1)
    clean = _CUE_RE.sub("", text).strip()
    # Collapse any double spaces left behind by cue removal
    clean = re.sub(r'\s{2,}', ' ', clean)
    return cue, clean


# ── Markdown stripping for TTS ────────────────────────────────────────────────

def _strip_markdown_for_tts(text: str) -> str:
    """Strip markdown artifacts before text reaches the TTS engine."""
    s = text
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


# ── Main turn handler ─────────────────────────────────────────────────────────

async def handle_user_turn(
    session: Session,
    user_text: str,
    emit: Emitter,
    settings: Settings | None = None,
) -> None:
    """Run one full user → assistant turn (possibly many tool calls)."""
    settings = settings or get_settings()
    text = (user_text or "").strip()
    if not text:
        await emit({"type": "error", "message": "I didn't catch that.", "code": "empty_input"})
        return

    request_id = secrets.token_hex(6)
    log = structlog.get_logger("genie.orchestrator").bind(
        session_id=session.session_id,
        request_id=request_id,
    )

    from .conversation_manager import conversation_manager
    context = conversation_manager.get_context(session.session_id)
    resolved_text = context.resolve_references(text)

    is_hindi = bool(re.search(r'[\u0900-\u097F]', resolved_text))
    lang_tag = "[Language: Hindi/Hinglish] " if is_hindi else "[Language: English] "
    tagged_text = lang_tag + resolved_text

    session.history.append({"role": "user", "content": tagged_text})

    system_prompt = load_system_prompt()
    context_summary = context.get_context_summary()
    full_prompt = system_prompt + "\n" + context_summary if context_summary else system_prompt

    messages = [{"role": "system", "content": full_prompt}] + _trim_history(session.history)

    await emit({"type": "orb_state", "state": "thinking"})

    log.info("turn_start", user_text_length=len(text))

    final_answer_parts: list[str] = []
    tts_queue = asyncio.Queue()
    first_chunk_emitted = False
    any_tools_used = False
    tool_calls_in_turn: list[dict] = []
    background_tasks: set[asyncio.Task] = set()
    current_cue = "neutral"
    sentence_seq = 0

    async def tts_consumer() -> None:
        """Consume TTS tasks from the queue, emit audio + word timings."""
        nonlocal first_chunk_emitted
        while True:
            item = await tts_queue.get()
            if item is None:
                break
            try:
                tts_task, seq, cue = item
                audio, mime, word_timings = await tts_task
                if audio:
                    if not first_chunk_emitted:
                        await emit({"type": "orb_state", "state": "speaking"})
                        first_chunk_emitted = True
                    # Send orb gesture for this sentence's cue
                    gesture = CUE_TO_GESTURE.get(cue, CUE_TO_GESTURE["neutral"])
                    await emit({
                        "type": "orb_gesture",
                        "cue": cue,
                        "gesture": gesture,
                    })
                    await emit({
                        "type": "assistant_audio_chunk",
                        "audio": base64.b64encode(audio).decode("ascii"),
                        "mime": mime,
                        "seq": seq,
                    })
                    # Send word timing data if available (Edge TTS only)
                    if word_timings:
                        await emit({
                            "type": "word_timing",
                            "seq": seq,
                            "words": word_timings,
                        })
            except asyncio.CancelledError:
                raise
            except Exception as tts_exc:  # noqa: BLE001
                log.warning("tts_chunk_failed", error=str(tts_exc))
            finally:
                tts_queue.task_done()

    consumer_task = asyncio.create_task(tts_consumer())

    async def generate_tts(text_chunk: str, cue: str, is_long_task: bool) -> tuple[bytes, str, list[dict]]:
        cleaned = _strip_markdown_for_tts(text_chunk)
        if not cleaned.strip():
            return b"", "audio/mpeg", []
        turn_settings = settings.model_copy()
        if turn_settings.tts_engine == "auto":
            turn_settings.tts_engine = "edge" if is_long_task else "elevenlabs"
        return await tts_module.synthesize_with_mime(cleaned, turn_settings, cue=cue)

    try:
        for iteration in range(MAX_TOOL_ITERATIONS):
            tool_calls_made = False
            iteration_text: list[str] = []
            sentence_buffer = ""

            async for event in llm_client.stream_chat(
                messages=messages, tools=TOOL_SCHEMAS, settings=settings
            ):
                etype = event["type"]

                if etype == "text_delta":
                    delta = event["delta"]
                    iteration_text.append(delta)

                    # Parse cue tags before sending delta to frontend
                    cue_in_delta, clean_delta = extract_cue(delta)
                    if cue_in_delta != "neutral":
                        current_cue = cue_in_delta

                    # Send CLEAN delta to the client (no [[cue]] tags visible)
                    if clean_delta:
                        final_answer_parts.append(clean_delta)
                        await emit({"type": "assistant_text", "delta": clean_delta, "final": False})

                    # Accumulate raw text for sentence boundary detection
                    sentence_buffer += delta
                    match = re.search(r'([.?!।]\s+)', sentence_buffer)
                    while match:
                        split_idx = match.end()
                        raw_sentence = sentence_buffer[:split_idx].strip()
                        if raw_sentence:
                            # Extract cue from the full sentence for TTS prosody
                            sent_cue, clean_sentence = extract_cue(raw_sentence)
                            if sent_cue != "neutral":
                                current_cue = sent_cue
                            if clean_sentence:
                                task = asyncio.create_task(
                                    generate_tts(clean_sentence, current_cue, any_tools_used)
                                )
                                background_tasks.add(task)
                                task.add_done_callback(background_tasks.discard)
                                await tts_queue.put((task, sentence_seq, current_cue))
                                sentence_seq += 1
                        sentence_buffer = sentence_buffer[split_idx:]
                        match = re.search(r'([.?!।]\s+)', sentence_buffer)

                elif etype == "tool_call":
                    tool_calls_made = True
                    any_tools_used = True
                    tool_calls_in_turn.append(event)
                    await _run_tool_call(event, session, messages, emit, settings, log)

            if not tool_calls_made:
                break

            if iteration == MAX_TOOL_ITERATIONS - 1:
                log.warning("tool_iteration_cap_reached", max=MAX_TOOL_ITERATIONS)

        # Flush remaining sentence buffer
        if sentence_buffer.strip():
            sent_cue, clean_remaining = extract_cue(sentence_buffer.strip())
            if sent_cue != "neutral":
                current_cue = sent_cue
            if clean_remaining:
                task = asyncio.create_task(
                    generate_tts(clean_remaining, current_cue, any_tools_used)
                )
                background_tasks.add(task)
                task.add_done_callback(background_tasks.discard)
                await tts_queue.put((task, sentence_seq, current_cue))
                sentence_seq += 1

        final_text = "".join(final_answer_parts).strip()
        await emit({"type": "assistant_text", "delta": "", "final": True})

        # Wait for all pipelined TTS chunks to finish
        await tts_queue.put(None)
        await consumer_task

        if first_chunk_emitted or (not tool_calls_made and final_text):
            await emit({"type": "assistant_audio_end"})

        if final_text:
            messages.append({"role": "assistant", "content": final_text})

        session.history = [m for m in messages if m.get("role") != "system"]
        context.update_context(text, tool_calls_in_turn)

        log.info("turn_end", response_length=len(final_text), tools_used=len(tool_calls_in_turn))
        await emit({"type": "orb_state", "state": "idle"})

    except asyncio.CancelledError:
        log.info("turn_cancelled")
        consumer_task.cancel()
        for t in background_tasks:
            t.cancel()
        raise

    except Exception as exc:
        log.exception("turn_error", error_type=type(exc).__name__, error=str(exc))
        consumer_task.cancel()
        for t in background_tasks:
            t.cancel()
        await emit({
            "type": "error",
            "message": "Something went wrong on my end. Please try again.",
            "code": type(exc).__name__,
        })
        await emit({"type": "orb_state", "state": "idle"})


async def _run_tool_call(
    event: dict,
    session: Session,
    messages: list[dict],
    emit: Emitter,
    settings: Settings,
    log: Any = None,
) -> None:
    """Execute a single finalised tool call and append its result to context."""
    name = event.get("name") or "<unknown>"
    args = event.get("arguments") or {}
    call_id = event.get("id") or name

    if log:
        log.info("tool_start", tool=name, args=args)

    await emit({"type": "tool_start", "name": name, "args": args})

    try:
        result = await asyncio.to_thread(execute_tool, name, args)
    except Exception as exc:  # noqa: BLE001
        from .schemas import ToolResult as TR
        result = TR(status="error", message=f"Tool '{name}' raised unexpectedly: {exc}")

    if log:
        log.info("tool_end", tool=name, status=result.status)

    await emit({"type": "tool_end", "name": name, "result": result.model_dump()})

    # Intercept media commands
    action = result.data.get("action")
    if action == "play_media":
        media_msg = {"type": "play_media"}
        if "video_id" in result.data:
            media_msg["video_id"] = result.data["video_id"]
        if "playlist_id" in result.data:
            media_msg["playlist_id"] = result.data["playlist_id"]
        await emit(media_msg)
    elif action == "stop_media":
        await emit({"type": "stop_media"})

    messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        ],
    })

    if result.data.get("vision"):
        await _handle_vision_result(result, messages, settings)
    else:
        messages.append({
            "role": "tool",
            "tool_call_id": call_id,
            "name": name,
            "content": result.message,
        })


async def _handle_vision_result(result: Any, messages: list[dict], settings: Settings) -> None:
    data = result.data
    try:
        answer = await llm_client.vision_describe(
            image_base64=data["image_base64"],
            image_mime=data["image_mime"],
            question=data.get("question") or "Describe what's on screen.",
            settings=settings,
        )
    except Exception as exc:  # noqa: BLE001
        _stdlib_log.warning("Vision call failed: %s", exc)
        answer = f"I captured the screen but couldn't analyze it: {exc}"

    messages.append({
        "role": "tool",
        "tool_call_id": "screen_vision",
        "name": "capture_screen",
        "content": answer,
    })
