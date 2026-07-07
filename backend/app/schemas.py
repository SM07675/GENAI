"""Pydantic models for the WebSocket message protocol and tool I/O.

Protocol summary
----------------
client -> server:
    {"type": "hello",      "pin": "1234"}
    {"type": "text",       "text": "open chrome"}
    {"type": "audio_end"}                # follows binary audio frames
    {"type": "cancel"}
  (binary frames are raw PCM/WebM audio chunks; STT decodes them)

server -> client:
    {"type": "auth_ok"|"auth_fail"}
    {"type": "public_url",  "url": "https://xxxx.ngrok-free.app"}
    {"type": "transcript",  "text": "open chrome"}
    {"type": "assistant_text", "delta": "...", "final": false}
    {"type": "assistant_audio", "audio": "<base64 mp3>"}
    {"type": "tool_start",  "name": "open_app", "args": {...}}
    {"type": "tool_end",    "name": "open_app", "result": {...}}
    {"type": "orb_state",   "state": "idle|listening|thinking|speaking"}
    {"type": "error",       "message": "..."}
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# ---- Orb / pipeline states the UI reacts to ----------------------------
OrbState = Literal["idle", "listening", "thinking", "speaking"]


class WSIn(BaseModel):
    """Validated inbound JSON message. Binary audio uses raw frames instead."""
    type: Literal["hello", "text", "audio_end", "cancel"]
    pin: Optional[str] = None
    text: Optional[str] = None


class ToolResult(BaseModel):
    """Uniform return shape for every Python tool.

    The orchestrator stringifies `message` into the GLM tool result so the
    model can phrase a natural spoken reply.
    """
    status: Literal["ok", "not_found", "error"] = "ok"
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class ClientMessage(BaseModel):
    """Convenience model for the REST /chat endpoint (non-WS clients)."""
    text: str
    session_id: Optional[str] = None
