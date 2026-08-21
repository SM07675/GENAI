"""Goal Engine — extracts structured goals from user input.

The Goal Engine is the first stage of the agentic pipeline. It takes raw
user input (text, voice transcript, or structured command) and produces a
typed Goal object that the Planner can work with.

Key responsibilities:
    1. Classify whether input is a simple chat query or a complex goal
    2. Extract objective, constraints, expected outcome
    3. Identify required capabilities (which agents/tools are needed)
    4. Attach relevant context from the environment
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import structlog

from .schemas import Goal, ModelRole

log = structlog.get_logger("genie.runtime.goal_engine")

# ── Goal classification prompt ────────────────────────────────────────────────

_CLASSIFICATION_PROMPT = """\
You are a goal classifier for an AI assistant called Genie. Given the user's input and current context, determine whether this is:

1. A SIMPLE request (greeting, question, quick lookup, casual chat, single-step action) — respond with is_simple=true
2. A COMPLEX goal (multi-step task, research, file operations, automation, anything requiring planning) — respond with is_simple=false

For COMPLEX goals, also extract:
- objective: A clear statement of what the user wants to accomplish
- constraints: Any limitations or requirements mentioned
- expected_outcome: What the final deliverable should be
- required_capabilities: Which types of capabilities are needed (research, file_ops, coding, browser, system, media, data_analysis, document, productivity)

Respond in JSON format:
{
    "is_simple": true/false,
    "objective": "...",
    "constraints": ["..."],
    "expected_outcome": "...",
    "required_capabilities": ["..."]
}
"""


class GoalEngine:
    """Extracts structured goals from user input using LLM classification."""

    def __init__(self, model_router: Any = None):
        self._model_router = model_router

    async def extract_goal(
        self,
        user_input: str,
        context_summary: str = "",
        session_id: str = "",
    ) -> Goal:
        """Extract a structured Goal from raw user input.

        For simple queries (greetings, questions), returns a Goal with
        is_simple=True so the runtime can fast-path to direct LLM response.

        For complex goals, uses LLM to extract objective, constraints,
        expected outcome, and required capabilities.
        """
        # Fast-path: very short inputs are almost always simple
        stripped = user_input.strip()
        if len(stripped) < 15 and not any(kw in stripped.lower() for kw in [
            "find", "create", "make", "build", "prepare", "research",
            "analyze", "download", "debug", "fix", "open", "search",
            "compare", "generate", "train", "deploy", "install",
        ]):
            return Goal(
                objective=stripped,
                raw_input=user_input,
                context_summary=context_summary,
                is_simple=True,
            )

        # Use LLM to classify and extract goal structure
        try:
            result = await self._classify_with_llm(user_input, context_summary)
            return Goal(
                objective=result.get("objective", stripped),
                constraints=result.get("constraints", []),
                expected_outcome=result.get("expected_outcome", ""),
                required_capabilities=result.get("required_capabilities", []),
                raw_input=user_input,
                context_summary=context_summary,
                is_simple=result.get("is_simple", False),
            )
        except Exception as exc:
            log.warning("goal_extraction_failed", error=str(exc))
            # Fallback: treat as potentially complex, let planner decide
            return Goal(
                objective=stripped,
                raw_input=user_input,
                context_summary=context_summary,
                is_simple=self._heuristic_is_simple(stripped),
            )

    async def _classify_with_llm(
        self, user_input: str, context_summary: str
    ) -> dict[str, Any]:
        """Use the model router to classify the input."""
        if self._model_router is None:
            return {"is_simple": self._heuristic_is_simple(user_input)}

        messages = [
            {"role": "system", "content": _CLASSIFICATION_PROMPT},
            {"role": "user", "content": f"Context: {context_summary}\n\nUser input: {user_input}"},
        ]

        response = await self._model_router.generate(
            messages=messages,
            role=ModelRole.FAST,
            response_format="json",
            max_tokens=500,
            temperature=0.1,
        )

        try:
            return json.loads(response)
        except (json.JSONDecodeError, TypeError):
            # Try to extract JSON from the response
            text = str(response)
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            raise ValueError(f"Could not parse goal classification response: {text[:200]}")

    @staticmethod
    def _heuristic_is_simple(text: str) -> bool:
        """Quick heuristic for simple vs complex classification.

        Used as fallback when LLM classification is unavailable.
        """
        lower = text.lower()

        # Multi-step indicators
        complex_indicators = [
            " and then ", " after that ", " next ", " finally ",
            "step by step", "prepare", "research", "analyze",
            "download and", "create a report", "make a presentation",
            "find and ", "compare", "train a model", "debug",
            "build", "deploy", "install", "set up", "configure",
            "organize", "clean up", "migrate", "refactor",
        ]
        if any(ind in lower for ind in complex_indicators):
            return False

        # Question patterns are usually simple
        if lower.startswith(("what", "who", "when", "where", "why", "how",
                             "is ", "are ", "can ", "do ", "does ", "did ",
                             "will ", "would ", "could ", "should ")):
            return True

        # Greetings / social
        if lower.startswith(("hi", "hello", "hey", "good ", "thanks", "thank")):
            return True

        # Single action commands
        if lower.startswith(("play ", "open ", "close ", "set ", "show ",
                             "tell ", "what's ", "what is ")):
            return True

        # Default: complex if longer than ~40 chars
        return len(text) < 40
