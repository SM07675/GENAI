"""Genie OS kernel.

The kernel is the compatibility bridge between the current assistant and the
target OS architecture. It owns task lifecycle and event emission, while the
existing orchestrator continues to handle model/tool execution for now.
"""
from __future__ import annotations

from typing import Any

from .checkpoints import CheckpointRecord, CheckpointRegistry
from .events import EventEnvelope, EventLog
from .permissions import PermissionRegistry, PermissionRequest, SideEffectLevel
from .store import SQLiteOSStore
from .tasks import TaskRecord, TaskRegistry, TaskStatus


class GenieOSKernel:
    def __init__(self, store: SQLiteOSStore | None = None):
        self.tasks = TaskRegistry()
        self.events = EventLog()
        self.permissions = PermissionRegistry()
        self.checkpoints = CheckpointRegistry()
        self.store = store or SQLiteOSStore()

    def emit_event(
        self,
        event_type: str,
        *,
        source: str,
        payload: dict[str, Any] | None = None,
        task_id: str | None = None,
        trace_id: str | None = None,
        privacy: str = "local",
    ) -> EventEnvelope:
        event = self.events.append(
            EventEnvelope(
                type=event_type,
                source=source,
                payload=payload or {},
                task_id=task_id,
                trace_id=trace_id,
                privacy=privacy,
            )
        )
        self.store.append_event(event)
        return event

    def begin_user_turn(
        self,
        *,
        session_id: str,
        input_text: str,
        source: str,
    ) -> TaskRecord:
        task = self.tasks.create(
            title=_title_from_input(input_text),
            source=source,
            session_id=session_id,
            input_text=input_text,
        )
        self.tasks.transition(task.task_id, TaskStatus.RUNNING)
        self.store.upsert_task(task)
        self.emit_event(
            "task.started",
            source=source,
            task_id=task.task_id,
            trace_id=task.trace_id,
            payload={
                "session_id": session_id,
                "title": task.title,
                "input_preview": input_text[:240],
            },
        )
        self.emit_event(
            "input.text.received",
            source=source,
            task_id=task.task_id,
            trace_id=task.trace_id,
            payload={"text": input_text},
        )
        return task

    def record_checkpoint(
        self,
        task_id: str,
        *,
        label: str,
        state: dict[str, Any] | None = None,
    ) -> CheckpointRecord:
        checkpoint = self.checkpoints.add(task_id=task_id, label=label, state=state or {})
        task = self.tasks.get(task_id)
        self.emit_event(
            "checkpoint.created",
            source="os.kernel",
            task_id=task_id,
            trace_id=task.trace_id if task else None,
            payload=checkpoint.to_dict(),
        )
        return checkpoint

    def record_tool_started(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        side_effect_level: SideEffectLevel,
        task_id: str | None = None,
        trace_id: str | None = None,
    ) -> EventEnvelope:
        return self.emit_event(
            "tool.started",
            source="tool.runtime",
            task_id=task_id,
            trace_id=trace_id,
            payload={
                "tool": tool_name,
                "arguments": _redact_tool_arguments(arguments),
                "side_effect_level": side_effect_level.value,
            },
        )

    def record_tool_completed(
        self,
        *,
        tool_name: str,
        status: str,
        message: str = "",
        task_id: str | None = None,
        trace_id: str | None = None,
    ) -> EventEnvelope:
        return self.emit_event(
            "tool.completed",
            source="tool.runtime",
            task_id=task_id,
            trace_id=trace_id,
            payload={
                "tool": tool_name,
                "status": status,
                "message": message[:500],
            },
        )

    def request_permission(
        self,
        *,
        risk: SideEffectLevel,
        description: str,
        source: str,
        task_id: str | None = None,
        tool_call_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> PermissionRequest:
        request = self.permissions.create(
            risk=risk,
            description=description,
            source=source,
            task_id=task_id,
            tool_call_id=tool_call_id,
            payload=payload or {},
        )
        self.emit_event(
            "permission.required",
            source=source,
            task_id=task_id,
            payload=request.to_dict(),
        )
        return request

    def decide_permission(
        self,
        request_id: str,
        *,
        approved: bool,
        reason: str = "",
    ) -> PermissionRequest | None:
        request = self.permissions.decide(request_id, approved=approved, reason=reason)
        if request is not None:
            self.emit_event(
                "permission.decided",
                source="os.kernel",
                task_id=request.task_id,
                payload=request.to_dict(),
            )
        return request

    def complete_task(self, task_id: str, result: dict[str, Any] | None = None) -> TaskRecord | None:
        task = self.tasks.complete(task_id, result=result)
        if task is not None:
            self.store.upsert_task(task)
            self.emit_event(
                "task.completed",
                source="os.kernel",
                task_id=task.task_id,
                trace_id=task.trace_id,
                payload=result or {},
            )
        return task

    def fail_task(self, task_id: str, error: str) -> TaskRecord | None:
        task = self.tasks.fail(task_id, error)
        if task is not None:
            self.store.upsert_task(task)
            self.emit_event(
                "task.failed",
                source="os.kernel",
                task_id=task.task_id,
                trace_id=task.trace_id,
                payload={"error": error},
            )
        return task

    def cancel_task(self, task_id: str, reason: str = "cancelled") -> TaskRecord | None:
        task = self.tasks.cancel(task_id, reason)
        if task is not None:
            self.store.upsert_task(task)
            self.emit_event(
                "task.cancelled",
                source="os.kernel",
                task_id=task.task_id,
                trace_id=task.trace_id,
                payload={"reason": reason},
            )
        return task

    def snapshot(self) -> dict[str, Any]:
        return {
            "tasks": [task.to_dict() for task in self.tasks.recent()],
            "events": [event.to_dict() for event in self.events.recent()],
            "permissions": [item.to_dict() for item in self.permissions.recent()],
        }


def _title_from_input(input_text: str) -> str:
    text = " ".join((input_text or "").split())
    if not text:
        return "User turn"
    return text[:80] + ("..." if len(text) > 80 else "")


def _redact_tool_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    sensitive_tokens = ("key", "token", "password", "secret", "pin")
    for key, value in (arguments or {}).items():
        if any(token in key.lower() for token in sensitive_tokens):
            redacted[key] = "[redacted]"
        else:
            redacted[key] = value
    return redacted


_KERNEL = GenieOSKernel()


def get_kernel() -> GenieOSKernel:
    return _KERNEL
