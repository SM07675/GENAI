"""
Unified ContextSnapshot for Genie OS.

Consolidates desktop state, user state, memory context, and active workspace
into a single snapshot object rebuilt once per turn.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .engine import context_engine
from .fusion import context_fusion, FusedContext
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
    fused: Optional[FusedContext] = None

    def to_prompt_string(self) -> str:
        """Render snapshot into a clean system prompt context block."""
        if self.fused and self.fused.relevant_items:
            return self.fused.to_prompt_block()

        lines = [
            f"=== CONTEXT SNAPSHOT [{self.timestamp}] ===",
            f"Active Application: {self.active_app}",
            f"Active Window: {self.active_window}",
        ]
        if self.active_tab:
            lines.append(f"Active Tab/Document: {self.active_tab}")
        if self.system_summary and "No active context available" not in self.system_summary:
            lines.append(f"System State: {self.system_summary}")

        lines.append(f"User Nickname: {self.user_nickname}")
        if self.preferences:
            pref_str = ", ".join(f"{k}: {v}" for k, v in self.preferences.items())
            lines.append(f"User Preferences: {pref_str}")
        if self.pending_callbacks:
            lines.append(f"Pending Follow-ups: {', '.join(self.pending_callbacks)}")

        return "\n".join(lines)


def get_turn_context_snapshot(query: str = "") -> ContextSnapshot:
    """Build and return a fresh ContextSnapshot for the current turn."""
    desktop_summary = context_engine.get_current_context_summary()
    rel_ctx = relationship_memory.get_relationship_context()

    # Try win32 foreground window detection first
    active_app = "Desktop"
    active_window = "Workspace"
    app_category = "general"

    try:
        from ...companion.capture import _get_win32_active_window, _classify_process
        win_info = _get_win32_active_window()
        if win_info:
            active_app = win_info.process_name or active_app
            active_window = win_info.title or active_window
            app_category = _classify_process(win_info.process_name, win_info.title)
    except Exception:
        # Fallback to context_engine state
        st = context_engine.state
        if st.get("active_window"):
            active_window = st["active_window"]
        if desktop_summary and ":" in desktop_summary:
            parts = desktop_summary.split("\n")[0].split(":", 1)
            if len(parts) > 1:
                active_app = parts[0].strip()

    app_state = {
        "active_app": active_app,
        "window_title": active_window,
        "category": app_category,
    }

    # Perform context fusion if query is provided
    fused = None
    if query:
        fused = context_fusion.fuse(
            query=query,
            app_state=app_state,
            preferences=rel_ctx.get("preferences"),
            clipboard=context_engine.state.get("clipboard"),
        )

    return ContextSnapshot(
        active_app=active_app,
        active_window=active_window,
        system_summary=desktop_summary,
        user_nickname=rel_ctx.get("nickname", "Friend"),
        preferences=rel_ctx.get("preferences", {}),
        pending_callbacks=rel_ctx.get("pending_callbacks", []),
        fused=fused,
    )
