"""Model Router for Genie AI OS.

Intelligently routes requests to the optimal model based on:
1. Role requirement (FAST for chat, REASONING for planning, CODING for software, VISION for visual analysis)
2. Local-first capability matching (local GGUF if sufficient, otherwise cloud)
3. Provider health & rate limits with automatic fallback pools
4. Streaming and structured JSON generation support
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import structlog

from ..config import Settings, get_settings
from ..llm_client import (
    ProviderConfig,
    get_or_create_client,
    get_provider_config,
    stream_chat,
)
from ..services.local_llm import local_llm
from .schemas import ModelRole

log = structlog.get_logger("genie.runtime.model_router")


class ModelRouter:
    """Intelligent multi-model router coordinating local & cloud providers."""

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()

    async def generate(
        self,
        messages: List[Dict[str, str]],
        role: ModelRole = ModelRole.FAST,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        response_format: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Generate a complete text/JSON response by streaming and accumulating."""
        full_text = ""
        async for chunk in self.stream(
            messages=messages,
            role=role,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format,
            tools=tools,
        ):
            if isinstance(chunk, dict) and chunk.get("type") == "text_delta":
                full_text += chunk.get("delta", "")
            elif isinstance(chunk, str):
                full_text += chunk
        return full_text.strip()

    async def stream(
        self,
        messages: List[Dict[str, str]],
        role: ModelRole = ModelRole.FAST,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        response_format: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream response chunks from the optimal model."""
        # 1. Check local model eligibility for FAST role
        if role == ModelRole.FAST and local_llm.is_available(self._settings):
            log.debug("model_router_using_local_llm")
            # Local LLM streaming
            async for delta in local_llm.generate(
                prompt=messages[-1].get("content", ""),
                max_tokens=max_tokens or 512,
                temperature=temperature or 0.4,
            ):
                yield {"type": "text_delta", "delta": delta}
            return

        # 2. Cloud provider routing
        # Apply role-based temperature and token defaults
        effective_temp = temperature
        if effective_temp is None:
            if role == ModelRole.REASONING or role == ModelRole.CODING:
                effective_temp = 0.2
            elif role == ModelRole.FAST:
                effective_temp = 0.4
            else:
                effective_temp = 0.5

        effective_max_tokens = max_tokens or (4096 if role in (ModelRole.REASONING, ModelRole.CODING) else 2048)

        # Use stream_chat from llm_client with multi-model fallback built-in
        async for event in stream_chat(
            messages=messages,
            tools=tools,
            settings=self._settings,
        ):
            yield event


# Global singleton
model_router = ModelRouter()
