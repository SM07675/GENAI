"""Ghost typing: bring a text field into focus and type long text automatically.

Uses `pyautogui` to type and `pygetwindow` to focus a target window first so
the keystrokes land in the right app (e.g. an open Notepad or chat box).

Safety: a small built-in delay lets you Ctrl-C / move the mouse to a corner to
abort if needed (pyautogui's default failsafe is on).
"""
from __future__ import annotations

import subprocess
import sys
import time

from ..schemas import ToolResult
from .registry import tool


def _focus_window(target: str | None) -> str:
    """Best-effort focus of a window by title substring. Returns what happened."""
    if not target:
        return "no-target"
    try:
        if sys.platform == "win32":
            import pygetwindow as gw  # lazy import
            wins = [w for w in gw.getAllWindows() if target.lower() in w.title.lower() and w.title]
            if wins:
                # Activate the most-recently-matched window.
                w = wins[0]
                try:
                    if w.isMinimized:
                        w.restore()
                except Exception:  # noqa: BLE001
                    pass
                w.activate()
                time.sleep(0.4)
                return f"focused:{w.title}"
        # macOS / Linux fallbacks: just type into whatever is focused.
    except Exception:  # noqa: BLE001
        pass
    return "focus-failed"


@tool
def ghost_type(text: str, target_window: str | None = None, wpm: int = 200) -> ToolResult:
    """Type a long block of text into whichever text field is currently focused. Optionally focus a window by title first (e.g. 'Notepad', 'WhatsApp'). Great for drafting letters or messages.

    :param text: The exact text to type out.
    :param target_window: Optional window title to focus before typing (e.g. 'Notepad').
    :param wpm: Optional typing speed in words-per-minute; default 200 (fast but readable).
    """
    if not text or not text.strip():
        return ToolResult(status="error", message="Nothing to type — text was empty.")

    focus_status = _focus_window(target_window)

    try:
        import pyautogui
    except ImportError:
        return ToolResult(
            status="error",
            message="pyautogui isn't installed, so I can't ghost-type.",
        )

    # pyautogui's failsafe (mouse to a screen corner) stays ON for safety.
    pyautogui.FAILSAFE = True
    # Per-key interval derived from wpm. Guard against silly values.
    wpm = max(20, min(1000, int(wpm)))
    # ~5 chars per "word"; interval is seconds per char.
    interval = max(0.0, (60.0 / wpm) / 5.0)

    # Give the user a beat before we start (also a chance to abort).
    time.sleep(0.6)

    try:
        pyautogui.write(text, interval=interval)
        return ToolResult(
            status="ok",
            message=f"Done — typed {len(text)} characters.",
            data={
                "chars": len(text),
                "target_window": target_window,
                "focus": focus_status,
                "wpm": wpm,
            },
        )
    except pyautogui.FailSafeException:
        return ToolResult(
            status="error",
            message="Ghost typing aborted — mouse hit a screen corner (failsafe).",
        )
    except Exception as e:  # noqa: BLE001
        return ToolResult(
            status="error",
            message=f"Ghost typing failed: {e}",
        )


def _open_notepad_then_type(text: str) -> ToolResult:
    """Convenience: open Notepad on Windows and type into it."""
    if sys.platform != "win32":
        return ToolResult(status="error", message="Notepad helper is Windows-only.")
    try:
        subprocess.Popen(["notepad.exe"])
        time.sleep(1.2)
    except Exception as e:  # noqa: BLE001
        return ToolResult(status="error", message=f"Couldn't open Notepad: {e}")
    return ghost_type(text, target_window="Notepad")
