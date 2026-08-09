"""Ambient Screen-Context Module

Watches for foreground window changes via a low-frequency background poll.
When the user switches contexts, it captures a downscaled screenshot via mss,
and calls the vision model ephemerally to describe it. Results are kept in a
rolling 5-minute RAM buffer, never touching the long-term SQLite database.
"""
import asyncio
import base64
import io
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

from .registry import tool
from ..schemas import ToolResult

_log = logging.getLogger(__name__)

@dataclass
class ScreenContext:
    timestamp: float
    window_title: str
    description: str

class ScreenContextManager:
    def __init__(self, max_history: int = 10, expiry_seconds: int = 300):
        self.buffer: deque[ScreenContext] = deque(maxlen=max_history)
        self.expiry_seconds = expiry_seconds
        self.last_window_title = ""
        self._task: asyncio.Task | None = None
        self._is_running = False

    def start(self):
        if not self._is_running:
            self._is_running = True
            self._task = asyncio.create_task(self._poll_loop())

    def stop(self):
        self._is_running = False
        if self._task:
            self._task.cancel()

    async def _poll_loop(self):
        try:
            import win32gui
        except ImportError:
            _log.warning("pywin32 not installed. Ambient screen context requires win32gui.")
            return

        while self._is_running:
            try:
                hwnd = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(hwnd)
                
                # If window changed and has a title
                if title and title != self.last_window_title:
                    self.last_window_title = title
                    # Offload the capture and vision call
                    asyncio.create_task(self._capture_and_describe(title))
                    
            except Exception as e:
                _log.debug("ScreenContext poll error: %s", e)
                
            await asyncio.sleep(2.0)  # low frequency poll

    async def _capture_and_describe(self, window_title: str):
        try:
            b64, mime = await asyncio.to_thread(self._capture_base64)
            
            # Import here to avoid circular imports
            from ..llm_client import vision_describe
            from ..config import get_settings
            
            description = await vision_describe(
                image_base64=b64,
                image_mime=mime,
                question=f"Describe what the user is looking at in the window titled '{window_title}'. Keep it brief.",
                settings=get_settings()
            )
            
            self.buffer.append(ScreenContext(
                timestamp=time.time(),
                window_title=window_title,
                description=description
            ))
            _log.info("Ambient screen context updated for window: %s", window_title)
        except Exception as e:
            _log.error("Failed to capture ambient screen context: %s", e)

    def _capture_base64(self, monitor: int = 1, max_width: int = 1280) -> tuple[str, str]:
        import mss
        from PIL import Image

        with mss.mss() as sct:
            try:
                shot = sct.grab(sct.monitors[monitor])
            except IndexError:
                shot = sct.grab(sct.monitors[0])
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

        if img.width > max_width:
            new_h = int(img.height * (max_width / img.width))
            img = img.resize((max_width, new_h), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("ascii"), "image/jpeg"

    def get_recent_context(self) -> str:
        now = time.time()
        valid_contexts = [
            c for c in self.buffer 
            if (now - c.timestamp) <= self.expiry_seconds
        ]
        
        if not valid_contexts:
            return "No recent screen context available in the last 5 minutes."
            
        context_strs = [
            f"- At {time.strftime('%H:%M:%S', time.localtime(c.timestamp))} (Window: {c.window_title}): {c.description}"
            for c in valid_contexts
        ]
        return "Recent Screen Context:\n" + "\n".join(context_strs)

# Global singleton
context_manager = ScreenContextManager()

@tool
def get_recent_screen_context() -> ToolResult:
    """Get a summary of what the user has recently been looking at on their screen. Use this when the user asks 'what am I looking at?' or refers to something on their screen without specifying."""
    try:
        context_text = context_manager.get_recent_context()
        return ToolResult(
            status="ok",
            message="Retrieved recent screen context.",
            data={"context": context_text}
        )
    except Exception as e:
        return ToolResult(
            status="error",
            message=f"Failed to get screen context: {e}"
        )

def init_ambient_context():
    context_manager.start()
