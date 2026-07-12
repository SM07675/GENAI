"""Unit tests for WebSocket message schemas (schemas.py)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import WSIn, ToolResult, ErrorMessage, ConfirmRequired, RateLimited


class TestWSIn:
    """Validate that WSIn accepts valid types and rejects unknown ones."""

    def test_hello_valid(self):
        msg = WSIn(type="hello", pin="1234")
        assert msg.type == "hello"
        assert msg.pin == "1234"

    def test_text_valid(self):
        msg = WSIn(type="text", text="open chrome")
        assert msg.text == "open chrome"

    def test_audio_end_valid(self):
        msg = WSIn(type="audio_end")
        assert msg.type == "audio_end"

    def test_cancel_valid(self):
        msg = WSIn(type="cancel")
        assert msg.type == "cancel"

    def test_heartbeat_valid(self):
        msg = WSIn(type="heartbeat")
        assert msg.type == "heartbeat"

    def test_confirm_valid(self):
        msg = WSIn(type="confirm", confirmed=True)
        assert msg.confirmed is True

    def test_unknown_type_rejected(self):
        with pytest.raises(ValidationError):
            WSIn(type="unknown_garbage")

    def test_extra_fields_ignored(self):
        """Pydantic model_config should ignore extra fields."""
        msg = WSIn(type="text", text="hello", extra_field="should_be_ignored")
        assert msg.type == "text"


class TestToolResult:
    def test_ok_status(self):
        r = ToolResult(status="ok", message="Done")
        assert r.status == "ok"
        assert r.data == {}

    def test_error_status(self):
        r = ToolResult(status="error", message="Something broke")
        assert r.status == "error"

    def test_not_found_status(self):
        r = ToolResult(status="not_found", message="App not found", data={"app": "notepad"})
        assert r.data["app"] == "notepad"

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            ToolResult(status="invalid", message="Bad")


class TestServerMessages:
    def test_error_message(self):
        m = ErrorMessage(message="Something failed", code="E001")
        assert m.type == "error"
        assert m.code == "E001"

    def test_confirm_required(self):
        m = ConfirmRequired(tool="sleep_pc", description="This will put the PC to sleep.")
        assert m.type == "confirm_required"

    def test_rate_limited(self):
        m = RateLimited(message="Slow down", retry_after_seconds=10)
        assert m.retry_after_seconds == 10
