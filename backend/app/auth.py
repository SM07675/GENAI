"""PIN-based authentication and per-session bearer tokens.

Flow:
  1. Client opens the WebSocket and sends `{"type":"hello","pin":"1234"}`.
  2. `verify_pin` checks against the configured/generated PIN.
  3. On success `issue_token` returns an opaque token bound to a session id.
  4. The token is stored in `SESSIONS` so the same WS (or a reconnect) can
     resume the conversation. Tokens expire after `session_token_ttl_seconds`.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Optional

from .config import Settings, get_settings


@dataclass
class Session:
    session_id: str
    token: str
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    # Conversation history (OpenAI-style role/content list). Kept in memory;
    # GLM 5.2's 1M-token window lets us keep a long-running transcript.
    history: list[dict] = field(default_factory=list)

    def touch(self) -> None:
        self.last_seen = time.time()

    def expired(self, ttl: int) -> bool:
        return (time.time() - self.last_seen) > ttl


# In-memory session store keyed by token. Sufficient for a single-user local
# assistant; swap for Redis if you scale beyond one machine.
SESSIONS: dict[str, Session] = {}


def verify_pin(pin: str, settings: Settings | None = None) -> bool:
    """Constant-time-ish comparison of a supplied PIN against the configured one."""
    settings = settings or get_settings()
    expected = settings.effective_pin
    return secrets.compare_digest(pin or "", expected)


def issue_token(session_id: Optional[str] = None) -> Session:
    """Create (or refresh) a session and return it."""
    sid = session_id or secrets.token_hex(8)
    token = secrets.token_urlsafe(32)
    session = Session(session_id=sid, token=token)
    SESSIONS[token] = session
    return session


def get_session(token: str, settings: Settings | None = None) -> Optional[Session]:
    """Look up a session, expiring it if stale."""
    settings = settings or get_settings()
    session = SESSIONS.get(token)
    if not session:
        return None
    if session.expired(settings.session_token_ttl_seconds):
        SESSIONS.pop(token, None)
        return None
    session.touch()
    return session


def session_by_id(session_id: str) -> Optional[Session]:
    """Find an existing session by its id (for REST resume)."""
    for s in SESSIONS.values():
        if s.session_id == session_id:
            return s
    return None


def cleanup_expired_sessions(settings: Settings | None = None) -> int:
    """Remove all expired sessions from the store.
    
    Returns the number of sessions cleaned up.
    Called periodically from the lifespan cleanup task (H8 fix).
    """
    settings = settings or get_settings()
    ttl = settings.session_token_ttl_seconds
    expired_tokens = [
        token for token, session in SESSIONS.items()
        if session.expired(ttl)
    ]
    for token in expired_tokens:
        del SESSIONS[token]
    return len(expired_tokens)
