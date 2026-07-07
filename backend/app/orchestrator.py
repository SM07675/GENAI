"""The conversation orchestrator: Gemini ReAct loop with tool calling.

Given a user turn (text or transcript), this:
  1. Appends the user message to session history.
  2. Calls Gemini with the full tool schema, streaming.
  3. Streams text deltas back to the client (for live chat typing).
  4. When the model emits a tool call, executes it (offloaded to a thread),
     emits tool_start/tool_end, and feeds the result back into the loop.
  5. Repeats until the model produces a final answer with no tool calls.
  6. Synthesizes TTS for the final answer and streams the audio back.

The system prompt (see `prompts/system_prompt.md`) instructs Gemini to keep
replies concise, voice-friendly, and to chain tool calls when a tool returns
`not_found` with a `suggestion` (the "Instagram problem" guardrail).

Callbacks are sent via `emitter(dict)` so the caller (WebSocket handler) can
push JSON to the client. All callbacks are plain dicts matching the protocol
in `schemas.py`.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Awaitable, Callable

from . import tts as tts_module
from . import stt, llm_client
from .auth import Session
from .config import Settings, get_settings
from .tools import TOOL_SCHEMAS, execute_tool

log = logging.getLogger("genie.orchestrator")

Emitter = Callable[[dict], Awaitable[None]]

# Hard cap on ReAct iterations to avoid runaway loops.
MAX_TOOL_ITERATIONS = 8

_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.md"


def load_system_prompt() -> str:
    """Load the master system prompt (cached at module import)."""
    if not hasattr(load_system_prompt, "_cache"):
        try:
            load_system_prompt._cache = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")  # type: ignore[attr-defined]
        except FileNotFoundError:
            log.warning("system_prompt.md missing; using minimal prompt.")
            load_system_prompt._cache = "You are Genie, a helpful assistant."  # type: ignore[attr-defined]
    return load_system_prompt._cache  # type: ignore[attr-defined]


async def handle_user_turn(
    session: Session,
    user_text: str,
    emit: Emitter,
    settings: Settings | None = None,
) -> None:
    """Run one full user -> assistant turn (possibly many tool calls)."""
    settings = settings or get_settings()
    text = (user_text or "").strip()
    if not text:
        await emit({"type": "error", "message": "I didn't catch that."})
        return

    # Quick language detection to tag the message for Gemini.
    import re
    is_hindi = bool(re.search(r'[\u0900-\u097F]', text))
    lang_tag = "[Language: Hindi/Hinglish] " if is_hindi else "[Language: English] "
    tagged_text = lang_tag + text

    # Append the user message to history (kept in-memory per session).
    session.history.append({"role": "user", "content": tagged_text})

    # Inject/refresh the system prompt at the head of the conversation.
    messages = [{"role": "system", "content": load_system_prompt()}] + session.history

    await emit({"type": "orb_state", "state": "thinking"})

    final_answer_parts: list[str] = []
    
    # --- Ultra-Low Latency TTS Pipelining ---
    import re
    import base64
    
    tts_queue = asyncio.Queue()
    first_chunk_emitted = False
    
    async def tts_consumer():
        nonlocal first_chunk_emitted
        while True:
            task = await tts_queue.get()
            if task is None:
                break
            try:
                audio = await task
                if audio:
                    if not first_chunk_emitted:
                        await emit({"type": "orb_state", "state": "speaking"})
                        first_chunk_emitted = True
                    await emit({
                        "type": "assistant_audio_chunk",
                        "audio": base64.b64encode(audio).decode("ascii"),
                    })
            except Exception as e:
                log.error(f"TTS chunk generation failed: {e}")
            finally:
                tts_queue.task_done()
                
    consumer_task = asyncio.create_task(tts_consumer())
    
    async def generate_tts(text_chunk: str):
        return await tts_module.synthesize(text_chunk, settings)

    try:
        for _iteration in range(MAX_TOOL_ITERATIONS):
            tool_calls_made = False
            iteration_text: list[str] = []

            # Stream this turn. We accumulate the assistant message so we can
            # append it to history at the end of the iteration.
            sentence_buffer = ""
            async for event in llm_client.stream_chat(
                messages=messages, tools=TOOL_SCHEMAS, settings=settings
            ):
                etype = event["type"]

                if etype == "text_delta":
                    delta = event["delta"]
                    iteration_text.append(delta)
                    final_answer_parts.append(delta)
                    await emit({"type": "assistant_text", "delta": delta, "final": False})
                    
                    sentence_buffer += delta
                    # Split on punctuation (. ? ! or Hindi ।) followed by space/newline
                    match = re.search(r'([.?!।]\s+)', sentence_buffer)
                    while match:
                        split_idx = match.end()
                        sentence = sentence_buffer[:split_idx].strip()
                        if sentence:
                            task = asyncio.create_task(generate_tts(sentence))
                            await tts_queue.put(task)
                        sentence_buffer = sentence_buffer[split_idx:]
                        match = re.search(r'([.?!।]\s+)', sentence_buffer)

                elif etype == "tool_call":
                    # A finalized tool call. Execute it.
                    tool_calls_made = True
                    await _run_tool_call(event, session, messages, emit, settings)

                # `tool_call_progress` is informational; the UI shows a
                # "calling X..." hint from `tool_start` instead.

            # After the stream finishes, append the assistant message we just
            # consumed so the next iteration has correct context. The finish
            # event already gave us the assembled message; reconstruct it.
            # We rely on stream_chat's `finish` event for the canonical copy.
            # Simpler: rebuild from what we streamed + tool_calls we ran.

            if not tool_calls_made:
                # No tools this round -> the model produced a final answer.
                break
            # Otherwise loop again: Gemini may want to call more tools or wrap up.

        # ---- Finalize ----------------------------------------------------
        # Flush any remaining text in the sentence buffer
        if sentence_buffer.strip():
            task = asyncio.create_task(generate_tts(sentence_buffer.strip()))
            await tts_queue.put(task)
            
        final_text = "".join(final_answer_parts).strip()
        # Trim any streamed "thinking aloud" we don't want spoken: we keep it
        # all for the transcript, but TTS only the last assistant turn.
        await emit({"type": "assistant_text", "delta": "", "final": True})

        # Wait for all pipelined TTS chunks to finish emitting
        await tts_queue.put(None)
        await consumer_task
        
        if first_chunk_emitted or (not tool_calls_made and final_text):
            await emit({"type": "assistant_audio_end"})

        await emit({"type": "orb_state", "state": "idle"})

    except Exception as e:  # noqa: BLE001
        log.exception("Orchestrator error: %s", e)
        await emit({
            "type": "error",
            "message": f"Something went wrong on my end: {e.__class__.__name__}.",
        })
        await emit({"type": "orb_state", "state": "idle"})


async def _run_tool_call(
    event: dict,
    session: Session,
    messages: list[dict],
    emit: Emitter,
    settings: Settings,
) -> None:
    """Execute a single finalized tool call and append its result to context."""
    name = event.get("name") or "<unknown>"
    args = event.get("arguments") or {}
    call_id = event.get("id") or name

    await emit({"type": "tool_start", "name": name, "args": args})

    # Offload the (blocking, OS-level) tool to a worker thread.
    result = await asyncio.to_thread(execute_tool, name, args)

    await emit({"type": "tool_end", "name": name, "result": result.model_dump()})

    # Append the assistant's tool_call message AND the tool result message so
    # the next model turn sees a correct function-call transcript.
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

    # If the tool returned a vision payload, route it through the vision model
    # so Gemini can actually "see" the screenshot before answering.
    if result.data.get("vision"):
        await _handle_vision_result(result, messages, settings)
    else:
        messages.append({
            "role": "tool",
            "tool_call_id": call_id,
            "name": name,
            "content": result.message,
        })


async def _handle_vision_result(result, messages: list[dict], settings: Settings) -> None:
    """Send a captured screenshot to Gemini vision and append its answer."""
    data = result.data
    try:
        answer = await llm_client.vision_describe(
            image_base64=data["image_base64"],
            image_mime=data["image_mime"],
            question=data.get("question") or "Describe what's on screen.",
            settings=settings,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("Vision call failed: %s", e)
        answer = f"I captured the screen but couldn't analyze it: {e}"
    # The vision answer becomes the effective tool result text.
    messages.append({
        "role": "tool",
        "tool_call_id": "screen_vision",
        "name": "capture_screen",
        "content": answer,
    })
