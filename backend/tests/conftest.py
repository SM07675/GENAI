"""Pytest configuration and shared fixtures for the Genie backend tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def settings():
    """Return a test Settings instance with safe defaults."""
    from app.config import Settings
    return Settings(
        gemini_api_key="test-key-not-real",
        genie_pin="1234",
        local_llm_enabled=False,
        ngrok_enabled=False,
        wake_word_enabled=False,
        tts_engine="edge",
    )


@pytest.fixture(scope="session")
def app_client(settings):
    """Return a FastAPI TestClient. Import app here to avoid lifespan side effects."""
    import os
    os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
    os.environ.setdefault("GENIE_PIN", "1234")
    os.environ.setdefault("LOCAL_LLM_ENABLED", "false")
    os.environ.setdefault("NGROK_ENABLED", "false")
    os.environ.setdefault("WAKE_WORD_ENABLED", "false")

    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
