"""Shared data models for the Genie Agent Runtime.

All runtime components communicate through these typed schemas. Using
dataclasses (not Pydantic) for the internal domain models keeps them
lightweight and import-fast. Pydantic is used only at the API boundary.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Optional
from uuid import uuid4


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class TaskStatus(StrEnum):
    """Lifecycle status for a top-level task."""
    CREATED = "created"
    PLANNING = "planning"
    RUNNING = "running"
    PAUSED = "paused"
    REPLANNING = "replanning"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(StrEnum):
    """Lifecycle status for an individual plan step."""
    PENDING = "pending"
    READY = "ready"          # all dependencies satisfied
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class FailureCategory(StrEnum):
    """Categorized failure types for the recovery engine."""
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    TOOL_ERROR = "tool_error"
    INVALID_INPUT = "invalid_input"
    AUTH_REQUIRED = "auth_required"
    ELEMENT_NOT_FOUND = "element_not_found"
    APPLICATION_NOT_FOUND = "application_not_found"
    MODEL_ERROR = "model_error"
    PARSER_ERROR = "parser_error"
    PERMISSION_DENIED = "permission_denied"
    RESOURCE_UNAVAILABLE = "resource_unavailable"
    UNKNOWN_ERROR = "unknown_error"


class RecoveryAction(StrEnum):
    """What the recovery engine decided to do."""
    RETRY = "retry"
    ALTERNATIVE = "alternative"      # try different tool/approach
    REPLAN = "replan"                # re-plan from current state
    SKIP = "skip"                    # skip step if non-critical
    ASK_USER = "ask_user"            # need human input
    ABORT = "abort"                  # unrecoverable, abort task


class VerificationStatus(StrEnum):
    """Result of verifying an action's outcome."""
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    INCONCLUSIVE = "inconclusive"


class AutonomyLevel(StrEnum):
    """Progressive autonomy settings."""
    MANUAL = "manual"            # ask before most actions
    ASSIST = "assist"            # auto-safe, ask for external
    BALANCED = "balanced"        # auto-routine, ask for sensitive
    AUTONOMOUS = "autonomous"    # minimal interruption, hard safety boundaries


class ModelRole(StrEnum):
    """Roles for the model router."""
    FAST = "fast"                # quick responses, low latency
    REASONING = "reasoning"      # complex planning, analysis
    CODING = "coding"            # code generation, debugging
    VISION = "vision"            # image/screenshot understanding
    EMBEDDING = "embedding"      # vector embeddings


# ═══════════════════════════════════════════════════════════════════════════════
# CORE DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

def _new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid4().hex[:12]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Goal:
    """A user's high-level objective extracted from their input."""
    objective: str
    constraints: list[str] = field(default_factory=list)
    expected_outcome: str = ""
    required_capabilities: list[str] = field(default_factory=list)
    raw_input: str = ""
    context_summary: str = ""
    goal_id: str = field(default_factory=lambda: _new_id("goal_"))
    created_at: str = field(default_factory=_now_iso)
    is_simple: bool = False  # True for quick chat, False for agentic tasks

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "objective": self.objective,
            "constraints": self.constraints,
            "expected_outcome": self.expected_outcome,
            "required_capabilities": self.required_capabilities,
            "raw_input": self.raw_input,
            "context_summary": self.context_summary,
            "is_simple": self.is_simple,
            "created_at": self.created_at,
        }


@dataclass
class RetryPolicy:
    """Retry configuration for a plan step."""
    max_retries: int = 2
    backoff_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    retryable_failures: list[FailureCategory] = field(
        default_factory=lambda: [
            FailureCategory.NETWORK_ERROR,
            FailureCategory.TIMEOUT,
            FailureCategory.TOOL_ERROR,
        ]
    )


@dataclass
class PlanStep:
    """A single executable step within an execution plan."""
    title: str
    description: str = ""
    agent: str = "general"
    tool_names: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    step_id: str = field(default_factory=lambda: _new_id("step_"))
    parallel_group: str | None = None    # steps in same group can run concurrently
    condition: str | None = None          # optional condition for execution
    fallback_step_id: str | None = None   # step to run if this one fails
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    timeout_seconds: float = 120.0
    retry_count: int = 0
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    observations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "description": self.description,
            "agent": self.agent,
            "tool_names": self.tool_names,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "parallel_group": self.parallel_group,
            "condition": self.condition,
            "fallback_step_id": self.fallback_step_id,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "observations": self.observations,
        }


@dataclass
class ExecutionPlan:
    """A structured plan for accomplishing a goal."""
    objective: str
    task_type: str = "general"
    steps: list[PlanStep] = field(default_factory=list)
    expected_failures: list[str] = field(default_factory=list)
    estimated_seconds: int | None = None
    plan_id: str = field(default_factory=lambda: _new_id("plan_"))
    created_at: str = field(default_factory=_now_iso)
    version: int = 1  # incremented on replan

    @property
    def completed_steps(self) -> list[PlanStep]:
        return [s for s in self.steps if s.status == StepStatus.COMPLETED]

    @property
    def failed_steps(self) -> list[PlanStep]:
        return [s for s in self.steps if s.status == StepStatus.FAILED]

    @property
    def pending_steps(self) -> list[PlanStep]:
        return [s for s in self.steps if s.status in (StepStatus.PENDING, StepStatus.READY)]

    @property
    def current_step(self) -> PlanStep | None:
        running = [s for s in self.steps if s.status == StepStatus.RUNNING]
        return running[0] if running else None

    @property
    def progress(self) -> float:
        if not self.steps:
            return 0.0
        done = len([s for s in self.steps if s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED)])
        return done / len(self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "objective": self.objective,
            "task_type": self.task_type,
            "steps": [s.to_dict() for s in self.steps],
            "expected_failures": self.expected_failures,
            "estimated_seconds": self.estimated_seconds,
            "progress": self.progress,
            "version": self.version,
            "created_at": self.created_at,
        }


@dataclass
class Observation:
    """Evidence collected after an action is performed."""
    source: str             # e.g. "filesystem", "browser_dom", "screenshot", "command_output"
    content: str            # human-readable summary
    raw_data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_now_iso)
    observation_id: str = field(default_factory=lambda: _new_id("obs_"))
    step_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "source": self.source,
            "content": self.content,
            "step_id": self.step_id,
            "timestamp": self.timestamp,
        }


@dataclass
class VerificationResult:
    """Result of verifying whether an action succeeded."""
    status: VerificationStatus
    message: str
    checks: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0
    step_id: str | None = None
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "message": self.message,
            "checks": self.checks,
            "confidence": self.confidence,
            "step_id": self.step_id,
            "timestamp": self.timestamp,
        }


@dataclass
class FailedStep:
    """Detailed failure information for a plan step."""
    step: PlanStep
    category: FailureCategory
    error_message: str
    traceback: str = ""
    attempt_number: int = 1
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step.step_id,
            "step_title": self.step.title,
            "category": self.category.value,
            "error_message": self.error_message,
            "attempt_number": self.attempt_number,
            "timestamp": self.timestamp,
        }


@dataclass
class TimelineEntry:
    """A single entry in the task timeline, visible to the user."""
    timestamp: str
    agent: str
    action: str
    detail: str = ""
    status: str = "info"  # info, success, warning, error
    step_id: str | None = None
    tool_name: str | None = None
    duration_ms: int | None = None
    entry_id: str = field(default_factory=lambda: _new_id("tl_"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "agent": self.agent,
            "action": self.action,
            "detail": self.detail,
            "status": self.status,
            "step_id": self.step_id,
            "tool_name": self.tool_name,
            "duration_ms": self.duration_ms,
        }


@dataclass
class AgentState:
    """Complete runtime state for a task — the core state object.

    This is what the runtime tracks for every active task and what the
    frontend queries to render the task workspace.
    """
    session_id: str
    task_id: str
    goal: Goal
    status: TaskStatus = TaskStatus.CREATED
    plan: ExecutionPlan | None = None
    active_agent: str | None = None
    active_tool: str | None = None
    observations: list[Observation] = field(default_factory=list)
    failed_steps: list[FailedStep] = field(default_factory=list)
    timeline: list[TimelineEntry] = field(default_factory=list)
    memory_context: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0
    autonomy_level: AutonomyLevel = AutonomyLevel.BALANCED
    started_at: str = field(default_factory=_now_iso)
    paused_at: str | None = None
    completed_at: str | None = None
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def elapsed_seconds(self) -> float:
        start = datetime.fromisoformat(self.started_at)
        end = datetime.now(timezone.utc) if not self.completed_at else datetime.fromisoformat(self.completed_at)
        return (end - start).total_seconds()

    @property
    def current_step(self) -> PlanStep | None:
        return self.plan.current_step if self.plan else None

    @property
    def progress(self) -> float:
        return self.plan.progress if self.plan else 0.0

    def add_timeline(
        self,
        agent: str,
        action: str,
        detail: str = "",
        status: str = "info",
        step_id: str | None = None,
        tool_name: str | None = None,
        duration_ms: int | None = None,
    ) -> TimelineEntry:
        entry = TimelineEntry(
            timestamp=_now_iso(),
            agent=agent,
            action=action,
            detail=detail,
            status=status,
            step_id=step_id,
            tool_name=tool_name,
            duration_ms=duration_ms,
        )
        self.timeline.append(entry)
        return entry

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "goal": self.goal.to_dict(),
            "status": self.status.value,
            "plan": self.plan.to_dict() if self.plan else None,
            "active_agent": self.active_agent,
            "active_tool": self.active_tool,
            "observations": [o.to_dict() for o in self.observations[-20:]],
            "failed_steps": [f.to_dict() for f in self.failed_steps],
            "timeline": [t.to_dict() for t in self.timeline[-50:]],
            "confidence": self.confidence,
            "autonomy_level": self.autonomy_level.value,
            "progress": self.progress,
            "started_at": self.started_at,
            "paused_at": self.paused_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "elapsed_seconds": self.elapsed_seconds,
        }


@dataclass
class TaskContext:
    """Context passed to agents when executing a step.

    Contains everything an agent needs to do its work.
    """
    task_id: str
    session_id: str
    goal: Goal
    step: PlanStep
    plan: ExecutionPlan
    previous_results: dict[str, dict[str, Any]] = field(default_factory=dict)  # step_id → result
    memory_context: list[dict[str, Any]] = field(default_factory=list)
    environment: dict[str, Any] = field(default_factory=dict)
    autonomy_level: AutonomyLevel = AutonomyLevel.BALANCED


@dataclass
class StepResult:
    """Result returned by an agent after executing a step."""
    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    observations: list[Observation] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)  # file paths created
    needs_verification: bool = True
    suggested_next: str | None = None  # suggestion for next step

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "observations": [o.to_dict() for o in self.observations],
            "artifacts": self.artifacts,
            "needs_verification": self.needs_verification,
            "suggested_next": self.suggested_next,
        }


@dataclass
class TaskResult:
    """Final result of a completed task."""
    task_id: str
    goal_id: str
    success: bool
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    timeline_summary: list[dict[str, Any]] = field(default_factory=list)
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    elapsed_seconds: float = 0.0
    completed_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal_id": self.goal_id,
            "success": self.success,
            "summary": self.summary,
            "data": self.data,
            "artifacts": self.artifacts,
            "timeline_summary": self.timeline_summary,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "elapsed_seconds": self.elapsed_seconds,
            "completed_at": self.completed_at,
        }
