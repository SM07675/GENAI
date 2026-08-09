"""PersonalityConfig — Companion Mode personality knobs and presets.

Controls both:
  1. The LLM system-prompt modifier injected into each CompanionBrain call.
  2. The animation intensity tokens sent to the frontend orb overlay.

All values are 0.0–1.0 floats.  Presets are named constants.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class PersonalityConfig:
    """Continuous personality vector for the companion."""
    energy: float = 0.75       # 0 = subdued / 1 = high-energy
    humor: float = 0.65        # 0 = serious / 1 = funny
    hype: float = 0.80         # 0 = calm / 1 = hype beast
    talkativeness: float = 0.50  # 0 = rarely speaks / 1 = always has a comment
    coaching: float = 0.35     # 0 = never coaches / 1 = full coach mode

    def to_prompt_modifier(self) -> str:
        """Build the personality instruction fragment injected into the LLM system prompt."""
        parts: list[str] = []

        if self.energy >= 0.8:
            parts.append("high energy, enthusiastic")
        elif self.energy <= 0.3:
            parts.append("calm, measured")

        if self.humor >= 0.7:
            parts.append("playful and occasionally funny")
        elif self.humor <= 0.2:
            parts.append("serious and professional")

        if self.hype >= 0.8:
            parts.append("hype and encouraging during big moments")

        if self.coaching >= 0.7:
            parts.append("proactively offer coaching tips when relevant")

        if self.talkativeness <= 0.3:
            parts.append("only speak when something truly notable happens")

        if not parts:
            parts.append("friendly and balanced")

        return f"Personality: {', '.join(parts)}. Keep responses short (1-2 sentences max)."

    def orb_intensity(self, base: float = 0.5) -> float:
        """Compute orb animation intensity token given the personality energy/hype."""
        return min(1.0, base + (self.energy * 0.2) + (self.hype * 0.2))

    def speaks_for_importance(self, importance: str) -> bool:
        """Gate: would this personality bother speaking for this importance level?"""
        thresholds = {
            "low": 0.85,      # only very talkative companions comment on low importance
            "medium": 0.45,   # moderate threshold
            "high": 0.10,     # almost everyone speaks on high importance
            "critical": 0.0,  # always speak
        }
        cutoff = thresholds.get(importance, 0.5)
        return self.talkativeness >= cutoff


# ── Presets ───────────────────────────────────────────────────────────────────

FRIENDLY_FRIEND = PersonalityConfig(
    energy=0.70, humor=0.60, hype=0.70, talkativeness=0.50, coaching=0.30
)

HYPE_FRIEND = PersonalityConfig(
    energy=0.95, humor=0.50, hype=1.00, talkativeness=0.75, coaching=0.20
)

FUNNY_FRIEND = PersonalityConfig(
    energy=0.70, humor=0.90, hype=0.60, talkativeness=0.65, coaching=0.10
)

COACH = PersonalityConfig(
    energy=0.60, humor=0.30, hype=0.40, talkativeness=0.70, coaching=0.95
)

QUIET_FRIEND = PersonalityConfig(
    energy=0.40, humor=0.40, hype=0.30, talkativeness=0.20, coaching=0.15
)

# Default: Friendly + Hype + slightly funny (per spec §11)
DEFAULT_PERSONALITY = PersonalityConfig(
    energy=0.75, humor=0.65, hype=0.80, talkativeness=0.50, coaching=0.35
)

PRESETS: Dict[str, PersonalityConfig] = {
    "friendly": FRIENDLY_FRIEND,
    "hype": HYPE_FRIEND,
    "funny": FUNNY_FRIEND,
    "coach": COACH,
    "quiet": QUIET_FRIEND,
    "default": DEFAULT_PERSONALITY,
}
