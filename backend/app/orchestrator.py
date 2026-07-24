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
from .core.context.peak_context import build_peak_context_packet, record_turn_memory
from .tools import TOOL_SCHEMAS, execute_tool

_stdlib_log = logging.getLogger("genie.orchestrator")

Emitter = Callable[[dict], Awaitable[None]]

MAX_TOOL_ITERATIONS = 8
TOOL_RESULT_CONTENT_LIMIT = 12000

_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.md"
_SYSTEM_PROMPT_CACHE: str | None = None

# Keep only the last N user+assistant turns in history.
# ~6 exchanges — prompt governs how much the model references, not this cap.
MAX_HISTORY_TURNS = 12

# Wake phrases to strip from the start of user input before sending to LLM
_WAKE_PHRASES = [
    "hey genie", "okay genie", "ok genie", "hi genie", "hello genie",
    "hey genie,", "okay genie,", "ok genie,", "hi genie,", "hello genie,",
]


def _strip_wake_phrase(text: str) -> str:
    """Remove wake phrase from the start of the user's utterance.

    Examples:
      'Hey Genie, open YouTube'  → 'open YouTube'
      'Hey Genie explain AI'     → 'explain AI'
      'Hey Genie'                → '' (caller must handle empty)
    """
    t = text.strip()
    lower = t.lower()
    for phrase in _WAKE_PHRASES:
        if lower.startswith(phrase):
            t = t[len(phrase):].lstrip(", ").strip()
            break
    return t


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
        trimmed = history
    else:
        cutoff_ua = ua[-(MAX_HISTORY_TURNS):]
        trimmed = history
        for i, m in enumerate(history):
            if m is cutoff_ua[0]:
                trimmed = history[i:]
                break
        else:
            trimmed = history[-(MAX_HISTORY_TURNS * 3):]
    return _sanitize_history_for_gemini(trimmed)


def _sanitize_history_for_gemini(history: list[dict]) -> list[dict]:
    """Remove orphaned tool_calls/tool messages that cause Gemini 400 errors.

    Gemini requires: tool_call assistant msg → immediately followed by tool response.
    If a turn was cancelled or interrupted, the assistant tool_call msg may have
    no matching tool response, causing: 'function call turn comes immediately after
    a user turn'. This strips any such orphaned pairs from history.
    """
    cleaned: list[dict] = []
    i = 0
    while i < len(history):
        msg = history[i]
        role = msg.get("role")

        # Assistant message with tool_calls — must be followed by tool responses
        if role == "assistant" and msg.get("tool_calls"):
            # Collect all consecutive tool-response messages that follow
            j = i + 1
            tool_responses: list[dict] = []
            while j < len(history) and history[j].get("role") == "tool":
                tool_responses.append(history[j])
                j += 1

            if tool_responses:
                # Valid pair — keep both
                cleaned.append(msg)
                cleaned.extend(tool_responses)
            # else: orphaned tool_call — drop it entirely
            i = j
            continue

        # Orphaned standalone tool response (no preceding assistant tool_call)
        if role == "tool":
            i += 1
            continue

        cleaned.append(msg)
        i += 1

    return cleaned


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
    clean = _CUE_RE.sub("", text)
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


def _tool_result_content(result: Any) -> str:
    """Serialize tool output for the next model step.

    The model needs structured result data for web/news summaries and for
    fallback instructions such as suggestion=open_url. Keep it bounded so a
    noisy API response cannot balloon the next prompt.
    """
    payload = {
        "status": result.status,
        "message": result.message,
        "data": result.data,
    }
    try:
        content = json.dumps(payload, ensure_ascii=False, default=str)
    except TypeError:
        content = json.dumps(
            {"status": result.status, "message": result.message, "data": {}},
            ensure_ascii=False,
        )
    if len(content) > TOOL_RESULT_CONTENT_LIMIT:
        content = content[:TOOL_RESULT_CONTENT_LIMIT] + "... [truncated]"
    return content


async def _maybe_open_suggested_url(result: Any, emit: Emitter, log: Any = None) -> Any:
    """Execute a tool-provided open_url fallback when one is explicitly offered."""
    if result.status != "not_found":
        return result

    data = result.data or {}
    if data.get("suggestion") != "open_url" or not data.get("url"):
        return result

    fallback_args = {"url": str(data["url"])}
    if log:
        log.info("tool_fallback_start", tool="open_url", args=fallback_args)
    await emit({"type": "tool_start", "name": "open_url", "args": fallback_args})

    try:
        fallback = await asyncio.to_thread(execute_tool, "open_url", fallback_args)
    except Exception as exc:  # noqa: BLE001
        from .schemas import ToolResult as TR
        fallback = TR(status="error", message=f"Fallback open_url failed: {exc}")

    if log:
        log.info("tool_fallback_end", tool="open_url", status=fallback.status)
    await emit({"type": "tool_end", "name": "open_url", "result": fallback.model_dump()})

    merged_data = {
        **data,
        "fallback_tool": "open_url",
        "fallback_result": fallback.model_dump(),
    }
    if fallback.status == "ok":
        return result.model_copy(update={
            "status": "ok",
            "message": fallback.message,
            "data": merged_data,
        })
    return result.model_copy(update={"data": merged_data})


# ── Main turn handler ─────────────────────────────────────────────────────────

async def handle_user_turn(
    session: Session,
    user_text: str,
    emit: Emitter,
    settings: Settings | None = None,
    cancel_token=None,
    skip_wake_strip: bool = False,
) -> None:
    """Run one full user → assistant turn (possibly many tool calls).

    Args:
        cancel_token: Optional CancellationToken from the conversation engine.
                      If set, workers abort at safe checkpoints.
        skip_wake_strip: If True, skip wake phrase removal (already done by pipeline).
    """
    settings = settings or get_settings()
    text = (user_text or "").strip()

    # Strip wake phrase (unless the pipeline already did it — audit fix #21)
    if not skip_wake_strip:
        text = _strip_wake_phrase(text)

    if not text:
        # User said only "Hey Genie" with nothing after — acknowledge and wait
        await emit({"type": "assistant_text", "delta": "Yes, I'm listening.", "final": True})
        ack_audio, ack_mime, _ = await tts_module.synthesize_with_mime("Yes, I'm listening.", settings)
        if ack_audio:
            await emit({"type": "orb_state", "state": "speaking"})
            await emit({"type": "tts_playing"})
            await emit({
                "type": "assistant_audio_chunk",
                "audio": base64.b64encode(ack_audio).decode("ascii"),
                "mime": ack_mime,
                "seq": 0,
            })
            await emit({"type": "assistant_audio_end"})
        await emit({"type": "tts_done"})
        await emit({"type": "orb_state", "state": "idle"})
        return

    request_id = secrets.token_hex(6)
    log = structlog.get_logger("genie.orchestrator").bind(
        session_id=session.session_id,
        request_id=request_id,
    )

    # Cancellation token — check at safe points to abort if interrupted
    _cancel = cancel_token

    from .conversation_manager import conversation_manager
    context = conversation_manager.get_context(session.session_id)
    resolved_text = context.resolve_references(text)
    
    is_hindi = bool(re.search(r'[\u0900-\u097F]', resolved_text))
    lang_tag = "[Language: Hindi/Hinglish] " if is_hindi else "[Language: English] "
    tagged_text = lang_tag + resolved_text

    session.history.append({"role": "user", "content": tagged_text})
    
    # Local intent routing is now handled by the engine's IntentAnalyzer.
    # The orchestrator only handles full LLM-routed turns.

    system_prompt = load_system_prompt()
    context_summary = context.get_context_summary()
    peak_context = build_peak_context_packet(resolved_text, session.session_id)
    full_prompt_parts = [system_prompt]
    if context_summary:
        full_prompt_parts.append(context_summary)
    if peak_context:
        full_prompt_parts.append(peak_context)
    full_prompt = "\n\n".join(full_prompt_parts)

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

    # Timeout applied only to individual TTS synthesis tasks (not queue.get).
    # The consumer itself exits via:
    #   - None sentinel  (normal, line below `await tts_queue.put(None)`)
    #   - consumer_task.cancel()  (CancelledError / exception paths)
    # Using a queue.get() timeout caused premature exits when the LLM was slow
    # (e.g. GGUF fallback taking 37s while the 30s clock ran from turn start).
    TTS_TASK_TIMEOUT = 45.0  # per-sentence synthesis wall-clock limit

    async def tts_consumer() -> None:
        """Consume TTS tasks from the queue, emit audio + word timings.

        Exits cleanly via:
          - None sentinel put by the orchestrator after LLM finishes
          - CancelledError when consumer_task.cancel() is called on error/cancel
        """
        nonlocal first_chunk_emitted
        while True:
            # Await directly — no timeout here. Premature timeouts broke
            # slow-LLM (GGUF) turns by killing the consumer before any text
            # was streamed. Exit is guaranteed by sentinel / cancel().
            item = await tts_queue.get()
            if item is None:
                break
            try:
                tts_task, seq, cue = item
                # Guard individual synthesis tasks against hangs
                try:
                    audio, mime, word_timings = await asyncio.wait_for(
                        tts_task, timeout=TTS_TASK_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    log.warning("tts_task_timeout", seq=seq, timeout=TTS_TASK_TIMEOUT)
                    continue
                if audio:
                    if not first_chunk_emitted:
                        await emit({"type": "orb_state", "state": "speaking"})
                        await emit({"type": "tts_playing"})
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

    # H2 fix: cache the settings copy once per turn instead of per-sentence
    _turn_settings = settings.model_copy()
    if _turn_settings.tts_engine == "auto":
        _turn_settings.tts_engine = "edge"  # default to fast engine

    async def generate_tts(text_chunk: str, cue: str, is_long_task: bool) -> tuple[bytes, str, list[dict]]:
        cleaned = _strip_markdown_for_tts(text_chunk)
        if not cleaned.strip():
            return b"", "audio/mpeg", []
        return await tts_module.synthesize_with_mime(cleaned, _turn_settings, cue=cue)

    try:
        for iteration in range(MAX_TOOL_ITERATIONS):
            tool_calls_made = False
            iteration_text: list[str] = []
            sentence_buffer = ""

            async for event in llm_client.stream_chat(
                messages=messages, tools=TOOL_SCHEMAS, settings=settings,
                cancel_token=_cancel,  # v12: checked on every chunk for fast barge-in
            ):
                # Check cancellation at each event
                if _cancel and _cancel.is_cancelled:
                    log.info("llm_stream_cancelled")
                    break
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
                                if not first_chunk_emitted:
                                    await emit({"type": "orb_state", "state": "speaking"})
                                    await emit({"type": "tts_playing"})
                                    first_chunk_emitted = True
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
                    
                elif etype == "error":
                    # Emit as a system note — NOT added to final_answer_parts
                    # and NOT sent to TTS. These are provider-switch notices
                    # (e.g. "Cloud AI is busy. Using offline Genie.") and
                    # must never be spoken aloud or included in the assistant reply.
                    msg_text = event.get("message", "Error")
                    await emit({"type": "system_note", "message": msg_text})

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
                if not first_chunk_emitted:
                    await emit({"type": "orb_state", "state": "speaking"})
                    await emit({"type": "tts_playing"})
                    first_chunk_emitted = True
                task = asyncio.create_task(
                    generate_tts(clean_remaining, current_cue, any_tools_used)
                )
                background_tasks.add(task)
                task.add_done_callback(background_tasks.discard)
                await tts_queue.put((task, sentence_seq, current_cue))
                sentence_seq += 1

        final_text = "".join(final_answer_parts).strip()
        await emit({"type": "assistant_text", "delta": "", "final": True})

        # Signal consumer to stop and wait for it.
        # Safety ceiling: if something went wrong and None was never consumed,
        # cap the wait so we don't hang forever.
        await tts_queue.put(None)
        try:
            await asyncio.wait_for(consumer_task, timeout=300.0)
        except asyncio.TimeoutError:
            log.error("tts_consumer_total_timeout", msg="Consumer did not exit in 5 min — cancelling")
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass

        if first_chunk_emitted:
            await emit({"type": "assistant_audio_end"})

        # ALWAYS signal frontend that the turn is done — mic can re-enable.
        # Previously this was conditional, causing the frontend to stay stuck
        # in PROCESSING/ASSISTANT_SPEAKING when no TTS audio was generated
        # (e.g. tool-only responses, empty LLM output).
        await emit({"type": "tts_done"})

        if final_text:
            messages.append({"role": "assistant", "content": final_text})

        session.history = [m for m in messages if m.get("role") != "system"]
        context.update_context(text, tool_calls_in_turn)
        await asyncio.to_thread(record_turn_memory, session.session_id, text, final_text)

        log.info("turn_end", response_length=len(final_text), tools_used=len(tool_calls_in_turn))
        await emit({"type": "orb_state", "state": "idle"})
        
        # Note: on_tts_complete is now triggered by the frontend's playback_complete event
        # to prevent microphone echo loops during audio playback.
    except asyncio.CancelledError:
        log.info("turn_cancelled")
        consumer_task.cancel()
        for t in background_tasks:
            t.cancel()
        # Always release the frontend from any waiting state on cancel
        await emit({"type": "tts_done"})
        await emit({"type": "orb_state", "state": "idle"})
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
        # Always emit tts_done on error so frontend never stays stuck
        await emit({"type": "tts_done"})
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

    result = await _maybe_open_suggested_url(result, emit, log)

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
            "content": _tool_result_content(result),
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
