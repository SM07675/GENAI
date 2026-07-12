"""
Companion Database  —  genie_memory.db
──────────────────────────────────────────────────────────────────────────────
Full SQLite schema for Genie AI's persistent memory system.
11 tables covering: user profile, conversations, long-term memory,
projects, tasks, preferences, facts, daily logs, agent history.

All operations are synchronous (called from thread executor in async code).
Zero cloud. Zero third-party. Local SQLite only.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "genie_memory.db"

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ── User Profile ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    field           TEXT    UNIQUE NOT NULL,
    value           TEXT    NOT NULL,
    updated_at      TEXT    DEFAULT (datetime('now'))
);

-- ── Conversations (one per session) ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT    UNIQUE NOT NULL,
    started_at      TEXT    DEFAULT (datetime('now')),
    ended_at        TEXT,
    summary         TEXT
);

-- ── Conversation Messages (every turn) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversation_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT    NOT NULL,
    role            TEXT    NOT NULL CHECK(role IN ('user','assistant')),
    content         TEXT    NOT NULL,
    agent_used      TEXT,
    topic           TEXT,
    sentiment       TEXT,
    created_at      TEXT    DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_msg_session ON conversation_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_msg_created ON conversation_messages(created_at);

-- ── Long-Term Memory (key facts) ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS long_term_memory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    type            TEXT    NOT NULL,   -- profile|preference|project|task|goal|learning|reminder|fact
    key             TEXT    NOT NULL,
    value           TEXT    NOT NULL,
    confidence      REAL    DEFAULT 1.0,
    source          TEXT    DEFAULT 'auto',  -- auto|manual
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ltm_type ON long_term_memory(type);
CREATE INDEX IF NOT EXISTS idx_ltm_key  ON long_term_memory(key);

-- Full-text search on long_term_memory
CREATE VIRTUAL TABLE IF NOT EXISTS ltm_fts USING fts5(
    key, value, type,
    content='long_term_memory',
    content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS ltm_ai AFTER INSERT ON long_term_memory BEGIN
    INSERT INTO ltm_fts(rowid, key, value, type) VALUES (new.id, new.key, new.value, new.type);
END;
CREATE TRIGGER IF NOT EXISTS ltm_ad AFTER DELETE ON long_term_memory BEGIN
    INSERT INTO ltm_fts(ltm_fts, rowid, key, value, type) VALUES ('delete', old.id, old.key, old.value, old.type);
END;
CREATE TRIGGER IF NOT EXISTS ltm_au AFTER UPDATE ON long_term_memory BEGIN
    INSERT INTO ltm_fts(ltm_fts, rowid, key, value, type) VALUES ('delete', old.id, old.key, old.value, old.type);
    INSERT INTO ltm_fts(rowid, key, value, type) VALUES (new.id, new.key, new.value, new.type);
END;

-- ── Projects ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    UNIQUE NOT NULL,
    description     TEXT,
    tech_stack      TEXT,   -- JSON array
    status          TEXT    DEFAULT 'active',
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now'))
);

-- ── Tasks ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT    NOT NULL,
    description     TEXT,
    status          TEXT    DEFAULT 'pending',  -- pending|done|cancelled
    deadline        TEXT,
    project_id      INTEGER REFERENCES projects(id),
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now'))
);

-- ── Preferences ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS preferences (
    key             TEXT    PRIMARY KEY,
    value           TEXT    NOT NULL,
    category        TEXT    DEFAULT 'general',
    updated_at      TEXT    DEFAULT (datetime('now'))
);

-- ── Important Facts ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS important_facts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fact            TEXT    NOT NULL UNIQUE,
    category        TEXT,
    created_at      TEXT    DEFAULT (datetime('now'))
);

-- ── Daily Logs ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS daily_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    log_date        TEXT    NOT NULL,
    mood            TEXT,
    summary         TEXT,
    created_at      TEXT    DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_log_date ON daily_logs(log_date);

-- ── Agent History ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT,
    agent           TEXT    NOT NULL,
    action          TEXT    NOT NULL,
    user_query      TEXT,
    result_summary  TEXT,
    created_at      TEXT    DEFAULT (datetime('now'))
);
"""


class CompanionDB:
    """Production SQLite companion memory database."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            isolation_level=None,   # autocommit
        )
        self._conn.row_factory = sqlite3.Row
        self._init()
        logger.info("[CompanionDB] Initialized at %s", self.db_path)

    def _init(self) -> None:
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _now(self) -> str:
        return datetime.utcnow().isoformat(timespec="seconds")

    def _row_to_dict(self, row: sqlite3.Row | None) -> dict | None:
        return dict(row) if row else None

    def _rows_to_list(self, rows) -> list[dict]:
        return [dict(r) for r in rows]

    # ── User Profile ─────────────────────────────────────────────────────────
    def set_profile(self, field: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO users (field, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(field) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (field.strip().lower(), value.strip(), self._now()),
        )

    def get_profile(self, field: str) -> str | None:
        cur = self._conn.execute("SELECT value FROM users WHERE field=?", (field.lower(),))
        row = cur.fetchone()
        return row["value"] if row else None

    def get_all_profile(self) -> dict[str, str]:
        cur = self._conn.execute("SELECT field, value FROM users")
        return {r["field"]: r["value"] for r in cur.fetchall()}

    # ── Conversations ─────────────────────────────────────────────────────────
    def start_session(self, session_id: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO conversations (session_id, started_at) VALUES (?, ?)",
            (session_id, self._now()),
        )

    def end_session(self, session_id: str, summary: str = "") -> None:
        self._conn.execute(
            "UPDATE conversations SET ended_at=?, summary=? WHERE session_id=?",
            (self._now(), summary, session_id),
        )

    def add_message(self, session_id: str, role: str, content: str, *,
                    agent_used: str = "", topic: str = "", sentiment: str = "") -> int:
        cur = self._conn.execute(
            "INSERT INTO conversation_messages "
            "(session_id, role, content, agent_used, topic, sentiment, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, role, content[:4000], agent_used, topic, sentiment, self._now()),
        )
        return cur.lastrowid

    def get_recent_messages(self, limit: int = 12) -> list[dict]:
        cur = self._conn.execute(
            "SELECT role, content, agent_used, topic, created_at "
            "FROM conversation_messages ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return list(reversed(self._rows_to_list(cur.fetchall())))

    def get_conversation_history(self, limit: int = 50) -> list[dict]:
        cur = self._conn.execute(
            "SELECT role, content, topic, agent_used, created_at "
            "FROM conversation_messages ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return list(reversed(self._rows_to_list(cur.fetchall())))

    def clear_conversations(self) -> None:
        self._conn.execute("DELETE FROM conversation_messages")
        self._conn.execute("DELETE FROM conversations")

    # ── Long-Term Memory ──────────────────────────────────────────────────────
    def upsert_memory(self, type_: str, key: str, value: str,
                       confidence: float = 1.0, source: str = "auto") -> int:
        """Insert or update a long-term memory entry. Returns the row ID."""
        cur = self._conn.execute(
            "SELECT id FROM long_term_memory WHERE type=? AND key=?",
            (type_, key.lower()),
        )
        row = cur.fetchone()
        if row:
            self._conn.execute(
                "UPDATE long_term_memory SET value=?, confidence=?, updated_at=? WHERE id=?",
                (value, confidence, self._now(), row["id"]),
            )
            return row["id"]
        else:
            cur = self._conn.execute(
                "INSERT INTO long_term_memory (type, key, value, confidence, source, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (type_, key.lower(), value, confidence, source, self._now(), self._now()),
            )
            return cur.lastrowid

    def get_memory(self, type_: str | None = None, limit: int = 100) -> list[dict]:
        if type_:
            cur = self._conn.execute(
                "SELECT * FROM long_term_memory WHERE type=? ORDER BY updated_at DESC LIMIT ?",
                (type_, limit),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM long_term_memory ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )
        return self._rows_to_list(cur.fetchall())

    def search_memory(self, query: str, limit: int = 8) -> list[dict]:
        """Full-text search across all long-term memory."""
        try:
            cur = self._conn.execute(
                "SELECT l.* FROM long_term_memory l "
                "JOIN ltm_fts f ON l.id = f.rowid "
                "WHERE ltm_fts MATCH ? ORDER BY rank LIMIT ?",
                (query, limit),
            )
            return self._rows_to_list(cur.fetchall())
        except Exception:
            # Fallback: LIKE search
            q = f"%{query}%"
            cur = self._conn.execute(
                "SELECT * FROM long_term_memory WHERE key LIKE ? OR value LIKE ? LIMIT ?",
                (q, q, limit),
            )
            return self._rows_to_list(cur.fetchall())

    def forget_memory(self, memory_id: int) -> bool:
        cur = self._conn.execute("DELETE FROM long_term_memory WHERE id=?", (memory_id,))
        return cur.rowcount > 0

    def forget_by_key(self, key: str) -> int:
        cur = self._conn.execute(
            "DELETE FROM long_term_memory WHERE key=?", (key.lower(),)
        )
        return cur.rowcount

    # ── Projects ──────────────────────────────────────────────────────────────
    def upsert_project(self, name: str, description: str = "",
                        tech_stack: list[str] | None = None) -> int:
        ts = json.dumps(tech_stack or [])
        cur = self._conn.execute(
            "INSERT INTO projects (name, description, tech_stack, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET description=COALESCE(excluded.description, description), "
            "tech_stack=COALESCE(excluded.tech_stack, tech_stack), updated_at=excluded.updated_at",
            (name.strip(), description, ts, self._now()),
        )
        return cur.lastrowid

    def get_projects(self) -> list[dict]:
        cur = self._conn.execute("SELECT * FROM projects ORDER BY updated_at DESC")
        return self._rows_to_list(cur.fetchall())

    # ── Tasks ─────────────────────────────────────────────────────────────────
    def add_task(self, title: str, description: str = "", deadline: str = "") -> int:
        cur = self._conn.execute(
            "INSERT INTO tasks (title, description, deadline, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (title.strip(), description, deadline, self._now(), self._now()),
        )
        return cur.lastrowid

    def get_tasks(self, status: str = "pending") -> list[dict]:
        cur = self._conn.execute(
            "SELECT * FROM tasks WHERE status=? ORDER BY created_at DESC",
            (status,),
        )
        return self._rows_to_list(cur.fetchall())

    # ── Preferences ───────────────────────────────────────────────────────────
    def set_preference(self, key: str, value: str, category: str = "general") -> None:
        self._conn.execute(
            "INSERT INTO preferences (key, value, category, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key.lower(), value, category, self._now()),
        )

    def get_preferences(self) -> dict[str, str]:
        cur = self._conn.execute("SELECT key, value FROM preferences")
        return {r["key"]: r["value"] for r in cur.fetchall()}

    # ── Agent History ─────────────────────────────────────────────────────────
    def log_agent(self, session_id: str, agent: str, action: str,
                   user_query: str = "", result_summary: str = "") -> None:
        self._conn.execute(
            "INSERT INTO agent_history (session_id, agent, action, user_query, result_summary, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, agent, action, user_query[:500], result_summary[:500], self._now()),
        )

    # ── Stats ─────────────────────────────────────────────────────────────────
    def get_stats(self) -> dict:
        tables = ["users", "conversations", "conversation_messages",
                  "long_term_memory", "projects", "tasks", "preferences"]
        stats: dict[str, int] = {}
        for t in tables:
            cur = self._conn.execute(f"SELECT COUNT(*) as c FROM {t}")
            stats[t] = cur.fetchone()["c"]
        size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0
        return {"tables": stats, "size_bytes": size_bytes,
                "size_kb": round(size_bytes / 1024, 1)}

    # ── Migration from memory.json ────────────────────────────────────────────
    def migrate_from_json(self, json_path: Path) -> int:
        """One-time migration from legacy memory.json → SQLite. Returns count imported."""
        if not json_path.exists():
            return 0
        import json as _json
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = _json.load(f)
        except Exception as e:
            logger.warning("[CompanionDB] Migration failed to read JSON: %s", e)
            return 0

        count = 0
        if data.get("user_name"):
            self.set_profile("name", data["user_name"])
            self.upsert_memory("profile", "name", data["user_name"], source="migrated")
            count += 1
        for p in data.get("projects", []):
            name = p if isinstance(p, str) else p.get("name", str(p))
            self.upsert_project(name)
            self.upsert_memory("project", name.lower(), name, source="migrated")
            count += 1
        for k, v in data.get("preferences", {}).items():
            self.set_preference(k, str(v))
            self.upsert_memory("preference", k, str(v), source="migrated")
            count += 1
        for t in data.get("tasks", []):
            title = t.get("task", str(t)) if isinstance(t, dict) else str(t)
            self.add_task(title)
            count += 1
        for c in data.get("conversations", [])[-50:]:
            role = c.get("role", "user")
            content = c.get("content", "")
            if content:
                self.add_message("migrated", role, content)
                count += 1

        logger.info("[CompanionDB] Migrated %d items from memory.json", count)
        return count


# ── Singleton ─────────────────────────────────────────────────────────────────
companion_db = CompanionDB()

# One-time migration from legacy memory.json
_LEGACY_JSON = Path(__file__).resolve().parents[2] / "data" / "memory.json"
_MIGRATION_FLAG = Path(__file__).resolve().parents[3] / "data" / ".migration_done"
if not _MIGRATION_FLAG.exists():
    try:
        n = companion_db.migrate_from_json(_LEGACY_JSON)
        _MIGRATION_FLAG.parent.mkdir(parents=True, exist_ok=True)
        _MIGRATION_FLAG.write_text(f"migrated {n} items")
        logger.info("[CompanionDB] Migration complete: %d items", n)
    except Exception as _me:
        logger.warning("[CompanionDB] Migration skipped: %s", _me)
