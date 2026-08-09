"""Unit tests for VisionCallLimiter — budget math and Quick Look reserved allowance.

Per spec §14: ambient throttling must never delay a Quick Look answer.
Per spec §20.13: flood ambient → Quick Look still answers from reserved allowance.
Per spec §1.5: these tests must exist, pass, and be shown passing.
"""
import time
import unittest
from app.companion.vision import VisionCallLimiter


class TestVisionCallLimiter(unittest.TestCase):
    """Verify budget math, degradation, and Quick Look allowance."""

    def test_starts_empty(self):
        limiter = VisionCallLimiter(max_calls_per_minute=6)
        self.assertEqual(limiter.calls_this_minute(), 0)
        self.assertFalse(limiter.is_over_limit())

    def test_records_calls_correctly(self):
        limiter = VisionCallLimiter(max_calls_per_minute=6)
        for _ in range(4):
            limiter.record_call()
        self.assertEqual(limiter.calls_this_minute(), 4)
        self.assertFalse(limiter.is_over_limit())

    def test_hits_limit_at_max(self):
        limiter = VisionCallLimiter(max_calls_per_minute=6)
        for _ in range(6):
            limiter.record_call()
        self.assertTrue(limiter.is_over_limit(), "Should be over limit at max_calls_per_minute")

    def test_session_usage_tracking(self):
        limiter = VisionCallLimiter(max_calls_per_minute=6)
        limiter.record_call()
        limiter.record_call()
        self.assertEqual(limiter._session_calls, 2)

    def test_interval_multiplier_starts_at_1(self):
        limiter = VisionCallLimiter(max_calls_per_minute=10)
        self.assertEqual(limiter.suggested_interval_multiplier(), 1.0)

    def test_interval_multiplier_increases_near_limit(self):
        limiter = VisionCallLimiter(max_calls_per_minute=10)
        for _ in range(9):
            limiter.record_call()
        multiplier = limiter.suggested_interval_multiplier()
        self.assertGreaterEqual(multiplier, 3.0, f"Expected >= 3.0 at 90% usage, got {multiplier}")

    def test_interval_multiplier_medium_load(self):
        limiter = VisionCallLimiter(max_calls_per_minute=10)
        for _ in range(7):
            limiter.record_call()
        multiplier = limiter.suggested_interval_multiplier()
        self.assertTrue(1.5 <= multiplier <= 3.0, f"Expected 1.5-3.0 at 70% usage, got {multiplier}")

    def test_quick_look_allowed_when_ambient_is_at_limit(self):
        """At ambient limit (6/6 calls), Quick Look should still be allowed
        because it draws from a reserved allowance (up to 2x normal max = 12)."""
        limiter = VisionCallLimiter(max_calls_per_minute=6)
        for _ in range(6):
            limiter.record_call()
        self.assertTrue(limiter.is_over_limit(), "Ambient should be at limit")
        self.assertTrue(
            limiter.reserve_for_quicklook(),
            "Quick Look should STILL be allowed even when ambient is at its limit"
        )

    def test_quick_look_blocked_only_at_2x_max(self):
        """Quick Look is blocked only when calls reach 2x the normal max."""
        max_ambient = 6
        limiter = VisionCallLimiter(max_calls_per_minute=max_ambient)
        for _ in range(12):
            limiter.record_call()
        self.assertFalse(
            limiter.reserve_for_quicklook(),
            f"Quick Look should be blocked at 2x max ({max_ambient * 2} calls)"
        )

    def test_quick_look_allowed_below_2x_threshold(self):
        """Quick Look allowed for calls 0 through (2×max − 1)."""
        max_ambient = 6
        limiter = VisionCallLimiter(max_calls_per_minute=max_ambient)
        for _ in range(11):
            limiter.record_call()
        self.assertTrue(
            limiter.reserve_for_quicklook(),
            "Quick Look should be allowed below the 2x reserved threshold"
        )

    def test_old_calls_expire(self):
        limiter = VisionCallLimiter(max_calls_per_minute=3)
        old_time = time.time() - 61
        limiter._call_timestamps = [old_time, old_time, old_time]
        self.assertEqual(limiter.calls_this_minute(), 0, "Calls >60s old should not count")
        self.assertFalse(limiter.is_over_limit(), "Should not be over limit after expiry")


if __name__ == "__main__":
    unittest.main()
