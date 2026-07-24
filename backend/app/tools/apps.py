"""App & game control tools.

Windows-first: dynamically finds apps and games (Steam, Epic, Xbox, regular apps)
by parsing Start Menu shortcuts and Desktop shortcuts.
"""
from __future__ import annotations

import os
import glob
import shutil
import subprocess
import sys
from difflib import SequenceMatcher

from ..schemas import ToolResult
from .registry import tool
import structlog

log = structlog.get_logger("genie.tools.apps")

_SHORTCUTS_CACHE: dict[str, str] = {}

def _build_shortcut_cache() -> None:
    if _SHORTCUTS_CACHE:
        return
    if sys.platform != "win32":
        return

    # Places to look for shortcuts
    paths = [
        os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%USERPROFILE%\Desktop"),
        os.path.expandvars(r"%PUBLIC%\Desktop"),
    ]
    
    # We look for .lnk (standard shortcut) and .url (Steam shortcuts)
    for p in paths:
        if not os.path.exists(p):
            continue
        for ext in ("*.lnk", "*.url"):
            for shortcut_path in glob.iglob(os.path.join(p, "**", ext), recursive=True):
                filename = os.path.basename(shortcut_path)
                name_without_ext = os.path.splitext(filename)[0]
                name_lower = name_without_ext.lower().strip()
                _SHORTCUTS_CACHE[name_lower] = shortcut_path

def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def _find_best_match(name: str) -> tuple[str, str] | None:
    """Finds the best matching shortcut in the cache."""
    _build_shortcut_cache()
    if not _SHORTCUTS_CACHE:
        return None
        
    name_lower = name.lower().strip()
    
    # Exact match first
    if name_lower in _SHORTCUTS_CACHE:
        return name_lower, _SHORTCUTS_CACHE[name_lower]
        
    # Contains match (e.g., "cyberpunk" in "cyberpunk 2077")
    matches = []
    for shortcut_name, path in _SHORTCUTS_CACHE.items():
        if name_lower in shortcut_name or shortcut_name in name_lower:
            matches.append((shortcut_name, path))
            
    if matches:
        # Sort by length difference to find the closest match
        matches.sort(key=lambda x: abs(len(x[0]) - len(name_lower)))
        return matches[0]
        
    # Fallback to fuzzy matching
    best_score = 0.0
    best_match = None
    for shortcut_name, path in _SHORTCUTS_CACHE.items():
        score = _similarity(name_lower, shortcut_name)
        if score > best_score:
            best_score = score
            best_match = (shortcut_name, path)
            
    if best_score > 0.6:  # Threshold for fuzzy matching
        return best_match
    return None

def _launch(command: str) -> None:
    if sys.platform == "win32":
        os.startfile(command)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", command])
    else:
        subprocess.Popen(["xdg-open", command])

# Fallback known commands for built-in UWP/system apps that don't have standard shortcuts
_SYSTEM_APPS = {
    "calculator": "calc.exe",
    "notepad": "notepad.exe",
    "settings": "ms-settings:",
    "clock": "ms-clock:",
    "calendar": "outlookcal:",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "task manager": "taskmgr.exe",
    "file explorer": "explorer.exe",
    "paint": "mspaint.exe",
    "snipping tool": "SnippingTool.exe",
}

@tool
def open_app(name: str) -> ToolResult:
    """Open a desktop application or game by its friendly name.
    Supports Steam games, Epic Games, Xbox games, and regular installed software.

    :param name: Friendly app or game name (e.g. 'chrome', 'whatsapp', 'palworld', 'gta v').
    """
    if not name:
        return ToolResult(status="error", message="No app name provided.")

    name_lower = name.lower().strip()

    # 1. Check built-in system apps first
    if name_lower in _SYSTEM_APPS:
        try:
            _launch(_SYSTEM_APPS[name_lower])
            return ToolResult(status="ok", message=f"Opening {name}.", data={"app": name})
        except Exception as e:
            return ToolResult(status="error", message=f"Couldn't start {name}: {e}")

    # 2. Check installed shortcuts (covers Steam, Epic, Xbox, standard apps)
    if sys.platform == "win32":
        match = _find_best_match(name)
        if match:
            shortcut_name, shortcut_path = match
            try:
                _launch(shortcut_path)
                return ToolResult(status="ok", message=f"Opening {shortcut_name}.", data={"app": shortcut_name})
            except Exception as e:
                return ToolResult(status="error", message=f"Couldn't launch {shortcut_name}: {e}")

    # 3. Fallback: PATH lookup
    guessed = name_lower if name_lower.endswith(".exe") else f"{name_lower}.exe"
    if shutil.which(guessed):
        try:
            subprocess.Popen(
                guessed, shell=True,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            return ToolResult(status="ok", message=f"Opening {name}.", data={"app": name})
        except Exception as e:
            return ToolResult(status="error", message=f"Couldn't start {name}: {e}")

    # Return suggestion so orchestrator uses search_web to find it
    return ToolResult(
        status="not_found",
        message=f"I couldn't find '{name}' installed on this PC.",
        data={"app": name},
    )

@tool
def close_app(name: str, force: bool = True) -> ToolResult:
    """Close a running application by name (e.g. chrome, spotify, discord).

    :param name: App name or process name.
    :param force: Kill immediately if true, otherwise terminate gracefully.
    """
    if not name:
        return ToolResult(status="error", message="No app name provided.")

    try:
        import psutil
    except ImportError:
        return ToolResult(status="error", message="psutil is not installed.")

    name_lower = name.lower().strip()
    exe_name = name_lower if name_lower.endswith(".exe") else f"{name_lower}.exe"

    killed: list[str] = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            pname = (proc.info.get("name") or "").lower()
            if pname == exe_name or name_lower in pname:
                proc.kill() if force else proc.terminate()
                killed.append(proc.info["name"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not killed:
        return ToolResult(status="ok", message=f"{name} wasn't running.", data={"closed": []})
    return ToolResult(
        status="ok",
        message=f"Closed {name}.",
        data={"app": name, "closed": killed},
    )

@tool
def launch_steam_game(game: str) -> ToolResult:
    """Launch a Steam game by name or App ID.
    
    :param game: The name of the game (e.g. 'palworld') or its Steam App ID.
    """
    if not game:
        return ToolResult(status="error", message="No game provided.")
    
    # Check if it's a numeric ID
    if game.isdigit():
        try:
            if sys.platform == "win32":
                os.startfile(f"steam://rungameid/{game}")
            else:
                subprocess.Popen(["xdg-open" if sys.platform != "darwin" else "open", f"steam://rungameid/{game}"])
            return ToolResult(status="ok", message=f"Launching Steam game ID {game}.")
        except Exception as e:
            return ToolResult(status="error", message=f"Couldn't launch: {e}")
            
    # Try finding in shortcut cache
    match = _find_best_match(game)
    if match:
        shortcut_name, shortcut_path = match
        try:
            _launch(shortcut_path)
            return ToolResult(status="ok", message=f"Opening {shortcut_name} via shortcut.", data={"app": shortcut_name})
        except Exception as e:
            return ToolResult(status="error", message=f"Couldn't launch {shortcut_name}: {e}")
            
    return ToolResult(status="not_found", message=f"Could not find Steam game '{game}'.")
