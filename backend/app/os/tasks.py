"""Task lifecycle primitives for Genie OS."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from threading import RLock
from typing import Any
from uuid import uuid4

from .events import utc_now


class TaskStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(slots=True)
class TaskRecord:
    """Durable-compatible task record for user-visible and background work."""

    title: str
    source: str
    session_id: str | None = None
    parent_id: str | None = None
    input_text: str = ""
    task_id: str = field(default_factory=lambda: f"task_{uuid4().hex}")
    trace_id: str = field(default_factory=lambda: f"trace_{uuid4().hex}")
    status: TaskStatus = TaskStatus.CREATED
    metadata: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "session_id": self.session_id,
            "title": self.title,
            "source": self.source,
            "input_text": self.input_text,
            "status": self.status.value,
            "metadata": self.metadata,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }


class TaskRegistry:
    """Thread-safe in-memory task registry."""

    def __init__(self):
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = RLock()

    def create(
        self,
        *,
        title: str,
        source: str,
        session_id: str | None = None,
        input_text: str = "",
        parent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskRecord:
        task = TaskRecord(
            title=title,
            source=source,
            session_id=session_id,
            input_text=input_text,
            parent_id=parent_id,
            metadata=metadata or {},
        )
        with self._lock:
            self._tasks[task.task_id] = task
        return task

    def transition(self, task_id: str, status: TaskStatus) -> TaskRecord | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            task.status = status
            task.updated_at = utc_now()
            if status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED}:
                task.completed_at = task.updated_at
            return task

    def complete(self, task_id: str, result: dict[str, Any] | None = None) -> TaskRecord | None:
        with self._lock:
            task = self.transition(task_id, TaskStatus.COMPLETED)
            if task is not None:
                task.result = result or {}
            return task

    def fail(self, task_id: str, error: str) -> TaskRecord | None:
        with self._lock:
            task = self.transition(task_id, TaskStatus.FAILED)
            if task is not None:
                task.error = error
            return task

    def cancel(self, task_id: str, reason: str = "cancelled") -> TaskRecord | None:
        with self._lock:
            task = self.transition(task_id, TaskStatus.CANCELLED)
            if task is not None:
                task.error = reason
            return task

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            return self._tasks.get(task_id)

    def recent(self, limit: int = 25) -> list[TaskRecord]:
        with self._lock:
            return list(self._tasks.values())[-limit:]
