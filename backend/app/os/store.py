"""SQLite persistence for Genie OS kernel records."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any

from .events import EventEnvelope
from .tasks import TaskRecord

DEFAULT_OS_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "genie_os.db"


_SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS os_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,
    source TEXT NOT NULL,
    task_id TEXT,
    trace_id TEXT,
    privacy TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_os_events_task ON os_events(task_id);
CREATE INDEX IF NOT EXISTS idx_os_events_type ON os_events(type);

CREATE TABLE IF NOT EXISTS os_tasks (
    task_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    parent_id TEXT,
    session_id TEXT,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    input_text TEXT,
    status TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_os_tasks_status ON os_tasks(status);
"""


class SQLiteOSStore:
    """Small durable store for local Genie OS records."""

    def __init__(self, db_path: Path = DEFAULT_OS_DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = RLock()
        with self._lock:
            self._conn.executescript(_SCHEMA)

    def append_event(self, event: EventEnvelope) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO os_events "
                "(event_id, type, source, task_id, trace_id, privacy, payload_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.type,
                    event.source,
                    event.task_id,
                    event.trace_id,
                    event.privacy,
                    _json(event.payload),
                    event.created_at,
                ),
            )

    def upsert_task(self, task: TaskRecord) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO os_tasks "
                "(task_id, trace_id, parent_id, session_id, title, source, input_text, status, "
                "metadata_json, result_json, error, created_at, updated_at, completed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(task_id) DO UPDATE SET "
                "status=excluded.status, metadata_json=excluded.metadata_json, "
                "result_json=excluded.result_json, error=excluded.error, "
                "updated_at=excluded.updated_at, completed_at=excluded.completed_at",
                (
                    task.task_id,
                    task.trace_id,
                    task.parent_id,
                    task.session_id,
                    task.title,
                    task.source,
                    task.input_text,
                    task.status.value,
                    _json(task.metadata),
                    _json(task.result),
                    task.error,
                    task.created_at,
                    task.updated_at,
                    task.completed_at,
                ),
            )


def _json(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, default=str)
