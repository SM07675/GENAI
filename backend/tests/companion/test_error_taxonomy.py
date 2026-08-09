"""Unit tests for Genie error taxonomy (§1.2, §1.3)."""
import unittest
from app.errors import (
    GenieError,
    BackendUnavailableError,
    VisionProviderError,
    TTSStreamError,
    ToolExecutionError,
    CaptureDeniedError,
)


class TestErrorTaxonomy(unittest.TestCase):

    def test_vision_provider_error_user_message(self):
        err = VisionProviderError("API rate limit 429")
        self.assertEqual(err.code, "VISION_PROVIDER_ERROR")
        self.assertTrue(err.recoverable)
        self.assertIn("couldn't analyze it right now", err.user_message)
        self.assertNotIn("429", err.user_message)  # User does not see raw status code

    def test_capture_denied_error_fallback(self):
        err = CaptureDeniedError("DRM protected surface")
        self.assertEqual(err.code, "CAPTURE_DENIED")
        self.assertIn("tell me what's happening", err.user_message)

    def test_tool_execution_error_dict(self):
        err = ToolExecutionError("open_app", "Process notepad not found")
        self.assertEqual(err.code, "TOOL_EXECUTION_ERROR")
        d = err.to_dict()
        self.assertTrue(d["error"])
        self.assertEqual(d["code"], "TOOL_EXECUTION_ERROR")


if __name__ == "__main__":
    unittest.main()
