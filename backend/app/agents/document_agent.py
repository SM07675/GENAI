"""Document Agent — PDF, DOCX, PPTX, spreadsheet processing."""
from __future__ import annotations
from .base_agent import BaseAgent
from ..runtime.schemas import Observation, PlanStep, StepResult, TaskContext, ModelRole


class DocumentAgent(BaseAgent):
    name = "document"
    description = "PDF, DOCX, PPTX, spreadsheet reading and generation"
    capabilities = ["doc_read", "doc_write", "doc_convert", "pdf", "docx", "pptx", "spreadsheet"]
    tools: list[str] = []

    async def execute(self, step: PlanStep, context: TaskContext) -> StepResult:
        desc = step.description or step.title

        # Use LLM to generate document content
        response = await self._call_llm(
            [{"role": "system", "content": (
                "You are a document specialist. Generate well-structured content for documents. "
                "Format output as clean text that can be converted to the target document format."
            )},
             {"role": "user", "content": f"Task: {desc}\nGoal: {context.goal.objective}"}],
            role=ModelRole.REASONING, max_tokens=4000,
        )

        return StepResult(
            success=True,
            message=f"Document content generated for: {step.title}",
            data={"content": response, "type": "document"},
            observations=[self._make_observation(
                "document", f"Generated document content ({len(response)} chars)", step_id=step.step_id,
            )],
            needs_verification=False,
        )
