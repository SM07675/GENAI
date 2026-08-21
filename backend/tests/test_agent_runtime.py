"""Unit & Integration tests for Genie Agent Runtime."""
import asyncio
import pytest
from app.runtime.schemas import (
    Goal,
    PlanStep,
    ExecutionPlan,
    StepStatus,
    TaskStatus,
    FailureCategory,
    RecoveryAction,
    VerificationStatus,
    StepResult,
    Observation,
    TaskContext,
    AutonomyLevel,
)
from app.runtime.goal_engine import GoalEngine
from app.runtime.planner import Planner
from app.runtime.task_graph import TaskGraph
from app.runtime.recovery_engine import RecoveryEngine
from app.runtime.verification_engine import VerificationEngine
from app.runtime.agent_router import AgentRouter
from app.runtime.agent_runtime import AgentRuntime
from app.agents.general_agent import GeneralAgent
from app.agents.research_agent import ResearchAgent
from app.agents.file_agent import FileAgent
from app.agents.system_agent import SystemAgent


# ── Goal Engine Tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_goal_engine_simple_heuristic():
    engine = GoalEngine(model_router=None)
    goal = await engine.extract_goal("What is the capital of France?")
    assert goal.is_simple is True
    assert "capital of France" in goal.objective


@pytest.mark.asyncio
async def test_goal_engine_complex_heuristic():
    engine = GoalEngine(model_router=None)
    goal = await engine.extract_goal("Research Kaggle datasets, download them, and prepare a presentation")
    assert goal.is_simple is False
    assert len(goal.objective) > 0


# ── Planner Tests ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_planner_simple_plan():
    planner = Planner(model_router=None)
    goal = Goal(objective="Hello Genie", is_simple=True)
    plan = await planner.create_plan(goal)
    assert len(plan.steps) == 1
    assert plan.steps[0].agent == "general"


@pytest.mark.asyncio
async def test_planner_fallback_multi_step_plan():
    planner = Planner(model_router=None)
    goal = Goal(
        objective="Research AI and write a file",
        required_capabilities=["research", "file_write"],
        is_simple=False,
    )
    plan = await planner.create_plan(goal)
    assert len(plan.steps) >= 3
    agents = [s.agent for s in plan.steps]
    assert "research" in agents or "general" in agents


# ── Task Graph Tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_task_graph_sequential_execution():
    step1 = PlanStep(step_id="s1", title="Step 1", agent="general")
    step2 = PlanStep(step_id="s2", title="Step 2", agent="general", depends_on=["s1"])
    plan = ExecutionPlan(objective="Test plan", steps=[step1, step2])

    graph = TaskGraph(plan)
    executed_order = []

    async def mock_executor(step, ctx):
        executed_order.append(step.step_id)
        return StepResult(success=True, message=f"Done {step.step_id}")

    ctx = TaskContext(
        task_id="t1",
        session_id="s1",
        goal=Goal(objective="Test"),
        step=step1,
        plan=plan,
    )

    results = await graph.execute(mock_executor, ctx)
    assert executed_order == ["s1", "s2"]
    assert step1.status == StepStatus.COMPLETED
    assert step2.status == StepStatus.COMPLETED
    assert graph.is_complete is True


@pytest.mark.asyncio
async def test_task_graph_parallel_execution():
    # Steps s1 and s2 have no dependencies on each other; s3 depends on both
    step1 = PlanStep(step_id="p1", title="Parallel 1", agent="general")
    step2 = PlanStep(step_id="p2", title="Parallel 2", agent="general")
    step3 = PlanStep(step_id="p3", title="Join", agent="general", depends_on=["p1", "p2"])
    plan = ExecutionPlan(objective="Parallel test", steps=[step1, step2, step3])

    graph = TaskGraph(plan)
    executed = []

    async def mock_executor(step, ctx):
        await asyncio.sleep(0.01)
        executed.append(step.step_id)
        return StepResult(success=True, message="OK")

    ctx = TaskContext(
        task_id="t2",
        session_id="s2",
        goal=Goal(objective="Parallel"),
        step=step1,
        plan=plan,
    )

    await graph.execute(mock_executor, ctx)
    assert "p1" in executed[:2]
    assert "p2" in executed[:2]
    assert executed[2] == "p3"
    assert graph.is_complete is True


# ── Recovery Engine Tests ─────────────────────────────────────────────────────

def test_recovery_engine_classification():
    recovery = RecoveryEngine()
    assert recovery.classify_failure("Connection refused by peer (httperror)") == FailureCategory.NETWORK_ERROR
    assert recovery.classify_failure("Step timed out after 30s") == FailureCategory.TIMEOUT
    assert recovery.classify_failure("401 Unauthorized: Invalid API key") == FailureCategory.AUTH_REQUIRED
    assert recovery.classify_failure("File not found: data/report.pdf") == FailureCategory.ELEMENT_NOT_FOUND


# ── Verification Engine Tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verification_engine_pass():
    verifier = VerificationEngine()
    step = PlanStep(step_id="v1", title="Test file creation")
    result = StepResult(success=True, message="File saved", needs_verification=True)
    obs = [
        Observation(
            source="filesystem",
            content="File exists: test.txt (1024 bytes)",
            raw_data={"exists": True, "size_bytes": 1024, "path": "test.txt"},
        )
    ]

    verif = await verifier.verify(step, result, obs)
    assert verif.status == VerificationStatus.PASSED
    assert verif.confidence == 1.0


@pytest.mark.asyncio
async def test_verification_engine_fail_on_missing_file():
    verifier = VerificationEngine()
    step = PlanStep(step_id="v2", title="Check download")
    result = StepResult(success=True, message="Done", needs_verification=True)
    obs = [
        Observation(
            source="filesystem",
            content="File does NOT exist: dataset.csv",
            raw_data={"exists": False, "path": "dataset.csv"},
        )
    ]

    verif = await verifier.verify(step, result, obs)
    assert verif.status == VerificationStatus.FAILED


# ── Full Agent Runtime Integration Test ───────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_runtime_end_to_end_execution():
    runtime = AgentRuntime(autonomy_level=AutonomyLevel.BALANCED)
    runtime.register_agent(GeneralAgent())
    runtime.register_agent(ResearchAgent())
    runtime.register_agent(FileAgent())
    runtime.register_agent(SystemAgent())

    events_emitted = []

    async def mock_emitter(event_type: str, payload: dict):
        events_emitted.append((event_type, payload))

    runtime.set_event_emitter(mock_emitter)

    result = await runtime.execute_goal(
        user_input="Quick system status check",
        session_id="test_session_1",
    )

    assert result.task_id is not None
    assert result.total_steps > 0
    assert len(events_emitted) > 0
    assert any(e[0] == "agent.goal_received" for e in events_emitted)
    assert any(e[0] == "agent.task_completed" for e in events_emitted)


@pytest.mark.asyncio
async def test_agent_runtime_kill_switch():
    runtime = AgentRuntime()
    events = []

    async def mock_emit(evt: str, data: dict):
        events.append((evt, data))

    runtime.set_event_emitter(mock_emit)
    cancelled = await runtime.stop_all()
    assert cancelled == 0  # No active tasks
    assert any(e[0] == "agent.kill_switch_activated" for e in events)

