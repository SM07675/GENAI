"""Genie FastAPI server: WebSocket endpoint + REST helpers + lifecycle hooks.

Enterprise hardening
--------------------
- Inbound WebSocket JSON is validated through `WSIn` (Pydantic); malformed
  frames get a clean `error` response instead of an unhandled exception.
- `heartbeat` / `pong` keep-alive protocol: client sends heartbeat, server
  responds with pong. Detects dead connections faster than TCP keepalive.
- Per-session token-bucket rate limiting: clients that flood the server get a
  friendly `rate_limited` message rather than a dropped connection.
- Structlog is configured at startup so all loggers emit JSON lines in
  production (human-friendly in dev).
- Circuit breaker statuses are exposed in the `/health` endpoint.
- Broad `except Exception` in the lifespan wake-word block is replaced with
  typed catches.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from . import ngrok_tunnel, orchestrator
from .api.external import router as external_api_router
from .api.music import router as music_api_router
from .auth import Session, get_session, issue_token, verify_pin
from .config import get_settings
from .schemas import WSIn
# Importing tools registers them via the @tool decorator side effect.
from .tools import TOOL_SCHEMAS  # noqa: F401

settings = get_settings()

# ── Logging setup ─────────────────────────────────────────────────────────────
# Use structlog with a processor chain. In dev the renderer is pretty-printed;
# in production it should be JSON (set GENIE_LOG_JSON=true).
import os as _os
_use_json_logs = _os.getenv("GENIE_LOG_JSON", "false").lower() in ("1", "true", "yes")

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer() if _use_json_logs
        else structlog.dev.ConsoleRenderer(colors=True),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",    # structlog already formats the message
)

log = structlog.get_logger("genie.main")

# ── Per-session token bucket ──────────────────────────────────────────────────
_SESSION_RATE_LIMIT_RPM = 20     # max turns per minute per session
_SESSION_BUCKET: dict[str, list[float]] = {}   # session_id -> list of timestamps


def _session_allow_request(session_id: str) -> tuple[bool, int]:
    """Token-bucket check. Returns (allowed, retry_after_seconds)."""
    now    = time.time()
    bucket = _SESSION_BUCKET.setdefault(session_id, [])
    # Evict timestamps older than 60 s
    while bucket and now - bucket[0] > 60:
        bucket.pop(0)
    if len(bucket) >= _SESSION_RATE_LIMIT_RPM:
        oldest      = bucket[0]
        retry_after = int(60.0 - (now - oldest)) + 1
        return False, retry_after
    bucket.append(now)
    return True, 0


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the ngrok tunnel on boot, tear it down on shutdown."""
    public_url = ngrok_tunnel.start_tunnel(settings.port, settings)
    if public_url:
        log.info("ngrok_tunnel_started", url=public_url)
    log.info("genie_pin", pin=settings.effective_pin)

    # Eagerly load the offline local LLM so it's instantly ready.
    from .services.local_llm import local_llm
    if local_llm.is_enabled(settings):
        log.info("local_llm_loading")
        await asyncio.to_thread(local_llm.is_available, settings)
        if local_llm.is_available(settings):
            log.info("local_llm_ready")
        else:
            log.warning("local_llm_failed", error=local_llm.load_error)

    # Start wake word detection if enabled.
    wake_detector = None
    if settings.wake_word_enabled:
        try:
            from .wake_word import WakeWordDetector

            loop = asyncio.get_running_loop()
            app.state.active_websockets = set()

            def on_wake_word() -> None:
                log.info("wake_word_detected")
                for ws_client in list(app.state.active_websockets):
                    asyncio.run_coroutine_threadsafe(
                        ws_client.send_text(json.dumps({"type": "wake_word_detected"})),
                        loop,
                    )

            wake_detector = WakeWordDetector(
                callback=on_wake_word,
                engine=settings.wake_word_engine,
                keywords=settings.wake_word_keywords,
            )
            wake_detector.start()
            app.state.wake_detector = wake_detector
            log.info("wake_word_enabled", keywords=settings.wake_word_keywords)

        except ImportError as e:
            log.warning("wake_word_import_failed", error=str(e))
        except OSError as e:
            log.warning("wake_word_audio_failed", error=str(e))
        except RuntimeError as e:
            log.warning("wake_word_start_failed", error=str(e))

    yield

    # Cleanup
    if wake_detector:
        wake_detector.stop()
    ngrok_tunnel.stop_tunnel()
    log.info("genie_shutdown")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Genie Backend", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(external_api_router, prefix="/api/v1")
app.include_router(music_api_router, prefix="/api/v1")


# ── REST endpoints ────────────────────────────────────────────────────────────
@app.get("/health")
async def health() -> dict:
    from .services.api_manager import api_manager
    from .services.circuit_breaker import all_circuit_breaker_statuses

    return {
        "status": "ok",
        "pin_configured": bool(settings.genie_pin),
        "tools": [t["function"]["name"] for t in TOOL_SCHEMAS],
        "apis": api_manager.status(),
        "circuit_breakers": all_circuit_breaker_statuses(),
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

    from .auth import session_by_id
    session = session_by_id(payload.get("session_id", "rest")) or issue_token("rest")

    captured: list[dict] = []

    async def emit(msg: dict) -> None:
        if msg["type"] == "assistant_text" and msg.get("delta"):
            captured.append(msg)

    await orchestrator.handle_user_turn(session, text, emit, settings)
    reply = "".join(m["delta"] for m in captured).strip()
    return JSONResponse({"reply": reply, "session_id": session.session_id})


# ── WebSocket endpoint ────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    session: Optional[Session] = None
    audio_buffer: bytearray    = bytearray()
    current_task: Optional[asyncio.Task] = None

    async def emit(msg: dict) -> None:
        """Send a JSON protocol message to the client; swallow send errors."""
        try:
            await ws.send_text(json.dumps(msg))
        except (WebSocketDisconnect, RuntimeError):
            pass   # client disconnected

    try:
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                raise WebSocketDisconnect(message.get("code", 1000))

            # ── Binary audio frame ────────────────────────────────────────────
            if "bytes" in message and message["bytes"] is not None:
                if session is None:
                    continue  # ignore audio until authenticated
                audio_buffer.extend(message["bytes"])
                continue

            # ── Text (JSON) frame ─────────────────────────────────────────────
            raw = message.get("text")
            if raw is None:
                continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await emit({"type": "error", "message": "Invalid JSON.", "code": "parse_error"})
                continue

            # Validate via Pydantic — reject unknown/malformed types cleanly.
            try:
                msg_in = WSIn(**data)
            except ValidationError as ve:
                mtype_raw = data.get("type", "<unknown>")
                await emit({
                    "type":    "error",
                    "message": f"Unknown or malformed message type '{mtype_raw}'.",
                    "code":    "invalid_message",
                })
                continue

            mtype = msg_in.type

            # ── Heartbeat (keep-alive) ────────────────────────────────────────
            if mtype == "heartbeat":
                await emit({"type": "pong"})
                continue

            # ── Auth handshake ────────────────────────────────────────────────
            if mtype == "hello":
                pin = str(msg_in.pin or "")
                if not verify_pin(pin, settings):
                    await emit({"type": "auth_fail"})
                    # Keep socket open so the UI can retry without reconnect.
                    continue
                session = issue_token()
                if hasattr(app.state, "active_websockets"):
                    app.state.active_websockets.add(ws)
                await emit({
                    "type":       "auth_ok",
                    "token":      session.token,
                    "session_id": session.session_id,
                })
                url = ngrok_tunnel.get_public_url()
                if url:
                    await emit({"type": "public_url", "url": url})
                continue

            # Everything below requires an authenticated session.
            if session is None:
                await emit({
                    "type":    "error",
                    "message": "Authenticate first with a hello+PIN frame.",
                    "code":    "unauthenticated",
                })
                continue

            # ── Per-session rate limit ────────────────────────────────────────
            if mtype in ("text", "audio_end"):
                allowed, retry_after = _session_allow_request(session.session_id)
                if not allowed:
                    await emit({
                        "type":                 "rate_limited",
                        "message":              "You're sending too quickly. Please slow down.",
                        "retry_after_seconds":  retry_after,
                    })
                    continue

            # ── Cancel an in-flight turn ──────────────────────────────────────
            if mtype == "cancel":
                if current_task and not current_task.done():
                    current_task.cancel()
                await emit({"type": "orb_state", "state": "idle"})
                continue

            # ── Text turn ─────────────────────────────────────────────────────
            if mtype == "text":
                user_text = (msg_in.text or "").strip()
                if not user_text:
                    continue
                if current_task and not current_task.done():
                    current_task.cancel()
                current_task = asyncio.create_task(
                    orchestrator.handle_user_turn(session, user_text, emit, settings)
                )
                continue

            # ── End of audio -> transcribe -> turn ────────────────────────────
            if mtype == "audio_end":
                audio_bytes = bytes(audio_buffer)
                audio_buffer.clear()
                if not audio_bytes:
                    continue
                await emit({"type": "orb_state", "state": "listening"})
                from . import stt
                transcript = await stt.transcribe(audio_bytes, settings)
                if not transcript:
                    await emit({
                        "type":    "error",
                        "message": "I didn't catch any speech. Please try again.",
                        "code":    "empty_transcript",
                    })
                    await emit({"type": "orb_state", "state": "idle"})
                    continue
                await emit({"type": "transcript", "text": transcript})
                if current_task and not current_task.done():
                    current_task.cancel()
                current_task = asyncio.create_task(
                    orchestrator.handle_user_turn(session, transcript, emit, settings)
                )
                continue

            # ── Confirm (for future Phase 2 tool confirmation gate) ───────────
            if mtype == "confirm":
                # Phase 2 will implement the confirmation flow.
                # For now, acknowledge receipt.
                log.debug("confirm_received", confirmed=msg_in.confirmed)
                continue

    except WebSocketDisconnect:
        log.info("ws_client_disconnected")
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        log.exception("ws_unexpected_error", error=str(exc), error_type=type(exc).__name__)
    finally:
        if hasattr(app.state, "active_websockets") and ws in app.state.active_websockets:
            app.state.active_websockets.discard(ws)
        if current_task and not current_task.done():
            current_task.cancel()
        if session:
            _SESSION_BUCKET.pop(session.session_id, None)
