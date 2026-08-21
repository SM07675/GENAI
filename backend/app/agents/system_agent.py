"""System Agent — safe system operations (apps, volume, screenshots, etc.).

Wraps existing system_control, apps, and screen tools.
"""
from __future__ import annotations
from typing import Any
from .base_agent import BaseAgent
from ..runtime.schemas import Observation, PlanStep, StepResult, TaskContext


class SystemAgent(BaseAgent):
    name = "system"
    description = "System operations: launch/close apps, volume, screenshots, system control"
    capabilities = [
        "app_launch", "app_close", "volume_control", "screenshot",
        "system_control", "night_light", "sleep", "window_focus",
    ]
    tools = [
        "open_app", "close_app", "set_volume", "capture_screen",
        "trigger_night_light", "sleep_pc", "ghost_type",
    ]

    async def execute(self, step: PlanStep, context: TaskContext) -> StepResult:
        observations: list[Observation] = []
        desc = (step.description or step.title).lower()

        # Determine which tool to use
        tool_name = None
        args: dict[str, Any] = {}

        if any(w in desc for w in ["open", "launch", "start"]):
            tool_name = "open_app"
            app_name = self._extract_app_name(desc)
            args = {"name": app_name} if app_name else {}
        elif any(w in desc for w in ["close", "quit", "exit", "kill"]):
            tool_name = "close_app"
            app_name = self._extract_app_name(desc)
            args = {"name": app_name} if app_name else {}
        elif "volume" in desc:
            tool_name = "set_volume"
            import re
            num = re.search(r'\d+', desc)
            args = {"percent": int(num.group()) if num else 50}
        elif any(w in desc for w in ["screenshot", "screen", "capture"]):
            tool_name = "capture_screen"
        elif any(w in desc for w in ["night"]):
            tool_name = "trigger_night_light"
        elif any(w in desc for w in ["sleep"]):
            tool_name = "sleep_pc"
        elif any(w in desc for w in ["type", "ghost"]):
            tool_name = "ghost_type"
            args = {"text": step.description or ""}
        elif any(w in desc for w in ["system info", "info", "specs", "telemetry", "status"]):
            # Direct system info gathering
            import platform
            import psutil
            cpu_pct = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            sys_data = {
                "platform": platform.platform(),
                "processor": platform.processor(),
                "cpu_percent": cpu_pct,
                "memory_total_gb": round(mem.total / (1024 ** 3), 1),
                "memory_used_pct": mem.percent,
            }
            obs = self._make_observation(
                "system", f"CPU: {cpu_pct}%, RAM: {mem.percent}% used", data=sys_data, step_id=step.step_id,
            )
            observations.append(obs)
            return StepResult(
                success=True,
                message=f"System: CPU {cpu_pct}%, RAM {mem.percent}% used on {platform.system()}",
                data={"system_info": sys_data},
                observations=observations,
            )

        if tool_name:
            try:
                result, obs = await self._execute_tool(tool_name, args, context)
                observations.append(obs)
                return StepResult(
                    success=result.status in ("ok", "success"),
                    message=result.message,
                    data={"tool": tool_name, "result": result.data or {}},
                    observations=observations,
                )
            except Exception as exc:
                return StepResult(success=False, message=f"System action failed: {exc}")

        return StepResult(
            success=False,
            message=f"Could not determine system action for: {step.title}",
        )

    @staticmethod
    def _extract_app_name(text: str) -> str | None:
        known_apps = [
            "chrome", "firefox", "edge", "spotify", "discord", "steam",
            "notepad", "calculator", "terminal", "cmd", "powershell",
            "explorer", "code", "vscode", "word", "excel", "powerpoint",
            "outlook", "teams", "slack", "zoom", "obs", "vlc",
        ]
        for app in known_apps:
            if app in text:
                return app
        words = text.split()
        for i, w in enumerate(words):
            if w in ("open", "launch", "start", "close", "quit"):
                if i + 1 < len(words):
                    return words[i + 1]
        return None
