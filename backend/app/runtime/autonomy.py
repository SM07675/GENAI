"""Progressive Autonomy Engine for Genie AI OS.

Defines 4 graduated operating modes:
1. MANUAL: Genie requests approval before executing any tool or external side-effect.
2. ASSIST: Genie autonomously reads context and performs non-destructive actions, but asks for files/commands.
3. BALANCED (Default): Genie autonomously executes standard workflows, asking confirmation only for destructive actions or sensitive data access.
4. AUTONOMOUS: Genie executes full multi-step workflows end-to-end, only stopping for hard safety boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Optional

from ..os.permissions import SideEffectLevel
from .schemas import AutonomyLevel


@dataclass
class AutonomyPolicy:
    level: AutonomyLevel = AutonomyLevel.BALANCED

    def requires_confirmation(self, side_effect: SideEffectLevel) -> bool:
        """Evaluate if an action with a given side effect level needs explicit user confirmation."""
        if self.level == AutonomyLevel.MANUAL:
            # Everything except pure read-only requires confirmation
            return side_effect != SideEffectLevel.READ_ONLY

        elif self.level == AutonomyLevel.ASSIST:
            # Local changes, external network, personal data, and destructive need approval
            return side_effect in (
                SideEffectLevel.LOCAL_CHANGE,
                SideEffectLevel.EXTERNAL_NETWORK,
                SideEffectLevel.PERSONAL_DATA,
                SideEffectLevel.DESTRUCTIVE,
                SideEffectLevel.ACCOUNT,
            )

        elif self.level == AutonomyLevel.BALANCED:
            # Only destructive and account-level side effects need approval
            return side_effect in (
                SideEffectLevel.DESTRUCTIVE,
                SideEffectLevel.ACCOUNT,
            )

        elif self.level == AutonomyLevel.AUTONOMOUS:
            # Only strictly irreversible destructive operations need approval
            return side_effect == SideEffectLevel.DESTRUCTIVE

        return False


# Global policy
autonomy_policy = AutonomyPolicy(level=AutonomyLevel.BALANCED)
