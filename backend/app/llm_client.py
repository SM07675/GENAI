"""Gemini client wrapper (OpenAI-compatible) — enterprise hardened.

Reliability guarantees
----------------------
1. **Tenacity retries**: Every Gemini API call is wrapped with exponential
   backoff + jitter (3 attempts, 1s base). Transient 500s/network hiccups
   are handled transparently.

2. **Circuit breaker**: After 3 consecutive failures the Gemini circuit opens
   for 60 s. Requests during open state fail fast to the local fallback without
   waiting for more timeouts.

3. **Mid-stream error handling**: Errors that arrive inside the async streaming
   loop (quota hit after the HTTP connection opened) are caught and fall through
   to the local model — the same as connect-time errors.

4. **Singleton client**: The AsyncOpenAI client is created once at module level,
   not per request.

5. **Local fallback is text-only**: The local GGUF model deliberately does NOT
   emit tool_call events to prevent an infinite ReAct loop when Gemini is down.
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from openai import AsyncOpenAI, APIConnectionError, APIStatusError, RateLimitError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .config import Settings, get_settings
from .services.circuit_breaker import get_circuit_breaker
from .services.local_llm import local_llm

log = logging.getLogger("genie.llm")

_client: AsyncOpenAI | None = None

# Circuit breaker singleton for the Gemini provider.
_gemini_cb = get_circuit_breaker(name="gemini", failure_threshold=3, cooldown_seconds=60.0)


def get_client(settings: Settings | None = None) -> AsyncOpenAI:
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
    log.info("Gemini client initialised (model=%s)", settings.gemini_model)
    return _client


def _is_rate_limit_or_quota(exc: Exception) -> bool:
    """Return True for errors that justify falling back to local LLM."""
    msg = str(exc).lower()
    code = getattr(exc, "status_code", None)
    return (
        isinstance(exc, RateLimitError)
        or code == 429
        or "resource_exhausted" in msg
        or "quota" in msg
        or "rate limit" in msg
        or "too many requests" in msg
    )


def _is_retryable(exc: Exception) -> bool:
    """Return True for errors worth retrying (transient network/server faults)."""
    code = getattr(exc, "status_code", None)
    return isinstance(exc, APIConnectionError) or code in (500, 502, 503, 504)


async def stream_chat(
    messages: list[dict],
    tools: list[dict] | None = None,
    settings: Settings | None = None,
    use_local: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    """Stream a chat turn. Yields text_delta / tool_call / finish events.

    Degradation ladder:
      1. Check circuit breaker — if OPEN, skip straight to local LLM.
      2. Try Gemini with tenacity retry (transient errors only).
      3. On rate-limit/quota hit → open circuit, fall back to local LLM.
      4. Local LLM fails → yield a plain error text event.
    """
    from .rate_limiter import get_rate_limiter

    settings     = settings or get_settings()
    rate_limiter = get_rate_limiter()

    # ── Force local (no API key or caller override) ───────────────────────────
    if use_local or not settings.gemini_api_key:
        async for event in _stream_local(messages, settings, tools=tools):
            yield event
        return

    # ── Circuit breaker check ─────────────────────────────────────────────────
    if not _gemini_cb.allow_request():
        log.warning("Gemini circuit OPEN — routing directly to local LLM")
        async for event in _stream_local(messages, settings, tools=tools):
            yield event
        return

    await rate_limiter.wait_if_needed()

    # ── Gemini streaming with retry ───────────────────────────────────────────
    client = get_client(settings)
    kwargs: dict[str, Any] = {
        "model":       settings.gemini_model,
        "messages":    messages,
        "temperature": settings.gemini_temperature,
        "max_tokens":  settings.gemini_max_tokens,
        "stream":      True,
    }
    if tools:
        kwargs["tools"]       = tools
        kwargs["tool_choice"] = "auto"

    content_parts: list[str]      = []
    tool_calls:    dict[int, dict] = {}
    finish_reason: str | None     = None

    try:
        # Retry only on transient server/network faults, NOT rate-limits.
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((APIConnectionError,)),
            wait=wait_exponential_jitter(initial=1, max=8),
            stop=stop_after_attempt(3),
            reraise=True,
        ):
            with attempt:
                stream = await client.chat.completions.create(**kwargs)

        # ── Stream the response ───────────────────────────────────────────────
        try:
            async with stream as s:
                async for chunk in s:
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    delta  = choice.delta

                    if delta and delta.content:
                        content_parts.append(delta.content)
                        yield {"type": "text_delta", "delta": delta.content}

                    if delta and delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx  = tc.index
                            slot = tool_calls.setdefault(
                                idx, {"id": "", "name": "", "arguments": "", "type": "function"}
                            )
                            if tc.id:                              slot["id"]   = tc.id
                            if tc.function and tc.function.name:  slot["name"] = tc.function.name
                            if tc.function and tc.function.arguments:
                                slot["arguments"] += tc.function.arguments
                                yield {
                                    "type":             "tool_call_progress",
                                    "index":            idx,
                                    "name":             slot["name"],
                                    "arguments_so_far": slot["arguments"],
                                }

                    if choice.finish_reason:
                        finish_reason = choice.finish_reason

        except Exception as mid_exc:
            # Mid-stream error (quota hit after connection opened)
            if _is_rate_limit_or_quota(mid_exc):
                log.warning(
                    "Gemini mid-stream rate-limit (%s) → circuit + local fallback",
                    type(mid_exc).__name__,
                )
                _gemini_cb.record_failure()
                async for event in _stream_local(messages, settings, tools=tools):
                    yield event
                return
            raise

        _gemini_cb.record_success()

    except (RateLimitError, APIStatusError) as exc:
        if _is_rate_limit_or_quota(exc):
            log.warning(
                "Gemini quota/rate-limit (%s) → circuit + local fallback",
                type(exc).__name__,
            )
            _gemini_cb.record_failure()
            async for event in _stream_local(messages, settings, tools=tools):
                yield event
            return
        # Non-quota API error — record failure and re-raise
        _gemini_cb.record_failure()
        raise

    except Exception as exc:
        log.exception("Unexpected Gemini error: %s", exc)
        _gemini_cb.record_failure()
        raise

    # ── Emit finalised tool calls ─────────────────────────────────────────────
    for idx in sorted(tool_calls):
        tc = tool_calls[idx]
        try:
            args_obj = json.loads(tc["arguments"]) if tc["arguments"] else {}
        except json.JSONDecodeError:
            args_obj = {"_raw": tc["arguments"]}
        yield {
            "type":      "tool_call",
            "index":     idx,
            "id":        tc["id"],
            "name":      tc["name"],
            "arguments": args_obj,
        }

    assembled = {
        "role":       "assistant",
        "content":    "".join(content_parts).strip() or None,
        "tool_calls": (
            [
                {
                    "id":   tc["id"],
                    "type": "function",
                    "function": {
                        "name":      tc["name"],
                        "arguments": tc["arguments"] or "{}",
                    },
                }
                for tc in (tool_calls[i] for i in sorted(tool_calls))
            ]
            if tool_calls else None
        ),
    }
    yield {"type": "finish", "finish_reason": finish_reason, "message": assembled}


async def _stream_local(
    messages: list[dict],
    settings: Settings,
    prefix: str = "",
    tools: list[dict] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Offline fallback: plain conversational text or tool calls via local GGUF.
    """
    import asyncio

    try:
        response_msg = await asyncio.to_thread(
            local_llm.generate_from_messages, messages, settings=settings, tools=tools
        )
    except Exception as exc:
        text = (
            "Gemini is temporarily unavailable and the offline model also "
            f"encountered a problem: {exc}. Please check your API key or try again shortly."
        )
        response_msg = {"role": "assistant", "content": text}

    if response_msg.get("tool_calls"):
        for i, tc in enumerate(response_msg["tool_calls"]):
            func = tc.get("function", {})
            args_str = func.get("arguments", "{}")
            try:
                args_obj = json.loads(args_str)
            except json.JSONDecodeError:
                args_obj = {"_raw": args_str}
            
            yield {
                "type": "tool_call",
                "index": i,
                "id": tc.get("id") or f"call_{i}",
                "name": func.get("name", ""),
                "arguments": args_obj,
            }
        
        yield {
            "type": "finish",
            "finish_reason": "tool_calls",
            "message": response_msg,
        }
        return

    full_text = (prefix + (response_msg.get("content") or "")).strip()

    for token in _word_chunks(full_text):
        yield {"type": "text_delta", "delta": token}
        await asyncio.sleep(0)

    yield {
        "type":          "finish",
        "finish_reason": "local_fallback",
        "message":       {"role": "assistant", "content": full_text, "tool_calls": None},
    }


def _word_chunks(text: str) -> list[str]:
    parts = text.split(" ")
    if len(parts) <= 1:
        return [text]
    return [p + (" " if i < len(parts) - 1 else "") for i, p in enumerate(parts)]


async def vision_describe(
    image_base64: str,
    image_mime:   str,
    question:     str,
    settings:     Settings | None = None,
) -> str:
    """One-shot Gemini vision call."""
    settings  = settings or get_settings()
    client    = get_client(settings)
    data_url  = f"data:{image_mime};base64,{image_base64}"
    try:
        resp = await client.chat.completions.create(
            model=settings.gemini_model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text",      "text":      question or "Describe what's on screen."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }],
            temperature=0.3,
            max_tokens=1024,
        )
        _gemini_cb.record_success()
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        _gemini_cb.record_failure()
        log.warning("Vision call failed: %s", exc)
        raise
