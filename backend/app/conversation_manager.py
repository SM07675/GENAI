"""Conversation manager for multi-turn, context-aware interactions.

Enhances Genie with:
- Conversation context tracking (pronouns, references)
- Follow-up question handling
- Smart interruption support
- Conversation summarization for long threads
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

log = logging.getLogger("genie.conversation")


class ConversationContext:
    """Tracks context across multiple turns for natural follow-ups."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.current_topic: str | None = None
        self.last_entity: dict[str, Any] = {}  # last mentioned location, person, app, etc.
        self.last_action: str | None = None
        self.pending_clarification: str | None = None
        self.conversation_start = datetime.now()
        self.turn_count = 0

    def update_context(self, user_text: str, tool_calls: list[dict]):
        """Extract context from user input and tool calls."""
        self.turn_count += 1

        # Extract entities from user text
        self._extract_entities(user_text)

        # Track last action from tool calls
        if tool_calls:
            last_tool = tool_calls[-1]
            self.last_action = last_tool.get("name")
            
            # Extract key entities from tool arguments
            args = last_tool.get("arguments", {})
            if "location" in args:
                self.last_entity["location"] = args["location"]
            if "query" in args:
                self.last_entity["query"] = args["query"]
            if "app" in args or "name" in args:
                self.last_entity["app"] = args.get("app") or args.get("name")

    def _extract_entities(self, text: str):
        """Simple entity extraction from user text."""
        text_lower = text.lower()

        # Location indicators
        location_patterns = [
            r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'\bat\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        ]
        for pattern in location_patterns:
            match = re.search(pattern, text)
            if match:
                self.last_entity["location"] = match.group(1)
                break

    def resolve_references(self, user_text: str) -> str:
        """Resolve pronouns and references using context.
        
        Examples:
        - "weather there" -> "weather in London" (if last location was London)
        - "play another" -> "play another song" (if last action was play_youtube)
        - "what about tomorrow" -> add temporal context
        """
        text_lower = user_text.lower()
        resolved = user_text

        # Resolve location references
        if any(word in text_lower for word in ["there", "that place", "same place"]):
            if "location" in self.last_entity:
                resolved = resolved.replace("there", f"in {self.last_entity['location']}")
                resolved = resolved.replace("that place", f"in {self.last_entity['location']}")

        # Resolve "another one" / "play another"
        if "another" in text_lower or "more" in text_lower:
            if self.last_action == "play_youtube" and "query" in self.last_entity:
                resolved = f"play more {self.last_entity['query']}"
            elif self.last_action == "search_web" and "query" in self.last_entity:
                resolved = f"search more about {self.last_entity['query']}"

        # Resolve app references
        if any(word in text_lower for word in ["it", "that app", "close it"]):
            if "app" in self.last_entity:
                resolved = resolved.replace(" it", f" {self.last_entity['app']}")
                resolved = resolved.replace("that app", self.last_entity['app'])

        # Add context note if we resolved anything
        if resolved != user_text:
            log.info(f"Resolved reference: '{user_text}' -> '{resolved}'")
            return f"[Context: {resolved}] {user_text}"

        return user_text

    def should_summarize(self) -> bool:
        """Check if conversation is getting long and needs summarization."""
        return self.turn_count > 20

    def get_context_summary(self) -> str:
        """Generate a brief context summary for the system prompt."""
        parts = []
        
        if self.current_topic:
            parts.append(f"Current topic: {self.current_topic}")
        
        if self.last_action:
            parts.append(f"Last action: {self.last_action}")
        
        if self.last_entity:
            entity_str = ", ".join(f"{k}: {v}" for k, v in self.last_entity.items())
            parts.append(f"Context entities: {entity_str}")

        if parts:
            return "## CONVERSATION CONTEXT\n" + "\n".join(parts) + "\n\n"
        return ""


class ConversationManager:
    """Manages all active conversation contexts."""

    MAX_CONTEXTS = 50  # H7 fix: cap total context count

    def __init__(self):
        self.contexts: dict[str, ConversationContext] = {}

    def get_context(self, session_id: str) -> ConversationContext:
        """Get or create conversation context for a session."""
        if session_id not in self.contexts:
            # Auto-cleanup if at capacity
            if len(self.contexts) >= self.MAX_CONTEXTS:
                self.cleanup_old_sessions(max_age_hours=1)
            # If still at capacity after cleanup, evict oldest
            if len(self.contexts) >= self.MAX_CONTEXTS:
                oldest_sid = min(
                    self.contexts,
                    key=lambda sid: self.contexts[sid].conversation_start,
                )
                del self.contexts[oldest_sid]
                log.info(f"Evicted oldest conversation context: {oldest_sid}")
            self.contexts[session_id] = ConversationContext(session_id)
        return self.contexts[session_id]

    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """Remove contexts older than max_age_hours. Returns count removed."""
        from datetime import timedelta
        now = datetime.now()
        expired = [
            sid for sid, ctx in self.contexts.items()
            if (now - ctx.conversation_start).total_seconds() > max_age_hours * 3600
        ]
        for sid in expired:
            del self.contexts[sid]
            log.info(f"Cleaned up expired conversation context: {sid}")
        return len(expired)


# Global conversation manager instance
conversation_manager = ConversationManager()
