"""
Relationship Memory Manager for Jenny Companion Layer.

Separate namespace from task memory: stores user preferences, running jokes/callbacks,
things the user mentioned checking back on, and conversational history context.
"""
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..event_bus import event_bus, GenieEvents

log = logging.getLogger("genie_os.relationship_memory")

_DEFAULT_STORAGE_PATH = Path(__file__).parent / "data" / "relationship_memory.json"


class RelationshipMemoryManager:
    """Manages persistent companion relationship memory across turns and sessions."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or _DEFAULT_STORAGE_PATH
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._memory_data: Dict[str, Any] = {
            "user_nickname": "Friend",
            "preferences": {},
            "running_jokes": [],
            "callbacks_pending": [],
            "favorite_topics": [],
            "recent_milestones": [],
            "last_interaction_timestamp": time.time(),
        }
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                self._memory_data.update(data)
                log.info("Relationship memory successfully loaded.")
            except Exception as e:
                log.error(f"Failed to load relationship memory: {e}")

    def save(self) -> None:
        try:
            self.storage_path.write_text(json.dumps(self._memory_data, indent=2), encoding="utf-8")
        except Exception as e:
            log.error(f"Failed to save relationship memory: {e}")

    def update_preference(self, key: str, value: Any) -> None:
        """Add or update a user preference (e.g. favorite music, preferred style)."""
        self._memory_data["preferences"][key] = value
        self.save()
        event_bus.publish_sync(GenieEvents.MEMORY_UPDATED, {
            "namespace": "relationship",
            "type": "preference_updated",
            "key": key,
            "value": value
        })

    def add_callback_topic(self, topic: str, callback_reason: str) -> None:
        """Queue a topic to follow up on during a future idle opening."""
        entry = {
            "topic": topic,
            "reason": callback_reason,
            "timestamp": time.time(),
            "status": "pending"
        }
        self._memory_data["callbacks_pending"].append(entry)
        self.save()
        event_bus.publish_sync(GenieEvents.MEMORY_UPDATED, {
            "namespace": "relationship",
            "type": "callback_queued",
            "entry": entry
        })

    def add_running_joke(self, joke_context: str) -> None:
        """Store a running joke or callback phrase."""
        if joke_context not in self._memory_data["running_jokes"]:
            self._memory_data["running_jokes"].append(joke_context)
            self.save()

    def get_relationship_context(self) -> Dict[str, Any]:
        """Returns condensed relationship context string and metadata for LLM prompt framing."""
        pref_summary = ", ".join(f"{k}: {v}" for k, v in self._memory_data["preferences"].items()) or "None recorded yet."
        pending_callbacks = [c["topic"] for c in self._memory_data["callbacks_pending"] if c["status"] == "pending"]
        
        return {
            "nickname": self._memory_data.get("user_nickname", "Friend"),
            "preferences": self._memory_data.get("preferences", {}),
            "preferences_summary": pref_summary,
            "running_jokes": self._memory_data.get("running_jokes", []),
            "pending_callbacks": pending_callbacks,
            "favorite_topics": self._memory_data.get("favorite_topics", []),
        }

    def pop_pending_callback(self) -> Optional[Dict[str, Any]]:
        """Retrieves and marks the oldest pending callback as processed for proactive suggestion."""
        for cb in self._memory_data["callbacks_pending"]:
            if cb["status"] == "pending":
                cb["status"] = "discussed"
                self.save()
                return cb
        return None


relationship_memory = RelationshipMemoryManager()
