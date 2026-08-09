"""
Voice Conversation Manager.

Orchestrates the complete voice pipeline for a single session turn:

    STT transcript
      → ContextBuilder (system prompt + history + memories)
      → CommunicationAIGateway (streaming AI response)
      → ResponseStreamer (text → WebSocket + TTS)
      → Message persistence (DB)
      → Memory update

Also manages the in-memory conversation history so context is available
immediately without hitting the database on every turn.

Interruption handling
---------------------
When interrupted mid-response, the partial AI response is recorded with
an "[interrupted]" marker and added to history so the next turn has
accurate context. The user's new utterance is then processed normally.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import AIRequest
from app.communication.ai_gateway import CommunicationAIGateway
from app.communication.context_builder import ContextBuilder
from app.communication.interrupt_manager import InterruptManager
from app.communication.metrics import CommunicationMetrics
from app.communication.speech_to_text import TranscriptResult, STTEngine
from app.communication.streaming import ResponseStreamer
from app.communication.text_to_speech import TTSEngine
from app.communication.state_machine import CommunicationState, StateMachine
from app.core.logging_config import get_logger
from app.models.message import Message, MessageRole, MessageType
from app.models.session import Session, SessionStatus

logger = get_logger(__name__)

# How many turns to keep in in-memory history
_HISTORY_WINDOW = 12

# Type aliases
TextCallback = Callable[[str], Awaitable[None]]
AudioCallback = Callable[[bytes, int], Awaitable[None]]
EventCallback = Callable[[str, dict], Awaitable[None]]


class VoiceConversationManager:
    """Orchestrates a complete voice conversation for one session.

    Args:
        session_id: Voice session UUID.
        user_id: Authenticated user ID (or 0 for unauthenticated testing).
        db_session: SQLAlchemy async session for persistence.
        state_machine: Shared session state machine.
        interrupt_manager: Shared interrupt coordinator.
        tts_engine: TTS engine instance.
        stt_engine: STT engine instance.
        metrics: Session metrics collector.

    Callbacks registered via set_* methods decouple output channels:
        on_text_token  – called per AI token (→ WebSocket partial_response)
        on_audio_chunk – called per TTS MP3 chunk (→ WebSocket audio_chunk)
        on_event       – called for named pipeline events (→ WebSocket events)
    """

    def __init__(
        self,
        session_id: str,
        user_id: int,
        db_session: AsyncSession,
        state_machine: StateMachine,
        interrupt_manager: InterruptManager,
        tts_engine: TTSEngine,
        stt_engine: STTEngine,
        metrics: CommunicationMetrics,
    ) -> None:
        self._session_id = session_id
        self._user_id = user_id
        self._db = db_session
        self._sm = state_machine
        self._interrupt = interrupt_manager
        self._tts = tts_engine
        self._stt = stt_engine
        self._metrics = metrics

        self._ai_gateway = CommunicationAIGateway(session_id=session_id)
        self._context_builder = ContextBuilder(db=db_session)

        # In-memory conversation history (role, content dicts)
        self._history: list[dict[str, str]] = []
        # Database session ID (set after first DB session creation)
        self._db_session_id: int | None = None

        # Callbacks (set after construction)
        self._on_text: TextCallback | None = None
        self._on_audio: AudioCallback | None = None
        self._on_event: EventCallback | None = None

    # ── Callback wiring ───────────────────────────────────────────

    def on_text_token(self, cb: TextCallback) -> None:
        self._on_text = cb

    def on_audio_chunk(self, cb: AudioCallback) -> None:
        self._on_audio = cb

    def on_event(self, cb: EventCallback) -> None:
        self._on_event = cb

    # ── Lifecycle ─────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Create or load a DB session for this voice conversation."""
        if self._user_id:
            db_session = Session(
                user_id=self._user_id,
                status=SessionStatus.ACTIVE.value,
            )
            self._db.add(db_session)
            await self._db.commit()
            await self._db.refresh(db_session)
            self._db_session_id = db_session.id
            logger.info(
                "DB session created for voice conversation",
                session_id=self._session_id,
                db_session_id=self._db_session_id,
            )
        else:
            logger.info(
                "No user_id — running in unauthenticated test mode",
                session_id=self._session_id,
            )

    async def close(self) -> None:
        """End the DB session on disconnect."""
        if self._db_session_id and self._user_id:
            from sqlalchemy import select
            result = await self._db.execute(
                select(Session).where(Session.id == self._db_session_id)
            )
            db_session = result.scalar_one_or_none()
            if db_session:
                db_session.status = SessionStatus.ENDED.value
                db_session.ended_at = datetime.now(timezone.utc)
                await self._db.commit()

    # ── Main Turn Handler ─────────────────────────────────────────

    async def process_transcript(self, transcript: TranscriptResult) -> None:
        """Process a final STT transcript through the full AI + TTS pipeline.

        This is the main turn handler. Called once per speech_ended event.

        Args:
            transcript: Final STT result for the current utterance.
        """
        if not transcript.text.strip():
            logger.debug("Empty transcript, skipping turn", session_id=self._session_id)
            await self._sm.transition(CommunicationState.LISTENING)
            return

        # ── 1. Persist user message ───────────────────────────────
        await self._persist_message(
            role=MessageRole.USER.value, content=transcript.text
        )
        self._history.append({"role": "user", "content": transcript.text})
        self._trim_history()

        if self._on_event:
            await self._on_event("final_transcript", {
                "text": transcript.text,
                "confidence": round(transcript.confidence, 3),
            })

        # ── 2. Build AI context ───────────────────────────────────
        await self._sm.transition(CommunicationState.GENERATING)
        if self._on_event:
            await self._on_event("generating", {})

        try:
            ai_request = await self._context_builder.build(
                user_id=self._user_id,
                session_id=self._db_session_id or 0,
                transcript=transcript,
                conversation_history=list(self._history[:-1]),  # exclude current
            )
        except Exception as exc:
            logger.error(
                "Context build failed",
                session_id=self._session_id,
                error=str(exc),
            )
            await self._handle_error("CONTEXT_ERROR", str(exc))
            return

        # ── 3. Reset interrupt state for this turn ────────────────
        self._interrupt.clear_interrupt()

        # ── 4. Start AI streaming ─────────────────────────────────
        await self._sm.transition(CommunicationState.SPEAKING)
        if self._on_event:
            await self._on_event("speaking", {})
        self._metrics.record_first_token()  # approximate (real timestamp in streamer)

        # Wire up text token → WebSocket callback
        async def on_token(token: str) -> None:
            if self._on_text:
                await self._on_text(token)
            self._interrupt.record_token(token)

        # Wire up sentence chunk → TTS
        async def on_speak(text: str) -> None:
            await self._tts.speak(text)

        streamer = ResponseStreamer(
            session_id=self._session_id,
            on_text=on_token,
            on_speak=on_speak,
        )

        try:
            token_stream = self._ai_gateway.stream_with_interrupt(
                request=ai_request,
                interrupt_event=self._interrupt.get_ai_interrupt_event(),
            )

            full_response, was_interrupted = await streamer.stream(
                token_stream=token_stream,
                interrupt_event=self._interrupt.get_ai_interrupt_event(),
            )
        except Exception as exc:
            logger.error(
                "AI streaming failed",
                session_id=self._session_id,
                error=str(exc),
            )
            await self._handle_error("PROVIDER_ERROR", "Provider Error")
            return

        # ── 5. Persist and update history ─────────────────────────
        if full_response:
            # Add interruption marker if applicable
            content = full_response
            if was_interrupted and self._interrupt.last_partial_response:
                content = f"{full_response} [interrupted]"

            await self._persist_message(
                role=MessageRole.ASSISTANT.value,
                content=content,
                ai_provider="voice_gateway",
            )
            self._history.append({"role": "assistant", "content": content})
            self._trim_history()

        self._metrics.end_turn(interrupted=was_interrupted)

        # ── 6. Transition back to LISTENING ───────────────────────
        if not was_interrupted and self._sm.state == CommunicationState.SPEAKING:
            await self._sm.transition(CommunicationState.LISTENING)
            if self._on_event:
                await self._on_event("completed", {
                    "chars": len(full_response),
                    "interrupted": was_interrupted,
                })

        logger.info(
            "Turn complete",
            session_id=self._session_id,
            response_chars=len(full_response),
            interrupted=was_interrupted,
        )

    # ── Helpers ───────────────────────────────────────────────────

    async def _persist_message(
        self,
        role: str,
        content: str,
        ai_provider: str | None = None,
    ) -> None:
        """Persist a message to the database (fire-and-forget on failure)."""
        if not self._db_session_id:
            return
        try:
            msg = Message(
                session_id=self._db_session_id,
                user_id=self._user_id or None,
                role=role,
                content=content,
                message_type=MessageType.VOICE.value
                if hasattr(MessageType, "VOICE")
                else MessageType.TEXT.value,
                ai_provider=ai_provider,
            )
            self._db.add(msg)
            await self._db.commit()
        except Exception as exc:
            logger.warning(
                "Message persist failed",
                session_id=self._session_id,
                error=str(exc),
            )

    async def _handle_error(self, code: str, message: str) -> None:
        """Transition to ERROR state and notify client."""
        self._metrics.record_error()
        try:
            await self._sm.force_state(CommunicationState.ERROR)
        except Exception:
            pass
        if self._on_event:
            await self._on_event("error", {"code": code, "message": message})

    def _trim_history(self) -> None:
        """Keep in-memory history within the window limit."""
        if len(self._history) > _HISTORY_WINDOW:
            self._history = self._history[-_HISTORY_WINDOW:]

    @property
    def history(self) -> list[dict[str, str]]:
        """Current in-memory conversation history (read-only copy)."""
        return list(self._history)
