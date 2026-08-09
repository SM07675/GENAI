"""OpenAI-compatible LLM client wrapper with provider routing.

Supported cloud providers:
- OpenRouter — access to 100+ models (DeepSeek, Qwen, Llama, Mistral, etc.)
              Many models are FREE. https://openrouter.ai
- Gemini     — via Google's OpenAI-compatible endpoint
- Grok       — via xAI's OpenAI-compatible endpoint
- Groq Cloud — via Groq's OpenAI-compatible endpoint

Priority / fallback chain:
  OpenRouter (or configured provider) → Gemini (if key present) → local GGUF

The orchestrator consumes one streaming event shape regardless of provider:
text_delta, tool_call_progress, tool_call, and finish.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator

from openai import (
    APIConnectionError,
    APIStatusError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .config import Settings, get_settings
from .services.circuit_breaker import get_circuit_breaker
from .services.local_llm import local_llm

log = logging.getLogger("genie.llm")


@dataclass(frozen=True)
class ProviderConfig:
    """Resolved settings for the active OpenAI-compatible provider."""

    id: str
    label: str
    api_key: str
    base_url: str
    model: str
    temperature: float
    max_tokens: int
    timeout_seconds: float


_CLIENTS: dict[tuple[str, str, str, float], AsyncOpenAI] = {}


def _normalise_provider(provider: str) -> str:
    raw = (provider or "openrouter").strip().lower()
    aliases = {
        "google":      "gemini",
        "grok":        "grok",
        "xai":         "grok",
        "x-ai":        "grok",
        "x.ai":        "grok",
        "groq":        "groq",
        "openrouter":  "openrouter",
        "or":          "openrouter",
        "open_router": "openrouter",
        "nvidia":      "nvidia",
    }
    provider_id = aliases.get(raw, raw)
    if provider_id not in {"openrouter", "gemini", "grok", "groq", "nvidia"}:
        raise RuntimeError(
            f"Unsupported LLM_PROVIDER '{provider}'. "
            "Use 'openrouter', 'gemini', 'grok'/'xai', 'groq', or 'nvidia'."
        )
    return provider_id


def get_provider_config(settings: Settings | None = None) -> ProviderConfig:
    """Resolve the active provider into concrete client parameters."""

    settings = settings or get_settings()
    provider = _normalise_provider(settings.llm_provider)

    if provider == "openrouter":
        return ProviderConfig(
            id="openrouter",
            label="OpenRouter",
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            model=settings.openrouter_primary_model,
            temperature=settings.openrouter_temperature,
            max_tokens=settings.openrouter_max_tokens,
            timeout_seconds=settings.openrouter_timeout_seconds,
        )

    if provider == "gemini":
        return ProviderConfig(
            id="gemini",
            label="Gemini",
            api_key=settings.gemini_api_key,
            base_url=settings.gemini_base_url,
            model=settings.gemini_model,
            temperature=settings.gemini_temperature,
            max_tokens=settings.gemini_max_tokens,
            timeout_seconds=settings.gemini_timeout_seconds,
        )

    if provider == "grok":
        return ProviderConfig(
            id="grok",
            label="Grok",
            api_key=settings.grok_api_key or settings.xai_api_key,
            base_url=settings.grok_base_url,
            model=settings.grok_model,
            temperature=settings.grok_temperature,
            max_tokens=settings.grok_max_tokens,
            timeout_seconds=settings.grok_timeout_seconds,
        )

    if provider == "nvidia":
        return ProviderConfig(
            id="nvidia",
            label="Nvidia",
            api_key=settings.nvidia_api_key,
            base_url=settings.nvidia_base_url,
            model=settings.nvidia_model,
            temperature=settings.nvidia_temperature,
            max_tokens=settings.nvidia_max_tokens,
            timeout_seconds=settings.nvidia_timeout_seconds,
        )

    return ProviderConfig(
        id="groq",
        label="Groq Cloud",
        api_key=settings.groq_api_key,
        base_url=settings.groq_base_url,
        model=settings.groq_model,
        temperature=settings.groq_temperature,
        max_tokens=settings.groq_max_tokens,
        timeout_seconds=settings.groq_timeout_seconds,
    )


def _missing_key_message(provider: ProviderConfig) -> str:
    hints = {
        "openrouter": "OPENROUTER_API_KEY (get a free key at https://openrouter.ai/keys)",
        "gemini":     "GEMINI_API_KEY",
        "grok":       "XAI_API_KEY or GROK_API_KEY",
        "groq":       "GROQ_API_KEY",
        "nvidia":     "NVIDIA_API_KEY",
    }
    env_hint = hints.get(provider.id, "API_KEY")
    return f"{env_hint} is not set. Add it to backend/.env before starting."


def _openrouter_headers(settings: Settings) -> dict[str, str]:
    """Extra headers required by OpenRouter for request attribution."""
    return {
        "HTTP-Referer": settings.openrouter_site_url or "http://localhost:8765",
        "X-Title":      settings.openrouter_site_name or "Genie AI Assistant",
    }


def get_client(settings: Settings | None = None) -> AsyncOpenAI:
    """Return a cached AsyncOpenAI client for the active provider."""

    settings = settings or get_settings()
    provider = get_provider_config(settings)
    if not provider.api_key:
        raise RuntimeError(_missing_key_message(provider))

    cache_key = (
        provider.id,
        provider.base_url.rstrip("/"),
        provider.api_key,
        provider.timeout_seconds,
    )
    client = _CLIENTS.get(cache_key)
    if client is not None:
        return client

    extra_headers: dict[str, str] = {}
    if provider.id == "openrouter":
        extra_headers = _openrouter_headers(settings)

    client = AsyncOpenAI(
        api_key=provider.api_key,
        base_url=provider.base_url,
        timeout=provider.timeout_seconds,
        default_headers=extra_headers if extra_headers else None,
    )
    _CLIENTS[cache_key] = client
    log.info(
        "%s client initialised (model=%s, base_url=%s)",
        provider.label,
        provider.model,
        provider.base_url,
    )
    return client


def _circuit_breaker(provider: ProviderConfig):
    return get_circuit_breaker(
        name=provider.id,
        failure_threshold=3,
        cooldown_seconds=60.0,
    )


def _is_generation_failure(exc: Exception) -> bool:
    """Return True for provider-side tool/function generation failures."""

    from openai import APIError

    if isinstance(exc, APIError):
        msg = str(exc).lower()
        return "failed to call a function" in msg or "failed_generation" in msg
    return False


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


def _is_auth_error(exc: Exception) -> bool:
    """Return True when the configured provider key is missing/invalid upstream."""

    msg = str(exc).lower()
    code = getattr(exc, "status_code", None)
    return (
        isinstance(exc, AuthenticationError)
        or code in (401, 403)
        or "invalid_api_key" in msg
        or "invalid api key" in msg
        or "unauthorized" in msg
        or "forbidden" in msg
    )


def _auth_fallback_prefix(provider: ProviderConfig) -> str:
    return (
        f"The configured {provider.label} API key was rejected, "
        "so I'm using offline mode for now. "
    )


def _gemini_fallback_settings(
    settings: Settings,
    failed_provider: ProviderConfig,
) -> Settings | None:
    """Prefer a configured Gemini key over local fallback when another provider fails."""

    if failed_provider.id == "gemini" or not settings.gemini_api_key:
        return None
    return settings.model_copy(update={"llm_provider": "gemini"})


def _is_retryable(exc: Exception) -> bool:
    """Return True for transient network/server faults."""

    from openai import APIError

    code = getattr(exc, "status_code", None)
    if isinstance(exc, APIConnectionError) or code in (500, 502, 503, 504):
        return True
    # Generic APIError that is NOT auth/rate-limit is almost always a transient
    # provider-side failure (e.g. Nvidia nemotron generation errors). Retry it.
    if isinstance(exc, APIError) and not _is_auth_error(exc) and not _is_rate_limit_or_quota(exc):
        return True
    return False


def _openai_tool_call_id(index: int, provider: ProviderConfig) -> str:
    """Generate a stable fallback ID if a provider omits the streamed call ID."""

    return f"call_{provider.id}_{index}"


async def stream_chat(
    messages: list[dict],
    tools: list[dict] | None = None,
    settings: Settings | None = None,
    use_local: bool = False,
    cancel_token=None,  # Optional[CancellationToken] — checked every chunk
) -> AsyncIterator[dict[str, Any]]:
    """Stream a chat turn. Yields text_delta / tool_call / finish events.

    v12: ``cancel_token`` is checked after EVERY streamed chunk so that a
    barge-in (or manual cancel) stops token generation within one iteration
    (~50 ms) rather than waiting for the full response to finish.
    """

    from .rate_limiter import get_rate_limiter
    import asyncio

    settings = settings or get_settings()
    provider = get_provider_config(settings)
    rate_limiter = get_rate_limiter()

    if use_local or not provider.api_key:
        yield {"type": "error", "message": "Cloud AI is busy. Using offline Genie."}
        async for event in _stream_local(messages, settings, tools=tools):
            yield event
        return

    models_to_try = []
    if provider.id == "openrouter":
        models_to_try = [settings.openrouter_primary_model] + settings.openrouter_fallback_models
        models_to_try = [m for m in models_to_try if m]
    else:
        models_to_try = [provider.model]

    for attempt_idx, current_model in enumerate(models_to_try):
        cb_name = f"{provider.id}_{current_model}"
        cb_threshold = settings.openrouter_max_retries_per_model if provider.id == "openrouter" else 3
        cb_cooldown = settings.openrouter_cooldown_seconds if provider.id == "openrouter" else 60.0
        
        cb = get_circuit_breaker(name=cb_name, failure_threshold=cb_threshold, cooldown_seconds=cb_cooldown)
        
        if not cb.allow_request():
            log.warning("[%s] Model %s circuit OPEN; skipping", provider.label, current_model)
            continue
            
        await rate_limiter.wait_if_needed()
        client = get_client(settings)
        
        attempt_provider = ProviderConfig(
            id=provider.id, label=provider.label, api_key=provider.api_key,
            base_url=provider.base_url, model=current_model,
            temperature=provider.temperature, max_tokens=provider.max_tokens,
            timeout_seconds=provider.timeout_seconds,
        )
        
        kwargs = {
            "model": current_model,
            "messages": messages,
            "temperature": provider.temperature,
            "max_tokens": provider.max_tokens,
            "stream": True,
        }
        if provider.id == "nvidia":
            kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": settings.nvidia_enable_thinking}}
            kwargs["top_p"] = 0.95
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
            
        content_parts = []
        tool_calls = {}
        finish_reason = None
        
        if attempt_idx > 0:
            yield {"type": "error", "message": "Trying another AI model..."}
            
        max_tries = settings.openrouter_max_retries_per_model if provider.id == "openrouter" else 3
        success = False
        
        try:
            for try_n in range(max_tries):
                # H3 fix: reset accumulators on each retry to prevent
                # duplicate text from a partially-streamed first attempt
                content_parts = []
                tool_calls = {}
                finish_reason = None

                try:
                    stream = await client.chat.completions.create(**kwargs)
                    # H4 fix: use try/finally for stream cleanup instead of
                    # fragile `async with` that breaks on some provider SDKs
                    try:
                        async for chunk in stream:
                            # v12: check cancel_token on EVERY chunk so barge-in
                            # stops generation within one iteration (~50ms).
                            if cancel_token and cancel_token.is_cancelled:
                                log.info(
                                    "stream_chat_cancelled_mid_stream",
                                    reason=cancel_token.reason,
                                    chunks_so_far=len(content_parts),
                                )
                                break

                            if not chunk.choices: continue
                            choice = chunk.choices[0]
                            delta = choice.delta
                            
                            if delta and delta.content:
                                content_parts.append(delta.content)
                                yield {"type": "text_delta", "delta": delta.content}
                                
                            if delta and delta.tool_calls:
                                for tc in delta.tool_calls:
                                    idx = int(tc.index or 0)
                                    slot = tool_calls.setdefault(idx, {
                                        "id": _openai_tool_call_id(idx, attempt_provider), 
                                        "name": "", "arguments": "", "type": "function"
                                    })
                                    if tc.id: slot["id"] = tc.id
                                    if tc.function and tc.function.name: slot["name"] = tc.function.name
                                    if tc.function and tc.function.arguments:
                                        slot["arguments"] += tc.function.arguments
                                        yield {
                                            "type": "tool_call_progress", 
                                            "index": idx, 
                                            "name": slot["name"], 
                                            "arguments_so_far": slot["arguments"]
                                        }
                                        
                            if choice.finish_reason:
                                finish_reason = choice.finish_reason
                    finally:
                        # Ensure the stream is properly closed
                        if hasattr(stream, "close"):
                            await stream.close()
                        elif hasattr(stream, "response") and hasattr(stream.response, "close"):
                            await stream.response.close()
                                
                    cb.record_success()
                    success = True
                    break
                    
                except Exception as stream_exc:
                    if _is_rate_limit_or_quota(stream_exc):
                        retry_after = getattr(stream_exc, "response", None)
                        cooldown = cb_cooldown
                        if retry_after and "retry-after" in retry_after.headers:
                            try:
                                cooldown = float(retry_after.headers["retry-after"])
                            except ValueError:
                                pass
                        log.warning("[%s] Model %s rate-limited! Circuit forced open for %s sec", provider.label, current_model, cooldown)
                        cb.force_open(cooldown)
                        raise stream_exc
                        
                    if _is_generation_failure(stream_exc) or _is_auth_error(stream_exc):
                        cb.record_failure()
                        raise stream_exc
                        
                    if _is_retryable(stream_exc):
                        log.warning("[%s] Transient error %s, retrying...", provider.label, stream_exc)
                        yield {"type": "error", "message": "Retrying..."}
                        await asyncio.sleep(2 ** try_n)
                        continue
                    
                    cb.record_failure()
                    raise stream_exc
                    
            if not success:
                cb.record_failure()
                raise RuntimeError(f"Max retries exhausted for {current_model}")
                
            for idx in sorted(tool_calls):
                tc = tool_calls[idx]
                try: 
                    args_obj = json.loads(tc["arguments"]) if tc["arguments"] else {}
                except json.JSONDecodeError: 
                    args_obj = {"_raw": tc["arguments"]}
                yield {
                    "type": "tool_call", "index": idx, "id": tc["id"], 
                    "name": tc["name"], "arguments": args_obj
                }

            assembled = {
                "role": "assistant",
                "content": "".join(content_parts).strip() or None,
                "tool_calls": ([{
                    "id": tc["id"], "type": "function", 
                    "function": {"name": tc["name"], "arguments": tc["arguments"] or "{}"}
                } for tc in (tool_calls[i] for i in sorted(tool_calls))] if tool_calls else None),
            }
            yield {"type": "finish", "finish_reason": finish_reason, "message": assembled}
            return
            
        except Exception as exc:
            log.warning("[%s] Model %s failed: %s", provider.label, current_model, type(exc).__name__)
            continue
            
    log.warning("All models failed. Falling back to local offline GGUF.")
    yield {"type": "error", "message": "Cloud AI is busy. Using offline Genie."}
    async for event in _stream_local(messages, settings, tools=tools):
        yield event

async def _stream_local(
    messages: list[dict],
    settings: Settings,
    prefix: str = "",
    tools: list[dict] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Offline fallback: plain conversational text or tool calls via local GGUF."""

    import asyncio

    try:
        response_msg = await asyncio.to_thread(
            local_llm.generate_from_messages,
            messages,
            settings=settings,
            tools=tools,
        )
    except Exception as exc:
        text = (
            "The cloud model is temporarily unavailable and the offline model "
            f"also hit a problem: {exc}. Please check your API key or try again shortly."
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
        "type": "finish",
        "finish_reason": "local_fallback",
        "message": {"role": "assistant", "content": full_text, "tool_calls": None},
    }


def _word_chunks(text: str) -> list[str]:
    parts = text.split(" ")
    if len(parts) <= 1:
        return [text]
    return [p + (" " if i < len(parts) - 1 else "") for i, p in enumerate(parts)]


async def vision_describe(
    image_base64: str,
    image_mime: str,
    question: str,
    settings: Settings | None = None,
) -> str:
    """One-shot vision call using the active OpenAI-compatible provider."""

    settings = settings or get_settings()
    provider = get_provider_config(settings)
    client = get_client(settings)
    cb = _circuit_breaker(provider)
    data_url = f"data:{image_mime};base64,{image_base64}"

    try:
        resp = await client.chat.completions.create(
            model=provider.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": question or "Describe what's on screen.",
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            temperature=min(provider.temperature, 0.3),
            max_tokens=min(provider.max_tokens, 1024),
        )
        cb.record_success()
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        cb.record_failure()
        log.warning("%s vision call failed: %s", provider.label, exc)
        raise
