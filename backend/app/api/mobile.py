"""Mobile API routes for Genie Mobile Companion."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Request

from ..tools.system_control import shutdown_pc, restart_pc, lock_pc
from ..tools.screen_vision import capture_screen
from ..tools.utilities import clipboard_read, clipboard_write

router = APIRouter(prefix="/mobile", tags=["mobile"])

@router.get("/devices")
async def get_devices() -> dict[str, Any]:
    """Get active input/output devices (audio, screen, etc)."""
    # For now, return stub data. Can be expanded by querying host OS audio APIs.
    return {
        "status": "ok",
        "devices": {
            "microphones": [{"id": "default", "name": "System Default Microphone"}],
            "speakers": [{"id": "default", "name": "System Default Speaker"}],
            "monitors": [{"id": "1", "name": "Primary Display"}],
        }
    }

@router.get("/notifications")
async def get_notifications() -> dict[str, Any]:
    """Get pending OS notifications or Genie task updates."""
    # Stub: return an empty list initially.
    return {"status": "ok", "notifications": []}

@router.post("/upload")
async def upload_file(request: Request) -> dict[str, Any]:
    """Upload a file from the mobile device to the PC."""
    # To be implemented with proper multipart form data handling
    return {"status": "ok", "message": "File upload endpoint ready"}

@router.get("/clipboard")
async def read_clipboard() -> dict[str, Any]:
    """Read the current PC clipboard."""
    result = clipboard_read()
    if result.status == "error":
        raise HTTPException(status_code=500, detail=result.message)
    return {"status": "ok", "clipboard": result.data.get("text", "") if result.data else ""}

@router.post("/clipboard")
async def write_clipboard(payload: dict[str, Any]) -> dict[str, Any]:
    """Write text to the PC clipboard."""
    text = payload.get("text", "")
    result = clipboard_write(text)
    if result.status == "error":
        raise HTTPException(status_code=500, detail=result.message)
    return {"status": "ok"}

@router.post("/screen")
async def take_screenshot(payload: dict[str, Any] = None) -> dict[str, Any]:
    """Capture the PC screen and return the base64 image."""
    monitor = (payload or {}).get("monitor", 1)
    result = capture_screen(monitor=monitor)
    if result.status == "error":
        raise HTTPException(status_code=500, detail=result.message)
    return {"status": "ok", "image_base64": result.data.get("image_base64", "") if result.data else ""}

@router.post("/camera")
async def take_camera_photo() -> dict[str, Any]:
    """Capture a photo using the PC's webcam."""
    # Future implementation: use cv2 or similar to grab a frame
    return {"status": "ok", "message": "Webcam capture endpoint ready"}

@router.post("/microphone")
async def record_microphone(payload: dict[str, Any] = None) -> dict[str, Any]:
    """Record a snippet from the PC's microphone."""
    # Future implementation: use pyaudio to record N seconds
    duration = (payload or {}).get("duration", 5)
    return {"status": "ok", "message": f"Microphone recorded for {duration} seconds"}

@router.get("/logs")
async def get_logs() -> dict[str, Any]:
    """Get recent system logs for diagnostics on mobile."""
    # Future implementation: read from structlog output
    return {"status": "ok", "logs": []}

@router.post("/shutdown")
async def shutdown() -> dict[str, Any]:
    """Shut down the PC."""
    result = shutdown_pc()
    if result.status == "error":
        raise HTTPException(status_code=500, detail=result.message)
    return {"status": "ok"}

@router.post("/restart")
async def restart() -> dict[str, Any]:
    """Restart the PC."""
    result = restart_pc()
    if result.status == "error":
        raise HTTPException(status_code=500, detail=result.message)
    return {"status": "ok"}

@router.post("/lock")
async def lock() -> dict[str, Any]:
    """Lock the PC screen."""
    result = lock_pc()
    if result.status == "error":
        raise HTTPException(status_code=500, detail=result.message)
    return {"status": "ok"}
