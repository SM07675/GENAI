"""
Session Manager.

Manages the lifecycle of VoiceSession objects and maintains the global
registry of active voice sessions.

VoiceSession
    One live voice conversation. Owns all per-session components:
    StateMachine, AudioStreamHandler, VoiceActivityDetector, STTEngine,
    TTSEngine, InterruptManager, VoiceConversationManager, CommunicationMetrics.

SessionRegistry
    In-memory dict of session_id → VoiceSession. Thread-safe via asyncio.Lock.
    Used by VoiceWebSocketManager to find the session for incoming messages.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.communication.audio_stream import AudioStreamHandler
from app.communication.conversation_manager import VoiceConversationManager
from app.communication.interrupt_manager import InterruptManager
from app.communication.metrics import CommunicationMetrics
from app.communication.speech_to_text import STTEngine
from app.communication.state_machine import CommunicationState, StateMachine
from app.communication.text_to_speech import TTSEngine
from app.communication.voice_activity import VoiceActivityDetector
from app.core.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class VoiceSession:
    """Represents one active voice conversation.

    Owns and wires up all pipeline components for a single session.
    Created by ``SessionRegistry.create_session()``.

    Args:
        session_id: Unique session UUID string.
        user_id: Authenticated user ID (0 for unauthenticated).
        db: SQLAlchemy async session.
    """

    def __init__(self, session_id: str, user_id: int, db: AsyncSession) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.created_at = datetime.now(timezone.utc)

        settings = get_settings()

        # ── State Machine ─────────────────────────────────────────
        self.state_machine = StateMachine(session_id=session_id)

        # ── Audio Pipeline ────────────────────────────────────────
        self.audio_handler = AudioStreamHandler(
            session_id=session_id,
            frame_ms=settings.vad_frame_duration_ms,
        )
        self.vad = VoiceActivityDetector(
            session_id=session_id,
            aggressiveness=settings.vad_aggressiveness,
            silence_threshold_ms=settings.vad_silence_threshold_ms,
            min_speech_ms=settings.vad_min_speech_ms,
            frame_ms=settings.vad_frame_duration_ms,
        )

        # ── STT ───────────────────────────────────────────────────
        self.stt = STTEngine.from_settings()

        # ── TTS ───────────────────────────────────────────────────
        self.tts = TTSEngine.from_settings(session_id=session_id)

        # ── Interrupt Manager ─────────────────────────────────────
        self.interrupt = InterruptManager(
            session_id=session_id,
            state_machine=self.state_machine,
        )
        self.interrupt.set_tts_engine(self.tts)

        # ── Metrics ───────────────────────────────────────────────
        self.metrics = CommunicationMetrics(session_id=session_id)

        # ── Conversation Manager ──────────────────────────────────
        self.conversation = VoiceConversationManager(
            session_id=session_id,
            user_id=user_id,
            db_session=db,
            state_machine=self.state_machine,
            interrupt_manager=self.interrupt,
            tts_engine=self.tts,
            stt_engine=self.stt,
            metrics=self.metrics,
        )

        # VAD processing task (runs as background asyncio Task)
        self._vad_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the session: initialize DB session and enter LISTENING state."""
        await self.conversation.initialize()
        await self.state_machine.transition(CommunicationState.LISTENING)
        logger.info("Voice session started", session_id=self.session_id, user_id=self.user_id)

    async def stop(self) -> None:
        """Gracefully stop the session and release resources."""
        # Cancel VAD loop
        if self._vad_task and not self._vad_task.done():
            self._vad_task.cancel()
            try:
                await self._vad_task
            except asyncio.CancelledError:
                pass

        # Stop TTS
        await self.tts.stop()

        # Close audio handler
        await self.audio_handler.close()

        # Close DB session
        await self.conversation.close()

        # Mark disconnected
        await self.state_machine.force_state(CommunicationState.DISCONNECTED)

        logger.info(
            "Voice session stopped",
            session_id=self.session_id,
            metrics=self.metrics.snapshot(),
        )

    def set_vad_task(self, task: asyncio.Task) -> None:
        """Register the background VAD processing task."""
        self._vad_task = task

    @property
    def state(self) -> CommunicationState:
        return self.state_machine.state


class SessionRegistry:
    """Thread-safe registry of active voice sessions.

    Usage::

        registry = SessionRegistry()
        session = await registry.create_session(user_id=42, db=db)
        ...
        await registry.destroy_session(session.session_id)
    """

    _instance: "SessionRegistry | None" = None

    def __init__(self) -> None:
        self._sessions: dict[str, VoiceSession] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def get(cls) -> "SessionRegistry":
        """Get or create the global SessionRegistry singleton."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def create_session(self, user_id: int, db: AsyncSession) -> VoiceSession:
        """Create and register a new voice session.

        Args:
            user_id: Authenticated user ID (0 for anonymous testing).
            db: SQLAlchemy async session (must stay open for session lifetime).

        Returns:
            Newly created and started VoiceSession.
        """
        session_id = str(uuid.uuid4())
        session = VoiceSession(session_id=session_id, user_id=user_id, db=db)

        async with self._lock:
            self._sessions[session_id] = session

        await session.start()
        logger.info("Session registered", session_id=session_id, total=len(self._sessions))
        return session

    async def destroy_session(self, session_id: str) -> None:
        """Stop and remove a session from the registry.

        Args:
            session_id: UUID of the session to destroy.
        """
        async with self._lock:
            session = self._sessions.pop(session_id, None)

        if session:
            await session.stop()
            logger.info("Session destroyed", session_id=session_id, remaining=len(self._sessions))

    def get_session(self, session_id: str) -> VoiceSession | None:
        """Look up a session by ID. Returns None if not found."""
        return self._sessions.get(session_id)

    @property
    def active_count(self) -> int:
        """Number of currently active sessions."""
        return len(self._sessions)

    async def destroy_all(self) -> None:
        """Destroy all active sessions (called on application shutdown)."""
        async with self._lock:
            session_ids = list(self._sessions.keys())

        for sid in session_ids:
            await self.destroy_session(sid)
