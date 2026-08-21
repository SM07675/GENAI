"""Browser Agent — web navigation, interaction, data extraction."""
from __future__ import annotations
from .base_agent import BaseAgent
from ..runtime.schemas import Observation, PlanStep, StepResult, TaskContext, ModelRole


class BrowserAgent(BaseAgent):
    name = "browser"
    description = "Browser navigation, web interaction, data extraction"
    capabilities = [
        "browser_navigate", "browser_click", "browser_type",
        "browser_extract", "web_scrape", "url_open",
    ]
    tools = ["open_url", "open_whatsapp_chat"]

    async def execute(self, step: PlanStep, context: TaskContext) -> StepResult:
        observations: list[Observation] = []
        desc = (step.description or step.title).lower()

        # URL opening
        if any(w in desc for w in ["open", "navigate", "go to", "visit"]):
            import re
            url_match = re.search(r'https?://[^\s"\'<>]+', step.description or step.title)
            if url_match:
                result, obs = await self._execute_tool(
                    "open_url", {"url": url_match.group()}, context,
                )
                observations.append(obs)
                return StepResult(
                    success=result.status in ("ok", "success"),
                    message=result.message,
                    data={"url": url_match.group()},
                    observations=observations,
                )

        # Default: describe what browser action is needed
        response = await self._call_llm(
            [{"role": "system", "content": "You are a browser automation assistant."},
             {"role": "user", "content": f"Task: {step.title}\nDetails: {step.description}"}],
            role=ModelRole.FAST,
        )
        return StepResult(
            success=True,
            message=response[:500],
            data={"response": response},
            observations=observations,
            needs_verification=False,
        )
