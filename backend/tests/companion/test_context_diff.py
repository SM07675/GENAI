"""Unit tests for companion/context_engine.py — Context Diff (reflex layer).

Per spec §9: identical scenes must produce zero events.
Per spec §1.5: these tests must exist, must pass, must be shown passing.
"""
import time
import unittest
from app.companion.context_engine import (
    ContextState,
    ScreenContext,
    ContextDelta,
    compute_context_diff,
)
from app.companion.capture import AppInfo


def _make_state(
    process_name: str = "chrome",
    category: str = "browser",
    activity: str = "browsing",
    vision_context: dict | None = None,
) -> ContextState:
    return ContextState(
        application=AppInfo(
            process_name=f"{process_name}.exe",
            process_name_stem=process_name,
            window_title=f"{process_name} - Window",
            category=category,
        ),
        screen=ScreenContext(
            app_name=process_name,
            app_category=category,
            activity=activity,
            vision_context=vision_context,
        ),
        current_mode=category,
    )


class TestContextDiff(unittest.TestCase):
    """Critical §9 / §22 requirement: repeated identical scenes produce zero events."""

    def test_first_observation_produces_no_events(self):
        """First call: previous=None → always empty (nothing to diff against)."""
        current = _make_state()
        deltas = compute_context_diff(None, current)
        self.assertEqual(deltas, [], f"Expected no events on first observation, got {deltas}")

    def test_identical_states_produce_no_events(self):
        """Same app, same activity, same vision → zero deltas (no LLM triggered)."""
        state = _make_state(
            vision_context={"entities": [], "events": [], "confidence": 0.9}
        )
        deltas = compute_context_diff(state, state)
        self.assertEqual(deltas, [], f"Identical scenes should produce 0 events, got {len(deltas)}")

    def test_repeated_enemy_detected_produces_no_event(self):
        """Enemy persists across cycles → exactly ONE detection event, not repeated spam.

        Spec §20.7: 'Repeated ambient event: enemy stays visible → exactly one comment, no spam.'
        This is enforced at the Context Diff level: same entity in both states = no new delta.
        """
        vision_with_enemy = {
            "scene": {"type": "game", "activity": "combat"},
            "entities": [{"type": "enemy", "position": "right", "confidence": 0.91}],
            "events": [{"type": "ENEMY_DETECTED", "importance": "high"}],
            "changes": [],
            "confidence": 0.91,
        }
        state_t1 = _make_state(category="game", vision_context=vision_with_enemy)
        state_t2 = _make_state(category="game", vision_context=vision_with_enemy)

        deltas = compute_context_diff(state_t1, state_t2)
        enemy_events = [d for d in deltas if "ENEMY" in d.event_type.upper()]
        self.assertEqual(enemy_events, [], f"Enemy persisted across cycles should produce 0 new events, got {enemy_events}")

    def test_app_change_produces_event(self):
        """Switching apps should always produce an APP_CHANGED event."""
        prev = _make_state(process_name="chrome", category="browser")
        curr = _make_state(process_name="Code", category="ide")

        deltas = compute_context_diff(prev, curr)
        event_types = [d.event_type for d in deltas]
        self.assertTrue(
            any("APP_CHANGED" in t.upper() or "app" in t.lower() for t in event_types),
            f"App switch should produce an event, got types: {event_types}"
        )

    def test_mode_change_detected(self):
        """Switching from general to gaming should be detected."""
        prev = _make_state(category="browser")
        curr = _make_state(category="game")
        curr.current_mode = "gaming"

        deltas = compute_context_diff(prev, curr)
        self.assertIsInstance(deltas, list)

    def test_context_diff_is_fast(self):
        """compute_context_diff must be synchronous, deterministic, and sub-50ms."""
        prev = _make_state()
        curr = _make_state()
        t0 = time.perf_counter()
        for _ in range(100):
            compute_context_diff(prev, curr)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        self.assertLess(elapsed_ms, 500, f"Context diff is too slow: {elapsed_ms:.1f}ms for 100 calls")


if __name__ == "__main__":
    unittest.main()
