"""Unit tests for CompanionBrain gate logic using unittest.

Per spec §10:
- IGNORE path must resolve on cheap rule-based checks ONLY — never by paying for an LLM call.
- Gates (cheapest first): importance × talkativeness, global cooldown, per-event cooldown,
  confidence threshold, user typing (coding), duplicate detection.

Per spec §1.5: these tests must exist, pass, and be shown passing.
"""
import asyncio
import time
import unittest
from unittest.mock import AsyncMock, patch

from app.companion.brain import CompanionBrain, BrainDecision, _GLOBAL_COOLDOWN
from app.companion.events import CompanionEvent, EventType
from app.companion.personality import PersonalityConfig, QUIET_FRIEND, HYPE_FRIEND


def _make_event(
    event_type: EventType = EventType.ENEMY_DETECTED,
    importance: str = "high",
    mode: str = "gaming",
    confidence: float = 0.95,
) -> CompanionEvent:
    return CompanionEvent(
        event_type=event_type,
        importance=importance,
        mode=mode,
        confidence=confidence,
    )


def _make_brain(
    personality: PersonalityConfig | None = None,
    emit: object = None,
    last_spoke_offset: float = 999.0,
) -> CompanionBrain:
    mock_emit = AsyncMock() if emit is None else emit
    brain = CompanionBrain(emit=mock_emit)
    if personality:
        brain.set_personality(personality)
    brain._last_spoke_at = time.time() - last_spoke_offset
    return brain


class TestBrainGates(unittest.IsolatedAsyncioTestCase):
    """Test CompanionBrain gate logic."""

    async def test_low_importance_ignored_by_quiet_personality(self):
        brain = _make_brain(personality=QUIET_FRIEND)
        event = _make_event(importance="low")
        result = await brain.process_event(event)
        self.assertEqual(result.decision, "IGNORE")

    async def test_ignore_never_calls_llm(self):
        """The IGNORE path must be pure rule-based — zero LLM calls."""
        brain = _make_brain(personality=QUIET_FRIEND)
        event = _make_event(importance="low")

        llm_calls = []

        async def spy(*args, **kwargs):
            llm_calls.append(args)
            return "Some line"

        brain._generate_line = spy
        result = await brain.process_event(event)
        self.assertEqual(result.decision, "IGNORE")
        self.assertEqual(len(llm_calls), 0, f"IGNORE path must not call LLM, but _generate_line was called {len(llm_calls)} times")

    async def test_global_cooldown_triggers_ignore(self):
        """Brain spoke 1 second ago → global cooldown (4s) should fire IGNORE."""
        brain = _make_brain(last_spoke_offset=1.0)
        brain.set_personality(HYPE_FRIEND)
        event = _make_event(importance="high")

        result = await brain.process_event(event)
        self.assertEqual(result.decision, "IGNORE")
        self.assertIn("cooldown", result.reason.lower())

    async def test_low_confidence_ignored(self):
        brain = _make_brain(personality=HYPE_FRIEND, last_spoke_offset=30.0)
        event = _make_event(confidence=0.3)

        result = await brain.process_event(event)
        self.assertEqual(result.decision, "IGNORE")
        self.assertIn("confidence", result.reason.lower())

    async def test_active_typing_suppresses_comment(self):
        """User is typing → coding gate should fire IGNORE."""
        from app.companion.context_engine import ContextState, ScreenContext
        from app.companion.capture import AppInfo

        brain = _make_brain(personality=HYPE_FRIEND, last_spoke_offset=30.0)
        event = _make_event(mode="coding", importance="medium")

        ctx = ContextState(
            application=AppInfo(
                process_name="Code.exe",
                process_name_stem="Code",
                window_title="Code",
                category="ide",
            ),
            screen=ScreenContext(app_name="Code"),
        )
        ctx.last_keypress_at = time.time() - 1.0

        with patch.object(brain, "_generate_line", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "Your code has an error."
            result = await brain.process_event(event, context=ctx)
            self.assertEqual(result.decision, "IGNORE")

    async def test_duplicate_line_suppressed(self):
        """If the exact same line was spoken this session, IGNORE."""
        brain = _make_brain(personality=HYPE_FRIEND, last_spoke_offset=30.0)
        duplicate_line = "Watch out, enemy on the right!"
        brain._session_lines.add(duplicate_line)

        event = _make_event(importance="high")

        with patch.object(brain, "_generate_line", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = duplicate_line
            brain._last_spoke_type.clear()
            result = await brain.process_event(event)
            self.assertEqual(result.decision, "IGNORE")


if __name__ == "__main__":
    unittest.main()
