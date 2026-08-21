"""Research Agent — web research, source discovery, comparison, summarization.

Uses search tools to find information, compare sources, extract facts,
and produce summarized research results.
"""
from __future__ import annotations

import json
from typing import Any

from .base_agent import BaseAgent
from ..runtime.schemas import Observation, PlanStep, StepResult, TaskContext, ModelRole


class ResearchAgent(BaseAgent):
    name = "research"
    description = "Web research, source discovery, comparison, fact extraction, summarization"
    capabilities = [
        "web_search", "research", "summarization", "fact_extraction",
        "source_comparison", "news", "information_gathering",
    ]
    tools = ["search_web", "get_news", "get_news_briefing", "get_api_status"]

    async def execute(self, step: PlanStep, context: TaskContext) -> StepResult:
        """Execute a research step — search, analyze, summarize."""
        observations: list[Observation] = []
        collected_data: dict[str, Any] = {}

        # Determine search query from step description or goal
        query = step.description or step.title or context.goal.objective

        # Step 1: Search the web
        try:
            search_result, search_obs = await self._execute_tool(
                "search_web", {"query": query}, context,
            )
            observations.append(search_obs)

            if search_result.status == "ok" and search_result.data:
                collected_data["search_results"] = search_result.data
            elif search_result.status == "not_found":
                # Try alternative search
                alt_query = f"{context.goal.objective} overview"
                search_result, search_obs = await self._execute_tool(
                    "search_web", {"query": alt_query}, context,
                )
                observations.append(search_obs)
                if search_result.data:
                    collected_data["search_results"] = search_result.data
        except Exception as exc:
            observations.append(self._make_observation(
                "research", f"Search failed: {exc}", step_id=step.step_id,
            ))

        # Step 2: Summarize findings using LLM
        summary = ""
        if collected_data:
            try:
                search_context = json.dumps(collected_data, default=str, ensure_ascii=False)[:6000]
                summary = await self._call_llm(
                    messages=[
                        {"role": "system", "content": (
                            "You are a research assistant. Summarize the search results "
                            "into a clear, well-structured answer. Include key facts, "
                            "sources, and relevant details. Be thorough but concise."
                        )},
                        {"role": "user", "content": (
                            f"Research query: {query}\n\n"
                            f"Search results:\n{search_context}\n\n"
                            f"Provide a comprehensive summary."
                        )},
                    ],
                    role=ModelRole.FAST,
                    max_tokens=3000,
                )
                collected_data["summary"] = summary
            except Exception as exc:
                observations.append(self._make_observation(
                    "research", f"Summarization failed: {exc}", step_id=step.step_id,
                ))

        success = bool(summary or collected_data.get("search_results"))

        return StepResult(
            success=success,
            message=summary[:500] if summary else "Research completed with data collected",
            data=collected_data,
            observations=observations,
            needs_verification=False,
        )
