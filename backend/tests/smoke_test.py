"""Smoke tests — boot the backend and hit key REST endpoints.

These run against the FastAPI test client (no real server needed).
They verify that the app starts, routes are reachable, and the
/health endpoint returns expected structure.
"""
from __future__ import annotations

import json
import os

import pytest

# Ensure test env vars are set before any app import.
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
os.environ.setdefault("GENIE_PIN", "9999")
os.environ.setdefault("LOCAL_LLM_ENABLED", "false")
os.environ.setdefault("NGROK_ENABLED", "false")
os.environ.setdefault("WAKE_WORD_ENABLED", "false")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_has_status_ok(self, client):
        data = client.get("/health").json()
        assert data.get("status") == "ok"

    def test_health_has_tools_list(self, client):
        data = client.get("/health").json()
        assert isinstance(data.get("tools"), list)
        assert len(data["tools"]) > 0

    def test_health_has_circuit_breakers(self, client):
        data = client.get("/health").json()
        # circuit_breakers key should exist (may be empty list before any call)
        assert "circuit_breakers" in data

    def test_health_has_apis(self, client):
        data = client.get("/health").json()
        assert "apis" in data


class TestInfoEndpoint:
    def test_info_returns_200(self, client):
        resp = client.get("/info")
        assert resp.status_code == 200

    def test_info_requires_pin(self, client):
        data = client.get("/info").json()
        assert data.get("requires_pin") is True


class TestChatEndpoint:
    def test_chat_missing_text_returns_400(self, client):
        resp = client.post("/chat", json={})
        assert resp.status_code == 400

    def test_chat_empty_text_returns_400(self, client):
        resp = client.post("/chat", json={"text": ""})
        assert resp.status_code == 400


class TestApiStatusEndpoint:
    def test_apis_status_returns_200(self, client):
        resp = client.get("/api/v1/apis/status")
        # May return 404 if router not loaded, but should not 500.
        assert resp.status_code in (200, 404)
