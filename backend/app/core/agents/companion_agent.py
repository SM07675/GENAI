"""
Companion Agent (15th Agent — Jenny Companion Layer).

Wraps the output of raw specialist agents to apply personality framing,
relationship memory context, prosody cue tags for TTS, and rate-limited
proactive suggestions.
"""
import logging
import time
from typing import Any, Dict, Optional
from ..memory.relationship_memory import relationship_memory
from ..event_bus import event_bus, GenieEvents

log = logging.getLogger("genie_os.companion_agent")

_PROACTIVE_SUGGESTION_COOLDOWN_SEC = 300  # Max 1 proactive suggestion per 5-minute idle window


class CompanionAgent:
    """The 15th agent layer wrapping raw responses with companion personality & initiative."""

    def __init__(self):
        self.last_suggestion_time = 0.0

    def process_response(
        self,
        raw_text: str,
        user_input: str,
        is_idle_opening: bool = False
    ) -> Dict[str, Any]:
        """Wraps the raw LLM response with companion persona cue tags and optional proactive suggestions.

        Returns:
            Dict containing:
                - text: Final response text (with prosody tag)
                - cue_tag: Selected emotional prosody cue tag
                - suggestion_added: bool
        """
        rel_context = relationship_memory.get_relationship_context()
        cue_tag = self._determine_cue_tag(raw_text, user_input)

        formatted_text = raw_text.strip()

        # Check if prosody tag is already present, else inject tag
        if not formatted_text.startswith("[["):
            formatted_text = f"[[{cue_tag}]] {formatted_text}"

        suggestion_added = False
        now = time.time()

        # Check for proactive suggestion queue if rate limit allows
        if is_idle_opening and (now - self.last_suggestion_time >= _PROACTIVE_SUGGESTION_COOLDOWN_SEC):
            pending_cb = relationship_memory.pop_pending_callback()
            if pending_cb:
                suggestion_suffix = f"\n\nBy the way, I was wondering — did that update regarding {pending_cb['topic']} turn out okay?"
                formatted_text += suggestion_suffix
                self.last_suggestion_time = now
                suggestion_added = True
                
                event_bus.publish_sync(GenieEvents.SUGGESTION_QUEUED, {
                    "topic": pending_cb["topic"],
                    "reason": pending_cb["reason"]
                })

        event_bus.publish_sync(GenieEvents.RESPONSE_GENERATED, {
            "text": formatted_text,
            "cue_tag": cue_tag,
            "proactive_suggestion": suggestion_added
        })

        return {
            "text": formatted_text,
            "cue_tag": cue_tag,
            "suggestion_added": suggestion_added
        }

    def _determine_cue_tag(self, text: str, user_input: str) -> str:
        """Selects appropriate prosody cue tag based on sentiment & context."""
        lower_t = text.lower()
        lower_u = user_input.lower()

        if any(w in lower_t or w in lower_u for w in ["error", "fail", "wrong", "cannot", "warning"]):
            return "thoughtful"
        elif any(w in lower_t or w in lower_u for w in ["urgent", "quick", "immediately", "alert"]):
            return "urgent"
        elif any(w in lower_t for w in ["haha", "funny", "awesome", "great", "play"]):
            return "playful"
        else:
            return "warm"


companion_agent = CompanionAgent()
