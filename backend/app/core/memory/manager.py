"""
MemoryManager v2 — Unified memory interface for Genie.

This replaces the stub MemoryManager in manager.py.

Integrates:
  - MemoryDatabase v2 (SQLite + Qdrant + sentence-transformers)
  - Conversation memory wiring (called by orchestrator)
  - Importance scoring (so not everything is stored)
  - Retrieval for context injection (called before each LLM call)

Usage in orchestrator:
    from app.core.memory import get_memory_manager

    # Before LLM call:
    ctx = await get_memory_manager().retrieve_for_context(query, project_id)

    # After conversation turn:
    await get_memory_manager().record_turn(user_text, assistant_text, session_id)
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional

import structlog

from .memory_db_v2 import MemoryDatabase, Memory, Project, get_memory_db
from .embeddings import get_embedding_service
from ..event_bus import event_bus

log = structlog.get_logger("genie.memory.manager")


# ── Importance scoring heuristics ────────────────────────────────────────────

# Keywords that indicate important content worth remembering
_HIGH_IMPORTANCE_PATTERNS = [
    r'\bremember\b', r'\bdon\'t forget\b', r'\bimportant\b', r'\bmy name is\b',
    r'\bi prefer\b', r'\bi like\b', r'\bi hate\b', r'\bi always\b', r'\bi never\b',
    r'\bmy project\b', r'\bmy goal\b', r'\bdeadline\b', r'\bi need\b',
    r'\bpassword\b', r'\bapi key\b', r'\bmy \w+ is\b',
]

_TEMP_PATTERNS = [
    r'\bright now\b', r'\bcurrently\b', r'\btoday\b', r'\bjust\b', r'\bmoment\b',
]


def _score_importance(text: str, role: str = "user") -> float:
    """Heuristic importance scoring for a piece of text (0.0–1.0).

    Rules:
    - User messages generally more important than assistant
    - High-importance keyword patterns boost score
    - Very short utterances are low importance
    - Questions have moderate importance
    """
    base = 0.4 if role == "user" else 0.25
    text_lower = text.lower()

    # Boost for explicit importance signals
    for pattern in _HIGH_IMPORTANCE_PATTERNS:
        if re.search(pattern, text_lower):
            base = min(1.0, base + 0.25)
            break

    # Reduce for very short or filler texts
    if len(text) < 30:
        base *= 0.6
    elif len(text) > 300:
        base = min(1.0, base + 0.1)

    # Questions: moderate importance
    if '?' in text:
        base = min(1.0, base + 0.05)

    return round(base, 2)


def _extract_category(text: str) -> str:
    """Heuristic category detection."""
    t = text.lower()
    if any(k in t for k in ['project', 'code', 'file', 'bug', 'error', 'deploy', 'git', 'build']):
        return "project"
    if any(k in t for k in ['prefer', 'like', 'hate', 'always', 'never', 'my style', 'my workflow']):
        return "personal_preference"
    if any(k in t for k in ['right now', 'currently', 'today', 'just now']):
        return "temporary"
    return "conversation"


# ═══════════════════════════════════════════════════════════════════════════════
# MemoryManager
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryManager:
    """High-level memory interface for the Genie companion system."""

    def __init__(self):
        self._db = get_memory_db()
        self._initialized = False
        event_bus.subscribe("memory.add", self._handle_add_memory_event)

    async def initialize(self) -> None:
        """Initialize the database and embedding service."""
        if self._initialized:
            return
        await self._db.initialize()
        self._initialized = True

    # ── Conversation pipeline integration ─────────────────────────────────

    async def record_turn(
        self,
        user_text: str,
        assistant_text: str,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> None:
        """Called after each conversation turn. Decides what to store."""
        if not self._initialized:
            await self.initialize()

        tasks = []

        # Score user message
        user_importance = _score_importance(user_text, role="user")
        if user_importance >= 0.3:
            user_cat = _extract_category(user_text)
            mem = Memory.temporary(user_text, importance=user_importance) \
                if user_cat == "temporary" else \
                Memory(
                    content=user_text,
                    category=user_cat,
                    importance=user_importance,
                    session_id=session_id,
                    project_id=project_id,
                )
            tasks.append(self._db.add_memory(mem))

        # Score assistant response (lower baseline — it's model output, not user-provided)
        asst_importance = _score_importance(assistant_text, role="assistant")
        if asst_importance >= 0.35:
            asst_mem = Memory(
                content=f"[Genie said] {assistant_text[:500]}",
                category="conversation",
                importance=asst_importance * 0.8,
                session_id=session_id,
                project_id=project_id,
            )
            tasks.append(self._db.add_memory(asst_mem))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def retrieve_for_context(
        self,
        query: str,
        project_id: Optional[str] = None,
        limit: int = 5,
    ) -> str:
        """Retrieve relevant memories and format as context string for LLM injection."""
        if not self._initialized:
            await self.initialize()

        if not query.strip():
            return ""

        try:
            memories = await self._db.search(
                query=query,
                project_id=project_id,
                limit=limit,
                min_importance=0.3,
            )
            preferences = await self._db.get_all_preferences()

            parts: List[str] = []

            if preferences:
                pref_lines = [f"  - {k}: {v}" for k, v in list(preferences.items())[:8]]
                parts.append("User Preferences:\n" + "\n".join(pref_lines))

            if memories:
                mem_lines = [f"  - {m.content[:200]}" for m in memories if not m.is_expired]
                if mem_lines:
                    parts.append("Relevant Memory:\n" + "\n".join(mem_lines))

            return "\n\n".join(parts)

        except Exception as exc:
            log.warning("memory_retrieve_failed", error=str(exc))
            return ""

    async def remember(
        self,
        content: str,
        category: str = "conversation",
        importance: float = 0.7,
        tags: Optional[List[str]] = None,
        project_id: Optional[str] = None,
    ) -> Optional[str]:
        """Explicitly add a memory (called by the 'remember' tool)."""
        if not self._initialized:
            await self.initialize()

        mem = Memory(
            content=content,
            category=category,
            importance=importance,
            tags=tags or [],
            project_id=project_id,
        )
        return await self._db.add_memory(mem)

    async def search(self, query: str, limit: int = 5) -> List[Memory]:
        """Search memories (used by tools)."""
        if not self._initialized:
            await self.initialize()
        return await self._db.search(query=query, limit=limit)

    async def set_preference(self, key: str, value: Any, category: str = "general") -> None:
        """Store a user preference."""
        if not self._initialized:
            await self.initialize()
        await self._db.set_preference(key, value, category)

    async def get_preference(self, key: str, default: Any = None) -> Any:
        """Retrieve a user preference."""
        if not self._initialized:
            await self.initialize()
        return await self._db.get_preference(key, default)

    async def save_project(self, project: Project) -> None:
        """Save project information."""
        if not self._initialized:
            await self.initialize()
        await self._db.save_project(project)

    async def get_projects(self) -> List[Project]:
        """Get all known projects."""
        if not self._initialized:
            await self.initialize()
        return await self._db.get_projects(status="active")

    async def get_recent_memories(self, limit: int = 8) -> List[Memory]:
        """Get recently accessed memories for dashboard display."""
        if not self._initialized:
            await self.initialize()
        return await self._db.get_recent(limit=limit)

    async def clear_session_memory(self, session_id: str) -> None:
        """Clear temporary memories from a completed session."""
        # Expiry is handled automatically by delete_expired()
        pass

    async def run_maintenance(self) -> None:
        """Periodic maintenance: delete expired memories."""
        if not self._initialized:
            await self.initialize()
        await self._db.delete_expired()

    # ── Event bus handler ─────────────────────────────────────────────────

    async def _handle_add_memory_event(self, event: Dict[str, Any]) -> None:
        """Handle memory.add events from the event bus."""
        content = event.get("content")
        if not content:
            return
        await self.remember(
            content=content,
            category=event.get("category", "conversation"),
            importance=event.get("importance", 0.6),
            tags=event.get("tags", []),
            project_id=event.get("project_id"),
        )


# ── Global singleton ─────────────────────────────────────────────────────────

_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get or create the global memory manager."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager


# Backward compat alias
memory_manager = get_memory_manager()
