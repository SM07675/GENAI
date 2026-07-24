"""Unified context manager — replaces both conversation_manager.ConversationContext
AND engine.context_manager.ContextManager.

Design:
- Single source of truth for conversational context.
- Rolling turn history with bounded size.
- Entity tracking + reference resolution.
- Used by both the pipeline supervisor and the orchestrator.
- Per-session, managed by a global ContextStore.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

import structlog

log = structlog.get_logger("genie.engine.brain.context")


class TurnRecord:
    """A single conversational turn."""

    __slots__ = ("role", "text", "timestamp", "interrupted", "tool_calls")

    def __init__(
        self,
        role: str,
        text: str,
        interrupted: bool = False,
        tool_calls: list[dict] | None = None,
    ):
        self.role = role
        self.text = text
        self.timestamp = datetime.now()
        self.interrupted = interrupted
        self.tool_calls = tool_calls or []


class UnifiedContext:
    """Per-session context that survives across turns.

    This is the SINGLE context manager for the entire pipeline.
    It replaces both the legacy ConversationContext (conversation_manager.py)
    and the engine's ContextManager (context_manager.py).
    """

    MAX_TURNS = 20
    MAX_CONTEXT_CHARS = 6000

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._turns: list[TurnRecord] = []

        # Short-term entities (this session only)
        self.current_topic: Optional[str] = None
        self.last_entity: dict[str, Any] = {}
        self.last_action: Optional[str] = None
        self.last_assistant_text: Optional[str] = None
        self.pending_clarification: Optional[str] = None

        # Conversation metadata
        self.created_at = datetime.now()
        self.turn_count = 0

    # ── Turn Management ───────────────────────────────────────────────────

    def add_user_turn(self, text: str, interrupted: bool = False) -> None:
        """Record a user turn."""
        self.turn_count += 1
        self._extract_entities(text)
        self._turns.append(TurnRecord("user", text, interrupted=interrupted))
        self._trim_turns()

    def add_assistant_turn(
        self,
        text: str,
        tool_calls: list[dict] | None = None,
        interrupted: bool = False,
    ) -> None:
        """Record an assistant turn."""
        display = text
        if interrupted:
            display += " [interrupted]"
        self.last_assistant_text = text
        self._turns.append(
            TurnRecord("assistant", display, interrupted=interrupted, tool_calls=tool_calls)
        )
        self._track_tool_entities(tool_calls)
        self._trim_turns()

    def _trim_turns(self) -> None:
        """Keep only the last MAX_TURNS."""
        if len(self._turns) > self.MAX_TURNS:
            self._turns = self._turns[-self.MAX_TURNS:]

    # ── Entity Extraction ─────────────────────────────────────────────────

    def _extract_entities(self, text: str) -> None:
        """Simple entity extraction from user text."""
        for pattern in [
            r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'\bat\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        ]:
            m = re.search(pattern, text)
            if m:
                self.last_entity["location"] = m.group(1)
                break

    def _track_tool_entities(self, tool_calls: list[dict] | None) -> None:
        """Extract entities from tool calls."""
        if not tool_calls:
            return
        last = tool_calls[-1]
        self.last_action = last.get("name")
        args = last.get("arguments", {})
        if isinstance(args, str):
            return
        if "location" in args:
            self.last_entity["location"] = args["location"]
        if "query" in args:
            self.last_entity["query"] = args["query"]
        if "app" in args or "name" in args:
            self.last_entity["app"] = args.get("app") or args.get("name")

    # ── Also supports the legacy update_context API ───────────────────────

    def update_context(self, user_text: str, tool_calls: list[dict]) -> None:
        """Legacy API: update context from orchestrator.

        The orchestrator calls this after processing a turn.
        """
        self._extract_entities(user_text)
        if tool_calls:
            last_tool = tool_calls[-1]
            self.last_action = last_tool.get("name")
            args = last_tool.get("arguments", {})
            if isinstance(args, dict):
                if "location" in args:
                    self.last_entity["location"] = args["location"]
                if "query" in args:
                    self.last_entity["query"] = args["query"]
                if "app" in args or "name" in args:
                    self.last_entity["app"] = args.get("app") or args.get("name")

    # ── Reference Resolution ──────────────────────────────────────────────

    def resolve_references(self, text: str) -> str:
        """Resolve pronouns/references using context."""
        text_lower = text.lower()
        resolved = text

        # Location references
        if any(w in text_lower for w in ["there", "that place", "same place"]):
            if "location" in self.last_entity:
                loc = self.last_entity["location"]
                resolved = resolved.replace("there", f"in {loc}")
                resolved = resolved.replace("that place", f"in {loc}")

        # "another"/"more" with context
        if "another" in text_lower or "more" in text_lower:
            if self.last_action == "play_youtube" and "query" in self.last_entity:
                resolved = f"play more {self.last_entity['query']}"
            elif self.last_action == "search_web" and "query" in self.last_entity:
                resolved = f"search more about {self.last_entity['query']}"

        # App references
        if any(w in text_lower for w in ["it", "that app", "close it"]):
            if "app" in self.last_entity:
                resolved = resolved.replace(" it", f" {self.last_entity['app']}")
                resolved = resolved.replace("that app", self.last_entity["app"])

        if resolved != text:
            log.info("reference_resolved", original=text[:60], resolved=resolved[:60])
            return f"[Context: {resolved}] {text}"

        return text

    # ── Context Summary ───────────────────────────────────────────────────

    def get_context_summary(self) -> str:
        """Generate a context summary for the system prompt."""
        parts = []

        if self.current_topic:
            parts.append(f"Current topic: {self.current_topic}")

        if self.last_action:
            parts.append(f"Last action: {self.last_action}")

        if self.last_entity:
            entity_str = ", ".join(f"{k}: {v}" for k, v in self.last_entity.items())
            parts.append(f"Context entities: {entity_str}")

        if parts:
            return "## CONVERSATION CONTEXT\n" + "\n".join(parts) + "\n\n"
        return ""

    def get_last_assistant_text(self) -> Optional[str]:
        return self.last_assistant_text

    def should_summarize(self) -> bool:
        return self.turn_count > 20

    def clear(self) -> None:
        """Clear all context."""
        self._turns.clear()
        self.current_topic = None
        self.last_entity.clear()
        self.last_action = None
        self.last_assistant_text = None
        self.pending_clarification = None
        self.turn_count = 0


class ContextStore:
    """Manages UnifiedContext instances across sessions."""

    MAX_SESSIONS = 50

    def __init__(self):
        self._sessions: dict[str, UnifiedContext] = {}

    def get(self, session_id: str) -> UnifiedContext:
        if session_id not in self._sessions:
            if len(self._sessions) >= self.MAX_SESSIONS:
                self._evict_oldest()
            self._sessions[session_id] = UnifiedContext(session_id)
        return self._sessions[session_id]

    def clear(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].clear()

    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """Remove contexts older than max_age_hours."""
        from datetime import timedelta
        now = datetime.now()
        expired = [
            sid for sid, ctx in self._sessions.items()
            if (now - ctx.created_at).total_seconds() > max_age_hours * 3600
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)

    def _evict_oldest(self) -> None:
        if not self._sessions:
            return
        oldest = min(self._sessions, key=lambda s: self._sessions[s].created_at)
        del self._sessions[oldest]


# Global context store — single source of truth.
context_store = ContextStore()
