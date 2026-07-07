"""Screen vision: capture the current monitor and answer questions about it.

The capture itself happens here (mss + Pillow); the *vision reasoning* is done
by the orchestrator, which calls GLM 5.2's multimodal endpoint with the
base64 image + the user's question. This tool therefore returns the image
payload and the question, and the orchestrator routes it to the vision model.

If you'd rather have the tool answer inline, `ask_about_screen` does a
self-contained vision call (requires the LLM client to be initialized).
"""
from __future__ import annotations

import base64
import io

from ..schemas import ToolResult
from .registry import tool


def _capture_base64(monitor: int = 1, max_width: int = 1600) -> tuple[str, str]:
    """Grab a screenshot and return (base64_jpeg, mime)."""
    import mss
    from PIL import Image

    with mss.mss() as sct:
        try:
            shot = sct.grab(sct.monitors[monitor])
        except IndexError:
            shot = sct.grab(sct.monitors[0])
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    # Downscale very wide images to keep tokens / latency sane.
    if img.width > max_width:
        new_h = int(img.height * (max_width / img.width))
        img = img.resize((max_width, new_h), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("ascii"), "image/jpeg"


@tool
def capture_screen(question: str | None = None, monitor: int = 1) -> ToolResult:
    """Capture the current screen so Genie can answer questions about what's on it (e.g. read weather indexes, find a button, summarize a page).

    :param question: Optional question about the screen content. If provided, the orchestrator will answer it using vision; if omitted, Genie will describe what it sees.
    :param monitor: Which monitor to capture (1 = primary). Default 1.
    """
    try:
        b64, mime = _capture_base64(monitor=monitor)
    except Exception as e:  # noqa: BLE001
        return ToolResult(
            status="error",
            message=f"I couldn't capture the screen: {e}",
        )
    # Return the image payload; the orchestrator turns this into a vision turn.
    return ToolResult(
        status="ok",
        message="Screen captured. Sending it to vision now.",
        data={
            "image_base64": b64,
            "image_mime": mime,
            "question": question or "Describe what's on screen.",
            "monitor": monitor,
            # Hint to the orchestrator that this result must be vision-routed.
            "vision": True,
        },
    )
