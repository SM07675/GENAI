"""Permission primitives for Genie OS.

The permission layer is intentionally local-first and deterministic. It does
not decide whether a tool is "safe" by prompting a model; it classifies side
effects and records explicit approval decisions that higher-level agents can
enforce before executing risky work.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from threading import RLock
from typing import Any
from uuid import uuid4

from .events import utc_now


class SideEffectLevel(StrEnum):
    READ_ONLY = "read_only"
    LOCAL_CHANGE = "local_change"
    EXTERNAL_NETWORK = "external_network"
    PERSONAL_DATA = "personal_data"
    DESTRUCTIVE = "destructive"
    ACCOUNT = "account"


class PermissionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


@dataclass(slots=True)
class PermissionRequest:
    """Human approval request for a sensitive action."""

    risk: SideEffectLevel
    description: str
    source: str
    task_id: str | None = None
    tool_call_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: f"perm_{uuid4().hex}")
    status: PermissionStatus = PermissionStatus.PENDING
    created_at: str = field(default_factory=utc_now)
    decided_at: str | None = None
    decision_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "task_id": self.task_id,
            "tool_call_id": self.tool_call_id,
            "risk": self.risk.value,
            "description": self.description,
            "source": self.source,
            "payload": self.payload,
            "status": self.status.value,
            "created_at": self.created_at,
            "decided_at": self.decided_at,
            "decision_reason": self.decision_reason,
        }


class PermissionRegistry:
    """Thread-safe in-memory permission registry.

    The current desktop app is single-user and local. This registry gives the
    runtime a concrete approval contract now; Phase 2 can persist the same
    request shape in SQLite without changing callers.
    """

    def __init__(self):
        self._requests: dict[str, PermissionRequest] = {}
        self._lock = RLock()

    def create(
        self,
        *,
        risk: SideEffectLevel,
        description: str,
        source: str,
        task_id: str | None = None,
        tool_call_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> PermissionRequest:
        request = PermissionRequest(
            risk=risk,
            description=description,
            source=source,
            task_id=task_id,
            tool_call_id=tool_call_id,
            payload=payload or {},
        )
        with self._lock:
            self._requests[request.request_id] = request
        return request

    def decide(
        self,
        request_id: str,
        *,
        approved: bool,
        reason: str = "",
    ) -> PermissionRequest | None:
        with self._lock:
            request = self._requests.get(request_id)
            if request is None:
                return None
            request.status = PermissionStatus.APPROVED if approved else PermissionStatus.DENIED
            request.decided_at = utc_now()
            request.decision_reason = reason
            return request

    def get(self, request_id: str) -> PermissionRequest | None:
        with self._lock:
            return self._requests.get(request_id)

    def pending(self) -> list[PermissionRequest]:
        with self._lock:
            return [r for r in self._requests.values() if r.status == PermissionStatus.PENDING]

    def recent(self, limit: int = 50) -> list[PermissionRequest]:
        with self._lock:
            return list(self._requests.values())[-limit:]


CONFIRMATION_LEVELS = {
    SideEffectLevel.DESTRUCTIVE,
    SideEffectLevel.ACCOUNT,
}


def side_effect_from_value(value: str | SideEffectLevel | None) -> SideEffectLevel:
    if isinstance(value, SideEffectLevel):
        return value
    raw = (value or SideEffectLevel.READ_ONLY.value).strip().lower()
    try:
        return SideEffectLevel(raw)
    except ValueError:
        return SideEffectLevel.READ_ONLY
