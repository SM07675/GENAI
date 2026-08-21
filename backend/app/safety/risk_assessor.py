"""Tool Risk Assessor for Genie OS.

Implements the 5-tier deterministic risk taxonomy (Levels 0–4):
  Level 0: READ_ONLY — search, read files, system info (Safe, auto-approved)
  Level 1: LOCAL_LOW_IMPACT — open app, adjust volume, play media (Low risk)
  Level 2: LOCAL_HIGH_IMPACT — file write/overwrite, process kill (Medium risk)
  Level 3: EXTERNAL_NETWORK — send email, post messages, network egress (High risk)
  Level 4: SYSTEM_DESTRUCTIVE — file delete, system shutdown, formatting (Critical risk)
"""
from __future__ import annotations

from enum import IntEnum
from typing import Any, Dict, Optional
from dataclasses import dataclass

import structlog

log = structlog.get_logger("genie.safety.risk")


class RiskLevel(IntEnum):
    READ_ONLY = 0
    LOCAL_LOW_IMPACT = 1
    LOCAL_HIGH_IMPACT = 2
    EXTERNAL_NETWORK = 3
    SYSTEM_DESTRUCTIVE = 4


@dataclass
class RiskAssessment:
    level: RiskLevel
    requires_confirmation: bool
    reason: str
    reversible: bool = True
    safe_to_autofill: bool = True


# Pre-mapped tool risk definitions
_TOOL_RISK_MAP: Dict[str, tuple[RiskLevel, bool, str]] = {
    # Level 0: READ_ONLY
    "search_web": (RiskLevel.READ_ONLY, False, "Public search query"),
    "get_news": (RiskLevel.READ_ONLY, False, "Read news feed"),
    "get_news_briefing": (RiskLevel.READ_ONLY, False, "Read multi-topic news briefing"),
    "search_youtube_music": (RiskLevel.READ_ONLY, False, "Search music catalog"),
    "read_file": (RiskLevel.READ_ONLY, False, "Read local file contents"),
    "search_files": (RiskLevel.READ_ONLY, False, "Search file names/contents"),
    "capture_screen": (RiskLevel.READ_ONLY, False, "Capture current screen state"),
    "get_system_info": (RiskLevel.READ_ONLY, False, "Read CPU, RAM, battery telemetry"),
    "list_processes": (RiskLevel.READ_ONLY, False, "Inspect running process list"),
    "lookup_contact": (RiskLevel.READ_ONLY, False, "Read local contact address book"),

    # Level 1: LOCAL_LOW_IMPACT
    "open_app": (RiskLevel.LOCAL_LOW_IMPACT, False, "Launch a desktop application"),
    "close_app": (RiskLevel.LOCAL_LOW_IMPACT, False, "Close a running desktop application"),
    "open_url": (RiskLevel.LOCAL_LOW_IMPACT, False, "Open URL in default web browser"),
    "set_volume": (RiskLevel.LOCAL_LOW_IMPACT, False, "Adjust master speaker volume"),
    "play_youtube": (RiskLevel.LOCAL_LOW_IMPACT, False, "Start YouTube media playback"),
    "play_youtube_music": (RiskLevel.LOCAL_LOW_IMPACT, False, "Start YouTube Music playback"),
    "ghost_type": (RiskLevel.LOCAL_LOW_IMPACT, False, "Type text into active foreground window"),

    # Level 2: LOCAL_HIGH_IMPACT
    "write_file": (RiskLevel.LOCAL_HIGH_IMPACT, False, "Create or overwrite a local file"),
    "edit_file": (RiskLevel.LOCAL_HIGH_IMPACT, False, "Modify lines within a local file"),
    "run_script": (RiskLevel.LOCAL_HIGH_IMPACT, True, "Execute local code/script"),
    "kill_process": (RiskLevel.LOCAL_HIGH_IMPACT, True, "Force terminate a system process"),

    # Level 3: EXTERNAL_NETWORK
    "send_email": (RiskLevel.EXTERNAL_NETWORK, True, "Send email via external SMTP"),
    "send_whatsapp_message": (RiskLevel.EXTERNAL_NETWORK, True, "Send WhatsApp message"),
    "send_instagram_dm": (RiskLevel.EXTERNAL_NETWORK, True, "Send Instagram DM"),
    "post_http_request": (RiskLevel.EXTERNAL_NETWORK, True, "Send POST/PUT/DELETE request over the internet"),

    # Level 4: SYSTEM_DESTRUCTIVE
    "delete_file": (RiskLevel.SYSTEM_DESTRUCTIVE, True, "Permanently delete a local file"),
    "delete_directory": (RiskLevel.SYSTEM_DESTRUCTIVE, True, "Permanently delete a local directory"),
    "system_shutdown": (RiskLevel.SYSTEM_DESTRUCTIVE, True, "Power off or reboot computer"),
    "format_disk": (RiskLevel.SYSTEM_DESTRUCTIVE, True, "Format disk volume"),
}


class RiskAssessor:
    """Evaluates the risk level and safety requirements of tool executions."""

    @staticmethod
    def assess(tool_name: str, args: Optional[Dict[str, Any]] = None) -> RiskAssessment:
        """Assess the risk profile of a given tool call."""
        args = args or {}
        tool_name_lower = tool_name.lower().strip()

        if tool_name_lower in _TOOL_RISK_MAP:
            level, requires_confirmation, reason = _TOOL_RISK_MAP[tool_name_lower]
        else:
            # Dynamic heuristic for unregistered or custom tools
            if any(k in tool_name_lower for k in ("delete", "remove", "destroy", "shutdown", "format", "wipe")):
                level = RiskLevel.SYSTEM_DESTRUCTIVE
                requires_confirmation = True
                reason = f"Destructive keyword in custom tool: {tool_name}"
            elif any(k in tool_name_lower for k in ("send", "post", "upload", "publish", "email", "tweet")):
                level = RiskLevel.EXTERNAL_NETWORK
                requires_confirmation = True
                reason = f"Network egress keyword in custom tool: {tool_name}"
            elif any(k in tool_name_lower for k in ("write", "edit", "update", "modify", "exec", "kill")):
                level = RiskLevel.LOCAL_HIGH_IMPACT
                requires_confirmation = False
                reason = f"State modification keyword in custom tool: {tool_name}"
            else:
                level = RiskLevel.LOCAL_LOW_IMPACT
                requires_confirmation = False
                reason = f"Standard execution: {tool_name}"

        # Argument-level escalation: e.g. deleting a sensitive path
        if "path" in args or "file_path" in args:
            target_path = str(args.get("path") or args.get("file_path")).lower()
            if any(p in target_path for p in ("system32", "windows", "/etc", "/bin", "credentials", ".env")):
                level = RiskLevel.SYSTEM_DESTRUCTIVE
                requires_confirmation = True
                reason = f"Sensitive target path detected: {target_path}"

        reversible = level not in (RiskLevel.SYSTEM_DESTRUCTIVE, RiskLevel.EXTERNAL_NETWORK)

        return RiskAssessment(
            level=level,
            requires_confirmation=requires_confirmation,
            reason=reason,
            reversible=reversible,
        )


risk_assessor = RiskAssessor()
