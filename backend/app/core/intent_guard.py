"""ToolIntentGuard — pre-execution tool authorization layer.

Architecture
------------
User transcript
  -> LLM generates tool_call proposal
  -> ToolIntentGuard.check(tool_name, args, raw_user_text)   <- THIS MODULE
      -> ALLOWED: execute tool
      -> REJECTED: skip tool, log reason, LLM answers conversationally

Policy
------
A tool call is ONLY permitted when the user's raw transcript contains an
explicit, unambiguous action signal that maps to that specific tool.

Rules (applied in order):
  1. Conversational phrases NEVER trigger action tools.
  2. Media tools require explicit playback/pause/stop verbs.
  3. Desktop tools require explicit open/close/launch verbs.
  4. Tool arguments must be derivable from the user's actual words.
  5. When in doubt, REJECT and let the LLM answer conversationally.
"""
from __future__ import annotations

import re
from typing import Any

import structlog

log = structlog.get_logger("genie.intent_guard")


# ---- Conversational phrases that NEVER warrant action tool execution ---------
# If the user text is purely conversational, all action tools are blocked.
_CONVERSATIONAL_PATTERNS = re.compile(
    r"^("
    # Identity / capability questions
    r"(who|what)\s+(are|is)\s+(you|genie|this)\b|"
    r"tell\s+me\s+about\s+(yourself|you)\b|"
    r"(describe|introduce)\s+(yourself|you)\b|"
    r"what\s+can\s+you\s+do\b|"
    r"(how|what)\s+(do\s+you\s+work|are\s+you\s+made)\b|"
    r"are\s+you\s+(an?\s+ai|a\s+bot|an?\s+assistant|real)\b|"
    # Refusal / frustration questions directed at Genie itself
    r"why\s+(are|is|aren'?t)\s+(you|genie)\s+(not\s+|still\s+)?(telling|saying|doing|working|responding)\b|"
    r"why\s+(won'?t|don'?t)\s+you\b|"
    r"(you'?re\s+not|you\s+are\s+not)\s+(telling|saying|working)\b|"
    # Vague info requests without action verbs
    r"i\s+(want|would\s+like)\s+to\s+(know|understand|learn)\b"
    r").*$",
    re.IGNORECASE | re.DOTALL,
)

# ---- Explicit action signals required per tool category ---------------------

_MEDIA_ACTION_VERBS = re.compile(
    r"\b(play|pause|resume|stop\s+music|skip|next\s+song|previous\s+song|"
    r"queue|repeat|shuffle|put\s+on|stream|blast|crank\s+up|start\s+playing)\b",
    re.IGNORECASE,
)

# Conversational blockers — if these dominate without play verbs, reject media tools
_MEDIA_CONV_BLOCKERS = re.compile(
    r"\b(about|tell|explain|describe|yourself|why|not\s+telling|"
    r"who\s+are|what\s+(is|are)|information|understand|learn)\b",
    re.IGNORECASE,
)

_DESKTOP_ACTION_VERBS = re.compile(
    r"\b(open|close|launch|start|run|quit|exit|terminate|switch\s+to|bring\s+up|"
    r"minimize|maximize|hide|show|focus|activate)\b",
    re.IGNORECASE,
)

_BROWSER_ACTION_VERBS = re.compile(
    r"\b(search|find|look\s+up|google|navigate|go\s+to|open|browse|visit|"
    r"check|look\s+for|surf)\b",
    re.IGNORECASE,
)

_SYSTEM_ACTION_VERBS = re.compile(
    r"\b(set|change|turn\s+(up|down|on|off)|adjust|enable|disable|toggle|sleep|shutdown|restart|"
    r"lock|type|write|paste|clipboard)\b",
    re.IGNORECASE,
)

_MEMORY_ACTION_VERBS = re.compile(
    r"\b(remember|note|save|store|remind|forget|delete|create\s+note|"
    r"add\s+note|set\s+reminder|schedule)\b",
    re.IGNORECASE,
)

# ---- Tool category mapping --------------------------------------------------

_TOOL_CATEGORIES: dict[str, str] = {
    # Media
    "play_youtube_music":    "media",
    "play_youtube":          "media",
    "play_youtube_playlist": "media",
    "search_youtube_music":  "media",
    # Desktop
    "open_app":              "desktop",
    "close_app":             "desktop",
    "launch_steam_game":     "desktop",
    # Browser
    "open_url":              "browser",
    "open_whatsapp_chat":    "browser",
    "open_instagram_chat":   "browser",
    # System
    "set_volume":            "system",
    "trigger_night_light":   "system",
    "sleep_pc":              "system",
    "ghost_type":            "system",
    # Info / search (lighter rules — reasonable for questions)
    "get_weather":           "info",
    "get_time":              "info",
    "calculate":             "info",
    "search_web":            "info",
    "get_news":              "info",
    "get_news_briefing":     "info",
    "capture_screen":        "info",
    # Memory
    "manage_note":           "memory",
    "set_reminder":          "memory",
    # Clipboard
    "clipboard_read":        "system",
    "clipboard_write":       "system",
}

# ---- Argument grounding checks ----------------------------------------------

# Queries that are clearly reformulations of conversational phrases,
# not actual media titles or targets.
_CONVERSATIONAL_QUERY_ARTIFACTS = [
    "about me", "about you", "yourself", "tell me", "why am i",
    "why are you", "not telling", "who are you", "what can you do",
    "i don't know", "i was talking", "the song", "some music",
    "genie", "ai assistant", "language model", "large language",
]


def _args_grounded(tool_name: str, args: dict[str, Any], user_text: str) -> tuple[bool, str]:
    """Return (grounded, reason). Checks that args are derivable from user_text."""
    if not args:
        return True, "no args"

    if tool_name in ("play_youtube_music", "play_youtube",
                     "play_youtube_playlist", "search_youtube_music"):
        query = str(args.get("query", "")).lower().strip()
        if query:
            for artifact in _CONVERSATIONAL_QUERY_ARTIFACTS:
                if artifact in query:
                    return False, (
                        f"query '{query}' is a conversational phrase, not a media title"
                    )
    return True, "ok"


# ---- Main guard class -------------------------------------------------------

class ToolIntentGuard:
    """Gates LLM tool calls with explicit-intent checks.

    Usage:
        allowed, reason = ToolIntentGuard.check(tool_name, args, raw_user_text)
        if not allowed:
            # skip tool execution
    """

    @staticmethod
    def check(
        tool_name: str,
        args: dict[str, Any],
        raw_user_text: str,
    ) -> tuple[bool, str]:
        """Return (allowed, reason)."""
        user_text = (raw_user_text or "").strip()
        user_lower = user_text.lower()
        category = _TOOL_CATEGORIES.get(tool_name, "unknown")

        # Rule 1: Pure conversational phrases block all action tools
        _ACTION_CATS = {"media", "desktop", "system", "browser", "memory"}
        if category in _ACTION_CATS:
            if _CONVERSATIONAL_PATTERNS.match(user_lower):
                reason = (
                    f"Conversational phrase detected — no action intent for '{tool_name}'. "
                    f"User said: '{user_text[:80]}'"
                )
                log.info(
                    "tool_rejected",
                    tool=tool_name,
                    category=category,
                    reason=reason,
                )
                return False, reason

        # Rule 2: Media tools require explicit playback verb
        if category == "media":
            if not _MEDIA_ACTION_VERBS.search(user_text):
                reason = (
                    f"Media tool '{tool_name}' blocked: no explicit playback intent "
                    f"(play/pause/stop/skip/queue). User said: '{user_text[:80]}'"
                )
                log.info("tool_rejected", tool=tool_name, category=category, reason=reason)
                return False, reason

        # Rule 3: Desktop tools require explicit app control verb
        if category == "desktop":
            if not _DESKTOP_ACTION_VERBS.search(user_text):
                reason = (
                    f"Desktop tool '{tool_name}' blocked: no explicit app control intent "
                    f"(open/close/launch/start). User said: '{user_text[:80]}'"
                )
                log.info("tool_rejected", tool=tool_name, category=category, reason=reason)
                return False, reason

        # Rule 4: open_url specifically requires navigation intent
        if tool_name == "open_url":
            if not _BROWSER_ACTION_VERBS.search(user_text):
                reason = (
                    f"Browser tool 'open_url' blocked: no explicit navigation intent. "
                    f"User said: '{user_text[:80]}'"
                )
                log.info("tool_rejected", tool=tool_name, category=category, reason=reason)
                return False, reason

        # Rule 5: System tools require explicit system control verb
        if category == "system":
            if not _SYSTEM_ACTION_VERBS.search(user_text):
                reason = (
                    f"System tool '{tool_name}' blocked: no explicit system control intent "
                    f"(set/change/turn/adjust/enable/disable). User said: '{user_text[:80]}'"
                )
                log.info("tool_rejected", tool=tool_name, category=category, reason=reason)
                return False, reason

        # Rule 6: Memory tools require explicit remember/note/remind verb
        if category == "memory":
            if not _MEMORY_ACTION_VERBS.search(user_text):
                reason = (
                    f"Memory tool '{tool_name}' blocked: no explicit remember/note/remind intent. "
                    f"User said: '{user_text[:80]}'"
                )
                log.info("tool_rejected", tool=tool_name, category=category, reason=reason)
                return False, reason

        # Rule 5: Argument grounding
        grounded, ground_reason = _args_grounded(tool_name, args, user_text)
        if not grounded:
            reason = f"Tool args not grounded in user text: {ground_reason}"
            log.info(
                "tool_rejected",
                tool=tool_name,
                category=category,
                reason=reason,
                args=str(args)[:120],
            )
            return False, reason

        # Allowed
        log.debug("tool_allowed", tool=tool_name, category=category)
        return True, "explicit intent confirmed"


# Convenience function
check_tool_intent = ToolIntentGuard.check
