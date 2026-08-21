"""Continuous Context Service for Genie AI OS.

Maintains live situational awareness of what the user is doing without
dumping raw dumps into LLM prompts. Implements intelligent relevance filtering.

Sources:
- Active foreground application & window title (Windows win32/pygetwindow)
- Current workspace / git repository
- Recent files & clipboard state
- System resource metrics (CPU, RAM, GPU, battery)
- Active project & task focus
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil
import structlog

log = structlog.get_logger("genie.runtime.context")


@dataclass
class SystemMetrics:
    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    battery_percent: Optional[float] = None
    power_plugged: Optional[bool] = None


@dataclass
class RichContextSnapshot:
    """Comprehensive environment snapshot."""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"))
    active_app: str = "Desktop"
    active_window: str = "Workspace"
    active_project: Optional[str] = None
    recent_files: List[str] = field(default_factory=list)
    system_metrics: SystemMetrics = field(default_factory=SystemMetrics)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    active_task_summary: Optional[str] = None
    working_directory: str = field(default_factory=os.getcwd)

    def to_prompt_string(self, max_length: int = 1000) -> str:
        """Render a concise, high-signal system prompt block."""
        lines = [
            f"=== DESKTOP CONTEXT [{self.timestamp}] ===",
            f"Active Window: {self.active_app} — {self.active_window}",
        ]
        if self.active_project:
            lines.append(f"Active Project: {self.active_project}")
        if self.active_task_summary:
            lines.append(f"Ongoing Mission: {self.active_task_summary}")
        lines.append(
            f"System: CPU {self.system_metrics.cpu_percent:.0f}%, RAM {self.system_metrics.ram_percent:.0f}% ({self.system_metrics.ram_used_gb:.1f}/{self.system_metrics.ram_total_gb:.1f}GB)"
        )
        if self.recent_files:
            lines.append(f"Recent Files: {', '.join(self.recent_files[:3])}")
        
        rendered = "\n".join(lines)
        return rendered[:max_length]


class ContextService:
    """Continuously observes desktop state and synthesizes filtered snapshots."""

    def __init__(self):
        self._cached_snapshot: Optional[RichContextSnapshot] = None
        self._last_sample_time: float = 0.0
        self._sample_interval: float = 2.0  # seconds between OS polls

    def get_system_metrics(self) -> SystemMetrics:
        """Collect current system resource usage."""
        try:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            battery = psutil.sensors_battery()
            return SystemMetrics(
                cpu_percent=cpu,
                ram_percent=mem.percent,
                ram_used_gb=mem.used / (1024 ** 3),
                ram_total_gb=mem.total / (1024 ** 3),
                battery_percent=battery.percent if battery else None,
                power_plugged=battery.power_plugged if battery else None,
            )
        except Exception as exc:
            log.debug("metrics_sampling_error", error=str(exc))
            return SystemMetrics()

    def get_active_window_info(self) -> tuple[str, str]:
        """Detect foreground window and process name on Windows."""
        try:
            if os.name == 'nt':
                import win32gui
                import win32process

                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    title = win32gui.GetWindowText(hwnd) or "Desktop"
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    try:
                        proc = psutil.Process(pid)
                        app_name = proc.name().replace(".exe", "").capitalize()
                    except Exception:
                        app_name = "Unknown"
                    return app_name, title
        except Exception as exc:
            log.debug("window_detection_error", error=str(exc))
        return "Desktop", "Workspace"

    async def get_snapshot(self, active_task_summary: Optional[str] = None) -> RichContextSnapshot:
        """Produce a fresh or cached context snapshot."""
        now = time.time()
        if self._cached_snapshot is None or (now - self._last_sample_time) > self._sample_interval:
            app_name, title = await asyncio.to_thread(self.get_active_window_info)
            metrics = await asyncio.to_thread(self.get_system_metrics)

            self._cached_snapshot = RichContextSnapshot(
                active_app=app_name,
                active_window=title,
                system_metrics=metrics,
                active_task_summary=active_task_summary,
                working_directory=os.getcwd(),
            )
            self._last_sample_time = now

        if active_task_summary:
            self._cached_snapshot.active_task_summary = active_task_summary

        return self._cached_snapshot


# Global singleton
context_service = ContextService()
