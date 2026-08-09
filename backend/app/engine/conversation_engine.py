"""Conversation Engine — the brain of Genie v2.

A persistent async loop that orchestrates the entire voice conversation
lifecycle. The engine never stops until shutdown:

    IDLE → WAKE_LISTENING → ACTIVE_LISTENING → PROCESSING → SPEAKING
                                                             ↓
                                              FOLLOW_UP_LISTENING → loop

Features:
- Persistent microphone (never closes)
- Cooperative cancellation (barge-in from any state)
- Streaming STT → LLM → TTS pipeline
- Context preservation across turns (including interrupted ones)
- Auto-recovery from errors

Thread model:
- Audio capture runs on a daemon thread (via AudioPipeline)
- Everything else is async on the main event loop
- Communication via asyncio.Queue
"""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Optional

import structlog

from ..auth import Session
from ..config import Settings, get_settings
from ..core.event_bus import event_bus
from ..core.event_bus.bus import VoicePipelineEvents
from .audio_pipeline import AudioEvent, AudioPipeline
from .cancellation import CancellationScope, CancellationToken
from .context_manager import ContextManager, context_store
from .intent_analyzer import IntentAnalyzer, IntentType
from .llm_router import LLMRouter
from .playback_controller import PlaybackController
from .state_machine import ConversationStateMachine, EngineState
from .stt_worker import STTWorker
from .tts_streamer import TTSStreamer
from .wake_engine import WakeEngine

log = structlog.get_logger("genie.engine")

Emitter = Callable[[dict], Awaitable[None]]

# Follow-up listening window
FOLLOW_UP_TIMEOUT_S = 12.0
# Watchdog: max time in an active state before force-recovery
WATCHDOG_TIMEOUT_S = 90.0


class ConversationEngine:
    """The main conversation loop — persistent, interruptible, context-aware.

    Call ``start()`` to begin the loop. It runs forever until ``stop()``.
    The WebSocket handler calls methods like ``on_manual_wake()``,
    ``on_playback_complete()``, ``on_cancel()`` to drive transitions.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()
        self._state = ConversationStateMachine()
        self._audio = AudioPipeline(
            sample_rate=16000,
            chunk_size=4000,  # Vosk expects 4000 frames
            silence_timeout=0.9,
            speech_start_timeout=5.0,
            minimum_speech_duration=0.3,
        )
        self._wake: Optional[WakeEngine] = None
        self._stt = STTWorker(self._settings)
        self._llm_router = LLMRouter(self._settings)
        self._intent = IntentAnalyzer()

        # Event queue: audio thread → async loop
        self._event_queue: asyncio.Queue = asyncio.Queue()

        # Active session and emitter (set by WebSocket handler)
        self._session: Optional[Session] = None
        self._emit: Optional[Emitter] = None

        # Current interaction's cancellation scope
        self._cancel_scope: Optional[CancellationScope] = None
        self._playback: Optional[PlaybackController] = None

        # Loop control
        self._running = False
        self._main_task: Optional[asyncio.Task] = None
        self._watchdog_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Register state transition callback
        self._state.on_transition(self._on_state_changed)

    # ══════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════════════════════

    async def start(self) -> None:
        """Start the conversation engine. Call once after WebSocket auth."""
        if self._running:
            return

        self._running = True
        self._loop = asyncio.get_running_loop()

        # Store loop reference for event bus
        event_bus.set_loop(self._loop)

        # Start audio pipeline
        success = self._audio.start(self._event_queue, self._loop)
        if not success:
            log.error("audio_pipeline_failed_to_start")
            # Continue without voice — text-only mode

        # Start wake word engine
        self._wake = WakeEngine(
            on_wake=self._on_wake_word_detected,
            keywords=self._settings.wake_word_keywords,
        )
        self._wake.start()
        self._audio.set_frame_callback(self._wake.process_frame)

        # Preload STT model in background
        asyncio.get_event_loop().run_in_executor(None, self._stt.preload_model)

        # Start main loop
        self._main_task = asyncio.create_task(self._main_loop())
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())

        # Transition to wake listening
        await self._state.transition(EngineState.WAKE_LISTENING, "engine_started")
        log.info("conversation_engine_started")

    async def stop(self) -> None:
        """Stop the conversation engine gracefully."""
        self._running = False

        # Cancel active interaction
        if self._cancel_scope:
            self._cancel_scope.cancel_all("engine_stopping")

        # Stop audio
        if self._wake:
            self._wake.stop()
        self._audio.stop()

        # Cancel tasks
        if self._watchdog_task:
            self._watchdog_task.cancel()
        if self._main_task:
            self._main_task.cancel()
            try:
                await self._main_task
            except (asyncio.CancelledError, Exception):
                pass

        await self._state.force_transition(EngineState.IDLE, "engine_stopped")
        log.info("conversation_engine_stopped")

    def set_session(self, session: Session, emit: Emitter) -> None:
        """Bind a WebSocket session and emitter."""
        self._session = session
        self._emit = emit

    # ══════════════════════════════════════════════════════════════════════
    # MAIN LOOP
    # ══════════════════════════════════════════════════════════════════════

    async def _main_loop(self) -> None:
        """The persistent event loop. Never exits until stop()."""
        log.info("main_loop_started")

        while self._running:
            try:
                # Wait for events from the audio pipeline
                try:
                    event = await asyncio.wait_for(
                        self._event_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                audio_event = event.get("event")
                state = self._state.state

                if audio_event == AudioEvent.SPEECH_START:
                    await self._handle_speech_start(state)

                elif audio_event == AudioEvent.SPEECH_END:
                    await self._handle_speech_end(state)

                elif audio_event == AudioEvent.INITIAL_SILENCE_TIMEOUT:
                    await self._handle_silence_timeout(state)

                elif audio_event == AudioEvent.MAX_DURATION:
                    await self._handle_speech_end(state)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error("main_loop_error", error=str(exc))
                await self._recover(str(exc))

        log.info("main_loop_exited")

    async def _handle_speech_start(self, state: EngineState) -> None:
        """Handle VAD detecting speech start."""
        if state in (EngineState.ACTIVE_LISTENING, EngineState.FOLLOW_UP_LISTENING):
            await self._state.transition(EngineState.RECORDING, "speech_detected")

        elif state in (EngineState.SPEAKING, EngineState.PROCESSING):
            # Barge-in! User started speaking while we're talking/thinking
            log.info("barge_in_detected", during=state.value)
            await self._interrupt("barge_in_speech")

    async def _handle_speech_end(self, state: EngineState) -> None:
        """Handle VAD detecting end of speech."""
        if state != EngineState.RECORDING:
            return

        # Get the audio
        audio_bytes = self._audio.get_speech_audio()
        if not audio_bytes or len(audio_bytes) < 1024:
            log.info("speech_too_short")
            await self._state.transition(EngineState.ACTIVE_LISTENING, "speech_too_short")
            self._audio.start_listening_session()
            return

        # Process the speech
        await self._process_speech(audio_bytes)

    async def _handle_silence_timeout(self, state: EngineState) -> None:
        """Handle initial silence timeout (user didn't speak)."""
        if state == EngineState.ACTIVE_LISTENING:
            log.info("no_speech_detected")
            await self._state.transition(EngineState.WAKE_LISTENING, "silence_timeout")

        elif state == EngineState.FOLLOW_UP_LISTENING:
            log.info("follow_up_timeout")
            await self._state.transition(EngineState.WAKE_LISTENING, "follow_up_timeout")

    # ══════════════════════════════════════════════════════════════════════
    # SPEECH PROCESSING PIPELINE
    # ══════════════════════════════════════════════════════════════════════

    async def _process_speech(self, audio_bytes: bytes) -> None:
        """Run the full pipeline: STT → LLM → TTS."""
        if not self._session or not self._emit:
            log.error("no_session_bound")
            await self._state.force_transition(EngineState.WAKE_LISTENING, "no_session")
            return

        # Create cancellation scope for this interaction
        self._cancel_scope = CancellationScope(interaction_id=f"turn_{int(time.time())}")
        cancel_token = self._cancel_scope.create_token()

        # ── TRANSCRIBE ────────────────────────────────────────────────────
        await self._state.transition(EngineState.TRANSCRIBING, "speech_captured")

        transcript = await self._stt.transcribe(audio_bytes, cancel_token)

        if cancel_token.is_cancelled:
            await self._state.force_transition(EngineState.ACTIVE_LISTENING, "stt_cancelled")
            self._audio.start_listening_session()
            return

        if not transcript.strip():
            log.info("empty_transcript")
            await self._state.transition(EngineState.WAKE_LISTENING, "empty_transcript")
            return

        log.info("transcript_received", text=transcript[:80])

        # Send transcript to frontend
        await self._emit({"type": "transcript", "text": transcript})

        # Get context
        context = context_store.get(self._session.session_id)

        # ── PROCESS (LLM) ────────────────────────────────────────────────
        await self._state.transition(EngineState.PROCESSING, "transcription_complete")

        # Enable echo suppression during processing (in case TTS starts)
        self._audio.set_echo_suppression(True)

        # Create playback controller for this turn
        self._playback = PlaybackController(self._emit)

        result = await self._llm_router.process(
            user_text=transcript,
            session=self._session,
            context=context,
            emit=self._emit,
            cancel_token=cancel_token,
        )

        # Record the turn in context
        context.add_user_turn(transcript, interrupted=result.get("interrupted", False))
        if result.get("text"):
            context.add_assistant_turn(
                result["text"],
                tool_calls=result.get("tool_calls"),
                interrupted=result.get("interrupted", False),
            )

        if cancel_token.is_cancelled:
            self._audio.set_echo_suppression(False)
            await self._state.force_transition(EngineState.ACTIVE_LISTENING, "processing_cancelled")
            self._audio.start_listening_session()
            return

        # ── POST-PROCESSING ───────────────────────────────────────────────

        # If audio was produced, wait for playback to complete
        if self._playback and self._playback.chunks_sent > 0:
            await self._state.transition(EngineState.SPEAKING, "tts_started")

            completed = await self._playback.wait_for_completion()

            self._audio.set_echo_suppression(False)

            if self._playback.was_interrupted:
                await self._state.force_transition(
                    EngineState.ACTIVE_LISTENING, "playback_interrupted"
                )
                self._audio.start_listening_session()
                return
        else:
            self._audio.set_echo_suppression(False)

        # ── FOLLOW-UP LISTENING ───────────────────────────────────────────
        await self._state.transition(EngineState.FOLLOW_UP_LISTENING, "turn_complete")
        self._audio.start_listening_session()

        # Wait for follow-up or timeout
        await self._follow_up_wait()

    async def _follow_up_wait(self) -> None:
        """Wait for user to speak again or timeout."""
        try:
            # The audio pipeline will post SPEECH_START if user speaks
            # The main loop will handle it. We just need to wait here
            # for the timeout.
            await asyncio.sleep(FOLLOW_UP_TIMEOUT_S)

            # If we're still in FOLLOW_UP_LISTENING, transition to WAKE_LISTENING
            if self._state.state == EngineState.FOLLOW_UP_LISTENING:
                await self._state.transition(
                    EngineState.WAKE_LISTENING, "follow_up_timeout"
                )
        except asyncio.CancelledError:
            pass

    # ══════════════════════════════════════════════════════════════════════
    # EXTERNAL EVENTS (from WebSocket handler)
    # ══════════════════════════════════════════════════════════════════════

    async def on_manual_wake(self) -> None:
        """User pressed the mic button."""
        state = self._state.state
        if state in (EngineState.WAKE_LISTENING, EngineState.IDLE):
            await self._state.force_transition(
                EngineState.ACTIVE_LISTENING, "manual_wake"
            )
            self._audio.start_listening_session()

    async def on_cancel(self) -> None:
        """User sent a cancel command."""
        await self._interrupt("user_cancel")

    async def on_playback_complete(self) -> None:
        """Frontend reports audio playback is done."""
        if self._playback:
            self._playback.on_playback_complete()

    async def on_text_input(self, text: str) -> None:
        """Handle typed text input (bypass STT)."""
        if not self._session or not self._emit:
            return

        # Cancel any active interaction
        if self._cancel_scope:
            self._cancel_scope.cancel_all("text_input")

        self._cancel_scope = CancellationScope(interaction_id="text_input")
        cancel_token = self._cancel_scope.create_token()

        await self._state.force_transition(EngineState.PROCESSING, "text_input")
        await self._emit({"type": "transcript", "text": text})

        context = context_store.get(self._session.session_id)
        self._playback = PlaybackController(self._emit)
        self._audio.set_echo_suppression(True)

        result = await self._llm_router.process(
            user_text=text,
            session=self._session,
            context=context,
            emit=self._emit,
            cancel_token=cancel_token,
        )

        context.add_user_turn(text)
        if result.get("text"):
            context.add_assistant_turn(result["text"], tool_calls=result.get("tool_calls"))

        # Wait for playback if audio was produced
        if self._playback and self._playback.chunks_sent > 0:
            await self._state.transition(EngineState.SPEAKING, "tts_started")
            await self._playback.wait_for_completion()

        self._audio.set_echo_suppression(False)
        await self._state.force_transition(EngineState.WAKE_LISTENING, "text_turn_complete")

    # ══════════════════════════════════════════════════════════════════════
    # INTERRUPTION
    # ══════════════════════════════════════════════════════════════════════

    async def _interrupt(self, reason: str) -> None:
        """Interrupt the current interaction — cancel everything."""
        log.info("interrupt", reason=reason, state=self._state.state.value)

        # Cancel all active operations
        if self._cancel_scope:
            self._cancel_scope.cancel_all(reason)

        # Stop audio playback on frontend
        if self._playback:
            res = self._playback.interrupt()
            if asyncio.iscoroutine(res):
                await res


        # Emit interrupt to frontend
        if self._emit:
            await self._emit({"type": "interrupt"})

        self._audio.set_echo_suppression(False)

        # Transition to active listening (user wants to say something)
        await self._state.force_transition(EngineState.ACTIVE_LISTENING, reason)
        self._audio.start_listening_session()

    def _on_wake_word_detected(self) -> None:
        """Called from the audio capture thread when wake word is detected.

        Must be thread-safe — posts to the event queue.
        """
        state = self._state.state

        if state == EngineState.WAKE_LISTENING:
            # Normal wake
            if self._event_queue and self._emit and self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._handle_wake(),
                    self._loop
                )
        elif state in (EngineState.SPEAKING, EngineState.PROCESSING):
            # Barge-in via wake word
            if self._event_queue and self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._interrupt("wake_word_barge_in"),
                    self._loop
                )

    async def _handle_wake(self) -> None:
        """Handle wake word detection (on the event loop)."""
        try:
            if self._emit:
                await self._emit({"type": "wake_word_detected"})
            await self._state.transition(EngineState.WAKE_DETECTED, "wake_word")
            await self._state.transition(EngineState.ACTIVE_LISTENING, "wake_acknowledged")
            self._audio.start_listening_session()
        except Exception as e:
            log.error("handle_wake_error", error=str(e), exc_info=True)

    # ══════════════════════════════════════════════════════════════════════
    # RECOVERY & WATCHDOG
    # ══════════════════════════════════════════════════════════════════════

    async def _recover(self, error_msg: str) -> None:
        """Recover from an error — reset to wake listening."""
        log.warning("recovering", error=error_msg)

        if self._cancel_scope:
            self._cancel_scope.cancel_all("error_recovery")

        self._audio.set_echo_suppression(False)
        self._audio.reset_speech()

        if self._emit:
            await self._emit({
                "type": "error",
                "message": "Something went wrong. I'm resetting.",
                "code": "engine_error",
            })
            await self._emit({"type": "tts_done"})
            await self._emit({"type": "orb_state", "state": "idle"})

        await self._state.force_transition(EngineState.WAKE_LISTENING, f"recovery:{error_msg[:50]}")

    async def _watchdog_loop(self) -> None:
        """Watchdog that recovers stuck states."""
        while self._running:
            try:
                await asyncio.sleep(10.0)

                if self._state.is_active() and self._state.time_in_state > WATCHDOG_TIMEOUT_S:
                    log.warning(
                        "watchdog_timeout",
                        state=self._state.state.value,
                        seconds=self._state.time_in_state,
                    )
                    await self._recover("watchdog_timeout")

            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error("watchdog_error", error=str(exc))

    # ══════════════════════════════════════════════════════════════════════
    # STATE CHANGE CALLBACK
    # ══════════════════════════════════════════════════════════════════════

    async def _on_state_changed(
        self, old: EngineState, new: EngineState, reason: str
    ) -> None:
        """Emit state change to frontend."""
        if self._emit:
            await self._emit({
                "type": "voice_state",
                "state": new.value,
            })

        # Publish to event bus
        await event_bus.publish(
            VoicePipelineEvents.STATE_CHANGED,
            {"old": old.value, "new": new.value, "reason": reason},
        )

    # ══════════════════════════════════════════════════════════════════════
    # DIAGNOSTICS
    # ══════════════════════════════════════════════════════════════════════

    @property
    def state(self) -> EngineState:
        return self._state.state

    @property
    def state_history(self) -> list[dict]:
        return self._state.history.recent


# ── Singleton ────────────────────────────────────────────────────────────

_engine: Optional[ConversationEngine] = None


def get_conversation_engine(settings: Optional[Settings] = None) -> ConversationEngine:
    """Get or create the global conversation engine singleton."""
    global _engine
    if _engine is None:
        _engine = ConversationEngine(settings)
    return _engine
