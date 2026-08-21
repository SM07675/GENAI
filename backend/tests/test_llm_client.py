"""Tests for cloud LLM provider selection."""
from __future__ import annotations

import pytest

from app.config import Settings
from app.llm_client import _gemini_fallback_settings, _is_auth_error, get_provider_config


def test_xai_provider_uses_grok_defaults_and_xai_key():
    settings = Settings(llm_provider="xai", xai_api_key="xai-test-key")

    provider = get_provider_config(settings)

    assert provider.id == "grok"
    assert provider.label == "Grok"
    assert provider.api_key == "xai-test-key"
    assert provider.base_url == "https://api.x.ai/v1"
    assert provider.model == "grok-4.5"


def test_grok_api_key_takes_precedence_over_xai_key():
    settings = Settings(
        llm_provider="grok",
        xai_api_key="xai-test-key",
        grok_api_key="grok-test-key",
    )

    provider = get_provider_config(settings)

    assert provider.id == "grok"
    assert provider.api_key == "grok-test-key"


def test_groq_provider_is_still_supported():
    settings = Settings(llm_provider="groq", groq_api_key="groq-test-key")

    provider = get_provider_config(settings)

    assert provider.id == "groq"
    assert provider.label == "Groq Cloud"
    assert provider.api_key == "groq-test-key"
    assert provider.base_url == "https://api.groq.com/openai/v1"


def test_unknown_provider_fails_fast():
    settings = Settings(llm_provider="not-real")

    with pytest.raises(RuntimeError, match="Unsupported LLM_PROVIDER"):
        get_provider_config(settings)


def test_status_401_counts_as_auth_error():
    class FakeAuthError(Exception):
        status_code = 401

    assert _is_auth_error(FakeAuthError("Invalid API Key"))


def test_gemini_fallback_used_for_failed_non_gemini_provider():
    settings = Settings(
        llm_provider="groq",
        groq_api_key="bad-groq-key",
        gemini_api_key="gemini-test-key",
    )
    failed_provider = get_provider_config(settings)

    fallback = _gemini_fallback_settings(settings, failed_provider)

    assert fallback is not None
    assert fallback.llm_provider == "gemini"


def test_nvidia_provider_uses_minimax_m3():
    settings = Settings(
        llm_provider="nvidia",
        nvidia_api_key="nvapi-test-key",
        nvidia_model="minimaxai/minimax-m3",
    )
    provider = get_provider_config(settings)

    assert provider.id == "nvidia"
    assert provider.label == "Nvidia"
    assert provider.api_key == "nvapi-test-key"
    assert provider.base_url == "https://integrate.api.nvidia.com/v1"
    assert provider.model == "minimaxai/minimax-m3"

