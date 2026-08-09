"""
Unified ContextSnapshot for Genie OS.

Consolidates desktop state, user state, memory context, and active workspace
into a single snapshot object rebuilt once per turn.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from .engine import context_engine
from ..memory.relationship_memory import relationship_memory


@dataclass
class ContextSnapshot:
    """Unified per-turn state snapshot passed to all agents."""

    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"))
    active_app: str = "Unknown"
    active_window: str = "Unknown"
    active_tab: Optional[str] = None
    system_summary: str = ""
    user_nickname: str = "Friend"
    preferences: Dict[str, Any] = field(default_factory=dict)
    pending_callbacks: List[str] = field(default_factory=list)
    recent_events: List[Dict[str, Any]] = field(default_factory=list)

    def to_prompt_string(self) -> str:
        """Render snapshot into a clean system prompt context block."""
        lines = [
            f"=== CONTEXT SNAPSHOT [{self.timestamp}] ===",
            f"Active Application: {self.active_app}",
            f"Active Window: {self.active_window}",
        ]
        if self.active_tab:
            lines.append(f"Active Tab/Document: {self.active_tab}")
        if self.system_summary:
            lines.append(f"System State: {self.system_summary}")

        lines.append(f"User Nickname: {self.user_nickname}")
        if self.preferences:
            pref_str = ", ".join(f"{k}: {v}" for k, v in self.preferences.items())
            lines.append(f"User Preferences: {pref_str}")
        if self.pending_callbacks:
            lines.append(f"Pending Follow-ups: {', '.join(self.pending_callbacks)}")

        return "\n".join(lines)


def get_turn_context_snapshot() -> ContextSnapshot:
    """Build and return a fresh ContextSnapshot for the current turn."""
    desktop_summary = context_engine.get_current_context_summary()
    rel_ctx = relationship_memory.get_relationship_context()

    # Parse app/window from engine summary if available
    active_app = "Desktop"
    active_window = "Workspace"
    if desktop_summary and ":" in desktop_summary:
        parts = desktop_summary.split("\n")[0].split(":", 1)
        if len(parts) > 1:
            active_app = parts[0].strip()
            active_window = parts[1].strip()

    return ContextSnapshot(
        active_app=active_app,
        active_window=active_window,
        system_summary=desktop_summary,
        user_nickname=rel_ctx.get("nickname", "Friend"),
        preferences=rel_ctx.get("preferences", {}),
        pending_callbacks=rel_ctx.get("pending_callbacks", []),
    )
