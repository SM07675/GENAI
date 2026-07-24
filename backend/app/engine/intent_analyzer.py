"""Fast local intent classifier for deterministic command handling.

Enhanced from the legacy ``local_intent_router.py`` with:
- Follow-up detection: "what about X", "tell me more"
- Interruption detection: "stop", "wait", "Genie" during speech
- Clarification detection: "what?", "huh?", "say again"
- Volume control: "louder", "quieter"
- Confirmation: "yes", "no", "do it"
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Optional


class IntentType(str, Enum):
    """Classified intent types."""
    NONE = "none"               # No match — route to LLM
    STOP_AUDIO = "stop_audio"
    PLAY_MUSIC = "play_music"
    CLEAR_HISTORY = "clear_history"
    FOLLOW_UP = "follow_up"
    REPEAT = "repeat"
    INTERRUPT = "interrupt"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    CONFIRM_YES = "confirm_yes"
    CONFIRM_NO = "confirm_no"
    GREETING = "greeting"
    WAKE_ONLY = "wake_only"     # Just "Hey Genie" with nothing after


# Regex patterns for each intent
_PATTERNS: dict[IntentType, list[str]] = {
    IntentType.STOP_AUDIO: [
        r"^(stop|pause|quiet|shh|shut up|cancel|be quiet|enough|that's enough)( audio| music| talking| speaking| it)?\.?$",
    ],
    IntentType.PLAY_MUSIC: [
        r"^(play|resume)( some)?( music| songs?| audio)\.?$",
    ],
    IntentType.CLEAR_HISTORY: [
        r"^(clear|forget|reset|delete|wipe)( my| all| the)?( history| memory| conversation| chat)\.?$",
    ],
    IntentType.REPEAT: [
        r"^(what|huh|say (that|it) again|repeat( that)?|come again|pardon|sorry what)[\?\.]?$",
    ],
    IntentType.INTERRUPT: [
        r"^(stop|wait|hold on|one (sec|second|moment)|genie stop)\.?$",
    ],
    IntentType.VOLUME_UP: [
        r"^(louder|volume up|speak louder|turn (it )?up)\.?$",
    ],
    IntentType.VOLUME_DOWN: [
        r"^(quieter|softer|volume down|speak softer|turn (it )?down)\.?$",
    ],
    IntentType.CONFIRM_YES: [
        r"^(yes|yeah|yep|sure|okay|ok|do it|go ahead|confirm|proceed|affirmative)\.?$",
    ],
    IntentType.CONFIRM_NO: [
        r"^(no|nah|nope|cancel|don't|never mind|stop|abort)\.?$",
    ],
    IntentType.GREETING: [
        r"^(hello|hi|hey|good (morning|afternoon|evening|night)|how are you|what's up|sup)[\?\.]?$",
    ],
}

# Follow-up indicators (these are NOT deterministic intents —
# they just tag the query as a follow-up so context is preserved)
_FOLLOW_UP_PATTERNS = [
    r"^(what about|how about|and|also|tell me more|more about|another|next|what else)",
    r"^(what|where|when|who|how|why) (is|are|was|were|did|does|do|can|could|should|would) (it|that|this|they|he|she)",
    r"\b(it|that|this|those|these|they|them|there|the same)\b",
]

# Wake phrases to strip
_WAKE_PHRASES = [
    "hey genie", "okay genie", "ok genie", "hi genie", "hello genie",
    "hey genie,", "okay genie,", "ok genie,", "hi genie,", "hello genie,",
]


class IntentAnalyzer:
    """Fast local intent classifier."""

    def classify(self, text: str) -> IntentType:
        """Classify user text into an intent.

        Returns IntentType.NONE if no pattern matches (route to LLM).
        """
        clean = self._clean(text)
        if not clean:
            return IntentType.WAKE_ONLY

        for intent_type, patterns in _PATTERNS.items():
            for pattern in patterns:
                if re.match(pattern, clean, re.IGNORECASE):
                    return intent_type

        return IntentType.NONE

    def is_follow_up(self, text: str) -> bool:
        """Check if the text appears to be a follow-up question."""
        clean = self._clean(text)
        if not clean:
            return False
        for pattern in _FOLLOW_UP_PATTERNS:
            if re.search(pattern, clean, re.IGNORECASE):
                return True
        return False

    def strip_wake_phrase(self, text: str) -> str:
        """Remove wake phrase from the start of user text."""
        t = text.strip()
        lower = t.lower()
        for phrase in _WAKE_PHRASES:
            if lower.startswith(phrase):
                t = t[len(phrase):].lstrip(", ").strip()
                break
        return t

    def _clean(self, text: str) -> str:
        """Normalize text for pattern matching."""
        t = self.strip_wake_phrase(text)
        t = re.sub(r'[^\w\s\?\.]', '', t.lower()).strip()
        return t
