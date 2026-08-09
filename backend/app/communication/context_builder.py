"""
Context Builder.

Assembles the full AI context for a voice turn by combining:
  - Recent conversation history (from DB session)
  - Long-term user memories (from MemoryService)
  - User profile (preferred language, communication style, goals, interests)
  - Current transcript + emotion metadata

Wraps the existing PromptBuilder and MemoryService — the voice pipeline
uses the same prompt templates as the text chat, ensuring consistency.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import AIRequest
from app.communication.speech_to_text import TranscriptResult
from app.core.logging_config import get_logger
from app.models.message import Message
from app.models.user import User
from app.prompts.builder import PromptBuilder
from app.services.memory_service import MemoryService

logger = get_logger(__name__)

# Number of recent turns to include in context
_HISTORY_LIMIT = 8


class ContextBuilder:
    """Builds AIRequest context for a voice turn.

    Reuses existing PromptBuilder + MemoryService for consistency with
    the text chat pipeline.

    Args:
        db: Async database session.

    Usage::

        builder = ContextBuilder(db=db_session)
        request = await builder.build(
            user_id=42,
            session_id=7,
            transcript=transcript_result,
            conversation_history=history_list,
        )
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._memory = MemoryService(db)
        self._prompt_builder = PromptBuilder()

    async def build(
        self,
        user_id: int,
        session_id: int,
        transcript: TranscriptResult,
        conversation_history: list[dict] | None = None,
        emotion_data: dict[str, Any] | None = None,
        max_tokens: int = 500,
        temperature: float = 0.75,
    ) -> AIRequest:
        """Build a complete AIRequest for the current voice turn.

        Args:
            user_id: Authenticated user ID.
            session_id: Current database session ID.
            transcript: STT result for the current user utterance.
            conversation_history: In-memory history list (avoids DB re-query
                                  when the caller already has it).
            emotion_data: Optional emotion analysis dict.
            max_tokens: Response token budget.
            temperature: AI sampling temperature.

        Returns:
            AIRequest ready to pass to CommunicationAIGateway.
        """
        # 1. Load user profile
        user = await self._get_user(user_id)
        user_name = "there"
        user_profile: dict[str, Any] = {}
        if user:
            user_name = (user.name or "").split()[0] or "there"
            user_profile = {
                "preferred_language": user.preferred_language or "en",
                "communication_style": user.communication_style or "balanced",
                "interests": user.interests or "",
                "goals": user.goals or "",
            }

        # 2. Retrieve long-term memories
        long_term = await self._memory.get_memory_for_prompt(user_id)

        # 3. Get conversation history if not provided by caller
        if conversation_history is None:
            conversation_history = await self._get_db_history(session_id)

        # 4. Build system prompt + message list via shared PromptBuilder
        system_prompt, messages = self._prompt_builder.build(
            user_name=user_name,
            user_message=transcript.text,
            emotion_data=emotion_data,
            user_profile=user_profile,
            long_term_memories=long_term,
            conversation_history=conversation_history,
        )

        logger.debug(
            "Context built",
            user_id=user_id,
            session_id=session_id,
            history_turns=len(conversation_history),
            memories=len(long_term),
            transcript_chars=len(transcript.text),
        )

        return AIRequest(
            prompt=transcript.text,
            system_prompt=system_prompt,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )

    # ── Helpers ───────────────────────────────────────────────────

    async def _get_user(self, user_id: int) -> User | None:
        result = await self._db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def _get_db_history(self, session_id: int) -> list[dict]:
        """Fetch recent messages from the database."""
        result = await self._db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(_HISTORY_LIMIT)
        )
        messages = list(reversed(result.scalars().all()))
        return [{"role": m.role, "content": m.content} for m in messages]
