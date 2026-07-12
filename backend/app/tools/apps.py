"""App & game control tools.

Windows-first: resolves app names via a comprehensive alias table, then
falls back to PATH lookup, then to a browser URL.  The "Instagram rule":
if the app isn't installed, return not_found + suggestion so the orchestrator
chains into open_url automatically.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

from ..schemas import ToolResult
from .registry import tool

# ── alias table ──────────────────────────────────────────────────────────────
# key (lower-case) → (display_name, win_executable, fallback_url | None)
_APP_ALIASES: dict[str, tuple[str, str, str | None]] = {
    # Browsers
    "chrome":           ("Google Chrome",          "chrome.exe",            "https://www.google.com"),
    "google chrome":    ("Google Chrome",          "chrome.exe",            "https://www.google.com"),
    "edge":             ("Microsoft Edge",          "msedge.exe",            "https://www.bing.com"),
    "firefox":          ("Mozilla Firefox",         "firefox.exe",           "https://www.mozilla.org"),
    "brave":            ("Brave Browser",           "brave.exe",             "https://brave.com"),
    "opera":            ("Opera",                   "opera.exe",             "https://opera.com"),

    # Productivity / editors
    "notepad":          ("Notepad",                 "notepad.exe",           None),
    "notepad++":        ("Notepad++",               "notepad++.exe",         "https://notepad-plus-plus.org"),
    "wordpad":          ("WordPad",                 "wordpad.exe",           None),
    "word":             ("Microsoft Word",          "winword.exe",           "https://office.com"),
    "excel":            ("Microsoft Excel",         "excel.exe",             "https://office.com"),
    "powerpoint":       ("Microsoft PowerPoint",    "powerpnt.exe",          "https://office.com"),
    "vscode":           ("Visual Studio Code",      "Code.exe",              "https://vscode.dev"),
    "vs code":          ("Visual Studio Code",      "Code.exe",              "https://vscode.dev"),
    "visual studio code": ("Visual Studio Code",   "Code.exe",              "https://vscode.dev"),

    # Media / creative
    "vlc":              ("VLC",                     "vlc.exe",               "https://videolan.org/vlc"),
    "filmora":          ("Wondershare Filmora",     "Filmora.exe",           "https://filmora.wondershare.com"),
    "obs":              ("OBS Studio",              "obs64.exe",             "https://obsproject.com"),
    "spotify":          ("Spotify",                 "Spotify.exe",           "https://open.spotify.com"),

    # Communication / social
    "whatsapp":         ("WhatsApp",                "WhatsApp.exe",          "https://web.whatsapp.com"),
    "telegram":         ("Telegram",                "Telegram.exe",          "https://web.telegram.org"),
    "discord":          ("Discord",                 "Discord.exe",           "https://discord.com/app"),
    "slack":            ("Slack",                   "slack.exe",             "https://app.slack.com"),
    "teams":            ("Microsoft Teams",         "ms-teams.exe",          "https://teams.microsoft.com"),
    "zoom":             ("Zoom",                    "Zoom.exe",              "https://zoom.us/join"),
    "instagram":        ("Instagram",               "Instagram.exe",         "https://www.instagram.com"),
    "facebook":         ("Facebook",                "Facebook.exe",          "https://www.facebook.com"),
    "twitter":          ("Twitter / X",             "Twitter.exe",           "https://twitter.com"),
    "x":                ("Twitter / X",             "Twitter.exe",           "https://twitter.com"),

    # Web / streaming
    "youtube":          ("YouTube",                 "youtube.exe",           "https://www.youtube.com"),
    "netflix":          ("Netflix",                 "Netflix.exe",           "https://www.netflix.com"),
    "prime video":      ("Prime Video",             "PrimeVideo.exe",        "https://www.primevideo.com"),
    "hotstar":          ("Disney+ Hotstar",         "Hotstar.exe",           "https://www.hotstar.com"),

    # Utilities
    "calculator":       ("Calculator",              "calc.exe",              None),
    "calendar":         ("Calendar",                "outlookcal:",           None),
    "paint":            ("Paint",                   "mspaint.exe",           None),
    "snipping tool":    ("Snipping Tool",           "SnippingTool.exe",      None),
    "task manager":     ("Task Manager",            "taskmgr.exe",           None),
    "file explorer":    ("File Explorer",           "explorer.exe",          None),
    "explorer":         ("File Explorer",           "explorer.exe",          None),
    "settings":         ("Windows Settings",        "ms-settings:",          None),
    "control panel":    ("Control Panel",           "control.exe",           None),
    "cmd":              ("Command Prompt",          "cmd.exe",               None),
    "powershell":       ("PowerShell",              "powershell.exe",        None),
    "terminal":         ("Windows Terminal",        "wt.exe",                None),

    # Gaming
    "steam":            ("Steam",                   "steam.exe",             "https://store.steampowered.com"),
    "epic games":       ("Epic Games Launcher",     "EpicGamesLauncher.exe", "https://store.epicgames.com"),
    "epic":             ("Epic Games Launcher",     "EpicGamesLauncher.exe", "https://store.epicgames.com"),
    "xbox":             ("Xbox",                    "xboxapp:",              "https://xbox.com"),
    "battlenet":        ("Battle.net",              "Battle.net.exe",        "https://battle.net"),

    # Other common
    "clock":            ("Clock",                   "ms-clock:",             None),
    "mail":             ("Mail",                    "outlookmail:",          "https://outlook.live.com"),
    "outlook":          ("Outlook",                 "outlook.exe",           "https://outlook.live.com"),
    "maps":             ("Maps",                    "maps:",                 "https://maps.google.com"),
    "google maps":      ("Google Maps",             "maps:",                 "https://maps.google.com"),
}

_STEAM_GAMES: dict[str, tuple[str, str]] = {
    "palworld":     ("Palworld",                       "1623730"),
    "spider-man":   ("Marvel's Spider-Man Remastered", "1817070"),
    "spider man":   ("Marvel's Spider-Man Remastered", "1817070"),
    "spiderman":    ("Marvel's Spider-Man Remastered", "1817070"),
    "csgo":         ("CS:GO",                          "730"),
    "cs2":          ("Counter-Strike 2",               "730"),
    "elden ring":   ("ELDEN RING",                     "1245620"),
    "cyberpunk":    ("Cyberpunk 2077",                 "1091500"),
    "gta5":         ("GTA V",                          "271590"),
    "gta v":        ("GTA V",                          "271590"),
    "minecraft":    ("Minecraft",                      "1672970"),
    "rdr2":         ("Red Dead Redemption 2",          "1174180"),
}


def _key(name: str) -> str:
    return (name or "").strip().lower()


def _exe_available(exe: str) -> bool:
    if not exe:
        return False
    # Windows URI scheme (ms-settings:, calc.exe special aliases)
    if exe.endswith(":"):
        return sys.platform == "win32"
    if os.path.isabs(exe):
        return os.path.exists(exe)
    return shutil.which(exe) is not None


def _launch(command: str) -> None:
    if sys.platform == "win32":
        subprocess.Popen(
            command, shell=True,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    elif sys.platform == "darwin":
        subprocess.Popen(["open", command])
    else:
        subprocess.Popen(["xdg-open", command])


# ─────────────────────────────────────────────────────────────────────────────

@tool
def open_app(name: str) -> ToolResult:
    """Open a desktop application by its friendly name.
    Supports: chrome, youtube, whatsapp, telegram, discord, spotify, steam,
    calculator, notepad, vscode, vlc, netflix, instagram, facebook, teams,
    zoom, obs, filmora, and many more.

    :param name: Friendly app name (e.g. 'chrome', 'whatsapp', 'calculator').
    """
    k = _key(name)
    if not k:
        return ToolResult(status="error", message="No app name provided.")

    display, exe, fallback_url = _APP_ALIASES.get(k, (name, f"{k}.exe", None))

    # Try the known exe first
    if _exe_available(exe):
        try:
            _launch(exe)
            return ToolResult(
                status="ok",
                message=f"Opening {display}.",
                data={"app": display},
            )
        except Exception as e:
            return ToolResult(status="error", message=f"Couldn't start {display}: {e}")

    # PATH fallback for unknown apps
    guessed = k if k.endswith(".exe") else f"{k}.exe"
    if shutil.which(guessed):
        try:
            _launch(guessed)
            return ToolResult(status="ok", message=f"Opening {name}.", data={"app": name})
        except Exception as e:
            return ToolResult(status="error", message=f"Couldn't start {name}: {e}")

    # Browser fallback
    if fallback_url:
        return ToolResult(
            status="not_found",
            message=f"{display} isn't installed. Opening its website instead.",
            data={"app": display, "suggestion": "open_url", "url": fallback_url},
        )

    return ToolResult(
        status="not_found",
        message=f"I couldn't find {display} on this PC.",
        data={"app": display},
    )


@tool
def close_app(name: str, force: bool = True) -> ToolResult:
    """Close a running application by name (e.g. chrome, spotify, discord).

    :param name: App name or process name.
    :param force: Kill immediately if true, otherwise terminate gracefully.
    """
    k = _key(name)
    if not k:
        return ToolResult(status="error", message="No app name provided.")

    display, exe, _ = _APP_ALIASES.get(k, (name, k, None))
    proc_name = exe if exe.lower().endswith(".exe") else f"{exe}.exe"

    try:
        import psutil
    except ImportError:
        return ToolResult(status="error", message="psutil is not installed.")

    killed: list[str] = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            pname = (proc.info.get("name") or "").lower()
            if pname == proc_name.lower() or k in pname:
                proc.kill() if force else proc.terminate()
                killed.append(proc.info["name"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not killed:
        return ToolResult(status="ok", message=f"{display} wasn't running.", data={"closed": []})
    return ToolResult(
        status="ok",
        message=f"Closed {display}.",
        data={"app": display, "closed": killed},
    )


@tool
def launch_steam_game(game: str) -> ToolResult:
    """Launch a Steam game by friendly name (e.g. palworld, elden ring, gta v, cs2).

    :param game: Game name or numeric Steam app ID.
    """
    k = _key(game)
    if k in _STEAM_GAMES:
        display, app_id = _STEAM_GAMES[k]
    elif k.isdigit():
        display, app_id = f"Steam app {k}", k
    else:
        return ToolResult(
            status="error",
            message=f"I don't know the Steam ID for '{game}'. Tell me the numeric app ID.",
            data={"known": [v[0] for v in _STEAM_GAMES.values()]},
        )

    try:
        _launch(f"steam://run/{app_id}")
        return ToolResult(
            status="ok",
            message=f"Launching {display} via Steam.",
            data={"game": display, "steam_app_id": app_id},
        )
    except Exception as e:
        return ToolResult(status="error", message=f"Couldn't launch {display}: {e}")
