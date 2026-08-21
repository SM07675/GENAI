"""Agent Runtime — the central orchestrator for Genie's agentic capabilities.

This is the heart of Genie. The AgentRuntime manages the full lifecycle of
a user's goal from intent to completion:

    User Input → Goal Engine → Planner → Task Graph → Agent Router
    → Tool Executor → Observation → Verification → Recovery → Memory

It supports:
    - Multiple concurrent tasks
    - Pause / resume / cancel
    - Replanning after failures
    - Real-time event streaming to the UI
    - Memory updates after task completion
    - User interruptions and plan modification
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Optional

import structlog

from .schemas import (
    AgentState,
    AutonomyLevel,
    ExecutionPlan,
    FailedStep,
    Goal,
    Observation,
    PlanStep,
    RecoveryAction,
    StepResult,
    StepStatus,
    TaskContext,
    TaskResult,
    TaskStatus,
    VerificationStatus,
    _new_id,
    _now_iso,
)
from .goal_engine import GoalEngine
from .planner import Planner
from .task_graph import TaskGraph
from .agent_router import AgentRouter
from .tool_executor import ToolExecutor
from .observation_engine import ObservationEngine
from .verification_engine import VerificationEngine
from .recovery_engine import RecoveryEngine

log = structlog.get_logger("genie.runtime")

# Type for event emission callback
EventEmitter = Callable[[str, dict[str, Any]], Awaitable[None]]


async def _noop_emit(event_type: str, payload: dict[str, Any]) -> None:
    """No-op event emitter."""
    pass


class AgentRuntime:
    """Central runtime for Genie's agentic task execution.

    Created once at startup. Manages all active tasks and their lifecycles.

    Usage:
        runtime = AgentRuntime(model_router=router, event_bus=bus)
        runtime.register_agent(GeneralAgent())
        runtime.register_agent(ResearchAgent())
        ...

        # Execute a goal
        result = await runtime.execute_goal(
            user_input="Research AI trends and create a report",
            session_id="session_123",
        )

        # Or for simple queries, fast-path through the goal engine
        goal = await runtime.classify_input("What time is it?")
        if goal.is_simple:
            # Handle directly via LLM, skip agentic pipeline
            ...
    """

    def __init__(
        self,
        model_router: Any = None,
        event_bus: Any = None,
        kernel: Any = None,
        autonomy_level: AutonomyLevel = AutonomyLevel.BALANCED,
    ):
        # Core engines
        self._goal_engine = GoalEngine(model_router=model_router)
        self._planner = Planner(model_router=model_router)
        self._agent_router = AgentRouter()
        self._tool_executor = ToolExecutor(
            kernel=kernel,
            event_bus=event_bus,
            autonomy_level=autonomy_level.value,
        )
        self._observation_engine = ObservationEngine()
        self._verification_engine = VerificationEngine()
        self._recovery_engine = RecoveryEngine(model_router=model_router)

        # State
        self._active_tasks: dict[str, AgentState] = {}
        self._task_graphs: dict[str, TaskGraph] = {}
        self._model_router = model_router
        self._event_bus = event_bus
        self._kernel = kernel
        self._autonomy_level = autonomy_level
        self._emit: EventEmitter = _noop_emit

        # Configuration
        self._max_replan_attempts = 3
        self._max_concurrent_tasks = 5

    # ── Agent registration ────────────────────────────────────────────────────

    def register_agent(self, agent: Any) -> None:
        """Register a specialized agent with the runtime."""
        self._agent_router.register(agent)

    def set_event_emitter(self, emitter: EventEmitter) -> None:
        """Set the event emitter for real-time UI updates."""
        self._emit = emitter

    # ── Goal classification (fast path check) ─────────────────────────────────

    async def classify_input(
        self,
        user_input: str,
        context_summary: str = "",
    ) -> Goal:
        """Classify user input as simple or complex.

        Use this to decide whether to route through the agentic pipeline
        or handle directly via the existing LLM orchestrator.
        """
        return await self._goal_engine.extract_goal(
            user_input=user_input,
            context_summary=context_summary,
        )

    # ── Main execution entry point ────────────────────────────────────────────

    async def execute_goal(
        self,
        user_input: str,
        session_id: str,
        context_summary: str = "",
    ) -> TaskResult:
        """Execute a user's goal through the full agentic pipeline.

        This is the primary entry point for complex tasks. For simple
        queries, use classify_input() first and handle directly.

        Pipeline:
            1. Extract goal from user input
            2. Create execution plan
            3. Build task graph
            4. Execute steps (with observation, verification, recovery)
            5. Update memory
            6. Return result
        """
        task_id = _new_id("task_")

        # Step 1: Extract goal
        await self._emit("agent.goal_received", {
            "task_id": task_id,
            "input": user_input[:500],
        })

        goal = await self._goal_engine.extract_goal(
            user_input=user_input,
            context_summary=context_summary,
            session_id=session_id,
        )

        # Create agent state
        state = AgentState(
            session_id=session_id,
            task_id=task_id,
            goal=goal,
            status=TaskStatus.PLANNING,
            autonomy_level=self._autonomy_level,
        )
        self._active_tasks[task_id] = state

        state.add_timeline("runtime", "Goal received", goal.objective)

        try:
            # Step 2: Create plan
            await self._emit("agent.planning_started", {
                "task_id": task_id,
                "goal": goal.objective,
            })

            plan = await self._planner.create_plan(
                goal=goal,
                context_summary=context_summary,
            )
            state.plan = plan
            state.status = TaskStatus.RUNNING

            state.add_timeline(
                "planner", "Plan created",
                f"{len(plan.steps)} steps, estimated {plan.estimated_seconds}s",
                status="success",
            )

            await self._emit("agent.plan_created", {
                "task_id": task_id,
                "plan": plan.to_dict(),
            })

            # Step 3: Execute plan
            result = await self._execute_plan(state)
            return result

        except asyncio.CancelledError:
            state.status = TaskStatus.CANCELLED
            state.completed_at = _now_iso()
            state.add_timeline("runtime", "Task cancelled", status="warning")

            await self._emit("agent.task_cancelled", {"task_id": task_id})

            return TaskResult(
                task_id=task_id,
                goal_id=goal.goal_id,
                success=False,
                summary="Task was cancelled",
            )

        except Exception as exc:
            state.status = TaskStatus.FAILED
            state.error = str(exc)
            state.completed_at = _now_iso()
            state.add_timeline("runtime", "Task failed", str(exc), status="error")

            await self._emit("agent.task_failed", {
                "task_id": task_id,
                "error": str(exc),
            })

            log.error("task_failed", task_id=task_id, error=str(exc))

            return TaskResult(
                task_id=task_id,
                goal_id=goal.goal_id,
                success=False,
                summary=f"Task failed: {exc}",
            )

        finally:
            # Clean up
            self._task_graphs.pop(task_id, None)

    # ── Plan execution ────────────────────────────────────────────────────────

    async def _execute_plan(self, state: AgentState) -> TaskResult:
        """Execute an entire plan through the task graph."""
        plan = state.plan
        assert plan is not None

        replan_count = 0

        while replan_count <= self._max_replan_attempts:
            # Build task graph
            graph = TaskGraph(plan)
            self._task_graphs[state.task_id] = graph

            # Execute the graph
            results = await graph.execute(
                executor=lambda step, ctx: self._execute_step(step, ctx, state),
                task_context=TaskContext(
                    task_id=state.task_id,
                    session_id=state.session_id,
                    goal=state.goal,
                    step=PlanStep(title=""),  # placeholder, overridden per-step
                    plan=plan,
                    memory_context=state.memory_context,
                    autonomy_level=state.autonomy_level,
                ),
                on_step_start=lambda step: self._on_step_start(step, state),
                on_step_complete=lambda step, result: self._on_step_complete(step, result, state),
                on_step_failed=lambda step, exc: self._on_step_failed(step, exc, state),
            )

            # Check if we need to replan
            if graph.has_failures and replan_count < self._max_replan_attempts:
                # Try recovery
                should_replan = False
                for step in plan.steps:
                    if step.status == StepStatus.FAILED:
                        action, failed_step, explanation = await self._recovery_engine.handle_failure(
                            step, step.error or "Unknown error", state
                        )

                        state.failed_steps.append(failed_step)
                        state.add_timeline(
                            "recovery", f"Recovery: {action.value}",
                            explanation, status="warning",
                        )

                        await self._emit("agent.recovery_action", {
                            "task_id": state.task_id,
                            "action": action.value,
                            "explanation": explanation,
                            "step_id": step.step_id,
                        })

                        if action == RecoveryAction.RETRY:
                            step.status = StepStatus.PENDING
                            step.retry_count += 1
                            step.error = None
                        elif action == RecoveryAction.REPLAN:
                            should_replan = True
                            break
                        elif action == RecoveryAction.SKIP:
                            step.status = StepStatus.SKIPPED
                        elif action == RecoveryAction.ABORT:
                            state.status = TaskStatus.FAILED
                            state.error = explanation
                            state.completed_at = _now_iso()
                            break
                        elif action == RecoveryAction.ASK_USER:
                            state.status = TaskStatus.PAUSED
                            state.paused_at = _now_iso()
                            state.add_timeline(
                                "runtime", "Waiting for user input",
                                explanation, status="warning",
                            )
                            break

                if should_replan:
                    replan_count += 1
                    state.status = TaskStatus.REPLANNING

                    state.add_timeline(
                        "planner", f"Replanning (attempt {replan_count})",
                        status="warning",
                    )

                    await self._emit("agent.replanning", {
                        "task_id": state.task_id,
                        "attempt": replan_count,
                    })

                    plan = await self._planner.replan(
                        goal=state.goal,
                        completed_steps=plan.completed_steps,
                        failed_step=state.failed_steps[-1],
                        context_summary=state.goal.context_summary,
                    )
                    state.plan = plan
                    state.status = TaskStatus.RUNNING

                    await self._emit("agent.plan_created", {
                        "task_id": state.task_id,
                        "plan": plan.to_dict(),
                        "version": plan.version,
                    })

                    continue  # re-execute with new plan

            # Plan execution finished
            break

        # Build final result
        return await self._build_task_result(state)

    async def _execute_step(
        self,
        step: PlanStep,
        context: TaskContext,
        state: AgentState,
    ) -> StepResult:
        """Execute a single plan step via the appropriate agent."""
        # Select agent
        agent = await self._agent_router.select_agent(step, context)
        state.active_agent = agent.name

        await self._emit("agent.agent_activated", {
            "task_id": state.task_id,
            "agent": agent.name,
            "step_id": step.step_id,
        })

        # Execute step through agent
        try:
            result = await agent.execute(step, context)
        except Exception as exc:
            result = StepResult(
                success=False,
                message=f"Agent '{agent.name}' failed: {exc}",
            )

        state.active_agent = None

        # Collect observations
        for obs in result.observations:
            obs.step_id = step.step_id
            state.observations.append(obs)

        # Verify if needed
        if result.needs_verification and result.success:
            verification = await self._verification_engine.verify(
                step, result, result.observations,
            )

            await self._emit("agent.verification_result", {
                "task_id": state.task_id,
                "step_id": step.step_id,
                "status": verification.status.value,
                "message": verification.message,
            })

            if verification.status == VerificationStatus.FAILED:
                result = StepResult(
                    success=False,
                    message=f"Verification failed: {verification.message}",
                    data=result.data,
                    observations=result.observations,
                )

        return result

    # ── Step lifecycle callbacks ───────────────────────────────────────────────

    async def _on_step_start(self, step: PlanStep, state: AgentState) -> None:
        """Called when a step starts execution."""
        state.add_timeline(
            state.active_agent or "runtime",
            f"Starting: {step.title}",
            step.description,
            step_id=step.step_id,
        )

        await self._emit("agent.step_started", {
            "task_id": state.task_id,
            "step": step.to_dict(),
            "progress": state.progress,
        })

    async def _on_step_complete(
        self, step: PlanStep, result: StepResult, state: AgentState
    ) -> None:
        """Called when a step completes successfully."""
        state.add_timeline(
            state.active_agent or "runtime",
            f"Completed: {step.title}",
            result.message,
            status="success",
            step_id=step.step_id,
        )

        await self._emit("agent.step_completed", {
            "task_id": state.task_id,
            "step_id": step.step_id,
            "result": result.to_dict(),
            "progress": state.progress,
        })

    async def _on_step_failed(
        self, step: PlanStep, exc: Exception, state: AgentState
    ) -> None:
        """Called when a step fails."""
        state.add_timeline(
            state.active_agent or "runtime",
            f"Failed: {step.title}",
            str(exc),
            status="error",
            step_id=step.step_id,
        )

        await self._emit("agent.step_failed", {
            "task_id": state.task_id,
            "step_id": step.step_id,
            "error": str(exc),
            "progress": state.progress,
        })

    # ── Task control ──────────────────────────────────────────────────────────

    async def pause_task(self, task_id: str) -> bool:
        """Pause a running task."""
        state = self._active_tasks.get(task_id)
        if not state or state.status != TaskStatus.RUNNING:
            return False

        graph = self._task_graphs.get(task_id)
        if graph:
            graph.pause()

        state.status = TaskStatus.PAUSED
        state.paused_at = _now_iso()
        state.add_timeline("runtime", "Task paused")

        await self._emit("agent.task_paused", {"task_id": task_id})
        return True

    async def resume_task(self, task_id: str) -> bool:
        """Resume a paused task."""
        state = self._active_tasks.get(task_id)
        if not state or state.status != TaskStatus.PAUSED:
            return False

        graph = self._task_graphs.get(task_id)
        if graph:
            graph.resume()

        state.status = TaskStatus.RUNNING
        state.paused_at = None
        state.add_timeline("runtime", "Task resumed")

        await self._emit("agent.task_resumed", {"task_id": task_id})
        return True

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running or paused task."""
        state = self._active_tasks.get(task_id)
        if not state or state.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            return False

        graph = self._task_graphs.get(task_id)
        if graph:
            graph.cancel()

        state.status = TaskStatus.CANCELLED
        state.completed_at = _now_iso()
        state.add_timeline("runtime", "Task cancelled")

        await self._emit("agent.task_cancelled", {"task_id": task_id})
        return True

    async def stop_all(self) -> int:
        """Global Kill Switch: immediately cancel all active tasks and tool executions."""
        cancelled_count = 0
        for task_id in list(self._active_tasks.keys()):
            state = self._active_tasks.get(task_id)
            if state and state.status in (TaskStatus.RUNNING, TaskStatus.PLANNING, TaskStatus.PAUSED, TaskStatus.VERIFYING):
                if await self.cancel_task(task_id):
                    cancelled_count += 1

        if hasattr(self._tool_executor, "cancel_all"):
            self._tool_executor.cancel_all()

        await self._emit("agent.kill_switch_activated", {
            "cancelled_tasks": cancelled_count,
            "timestamp": _now_iso(),
        })
        log.warning("global_kill_switch_activated", cancelled_count=cancelled_count)
        return cancelled_count

    # ── State queries ─────────────────────────────────────────────────────────

    def get_task_state(self, task_id: str) -> AgentState | None:
        """Get the current state of a task."""
        return self._active_tasks.get(task_id)

    def get_all_tasks(self) -> list[AgentState]:
        """Get all active tasks."""
        return list(self._active_tasks.values())

    def get_agent_info(self) -> list[dict[str, Any]]:
        """Get info about all registered agents."""
        return self._agent_router.get_agent_info()

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _build_task_result(self, state: AgentState) -> TaskResult:
        """Build the final TaskResult from the agent state."""
        plan = state.plan

        if state.status == TaskStatus.FAILED:
            success = False
            summary = f"Task failed: {state.error or 'Unknown error'}"
        elif state.status == TaskStatus.CANCELLED:
            success = False
            summary = "Task was cancelled"
        elif plan and plan.progress >= 1.0:
            success = True
            summary = f"Completed: {state.goal.objective}"
            state.status = TaskStatus.COMPLETED
        elif plan and plan.progress > 0:
            success = True
            summary = f"Partially completed ({plan.progress:.0%}): {state.goal.objective}"
            state.status = TaskStatus.COMPLETED
        else:
            success = False
            summary = "No steps were completed"
            state.status = TaskStatus.FAILED

        state.completed_at = _now_iso()

        result = TaskResult(
            task_id=state.task_id,
            goal_id=state.goal.goal_id,
            success=success,
            summary=summary,
            data=state.result,
            artifacts=[],
            timeline_summary=[t.to_dict() for t in state.timeline[-20:]],
            total_steps=len(plan.steps) if plan else 0,
            completed_steps=len(plan.completed_steps) if plan else 0,
            failed_steps=len(plan.failed_steps) if plan else 0,
            elapsed_seconds=state.elapsed_seconds,
        )

        state.result = result.to_dict()

        # Emit completion event
        await self._emit("agent.task_completed", {
            "task_id": state.task_id,
            "success": success,
            "summary": summary,
            "progress": state.progress,
            "elapsed_seconds": state.elapsed_seconds,
        })

        state.add_timeline(
            "runtime",
            "Task completed" if success else "Task finished with issues",
            summary,
            status="success" if success else "error",
        )

        return result
