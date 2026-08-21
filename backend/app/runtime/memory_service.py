"""Unified Memory Service for Genie AI OS.

Implements multi-tiered cognitive memory:
1. Short-term memory: Current turn dialogue buffer
2. Working memory: Active task/mission execution state
3. Long-term memory: Enduring user knowledge and historical facts
4. Semantic memory: Vector-indexed concepts & knowledge items
5. Episodic memory: Past task milestones and execution outcomes
6. Project memory: Per-project architecture notes, tasks, bugs
7. Preference memory: User habits, styles, constraints
8. Environment memory: Device, workspace, and connected services context

Backed by MemoryDatabase v2 with SQLite + embeddings.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Dict, List, Optional

import structlog

from ..core.memory.memory_db_v2 import Memory, MemoryDatabase, Project, UserPreference

log = structlog.get_logger("genie.runtime.memory")


class MemoryType(StrEnum):
    SHORT_TERM = "short_term"
    WORKING = "working"
    LONG_TERM = "long_term"
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    PROJECT = "project"
    PREFERENCE = "preference"
    ENVIRONMENT = "environment"


@dataclass
class WorkingMemoryItem:
    task_id: str
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None


class MemoryService:
    """Unified cognitive memory service coordinating short, working, and long-term memory."""

    def __init__(self, db: Optional[MemoryDatabase] = None):
        self._db = db or MemoryDatabase()
        self._working_memory: Dict[str, Dict[str, WorkingMemoryItem]] = {}  # task_id -> key -> item
        self._short_term_buffer: Dict[str, List[Dict[str, Any]]] = {}      # session_id -> list of turns
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize backing stores."""
        if not self._initialized:
            await self._db.initialize()
            self._initialized = True
            log.info("memory_service_ready")

    # ── Working Memory (Active Task State) ─────────────────────────────────────

    def set_working_memory(self, task_id: str, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        """Set a value in the fast volatile working memory for an active task."""
        if task_id not in self._working_memory:
            self._working_memory[task_id] = {}
        expires_at = time.time() + ttl_seconds if ttl_seconds else None
        self._working_memory[task_id][key] = WorkingMemoryItem(
            task_id=task_id, key=key, value=value, expires_at=expires_at
        )

    def get_working_memory(self, task_id: str, key: str) -> Optional[Any]:
        """Retrieve a working memory item if not expired."""
        task_store = self._working_memory.get(task_id)
        if not task_store or key not in task_store:
            return None
        item = task_store[key]
        if item.expires_at and time.time() > item.expires_at:
            del task_store[key]
            return None
        return item.value

    def get_all_working_memory(self, task_id: str) -> Dict[str, Any]:
        """Get all active working memory entries for a task."""
        task_store = self._working_memory.get(task_id, {})
        now = time.time()
        result = {}
        for k, item in list(task_store.items()):
            if item.expires_at and now > item.expires_at:
                del task_store[k]
            else:
                result[k] = item.value
        return result

    def clear_working_memory(self, task_id: str) -> None:
        """Clear working memory when task finishes."""
        self._working_memory.pop(task_id, None)

    # ── Short-term Dialogue Memory ─────────────────────────────────────────────

    def append_short_term(self, session_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a message turn to the short-term dialogue buffer."""
        if session_id not in self._short_term_buffer:
            self._short_term_buffer[session_id] = []
        self._short_term_buffer[session_id].append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {},
        })
        # Keep buffer bounded (last 20 turns)
        if len(self._short_term_buffer[session_id]) > 20:
            self._short_term_buffer[session_id] = self._short_term_buffer[session_id][-20:]

    def get_short_term(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent dialogue history for a session."""
        return self._short_term_buffer.get(session_id, [])[-limit:]

    # ── Long-term & Semantic Memory (Persistent) ───────────────────────────────

    async def remember(
        self,
        content: str,
        category: MemoryType = MemoryType.LONG_TERM,
        importance: float = 0.6,
        tags: Optional[List[str]] = None,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Optional[Memory]:
        """Store a new long-term/semantic memory with automatic vector indexing."""
        if not self._initialized:
            await self.initialize()
        return await self._db.remember(
            content=content,
            category=category.value,
            importance=importance,
            tags=tags or [],
            project_id=project_id,
            session_id=session_id,
        )

    async def recall(
        self,
        query: str,
        limit: int = 5,
        category: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> List[Memory]:
        """Semantic search across long-term memories."""
        if not self._initialized:
            await self.initialize()
        return await self._db.recall(
            query=query,
            limit=limit,
            category=category,
            project_id=project_id,
        )

    async def get_recent_memories(self, limit: int = 25) -> List[Memory]:
        """Retrieve latest memories across categories."""
        if not self._initialized:
            await self.initialize()
        return await self._db.get_recent(limit=limit)

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a persistent memory record."""
        if not self._initialized:
            await self.initialize()
        return await self._db.delete(memory_id)

    # ── Preferences ────────────────────────────────────────────────────────────

    async def set_preference(self, key: str, value: Any, category: str = "general") -> UserPreference:
        """Store user preference."""
        if not self._initialized:
            await self.initialize()
        return await self._db.set_preference(key=key, value=value, category=category)

    async def get_preference(self, key: str) -> Optional[Any]:
        """Get single preference value."""
        if not self._initialized:
            await self.initialize()
        pref = await self._db.get_preference(key)
        return pref.value if pref else None

    async def get_all_preferences(self) -> Dict[str, Any]:
        """Retrieve map of all preferences."""
        if not self._initialized:
            await self.initialize()
        prefs = await self._db.get_all_preferences()
        return {p.key: p.value for p in prefs}

    # ── Projects ───────────────────────────────────────────────────────────────

    async def get_projects(self) -> List[Project]:
        """Get all registered projects."""
        if not self._initialized:
            await self.initialize()
        return await self._db.get_all_projects()

    async def get_project(self, project_id: str) -> Optional[Project]:
        """Get single project by ID."""
        if not self._initialized:
            await self.initialize()
        return await self._db.get_project(project_id)

    async def save_project(self, project: Project) -> None:
        """Save project state."""
        if not self._initialized:
            await self.initialize()
        await self._db.save_project(project)


# Global singleton
memory_service = MemoryService()
