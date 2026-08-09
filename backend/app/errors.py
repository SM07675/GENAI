"""Typed Error Taxonomy for Genie OS (§1.2, §1.3).

All errors across voice, vision, LLM, TTS, Companion Brain, screen capture,
backend process, and tools inherit from GenieError and specify:
1. code: machine-readable error code string
2. user_message: clean, human-friendly message (never raw tracebacks)
3. recoverable: bool indicating if automatic recovery/retry is expected
4. debug_detail: string with diagnostic context (logged, never shown to user)
"""
from __future__ import annotations

from typing import Any, Optional


class GenieError(Exception):
    """Base exception for all domain-specific Genie errors."""

    def __init__(
        self,
        message: str,
        code: str = "GENIE_ERROR",
        user_message: str = "An unexpected error occurred in Genie.",
        recoverable: bool = True,
        debug_detail: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.user_message = user_message
        self.recoverable = recoverable
        self.debug_detail = debug_detail or message

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": True,
            "code": self.code,
            "message": self.user_message,
            "recoverable": self.recoverable,
        }


class BackendUnavailableError(GenieError):
    """Raised when the FastAPI sidecar or a core engine dependency is offline."""

    def __init__(self, detail: str = "Backend server is not responding") -> None:
        super().__init__(
            message=detail,
            code="BACKEND_UNAVAILABLE",
            user_message="Genie backend service is temporarily unavailable.",
            recoverable=True,
            debug_detail=detail,
        )


class VisionProviderError(GenieError):
    """Raised when the multimodal vision API (NVIDIA Nemotron 12B VL) fails."""

    def __init__(self, detail: str = "Vision API request failed") -> None:
        super().__init__(
            message=detail,
            code="VISION_PROVIDER_ERROR",
            user_message="I took a look at your screen, but couldn't analyze it right now.",
            recoverable=True,
            debug_detail=detail,
        )


class TTSStreamError(GenieError):
    """Raised when Text-to-Speech synthesis fails."""

    def __init__(self, detail: str = "TTS synthesis failed") -> None:
        super().__init__(
            message=detail,
            code="TTS_STREAM_ERROR",
            user_message="Voice output synthesis failed.",
            recoverable=True,
            debug_detail=detail,
        )


class ToolExecutionError(GenieError):
    """Raised when an OS, media, or web search tool fails execution."""

    def __init__(self, tool_name: str, detail: str) -> None:
        super().__init__(
            message=f"Tool {tool_name} failed: {detail}",
            code="TOOL_EXECUTION_ERROR",
            user_message=f"Could not complete action for tool '{tool_name}'.",
            recoverable=False,
            debug_detail=f"Tool {tool_name} error: {detail}",
        )


class CaptureDeniedError(GenieError):
    """Raised when mss / Win32 cannot capture screen surface (DRM or anti-cheat)."""

    def __init__(self, detail: str = "Screen capture blocked or failed") -> None:
        super().__init__(
            message=detail,
            code="CAPTURE_DENIED",
            user_message="I can't see that window right now, but tell me what's happening and I'll help.",
            recoverable=True,
            debug_detail=detail,
        )
