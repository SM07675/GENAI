"""Agent Router — routes plan steps to the appropriate specialized agent.

Given a PlanStep, the router selects the best agent to handle it based on:
    1. The step's declared agent name (if specified)
    2. The step's required capabilities
    3. Each agent's confidence score for the step
    4. Agent availability and current load
"""
from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

import structlog

from .schemas import PlanStep, TaskContext

if TYPE_CHECKING:
    from ..agents.base_agent import BaseAgent

log = structlog.get_logger("genie.runtime.agent_router")


class AgentRouter:
    """Routes plan steps to specialized agents.

    Agents register themselves with the router at startup. When a step
    needs to be executed, the router selects the best agent based on
    the step's requirements and each agent's capabilities.
    """

    def __init__(self):
        self._agents: dict[str, "BaseAgent"] = {}

    def register(self, agent: "BaseAgent") -> None:
        """Register an agent with the router."""
        self._agents[agent.name] = agent
        log.info("agent_registered", name=agent.name, capabilities=agent.capabilities)

    def unregister(self, name: str) -> None:
        """Remove an agent from the router."""
        self._agents.pop(name, None)

    def get_agent(self, name: str) -> Optional["BaseAgent"]:
        """Get an agent by name."""
        return self._agents.get(name)

    @property
    def available_agents(self) -> dict[str, "BaseAgent"]:
        """All registered agents."""
        return dict(self._agents)

    async def select_agent(
        self,
        step: PlanStep,
        context: TaskContext,
    ) -> "BaseAgent":
        """Select the best agent for a given step.

        Selection priority:
            1. Exact agent name match (if step specifies one)
            2. Highest confidence score from can_handle()
            3. Fallback to general agent

        Raises:
            ValueError: If no suitable agent is found
        """
        # 1. Try exact name match
        if step.agent and step.agent in self._agents:
            agent = self._agents[step.agent]
            log.debug("agent_selected_by_name", agent=step.agent, step=step.title)
            return agent

        # 2. Ask all agents for confidence scores
        candidates: list[tuple[float, "BaseAgent"]] = []
        for agent in self._agents.values():
            try:
                confidence = await agent.can_handle(step)
                if confidence > 0:
                    candidates.append((confidence, agent))
            except Exception as exc:
                log.warning(
                    "agent_can_handle_error",
                    agent=agent.name,
                    error=str(exc),
                )

        if candidates:
            # Sort by confidence, pick highest
            candidates.sort(key=lambda c: c[0], reverse=True)
            best_confidence, best_agent = candidates[0]
            log.debug(
                "agent_selected_by_confidence",
                agent=best_agent.name,
                confidence=best_confidence,
                step=step.title,
            )
            return best_agent

        # 3. Fallback to general agent
        general = self._agents.get("general")
        if general:
            log.debug("agent_fallback_to_general", step=step.title)
            return general

        raise ValueError(
            f"No suitable agent found for step '{step.title}' "
            f"(requested agent: '{step.agent}')"
        )

    def get_agent_info(self) -> list[dict[str, Any]]:
        """Get info about all registered agents for the frontend."""
        return [
            {
                "name": agent.name,
                "description": agent.description,
                "capabilities": agent.capabilities,
                "tools": agent.tools,
            }
            for agent in self._agents.values()
        ]
