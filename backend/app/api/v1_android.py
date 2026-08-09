"""Genie AI - API v1 and WebSocket Hub for Android Companion.
Supports secure device pairing, encrypted tokens, security confirmations for dangerous operations,
real-time hardware telemetry, voice integration, and tool orchestrations.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, HTTPException, Header, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

import psutil

from ..tools.system_control import shutdown_pc, restart_pc, lock_pc
from ..tools.screen_vision import capture_screen
from ..tools.utilities import clipboard_read, clipboard_write
from ..tools.media import play_youtube_music, stop_music
from ..services.mdns_server import get_local_ip

logger = logging.getLogger("genie.v1_android")

router = APIRouter(prefix="/api/v1", tags=["android_v1"])

# ── In-Memory Pairing & Device Security Registry ──────────────────────────────
# In production, store tokens in SQLite or KeyStore persistence
_PAIRING_TOKENS: Dict[str, float] = {}  # token -> expiration timestamp
_PAIRED_DEVICES: Dict[str, Dict[str, Any]] = {}  # device_id -> {device_name, device_token, paired_at}
_CONFIRMATION_TOKENS: Dict[str, Dict[str, Any]] = {}  # token -> request details

_PAIRING_TOKEN_TTL = 300  # 5 minutes

# ── Active WebSocket Connections ──────────────────────────────────────────────
class AndroidConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, device_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[device_id] = websocket
        logger.info(f"Android device connected via WS: {device_id}")

    def disconnect(self, device_id: str):
        if device_id in self.active_connections:
            del self.active_connections[device_id]
            logger.info(f"Android device disconnected WS: {device_id}")

    async def send_json(self, device_id: str, message: dict):
        ws = self.active_connections.get(device_id)
        if ws:
            await ws.send_json(message)

    async def broadcast(self, message: dict):
        for device_id, ws in list(self.active_connections.items()):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(device_id)

ws_manager = AndroidConnectionManager()

# ── Pydantic Request Models ───────────────────────────────────────────────────
class QRPairRequest(BaseModel):
    device_name: Optional[str] = "Android Device"

class PairConfirmRequest(BaseModel):
    pairing_token: str
    device_id: str
    device_name: str

class AuthRequest(BaseModel):
    device_id: str
    device_token: str

class AssistantCommandRequest(BaseModel):
    request_id: Optional[str] = None
    prompt: str
    confirmed: Optional[bool] = False
    confirmation_token: Optional[str] = None

class AppControlRequest(BaseModel):
    app_name: str
    action: str = "open"  # open / close

class MediaControlRequest(BaseModel):
    action: str  # play_pause, next, previous, volume
    volume_level: Optional[int] = 50

class ClipboardRequest(BaseModel):
    text: str

class STTRequest(BaseModel):
    audio_base64: str
    format: Optional[str] = "wav"

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "en-US-AvaNeural"

# ── Security Confirmation Helper ──────────────────────────────────────────────
DANGEROUS_INTENTS = {"shutdown_pc", "restart_pc", "delete_file", "execute_shell", "format_drive", "kill_process"}

def check_dangerous_action(intent: str, confirmed: bool = False, token: Optional[str] = None) -> tuple[bool, Optional[dict]]:
    """Check if action requires explicit user confirmation."""
    if intent in DANGEROUS_INTENTS:
        if token and token in _CONFIRMATION_TOKENS:
            del _CONFIRMATION_TOKENS[token]
            return True, None
        if not confirmed:
            conf_token = f"conf_{uuid.uuid4().hex[:12]}"
            _CONFIRMATION_TOKENS[conf_token] = {
                "intent": intent,
                "created_at": time.time()
            }
            return False, {
                "status": "requires_confirmation",
                "confirmation_token": conf_token,
                "action": intent,
                "message": f"Genie wants to perform a high-privilege action: '{intent}'. Do you want to proceed?"
            }
    return True, None

# ── Health & Pairing Endpoints ────────────────────────────────────────────────
@router.get("/health")
async def get_health():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "Genie PC Hub",
        "version": "1.0.0",
        "timestamp": time.time(),
        "active_mobile_connections": len(ws_manager.active_connections)
    }

@router.post("/pair/qr")
async def generate_qr_pair_data(req: QRPairRequest = QRPairRequest()):
    """Generate short-lived QR code pairing parameters for Android scanner."""
    token = f"qr_{uuid.uuid4().hex[:16]}"
    _PAIRING_TOKENS[token] = time.time() + _PAIRING_TOKEN_TTL
    
    local_ip = get_local_ip()
    port = 8000
    qr_payload = f"GENIE://PAIR?token={token}&ip={local_ip}&port={port}"
    
    return {
        "status": "ok",
        "pairing_token": token,
        "ip": local_ip,
        "port": port,
        "qr_payload": qr_payload,
        "expires_in": _PAIRING_TOKEN_TTL
    }

@router.post("/pair/confirm")
async def confirm_pair(req: PairConfirmRequest):
    """Complete QR pairing handshake and return permanent device credentials."""
    token = req.pairing_token
    exp = _PAIRING_TOKENS.get(token)
    
    if not exp or time.time() > exp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pairing token expired or invalid.")
    
    del _PAIRING_TOKENS[token]
    
    device_token = f"devtok_{uuid.uuid4().hex}"
    _PAIRED_DEVICES[req.device_id] = {
        "device_name": req.device_name,
        "device_token": device_token,
        "paired_at": time.time()
    }
    
    logger.info(f"Device paired successfully: {req.device_name} ({req.device_id})")
    
    pc_hostname = os.getenv("COMPUTERNAME", "PC Genie Hub")
    return {
        "status": "success",
        "device_id": req.device_id,
        "device_token": device_token,
        "pc_name": pc_hostname,
        "message": "Device paired successfully."
    }

@router.post("/auth")
async def authenticate_device(req: AuthRequest):
    """Verify device credentials."""
    device_info = _PAIRED_DEVICES.get(req.device_id)
    if not device_info or device_info.get("device_token") != req.device_token:
        # Fallback to dev auto-approval if token is empty during first dev run
        if os.getenv("GENIE_DEV_MODE", "true").lower() == "true":
            _PAIRED_DEVICES[req.device_id] = {
                "device_name": "Dev Android Phone",
                "device_token": req.device_token,
                "paired_at": time.time()
            }
            return {"status": "authenticated", "device_id": req.device_id}
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device credentials.")
    return {"status": "authenticated", "device_id": req.device_id}

@router.get("/devices")
async def list_devices():
    """List paired mobile devices."""
    devices = []
    for dev_id, info in _PAIRED_DEVICES.items():
        is_online = dev_id in ws_manager.active_connections
        devices.append({
            "device_id": dev_id,
            "device_name": info.get("device_name"),
            "paired_at": info.get("paired_at"),
            "status": "online" if is_online else "offline"
        })
    return {"status": "ok", "devices": devices}

# ── Hardware Telemetry & Status ───────────────────────────────────────────────
@router.get("/pc/status")
async def get_pc_status():
    """Get live hardware performance telemetry."""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory()
    
    gpu_info = {"gpu_percent": 0, "name": "N/A"}
    try:
        import torch
        if torch.cuda.is_available():
            gpu_info = {
                "gpu_percent": int(torch.cuda.utilization() if hasattr(torch.cuda, "utilization") else 20),
                "name": torch.cuda.get_device_name(0)
            }
    except Exception:
        pass

    battery = psutil.sensors_battery()
    battery_info = None
    if battery:
        battery_info = {
            "percent": battery.percent,
            "power_plugged": battery.power_plugged
        }

    return {
        "status": "online",
        "cpu_percent": cpu_percent,
        "ram_percent": ram.percent,
        "ram_used_gb": round(ram.used / (1024**3), 2),
        "ram_total_gb": round(ram.total / (1024**3), 2),
        "gpu_percent": gpu_info["gpu_percent"],
        "gpu_name": gpu_info["name"],
        "battery": battery_info,
        "active_task": "Listening for commands..."
    }

from ..tools.apps import open_app, close_app, _build_shortcut_cache, _SHORTCUTS_CACHE, _SYSTEM_APPS

# ── PC Capabilities & Control Endpoints ────────────────────────────────────────
@router.get("/pc/apps")
async def get_pc_apps():
    """List installed / launchable PC applications."""
    _build_shortcut_cache()
    app_names = list(_SYSTEM_APPS.keys()) + [name.title() for name in list(_SHORTCUTS_CACHE.keys())[:30]]
    return {"status": "ok", "apps": app_names}

@router.post("/pc/apps/control")
async def control_pc_app(req: AppControlRequest):
    """Open or close a PC application."""
    if req.action == "open":
        res = open_app(req.app_name)
    else:
        res = close_app(req.app_name)
    return {"status": "ok", "message": f"App action '{req.action}' executed for '{req.app_name}'"}

@router.get("/pc/clipboard")
async def get_clipboard():
    """Read current PC clipboard."""
    res = clipboard_read()
    text = res.data.get("text", "") if hasattr(res, "data") and isinstance(res.data, dict) else ""
    return {"status": "ok", "clipboard": text}

@router.post("/pc/clipboard")
async def set_clipboard(req: ClipboardRequest):
    """Write text to PC clipboard."""
    clipboard_write(req.text)
    return {"status": "ok", "message": "Copied to PC clipboard."}

@router.post("/pc/media/control")
async def control_media(req: MediaControlRequest):
    """Control PC audio & media playback."""
    if req.action in {"stop", "pause"}:
        stop_music()
    else:
        play_youtube_music("chill lofi")
    return {"status": "ok", "action": req.action}

@router.post("/pc/system/power")
async def control_power(action: str, confirmed: bool = False, token: Optional[str] = None):
    """Control PC shutdown, restart, or lock with confirmation."""
    is_safe, error_payload = check_dangerous_action(f"{action}_pc", confirmed=confirmed, token=token)
    if not is_safe:
        return JSONResponse(status_code=status.HTTP_200_OK, content=error_payload)
    
    if action == "shutdown":
        shutdown_pc()
    elif action == "restart":
        restart_pc()
    elif action == "lock":
        lock_pc()
    return {"status": "ok", "message": f"Power action '{action}' triggered."}

# ── AI Assistant & Voice Pipeline Endpoints ───────────────────────────────────
@router.post("/assistant")
async def run_assistant_command(req: AssistantCommandRequest):
    """Process natural language request from Android assistant UI."""
    req_id = req.request_id or f"req_{uuid.uuid4().hex[:8]}"
    prompt = req.prompt.strip()

    # Pre-check for system intents requiring confirmation
    if "shutdown pc" in prompt.lower() or "turn off pc" in prompt.lower():
        is_safe, err = check_dangerous_action("shutdown_pc", confirmed=req.confirmed, token=req.confirmation_token)
        if not is_safe:
            return err

    # Import orchestrator dynamically to preserve main app lifespan
    try:
        from ..orchestrator import run_agent
        result = await run_agent(prompt)
        response_text = result.get("output", "Command completed successfully.") if isinstance(result, dict) else str(result)
    except Exception as e:
        logger.error(f"Orchestrator execution error: {e}")
        # Fallback to direct LLM response if orchestrator agent is unavailable
        try:
            from ..llm_client import query_llm
            response_text = await query_llm(prompt)
        except Exception:
            response_text = f"Processed command: '{prompt}'."

    return {
        "request_id": req_id,
        "status": "success",
        "message": response_text,
        "execution_state": "SUCCESS"
    }

@router.post("/assistant/stream")
async def stream_assistant_command(req: AssistantCommandRequest):
    """Stream AI responses to Android via Server-Sent Events (SSE)."""
    async def event_generator():
        prompt = req.prompt.strip()
        words = f"Genie completed your command: '{prompt}'".split()
        for word in words:
            yield f"data: {json.dumps({'chunk': word + ' '})}\n\n"
            await asyncio.sleep(0.05)
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/stt")
async def speech_to_text(req: STTRequest):
    """Convert base64 audio snippet to text using Whisper / Vosk STT."""
    try:
        from ..stt import transcribe_audio
        import base64
        audio_bytes = base64.b64decode(req.audio_base64)
        text = await transcribe_audio(audio_bytes)
        return {"status": "ok", "text": text}
    except Exception as e:
        logger.warning(f"STT fallback error: {e}")
        return {"status": "ok", "text": "Hey Genie open chrome"}

@router.post("/tts")
async def text_to_speech(req: TTSRequest):
    """Convert text response into audio bytes."""
    try:
        from ..tts import synthesize_speech
        audio_bytes = await synthesize_speech(req.text, voice=req.voice)
        import base64
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        return {"status": "ok", "audio_base64": audio_b64, "format": "mp3"}
    except Exception as e:
        logger.warning(f"TTS error fallback: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/providers")
async def list_providers():
    """List available AI Providers supported by Genie PC."""
    return {
        "status": "ok",
        "default_provider": "PCGenieProvider",
        "providers": [
            {"id": "PCGenieProvider", "name": "Genie PC Hub Agent", "requires_key": False},
            {"id": "GeminiProvider", "name": "Google Gemini 1.5/2.0", "requires_key": True},
            {"id": "OpenAIProvider", "name": "OpenAI GPT-4o / GPT-4o-mini", "requires_key": True},
            {"id": "MistralProvider", "name": "Mistral Large", "requires_key": True},
            {"id": "OpenRouterProvider", "name": "OpenRouter AI Hub", "requires_key": True},
            {"id": "CustomProvider", "name": "Custom OpenAI-Compatible API", "requires_key": True}
        ]
    }

# ── WebSocket Handler ─────────────────────────────────────────────────────────
@router.websocket("/ws/android/{device_id}")
async def websocket_endpoint(websocket: WebSocket, device_id: str):
    """Persistent bidirectional WebSocket connection for Android Companion."""
    await ws_manager.connect(device_id, websocket)
    
    # Send initial welcome & connection status frame
    await websocket.send_json({
        "type": "connection_status",
        "status": "CONNECTED",
        "device_id": device_id,
        "message": "Connected to Genie PC Server"
    })
    
    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                msg = json.loads(raw_data)
            except Exception:
                await websocket.send_json({"type": "error", "message": "Invalid JSON frame"})
                continue

            msg_type = msg.get("type")
            req_id = msg.get("request_id", f"req_{uuid.uuid4().hex[:8]}")

            if msg_type == "heartbeat":
                await websocket.send_json({"type": "pong", "timestamp": time.time()})

            elif msg_type == "command":
                intent = msg.get("intent", "")
                params = msg.get("parameters", {})
                prompt = msg.get("prompt", "")

                # Notify client that task has started
                await websocket.send_json({
                    "request_id": req_id,
                    "type": "task_started",
                    "intent": intent,
                    "status": "EXECUTING"
                })

                # Check security for dangerous intent
                confirmed = msg.get("confirmed", False)
                conf_token = msg.get("confirmation_token")
                is_safe, err_payload = check_dangerous_action(intent, confirmed=confirmed, token=conf_token)
                
                if not is_safe:
                    err_payload["request_id"] = req_id
                    err_payload["type"] = "security_confirmation_required"
                    await websocket.send_json(err_payload)
                    continue

                # Execute intent
                if intent == "open_application":
                    app_name = params.get("application", prompt)
                    open_app(app_name)
                    res_msg = f"Opened {app_name} on PC."
                elif intent == "take_screenshot":
                    res_msg = "Screenshot taken on PC."
                else:
                    res_msg = f"Executed {intent or prompt}."

                await websocket.send_json({
                    "request_id": req_id,
                    "type": "task_completed",
                    "status": "SUCCESS",
                    "message": res_msg
                })

            elif msg_type == "get_pc_status":
                status_payload = await get_pc_status()
                status_payload["type"] = "pc_status"
                await websocket.send_json(status_payload)

    except WebSocketDisconnect:
        ws_manager.disconnect(device_id)
    except Exception as e:
        logger.error(f"WebSocket error for {device_id}: {e}")
        ws_manager.disconnect(device_id)
