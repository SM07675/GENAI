"""LLM Router — intent-based dispatch with cancellation support.

Routes user utterances through the pipeline:
1. Intent analyzer (deterministic fast path)
2. Orchestrator (LLM streaming with tool calling)

Wraps the existing ``orchestrator.handle_user_turn()`` with:
- Cancellation token injection
- Context resolution
- Local intent short-circuiting
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional

import structlog

from ..auth import Session
from ..config import Settings, get_settings
from .cancellation import CancellationToken
from .context_manager import ContextManager
from .intent_analyzer import IntentAnalyzer, IntentType

log = structlog.get_logger("genie.engine.llm_router")

Emitter = Callable[[dict], Awaitable[None]]


class LLMRouter:
    """Routes user text to the right handler: local intent or LLM."""

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()
        self._intent_analyzer = IntentAnalyzer()

    async def process(
        self,
        user_text: str,
        session: Session,
        context: ContextManager,
        emit: Emitter,
        cancel_token: Optional[CancellationToken] = None,
    ) -> dict:
        """Process user text through the intent→LLM pipeline.

        Returns a result dict with:
            text: str — the assistant's response
            handled_locally: bool — True if no LLM was needed
            interrupted: bool — True if cancelled mid-generation
            tool_calls: list — tool calls made during the turn
        """
        # Strip wake phrase
        clean_text = self._intent_analyzer.strip_wake_phrase(user_text)
        if not clean_text:
            return await self._handle_wake_only(emit)

        # Check for local intent
        intent = self._intent_analyzer.classify(clean_text)

        if intent == IntentType.STOP_AUDIO:
            return await self._handle_stop_audio(emit)

        if intent == IntentType.CLEAR_HISTORY:
            return await self._handle_clear_history(session, context, emit)

        if intent == IntentType.PLAY_MUSIC:
            return await self._handle_play_music(emit)

        if intent == IntentType.REPEAT:
            return await self._handle_repeat(context, emit)

        if intent == IntentType.GREETING:
            # Let the LLM handle greetings for personality
            pass

        # Resolve references using context
        resolved_text = context.resolve_references(clean_text)

        # Check for cancellation before starting LLM
        if cancel_token and cancel_token.is_cancelled:
            return {
                "text": "",
                "handled_locally": False,
                "interrupted": True,
                "tool_calls": [],
            }

        # Route to the orchestrator (LLM + tool calling)
        return await self._route_to_llm(
            resolved_text, session, context, emit, cancel_token
        )

    async def _route_to_llm(
        self,
        text: str,
        session: Session,
        context: ContextManager,
        emit: Emitter,
        cancel_token: Optional[CancellationToken] = None,
    ) -> dict:
        """Run the full orchestrator pipeline with cancellation support."""
        from ..orchestrator import handle_user_turn

        result = {
            "text": "",
            "handled_locally": False,
            "interrupted": False,
            "tool_calls": [],
        }

        # Create a wrapped emitter that captures the final response
        response_parts: list[str] = []
        tool_calls: list[dict] = []

        async def capturing_emit(msg: dict) -> None:
            msg_type = msg.get("type")

            # Capture text deltas
            if msg_type == "assistant_text" and msg.get("delta"):
                response_parts.append(msg["delta"])

            # Capture tool calls
            if msg_type == "tool_start":
                tool_calls.append({
                    "name": msg.get("name"),
                    "arguments": msg.get("args"),
                })

            # Forward everything to the WebSocket
            await emit(msg)

        try:
            await handle_user_turn(
                session=session,
                user_text=text,
                emit=capturing_emit,
                settings=self._settings,
                cancel_token=cancel_token,
            )

            result["text"] = "".join(response_parts).strip()
            result["tool_calls"] = tool_calls

        except asyncio.CancelledError:
            result["text"] = "".join(response_parts).strip()
            result["interrupted"] = True
            result["tool_calls"] = tool_calls
            log.info("llm_turn_cancelled", text_so_far=result["text"][:80])

        except Exception as exc:
            log.error("llm_turn_error", error=str(exc))
            await emit({
                "type": "error",
                "message": "Something went wrong. Please try again.",
                "code": type(exc).__name__,
            })

        return result

    # ── Local Intent Handlers ─────────────────────────────────────────────

    async def _handle_wake_only(self, emit: Emitter) -> dict:
        text = "Yes, I'm listening."
        await emit({"type": "assistant_text", "delta": text, "final": True})
        return {"text": text, "handled_locally": True, "interrupted": False, "tool_calls": []}

    async def _handle_stop_audio(self, emit: Emitter) -> dict:
        await emit({"type": "stop_media"})
        text = "*[Audio stopped]*"
        await emit({"type": "assistant_text", "delta": text, "final": True})
        return {"text": text, "handled_locally": True, "interrupted": False, "tool_calls": []}

    async def _handle_clear_history(
        self, session: Session, context: ContextManager, emit: Emitter
    ) -> dict:
        session.history.clear()
        context.clear()
        text = "*[Conversation history cleared]*"
        await emit({"type": "assistant_text", "delta": text, "final": True})
        return {"text": text, "handled_locally": True, "interrupted": False, "tool_calls": []}

    async def _handle_play_music(self, emit: Emitter) -> dict:
        text = "*[Resuming music playback]*"
        await emit({"type": "assistant_text", "delta": text, "final": True})
        await emit({"type": "play_media", "playlist_id": "PLw-VjHDlEOgs658kAHR_LAaILBXb-s6Q5"})
        return {"text": text, "handled_locally": True, "interrupted": False, "tool_calls": []}

    async def _handle_repeat(self, context: ContextManager, emit: Emitter) -> dict:
        last = context.get_last_assistant_text()
        if last:
            text = last
        else:
            text = "I don't have a previous response to repeat."
        await emit({"type": "assistant_text", "delta": text, "final": True})
        return {"text": text, "handled_locally": True, "interrupted": False, "tool_calls": []}
