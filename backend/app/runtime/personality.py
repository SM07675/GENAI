"""Personality and Persona Engine for Genie AI OS.

Controls:
- Tone adaptation (warm, focused, concise, reassuring, urgent, playful)
- Speaking prosody cue injection for Edge TTS
- Proactivity frequency gating
- Relationship alignment based on user feedback
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Dict, Optional


class SpeakingStyle(StrEnum):
    CONCISE = "concise"
    BALANCED = "balanced"
    EXPLANATORY = "explanatory"
    EXPERT = "expert"


@dataclass
class PersonalityConfig:
    tone: str = "warm"
    style: SpeakingStyle = SpeakingStyle.BALANCED
    proactivity_level: float = 0.5  # 0.0 (silent) to 1.0 (very proactive)
    user_name: str = "Friend"
    companion_mode: bool = True

    def get_system_prompt_addition(self) -> str:
        """Render personality instructions for model conditioning."""
        return (
            f"You are Genie, a helpful, intelligent, and calm personal AI companion. "
            f"Address the user as {self.user_name}. Maintain a {self.tone} and {self.style.value} tone. "
            f"When completing actions, explain clearly what was done without revealing internal chain-of-thought."
        )


# Global default personality
default_personality = PersonalityConfig()
