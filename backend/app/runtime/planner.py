"""Autonomous Planner — generates execution plans from goals.

The Planner takes a Goal and produces an ExecutionPlan containing ordered
steps with dependencies. It uses the LLM to reason about what agents and
tools are needed, and in what order.

Key capabilities:
    - Sequential, parallel, and dependent task planning
    - Retry and fallback path generation
    - Replanning from partial progress after failures
    - Awareness of available agents and tools
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import structlog

from .schemas import (
    ExecutionPlan,
    FailedStep,
    Goal,
    ModelRole,
    PlanStep,
    RetryPolicy,
    StepStatus,
)

log = structlog.get_logger("genie.runtime.planner")

# ── Available agents (registered at startup, but default set here) ────────────

DEFAULT_AGENTS = {
    "general": {
        "description": "General reasoning, conversation, and catch-all tasks",
        "capabilities": ["reasoning", "conversation", "summarization"],
    },
    "research": {
        "description": "Web research, source discovery, comparison, summarization",
        "capabilities": ["web_search", "summarization", "fact_extraction"],
        "tools": ["search_web", "get_news", "get_news_briefing"],
    },
    "file": {
        "description": "File search, read, create, modify, organize",
        "capabilities": ["file_read", "file_write", "file_search"],
    },
    "coding": {
        "description": "Code reading, writing, debugging, testing",
        "capabilities": ["code_read", "code_write", "code_debug", "code_test"],
    },
    "system": {
        "description": "System operations: volume, apps, windows, screenshots",
        "capabilities": ["app_launch", "app_close", "volume", "screenshot", "system_control"],
        "tools": ["open_app", "close_app", "set_volume", "capture_screen"],
    },
    "media": {
        "description": "Music and video playback, media discovery",
        "capabilities": ["music_play", "video_play", "media_search"],
        "tools": ["play_youtube", "play_youtube_music", "search_youtube_music"],
    },
    "browser": {
        "description": "Browser navigation, interaction, data extraction",
        "capabilities": ["browser_navigate", "browser_click", "browser_type", "browser_extract"],
        "tools": ["open_url"],
    },
    "data": {
        "description": "Data analysis, visualization, Python execution",
        "capabilities": ["data_analysis", "visualization", "python_exec"],
    },
    "document": {
        "description": "PDF, DOCX, PPTX, spreadsheet processing",
        "capabilities": ["doc_read", "doc_write", "doc_convert"],
    },
    "productivity": {
        "description": "Tasks, reminders, notes, calendar",
        "capabilities": ["task_manage", "reminder", "note"],
        "tools": ["manage_note", "set_reminder"],
    },
}

# ── Planning prompt ───────────────────────────────────────────────────────────

_PLANNING_PROMPT = """\
You are a planning engine for an AI assistant called Genie. Given a user's goal, create a structured execution plan.

## Available Agents
{agents_description}

## Rules
1. Break the goal into concrete, executable steps
2. Each step must specify which agent should handle it
3. Steps can depend on other steps (via depends_on)
4. Steps in the same parallel_group can run concurrently
5. Include verification steps where important (e.g., after file creation, downloads)
6. Keep the plan minimal — don't add unnecessary steps
7. For simple single-step tasks, create a plan with just 1-2 steps
8. Estimate total time in seconds

## Response Format (JSON)
{{
    "task_type": "research|coding|file_ops|system|media|data|document|productivity|general",
    "steps": [
        {{
            "title": "Short step title",
            "description": "What to do in detail",
            "agent": "agent_name",
            "tool_names": ["specific_tools_if_known"],
            "depends_on": ["step_ids_this_depends_on"],
            "parallel_group": "group_name_for_concurrent_steps_or_null",
            "timeout_seconds": 60
        }}
    ],
    "expected_failures": ["possible failure scenarios"],
    "estimated_seconds": 30
}}
"""


class Planner:
    """Generates execution plans from goals using LLM reasoning."""

    def __init__(self, model_router: Any = None, agents: dict[str, Any] | None = None):
        self._model_router = model_router
        self._agents = agents or DEFAULT_AGENTS

    async def create_plan(
        self,
        goal: Goal,
        context_summary: str = "",
    ) -> ExecutionPlan:
        """Generate an execution plan for a goal.

        Uses LLM to reason about what steps are needed, which agents
        should handle them, and in what order.
        """
        # For simple goals, create a minimal plan
        if goal.is_simple:
            return self._create_simple_plan(goal)

        try:
            return await self._create_llm_plan(goal, context_summary)
        except Exception as exc:
            log.warning("llm_planning_failed", error=str(exc), goal=goal.objective)
            return self._create_fallback_plan(goal)

    async def replan(
        self,
        goal: Goal,
        completed_steps: list[PlanStep],
        failed_step: FailedStep,
        context_summary: str = "",
    ) -> ExecutionPlan:
        """Re-plan from current state after a failure.

        Considers what has already been completed and what failed,
        then generates a new plan for the remaining work.
        """
        try:
            return await self._create_replan(goal, completed_steps, failed_step, context_summary)
        except Exception as exc:
            log.warning("replanning_failed", error=str(exc))
            return self._create_fallback_plan(goal)

    # ── Internal planning methods ─────────────────────────────────────────────

    async def _create_llm_plan(
        self, goal: Goal, context_summary: str
    ) -> ExecutionPlan:
        """Use LLM to generate a structured plan."""
        if self._model_router is None:
            return self._create_fallback_plan(goal)

        agents_desc = self._format_agents_description()
        system_prompt = _PLANNING_PROMPT.format(agents_description=agents_desc)

        user_content = f"Goal: {goal.objective}"
        if goal.constraints:
            user_content += f"\nConstraints: {', '.join(goal.constraints)}"
        if goal.expected_outcome:
            user_content += f"\nExpected outcome: {goal.expected_outcome}"
        if goal.required_capabilities:
            user_content += f"\nRequired capabilities: {', '.join(goal.required_capabilities)}"
        if context_summary:
            user_content += f"\nCurrent context: {context_summary}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        response = await self._model_router.generate(
            messages=messages,
            role=ModelRole.REASONING,
            response_format="json",
            max_tokens=2000,
            temperature=0.2,
        )

        plan_data = self._parse_plan_response(response)
        return self._build_plan_from_data(goal, plan_data)

    async def _create_replan(
        self,
        goal: Goal,
        completed_steps: list[PlanStep],
        failed_step: FailedStep,
        context_summary: str,
    ) -> ExecutionPlan:
        """Use LLM to generate a revised plan after failure."""
        if self._model_router is None:
            return self._create_fallback_plan(goal)

        completed_summary = "\n".join(
            f"- ✓ {s.title} (agent: {s.agent})" for s in completed_steps
        )
        failure_summary = (
            f"Step '{failed_step.step.title}' failed: {failed_step.error_message} "
            f"(category: {failed_step.category.value})"
        )

        agents_desc = self._format_agents_description()
        system_prompt = _PLANNING_PROMPT.format(agents_description=agents_desc)

        user_content = (
            f"Goal: {goal.objective}\n\n"
            f"Completed steps:\n{completed_summary}\n\n"
            f"Failure: {failure_summary}\n\n"
            f"Create a revised plan to complete the REMAINING work, "
            f"working around the failure. Do NOT repeat completed steps."
        )
        if context_summary:
            user_content += f"\nCurrent context: {context_summary}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        response = await self._model_router.generate(
            messages=messages,
            role=ModelRole.REASONING,
            response_format="json",
            max_tokens=2000,
            temperature=0.2,
        )

        plan_data = self._parse_plan_response(response)
        plan = self._build_plan_from_data(goal, plan_data)
        plan.version += 1
        return plan

    # ── Plan construction helpers ─────────────────────────────────────────────

    def _create_simple_plan(self, goal: Goal) -> ExecutionPlan:
        """Create a minimal 1-step plan for simple queries."""
        return ExecutionPlan(
            objective=goal.objective,
            task_type="general",
            steps=[
                PlanStep(
                    title="Respond to user",
                    description=f"Answer or respond to: {goal.objective}",
                    agent="general",
                    timeout_seconds=30.0,
                ),
            ],
            estimated_seconds=5,
        )

    def _create_fallback_plan(self, goal: Goal) -> ExecutionPlan:
        """Create a conservative fallback plan when LLM planning fails."""
        steps = [
            PlanStep(
                title="Understand request",
                description=f"Analyze and understand: {goal.objective}",
                agent="general",
                timeout_seconds=30.0,
            ),
        ]

        # Add capability-specific steps
        caps = goal.required_capabilities or []
        if "research" in caps or "web_search" in caps:
            steps.append(PlanStep(
                title="Research",
                description="Search for relevant information",
                agent="research",
                tool_names=["search_web"],
                depends_on=[steps[-1].step_id],
                timeout_seconds=60.0,
            ))
        if any(c in caps for c in ["file_read", "file_write", "file_search"]):
            steps.append(PlanStep(
                title="File operations",
                description="Handle file-related tasks",
                agent="file",
                depends_on=[steps[-1].step_id],
                timeout_seconds=60.0,
            ))
        if any(c in caps for c in ["code_read", "code_write", "code_debug"]):
            steps.append(PlanStep(
                title="Code task",
                description="Handle code-related tasks",
                agent="coding",
                depends_on=[steps[-1].step_id],
                timeout_seconds=120.0,
            ))

        # Always end with a response step
        steps.append(PlanStep(
            title="Generate result",
            description="Compile and present the final result to the user",
            agent="general",
            depends_on=[steps[-1].step_id],
            timeout_seconds=30.0,
        ))

        return ExecutionPlan(
            objective=goal.objective,
            task_type="general",
            steps=steps,
            expected_failures=["tool unavailable", "network error"],
            estimated_seconds=len(steps) * 15,
        )

    def _build_plan_from_data(
        self, goal: Goal, plan_data: dict[str, Any]
    ) -> ExecutionPlan:
        """Build an ExecutionPlan from parsed LLM response data."""
        steps: list[PlanStep] = []
        step_id_map: dict[int, str] = {}  # index → step_id

        for i, step_data in enumerate(plan_data.get("steps", [])):
            step = PlanStep(
                title=step_data.get("title", f"Step {i + 1}"),
                description=step_data.get("description", ""),
                agent=step_data.get("agent", "general"),
                tool_names=step_data.get("tool_names", []),
                parallel_group=step_data.get("parallel_group"),
                timeout_seconds=step_data.get("timeout_seconds", 60.0),
            )
            step_id_map[i] = step.step_id

            # Resolve depends_on (LLM may return step indices or step_ids)
            raw_deps = step_data.get("depends_on", [])
            resolved_deps = []
            for dep in raw_deps:
                if isinstance(dep, int) and dep in step_id_map:
                    resolved_deps.append(step_id_map[dep])
                elif isinstance(dep, str) and dep.startswith("step_"):
                    resolved_deps.append(dep)
                elif isinstance(dep, str):
                    # Try to find by title
                    for s in steps:
                        if s.title.lower() == dep.lower():
                            resolved_deps.append(s.step_id)
                            break
            step.depends_on = resolved_deps

            # Validate agent name
            if step.agent not in self._agents:
                log.warning("unknown_agent_in_plan", agent=step.agent, step=step.title)
                step.agent = "general"

            steps.append(step)

        return ExecutionPlan(
            objective=goal.objective,
            task_type=plan_data.get("task_type", "general"),
            steps=steps,
            expected_failures=plan_data.get("expected_failures", []),
            estimated_seconds=plan_data.get("estimated_seconds"),
        )

    def _parse_plan_response(self, response: Any) -> dict[str, Any]:
        """Parse the LLM response into plan data."""
        text = str(response)
        # Try to extract JSON
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise ValueError(f"Could not parse plan response: {text[:300]}")

    def _format_agents_description(self) -> str:
        """Format agent descriptions for the planning prompt."""
        lines = []
        for name, info in self._agents.items():
            desc = info.get("description", "")
            caps = info.get("capabilities", [])
            tools = info.get("tools", [])
            line = f"- **{name}**: {desc}"
            if caps:
                line += f" (capabilities: {', '.join(caps)})"
            if tools:
                line += f" (tools: {', '.join(tools)})"
            lines.append(line)
        return "\n".join(lines)
