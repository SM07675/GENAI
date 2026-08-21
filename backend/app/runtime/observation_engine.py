"""Observation Engine — collects evidence after actions.

After every significant action (tool execution, file creation, browser
interaction), the observation engine collects evidence about what
actually happened. This evidence feeds into the verification engine.

Observation sources:
    - Tool results (status, data)
    - Filesystem state (file exists, size, content)
    - Command output (exit code, stdout, stderr)
    - Browser state (URL, DOM elements, screenshot)
    - Application state (window title, process status)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import structlog

from .schemas import Observation, StepResult, _now_iso

log = structlog.get_logger("genie.runtime.observation")


class ObservationEngine:
    """Collects post-action evidence for verification.

    The observation engine doesn't decide success/failure — that's the
    verifier's job. It just gathers evidence.
    """

    async def observe_tool_result(
        self,
        tool_name: str,
        tool_result: Any,
        step_id: str | None = None,
    ) -> Observation:
        """Create an observation from a tool execution result."""
        status = getattr(tool_result, "status", "unknown")
        message = getattr(tool_result, "message", str(tool_result))
        data = getattr(tool_result, "data", {})

        return Observation(
            source=f"tool:{tool_name}",
            content=f"Tool '{tool_name}' returned status='{status}': {message}",
            raw_data={
                "status": status,
                "message": message,
                "data": data if isinstance(data, dict) else {},
                "tool_name": tool_name,
            },
            step_id=step_id,
        )

    async def observe_file(
        self,
        file_path: str,
        step_id: str | None = None,
    ) -> Observation:
        """Observe the state of a file after an action."""
        path = Path(file_path)
        exists = path.exists()

        raw_data: dict[str, Any] = {
            "path": str(path),
            "exists": exists,
        }

        if exists:
            stat = path.stat()
            raw_data["size_bytes"] = stat.st_size
            raw_data["is_file"] = path.is_file()
            raw_data["is_dir"] = path.is_dir()
            raw_data["extension"] = path.suffix

            content_summary = f"File exists: {path.name} ({stat.st_size} bytes)"

            # For small text files, peek at content
            if path.is_file() and stat.st_size < 10000 and path.suffix in (
                ".txt", ".md", ".json", ".csv", ".py", ".js", ".ts", ".html",
                ".css", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".log",
            ):
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")[:2000]
                    raw_data["content_preview"] = text
                    content_summary += f", preview: {text[:200]}..."
                except Exception:
                    pass
        else:
            content_summary = f"File does NOT exist: {file_path}"

        return Observation(
            source="filesystem",
            content=content_summary,
            raw_data=raw_data,
            step_id=step_id,
        )

    async def observe_directory(
        self,
        dir_path: str,
        step_id: str | None = None,
    ) -> Observation:
        """Observe the state of a directory."""
        path = Path(dir_path)
        exists = path.exists() and path.is_dir()

        raw_data: dict[str, Any] = {
            "path": str(path),
            "exists": exists,
        }

        if exists:
            try:
                entries = list(path.iterdir())
                raw_data["entry_count"] = len(entries)
                raw_data["entries"] = [
                    {"name": e.name, "is_dir": e.is_dir()} for e in entries[:50]
                ]
                content = f"Directory exists: {len(entries)} entries"
            except PermissionError:
                content = f"Directory exists but access denied: {dir_path}"
                raw_data["error"] = "permission_denied"
        else:
            content = f"Directory does NOT exist: {dir_path}"

        return Observation(
            source="filesystem",
            content=content,
            raw_data=raw_data,
            step_id=step_id,
        )

    async def observe_command(
        self,
        command: str,
        exit_code: int,
        stdout: str,
        stderr: str,
        step_id: str | None = None,
    ) -> Observation:
        """Observe the result of a command execution."""
        success = exit_code == 0

        raw_data = {
            "command": command,
            "exit_code": exit_code,
            "stdout": stdout[:5000] if stdout else "",
            "stderr": stderr[:2000] if stderr else "",
            "success": success,
        }

        if success:
            content = f"Command succeeded (exit 0): {command}"
            if stdout:
                content += f"\nOutput: {stdout[:500]}"
        else:
            content = f"Command failed (exit {exit_code}): {command}"
            if stderr:
                content += f"\nError: {stderr[:500]}"

        return Observation(
            source="command",
            content=content,
            raw_data=raw_data,
            step_id=step_id,
        )

    async def observe_web_search(
        self,
        query: str,
        results: list[dict[str, Any]],
        step_id: str | None = None,
    ) -> Observation:
        """Observe web search results."""
        raw_data = {
            "query": query,
            "result_count": len(results),
            "results": results[:10],  # keep top 10
        }

        content = f"Web search '{query}': {len(results)} results found"
        if results:
            top = results[0]
            content += f"\nTop result: {top.get('title', 'N/A')} — {top.get('url', 'N/A')}"

        return Observation(
            source="web_search",
            content=content,
            raw_data=raw_data,
            step_id=step_id,
        )

    async def observe_general(
        self,
        source: str,
        content: str,
        data: dict[str, Any] | None = None,
        step_id: str | None = None,
    ) -> Observation:
        """Create a general-purpose observation."""
        return Observation(
            source=source,
            content=content,
            raw_data=data or {},
            step_id=step_id,
        )
