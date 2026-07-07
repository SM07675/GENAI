"""App & game control tools: open/close native apps and launch Steam games.

Implements the "Instagram problem" guardrail: when a native app isn't found,
`open_app` returns a structured `not_found` result with a `suggestion` so the
orchestrator (and GLM via the system prompt) can chain into `open_url`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

from ..schemas import ToolResult
from .registry import tool

# ---------------------------------------------------------------------
# Known app aliases -> launch commands. Extend freely; aliases let the user
# say "open filmora" / "open chrome" naturally. We resolve case-insensitively
# and fall back to PATH lookup.
# ---------------------------------------------------------------------
# Each value is a tuple (display_name, executable, optional_url_if_missing).
# `optional_url_if_missing` powers the browser-fallback suggestion.
_APP_ALIASES: dict[str, tuple[str, str, str | None]] = {
    # Browsers
    "chrome": ("Google Chrome", "chrome.exe", "https://www.google.com"),
    "edge": ("Microsoft Edge", "msedge.exe", "https://www.microsoft.com/edge"),
    "firefox": ("Mozilla Firefox", "firefox.exe", "https://www.mozilla.org"),
    # Editors / media
    "notepad": ("Notepad", "notepad.exe", None),
    "vscode": ("Visual Studio Code", "Code.exe", "https://vscode.dev"),
    "filmora": ("Wondershare Filmora", "Filmora.exe", "https://filmora.wondershare.com"),
    # Comms / social
    "whatsapp": ("WhatsApp", "WhatsApp.exe", "https://web.whatsapp.com"),
    "spotify": ("Spotify", "Spotify.exe", "https://open.spotify.com"),
    "steam": ("Steam", "steam.exe", "https://store.steampowered.com"),
    "discord": ("Discord", "Discord.exe", "https://discord.com/app"),
}

# Known Steam Run IDs. Add more as you install them.
_STEAM_GAMES: dict[str, tuple[str, str]] = {
    # alias -> (display name, app id)
    "palworld": ("Palworld", "1623730"),
    "spider-man": ("Marvel's Spider-Man Remastered", "1817070"),
    "spider man": ("Marvel's Spider-Man Remastered", "1817070"),
    "spiderman": ("Marvel's Spider-Man Remastered", "1817070"),
    "csgo": ("CS:GO", "730"),
    "cs2": ("Counter-Strike 2", "730"),
    "elden ring": ("ELDEN RING", "1245620"),
    "cyberpunk": ("Cyberpunk 2077", "1091500"),
    "gta5": ("GTA V", "271590"),
    "gta v": ("GTA V", "271590"),
}


def _resolve_alias(name: str) -> str:
    return (name or "").strip().lower()


def _is_executable_available(exe: str) -> bool:
    """True if `exe` is on PATH or exists as an absolute path."""
    if os.path.isabs(exe) and os.path.exists(exe):
        return True
    return shutil.which(exe) is not None


def _open_with_shell(command: str) -> None:
    """Cross-platform `start`/`open`/`xdg-open` so we never block the server."""
    if sys.platform == "win32":
        # `start` returns immediately via cmd; detach from our process.
        subprocess.Popen(
            command, shell=True,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    elif sys.platform == "darwin":
        subprocess.Popen(["open", command])
    else:
        subprocess.Popen(["xdg-open", command])


# =====================================================================
# Tools
# =====================================================================
@tool
def open_app(name: str) -> ToolResult:
    """Open a desktop application by friendly name (e.g. chrome, notepad, filmora, whatsapp, spotify, steam, discord).

    :param name: Friendly app name or executable name.
    """
    key = _resolve_alias(name)
    if not key:
        return ToolResult(status="error", message="No app name provided.")

    if key in _APP_ALIASES:
        display, exe, fallback_url = _APP_ALIASES[key]
    else:
        # Treat the raw name as an executable and try it directly.
        display = name
        exe = key if key.endswith(".exe") else f"{key}.exe"
        fallback_url = None

    if _is_executable_available(exe):
        try:
            _open_with_shell(exe)
            return ToolResult(
                status="ok",
                message=f"Opened {display}.",
                data={"app": display, "executable": exe},
            )
        except Exception as e:  # noqa: BLE001
            return ToolResult(
                status="error",
                message=f"I couldn't start {display}: {e}",
                data={"app": display},
            )

    # Not installed locally -> suggest the browser fallback (Instagram rule).
    if fallback_url:
        return ToolResult(
            status="not_found",
            message=(
                f"{display} isn't installed as a desktop app, but I can open "
                f"its website at {fallback_url} instead."
            ),
            data={
                "app": display,
                "suggestion": "open_url",
                "url": fallback_url,
            },
        )
    return ToolResult(
        status="not_found",
        message=(
            f"I couldn't find {display} on this PC. Make sure it's installed, "
            f"or ask me to open its website instead."
        ),
        data={"app": display},
    )


@tool
def close_app(name: str, force: bool = True) -> ToolResult:
    """Force-close a running application by friendly name or process name (e.g. chrome, steam).

    :param name: Friendly app name or process name (with or without .exe).
    :param force: If true, kill the process tree forcefully.
    """
    key = _resolve_alias(name)
    if not key:
        return ToolResult(status="error", message="No app name provided.")

    display, exe, _ = _APP_ALIASES.get(key, (name, key, None))
    proc_name = exe if exe.lower().endswith(".exe") else f"{exe}.exe"

    try:
        import psutil  # imported lazily so the server still boots if missing
    except ImportError:
        return ToolResult(
            status="error",
            message="psutil is not installed; cannot close apps.",
        )

    killed: list[str] = []
    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = (proc.info.get("name") or "").lower()
                if pname == proc_name.lower() or key in pname:
                    if force:
                        proc.kill()
                    else:
                        proc.terminate()
                    killed.append(f"{proc.info['name']}({proc.info['pid']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:  # noqa: BLE001
        return ToolResult(status="error", message=f"Failed to close {display}: {e}")

    if not killed:
        return ToolResult(
            status="ok",
            message=f"{display} wasn't running, so nothing to close.",
            data={"app": display, "closed": []},
        )
    return ToolResult(
        status="ok",
        message=f"Closed {display} ({len(killed)} process(es)).",
        data={"app": display, "closed": killed},
    )


@tool
def launch_steam_game(game: str) -> ToolResult:
    """Launch a Steam game by its friendly name using its Steam Run ID (e.g. palworld, spider-man, elden ring, cs2).

    :param game: Friendly game name (must exist in the known games list).
    """
    key = _resolve_alias(game)
    if key in _STEAM_GAMES:
        display, app_id = _STEAM_GAMES[key]
    else:
        # Allow passing a raw numeric Steam app id directly.
        if key.isdigit():
            display, app_id = f"Steam app {key}", key
        else:
            return ToolResult(
                status="error",
                message=(
                    f"I don't know the Steam Run ID for '{game}'. "
                    f"Tell me the numeric app id or add it to the games list."
                ),
                data={"known_games": [g[0] for g in _STEAM_GAMES.values()]},
            )

    uri = f"steam://run/{app_id}"
    try:
        _open_with_shell(uri)
        return ToolResult(
            status="ok",
            message=f"Launching {display} via Steam.",
            data={"game": display, "steam_app_id": app_id, "uri": uri},
        )
    except Exception as e:  # noqa: BLE001
        return ToolResult(
            status="error",
            message=f"I couldn't launch {display}: {e}. Is Steam running?",
            data={"game": display},
        )
