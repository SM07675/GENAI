"""
Voice WebSocket Manager.

Handles the full WebSocket message protocol for a voice session.
Decouples the WebSocket transport layer from the pipeline logic.

Client → Server messages
------------------------
session_start   : {"type": "session_start", "user_id": null}
audio_chunk     : binary frame (raw 16kHz PCM) or
                  {"type": "audio_chunk", "data": "<base64>"}
interrupt       : {"type": "interrupt"}
stop_session    : {"type": "stop_session"}
ping            : {"type": "ping"}

Server → Client messages
------------------------
session_ready    : {"type": "session_ready", "session_id": "..."}
state_change     : {"type": "state_change", "state": "LISTENING"}
partial_transcript: {"type": "partial_transcript", "text": "...", "confidence": 0.9}
final_transcript : {"type": "final_transcript", "text": "...", "confidence": 0.95}
thinking         : {"type": "thinking"}
partial_response : {"type": "partial_response", "text": "..."}
audio_chunk      : {"type": "audio_chunk", "data": "<base64>", "sequence": 1}
speaking         : {"type": "speaking"}
interrupted      : {"type": "interrupted"}
completed        : {"type": "completed", "chars": 120, "interrupted": false}
metrics          : {"type": "metrics", "data": {...}}
error            : {"type": "error", "code": "...", "message": "..."}
pong             : {"type": "pong"}
"""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from app.communication.interrupt_manager import InterruptManager
from app.communication.session_manager import SessionRegistry, VoiceSession
from app.communication.speech_to_text import TranscriptResult
from app.communication.state_machine import CommunicationState
from app.communication.voice_activity import VADEvent, VoiceActivityDetector
from app.core.logging_config import get_logger
from app.db.engine import async_session_factory

logger = get_logger(__name__)

# Keepalive interval in seconds
_PING_INTERVAL_S = 30


class VoiceWebSocketManager:
    """Manages a single voice WebSocket connection end-to-end.

    Usage (from the API route)::

        manager = VoiceWebSocketManager()
        await manager.handle(websocket)
    """

    def __init__(self) -> None:
        self._registry = SessionRegistry.get()

    # ── Entry point ───────────────────────────────────────────────

    async def handle(self, websocket: WebSocket) -> None:
        """Accept and drive a voice WebSocket connection.

        Runs until the client disconnects or an unrecoverable error occurs.
        """
        await websocket.accept()
        logger.info("Voice WebSocket accepted")

        session: VoiceSession | None = None

        try:
            async with async_session_factory() as db:
                while True:
                    try:
                        message = await asyncio.wait_for(
                            websocket.receive(), timeout=_PING_INTERVAL_S
                        )
                    except asyncio.TimeoutError:
                        # Send keepalive
                        await self._send(websocket, {"type": "ping"})
                        continue
                    except WebSocketDisconnect:
                        break

                    # Dispatch based on message type
                    if message.get("bytes"):
                        # Binary frame = raw PCM audio
                        if session:
                            await session.audio_handler.feed(message["bytes"])
                        continue

                    # JSON text message
                    raw = message.get("text", "")
                    if not raw:
                        continue

                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        await self._send(websocket, {
                            "type": "error",
                            "code": "INVALID_JSON",
                            "message": "Message must be valid JSON",
                        })
                        continue

                    msg_type = msg.get("type", "")
                    session = await self._dispatch(
                        websocket=websocket,
                        msg=msg,
                        msg_type=msg_type,
                        session=session,
                        db=db,
                    )

                    if session and session.state == CommunicationState.DISCONNECTED:
                        break

        except WebSocketDisconnect:
            logger.info("Voice WebSocket disconnected")
        except Exception as exc:
            logger.error("Voice WebSocket error", error=str(exc), error_type=type(exc).__name__)
            try:
                await self._send(websocket, {
                    "type": "error",
                    "code": "SERVER_ERROR",
                    "message": "An internal server error occurred",
                })
            except Exception:
                pass
        finally:
            if session:
                await self._registry.destroy_session(session.session_id)
            logger.info("Voice WebSocket handler exiting")

    # ── Dispatcher ────────────────────────────────────────────────

    async def _dispatch(
        self,
        websocket: WebSocket,
        msg: dict,
        msg_type: str,
        session: VoiceSession | None,
        db,
    ) -> VoiceSession | None:
        """Route a JSON message to the appropriate handler."""

        if msg_type == "ping":
            await self._send(websocket, {"type": "pong"})
            return session

        if msg_type == "session_start":
            if session:
                await self._registry.destroy_session(session.session_id)
            session = await self._handle_session_start(websocket, msg, db)
            return session

        if msg_type == "audio_chunk":
            # Base64-encoded audio in JSON (fallback for environments without binary WS)
            if session:
                b64 = msg.get("data", "")
                if b64:
                    try:
                        pcm = base64.b64decode(b64)
                        await session.audio_handler.feed(pcm)
                    except Exception as exc:
                        logger.warning("Audio decode error", error=str(exc))
            return session

        if msg_type == "interrupt":
            if session:
                await self._handle_interrupt(websocket, session)
            return session

        if msg_type == "stop_session":
            if session:
                await self._registry.destroy_session(session.session_id)
                await self._send(websocket, {"type": "state_change", "state": "DISCONNECTED"})
                return None
            return session

        logger.debug("Unknown message type", msg_type=msg_type)
        return session

    # ── Session Start ─────────────────────────────────────────────

    async def _handle_session_start(
        self, websocket: WebSocket, msg: dict, db
    ) -> VoiceSession:
        """Create a new voice session and wire up all callbacks."""
        user_id = int(msg.get("user_id") or 0)

        session = await self._registry.create_session(user_id=user_id, db=db)

        # ── State change callback → send state_change events ──────
        async def on_state_change(from_state, to_state):
            await self._send(websocket, {
                "type": "state_change",
                "state": to_state.value,
            })

        session.state_machine.on_state_change(on_state_change)

        # ── Conversation callbacks → send text/audio events ───────
        async def on_text_token(token: str) -> None:
            await self._send(websocket, {
                "type": "partial_response",
                "text": token,
            })

        async def on_audio_chunk(audio_bytes: bytes, sequence: int) -> None:
            session.metrics.record_first_audio()
            self._send_audio_chunk(websocket, audio_bytes, sequence)

        async def on_event(event_name: str, data: dict) -> None:
            await self._send(websocket, {"type": event_name, **data})
            if event_name == "completed":
                # Send metrics snapshot after each turn
                await self._send(websocket, {
                    "type": "metrics",
                    "data": session.metrics.snapshot(),
                })

        session.conversation.on_text_token(on_text_token)
        session.conversation.on_audio_chunk(on_audio_chunk)
        session.conversation.on_event(on_event)

        # ── TTS audio callback ────────────────────────────────────
        async def on_tts_chunk(audio_bytes: bytes, seq: int) -> None:
            session.metrics.record_first_audio()
            await self._send(websocket, {
                "type": "audio_chunk",
                "data": base64.b64encode(audio_bytes).decode(),
                "sequence": seq,
            })

        async def on_tts_event(event_name: str) -> None:
            if event_name == "speaking_started":
                await self._send(websocket, {"type": "speaking"})
            elif event_name in ("speaking_done", "interrupted"):
                pass  # handled by state machine transitions

        session.tts.on_audio_chunk(on_tts_chunk)
        session.tts.on_event(on_tts_event)

        # ── Start VAD background loop ──────────────────────────────
        vad_task = asyncio.create_task(
            self._run_vad_loop(websocket, session),
            name=f"vad-{session.session_id}",
        )
        session.set_vad_task(vad_task)

        try:
            await session.state_machine.transition(CommunicationState.CONNECTING)
            await session.state_machine.transition(CommunicationState.LISTENING)
        except ValueError:
            pass

        await self._send(websocket, {
            "type": "session_ready",
            "session_id": session.session_id,
        })

        logger.info("Voice session ready", session_id=session.session_id)
        return session

    # ── VAD Loop ──────────────────────────────────────────────────

    async def _run_vad_loop(
        self, websocket: WebSocket, session: VoiceSession
    ) -> None:
        """Background task: runs VAD on audio frames and drives STT.

        Runs as a persistent Task for the lifetime of the session.
        """
        logger.info("VAD loop started", session_id=session.session_id)
        in_speech = False

        try:
            async for result in session.vad.process(session.audio_handler.frames()):
                current_state = session.state_machine.state

                # Only drive STT transitions when in LISTENING/USER_SPEAKING states
                if current_state in (
                    CommunicationState.SPEAKING,
                    CommunicationState.GENERATING,
                    CommunicationState.DISCONNECTED,
                ):
                    # During speaking/generating: check for barge-in
                    if result.is_speech and current_state in (CommunicationState.SPEAKING, CommunicationState.GENERATING):
                        logger.info("Barge-in detected", session_id=session.session_id)
                        await session.interrupt.trigger_interrupt()
                        await self._send(websocket, {"type": "interrupted"})
                        session.stt.clear_buffer()
                        in_speech = True
                        try:
                            await session.state_machine.transition(CommunicationState.USER_SPEAKING)
                        except ValueError:
                            pass
                    continue

                if result.event == VADEvent.SPEECH_STARTED:
                    in_speech = True
                    session.stt.clear_buffer()
                    session.metrics.start_stt()
                    try:
                        await session.state_machine.transition(CommunicationState.USER_SPEAKING)
                    except ValueError:
                        pass
                    await self._send(websocket, {
                        "type": "listening",
                        "active": True,
                    })

                elif result.is_speech and in_speech:
                    # Accumulate audio into STT buffer
                    # (the raw frame is not available here, so we rely
                    #  on the STT engine receiving it via audio_handler feed)
                    pass

                elif result.event == VADEvent.SPEECH_ENDED and in_speech:
                    in_speech = False

                    try:
                        await session.state_machine.transition(
                            CommunicationState.TRANSCRIBING
                        )
                    except ValueError:
                        continue

                    await self._send(websocket, {
                        "type": "listening",
                        "active": False,
                    })

                    # Transcribe buffered audio
                    async def on_partial(text: str, confidence: float) -> None:
                        await self._send(websocket, {
                            "type": "partial_transcript",
                            "text": text,
                            "confidence": round(confidence, 3),
                        })

                    transcript = await session.stt.transcribe_buffer(
                        on_partial=on_partial
                    )
                    session.metrics.end_stt()

                    if not transcript.text.strip():
                        # Nothing intelligible — go back to listening
                        try:
                            await session.state_machine.transition(
                                CommunicationState.LISTENING
                            )
                        except ValueError:
                            pass
                        continue

                    # Hand off to conversation manager for AI pipeline
                    asyncio.create_task(
                        session.conversation.process_transcript(transcript),
                        name=f"turn-{session.session_id}",
                    )

        except asyncio.CancelledError:
            logger.info("VAD loop cancelled", session_id=session.session_id)
        except Exception as exc:
            logger.error("VAD loop error", session_id=session.session_id, error=str(exc))

    # ── Interrupt ─────────────────────────────────────────────────

    async def _handle_interrupt(self, websocket: WebSocket, session: VoiceSession) -> None:
        """Handle a client-initiated interrupt message."""
        triggered = await session.interrupt.trigger_interrupt()
        if triggered:
            await self._send(websocket, {"type": "interrupted"})
            session.stt.clear_buffer()
            session.vad.reset()

    # ── Transport helpers ─────────────────────────────────────────

    @staticmethod
    async def _send(websocket: WebSocket, data: dict[str, Any]) -> None:
        """Send a JSON message, silently ignoring closed-connection errors."""
        try:
            await websocket.send_text(json.dumps(data))
        except Exception:
            pass

    @staticmethod
    def _send_audio_chunk(
        websocket: WebSocket, audio_bytes: bytes, sequence: int
    ) -> None:
        """Schedule an audio chunk send as a fire-and-forget task."""
        asyncio.create_task(
            VoiceWebSocketManager._send(
                websocket,
                {
                    "type": "audio_chunk",
                    "data": base64.b64encode(audio_bytes).decode(),
                    "sequence": sequence,
                },
            )
        )
