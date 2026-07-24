"""LLM streaming wrapper with cancellation and TTS integration.

Wraps the existing orchestrator.handle_user_turn with:
- Proper cancellation token injection
- Text delta capture for TTS pipeline
- Context recording
- Metrics tracking

The orchestrator remains the source of truth for LLM interaction,
tool calling, and response generation. This wrapper adds the pipeline
integration layer.
"""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Optional

import structlog

from ...auth import Session
from ...config import Settings, get_settings
from ..cancellation import CancellationToken
from ..event_bus import PipelineEvent, engine_events
from ..metrics import pipeline_metrics
from .context import UnifiedContext
from .intent_router import IntentRouter, IntentType

log = structlog.get_logger("genie.engine.brain.llm_stream")

Emitter = Callable[[dict], Awaitable[None]]


class LLMStream:
    """Orchestrates the LLM turn with text delta streaming.

    Captures text deltas for the TTS pipeline while forwarding all
    events to the WebSocket emitter.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()
        self._intent_router = IntentRouter()
        self._last_heartbeat = time.time()

    async def process(
        self,
        user_text: str,
        session: Session,
        context: UnifiedContext,
        emit: Emitter,
        cancel_token: Optional[CancellationToken] = None,
        on_text_delta: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> dict:
        """Process user text through the intent → LLM pipeline.

        Args:
            user_text: Raw user transcript.
            session: Authenticated session.
            context: Unified context for this session.
            emit: WebSocket emitter.
            cancel_token: Cooperative cancellation.
            on_text_delta: Callback for each text delta (feeds TTS worker).

        Returns:
            dict with keys: text, handled_locally, interrupted, tool_calls
        """
        # Strip wake phrase (ONLY here, never again)
        clean_text = self._intent_router.strip_wake_phrase(user_text)
        if not clean_text:
            return await self._handle_wake_only(emit)

        # Check for local intent
        intent = self._intent_router.classify(clean_text)

        if intent == IntentType.STOP_AUDIO:
            return await self._handle_stop_audio(emit)

        if intent == IntentType.CLEAR_HISTORY:
            return await self._handle_clear_history(session, context, emit)

        if intent == IntentType.PLAY_MUSIC:
            return await self._handle_play_music(emit)

        if intent == IntentType.REPEAT:
            return await self._handle_repeat(context, emit)

        # Resolve references using context
        resolved_text = context.resolve_references(clean_text)

        # Check cancellation before LLM
        if cancel_token and cancel_token.is_cancelled:
            return {
                "text": "",
                "handled_locally": False,
                "interrupted": True,
                "tool_calls": [],
            }

        # Route to orchestrator (LLM + tool calling)
        return await self._route_to_llm(
            resolved_text, session, context, emit,
            cancel_token, on_text_delta,
        )

    async def _route_to_llm(
        self,
        text: str,
        session: Session,
        context: UnifiedContext,
        emit: Emitter,
        cancel_token: Optional[CancellationToken] = None,
        on_text_delta: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> dict:
        """Run the full orchestrator pipeline."""
        from ...orchestrator import handle_user_turn

        result = {
            "text": "",
            "handled_locally": False,
            "interrupted": False,
            "tool_calls": [],
        }

        response_parts: list[str] = []
        tool_calls: list[dict] = []
        timer = pipeline_metrics.time("llm.turn")

        # Messages that the pipeline manages directly via TTSStreamWorker.
        # When on_text_delta is provided (pipeline mode), suppress them so the
        # orchestrator's inline TTS consumer doesn't fight the pipeline's TTS.
        _PIPELINE_OWNED_TYPES = {
            "assistant_audio_chunk", "tts_done", "tts_playing",
            "assistant_audio_end",
        }

        async def capturing_emit(msg: dict) -> None:
            msg_type = msg.get("type")

            # Capture text deltas and forward to TTS pipeline
            if msg_type == "assistant_text" and msg.get("delta"):
                delta = msg["delta"]
                response_parts.append(delta)
                # Feed the pipeline's TTSStreamWorker
                if on_text_delta and not msg.get("final"):
                    try:
                        await on_text_delta(delta)
                    except Exception as e:
                        log.warning("text_delta_callback_error", error=str(e))

            # Capture tool calls
            if msg_type == "tool_start":
                tool_calls.append({
                    "name": msg.get("name"),
                    "arguments": msg.get("args"),
                })

            # In pipeline mode: drop orchestrator-level audio/TTS messages —
            # the pipeline owns those transitions via TTSStreamWorker.
            if on_text_delta and msg_type in _PIPELINE_OWNED_TYPES:
                return
            if on_text_delta and msg_type == "orb_state" and msg.get("state") == "speaking":
                return

            # Forward everything else to the WebSocket
            await emit(msg)

        try:
            await handle_user_turn(
                session=session,
                user_text=text,
                emit=capturing_emit,
                settings=self._settings,
                cancel_token=cancel_token,
                skip_wake_strip=True,  # pipeline already stripped it
            )

            result["text"] = "".join(response_parts).strip()
            result["tool_calls"] = tool_calls
            timer.finish()
            self._last_heartbeat = time.time()

        except asyncio.CancelledError:
            result["text"] = "".join(response_parts).strip()
            result["interrupted"] = True
            result["tool_calls"] = tool_calls
            timer.finish()
            log.info("llm_turn_cancelled", text_so_far=result["text"][:80])

        except Exception as exc:
            timer.finish()
            log.error("llm_turn_error", error=str(exc))
            pipeline_metrics.record_error("llm", str(exc))
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
        self, session: Session, context: UnifiedContext, emit: Emitter
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

    async def _handle_repeat(self, context: UnifiedContext, emit: Emitter) -> dict:
        last = context.get_last_assistant_text()
        if last:
            text = last
        else:
            text = "I don't have a previous response to repeat."
        await emit({"type": "assistant_text", "delta": text, "final": True})
        return {"text": text, "handled_locally": True, "interrupted": False, "tool_calls": []}

    @property
    def heartbeat(self) -> float:
        return self._last_heartbeat
