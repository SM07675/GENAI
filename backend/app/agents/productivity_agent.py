"""Productivity Agent — tasks, reminders, notes, calendar."""
from __future__ import annotations
from .base_agent import BaseAgent
from ..runtime.schemas import Observation, PlanStep, StepResult, TaskContext


class ProductivityAgent(BaseAgent):
    name = "productivity"
    description = "Tasks, reminders, notes management"
    capabilities = ["task_manage", "reminder", "note", "todo", "calendar"]
    tools = ["manage_note", "set_reminder"]

    async def execute(self, step: PlanStep, context: TaskContext) -> StepResult:
        observations: list[Observation] = []
        desc = (step.description or step.title).lower()

        if any(w in desc for w in ["reminder", "remind"]):
            result, obs = await self._execute_tool(
                "set_reminder", {"text": step.description or step.title}, context,
            )
            observations.append(obs)
            return StepResult(
                success=result.status in ("ok", "success"),
                message=result.message,
                data=result.data or {},
                observations=observations,
            )

        if any(w in desc for w in ["note", "save", "remember"]):
            result, obs = await self._execute_tool(
                "manage_note", {"action": "create", "content": step.description or step.title}, context,
            )
            observations.append(obs)
            return StepResult(
                success=result.status in ("ok", "success"),
                message=result.message,
                data=result.data or {},
                observations=observations,
            )

        return StepResult(
            success=False,
            message=f"Unknown productivity action: {step.title}",
        )
