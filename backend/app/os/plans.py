"""Planning contracts for Genie OS tasks."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4


class PlanStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(slots=True)
class PlanStep:
    """A single executable or reasoning step."""

    title: str
    agent: str = "supervisor"
    tool_names: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    status: PlanStepStatus = PlanStepStatus.PENDING
    step_id: str = field(default_factory=lambda: f"step_{uuid4().hex}")
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "agent": self.agent,
            "tool_names": self.tool_names,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "notes": self.notes,
        }


@dataclass(slots=True)
class ExecutionPlan:
    """Structured plan attached to a Genie OS task."""

    objective: str
    task_type: str = "general"
    steps: list[PlanStep] = field(default_factory=list)
    expected_failures: list[str] = field(default_factory=list)
    estimated_seconds: int | None = None
    plan_id: str = field(default_factory=lambda: f"plan_{uuid4().hex}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "objective": self.objective,
            "task_type": self.task_type,
            "steps": [step.to_dict() for step in self.steps],
            "expected_failures": self.expected_failures,
            "estimated_seconds": self.estimated_seconds,
        }


def create_fast_plan(objective: str, *, task_type: str = "general") -> ExecutionPlan:
    """Create a conservative default plan for compatibility-mode turns."""
    return ExecutionPlan(
        objective=objective,
        task_type=task_type,
        steps=[
            PlanStep(title="Understand request", agent="conversation_agent"),
            PlanStep(title="Retrieve context and memory", agent="memory_agent"),
            PlanStep(title="Execute or answer", agent="supervisor_agent"),
            PlanStep(title="Verify result", agent="reflection_agent"),
            PlanStep(title="Update memory if useful", agent="memory_agent"),
        ],
        expected_failures=[
            "missing tool permission",
            "model/provider unavailable",
            "stale desktop context",
        ],
        estimated_seconds=10,
    )
