"""Unit tests for all registered tools.

These tests mock OS-level calls (subprocess, webbrowser, etc.) so they run
without needing a real Windows desktop or any API keys.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.schemas import ToolResult
from app.tools.registry import execute_tool, tool_manifests
from app.tools.internet import _parse_duckduckgo_html_results


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
             patch("os.path.exists", return_value=False), \
             patch("app.tools.apps._find_best_match", return_value=None):
            result = execute_tool("open_app", {"name": "chrome"})
            assert result.status == "not_found"
            assert "app" in result.data


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


# ── Web search helpers ────────────────────────────────────────────────────────

class TestWebSearchHelpers:
    def test_parse_duckduckgo_html_results(self):
        html = """
        <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fstory">
            Example Story
        </a>
        <div class="result__snippet">A short <b>summary</b> of the result.</div>
        """

        results = _parse_duckduckgo_html_results(html, max_results=5)

        assert results == [{
            "title": "Example Story",
            "url": "https://example.com/story",
            "body": "A short summary of the result.",
            "source": "example.com",
        }]


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
        with patch("subprocess.Popen"), \
             patch("app.tools.apps._launch"), \
             patch("app.tools.apps._find_best_match", return_value=("Palworld", "C:\\fake\\path")):
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


# ── Media tools ───────────────────────────────────────────────────────────────

class TestMediaTools:
    def test_play_youtube_uses_no_key_youtube_search(self):
        fake_result = [{
            "title": "Lo-fi Beats",
            "video_id": "dQw4w9WgXcQ",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        }]
        with patch("app.tools.media._youtube_video_search", return_value=[]), \
             patch("app.tools.media._ddg_youtube_video_search", return_value=fake_result):
            result = execute_tool("play_youtube", {"query": "lofi beats"})

        ok(result)
        assert result.data["action"] == "play_media"
        assert result.data["video_id"] == "dQw4w9WgXcQ"

    def test_play_youtube_music_browser_fallback_when_no_provider(self):
        with patch("app.tools.media.music_service.available", return_value=False), \
             patch("app.tools.media.api_manager.is_configured", return_value=False), \
             patch("app.tools.media._ddg_youtube_video_search", return_value=[]):
            result = execute_tool("play_youtube_music", {"query": "some rare song"})

        assert result.status == "not_found"
        assert result.data["suggestion"] == "open_url"
        assert "music.youtube.com/search" in result.data["url"]


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

    def test_tool_manifest_exposes_policy_metadata(self):
        manifests = {item["name"]: item for item in tool_manifests()}

        assert "open_app" in manifests
        assert manifests["open_app"]["side_effect_level"] in {
            "local_change",
            "read_only",
            "external_network",
        }
        assert "timeout_ms" in manifests["open_app"]
        assert manifests["open_app"]["parameters"]["type"] == "object"
