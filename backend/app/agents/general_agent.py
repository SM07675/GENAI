"""General Agent — handles general reasoning, conversation, and catch-all tasks.

This is the default agent that handles anything not covered by specialized
agents: greetings, questions, explanations, summarization, general reasoning.
"""
from __future__ import annotations

from typing import Any

from .base_agent import BaseAgent
from ..runtime.schemas import PlanStep, StepResult, TaskContext, ModelRole


class GeneralAgent(BaseAgent):
    name = "general"
    description = "General reasoning, conversation, summarization, and catch-all tasks"
    capabilities = ["reasoning", "conversation", "summarization", "explanation", "general"]
    tools: list[str] = []

    async def execute(self, step: PlanStep, context: TaskContext) -> StepResult:
        """Execute a general reasoning/conversation step."""
        # Build context from previous results
        context_parts = []
        if context.goal.objective:
            context_parts.append(f"Goal: {context.goal.objective}")
        if context.previous_results:
            for sid, res in list(context.previous_results.items())[-5:]:
                msg = res.get("message", "")
                if msg:
                    context_parts.append(f"Previous step result: {msg[:500]}")

        system_prompt = (
            "You are Genie, an intelligent personal AI assistant. "
            "You are working on a task and need to complete this step. "
            "Be concise, accurate, and helpful."
        )

        user_prompt = f"Step: {step.title}\n"
        if step.description:
            user_prompt += f"Details: {step.description}\n"
        if context_parts:
            user_prompt += f"\nContext:\n" + "\n".join(context_parts)

        try:
            response = await self._call_llm(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                role=ModelRole.FAST,
                max_tokens=2000,
            )

            return StepResult(
                success=True,
                message=response[:500],
                data={"response": response},
                observations=[
                    self._make_observation(
                        "llm", f"General agent response: {response[:200]}...",
                        step_id=step.step_id,
                    )
                ],
                needs_verification=False,
            )
        except Exception as exc:
            return StepResult(
                success=False,
                message=f"General agent failed: {exc}",
            )

    async def can_handle(self, step: PlanStep) -> float:
        """General agent always returns a baseline confidence."""
        base = await super().can_handle(step)
        return max(base, 0.1)  # always a fallback option
