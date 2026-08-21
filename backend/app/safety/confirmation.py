"""Human Confirmation Engine for Genie OS.

Handles the interactive approval lifecycle for sensitive actions:
- Builds structured confirmation dialog payloads for the UI
- Manages pending confirmation futures with timeout
- Integrates with the WebSocket protocol and OS permissions registry
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from uuid import uuid4

import structlog
from .risk_assessor import RiskLevel, RiskAssessment

log = structlog.get_logger("genie.safety.confirmation")


@dataclass
class ConfirmationPrompt:
    confirmation_id: str
    tool_name: str
    args: Dict[str, Any]
    risk: RiskAssessment
    description: str
    created_at: float = field(default_factory=time.time)
    timeout_seconds: float = 60.0


class ConfirmationManager:
    """Manages pending confirmation requests awaiting user approval."""

    def __init__(self):
        self._pending: Dict[str, asyncio.Future[bool]] = {}
        self._prompts: Dict[str, ConfirmationPrompt] = {}

    def create_request(
        self,
        tool_name: str,
        args: Dict[str, Any],
        risk: RiskAssessment,
        description: str,
        timeout_seconds: float = 60.0,
    ) -> ConfirmationPrompt:
        """Create a new confirmation request and return the prompt payload."""
        cid = f"conf_{uuid4().hex[:12]}"
        prompt = ConfirmationPrompt(
            confirmation_id=cid,
            tool_name=tool_name,
            args=args,
            risk=risk,
            description=description,
            timeout_seconds=timeout_seconds,
        )
        self._prompts[cid] = prompt
        loop = asyncio.get_event_loop()
        self._pending[cid] = loop.create_future()
        return prompt

    async def wait_for_decision(self, confirmation_id: str) -> bool:
        """Wait for the user's response (or timeout)."""
        future = self._pending.get(confirmation_id)
        prompt = self._prompts.get(confirmation_id)
        if not future or not prompt:
            return False

        try:
            approved = await asyncio.wait_for(future, timeout=prompt.timeout_seconds)
            log.info("confirmation_decided", confirmation_id=confirmation_id, approved=approved)
            return approved
        except asyncio.TimeoutError:
            log.warning("confirmation_timed_out", confirmation_id=confirmation_id)
            return False
        finally:
            self._pending.pop(confirmation_id, None)
            self._prompts.pop(confirmation_id, None)

    def resolve(self, confirmation_id: str, approved: bool) -> bool:
        """Resolve a pending confirmation future with the user's decision."""
        future = self._pending.get(confirmation_id)
        if future and not future.done():
            future.set_result(approved)
            return True
        return False


confirmation_manager = ConfirmationManager()
