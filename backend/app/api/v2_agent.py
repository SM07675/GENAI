"""Genie Agent Runtime REST API (v2).

Exposes the agent runtime to the frontend via REST endpoints and
integrates with the WebSocket for real-time event streaming.

Endpoints:
    POST /api/v2/goals         — Submit a new goal
    GET  /api/v2/tasks         — List active/recent tasks
    GET  /api/v2/tasks/{id}    — Get task state + plan + timeline
    POST /api/v2/tasks/{id}/pause   — Pause task
    POST /api/v2/tasks/{id}/resume  — Resume task
    POST /api/v2/tasks/{id}/cancel  — Cancel task
    GET  /api/v2/agents        — List available agents
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger("genie.api.v2")

router = APIRouter(prefix="/api/v2", tags=["agent-runtime"])

# The runtime instance is set by main.py at startup
_runtime = None


def set_runtime(runtime: Any) -> None:
    """Set the global runtime instance. Called from main.py."""
    global _runtime
    _runtime = runtime


def get_runtime():
    """Get the global runtime instance."""
    if _runtime is None:
        raise HTTPException(status_code=503, detail="Agent runtime not initialized")
    return _runtime


# ── Request / Response models ─────────────────────────────────────────────────

class GoalRequest(BaseModel):
    input: str = Field(..., description="User's natural language input")
    session_id: str = Field(default="default", description="Session identifier")
    context: str = Field(default="", description="Optional context summary")


class GoalResponse(BaseModel):
    task_id: str
    goal_id: str
    objective: str
    is_simple: bool
    status: str


class TaskListResponse(BaseModel):
    tasks: list[dict[str, Any]]
    count: int


class TaskDetailResponse(BaseModel):
    task: dict[str, Any]


class ActionResponse(BaseModel):
    success: bool
    message: str


class AgentListResponse(BaseModel):
    agents: list[dict[str, Any]]
    count: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/goals", response_model=GoalResponse)
async def submit_goal(request: GoalRequest):
    """Submit a new goal for the agent runtime to execute.

    For simple queries (greetings, questions), returns immediately with
    is_simple=True so the frontend can handle directly.

    For complex goals, starts async execution and returns the task_id
    for tracking.
    """
    runtime = get_runtime()

    # Classify input first
    goal = await runtime.classify_input(
        user_input=request.input,
        context_summary=request.context,
    )

    if goal.is_simple:
        return GoalResponse(
            task_id="",
            goal_id=goal.goal_id,
            objective=goal.objective,
            is_simple=True,
            status="simple",
        )

    # Start async execution (don't await the full result)
    task_id = None

    async def _run():
        nonlocal task_id
        result = await runtime.execute_goal(
            user_input=request.input,
            session_id=request.session_id,
            context_summary=request.context,
        )
        return result

    # Create the task and get its ID
    # We need to start the execution and return immediately
    task = asyncio.create_task(_run())

    # Give the runtime a moment to create the task
    await asyncio.sleep(0.1)

    # Find the most recently created task
    all_tasks = runtime.get_all_tasks()
    if all_tasks:
        latest = all_tasks[-1]
        return GoalResponse(
            task_id=latest.task_id,
            goal_id=goal.goal_id,
            objective=goal.objective,
            is_simple=False,
            status=latest.status.value,
        )

    return GoalResponse(
        task_id="pending",
        goal_id=goal.goal_id,
        objective=goal.objective,
        is_simple=False,
        status="planning",
    )


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks():
    """List all active and recent tasks."""
    runtime = get_runtime()
    tasks = runtime.get_all_tasks()
    return TaskListResponse(
        tasks=[t.to_dict() for t in tasks],
        count=len(tasks),
    )


@router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task(task_id: str):
    """Get detailed state of a specific task."""
    runtime = get_runtime()
    state = runtime.get_task_state(task_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return TaskDetailResponse(task=state.to_dict())


@router.post("/tasks/{task_id}/pause", response_model=ActionResponse)
async def pause_task(task_id: str):
    """Pause a running task."""
    runtime = get_runtime()
    success = await runtime.pause_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot pause task (not running)")
    return ActionResponse(success=True, message="Task paused")


@router.post("/tasks/{task_id}/resume", response_model=ActionResponse)
async def resume_task(task_id: str):
    """Resume a paused task."""
    runtime = get_runtime()
    success = await runtime.resume_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot resume task (not paused)")
    return ActionResponse(success=True, message="Task resumed")


@router.post("/tasks/{task_id}/cancel", response_model=ActionResponse)
async def cancel_task(task_id: str):
    """Cancel a running or paused task."""
    runtime = get_runtime()
    success = await runtime.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel task")
    return ActionResponse(success=True, message="Task cancelled")


@router.get("/agents", response_model=AgentListResponse)
async def list_agents():
    """List all available agents."""
    runtime = get_runtime()
    agents = runtime.get_agent_info()
    return AgentListResponse(
        agents=agents,
        count=len(agents),
    )


@router.post("/kill", response_model=ActionResponse)
async def global_kill_switch():
    """Global Kill Switch: immediately cancel all active tasks and tool executions."""
    runtime = get_runtime()
    cancelled = await runtime.stop_all()
    return ActionResponse(
        success=True,
        message=f"Global kill switch executed: cancelled {cancelled} active tasks",
    )
