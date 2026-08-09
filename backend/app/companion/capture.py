"""ScreenCaptureManager — low-overhead screen/window capture for Companion Mode.

Design principles (per spec §5)
---------------------------------
* Backend-owned: the Python process owns screen capture (same philosophy as mic).
* `mss` for frame capture — fast, no DLL injection, no render-pipeline hooks.
* `pywin32` for active-window / active-app identification — free, instant, no
  vision API call required.  App identity is determined BEFORE any vision spend.
* Frames are bytes in memory ONLY — never written to disk or any memory tier.
* Capture is disabled when CompanionMode != ACTIVE (enforced by the caller).
* Anti-cheat / DRM: if `mss` cannot capture a surface (returns a blank/black
  frame or raises), we fall back to voice-only companion — no injection attempted.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from typing import Optional
import io

import structlog

log = structlog.get_logger("genie.companion.capture")


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    class_name: str
    process_name: str
    pid: int


@dataclass
class AppInfo:
    process_name: str          # e.g. "Code.exe"
    process_name_stem: str     # e.g. "Code"
    window_title: str
    category: str = "general"  # "game" | "ide" | "browser" | "writing" | "general"
    pid: int = 0


# ── Win32 helpers (pywin32) ───────────────────────────────────────────────────

def _get_win32_active_window() -> Optional[WindowInfo]:
    """Return foreground window info using pywin32. Returns None if unavailable."""
    try:
        import win32gui
        import win32process
        import win32api

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None

        title = win32gui.GetWindowText(hwnd)
        class_name = win32gui.GetClassName(hwnd)

        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            handle = win32api.OpenProcess(0x0410, False, pid)  # PROCESS_QUERY_INFO | VM_READ
            exe_path: str = win32api.GetModuleFileNameEx(handle, 0)
            process_name = exe_path.split("\\")[-1] if exe_path else "unknown"
            win32api.CloseHandle(handle)
        except Exception:
            process_name = "unknown"

        return WindowInfo(
            hwnd=hwnd,
            title=title,
            class_name=class_name,
            process_name=process_name,
            pid=pid,
        )
    except ImportError:
        log.warning("pywin32_not_available", note="install pywin32 for active-window detection")
        return None
    except Exception as exc:
        log.warning("win32_active_window_error", error=str(exc))
        return None


_APP_CATEGORIES: dict[str, str] = {
    # IDEs / terminals
    "code": "ide", "devenv": "ide", "idea64": "ide", "pycharm64": "ide",
    "webstorm64": "ide", "rider64": "ide", "clion64": "ide",
    "windowsterminal": "ide", "powershell": "ide", "cmd": "ide",
    "jupyter": "ide",
    # Games / game launchers
    "gamebar": "game", "steam": "game", "epicgameslauncher": "game",
    "riotclientservices": "game", "battle.net": "game",
    "minecraft.windows": "game",
    # Browsers
    "chrome": "browser", "firefox": "browser", "msedge": "browser",
    "brave": "browser", "opera": "browser",
    # Writing
    "winword": "writing", "notepad": "writing", "typora": "writing",
    "obsidian": "writing", "notion": "writing",
}


def _categorize_app(process_name_stem: str) -> str:
    lower = process_name_stem.lower()
    for key, cat in _APP_CATEGORIES.items():
        if key in lower:
            return cat
    return "general"


# ── ScreenCaptureManager ──────────────────────────────────────────────────────

class ScreenCaptureManager:
    """Captures the screen or active window using mss.

    Thread-safe: mss instances are created per-call (lightweight).
    Frame bytes are in-memory only — never persisted.

    If mss is unavailable (e.g. DRM surface), returns None and logs a warning.
    The caller (ObservationLoop) must handle None as "fall back to voice-only".
    """

    def __init__(self) -> None:
        self._mss_available: Optional[bool] = None  # lazy-checked

    def _check_mss(self) -> bool:
        if self._mss_available is None:
            try:
                import mss  # noqa: F401
                self._mss_available = True
            except ImportError:
                log.warning("mss_not_installed", note="pip install mss")
                self._mss_available = False
        return self._mss_available

    def capture_screen(self, monitor: int = 1) -> Optional[bytes]:
        """Capture the primary monitor. Returns raw PNG bytes or None on failure."""
        if not self._check_mss():
            return None
        try:
            import mss
            import mss.tools
            with mss.mss() as sct:
                mon = sct.monitors[monitor]
                screenshot = sct.grab(mon)
                return mss.tools.to_png(screenshot.rgb, screenshot.size)
        except Exception as exc:
            log.warning("screen_capture_failed", error=str(exc))
            return None

    def capture_active_window(self) -> Optional[bytes]:
        """Capture only the bounding rect of the foreground window.

        Falls back to full-screen capture if the window rect can't be obtained.
        Returns None if any DRM/anti-cheat surface blocks capture.
        """
        if not self._check_mss():
            return None
        try:
            import mss
            import mss.tools
            import win32gui

            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return self.capture_screen()

            rect = win32gui.GetWindowRect(hwnd)
            left, top, right, bottom = rect
            region = {"left": left, "top": top, "width": right - left, "height": bottom - top}

            if region["width"] <= 0 or region["height"] <= 0:
                return self.capture_screen()

            with mss.mss() as sct:
                screenshot = sct.grab(region)
                raw = mss.tools.to_png(screenshot.rgb, screenshot.size)

            # Anti-cheat / DRM detection: if the frame is entirely black,
            # the surface is protected — return None to trigger voice-only fallback.
            if _is_black_frame(raw):
                log.info("capture_black_frame_detected", note="possible DRM surface, voice-only fallback")
                return None

            return raw
        except ImportError:
            # pywin32 not available — fall back to full screen
            return self.capture_screen()
        except Exception as exc:
            log.warning("active_window_capture_failed", error=str(exc))
            return None

    def capture_now(self) -> Optional[bytes]:
        """On-demand capture for Quick Look.

        Bypasses ambient observation intervals and scheduler queues to capture
        the active window (or full screen fallback) instantly.
        """
        frame = self.capture_active_window()
        if frame is None:
            frame = self.capture_screen()
        return frame

    def capture_region(self, left: int, top: int, width: int, height: int) -> Optional[bytes]:
        """Capture an arbitrary screen region."""
        if not self._check_mss():
            return None
        try:
            import mss
            import mss.tools
            with mss.mss() as sct:
                region = {"left": left, "top": top, "width": width, "height": height}
                screenshot = sct.grab(region)
                return mss.tools.to_png(screenshot.rgb, screenshot.size)
        except Exception as exc:
            log.warning("region_capture_failed", error=str(exc))
            return None

    def get_active_window(self) -> Optional[WindowInfo]:
        """Return info about the current foreground window (no vision call)."""
        return _get_win32_active_window()

    def get_active_application(self) -> AppInfo:
        """Return structured AppInfo about the active process (no vision call).

        This is the cheap, always-first step before any vision API spend.
        """
        info = _get_win32_active_window()
        if info is None:
            return AppInfo(
                process_name="unknown",
                process_name_stem="unknown",
                window_title="",
                category="general",
            )

        stem = info.process_name.replace(".exe", "").replace(".EXE", "")
        category = _categorize_app(stem)
        return AppInfo(
            process_name=info.process_name,
            process_name_stem=stem,
            window_title=info.title,
            category=category,
            pid=info.pid,
        )


def _is_black_frame(png_bytes: bytes) -> bool:
    """Heuristic: check if a PNG is entirely (or nearly entirely) black.

    This detects DRM-protected surfaces that mss captures as all-black.
    We check the compressed data size as a proxy — a solid-black image
    compresses to a tiny fraction of a normal screenshot.
    """
    try:
        if len(png_bytes) < 200:
            return True
        # PNG files: IHDR chunk starts at byte 16, compressed data in IDAT chunks.
        # A very small file relative to expected size suggests blank/black frame.
        # Rough heuristic: < 2KB for any monitor size → likely black
        return len(png_bytes) < 2048
    except Exception:
        return False


# Module-level singleton
screen_capture = ScreenCaptureManager()
