"""High-signal context injection for Genie turns.

This module turns Genie's local state into a compact prompt packet. It uses the
existing SQLite companion database instead of adding another memory backend, so
the assistant can retrieve useful context even when cloud/vector services are
unavailable.
"""
from __future__ import annotations

import re
from typing import Any, Protocol

from .engine import context_engine

MAX_PACKET_CHARS = 6000
MAX_FIELD_CHARS = 420
STOP_WORDS = {
    "about", "after", "again", "also", "because", "before", "could", "from",
    "have", "into", "just", "make", "need", "please", "should", "that",
    "their", "there", "this", "want", "what", "when", "where", "which",
    "with", "would", "your",
}


class CompanionStore(Protocol):
    def start_session(self, session_id: str) -> None: ...

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        **kwargs: Any,
    ) -> int: ...

    def search_memory(self, query: str, limit: int = 8) -> list[dict]: ...

    def upsert_memory(
        self,
        type_: str,
        key: str,
        value: str,
        confidence: float = 1.0,
        source: str = "auto",
    ) -> int: ...

    def get_preferences(self) -> dict[str, str]: ...
    def set_preference(self, key: str, value: str, category: str = "general") -> None: ...
    def set_profile(self, field: str, value: str) -> None: ...
    def get_projects(self) -> list[dict]: ...
    def get_tasks(self, status: str = "pending") -> list[dict]: ...

    def log_agent(
        self,
        session_id: str,
        agent: str,
        action: str,
        user_query: str = "",
        result_summary: str = "",
    ) -> None: ...


def build_peak_context_packet(
    user_text: str,
    session_id: str,
    *,
    db: CompanionStore | None = None,
) -> str:
    """Build a bounded prompt packet with the most useful current context."""
    db = db or _default_db()
    sections: list[str] = []

    desktop_context = context_engine.get_current_context_summary()
    if desktop_context and "No active context available" not in desktop_context:
        sections.append(desktop_context.strip())

    memories = _search_relevant_memories(user_text, db=db)
    if memories:
        lines = ["Relevant long-term memory:"]
        for memory in memories[:6]:
            label = memory.get("type", "memory")
            key = _compact(memory.get("key", ""))
            value = _compact(memory.get("value", ""))
            if key and value:
                lines.append(f"- [{label}] {key}: {value}")
        sections.append("\n".join(lines))

    preferences = _top_items(db.get_preferences(), limit=6)
    if preferences:
        lines = ["User preferences:"]
        lines.extend(f"- {key}: {_compact(value)}" for key, value in preferences)
        sections.append("\n".join(lines))

    projects = db.get_projects()[:5]
    if projects:
        lines = ["Known projects:"]
        for project in projects:
            name = _compact(project.get("name", ""))
            description = _compact(project.get("description", ""))
            if name:
                lines.append(f"- {name}" + (f": {description}" if description else ""))
        sections.append("\n".join(lines))

    tasks = db.get_tasks("pending")[:5]
    if tasks:
        lines = ["Pending tasks/reminders:"]
        for task in tasks:
            title = _compact(task.get("title", ""))
            deadline = _compact(task.get("deadline", ""))
            if title:
                lines.append(f"- {title}" + (f" ({deadline})" if deadline else ""))
        sections.append("\n".join(lines))

    if not sections:
        return ""

    packet = (
        "## GENIE OS CONTEXT PACKET\n"
        "Use this silently to answer with better continuity. Do not quote or "
        "mention this packet unless the user asks about memory/context.\n\n"
        + "\n\n".join(sections)
    )
    return packet[:MAX_PACKET_CHARS]


def record_turn_memory(
    session_id: str,
    user_text: str,
    assistant_text: str,
    *,
    db: CompanionStore | None = None,
) -> None:
    """Persist the turn and promote explicit user memory signals."""
    db = db or _default_db()
    clean_user = (user_text or "").strip()
    clean_assistant = (assistant_text or "").strip()
    if not clean_user and not clean_assistant:
        return

    db.start_session(session_id)
    if clean_user:
        db.add_message(session_id, "user", clean_user)
    if clean_assistant:
        db.add_message(session_id, "assistant", clean_assistant)

    learned = learn_explicit_memories(clean_user, db=db)
    if learned:
        db.log_agent(
            session_id,
            "memory_agent",
            "promoted_explicit_memory",
            user_query=clean_user,
            result_summary=", ".join(learned),
        )


def learn_explicit_memories(user_text: str, *, db: CompanionStore | None = None) -> list[str]:
    """Store only clear, user-intended memory statements."""
    db = db or _default_db()
    text = _normalise_sentence(user_text)
    if not text:
        return []

    learned: list[str] = []

    name = _match_first(text, [
        r"\bmy name is\s+(.+)$",
        r"\bcall me\s+(.+)$",
    ])
    if name:
        clean_name = _compact(name, 80)
        db.set_profile("name", clean_name)
        db.upsert_memory("profile", "name", clean_name, confidence=1.0, source="auto")
        learned.append("profile:name")

    preference = _match_first(text, [
        r"\bi prefer\s+(.+)$",
        r"\bi like\s+(.+)$",
        r"\bi usually\s+(.+)$",
    ])
    if preference:
        clean_pref = _compact(preference, 220)
        key = _memory_key(clean_pref)
        db.set_preference(key, clean_pref, category="learned")
        db.upsert_memory("preference", key, clean_pref, confidence=0.85, source="auto")
        learned.append(f"preference:{key}")

    remembered = _match_first(text, [
        r"\bremember that\s+(.+)$",
        r"\bremember\s+(.+)$",
    ])
    remembered_is_preference = bool(
        preference
        and remembered
        and remembered.lower().startswith(("i prefer", "i like", "i usually"))
    )
    if remembered and not remembered_is_preference:
        clean_fact = _compact(remembered, 300)
        key = _memory_key(clean_fact)
        db.upsert_memory("fact", key, clean_fact, confidence=0.9, source="auto")
        learned.append(f"fact:{key}")

    return learned


def _default_db() -> CompanionStore:
    from ...tools.memory_db import companion_db

    return companion_db


def _search_relevant_memories(user_text: str, *, db: CompanionStore) -> list[dict]:
    seen: dict[Any, dict] = {}

    for memory in db.search_memory(user_text, limit=6):
        seen[memory.get("id", id(memory))] = memory

    for token in _query_terms(user_text)[:8]:
        for memory in db.search_memory(token, limit=3):
            seen.setdefault(memory.get("id", id(memory)), memory)

    terms = set(_query_terms(user_text))
    ranked = list(seen.values())
    ranked.sort(key=lambda item: _memory_score(item, terms), reverse=True)
    return ranked


def _memory_score(memory: dict, terms: set[str]) -> float:
    haystack = f"{memory.get('key', '')} {memory.get('value', '')}".lower()
    overlap = sum(1 for term in terms if term in haystack)
    confidence = float(memory.get("confidence") or 0.0)
    return overlap + confidence


def _query_terms(text: str) -> list[str]:
    tokens = re.findall(r"[\w\u0900-\u097F]{3,}", text.lower())
    return [token for token in tokens if token not in STOP_WORDS]


def _top_items(items: dict[str, str], limit: int) -> list[tuple[str, str]]:
    return list(items.items())[:limit]


def _match_first(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" .!?")
    return None


def _normalise_sentence(text: str) -> str:
    text = re.sub(r"^\[Language:[^\]]+\]\s*", "", text or "", flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _memory_key(value: str) -> str:
    terms = _query_terms(value)
    if not terms:
        return "memory"
    return "_".join(terms[:6])[:80]


def _compact(value: Any, limit: int = MAX_FIELD_CHARS) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
