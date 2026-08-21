"""Unit tests for Genie OS Specialist Agents (Phase 7).

Verifies that all 10 specialist agents correctly handle their declared capabilities:
- can_handle confidence scoring
- step execution logic and observation collection
- tool delegation
"""
import pytest
from app.agents import (
    GeneralAgent,
    ResearchAgent,
    FileAgent,
    CodingAgent,
    SystemAgent,
    BrowserAgent,
    MediaAgent,
    DataAgent,
    DocumentAgent,
    ProductivityAgent,
)
from app.runtime.schemas import Goal, PlanStep, TaskContext, ExecutionPlan


@pytest.fixture
def base_context():
    goal = Goal(goal_id="g1", raw_input="Do work", objective="Do work")
    step = PlanStep(title="Sample step", description="Sample step description")
    plan = ExecutionPlan(objective="Do work", steps=[step])
    return TaskContext(
        task_id="t1",
        session_id="s1",
        goal=goal,
        step=step,
        plan=plan,
    )


@pytest.mark.asyncio
async def test_agent_can_handle_confidence():
    agents = [
        (ResearchAgent(), PlanStep(title="Search latest AI news", description="search web for AI")),
        (CodingAgent(), PlanStep(title="Debug python syntax error", description="fix bug in script")),
        (FileAgent(), PlanStep(title="Read config.json file", description="read file")),
        (SystemAgent(), PlanStep(title="Set speaker volume to 50", description="set volume")),
        (BrowserAgent(), PlanStep(title="Open URL in browser", description="open web page")),
        (MediaAgent(), PlanStep(title="Play music playlist on YouTube", description="play music")),
        (DataAgent(), PlanStep(title="Analyze data with Python", description="plot chart")),
        (DocumentAgent(), PlanStep(title="Extract text from PDF document", description="read pdf")),
        (ProductivityAgent(), PlanStep(title="Set reminder for meeting", description="create task")),
        (GeneralAgent(), PlanStep(title="Summarize general thoughts", description="general question")),
    ]

    for agent, step in agents:
        confidence = await agent.can_handle(step)
        assert confidence > 0.0, f"Agent {agent.name} had zero confidence for step {step.title}"


@pytest.mark.asyncio
async def test_general_agent_execution(base_context, monkeypatch):
    agent = GeneralAgent()
    async def mock_call_llm(*args, **kwargs):
        return "All systems nominal and ready."
    monkeypatch.setattr(agent, "_call_llm", mock_call_llm)

    step = PlanStep(title="Status check", description="Report current status")
    res = await agent.execute(step, base_context)
    assert res.success is True
    assert res.message != ""


@pytest.mark.asyncio
async def test_file_agent_execution(base_context, tmp_path):
    agent = FileAgent()
    test_file = tmp_path / "hello.txt"
    test_file.write_text("Hello from Genie OS", encoding="utf-8")

    step = PlanStep(title="Read file", description=f"read {test_file}")
    res = await agent.execute(step, base_context)
    assert res.success is True
    assert "Hello from Genie OS" in str(res.data)


@pytest.mark.asyncio
async def test_system_agent_execution(base_context):
    agent = SystemAgent()
    step = PlanStep(title="Get system info", description="get system info")
    res = await agent.execute(step, base_context)
    assert res.success is True
    assert "system_info" in res.data


@pytest.mark.asyncio
async def test_research_agent_execution(base_context, monkeypatch):
    agent = ResearchAgent()

    async def mock_execute_tool(name, args, ctx):
        from app.schemas import ToolResult
        from app.runtime.schemas import Observation
        res = ToolResult(status="ok", message="Search results found", data={"results": ["Quantum computing uses qubits"]})
        obs = Observation(source="search", content="Search returned 1 result")
        return res, obs

    async def mock_call_llm(*args, **kwargs):
        return "Quantum computing leverages superposition and entanglement to perform complex computations."

    monkeypatch.setattr(agent, "_execute_tool", mock_execute_tool)
    monkeypatch.setattr(agent, "_call_llm", mock_call_llm)

    step = PlanStep(title="Web Search", description="Search quantum computing")
    res = await agent.execute(step, base_context)
    assert res.success is True
    assert "Quantum computing" in res.data.get("summary", "")
