"""Base Agent — abstract base class for all Genie agents.

Every specialized agent inherits from BaseAgent and implements:
    - execute(): Run a plan step
    - can_handle(): Report confidence for handling a step
"""
from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Optional

import structlog

from ..runtime.schemas import (
    Observation,
    PlanStep,
    StepResult,
    TaskContext,
    ModelRole,
)

log = structlog.get_logger("genie.agents.base")


class BaseAgent(ABC):
    """Abstract base class for all Genie specialized agents.

    Subclasses must implement:
        - name: str — unique agent name
        - description: str — human-readable description
        - capabilities: list[str] — what this agent can do
        - tools: list[str] — tool names this agent uses
        - execute() — run a plan step
        - can_handle() — report confidence for a step
    """

    name: str = "base"
    description: str = "Base agent"
    capabilities: list[str] = []
    tools: list[str] = []

    def __init__(self, model_router: Any = None):
        self._model_router = model_router
        self._log = structlog.get_logger(f"genie.agents.{self.name}")

    @abstractmethod
    async def execute(self, step: PlanStep, context: TaskContext) -> StepResult:
        """Execute a plan step.

        Args:
            step: The plan step to execute
            context: Full task context including goal, plan, previous results

        Returns:
            StepResult with success/failure status, data, and observations
        """
        ...

    async def can_handle(self, step: PlanStep) -> float:
        """Report confidence (0.0-1.0) for handling a step.

        Higher confidence means this agent is better suited for the step.
        Default implementation checks tool and capability overlap.
        """
        score = 0.0

        # Check if any of the step's tools match this agent's tools
        if step.tool_names:
            matching_tools = set(step.tool_names) & set(self.tools)
            if matching_tools:
                score += 0.5 * (len(matching_tools) / len(step.tool_names))

        # Check agent name match
        if step.agent == self.name:
            score += 0.5

        # Check description/title keyword overlap
        step_words = set(step.title.lower().split() + step.description.lower().split())
        cap_words = set()
        for cap in self.capabilities:
            cap_words.update(cap.lower().replace("_", " ").split())
        overlap = step_words & cap_words
        if overlap:
            score += 0.3 * min(len(overlap) / max(len(step_words), 1), 1.0)

        return min(score, 1.0)

    # ── Helper methods for subclasses ─────────────────────────────────────────

    async def _call_llm(
        self,
        messages: list[dict[str, str]],
        role: ModelRole = ModelRole.FAST,
        max_tokens: int = 2000,
        temperature: float = 0.3,
        response_format: str | None = None,
    ) -> str:
        """Call the LLM through the model router.

        Convenience method for agents that need LLM reasoning.
        """
        if self._model_router is None:
            # Fallback: use the global LLM client
            return await self._call_llm_fallback(messages, max_tokens, temperature)

        response = await self._model_router.generate(
            messages=messages,
            role=role,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format,
        )
        return str(response)

    async def _call_llm_fallback(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.3,
    ) -> str:
        """Fallback LLM call using the existing llm_client."""
        try:
            from ..llm_client import get_provider_config, stream_chat
            from ..config import get_settings

            settings = get_settings()
            provider = get_provider_config(settings)

            # Collect full response from streaming
            full_text = ""
            async for event in stream_chat(
                messages=messages,
                tools=None,
                settings=settings,
            ):
                if event.get("type") == "text_delta":
                    full_text += event.get("delta", "")

            return full_text
        except Exception as exc:
            self._log.warning("llm_fallback_failed", error=str(exc))
            return f"[Agent {self.name}: LLM unavailable — {exc}]"

    async def _execute_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: TaskContext,
    ) -> tuple[Any, Observation]:
        """Execute a tool and return its result + observation.

        Convenience method that wraps direct tool execution.
        """
        try:
            from ..tools import execute_tool

            result = await asyncio.to_thread(execute_tool, tool_name, args)

            observation = Observation(
                source=f"tool:{tool_name}",
                content=f"Tool '{tool_name}': {result.status} — {result.message}",
                raw_data={
                    "status": result.status,
                    "message": result.message,
                    "data": result.data if result.data else {},
                },
                step_id=context.step.step_id if context.step else None,
            )

            return result, observation

        except Exception as exc:
            observation = Observation(
                source=f"tool:{tool_name}",
                content=f"Tool '{tool_name}' failed: {exc}",
                step_id=context.step.step_id if context.step else None,
            )
            from ..schemas import ToolResult
            return ToolResult(status="error", message=str(exc)), observation

    def _make_observation(
        self,
        source: str,
        content: str,
        data: dict[str, Any] | None = None,
        step_id: str | None = None,
    ) -> Observation:
        """Create an observation."""
        return Observation(
            source=source,
            content=content,
            raw_data=data or {},
            step_id=step_id,
        )
