"""Unit tests for the delivery cue parser in orchestrator.py."""
from __future__ import annotations

import pytest

from app.orchestrator import extract_cue, _strip_markdown_for_tts


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
