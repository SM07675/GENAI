# Adding Specialized Agents to Genie

Specialized agents in Genie inherit from `BaseAgent` (`backend/app/agents/base_agent.py`) and are registered with the `AgentRouter`.

## Step 1: Create the Agent Class

Create `backend/app/agents/my_custom_agent.py`:

```python
from __future__ import annotations
from typing import Any
from .base_agent import BaseAgent
from ..runtime.schemas import Observation, PlanStep, StepResult, TaskContext, ModelRole

class MyCustomAgent(BaseAgent):
    name = "my_custom"
    description = "Handles custom workflow tasks"
    capabilities = ["custom_analysis", "custom_processing"]
    tools = ["custom_tool_name"]

    async def execute(self, step: PlanStep, context: TaskContext) -> StepResult:
        # 1. Execute required tools
        tool_result, obs = await self._execute_tool("custom_tool_name", {"arg": 123}, context)
        
        # 2. Perform optional LLM reasoning
        response = await self._call_llm(
            messages=[
                {"role": "system", "content": "You are a custom specialist."},
                {"role": "user", "content": f"Task: {step.title}"}
            ],
            role=ModelRole.FAST,
        )

        return StepResult(
            success=True,
            message="Custom step completed successfully",
            data={"analysis": response},
            observations=[obs],
            needs_verification=True,
        )

    async def can_handle(self, step: PlanStep) -> float:
        """Return confidence score from 0.0 to 1.0."""
        if "custom" in step.title.lower():
            return 0.95
        return await super().can_handle(step)
```

## Step 2: Register in `backend/app/agents/__init__.py`

Add your agent to `get_all_agents()`:

```python
from .my_custom_agent import MyCustomAgent

def get_all_agents() -> list[BaseAgent]:
    return [
        ...,
        MyCustomAgent(),
    ]
```

Genie will automatically discover and route relevant plan steps to your new agent!
