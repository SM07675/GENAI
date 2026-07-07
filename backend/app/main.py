"""Genie FastAPI server: WebSocket endpoint + REST helpers + lifecycle hooks.

Startup:
  * imports the tools package (registers all tools)
  * starts the ngrok tunnel (if enabled) and advertises the public URL

WebSocket protocol lives here. One persistent `/ws` connection per client.
Auth happens on the first `hello` frame (PIN check); subsequent frames drive
the conversation via the orchestrator.
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import ngrok_tunnel, orchestrator
from .auth import Session, get_session, issue_token, verify_pin
from .config import get_settings
# Importing tools registers them via the @tool decorator side effect.
from .tools import TOOL_SCHEMAS  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("genie.main")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the ngrok tunnel on boot, tear it down on shutdown."""
    public_url = ngrok_tunnel.start_tunnel(settings.port, settings)
    if public_url:
        log.info("Public URL for mobile: %s", public_url)
    log.info("Genie PIN: %s", settings.effective_pin)
    yield
    ngrok_tunnel.stop_tunnel()
    log.info("Genie shutting down.")


app = FastAPI(title="Genie Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================================
# REST endpoints (handy for smoke tests / non-WS clients)
# =====================================================================
@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "pin_configured": bool(settings.genie_pin),
        "tools": [t["function"]["name"] for t in TOOL_SCHEMAS],
    }


@app.get("/info")
async def info() -> dict:
    """Public info: ngrok URL + whether a PIN is required (no secrets)."""
    return {
        "public_url": ngrok_tunnel.get_public_url(),
        "requires_pin": True,
    }


@app.post("/chat")
async def rest_chat(payload: dict) -> JSONResponse:
    """Synchronous one-shot chat (no streaming). Returns the spoken reply."""
    text = (payload or {}).get("text", "").strip()
    if not text:
        return JSONResponse({"error": "missing 'text'"}, status_code=400)

    # Reuse or create an ephemeral session for this REST call.
    from .auth import session_by_id
    session = session_by_id(payload.get("session_id", "rest")) or issue_token("rest")

    captured: list[dict] = []

    async def emit(msg: dict) -> None:
        if msg["type"] == "assistant_text" and msg.get("delta"):
            captured.append(msg)

    await orchestrator.handle_user_turn(session, text, emit, settings)
    reply = "".join(m["delta"] for m in captured).strip()
    return JSONResponse({"reply": reply, "session_id": session.session_id})


# =====================================================================
# WebSocket endpoint
# =====================================================================
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    session: Session | None = None
    audio_buffer: bytearray = bytearray()
    current_task: asyncio.Task | None = None

    async def emit(msg: dict) -> None:
        """Send a JSON protocol message to the client; swallow send errors."""
        try:
            await ws.send_text(json.dumps(msg))
        except Exception:  # noqa: BLE001 - client may have disconnected
            pass

    try:
        while True:
            # Receive either a text (JSON) frame or a binary (audio) frame.
            message = await ws.receive()

            # ---- Binary audio frame -------------------------------------
            if "bytes" in message and message["bytes"] is not None:
                if session is None:
                    continue  # ignore audio until authenticated
                audio_buffer.extend(message["bytes"])
                continue

            # ---- Text (JSON) frame --------------------------------------
            raw = message.get("text")
            if raw is None:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await emit({"type": "error", "message": "Invalid JSON."})
                continue

            mtype = data.get("type")

            # --- Auth handshake -----------------------------------------
            if mtype == "hello":
                pin = str(data.get("pin") or "")
                if not verify_pin(pin, settings):
                    await emit({"type": "auth_fail"})
                    # Keep the socket open so the UI can retry without reconnect.
                    continue
                session = issue_token()
                await emit({"type": "auth_ok", "token": session.token,
                            "session_id": session.session_id})
                url = ngrok_tunnel.get_public_url()
                if url:
                    await emit({"type": "public_url", "url": url})
                continue

            # Everything below requires an authenticated session.
            if session is None:
                await emit({"type": "error",
                            "message": "Authenticate first with a hello+PIN frame."})
                continue

            # --- Cancel an in-flight turn --------------------------------
            if mtype == "cancel":
                if current_task and not current_task.done():
                    current_task.cancel()
                await emit({"type": "orb_state", "state": "idle"})
                continue

            # --- Text turn -----------------------------------------------
            if mtype == "text":
                user_text = (data.get("text") or "").strip()
                if not user_text:
                    continue
                # One turn at a time; cancel any prior turn.
                if current_task and not current_task.done():
                    current_task.cancel()
                current_task = asyncio.create_task(
                    orchestrator.handle_user_turn(session, user_text, emit, settings)
                )
                continue

            # --- End of audio -> transcribe -> turn ----------------------
            if mtype == "audio_end":
                audio_bytes = bytes(audio_buffer)
                audio_buffer.clear()
                if not audio_bytes:
                    continue
                await emit({"type": "orb_state", "state": "listening"})
                # Transcribe off the event loop, then run the turn.
                from . import stt
                transcript = await stt.transcribe(audio_bytes, settings)
                if not transcript:
                    await emit({"type": "error",
                                "message": "I didn't catch any speech."})
                    await emit({"type": "orb_state", "state": "idle"})
                    continue
                await emit({"type": "transcript", "text": transcript})
                if current_task and not current_task.done():
                    current_task.cancel()
                current_task = asyncio.create_task(
                    orchestrator.handle_user_turn(session, transcript, emit, settings)
                )
                continue

            await emit({"type": "error",
                        "message": f"Unknown message type: {mtype}"})

    except WebSocketDisconnect:
        log.info("Client disconnected from /ws")
    except Exception as e:  # noqa: BLE001
        log.exception("WebSocket error: %s", e)
    finally:
        if current_task and not current_task.done():
            current_task.cancel()
