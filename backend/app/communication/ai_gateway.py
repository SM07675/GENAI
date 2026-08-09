"""
Communication AI Gateway.

A thin adapter around the existing AIGateway that adds voice-session
awareness:

  - Accepts an asyncio.Event for interrupt-checking between tokens.
  - Builds an AIRequest from a TranscriptResult + voice session metadata.
  - Provides ``stream_with_interrupt()`` which yields StreamChunks but
    stops immediately when the interrupt event fires.

The existing AIGateway handles multi-provider fallback and circuit-breaking,
so this adapter focuses only on voice-specific concerns.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

from app.ai.base import AIRequest, StreamChunk
from app.ai.gateway import AIGateway
from app.communication.speech_to_text import TranscriptResult
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Singleton gateway (reuses circuit-breaker state across voice sessions)
_shared_gateway: AIGateway | None = None


def _get_gateway() -> AIGateway:
    global _shared_gateway
    if _shared_gateway is None:
        _shared_gateway = AIGateway()
    return _shared_gateway


class CommunicationAIGateway:
    """AI Gateway adapter for the voice communication pipeline.

    Args:
        session_id: Logging context.
        gateway: Optional AIGateway injection (defaults to shared singleton).

    Usage::

        gw = CommunicationAIGateway(session_id="abc")
        request = gw.build_request(
            transcript=transcript_result,
            system_prompt=system_prompt,
            messages=history_messages,
        )
        async for chunk in gw.stream_with_interrupt(request, interrupt_event):
            handle(chunk)
    """

    def __init__(
        self,
        session_id: str,
        gateway: AIGateway | None = None,
    ) -> None:
        self._session_id = session_id
        self._gateway = gateway or _get_gateway()

    def build_request(
        self,
        transcript: TranscriptResult,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int = 500,
        temperature: float = 0.75,
    ) -> AIRequest:
        """Build an AIRequest from a transcription result and context.

        Args:
            transcript: STT output (text + confidence).
            system_prompt: Full assembled system prompt from ContextBuilder.
            messages: OpenAI-format message history.
            max_tokens: Response length cap.
            temperature: Sampling temperature.

        Returns:
            An AIRequest ready for the gateway.
        """
        return AIRequest(
            prompt=transcript.text,
            system_prompt=system_prompt,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )

    async def stream_with_interrupt(
        self,
        request: AIRequest,
        interrupt_event: asyncio.Event,
    ) -> AsyncIterator[StreamChunk]:
        """Stream AI response tokens, stopping when interrupt_event is set.

        Yields StreamChunk objects from the underlying AIGateway, but
        returns early if the interrupt event fires between chunks.

        Args:
            request: AIRequest to send.
            interrupt_event: asyncio.Event set by InterruptManager on barge-in.
        """
        provider_name = "unknown"
        try:
            async for chunk in self._gateway.stream(request):
                if interrupt_event.is_set():
                    logger.info(
                        "AI stream interrupted by barge-in event",
                        session_id=self._session_id,
                        provider=provider_name,
                    )
                    return

                provider_name = chunk.provider or provider_name
                yield chunk

        except Exception as exc:
            logger.error(
                "AI gateway stream error",
                session_id=self._session_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise
