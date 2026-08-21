"""Task Graph — DAG-based execution engine for plan steps.

The TaskGraph takes an ExecutionPlan and executes its steps as a
directed acyclic graph, respecting dependencies and enabling parallel
execution where steps are independent.

Key capabilities:
    - Dependency resolution (topological sort)
    - Parallel execution of independent steps
    - Step lifecycle management
    - Cancellation and timeout support
    - Dynamic step insertion (for recovery/replanning)
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any, Callable, Awaitable, Optional

import structlog

from .schemas import (
    ExecutionPlan,
    PlanStep,
    StepResult,
    StepStatus,
    TaskContext,
    _now_iso,
)

log = structlog.get_logger("genie.runtime.task_graph")

# Type for the step executor callback
StepExecutor = Callable[[PlanStep, TaskContext], Awaitable[StepResult]]


class TaskGraph:
    """DAG-based execution engine for plan steps.

    Given an ExecutionPlan, resolves dependencies and executes steps
    in the correct order, running independent steps in parallel where
    possible.
    """

    def __init__(self, plan: ExecutionPlan):
        self._plan = plan
        self._steps: dict[str, PlanStep] = {s.step_id: s for s in plan.steps}
        self._results: dict[str, StepResult] = {}
        self._cancelled = False
        self._paused = asyncio.Event()
        self._paused.set()  # not paused initially

        # Build adjacency data
        self._dependents: dict[str, list[str]] = defaultdict(list)  # step → steps that depend on it
        for step in plan.steps:
            for dep_id in step.depends_on:
                self._dependents[dep_id].append(step.step_id)

    @property
    def results(self) -> dict[str, StepResult]:
        """All step results collected so far."""
        return dict(self._results)

    @property
    def is_complete(self) -> bool:
        """True if all steps have reached a terminal status."""
        return all(
            s.status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED, StepStatus.CANCELLED)
            for s in self._steps.values()
        )

    @property
    def has_failures(self) -> bool:
        """True if any step has failed (and was not recovered)."""
        return any(s.status == StepStatus.FAILED for s in self._steps.values())

    def cancel(self) -> None:
        """Cancel all pending steps."""
        self._cancelled = True
        self._paused.set()  # unblock if paused
        for step in self._steps.values():
            if step.status in (StepStatus.PENDING, StepStatus.READY):
                step.status = StepStatus.CANCELLED

    def pause(self) -> None:
        """Pause execution (new steps won't start until resumed)."""
        self._paused.clear()

    def resume(self) -> None:
        """Resume paused execution."""
        self._paused.set()

    def get_ready_steps(self) -> list[PlanStep]:
        """Get steps whose dependencies are all satisfied."""
        ready = []
        for step in self._steps.values():
            if step.status != StepStatus.PENDING:
                continue
            if self._all_deps_satisfied(step):
                ready.append(step)
                step.status = StepStatus.READY
        return ready

    async def execute(
        self,
        executor: StepExecutor,
        task_context: TaskContext,
        on_step_start: Callable[[PlanStep], Awaitable[None]] | None = None,
        on_step_complete: Callable[[PlanStep, StepResult], Awaitable[None]] | None = None,
        on_step_failed: Callable[[PlanStep, Exception], Awaitable[None]] | None = None,
    ) -> dict[str, StepResult]:
        """Execute the task graph, respecting dependencies.

        Steps with satisfied dependencies are launched concurrently.
        The executor callback is responsible for actually running each step.

        Args:
            executor: Async function that executes a single step
            task_context: Shared context for all steps
            on_step_start: Optional callback when a step starts
            on_step_complete: Optional callback when a step completes
            on_step_failed: Optional callback when a step fails

        Returns:
            Dict mapping step_id → StepResult
        """
        while not self.is_complete and not self._cancelled:
            # Wait if paused
            await self._paused.wait()

            if self._cancelled:
                break

            ready_steps = self.get_ready_steps()

            if not ready_steps:
                # No steps ready — either all done or deadlocked
                running = [s for s in self._steps.values() if s.status == StepStatus.RUNNING]
                if running:
                    # Wait for running steps to complete
                    await asyncio.sleep(0.1)
                    continue
                else:
                    # Deadlock or all steps in terminal state
                    break

            # Execute ready steps concurrently
            tasks = []
            for step in ready_steps:
                if self._cancelled:
                    break
                task = asyncio.create_task(
                    self._execute_step(
                        step, executor, task_context,
                        on_step_start, on_step_complete, on_step_failed,
                    ),
                    name=f"step_{step.step_id}",
                )
                tasks.append(task)

            if tasks:
                # Wait for all concurrent steps to complete
                await asyncio.gather(*tasks, return_exceptions=True)

        return self._results

    async def _execute_step(
        self,
        step: PlanStep,
        executor: StepExecutor,
        task_context: TaskContext,
        on_step_start: Callable[[PlanStep], Awaitable[None]] | None,
        on_step_complete: Callable[[PlanStep, StepResult], Awaitable[None]] | None,
        on_step_failed: Callable[[PlanStep, Exception], Awaitable[None]] | None,
    ) -> None:
        """Execute a single step with timeout and error handling."""
        step.status = StepStatus.RUNNING
        step.started_at = _now_iso()

        if on_step_start:
            try:
                await on_step_start(step)
            except Exception:
                pass

        # Check condition if present
        if step.condition and not self._evaluate_condition(step.condition):
            step.status = StepStatus.SKIPPED
            step.completed_at = _now_iso()
            log.info("step_skipped_condition", step_id=step.step_id, condition=step.condition)
            return

        # Build step-specific context with previous results
        step_context = TaskContext(
            task_id=task_context.task_id,
            session_id=task_context.session_id,
            goal=task_context.goal,
            step=step,
            plan=task_context.plan,
            previous_results={
                sid: r.to_dict() for sid, r in self._results.items()
            },
            memory_context=task_context.memory_context,
            environment=task_context.environment,
            autonomy_level=task_context.autonomy_level,
        )

        try:
            result = await asyncio.wait_for(
                executor(step, step_context),
                timeout=step.timeout_seconds,
            )

            if result.success:
                step.status = StepStatus.COMPLETED
                step.result = result.data
                step.completed_at = _now_iso()
                self._results[step.step_id] = result
                log.info("step_completed", step_id=step.step_id, title=step.title)

                if on_step_complete:
                    try:
                        await on_step_complete(step, result)
                    except Exception:
                        pass
            else:
                raise RuntimeError(result.message)

        except asyncio.TimeoutError:
            step.status = StepStatus.FAILED
            step.error = f"Step timed out after {step.timeout_seconds}s"
            step.completed_at = _now_iso()
            log.warning("step_timeout", step_id=step.step_id, timeout=step.timeout_seconds)

            if on_step_failed:
                try:
                    await on_step_failed(step, TimeoutError(step.error))
                except Exception:
                    pass

        except asyncio.CancelledError:
            step.status = StepStatus.CANCELLED
            step.completed_at = _now_iso()

        except Exception as exc:
            step.status = StepStatus.FAILED
            step.error = str(exc)
            step.completed_at = _now_iso()
            log.warning("step_failed", step_id=step.step_id, error=str(exc))

            if on_step_failed:
                try:
                    await on_step_failed(step, exc)
                except Exception:
                    pass

    def _all_deps_satisfied(self, step: PlanStep) -> bool:
        """Check if all dependencies of a step are satisfied."""
        for dep_id in step.depends_on:
            dep_step = self._steps.get(dep_id)
            if dep_step is None:
                continue  # missing dep is treated as satisfied
            if dep_step.status not in (StepStatus.COMPLETED, StepStatus.SKIPPED):
                return False
        return True

    def _evaluate_condition(self, condition: str) -> bool:
        """Evaluate a step condition against current results.

        Simple conditions like "step_abc123.success == true" or
        "step_abc123.data.file_exists == true".
        """
        # For now, all conditions pass — proper expression evaluation
        # would parse the condition against self._results
        return True

    def add_step(self, step: PlanStep) -> None:
        """Dynamically add a step to the graph (e.g., during recovery)."""
        self._steps[step.step_id] = step
        self._plan.steps.append(step)
        for dep_id in step.depends_on:
            self._dependents[dep_id].append(step.step_id)

    def skip_step(self, step_id: str) -> None:
        """Mark a step as skipped."""
        step = self._steps.get(step_id)
        if step and step.status in (StepStatus.PENDING, StepStatus.READY):
            step.status = StepStatus.SKIPPED
            step.completed_at = _now_iso()

    def get_step(self, step_id: str) -> PlanStep | None:
        """Get a step by ID."""
        return self._steps.get(step_id)

    def get_execution_order(self) -> list[PlanStep]:
        """Return steps in topological order (for display)."""
        visited: set[str] = set()
        order: list[PlanStep] = []

        def visit(step_id: str) -> None:
            if step_id in visited:
                return
            visited.add(step_id)
            step = self._steps.get(step_id)
            if step is None:
                return
            for dep_id in step.depends_on:
                visit(dep_id)
            order.append(step)

        for step_id in self._steps:
            visit(step_id)

        return order
