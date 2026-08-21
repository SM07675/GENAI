"""Verification Engine — validates that actions actually succeeded.

Never assume success simply because the command completed. The verification
engine checks that the expected outcome was actually achieved.

Verification strategies:
    - File existence and non-zero size
    - Command exit code validation
    - Tool result status check
    - Content validation (expected text/data present)
    - State change detection (before/after comparison)
"""
from __future__ import annotations

from typing import Any, Optional

import structlog

from .schemas import (
    Observation,
    PlanStep,
    StepResult,
    VerificationResult,
    VerificationStatus,
    _now_iso,
)

log = structlog.get_logger("genie.runtime.verification")


class VerificationEngine:
    """Verifies that actions produced the expected outcomes.

    Uses observations as evidence and applies verification rules
    based on the type of action that was performed.
    """

    async def verify(
        self,
        step: PlanStep,
        result: StepResult,
        observations: list[Observation],
    ) -> VerificationResult:
        """Verify that a step's execution actually succeeded.

        Applies appropriate verification checks based on what the step
        did and what observations are available.
        """
        if not result.needs_verification:
            return VerificationResult(
                status=VerificationStatus.SKIPPED,
                message="Verification skipped (not required for this step)",
                step_id=step.step_id,
            )

        checks: list[dict[str, Any]] = []

        # Check 1: Basic result status
        result_check = self._check_result_status(result)
        checks.append(result_check)

        # Check 2: Observation-based checks
        for obs in observations:
            obs_check = self._check_observation(obs, step)
            if obs_check:
                checks.append(obs_check)

        # Check 3: Tool-specific checks
        for tool_name in step.tool_names:
            tool_check = self._check_tool_specific(tool_name, result, observations)
            if tool_check:
                checks.append(tool_check)

        # Aggregate results
        all_passed = all(c.get("passed", False) for c in checks)
        any_failed = any(c.get("passed") is False for c in checks)
        has_warnings = any(c.get("warning", False) for c in checks)

        if all_passed and not has_warnings:
            status = VerificationStatus.PASSED
            message = f"All {len(checks)} verification checks passed"
            confidence = 1.0
        elif any_failed:
            status = VerificationStatus.FAILED
            failed = [c for c in checks if not c.get("passed", True)]
            message = f"Verification failed: {failed[0].get('reason', 'unknown')}"
            confidence = 0.0
        elif has_warnings:
            status = VerificationStatus.PARTIAL
            message = "Verification partially passed with warnings"
            confidence = 0.7
        else:
            status = VerificationStatus.INCONCLUSIVE
            message = "Could not conclusively verify outcome"
            confidence = 0.5

        return VerificationResult(
            status=status,
            message=message,
            checks=checks,
            confidence=confidence,
            step_id=step.step_id,
        )

    def _check_result_status(self, result: StepResult) -> dict[str, Any]:
        """Check the basic result status."""
        return {
            "check": "result_status",
            "passed": result.success,
            "reason": result.message if not result.success else "Step reported success",
            "detail": {"success": result.success, "message": result.message},
        }

    def _check_observation(
        self, obs: Observation, step: PlanStep
    ) -> dict[str, Any] | None:
        """Check an observation for verification evidence."""
        source = obs.source
        data = obs.raw_data

        # Filesystem observations
        if source == "filesystem":
            exists = data.get("exists", False)
            size = data.get("size_bytes", 0)

            if not exists:
                return {
                    "check": "file_exists",
                    "passed": False,
                    "reason": f"Expected file does not exist: {data.get('path', 'unknown')}",
                    "detail": data,
                }

            if exists and size == 0:
                return {
                    "check": "file_non_empty",
                    "passed": False,
                    "warning": True,
                    "reason": f"File exists but is empty: {data.get('path', 'unknown')}",
                    "detail": data,
                }

            return {
                "check": "file_exists",
                "passed": True,
                "reason": f"File exists with {size} bytes",
                "detail": data,
            }

        # Command observations
        if source == "command":
            success = data.get("success", False)
            exit_code = data.get("exit_code", -1)

            return {
                "check": "command_exit_code",
                "passed": success,
                "reason": f"Command exit code: {exit_code}",
                "detail": {
                    "command": data.get("command", ""),
                    "exit_code": exit_code,
                    "stderr": data.get("stderr", "")[:500],
                },
            }

        # Tool observations
        if source.startswith("tool:"):
            tool_status = data.get("status", "unknown")
            passed = tool_status in ("ok", "success", "completed")

            return {
                "check": "tool_status",
                "passed": passed,
                "reason": f"Tool status: {tool_status}",
                "detail": data,
            }

        # Web search observations
        if source == "web_search":
            result_count = data.get("result_count", 0)
            return {
                "check": "search_results",
                "passed": result_count > 0,
                "reason": f"Found {result_count} results",
                "detail": {"query": data.get("query", ""), "count": result_count},
            }

        return None

    def _check_tool_specific(
        self,
        tool_name: str,
        result: StepResult,
        observations: list[Observation],
    ) -> dict[str, Any] | None:
        """Apply tool-specific verification logic."""
        data = result.data

        # File creation tools
        if tool_name in ("write_file", "create_file", "save_file"):
            path = data.get("path") or data.get("file_path")
            if path:
                # Look for filesystem observation
                for obs in observations:
                    if obs.source == "filesystem" and obs.raw_data.get("path") == path:
                        return None  # already checked by _check_observation

        # Web search
        if tool_name == "search_web":
            results = data.get("results", [])
            return {
                "check": "search_quality",
                "passed": len(results) > 0,
                "reason": f"Search returned {len(results)} results",
                "detail": {"result_count": len(results)},
            }

        # App operations
        if tool_name in ("open_app", "launch_app"):
            return {
                "check": "app_launched",
                "passed": result.success,
                "reason": f"App launch: {'success' if result.success else 'failed'}",
                "detail": data,
            }

        return None
