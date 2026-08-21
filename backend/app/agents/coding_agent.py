"""Coding Agent — code reading, writing, debugging, testing."""
from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Any
from .base_agent import BaseAgent
from ..runtime.schemas import Observation, PlanStep, StepResult, TaskContext, ModelRole


class CodingAgent(BaseAgent):
    name = "coding"
    description = "Code reading, understanding, writing, debugging, testing, iterative fixes"
    capabilities = [
        "code_read", "code_write", "code_debug", "code_test",
        "code_explain", "code_review", "code_fix", "code_generate",
    ]
    tools: list[str] = []

    async def execute(self, step: PlanStep, context: TaskContext) -> StepResult:
        observations: list[Observation] = []
        desc = (step.description or step.title).lower()

        # Gather code context from previous steps
        code_context = ""
        for prev in context.previous_results.values():
            data = prev.get("data", {})
            if "content" in data and any(
                data.get("path", "").endswith(ext) for ext in [".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs"]
            ):
                code_context += f"\n--- {data.get('path', 'file')} ---\n{data['content'][:5000]}\n"

        if any(w in desc for w in ["debug", "fix", "error", "bug"]):
            return await self._debug_code(step, context, code_context, observations)
        elif any(w in desc for w in ["write", "create", "generate", "implement"]):
            return await self._write_code(step, context, code_context, observations)
        elif any(w in desc for w in ["test", "run test", "unittest"]):
            return await self._run_tests(step, context, observations)
        elif any(w in desc for w in ["explain", "understand", "review"]):
            return await self._explain_code(step, context, code_context, observations)
        else:
            return await self._general_coding(step, context, code_context, observations)

    async def _debug_code(self, step: PlanStep, ctx: TaskContext, code: str, obs: list) -> StepResult:
        prompt = (
            f"Debug this code issue:\n{step.description}\n\n"
            f"Code context:\n{code[:8000]}\n\n"
            "Identify the bug, explain it, and provide the fix."
        )
        response = await self._call_llm(
            [{"role": "system", "content": "You are an expert debugger. Find and fix bugs precisely."},
             {"role": "user", "content": prompt}],
            role=ModelRole.CODING, max_tokens=3000,
        )
        return StepResult(success=True, message=response[:500], data={"analysis": response, "type": "debug"},
                          observations=obs, needs_verification=False)

    async def _write_code(self, step: PlanStep, ctx: TaskContext, code: str, obs: list) -> StepResult:
        prompt = f"Write code for: {step.description or step.title}\n\nExisting code context:\n{code[:5000]}"
        response = await self._call_llm(
            [{"role": "system", "content": "You are an expert programmer. Write clean, well-documented code."},
             {"role": "user", "content": prompt}],
            role=ModelRole.CODING, max_tokens=4000,
        )
        return StepResult(success=True, message=f"Code generated for: {step.title}", data={"code": response, "type": "generate"},
                          observations=obs, needs_verification=False)

    async def _run_tests(self, step: PlanStep, ctx: TaskContext, obs: list) -> StepResult:
        cmd = step.description or "python -m pytest"
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=ctx.environment.get("cwd"))
            success = result.returncode == 0
            obs.append(self._make_observation(
                "command", f"Test {'passed' if success else 'failed'}: exit {result.returncode}",
                data={"stdout": result.stdout[:3000], "stderr": result.stderr[:1000], "exit_code": result.returncode},
                step_id=step.step_id,
            ))
            return StepResult(success=success, message=f"Tests {'passed' if success else 'failed'}",
                              data={"stdout": result.stdout[:5000], "stderr": result.stderr[:2000], "exit_code": result.returncode},
                              observations=obs)
        except Exception as exc:
            return StepResult(success=False, message=f"Test execution failed: {exc}")

    async def _explain_code(self, step: PlanStep, ctx: TaskContext, code: str, obs: list) -> StepResult:
        response = await self._call_llm(
            [{"role": "system", "content": "Explain code clearly and concisely."},
             {"role": "user", "content": f"Explain: {step.description}\n\nCode:\n{code[:8000]}"}],
            role=ModelRole.FAST,
        )
        return StepResult(success=True, message=response[:500], data={"explanation": response},
                          observations=obs, needs_verification=False)

    async def _general_coding(self, step: PlanStep, ctx: TaskContext, code: str, obs: list) -> StepResult:
        response = await self._call_llm(
            [{"role": "system", "content": "You are an expert software engineer."},
             {"role": "user", "content": f"Task: {step.title}\n{step.description}\n\nCode:\n{code[:5000]}"}],
            role=ModelRole.CODING, max_tokens=3000,
        )
        return StepResult(success=True, message=response[:500], data={"response": response},
                          observations=obs, needs_verification=False)
