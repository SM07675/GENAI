"""Gemini client wrapper (OpenAI-compatible).

We use the `openai` SDK pointed at the Gemini v1beta OpenAI endpoint.

This module exposes:
  * `get_client()`  -> configured AsyncOpenAI singleton
  * `stream_chat()` -> async generator yielding dicts:
        {"type":"text_delta", "delta": "..."}
        {"type":"tool_call", "index": i, "id":..., "name":..., "arguments":"..."}
        {"type":"finish", "finish_reason": ..., "message": {...}}
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from .config import Settings, get_settings

_client: AsyncOpenAI | None = None


def get_client(settings: Settings | None = None) -> AsyncOpenAI:
    """Lazily build (and cache) the async OpenAI-compatible client."""
    global _client
    if _client is not None:
        return _client
    settings = settings or get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to backend/.env before starting."
        )
    _client = AsyncOpenAI(
        api_key=settings.gemini_api_key,
        base_url=settings.gemini_base_url,
    )
    return _client


async def stream_chat(
    messages: list[dict],
    tools: list[dict] | None = None,
    settings: Settings | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Stream a chat completion, yielding text deltas, tool calls, and a finish event.

    The yielded `message` on `finish` is the fully-assembled assistant message
    (with content + tool_calls) ready to append to history.
    """
    settings = settings or get_settings()
    client = get_client(settings)

    request_kwargs: dict[str, Any] = {
        "model": settings.gemini_model,
        "messages": messages,
        "temperature": settings.gemini_temperature,
        "max_tokens": settings.gemini_max_tokens,
        "stream": True,
    }
    if tools:
        request_kwargs["tools"] = tools
        request_kwargs["tool_choice"] = "auto"

    stream = await client.chat.completions.create(**request_kwargs)

    # Accumulate the full message so callers can append it to history.
    content_parts: list[str] = []
    # tool_calls indexed by their streaming index.
    tool_calls: dict[int, dict[str, Any]] = {}
    finish_reason: str | None = None

    async with stream as s:  # `stream` is an AsyncContextManager in openai>=1.x
        async for event in s:
            if not event.choices:
                continue
            choice = event.choices[0]
            delta = choice.delta

            # --- Text deltas ------------------------------------------------
            if delta and delta.content:
                content_parts.append(delta.content)
                yield {"type": "text_delta", "delta": delta.content}

            # --- Tool call deltas (assembled incrementally) -----------------
            if delta and delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    slot = tool_calls.setdefault(
                        idx,
                        {"id": "", "name": "", "arguments": "", "type": "function"},
                    )
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        slot["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["arguments"] += tc.function.arguments
                        # Emit a streamed tool call only once it has a name, so
                        # the UI can show "calling open_app..." promptly. We
                        # emit progress as arguments arrive (handled in
                        # orchestrator by buffering per index).
                        yield {
                            "type": "tool_call_progress",
                            "index": idx,
                            "name": slot["name"],
                            "arguments_so_far": slot["arguments"],
                        }

            if choice.finish_reason:
                finish_reason = choice.finish_reason

    # Emit one finalized tool_call event per call (id/name/args complete).
    for idx in sorted(tool_calls.keys()):
        tc = tool_calls[idx]
        # Parse arguments JSON defensively; fall back to raw string.
        try:
            args_obj = json.loads(tc["arguments"]) if tc["arguments"] else {}
        except json.JSONDecodeError:
            args_obj = {"_raw": tc["arguments"]}
        yield {
            "type": "tool_call",
            "index": idx,
            "id": tc["id"],
            "name": tc["name"],
            "arguments": args_obj,
        }

    assembled = {
        "role": "assistant",
        "content": "".join(content_parts).strip() or None,
        "tool_calls": (
            [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"] or "{}",
                    },
                }
                for tc in (tool_calls[i] for i in sorted(tool_calls.keys()))
            ]
            if tool_calls
            else None
        ),
    }
    yield {"type": "finish", "finish_reason": finish_reason, "message": assembled}


async def vision_describe(
    image_base64: str,
    image_mime: str,
    question: str,
    settings: Settings | None = None,
) -> str:
    """One-shot vision call: answer `question` about the supplied base64 image."""
    settings = settings or get_settings()
    client = get_client(settings)
    data_url = f"data:{image_mime};base64,{image_base64}"
    resp = await client.chat.completions.create(
        model=settings.gemini_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question or "Describe what's on screen."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        temperature=0.3,
        max_tokens=1024,
    )
    return (resp.choices[0].message.content or "").strip()
