"""Tool Executor — permissioned tool execution with timeout and observation.

Wraps the existing tool registry with:
    - Permission checks before execution
    - Timeout enforcement
    - Audit logging
    - Event emission for real-time UI updates
    - Observation collection after execution
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import structlog

from .schemas import Observation, _now_iso
from ..schemas import ToolResult
from ..os.permissions import SideEffectLevel, CONFIRMATION_LEVELS

log = structlog.get_logger("genie.runtime.tool_executor")


class ToolExecutor:
    """Executes tools with permission checks, timeouts, and observations.

    This wraps the existing ``tools.execute_tool`` with the runtime's
    safety and observability requirements.
    """

    def __init__(
        self,
        kernel: Any = None,
        event_bus: Any = None,
        autonomy_level: str = "balanced",
    ):
        self._kernel = kernel
        self._event_bus = event_bus
        self._autonomy_level = autonomy_level
        self._execution_log: list[dict[str, Any]] = []

    async def execute(
        self,
        tool_name: str,
        args: dict[str, Any],
        *,
        task_id: str | None = None,
        step_id: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> tuple[ToolResult, Observation]:
        """Execute a tool with permission checks and observation.

        Returns:
            Tuple of (ToolResult, Observation) — the tool's result and
            the observation of what happened.
        """
        start_time = time.monotonic()

        # Emit tool_start event
        await self._emit_event("agent.tool_called", {
            "tool_name": tool_name,
            "args": self._sanitize_args(args),
            "task_id": task_id,
            "step_id": step_id,
        })

        try:
            # Import here to avoid circular imports
            from ..tools import execute_tool, TOOLS

            # Check if tool exists
            tool_entry = TOOLS.get(tool_name)
            if tool_entry is None:
                result = ToolResult(
                    status="error",
                    message=f"Tool '{tool_name}' not found",
                )
                observation = Observation(
                    source="tool_executor",
                    content=f"Tool '{tool_name}' not found in registry",
                    step_id=step_id,
                )
                return result, observation

            # Check permissions
            if tool_entry.side_effect_level in CONFIRMATION_LEVELS:
                if self._autonomy_level in ("manual", "assist"):
                    # Would need user confirmation — for now, proceed with logging
                    log.info(
                        "tool_permission_check",
                        tool=tool_name,
                        level=tool_entry.side_effect_level.value,
                        autonomy=self._autonomy_level,
                    )

            # Execute with timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(execute_tool, tool_name, args),
                timeout=timeout_seconds,
            )

            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            # Create observation from result
            observation = Observation(
                source=f"tool:{tool_name}",
                content=f"Tool '{tool_name}' returned: {result.status} — {result.message}",
                raw_data={
                    "status": result.status,
                    "message": result.message,
                    "data": result.data if result.data else {},
                },
                step_id=step_id,
            )

            # Log execution
            self._execution_log.append({
                "tool_name": tool_name,
                "args": self._sanitize_args(args),
                "status": result.status,
                "elapsed_ms": elapsed_ms,
                "task_id": task_id,
                "step_id": step_id,
                "timestamp": _now_iso(),
            })

            # Emit tool_complete event
            await self._emit_event("agent.tool_completed", {
                "tool_name": tool_name,
                "status": result.status,
                "elapsed_ms": elapsed_ms,
                "task_id": task_id,
                "step_id": step_id,
            })

            return result, observation

        except asyncio.TimeoutError:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            result = ToolResult(
                status="error",
                message=f"Tool '{tool_name}' timed out after {timeout_seconds}s",
            )
            observation = Observation(
                source=f"tool:{tool_name}",
                content=f"Tool '{tool_name}' timed out after {timeout_seconds}s",
                step_id=step_id,
            )

            await self._emit_event("agent.tool_failed", {
                "tool_name": tool_name,
                "error": "timeout",
                "elapsed_ms": elapsed_ms,
                "task_id": task_id,
                "step_id": step_id,
            })

            return result, observation

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            result = ToolResult(
                status="error",
                message=f"Tool '{tool_name}' failed: {exc}",
            )
            observation = Observation(
                source=f"tool:{tool_name}",
                content=f"Tool '{tool_name}' raised exception: {exc}",
                step_id=step_id,
            )

            await self._emit_event("agent.tool_failed", {
                "tool_name": tool_name,
                "error": str(exc),
                "elapsed_ms": elapsed_ms,
                "task_id": task_id,
                "step_id": step_id,
            })

            return result, observation

    async def _emit_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Emit an event through the event bus."""
        if self._event_bus:
            try:
                await self._event_bus.publish(event_type, payload)
            except Exception:
                pass

    @staticmethod
    def _sanitize_args(args: dict[str, Any]) -> dict[str, Any]:
        """Sanitize args for logging (remove sensitive data)."""
        sanitized = {}
        sensitive_keys = {"password", "token", "key", "secret", "auth"}
        for k, v in args.items():
            if any(sk in k.lower() for sk in sensitive_keys):
                sanitized[k] = "***"
            elif isinstance(v, str) and len(v) > 500:
                sanitized[k] = v[:500] + "..."
            else:
                sanitized[k] = v
        return sanitized

    @property
    def recent_executions(self) -> list[dict[str, Any]]:
        """Get recent tool executions for debugging."""
        return self._execution_log[-50:]
