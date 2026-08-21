"""Recovery Engine — intelligent failure handling and recovery.

When a step fails, the recovery engine:
    1. Classifies the failure (network, timeout, tool error, etc.)
    2. Determines recoverability
    3. Decides on recovery action (retry, alternative, replan, ask user, abort)
    4. Executes the recovery strategy

The goal is for Genie to say "The first source is unavailable, so I
found another source" instead of simply "Error."
"""
from __future__ import annotations

import re
from typing import Any, Optional

import structlog

from .schemas import (
    AgentState,
    FailedStep,
    FailureCategory,
    PlanStep,
    RecoveryAction,
    StepStatus,
    _now_iso,
)

log = structlog.get_logger("genie.runtime.recovery")


# ── Failure classification patterns ──────────────────────────────────────────

_FAILURE_PATTERNS: list[tuple[FailureCategory, list[str]]] = [
    (FailureCategory.NETWORK_ERROR, [
        "connection", "network", "dns", "refused", "unreachable",
        "ssl", "certificate", "socket", "httperror",
    ]),
    (FailureCategory.TIMEOUT, [
        "timeout", "timed out", "deadline", "took too long",
    ]),
    (FailureCategory.AUTH_REQUIRED, [
        "auth", "unauthorized", "forbidden", "403", "401",
        "login", "credential", "api key", "token expired",
    ]),
    (FailureCategory.PERMISSION_DENIED, [
        "permission", "access denied", "not allowed", "restricted",
    ]),
    (FailureCategory.ELEMENT_NOT_FOUND, [
        "not found", "404", "no such file", "does not exist",
        "element not found", "selector not found", "no results",
    ]),
    (FailureCategory.APPLICATION_NOT_FOUND, [
        "application not found", "app not found", "not installed",
        "command not found", "executable not found",
    ]),
    (FailureCategory.MODEL_ERROR, [
        "model error", "llm", "generation failed", "token limit",
        "context length", "rate limit", "quota", "openai",
    ]),
    (FailureCategory.PARSER_ERROR, [
        "parse", "json", "syntax", "decode", "format",
        "unexpected token", "invalid",
    ]),
    (FailureCategory.INVALID_INPUT, [
        "invalid", "missing required", "bad request", "validation",
        "type error", "value error",
    ]),
    (FailureCategory.RESOURCE_UNAVAILABLE, [
        "resource", "unavailable", "capacity", "memory", "disk",
        "out of", "insufficient",
    ]),
]


class RecoveryEngine:
    """Handles failure classification and recovery strategies.

    The recovery engine is the component that makes Genie resilient.
    Instead of stopping at the first error, it classifies the failure
    and decides on the best recovery action.
    """

    def __init__(self, model_router: Any = None):
        self._model_router = model_router
        self._recovery_log: list[dict[str, Any]] = []

    async def handle_failure(
        self,
        step: PlanStep,
        error: Exception | str,
        state: AgentState,
    ) -> tuple[RecoveryAction, FailedStep, str]:
        """Handle a step failure and decide on recovery.

        Returns:
            Tuple of (RecoveryAction, FailedStep, explanation)
        """
        error_message = str(error)
        category = self.classify_failure(error_message)

        failed_step = FailedStep(
            step=step,
            category=category,
            error_message=error_message,
            attempt_number=step.retry_count + 1,
        )

        # Determine recovery action
        action, explanation = await self._decide_recovery(
            failed_step, state
        )

        # Log recovery decision
        self._recovery_log.append({
            "step_id": step.step_id,
            "step_title": step.title,
            "category": category.value,
            "error": error_message[:500],
            "action": action.value,
            "explanation": explanation,
            "attempt": step.retry_count + 1,
            "timestamp": _now_iso(),
        })

        log.info(
            "recovery_decision",
            step=step.title,
            category=category.value,
            action=action.value,
            attempt=step.retry_count + 1,
        )

        return action, failed_step, explanation

    def classify_failure(self, error_message: str) -> FailureCategory:
        """Classify an error into a failure category.

        Uses pattern matching against known error signatures.
        """
        lower = error_message.lower()

        for category, patterns in _FAILURE_PATTERNS:
            if any(pattern in lower for pattern in patterns):
                return category

        return FailureCategory.UNKNOWN_ERROR

    async def _decide_recovery(
        self,
        failed_step: FailedStep,
        state: AgentState,
    ) -> tuple[RecoveryAction, str]:
        """Decide on the best recovery action for a failure.

        Decision matrix:
            - Retryable category + retries remaining → RETRY
            - Network/timeout + alternative available → ALTERNATIVE
            - Tool error + tool has fallback → ALTERNATIVE
            - Auth required → ASK_USER
            - Permission denied → ASK_USER
            - Multiple failures on same step → REPLAN
            - Non-critical step → SKIP
            - Everything else → REPLAN or ABORT
        """
        step = failed_step.step
        category = failed_step.category
        attempt = failed_step.attempt_number
        retry_policy = step.retry_policy

        # Check if this failure category is retryable
        is_retryable = category in retry_policy.retryable_failures
        retries_remaining = retry_policy.max_retries - attempt + 1

        # Decision: RETRY
        if is_retryable and retries_remaining > 0:
            return (
                RecoveryAction.RETRY,
                f"Retrying step '{step.title}' (attempt {attempt + 1}/{retry_policy.max_retries + 1}). "
                f"Error was: {category.value}",
            )

        # Decision: ASK_USER for auth/permission
        if category in (FailureCategory.AUTH_REQUIRED, FailureCategory.PERMISSION_DENIED):
            return (
                RecoveryAction.ASK_USER,
                f"Step '{step.title}' requires authorization or permission. "
                f"Please provide the necessary credentials or approve the action.",
            )

        # Decision: ALTERNATIVE if there's a fallback step
        if step.fallback_step_id:
            return (
                RecoveryAction.ALTERNATIVE,
                f"Step '{step.title}' failed. Trying fallback approach.",
            )

        # Decision: SKIP for non-critical steps
        if self._is_non_critical(step, state):
            return (
                RecoveryAction.SKIP,
                f"Skipping non-critical step '{step.title}'. "
                f"The task can continue without it.",
            )

        # Decision: REPLAN if we have completed meaningful work
        completed_count = len(state.plan.completed_steps) if state.plan else 0
        if completed_count > 0:
            return (
                RecoveryAction.REPLAN,
                f"Step '{step.title}' failed after {attempt} attempts. "
                f"Replanning from current state ({completed_count} steps completed).",
            )

        # Decision: REPLAN for recoverable errors
        if category in (
            FailureCategory.NETWORK_ERROR,
            FailureCategory.TIMEOUT,
            FailureCategory.ELEMENT_NOT_FOUND,
            FailureCategory.RESOURCE_UNAVAILABLE,
        ):
            return (
                RecoveryAction.REPLAN,
                f"Step '{step.title}' failed due to {category.value}. "
                f"Creating an alternative plan.",
            )

        # Decision: ABORT for unrecoverable errors
        if category in (FailureCategory.MODEL_ERROR,) and attempt >= 3:
            return (
                RecoveryAction.ABORT,
                f"Step '{step.title}' failed repeatedly due to {category.value}. "
                f"Unable to continue.",
            )

        # Default: REPLAN
        return (
            RecoveryAction.REPLAN,
            f"Step '{step.title}' failed: {failed_step.error_message[:200]}. "
            f"Attempting to find an alternative approach.",
        )

    @staticmethod
    def _is_non_critical(step: PlanStep, state: AgentState) -> bool:
        """Determine if a step is non-critical and can be skipped.

        A step is non-critical if:
            - No other step depends on it
            - It's a verification or cleanup step
            - It's an optional enhancement step
        """
        if not state.plan:
            return False

        # Check if any other step depends on this one
        has_dependents = any(
            step.step_id in s.depends_on
            for s in state.plan.steps
            if s.step_id != step.step_id
        )

        if has_dependents:
            return False

        # Check title patterns for non-critical steps
        non_critical_patterns = [
            "verify", "validate", "check", "cleanup", "optimize",
            "enhance", "polish", "format", "beautify",
        ]
        lower_title = step.title.lower()
        return any(p in lower_title for p in non_critical_patterns)

    @property
    def recovery_history(self) -> list[dict[str, Any]]:
        """Get recovery decision history for debugging."""
        return self._recovery_log[-50:]
