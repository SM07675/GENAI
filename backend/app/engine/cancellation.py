"""Cooperative cancellation tokens for the conversation engine.

Instead of ``asyncio.Task.cancel()`` — which throws ``CancelledError``
mid-stream and can corrupt shared state — workers check a shared
``CancellationToken`` at safe points and exit cleanly.

Usage::

    token = CancellationToken()

    # In a worker:
    async for chunk in stream:
        if token.is_cancelled:
            break
        process(chunk)

    # To cancel from outside:
    token.cancel(reason="user_interrupted")
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CancellationToken:
    """A cooperative cancellation signal for async pipelines.

    Thread-safe: the underlying ``asyncio.Event`` is thread-safe for
    ``set()`` but ``wait()`` must be called from the event loop.
    """

    _event: asyncio.Event = field(default_factory=asyncio.Event)
    _reason: Optional[str] = field(default=None, init=False)
    _cancelled_at: float = field(default=0.0, init=False)

    @property
    def is_cancelled(self) -> bool:
        """Non-blocking check — safe to call from any thread."""
        return self._event.is_set()

    @property
    def reason(self) -> Optional[str]:
        return self._reason

    @property
    def cancelled_at(self) -> float:
        """Unix timestamp of cancellation, or 0.0 if not cancelled."""
        return self._cancelled_at

    def cancel(self, reason: str = "cancelled") -> None:
        """Signal cancellation. Idempotent — calling twice is safe."""
        if not self._event.is_set():
            self._reason = reason
            self._cancelled_at = time.time()
            self._event.set()

    async def wait(self, timeout: Optional[float] = None) -> bool:
        """Await cancellation. Returns True if cancelled, False on timeout."""
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def raise_if_cancelled(self) -> None:
        """Raise ``CancelledError`` if the token has been cancelled.

        Use at safe checkpoints where you *want* CancelledError propagation
        (e.g., at the top of a loop body).
        """
        if self._event.is_set():
            raise asyncio.CancelledError(self._reason or "cancelled")

    def reset(self) -> None:
        """Reset for reuse — only call when no workers hold a reference."""
        self._event.clear()
        self._reason = None
        self._cancelled_at = 0.0


class CancellationScope:
    """Manages a pool of cancellation tokens for a single interaction.

    When the scope is cancelled, all tokens created within it are cancelled.
    """

    def __init__(self, interaction_id: str = ""):
        self.interaction_id = interaction_id
        self._tokens: list[CancellationToken] = []
        self._cancelled = False

    def create_token(self) -> CancellationToken:
        """Create a new token scoped to this interaction."""
        token = CancellationToken()
        if self._cancelled:
            token.cancel(reason=f"scope_already_cancelled:{self.interaction_id}")
        self._tokens.append(token)
        return token

    def cancel_all(self, reason: str = "scope_cancelled") -> int:
        """Cancel all tokens in this scope. Returns count cancelled."""
        self._cancelled = True
        count = 0
        for token in self._tokens:
            if not token.is_cancelled:
                token.cancel(reason=reason)
                count += 1
        return count

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def clear(self) -> None:
        """Drop all token references for GC."""
        self._tokens.clear()
        self._cancelled = False
