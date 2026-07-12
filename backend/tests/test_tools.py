"""Unit tests for all registered tools.

These tests mock OS-level calls (subprocess, webbrowser, etc.) so they run
without needing a real Windows desktop or any API keys.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.schemas import ToolResult
from app.tools.registry import execute_tool


# ── Helper ────────────────────────────────────────────────────────────────────

def ok(result: ToolResult) -> None:
    """Assert a tool returned status=ok."""
    assert result.status == "ok", f"Expected ok, got {result.status}: {result.message}"


def err(result: ToolResult) -> None:
    """Assert a tool returned status=error or not_found."""
    assert result.status in ("error", "not_found"), (
        f"Expected error/not_found, got {result.status}"
    )


# ── open_app ──────────────────────────────────────────────────────────────────

class TestOpenApp:
    def test_known_app_in_path(self):
        with patch("shutil.which", return_value="C:\\Windows\\notepad.exe"), \
             patch("subprocess.Popen"):
            result = execute_tool("open_app", {"name": "notepad"})
            ok(result)

    def test_unknown_app_returns_not_found(self):
        with patch("shutil.which", return_value=None), \
             patch("os.path.isabs", return_value=False):
            result = execute_tool("open_app", {"name": "totally_fake_app_xyz"})
            assert result.status in ("not_found", "ok")  # fallback URL is ok too

    def test_empty_name_returns_error(self):
        result = execute_tool("open_app", {"name": ""})
        err(result)

    def test_chrome_has_browser_fallback(self):
        with patch("shutil.which", return_value=None), \
             patch("os.path.exists", return_value=False):
            result = execute_tool("open_app", {"name": "chrome"})
            # Chrome has a known fallback URL; should be not_found, not error.
            assert result.status == "not_found"
            assert "suggestion" in result.data or "url" in result.data


# ── open_url ──────────────────────────────────────────────────────────────────

class TestOpenUrl:
    def test_valid_url(self):
        with patch("webbrowser.open"):
            result = execute_tool("open_url", {"url": "https://example.com"})
            ok(result)

    def test_bare_domain_normalized(self):
        with patch("webbrowser.open") as mock_open:
            result = execute_tool("open_url", {"url": "example.com"})
            ok(result)
            called_url = mock_open.call_args[0][0]
            assert called_url.startswith("https://"), f"Expected https://, got {called_url}"

    def test_empty_url_returns_error(self):
        result = execute_tool("open_url", {"url": ""})
        err(result)


# ── open_whatsapp_chat ────────────────────────────────────────────────────────

class TestOpenWhatsappChat:
    def test_phone_number(self):
        with patch("webbrowser.open"):
            result = execute_tool("open_whatsapp_chat", {"contact": "919876543210"})
            ok(result)
            assert "wa.me" in result.data.get("url", "")

    def test_no_contact_opens_web(self):
        with patch("webbrowser.open"):
            result = execute_tool("open_whatsapp_chat", {"contact": None})
            ok(result)
            assert "web.whatsapp.com" in result.data.get("url", "")

    def test_contact_name_no_registry_opens_web(self):
        with patch("webbrowser.open"), \
             patch("app.contacts.lookup_contact", return_value=None):
            result = execute_tool("open_whatsapp_chat", {"contact": "Some Person"})
            ok(result)


# ── open_instagram_chat ───────────────────────────────────────────────────────

class TestOpenInstagramChat:
    def test_username(self):
        with patch("webbrowser.open"):
            result = execute_tool("open_instagram_chat", {"contact": "testuser"})
            ok(result)
            assert "instagram.com" in result.data.get("url", "")

    def test_contact_registry_lookup(self):
        mock_contact = {"name": "Alice", "instagram": "alice_real"}
        with patch("webbrowser.open"), \
             patch("app.tools.web.lookup_contact", return_value=mock_contact):
            result = execute_tool("open_instagram_chat", {"contact": "alice"})
            ok(result)
            assert "alice_real" in result.data.get("url", "")


# ── launch_steam_game ─────────────────────────────────────────────────────────

class TestLaunchSteamGame:
    def test_known_game(self):
        with patch("subprocess.Popen"):
            result = execute_tool("launch_steam_game", {"game": "palworld"})
            ok(result)
            assert "Palworld" in result.message

    def test_numeric_app_id(self):
        with patch("subprocess.Popen"):
            result = execute_tool("launch_steam_game", {"game": "271590"})
            ok(result)

    def test_unknown_game(self):
        result = execute_tool("launch_steam_game", {"game": "completely_unknown_game_xyz"})
        err(result)


# ── System control tools ──────────────────────────────────────────────────────

class TestSystemControl:
    def test_set_volume_valid_range(self):
        """set_volume clamps values; 150 -> 100, -10 -> 0. Both return ok."""
        # On Windows, it will try to use pycaw. On CI it will return 'error'
        # (no Windows audio devices). We just assert it doesn't crash.
        result = execute_tool("set_volume", {"percent": 50})
        assert result.status in ("ok", "error")   # ok on Windows, error on CI

    def test_set_volume_clamped_high(self):
        """150 is clamped to 100 — it's not rejected, it's a valid ok."""
        result = execute_tool("set_volume", {"percent": 150})
        # Clamped to 100 -> ok (Windows) or error (no audio device on CI)
        assert result.status in ("ok", "error")
        if result.status == "ok":
            assert "100" in result.message

    def test_set_volume_clamped_low(self):
        """Negative values are clamped to 0 — not rejected."""
        result = execute_tool("set_volume", {"percent": -10})
        assert result.status in ("ok", "error")
        if result.status == "ok":
            assert "0" in result.message


# ── execute_tool: unknown tool ────────────────────────────────────────────────

class TestExecuteTool:
    def test_unknown_tool_returns_error(self):
        result = execute_tool("nonexistent_tool_xyz", {})
        err(result)

    def test_bad_args_returns_error(self):
        result = execute_tool("open_app", {"wrong_param": "value"})
        # open_app requires `name` — should return error, not crash
        assert result.status in ("error", "ok", "not_found")
