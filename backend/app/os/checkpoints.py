"""Checkpoint records for long-running Genie OS tasks."""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any
from uuid import uuid4

from .events import utc_now


@dataclass(slots=True)
class CheckpointRecord:
    """Recoverable task milestone.

    Checkpoints are small JSON-compatible state snapshots. They let agents stop,
    retry, or resume a task without relying on chat history as the source of
    truth.
    """

    task_id: str
    label: str
    state: dict[str, Any] = field(default_factory=dict)
    checkpoint_id: str = field(default_factory=lambda: f"chk_{uuid4().hex}")
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "task_id": self.task_id,
            "label": self.label,
            "state": self.state,
            "created_at": self.created_at,
        }


class CheckpointRegistry:
    """Thread-safe checkpoint store for the local process."""

    def __init__(self):
        self._checkpoints: dict[str, list[CheckpointRecord]] = {}
        self._lock = RLock()

    def add(
        self,
        *,
        task_id: str,
        label: str,
        state: dict[str, Any] | None = None,
    ) -> CheckpointRecord:
        checkpoint = CheckpointRecord(task_id=task_id, label=label, state=state or {})
        with self._lock:
            self._checkpoints.setdefault(task_id, []).append(checkpoint)
        return checkpoint

    def for_task(self, task_id: str) -> list[CheckpointRecord]:
        with self._lock:
            return list(self._checkpoints.get(task_id, []))

    def latest(self, task_id: str) -> CheckpointRecord | None:
        with self._lock:
            items = self._checkpoints.get(task_id, [])
            return items[-1] if items else None
