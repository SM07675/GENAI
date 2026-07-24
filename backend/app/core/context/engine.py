"""
Context Engine for Genie OS.
Maintains the immediate state of the user's environment.
"""
from typing import Dict, Any, Optional
import time
from datetime import datetime
from ..event_bus import event_bus
import logging

log = logging.getLogger("genie_os.context")

class ContextEngine:
    def __init__(self):
        self.state: Dict[str, Any] = {
            "active_window": None,
            "clipboard": None,
            "browser_url": None,
            "current_project": None,
            "last_updated": time.time(),
        }
        self.history: list[Dict[str, Any]] = []
        
        # Subscribe to context updates
        event_bus.subscribe("context.update", self._handle_update)
        event_bus.subscribe("perception.screen", self._handle_screen)
        event_bus.subscribe("perception.clipboard", self._handle_clipboard)

    async def _handle_update(self, event: Dict[str, Any]) -> None:
        updates = event.get("updates", {})
        self._apply_updates(updates)

    async def _handle_screen(self, event: Dict[str, Any]) -> None:
        updates = {
            "active_window": event.get("window_title"),
            "browser_url": event.get("browser_url") # If detected by screen perception
        }
        self._apply_updates({k: v for k, v in updates.items() if v is not None})
        
    async def _handle_clipboard(self, event: Dict[str, Any]) -> None:
        self._apply_updates({"clipboard": event.get("content")})

    def _apply_updates(self, updates: Dict[str, Any]) -> None:
        if not updates:
            return
            
        # Snapshot previous state if significant change
        self._snapshot_state()
        
        self.state.update(updates)
        self.state["last_updated"] = time.time()
        log.debug(f"Context updated: {updates.keys()}")
        
    def _snapshot_state(self) -> None:
        # Keep last 50 states
        snapshot = self.state.copy()
        snapshot["timestamp"] = datetime.now().isoformat()
        self.history.append(snapshot)
        if len(self.history) > 50:
            self.history.pop(0)

    def get_current_context_summary(self) -> str:
        """Returns a string representation of the current context for LLM injection."""
        summary = ["--- Current User Context ---"]
        if self.state.get("active_window"):
            summary.append(f"Active Window: {self.state['active_window']}")
        if self.state.get("browser_url"):
            summary.append(f"Browser URL: {self.state['browser_url']}")
        if self.state.get("clipboard"):
            clip = self.state['clipboard']
            if len(clip) > 100:
                clip = clip[:100] + "..."
            summary.append(f"Clipboard: {clip}")
        if self.state.get("current_project"):
            summary.append(f"Current Project: {self.state['current_project']}")
            
        if len(summary) == 1:
            return "--- Current User Context ---\n(No active context available)"
            
        return "\n".join(summary)

    def snapshot(self) -> Dict[str, Any]:
        """Return a structured context snapshot for APIs and agents."""
        return {
            "state": self.state.copy(),
            "history": list(self.history[-10:]),
            "summary": self.get_current_context_summary(),
        }

context_engine = ContextEngine()
