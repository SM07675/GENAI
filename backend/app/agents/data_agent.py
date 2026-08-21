"""Data Agent — data analysis, visualization, Python execution."""
from __future__ import annotations
import subprocess
import tempfile
from pathlib import Path
from .base_agent import BaseAgent
from ..runtime.schemas import Observation, PlanStep, StepResult, TaskContext, ModelRole


class DataAgent(BaseAgent):
    name = "data"
    description = "Data analysis, visualization, Python execution, ML workflows"
    capabilities = ["data_analysis", "visualization", "python_exec", "ml", "statistics"]
    tools: list[str] = []

    async def execute(self, step: PlanStep, context: TaskContext) -> StepResult:
        observations: list[Observation] = []
        desc = step.description or step.title

        # Generate Python code for the data task
        code = await self._call_llm(
            [{"role": "system", "content": (
                "You are a data scientist. Write Python code to accomplish the task. "
                "Use pandas, numpy, matplotlib as needed. Output only the Python code, "
                "no markdown fences. Print results to stdout."
            )},
             {"role": "user", "content": f"Task: {desc}"}],
            role=ModelRole.CODING, max_tokens=3000,
        )

        # Clean code (remove markdown fences if present)
        code = code.strip()
        if code.startswith("```"):
            lines = code.split("\n")
            code = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        # Execute Python code safely
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
                f.write(code)
                script_path = f.name

            result = subprocess.run(
                ["python", script_path],
                capture_output=True, text=True, timeout=120,
            )

            Path(script_path).unlink(missing_ok=True)

            success = result.returncode == 0
            obs = self._make_observation(
                "python", f"Script {'succeeded' if success else 'failed'}: exit {result.returncode}",
                data={"stdout": result.stdout[:5000], "stderr": result.stderr[:2000], "code": code[:3000]},
                step_id=step.step_id,
            )
            observations.append(obs)

            return StepResult(
                success=success,
                message=result.stdout[:500] if success else f"Script failed: {result.stderr[:500]}",
                data={"stdout": result.stdout[:10000], "stderr": result.stderr[:3000], "code": code},
                observations=observations,
            )
        except subprocess.TimeoutExpired:
            return StepResult(success=False, message="Python script timed out (120s limit)")
        except Exception as exc:
            return StepResult(success=False, message=f"Python execution failed: {exc}")
