"""Interrupt Handler for Genie AI OS.

Enables natural user interventions during task execution:
- "Wait / Pause" -> Pauses execution graph
- "Cancel that / Stop" -> Terminates running task cleanly
- "Change that / Use X instead" -> Injects updated constraint and triggers replan
- "Continue / Resume" -> Resumes paused graph
- "What are you doing?" -> Summarizes active step and recent observations
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Optional

import structlog

from .agent_runtime import AgentRuntime
from .schemas import AgentState, TaskStatus

log = structlog.get_logger("genie.runtime.interrupt")


class InterruptType(StrEnum):
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"
    STATUS_QUERY = "status_query"
    MODIFY_CONSTRAINT = "modify_constraint"
    UNKNOWN = "unknown"


@dataclass
class InterruptResult:
    handled: bool
    interrupt_type: InterruptType
    message: str
    action_taken: Optional[str] = None


class InterruptHandler:
    """Detects and executes runtime interruptions from user voice/text input."""

    def __init__(self, runtime: AgentRuntime):
        self._runtime = runtime

    def classify_interrupt(self, user_text: str) -> tuple[InterruptType, Optional[str]]:
        """Determine if text is an interrupt command."""
        t = user_text.strip().lower()
        
        # Stop / Cancel
        if any(re.search(rf"\b{word}\b", t) for word in ["cancel", "stop", "abort", "nevermind", "kill task"]):
            return InterruptType.CANCEL, None

        # Pause / Wait
        if any(re.search(rf"\b{word}\b", t) for word in ["pause", "hold on", "wait", "freeze"]):
            return InterruptType.PAUSE, None

        # Resume / Continue
        if any(re.search(rf"\b{word}\b", t) for word in ["resume", "continue", "go ahead", "unpause", "keep going"]):
            return InterruptType.RESUME, None

        # Status / What are you doing
        if any(phrase in t for phrase in ["what are you doing", "what's the progress", "status update", "where are we"]):
            return InterruptType.STATUS_QUERY, None

        # Constraint modification (e.g. "instead use kaggle", "switch to python")
        if any(t.startswith(prefix) for prefix in ["instead ", "switch to ", "change to ", "use "]):
            return InterruptType.MODIFY_CONSTRAINT, user_text

        return InterruptType.UNKNOWN, None

    async def handle_if_interrupt(self, user_text: str, active_task_id: Optional[str] = None) -> InterruptResult:
        """Evaluate if input is an interrupt and execute it against active task."""
        itype, param = self.classify_interrupt(user_text)
        if itype == InterruptType.UNKNOWN:
            return InterruptResult(handled=False, interrupt_type=itype, message="")

        # Resolve active task if not explicitly passed
        target_task_id = active_task_id
        if not target_task_id:
            tasks = [t for t in self._runtime.get_all_tasks() if t.status in (TaskStatus.RUNNING, TaskStatus.PAUSED)]
            if tasks:
                target_task_id = tasks[-1].task_id

        if not target_task_id:
            return InterruptResult(
                handled=True,
                interrupt_type=itype,
                message="There is no active task currently running.",
            )

        state = self._runtime.get_task_state(target_task_id)
        if not state:
            return InterruptResult(handled=False, interrupt_type=itype, message="Task not found.")

        if itype == InterruptType.CANCEL:
            await self._runtime.cancel_task(target_task_id)
            return InterruptResult(
                handled=True,
                interrupt_type=itype,
                message=f"I've stopped the task: {state.goal.objective}.",
                action_taken="cancelled",
            )

        elif itype == InterruptType.PAUSE:
            await self._runtime.pause_task(target_task_id)
            return InterruptResult(
                handled=True,
                interrupt_type=itype,
                message="I've paused the current task. Let me know when you want to continue.",
                action_taken="paused",
            )

        elif itype == InterruptType.RESUME:
            await self._runtime.resume_task(target_task_id)
            return InterruptResult(
                handled=True,
                interrupt_type=itype,
                message="Resuming the task now.",
                action_taken="resumed",
            )

        elif itype == InterruptType.STATUS_QUERY:
            current = state.current_step.title if state.current_step else "Executing"
            pct = int(state.progress * 100)
            return InterruptResult(
                handled=True,
                interrupt_type=itype,
                message=f"I'm working on '{state.goal.objective}' ({pct}% complete). Current step: {current}.",
                action_taken="reported_status",
            )

        elif itype == InterruptType.MODIFY_CONSTRAINT:
            # Add constraint to goal and replan
            state.goal.constraints.append(param or user_text)
            state.add_timeline("user", f"Updated instruction: {param}")
            # Trigger pause & resume to pick up new constraint
            await self._runtime.pause_task(target_task_id)
            await self._runtime.resume_task(target_task_id)
            return InterruptResult(
                handled=True,
                interrupt_type=itype,
                message=f"Got it. Adjusting the approach to: {param}.",
                action_taken="modified_constraint",
            )

        return InterruptResult(handled=False, interrupt_type=InterruptType.UNKNOWN, message="")
