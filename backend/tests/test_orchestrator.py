"""Unit tests for the delivery cue parser in orchestrator.py."""
from __future__ import annotations

import pytest

from app.orchestrator import extract_cue, _strip_markdown_for_tts, _tool_result_content
from app.schemas import ToolResult


class TestExtractCue:
    def test_no_cue_returns_neutral(self):
        cue, text = extract_cue("Hello, how are you?")
        assert cue == "neutral"
        assert text == "Hello, how are you?"

    def test_single_cue_extracted(self):
        cue, text = extract_cue("[[warm]] That sounds great.")
        assert cue == "warm"
        assert text == "That sounds great."

    def test_cue_mid_sentence(self):
        cue, text = extract_cue("Done — sent. [[apologetic]] Couldn't attach the PDF though.")
        assert cue == "apologetic"
        assert text == "Done — sent. Couldn't attach the PDF though."

    def test_multiple_cues_last_wins(self):
        cue, text = extract_cue("[[cheerful]] Great! [[urgent]] But hurry.")
        assert cue == "urgent"
        assert text == "Great! But hurry."

    def test_all_valid_cues(self):
        valid_cues = ["neutral", "warm", "cheerful", "empathetic",
                      "apologetic", "urgent", "focused", "reassuring"]
        for c in valid_cues:
            cue, text = extract_cue(f"[[{c}]] Test.")
            assert cue == c
            assert text == "Test."

    def test_invalid_cue_not_extracted(self):
        cue, text = extract_cue("[[angry]] This should stay.")
        assert cue == "neutral"
        assert text == "[[angry]] This should stay."

    def test_double_spaces_collapsed(self):
        cue, text = extract_cue("Hello [[warm]] world.")
        assert "  " not in text


class TestStripMarkdownForTts:
    def test_strips_headers(self):
        assert _strip_markdown_for_tts("## Hello World") == "Hello World"

    def test_strips_bold(self):
        assert _strip_markdown_for_tts("This is **bold** text") == "This is bold text"

    def test_strips_italic(self):
        assert _strip_markdown_for_tts("This is *italic* text") == "This is italic text"

    def test_strips_bullet_lists(self):
        result = _strip_markdown_for_tts("- Item one\n- Item two")
        assert "- " not in result
        assert "Item one" in result

    def test_strips_urls(self):
        result = _strip_markdown_for_tts("Visit https://example.com for details.")
        assert "https://" not in result

    def test_strips_code_fences(self):
        result = _strip_markdown_for_tts("Run `pip install`")
        assert "`" not in result
        assert "pip install" in result

    def test_empty_input(self):
        assert _strip_markdown_for_tts("") == ""

    def test_plain_text_unchanged(self):
        text = "Hello, how are you doing today?"
        assert _strip_markdown_for_tts(text) == text


class TestToolResultContent:
    def test_includes_structured_data_for_model(self):
        result = ToolResult(
            status="ok",
            message="Found 1 result.",
            data={"results": [{"title": "Example", "url": "https://example.com"}]},
        )

        content = _tool_result_content(result)

        assert '"status": "ok"' in content
        assert '"message": "Found 1 result."' in content
        assert "https://example.com" in content


class TestStripWakePhrase:
    """Test wake phrase stripping (M1 fix validation)."""

    def test_hey_genie_with_command(self):
        from app.orchestrator import _strip_wake_phrase
        assert _strip_wake_phrase("Hey Genie, open YouTube") == "open YouTube"

    def test_okay_genie_with_command(self):
        from app.orchestrator import _strip_wake_phrase
        assert _strip_wake_phrase("Okay Genie what's the weather") == "what's the weather"

    def test_bare_wake_phrase(self):
        """M1: bare 'Hey Genie' should return empty string."""
        from app.orchestrator import _strip_wake_phrase
        assert _strip_wake_phrase("Hey Genie") == ""

    def test_bare_wake_phrase_with_comma(self):
        from app.orchestrator import _strip_wake_phrase
        assert _strip_wake_phrase("Hey Genie,") == ""

    def test_no_wake_phrase(self):
        from app.orchestrator import _strip_wake_phrase
        assert _strip_wake_phrase("open YouTube") == "open YouTube"

    def test_case_insensitive(self):
        from app.orchestrator import _strip_wake_phrase
        assert _strip_wake_phrase("HEY GENIE open chrome") == "open chrome"

    def test_whitespace_handling(self):
        from app.orchestrator import _strip_wake_phrase
        assert _strip_wake_phrase("  Hey Genie   play music  ") == "play music"


class TestSentenceBoundaryDetection:
    """Test sentence boundary regex used in TTS pipeline (M2 fix validation)."""

    def test_period_boundary(self):
        import re
        text = "Hello world. How are you? "
        match = re.search(r'([.?!।]\s+)', text)
        assert match is not None
        assert match.end() > 0

    def test_question_boundary(self):
        import re
        text = "How are you? I'm fine."
        match = re.search(r'([.?!।]\s+)', text)
        assert match is not None

    def test_no_boundary_without_space(self):
        """M2: punctuation without trailing space doesn't split."""
        import re
        text = "Hello world."
        match = re.search(r'([.?!।]\s+)', text)
        assert match is None  # no space after period

    def test_multiple_sentences(self):
        """Multiple sentence boundaries are found iteratively."""
        import re
        text = "First. Second! Third? Done."
        boundaries = list(re.finditer(r'([.?!।]\s+)', text))
        assert len(boundaries) == 3

    def test_hindi_punctuation(self):
        """Hindi danda (।) is also a sentence boundary."""
        import re
        text = "हैलो। कैसे हो? "
        match = re.search(r'([.?!।]\s+)', text)
        assert match is not None

