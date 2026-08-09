"""
Interrupt Manager.

Coordinates barge-in interruption when the user speaks while Aura is talking.

Responsibilities
----------------
1. Set the TTS interrupt event and cancel the active TTS task.
2. Cancel the active AI generation task (stops token streaming).
3. Transition the state machine to INTERRUPTED → LISTENING.
4. Record partial response text that was cut off (for context continuity).
5. Track interrupt count and timing for metrics.

The InterruptManager does NOT own the TTS or AI tasks — it holds references
to them via asyncio.Event objects that are checked by the streaming loops.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.communication.state_machine import CommunicationState, StateMachine
from app.core.logging_config import get_logger

if TYPE_CHECKING:
    from app.communication.text_to_speech import TTSEngine

logger = get_logger(__name__)


@dataclass
class InterruptRecord:
    """Record of a single barge-in interruption."""
    timestamp: float
    partial_response: str       # AI text generated before interrupt
    tokens_generated: int
    tts_chunks_sent: int


class InterruptManager:
    """Manages barge-in interruption for a voice session.

    Usage::

        mgr = InterruptManager(session_id="abc", state_machine=sm)
        mgr.set_tts_engine(tts_engine)
        mgr.set_ai_interrupt_event(ai_event)

        # When VAD detects speech during SPEAKING:
        await mgr.trigger_interrupt()
    """

    def __init__(self, session_id: str, state_machine: StateMachine) -> None:
        self._session_id = session_id
        self._sm = state_machine

        self._tts_engine: "TTSEngine | None" = None
        self._ai_interrupt_event: asyncio.Event = asyncio.Event()
        self._lock = asyncio.Lock()

        self._records: list[InterruptRecord] = []
        self._partial_response: str = ""
        self._tokens_generated: int = 0
        self._tts_chunks_sent: int = 0

    # ── Wiring ────────────────────────────────────────────────────

    def set_tts_engine(self, engine: "TTSEngine") -> None:
        """Attach the TTS engine so interrupts can stop audio."""
        self._tts_engine = engine

    def get_ai_interrupt_event(self) -> asyncio.Event:
        """Return the asyncio.Event the AI streaming loop checks per token."""
        return self._ai_interrupt_event

    def clear_interrupt(self) -> None:
        """Clear interrupt state — call before starting a new AI generation."""
        self._ai_interrupt_event.clear()
        self._partial_response = ""
        self._tokens_generated = 0
        self._tts_chunks_sent = 0

    def record_token(self, token: str) -> None:
        """Track AI tokens generated (called by streaming loop)."""
        self._partial_response += token
        self._tokens_generated += 1

    def record_tts_chunk(self) -> None:
        """Track TTS audio chunks sent (called by TTS engine)."""
        self._tts_chunks_sent += 1

    # ── Interrupt ─────────────────────────────────────────────────

    async def trigger_interrupt(self) -> bool:
        """Execute a barge-in interruption.

        1. Set the AI generation interrupt event.
        2. Stop the TTS engine immediately.
        3. Transition state machine: SPEAKING → INTERRUPTED → LISTENING.
        4. Record interrupt details.

        Returns:
            True if interruption was executed; False if not in SPEAKING state.
        """
        async with self._lock:
            current = self._sm.state
            if current != CommunicationState.SPEAKING:
                logger.debug(
                    "Interrupt ignored — not in SPEAKING state",
                    session_id=self._session_id,
                    current_state=current.value,
                )
                return False

            logger.info(
                "Barge-in interrupt triggered",
                session_id=self._session_id,
                tokens_generated=self._tokens_generated,
                tts_chunks_sent=self._tts_chunks_sent,
            )

            # 1. Signal AI streaming to stop
            self._ai_interrupt_event.set()

            # 2. Stop TTS immediately
            if self._tts_engine:
                await self._tts_engine.stop()

            # 3. Record this interrupt
            record = InterruptRecord(
                timestamp=time.monotonic(),
                partial_response=self._partial_response,
                tokens_generated=self._tokens_generated,
                tts_chunks_sent=self._tts_chunks_sent,
            )
            self._records.append(record)

            # 4. Transition state
            try:
                await self._sm.transition(CommunicationState.INTERRUPTED)
                await self._sm.transition(CommunicationState.LISTENING)
            except ValueError as exc:
                logger.warning(
                    "State transition failed during interrupt",
                    session_id=self._session_id,
                    error=str(exc),
                )

            return True

    # ── Properties ────────────────────────────────────────────────

    @property
    def interrupt_count(self) -> int:
        """Total number of barge-in interruptions this session."""
        return len(self._records)

    @property
    def last_partial_response(self) -> str:
        """Text that was being generated when the last interrupt occurred."""
        if self._records:
            return self._records[-1].partial_response
        return ""

    @property
    def records(self) -> list[InterruptRecord]:
        """Full history of interrupt records (read-only copy)."""
        return list(self._records)

    @property
    def stats(self) -> dict:
        return {
            "interrupt_count": self.interrupt_count,
            "last_partial_response_chars": len(self.last_partial_response),
        }
