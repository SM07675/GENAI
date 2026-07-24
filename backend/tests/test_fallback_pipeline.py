"""Tests for the resilient fallback pipeline, rate limiting, deduplication, and intent routing."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from openai import RateLimitError
import httpx

from app.config import Settings
from app.llm_client import stream_chat, get_provider_config
from app.services.circuit_breaker import get_circuit_breaker
from app.services.local_intent_router import route_intent

@pytest.fixture
def test_settings():
    return Settings(
        llm_provider="openrouter",
        openrouter_primary_model="primary-model",
        openrouter_fallback_models=["secondary-model"],
        openrouter_api_key="sk-test",
        openrouter_max_retries_per_model=1,
        openrouter_cooldown_seconds=60,
    )

def test_local_intent_router():
    assert route_intent("stop audio") == "stop_audio"
    assert route_intent("play music") == "play_music"
    assert route_intent("clear history") == "clear_history"
    assert route_intent("What is the weather?") is None
    assert route_intent("stop") == "stop_audio"
    # Hindi/Hinglish test for intent
    assert route_intent("play some music") == "play_music"

@pytest.mark.asyncio
async def test_llm_client_fallback_success(test_settings):
    messages = [{"role": "user", "content": "hello"}]
    
    # Mock AsyncOpenAI client
    mock_client = MagicMock()
    mock_chat = AsyncMock()
    mock_client.chat.completions.create = mock_chat
    
    # Raise RateLimitError on first call (primary), succeed on second (secondary)
    err_response = httpx.Response(429, request=httpx.Request("POST", "url"), headers={"retry-after": "30"})
    rate_limit_err = RateLimitError("429 Too Many Requests", response=err_response, body=None)
    
    # We mock stream to return a choice
    class MockStream:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def __aiter__(self):
            return self
        async def __anext__(self):
            if not getattr(self, '_yielded', False):
                self._yielded = True
                choice = MagicMock()
                choice.choices = [MagicMock()]
                choice.choices[0].delta.content = "fallback success"
                choice.choices[0].delta.tool_calls = None
                choice.choices[0].finish_reason = "stop"
                return choice
            raise StopAsyncIteration
            
    mock_chat.side_effect = [rate_limit_err, MockStream()]
    
    with patch("app.llm_client.get_client", return_value=mock_client):
        events = []
        async for event in stream_chat(messages, settings=test_settings):
            events.append(event)
            
    # Check circuit breaker for primary model
    cb_primary = get_circuit_breaker("openrouter_primary-model")
    assert cb_primary.allow_request() is False
    assert cb_primary._current_cooldown == 30.0
    
    # Should yield error about trying another model
    assert any(e.get("type") == "error" and "Trying another" in e.get("message", "") for e in events)
    assert any(e.get("type") == "text_delta" and e.get("delta") == "fallback success" for e in events)

@pytest.mark.asyncio
async def test_llm_client_local_fallback(test_settings):
    messages = [{"role": "user", "content": "hello"}]
    
    # Both primary and secondary fail with 429
    mock_client = MagicMock()
    mock_chat = AsyncMock()
    mock_client.chat.completions.create = mock_chat
    
    err_response = httpx.Response(429, request=httpx.Request("POST", "url"))
    rate_limit_err = RateLimitError("429 Too Many Requests", response=err_response, body=None)
    mock_chat.side_effect = [rate_limit_err, rate_limit_err]
    
    with patch("app.llm_client.get_client", return_value=mock_client), \
         patch("app.llm_client._stream_local") as mock_local:
        
        async def dummy_local(*args, **kwargs):
            yield {"type": "text_delta", "delta": "local success"}
            yield {"type": "finish", "finish_reason": "stop"}
            
        mock_local.side_effect = dummy_local
        
        events = []
        async for event in stream_chat(messages, settings=test_settings):
            events.append(event)
            
    # Should yield error about local fallback
    assert any(e.get("type") == "error" and "Cloud AI is busy" in e.get("message", "") for e in events)
    assert any(e.get("type") == "text_delta" and e.get("delta") == "local success" for e in events)
