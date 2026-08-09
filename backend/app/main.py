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
import os
import time
import urllib.request
from contextlib import asynccontextmanager
from typing import Optional

# Disable non-critical HuggingFace Hub warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Ensure av's FFmpeg DLLs and nvidia CUDA DLLs (cublas, cudnn) are registered at process startup
if os.name == 'nt':
    try:
        import importlib.util
        _av_spec = importlib.util.find_spec('av')
        if _av_spec and _av_spec.submodule_search_locations:
            _av_dir = list(_av_spec.submodule_search_locations)[0]
            _av_libs = os.path.abspath(os.path.join(_av_dir, os.pardir, 'av.libs'))
            if os.path.exists(_av_libs) and hasattr(os, 'add_dll_directory'):
                try:
                    os.add_dll_directory(_av_libs)
                except Exception:
                    pass
            _path_env = os.environ.get('PATH', '')
            if _av_libs not in _path_env:
                os.environ['PATH'] = _av_libs + os.pathsep + _path_env

        _nv_spec = importlib.util.find_spec('nvidia')
        if _nv_spec and _nv_spec.submodule_search_locations:
            _nv_dir = list(_nv_spec.submodule_search_locations)[0]
            for _root, _dirs, _files in os.walk(_nv_dir):
                if os.path.basename(_root) == 'bin':
                    try:
                        os.add_dll_directory(_root)
                    except Exception:
                        pass
                    _path_env = os.environ.get('PATH', '')
                    if _root not in _path_env:
                        os.environ['PATH'] = _root + os.pathsep + _path_env
        import av  # noqa: F401 - Preload av into sys.modules
    except Exception:
        pass

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from . import llm_client, ngrok_tunnel, orchestrator
from .api.external import router as external_api_router
from .api.music import router as music_api_router
from .api.mobile import router as mobile_api_router
from .api.v1_android import router as v1_android_router
from .services.mdns_server import start_mdns_service, stop_mdns_service
from .auth import Session, get_session, issue_token, verify_pin
from .config import get_settings
from .os import get_kernel
from .schemas import WSIn
# Importing tools registers them via the @tool decorator side effect.
from .tools import TOOL_MANIFESTS, TOOL_SCHEMAS  # noqa: F401
# Conversation Engine (Genie v2) — now uses VoicePipeline
from .engine import get_voice_pipeline
# Health check
from .services.health_check import run_startup_health_check

settings = get_settings()
kernel = get_kernel()

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

# #region debug-point B:websocket-events
def _debug_ws_event(hypothesis_id: str, location: str, msg: str, data: Optional[dict] = None) -> None:
    pass
# #endregion

# ── Per-session token bucket (H9 fix: deque instead of list for O(1) eviction) ─
from collections import deque as _deque

_SESSION_RATE_LIMIT_RPM = 20     # max turns per minute per session
_SESSION_BUCKET: dict[str, _deque[float]] = {}   # session_id -> deque of timestamps


def _session_allow_request(session_id: str) -> tuple[bool, int]:
    """Token-bucket check. Returns (allowed, retry_after_seconds)."""
    now    = time.time()
    if session_id not in _SESSION_BUCKET:
        _SESSION_BUCKET[session_id] = _deque()
    bucket = _SESSION_BUCKET[session_id]
    # Evict timestamps older than 60 s — O(1) with deque.popleft()
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
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

    provider = llm_client.get_provider_config(settings)
    log.info(
        "llm_provider_configured",
        provider=provider.id,
        label=provider.label,
        model=provider.model,
        base_url=provider.base_url,
        api_key_configured=bool(provider.api_key),
    )
    if provider.id == "groq":
        log.warning(
            "llm_provider_groq_cloud_selected",
            note="LLM_PROVIDER=groq means Groq Cloud. Use LLM_PROVIDER=grok for xAI/Grok.",
        )

    # Eagerly load the offline local LLM so it's instantly ready.
    from .services.local_llm import local_llm
    if local_llm.is_enabled(settings):
        log.info("local_llm_loading")
        await asyncio.to_thread(local_llm.is_available, settings)
        if local_llm.is_available(settings):
            log.info("local_llm_ready")
        else:
            log.warning("local_llm_failed", error=local_llm.load_error)

    # Always initialise the websocket registry — wake word callback needs it
    # regardless of whether the wake word engine starts successfully.
    if not hasattr(app.state, "active_websockets"):
        app.state.active_websockets = set()

    # Run startup health check (lightweight — no PyAudio, avoids mic conflict)
    log.info("running_startup_health_check")
    health_passed = await run_startup_health_check(settings)
    if not health_passed:
        log.warning("health_check_failed_critical", note="Voice system may not function properly")
    app.state.health_check_passed = health_passed

    # Initialize the voice pipeline (opens mic, starts workers)
    pipeline = get_voice_pipeline()
    await pipeline.start()
    app.state.engine = pipeline
    log.info("voice_pipeline_started")

    # Initialize TTS model on startup in the background so it doesn't block the server
    from .tts import init_tts_model
    log.info("tts_initializing_in_background")

    # M8 fix: monitor the TTS init task for errors instead of fire-and-forget
    async def _tts_init_with_error_handling():
        try:
            await asyncio.to_thread(init_tts_model)
            log.info("tts_model_loaded_successfully")
        except Exception as e:
            log.error("tts_model_init_failed", error=str(e))
            # TTS will gracefully fail on first real call — no crash

    app.state.tts_init_task = asyncio.create_task(_tts_init_with_error_handling())

    # Periodic cleanup task: clean expired sessions & conversation contexts every 30 min
    async def _periodic_cleanup():
        from .auth import cleanup_expired_sessions
        from .engine.brain.context import context_store
        while True:
            await asyncio.sleep(30 * 60)  # every 30 minutes
            try:
                sessions_cleaned = cleanup_expired_sessions(settings)
                contexts_cleaned = context_store.cleanup_old_sessions(max_age_hours=24)
                if sessions_cleaned or contexts_cleaned:
                    log.info(
                        "periodic_cleanup",
                        sessions=sessions_cleaned,
                        contexts=contexts_cleaned,
                    )
            except Exception as e:
                log.warning("periodic_cleanup_error", error=str(e))

    app.state.cleanup_task = asyncio.create_task(_periodic_cleanup())

    # Start mDNS Zeroconf service for Android auto-discovery
    start_mdns_service(settings.port)

    # Initialize Companion Manager (lazy — does nothing until activated by voice intent)
    from .companion.manager import companion_manager
    app.state.companion = companion_manager
    log.info("companion_manager_initialized")

    yield

    # Cleanup
    stop_mdns_service()
    # Stop companion cleanly (zero orphaned tasks)
    if hasattr(app.state, "companion"):
        try:
            await app.state.companion.stop()
        except Exception:
            pass
    if hasattr(app.state, "cleanup_task"):
        app.state.cleanup_task.cancel()
    if hasattr(app.state, "engine"):
        await app.state.engine.stop()
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
app.include_router(mobile_api_router, prefix="/api/v1")
app.include_router(v1_android_router)


# ── REST endpoints ────────────────────────────────────────────────────────────
@app.get("/health")
async def health() -> dict:
    from .services.api_manager import api_manager
    from .services.circuit_breaker import all_circuit_breaker_statuses

    return {
        "status": "ok",
        "service": "genie",
        "version": "1.0.0",
        "ready": True,
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


@app.get("/api/v1/system/status")
async def system_status() -> dict:
    """Genie OS kernel snapshot for migration diagnostics."""
    snapshot = kernel.snapshot()
    return {
        "status": "ok",
        "kernel": {
            "recent_task_count": len(snapshot["tasks"]),
            "recent_event_count": len(snapshot["events"]),
            "tasks": snapshot["tasks"],
            "events": snapshot["events"],
            "permissions": snapshot["permissions"],
        },
    }


@app.get("/api/v1/tasks")
async def list_tasks(limit: int = 25) -> dict:
    """Recent Genie OS tasks."""
    return {
        "status": "ok",
        "tasks": [task.to_dict() for task in kernel.tasks.recent(limit)],
    }


@app.get("/api/v1/tasks/{task_id}")
async def get_task(task_id: str) -> JSONResponse:
    """Task detail with events and checkpoints."""
    task = kernel.tasks.get(task_id)
    if task is None:
        return JSONResponse({"error": "task_not_found", "task_id": task_id}, status_code=404)
    return JSONResponse({
        "status": "ok",
        "task": task.to_dict(),
        "events": [event.to_dict() for event in kernel.events.for_task(task_id)],
        "checkpoints": [item.to_dict() for item in kernel.checkpoints.for_task(task_id)],
    })


@app.post("/api/v1/tasks/{task_id}/cancel")
async def cancel_task(task_id: str) -> JSONResponse:
    """Cancel a tracked task from an OS client."""
    task = kernel.cancel_task(task_id, "api_cancelled")
    if task is None:
        return JSONResponse({"error": "task_not_found", "task_id": task_id}, status_code=404)
    return JSONResponse({"status": "ok", "task": task.to_dict()})


@app.get("/api/v1/context/snapshot")
async def context_snapshot() -> dict:
    """Current structured desktop/user context."""
    from .core.context.engine import context_engine

    return {"status": "ok", "context": context_engine.snapshot()}


@app.get("/api/v1/memory/search")
async def memory_search(q: str = "", limit: int = 8) -> dict:
    """Search durable local companion memory."""
    from .tools.memory_db import companion_db

    query = (q or "").strip()
    results = companion_db.search_memory(query, limit=limit) if query else companion_db.get_memory(limit=limit)
    return {"status": "ok", "query": query, "results": results}


@app.get("/api/v1/tools")
async def list_tools() -> dict:
    """Registered tool manifests with runtime policy metadata."""
    return {"status": "ok", "tools": TOOL_MANIFESTS}


@app.post("/api/v1/tools/{tool_name}/invoke")
async def invoke_tool(tool_name: str, payload: dict) -> JSONResponse:
    """Invoke a registered tool through the OS permission boundary."""
    from .os.permissions import CONFIRMATION_LEVELS
    from .tools import execute_tool
    from .tools.registry import REGISTRY

    entry = REGISTRY.get(tool_name)
    if entry is None:
        return JSONResponse({"error": "tool_not_found", "tool": tool_name}, status_code=404)

    arguments = (payload or {}).get("arguments") or {}
    task_id = (payload or {}).get("task_id")
    if entry.side_effect_level in CONFIRMATION_LEVELS:
        request = kernel.request_permission(
            risk=entry.side_effect_level,
            description=f"Allow Genie to run {tool_name}",
            source="tool.api",
            task_id=task_id,
            payload={"tool": tool_name, "arguments": arguments},
        )
        return JSONResponse(
            {
                "status": "permission_required",
                "permission": request.to_dict(),
            },
            status_code=202,
        )

    result = await asyncio.to_thread(execute_tool, tool_name, arguments)
    return JSONResponse({"status": "ok", "result": result.model_dump()})


@app.get("/api/v1/permissions/pending")
async def pending_permissions() -> dict:
    """Pending permission requests for the local user."""
    return {
        "status": "ok",
        "permissions": [request.to_dict() for request in kernel.permissions.pending()],
    }


@app.post("/api/v1/permissions/{request_id}")
async def decide_permission(request_id: str, payload: dict) -> JSONResponse:
    """Approve or deny a pending permission request."""
    approved = bool((payload or {}).get("approved"))
    reason = str((payload or {}).get("reason") or "")
    request = kernel.decide_permission(request_id, approved=approved, reason=reason)
    if request is None:
        return JSONResponse({"error": "permission_not_found", "request_id": request_id}, status_code=404)
    return JSONResponse({"status": "ok", "permission": request.to_dict()})


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

    task = kernel.begin_user_turn(
        session_id=session.session_id,
        input_text=text,
        source="gateway.rest",
    )
    try:
        await orchestrator.handle_user_turn(session, text, emit, settings)
    except asyncio.CancelledError:
        kernel.cancel_task(task.task_id, "rest_turn_cancelled")
        raise
    except Exception as exc:
        kernel.fail_task(task.task_id, f"{type(exc).__name__}: {exc}")
        raise

    reply = "".join(m["delta"] for m in captured).strip()
    kernel.complete_task(task.task_id, {"reply_length": len(reply)})
    return JSONResponse({
        "reply": reply,
        "session_id": session.session_id,
        "task_id": task.task_id,
        "trace_id": task.trace_id,
    })


# ── WebSocket endpoint ────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    session: Optional[Session] = None
    current_task: Optional[asyncio.Task] = None
    in_flight_request_text: Optional[str] = None

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



            # ── Binary frame (Audio Chunk) ────────────────────────────────────
            bytes_data = message.get("bytes")
            if bytes_data is not None:
                if session and hasattr(app.state, "engine"):
                    # Web/Android client streaming binary audio frame
                    pass
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
                _debug_ws_event(
                    "B",
                    "main.py:websocket:auth_ok",
                    "websocket authenticated",
                    {"session_id": session.session_id},
                )
                await emit({
                    "type":       "auth_ok",
                    "token":      session.token,
                    "session_id": session.session_id,
                })
                url = ngrok_tunnel.get_public_url()
                if url:
                    await emit({"type": "public_url", "url": url})
                    
                # Bind session to conversation engine
                if hasattr(app.state, "engine"):
                    app.state.engine.set_session(session, emit)
                    
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
                _debug_ws_event(
                    "B",
                    "main.py:websocket:cancel",
                    "cancel received",
                    {
                        "session_id": session.session_id,
                        "had_current_task": bool(current_task and not current_task.done()),
                    },
                )
                if hasattr(app.state, "engine"):
                    await app.state.engine.on_cancel()
                continue

            if mtype == "manual_wake":
                if hasattr(app.state, "engine"):
                    await app.state.engine.on_manual_wake()
                continue

            # ── Text turn ─────────────────────────────────────────────────────
            if mtype == "text":
                user_text = (msg_in.text or "").strip()
                if not user_text:
                    continue
                if current_task and not current_task.done():
                    if in_flight_request_text == user_text:
                        log.debug("deduplicated_text_request", text=user_text)
                        continue
                    current_task.cancel()
                in_flight_request_text = user_text

                # Use engine for text turns now
                if hasattr(app.state, "engine"):
                    await app.state.engine.on_text_input(user_text)
                continue



            # ── Confirm (for future Phase 2 tool confirmation gate) ───────────
            if mtype == "confirm":
                # Phase 2 will implement the confirmation flow.
                # For now, acknowledge receipt.
                log.debug("confirm_received", confirmed=msg_in.confirmed)
                continue

            # ── Playback Complete (triggers follow-up listening) ──────────────
            if mtype == "playback_complete":
                _debug_ws_event(
                    "E",
                    "main.py:websocket:playback_complete",
                    "frontend playback complete",
                    {"session_id": session.session_id},
                )
                if hasattr(app.state, "engine"):
                    await app.state.engine.on_playback_complete()
                continue

            # ── Companion Mode control messages ───────────────────────────────
            if mtype in ("companion_start", "companion_stop", "companion_pause",
                         "companion_resume", "companion_set_mode", "companion_hotkey_analyze",
                         "companion_quick_look"):
                if hasattr(app.state, "companion"):
                    companion = app.state.companion
                    # Bind the current session emitter so companion can send WS messages
                    companion.set_emit(emit)
                    try:
                        if mtype == "companion_start":
                            from .companion.manager import CompanionSubMode
                            raw_mode = (msg_in.mode or "general").lower()
                            sub_mode = CompanionSubMode(raw_mode) if raw_mode in CompanionSubMode._value2member_map_ else CompanionSubMode.GENERAL
                            await companion.start(
                                sub_mode=sub_mode,
                                personality_preset=settings.companion_default_personality,
                            )
                        elif mtype == "companion_stop":
                            await companion.stop()
                        elif mtype == "companion_pause":
                            await companion.pause()
                        elif mtype == "companion_resume":
                            await companion.resume()
                        elif mtype == "companion_set_mode":
                            from .companion.manager import CompanionSubMode
                            raw_mode = (msg_in.mode or "general").lower()
                            sub_mode = CompanionSubMode(raw_mode) if raw_mode in CompanionSubMode._value2member_map_ else CompanionSubMode.GENERAL
                            await companion.set_mode(sub_mode)
                        elif mtype == "companion_hotkey_analyze":
                            # On-demand single analysis (GameCompanionAI-style fallback)
                            if companion.is_active and companion._observation_loop:
                                asyncio.create_task(
                                    companion._observation_loop._observe_once(),
                                    name="companion_hotkey_observe",
                                )
                        elif mtype == "companion_quick_look":
                            # Quick Look ("Look & Answer" fast path)
                            asyncio.create_task(
                                companion.quick_look(question=msg_in.text),
                                name="companion_quick_look_task",
                            )
                    except Exception as exc:
                        # Companion failure never affects base Genie
                        log.warning("companion_ws_handler_error", mtype=mtype, error=str(exc))
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
