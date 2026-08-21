"""Pydantic models for the WebSocket message protocol and tool I/O.

Protocol summary
----------------
client -> server:
    {"type": "hello",      "pin": "1234"}
    {"type": "text",       "text": "open chrome"}
    {"type": "audio_end"}                # follows binary audio frames
    {"type": "cancel"}
    {"type": "heartbeat"}                # keep-alive ping from client
    {"type": "confirm",   "confirmed": true|false}  # response to confirm_required
  (binary frames are raw PCM/WebM audio chunks; STT decodes them)

server -> client:
    {"type": "auth_ok"|"auth_fail"}
    {"type": "public_url",  "url": "https://xxxx.ngrok-free.app"}
    {"type": "transcript",  "text": "open chrome"}
    {"type": "assistant_text", "delta": "...", "final": false}
    {"type": "assistant_audio_chunk", "audio": "<base64>", "mime": "audio/mpeg|audio/wav"}
    {"type": "assistant_audio_end"}
    {"type": "tool_start",  "name": "open_app", "args": {...}}
    {"type": "tool_end",    "name": "open_app", "result": {...}}
    {"type": "voice_state", "state": "idle|wake_listening|active_listening|processing|speaking|follow_up_listening|interrupted"}
    {"type": "error",       "message": "...", "code": "optional_error_code"}
    {"type": "pong"}                     # response to client heartbeat
    {"type": "wake_word_detected"}       # server-side wake word fired
    {"type": "confirm_required",         # user must confirm before tool runs
              "tool": "...",
              "description": "..."}
    {"type": "tts_playing"}             # TTS audio started — client mutes mic
    {"type": "tts_done"}                 # TTS audio ended — client re-enables mic
    {"type": "rate_limited",             # per-session rate limit hit
              "message": "...",
              "retry_after_seconds": 5}
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# ---- Orb / pipeline states the UI reacts to ----------------------------
OrbState = Literal["idle", "listening", "thinking", "speaking"]


class WSIn(BaseModel):
    """Validated inbound JSON message. Binary audio uses raw frames instead."""
    type: Literal[
        "hello", "text", "image", "audio_end", "cancel", "kill", "heartbeat", "confirm",
        "playback_complete", "manual_wake", "barge_in", "camera_frame",
        # Agent Runtime OS messages
        "goal",                   # { text: "research datasets and train model", context?: "..." }
        "task_action",            # { action: "pause"|"resume"|"cancel", task_id: "..." }
        # Companion Mode control messages
        "companion_start",        # { mode?: "gaming"|"coding"|"writing"|"general" }
        "companion_stop",         # {}
        "companion_pause",        # {}
        "companion_resume",       # {}
        "companion_set_mode",     # { mode: "gaming"|"coding"|"writing"|"general" }
        "companion_hotkey_analyze",  # on-demand single analysis (GameCompanionAI fallback)
        "companion_quick_look",   # { text?: "what does this error mean?" } (Quick Look fast path)
    ]
    pin: Optional[str] = None
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    text: Optional[str] = None
    frame: Optional[str] = None       # base64 image for image/camera_frame
    mime: Optional[str] = None
    filename: Optional[str] = None
    timestamp: Optional[int] = None   # client timestamp ms
    confirmed: Optional[bool] = None  # for "confirm" messages
    mode: Optional[str] = None        # for companion_start / companion_set_mode


class ToolResult(BaseModel):
    """Uniform return shape for every Python tool.

    The orchestrator stringifies `message` into the GLM tool result so the
    model can phrase a natural spoken reply.
    """
    status: Literal["ok", "not_found", "error"] = "ok"
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    # Metadata for the orchestrator — not forwarded to the client.
    requires_confirmation: bool = False  # if True, orchestrator will pause and ask user


class ClientMessage(BaseModel):
    """Convenience model for the REST /chat endpoint (non-WS clients)."""
    text: str
    session_id: Optional[str] = None


class ErrorMessage(BaseModel):
    """Server -> client error envelope."""
    type: Literal["error"] = "error"
    message: str
    code: Optional[str] = None  # machine-readable error code


class ConfirmRequired(BaseModel):
    """Server -> client confirmation request for a destructive tool."""
    type: Literal["confirm_required"] = "confirm_required"
    tool: str
    description: str


class RateLimited(BaseModel):
    """Server -> client rate limit notification."""
    type: Literal["rate_limited"] = "rate_limited"
    message: str
    retry_after_seconds: int = 5
