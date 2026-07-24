"""Pipeline supervisor — the main coordinator for Genie's voice pipeline.

This is the central brain that:
1. Creates and owns all workers as async tasks.
2. Wires inter-worker communication via bounded async queues.
3. Drives the state machine through conversation cycles.
4. Handles speech processing as a SEPARATE task (not inline in the event loop).
5. Implements follow-up timeout as an async timer (not a blocking sleep).
6. Handles barge-in detection at every stage.
7. Integrates the watchdog for worker health monitoring.
8. Handles text input, manual wake, and frontend events.

Worker topology:
    MicrophoneService (thread)
        ↓ frames_queue (bounded 200)
    VADWorker (async task)
        → speech events → pipeline coordinator
    WakeDetector (async task)
        → wake events → pipeline coordinator
    StreamingSTT → BrainWorker (LLM) → TTSStreamWorker → PlaybackTracker
        (chained per-turn, not persistent tasks)
"""
from __future__ import annotations

import asyncio
import base64
import time
from typing import Awaitable, Callable, Optional

import structlog

from ..auth import Session
from ..config import Settings, get_settings
from .audio.echo_cancellation import EchoCanceller
from .audio.microphone import MicrophoneService
from .audio.vad import VADWorker
from .audio.vad_gate import BargeInConfig, VADGate, queue_to_async_iter
from .brain.context import UnifiedContext, context_store
from .brain.llm_stream import LLMStream
from .cancellation import CancellationScope, CancellationToken
from .event_bus import Event, PipelineEvent, engine_events
from .metrics import pipeline_metrics
from .speech.playback import PlaybackTracker
from .speech.tts_streamer import TTSStreamWorker
from .state_machine import ConversationStateMachine, EngineState
from .stt.streaming_stt import StreamingSTT
from .wake.wake_detector import WakeDetector
from .watchdog import PipelineWatchdog

log = structlog.get_logger("genie.engine.pipeline")

Emitter = Callable[[dict], Awaitable[None]]


async def _noop_emit(msg: dict) -> None:
    """Placeholder emitter until a WebSocket connects."""
    pass


class VoicePipeline:
    """Production voice pipeline supervisor.

    Created ONCE at startup. Never destroyed. Never recreated.

    Lifecycle:
        await pipeline.start()       # boot all workers
        pipeline.set_session(...)    # bind a WebSocket
        ...                          # runs forever
        await pipeline.stop()        # graceful shutdown
    """

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()

        # State machine — single instance, never recreated
        self._sm = ConversationStateMachine()

        # Session / emit
        self._session: Optional[Session] = None
        self._emit: Emitter = _noop_emit

        # Workers
        self._mic = MicrophoneService(
            sample_rate=16000,
            chunk_size=512,
            ring_buffer_seconds=30.0,
        )
        self._echo = EchoCanceller(sample_rate=16000)
        self._vad = VADWorker(
            sample_rate=16000,
            chunk_size=512,
            vad_threshold=self._settings.vad_threshold,
            silence_timeout=self._settings.vad_min_silence_duration_ms / 1000.0,
            echo_canceller=self._echo,
        )
        self._wake = WakeDetector(
            keywords=self._settings.wake_word_keywords,
            cooldown_s=self._settings.wake_word_cooldown_ms / 1000.0,
        )
        self._stt = StreamingSTT(settings=self._settings)
        self._llm = LLMStream(settings=self._settings)

        # Watchdog
        self._watchdog = PipelineWatchdog(
            state_machine=self._sm,
            on_worker_stuck=self._on_worker_stuck,
        )

        # v12: VAD Gate for continuous barge-in detection
        self._vad_gate = VADGate(
            config=BargeInConfig(
                threshold=0.5,
                min_speech_ms=200,
                cooldown_ms=400,
            )
        )
        self._vad_gate_task: Optional[asyncio.Task] = None

        # Per-turn state
        self._cancel_scope: Optional[CancellationScope] = None
        self._playback: Optional[PlaybackTracker] = None
        self._current_turn_task: Optional[asyncio.Task] = None
        self._follow_up_timer: Optional[asyncio.Task] = None

        # v12 latency tracking (per-turn, reset each turn)
        self._turn_vad_first_voiced_ms: float = 0.0
        self._turn_llm_first_token_ms: float = 0.0
        self._turn_tts_first_audio_ms: float = 0.0
        self._turn_start_ms: float = 0.0

        # Lifecycle
        self._started = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ══════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════════════════════

    async def start(self) -> None:
        """Boot all workers and start the pipeline."""
        if self._started:
            return

        self._loop = asyncio.get_running_loop()
        engine_events.set_loop(self._loop)

        # Register event subscriptions
        engine_events.subscribe(PipelineEvent.WAKE_DETECTED, self._on_wake_detected)
        engine_events.subscribe(PipelineEvent.SPEECH_START, self._on_speech_start)
        engine_events.subscribe(PipelineEvent.SPEECH_END, self._on_speech_end)
        engine_events.subscribe(PipelineEvent.SILENCE_TIMEOUT, self._on_silence_timeout)
        engine_events.subscribe(PipelineEvent.MAX_DURATION, self._on_max_duration)

        # Register state machine callbacks
        self._sm.on_transition(self._on_state_changed)

        # Start microphone (opens PyAudio ONCE)
        mic_ok = self._mic.start(self._loop)
        if not mic_ok:
            log.error("pipeline_mic_failed")
            # Continue anyway — text input still works

        # Create SEPARATE subscriber queues — each worker gets every frame
        # (fixes: wake & VAD were sharing one queue, stealing frames from each other)
        vad_queue = self._mic.create_subscriber_queue(maxsize=200)
        await self._vad.start(vad_queue)

        # Start wake detector with its OWN queue
        if self._settings.wake_word_enabled:
            wake_queue = self._mic.create_subscriber_queue(maxsize=200)
            await self._wake.start(wake_queue)

        # v12: Start VAD Gate on its own subscriber queue (continuous barge-in watcher)
        if getattr(self._settings, "enable_barge_in", True):
            barge_queue = self._mic.create_subscriber_queue(maxsize=200)
            await self._vad_gate.preload()
            self._vad_gate_task = asyncio.create_task(
                self._vad_gate.watch(
                    frames=queue_to_async_iter(barge_queue),
                    on_speech_start=self._on_vad_gate_speech_start,
                    active=self._is_barge_in_eligible,
                ),
                name="vad_gate",
            )
            log.info("vad_gate_started")

        # Preload STT model in background
        asyncio.create_task(self._stt.preload_model())

        # Register workers with watchdog
        self._watchdog.register_worker("vad", lambda: self._vad.heartbeat)
        if self._settings.wake_word_enabled:
            self._watchdog.register_worker("wake", lambda: self._wake.heartbeat)

        # Start watchdog
        await self._watchdog.start()

        # Transition to WAIT_WAKE
        await self._sm.transition(EngineState.IDLE, "boot")
        await self._sm.transition(EngineState.WAIT_WAKE, "ready")

        self._started = True
        log.info("pipeline_started")

    async def stop(self) -> None:
        """Graceful shutdown."""
        if not self._started:
            return

        self._started = False

        # Cancel any in-flight turn
        await self._cancel_current_turn("shutdown")
        self._cancel_follow_up_timer()

        # Stop VAD Gate task
        if self._vad_gate_task and not self._vad_gate_task.done():
            self._vad_gate_task.cancel()
            try:
                await self._vad_gate_task
            except (asyncio.CancelledError, Exception):
                pass
            self._vad_gate_task = None

        # Stop workers in reverse order
        await self._watchdog.stop()
        await self._wake.stop()
        await self._vad.stop()
        self._mic.stop()

        await self._sm.force_transition(EngineState.IDLE, "shutdown")
        log.info("pipeline_stopped", metrics=pipeline_metrics.snapshot())

    # ══════════════════════════════════════════════════════════════════════
    # SESSION BINDING
    # ══════════════════════════════════════════════════════════════════════

    def set_session(self, session: Session, emit: Emitter) -> None:
        """Bind an authenticated WebSocket session."""
        self._session = session
        self._emit = emit
        log.info("pipeline_session_bound", session_id=session.session_id)

    # ══════════════════════════════════════════════════════════════════════
    # EXTERNAL EVENT HANDLERS (from main.py)
    # ══════════════════════════════════════════════════════════════════════

    async def on_text_input(self, text: str) -> None:
        """Handle typed text input from the WebSocket."""
        if not self._session:
            return

        # Cancel any current turn
        await self._cancel_current_turn("text_input_override")
        self._cancel_follow_up_timer()

        # Start a new turn as a separate task (non-blocking!)
        self._current_turn_task = asyncio.create_task(
            self._process_turn(text, source="text")
        )

    async def on_manual_wake(self) -> None:
        """Handle manual wake (mic button press)."""
        current = self._sm.state
        if current == EngineState.WAIT_WAKE:
            await self._begin_listening("manual_wake")
        elif self._sm.allows_bargein():
            await self._handle_bargein("manual_wake")

    async def on_cancel(self) -> None:
        """Handle cancel from the WebSocket."""
        await self._cancel_current_turn("user_cancel")
        self._cancel_follow_up_timer()
        await self._sm.force_transition(EngineState.WAIT_WAKE, "user_cancel")
        await self._emit({"type": "orb_state", "state": "idle"})

    async def on_playback_complete(self) -> None:
        """Handle playback_complete from the frontend."""
        if self._playback:
            self._playback.mark_playback_complete()
        # Disable echo suppression NOW — audio has finished playing on the frontend.
        # This is the correct time, NOT when tts_done is sent (which is before
        # the frontend even starts playing the audio).
        self._echo.disable()
        log.debug("echo_suppression_disabled_on_playback_complete")

    # ══════════════════════════════════════════════════════════════════════
    # EVENT BUS HANDLERS (from workers)
    # ══════════════════════════════════════════════════════════════════════

    async def _on_wake_detected(self, event: Event) -> None:
        """Wake word detected — transition to LISTENING or barge in."""
        if self._sm.state == EngineState.WAIT_WAKE:
            await self._begin_listening("wake_word")
        elif self._sm.allows_bargein():
            await self._handle_bargein("wake_word")

    async def _on_speech_start(self, event: Event) -> None:
        """VAD detected speech start."""
        if self._sm.state == EngineState.LISTENING:
            self._mic.start_speech_recording()
            await self._emit({"type": "orb_state", "state": "user_speaking"})

        elif self._sm.state in (EngineState.SPEAKING, EngineState.STREAMING_RESPONSE):
            # Barge-in during TTS playback (VAD threshold is already raised, so this is genuine)
            await self._handle_bargein("speech_during_tts")

    # ── v12: VAD Gate handlers ────────────────────────────────────────────

    def _is_barge_in_eligible(self) -> bool:
        """Return True when barge-in should be armed.

        The VAD gate is active during any state where Genie is generating
        or playing back a response — but NOT during idle / wake_listening,
        since the normal STT / wake path handles those.
        """
        return self._sm.state in (
            EngineState.THINKING,
            EngineState.STREAMING_RESPONSE,
            EngineState.SPEAKING,
            EngineState.UNDERSTANDING,
        )

    async def _on_vad_gate_speech_start(self) -> None:
        """Called by the VAD Gate when real speech is detected mid-response.

        This is the automatic barge-in path — equivalent to the user
        clicking the cancel button, but triggered by voice.
        """
        if not self._is_barge_in_eligible():
            return

        if not getattr(self._settings, "enable_barge_in", True):
            log.debug("vad_gate_barge_in_disabled")
            return

        # v12 latency telemetry
        now_ms = time.monotonic() * 1000
        log.info(
            "vad_gate_barge_in_firing",
            state=self._sm.state.value,
            voiced_ms=200,  # gate already requires 200ms of continuous speech
        )

        await self._handle_bargein("vad_gate")

    async def _on_speech_end(self, event: Event) -> None:
        """VAD detected end of speech — trigger STT + LLM pipeline."""
        if self._sm.state != EngineState.LISTENING:
            return

        self._mic.stop_speech_recording()

        # Get the captured audio
        audio = self._mic.get_speech_audio()
        if not audio or len(audio) < 1024:
            log.info("speech_too_short", bytes=len(audio) if audio else 0)
            # Stay in LISTENING, wait for more speech
            return

        # Start a new turn as a separate task (non-blocking!)
        self._cancel_follow_up_timer()
        self._current_turn_task = asyncio.create_task(
            self._process_turn_from_audio(audio)
        )

    async def _on_silence_timeout(self, event: Event) -> None:
        """No speech detected within timeout — return to wake."""
        if self._sm.state == EngineState.LISTENING:
            await self._sm.transition(EngineState.WAIT_WAKE, "silence_timeout")
            self._vad.stop_listening_session()
            self._mic.reset_speech_buffer()
            await self._emit({"type": "orb_state", "state": "idle"})

    async def _on_max_duration(self, event: Event) -> None:
        """Speech exceeded max duration — process what we have."""
        if self._sm.state == EngineState.LISTENING:
            self._mic.stop_speech_recording()
            audio = self._mic.get_speech_audio()
            if audio and len(audio) > 1024:
                self._current_turn_task = asyncio.create_task(
                    self._process_turn_from_audio(audio)
                )

    async def _on_state_changed(
        self, old: EngineState, new: EngineState, reason: str
    ) -> None:
        """Notify the frontend of every state change."""
        await self._emit({
            "type": "engine_state",
            "state": new.value,
            "previous": old.value,
            "reason": reason,
        })

        # Update wake/VAD activation based on new state
        is_wake_active = self._sm.is_wake_active()
        if is_wake_active and old != EngineState.WAIT_WAKE:
            self._wake.reset()
        self._wake.set_enabled(is_wake_active)

    # ══════════════════════════════════════════════════════════════════════
    # CORE PIPELINE — runs as a SEPARATE task, not inline
    # ══════════════════════════════════════════════════════════════════════

    async def _begin_listening(self, reason: str) -> None:
        """Transition to LISTENING state."""
        self._cancel_follow_up_timer()

        ok = await self._sm.transition(EngineState.LISTENING, reason)
        if not ok:
            return

        self._vad.start_listening_session()
        self._mic.reset_speech_buffer()
        await self._emit({"type": "orb_state", "state": "listening"})

    async def _process_turn_from_audio(self, audio_bytes: bytes) -> None:
        """Full pipeline: Audio → STT → LLM → TTS → Playback."""
        # ── STT Phase ─────────────────────────────────────────────────────
        ok = await self._sm.transition(EngineState.UNDERSTANDING, "speech_captured")
        if not ok:
            return

        self._vad.stop_listening_session()
        await self._emit({"type": "orb_state", "state": "processing"})

        cancel_scope = CancellationScope(interaction_id=f"turn_{int(time.time())}")
        self._cancel_scope = cancel_scope
        cancel_token = cancel_scope.create_token()

        timer = pipeline_metrics.time("turn.total")

        transcript = await self._stt.transcribe(audio_bytes, cancel_token=cancel_token)

        if cancel_token.is_cancelled:
            timer.finish()
            return

        if not transcript.strip():
            log.info("stt_empty_transcript")
            await self._emit({"type": "error", "message": "I didn't catch that. Could you try again?"})
            # Go back to listening or wake
            if self._settings.follow_up_mode:
                await self._begin_listening("empty_transcript_retry")
            else:
                await self._sm.transition(EngineState.WAIT_WAKE, "empty_transcript")
                await self._emit({"type": "orb_state", "state": "idle"})
            timer.finish()
            return

        # Show transcript to user
        await self._emit({"type": "user_text", "text": transcript})

        # Continue to LLM
        await self._process_turn(transcript, source="voice", cancel_scope=cancel_scope, timer=timer)

    async def _process_turn(
        self,
        text: str,
        source: str = "text",
        cancel_scope: Optional[CancellationScope] = None,
        timer=None,
    ) -> None:
        """Process a user turn through the LLM → TTS → Playback pipeline.

        This runs as a SEPARATE asyncio task — it NEVER blocks the main
        event loop. Other events (barge-in, wake, etc.) continue to be
        processed while this runs.
        """
        if not self._session:
            log.warning("process_turn_no_session")
            await self._sm.transition(EngineState.WAIT_WAKE, "no_session")
            return

        if cancel_scope is None:
            cancel_scope = CancellationScope(interaction_id=f"turn_{int(time.time())}")
            self._cancel_scope = cancel_scope

        cancel_token = cancel_scope.create_token()

        if timer is None:
            timer = pipeline_metrics.time("turn.total", source=source)

        # ── Thinking Phase ────────────────────────────────────────────────
        ok = await self._sm.transition(EngineState.THINKING, "llm_start")
        if not ok:
            timer.finish()
            return

        await self._emit({"type": "orb_state", "state": "thinking"})

        # Create TTS queue and playback tracker
        tts_text_queue: asyncio.Queue[Optional[str]] = asyncio.Queue(maxsize=50)
        self._playback = PlaybackTracker(playback_timeout=60.0)
        tts_worker = TTSStreamWorker(sample_rate=self._settings.tts_sample_rate)

        # Get unified context
        context = context_store.get(self._session.session_id)
        context.add_user_turn(text)

        # Per-turn flag: have we transitioned to STREAMING_RESPONSE yet?
        # Set on the first text delta so the state machine reflects that
        # the LLM is actively generating text (not waiting for it to finish).
        _streaming_started = False

        # ── Start TTS worker as concurrent task ───────────────────────────
        tts_cancel = cancel_scope.create_token()

        # v12 latency tracking
        self._turn_start_ms = time.monotonic() * 1000
        self._turn_llm_first_token_ms = 0.0
        self._turn_tts_first_audio_ms = 0.0
        _tts_first_audio_logged = False

        async def _on_tts_audio(audio_bytes: bytes, mime_type: str, word_timings: Optional[list[dict]] = None) -> None:
            """Called by TTS worker when a chunk is synthesized."""
            nonlocal _tts_first_audio_logged
            if cancel_token.is_cancelled:
                return

            # v12: record time-to-first-audio-byte
            if not _tts_first_audio_logged:
                _tts_first_audio_logged = True
                self._turn_tts_first_audio_ms = time.monotonic() * 1000
                log.info(
                    "latency_tts_first_audio",
                    elapsed_ms=round(self._turn_tts_first_audio_ms - self._turn_start_ms),
                )

            # Transition to SPEAKING on first audio chunk
            current = self._sm.state
            if current == EngineState.STREAMING_RESPONSE:
                await self._sm.transition(EngineState.SPEAKING, "first_audio")
                await self._emit({"type": "orb_state", "state": "speaking"})
                await self._emit({"type": "tts_playing"})
                self._echo.enable()

            self._playback.record_chunk_sent(len(audio_bytes))
            await self._emit({
                "type": "assistant_audio_chunk",
                "audio": base64.b64encode(audio_bytes).decode("ascii"),
                "mime": mime_type,
                "seq": self._playback.chunks_sent,
            })
            
            if word_timings:
                await self._emit({
                    "type": "word_timing",
                    "seq": self._playback.chunks_sent,
                    "words": word_timings,
                })

        tts_task = asyncio.create_task(
            tts_worker.run(tts_text_queue, _on_tts_audio, cancel_token=tts_cancel)
        )

        # ── LLM Phase ────────────────────────────────────────────────────
        _llm_first_token_logged = False

        async def _on_text_delta(delta: str) -> None:
            """Feed text deltas to TTS worker and update state machine."""
            nonlocal _streaming_started, _llm_first_token_logged
            if cancel_token.is_cancelled:
                return

            # v12: record time-to-first-LLM-token
            if not _llm_first_token_logged:
                _llm_first_token_logged = True
                self._turn_llm_first_token_ms = time.monotonic() * 1000
                log.info(
                    "latency_llm_first_token",
                    elapsed_ms=round(self._turn_llm_first_token_ms - self._turn_start_ms),
                )

            # Transition to STREAMING_RESPONSE on the FIRST text delta —
            # this is when streaming actually begins, not after it's done.
            if not _streaming_started and self._sm.state == EngineState.THINKING:
                _streaming_started = True
                await self._sm.transition(EngineState.STREAMING_RESPONSE, "llm_response")

            try:
                await asyncio.wait_for(tts_text_queue.put(delta), timeout=5.0)
            except asyncio.TimeoutError:
                log.warning("tts_queue_full_timeout")

        try:
            result = await self._llm.process(
                user_text=text,
                session=self._session,
                context=context,
                emit=self._emit,
                cancel_token=cancel_token,
                on_text_delta=_on_text_delta,
            )

            # If LLM produced text but no delta ever fired (e.g. local intent handler
            # returned a result without streaming), ensure we've left THINKING.
            if result.get("text") and not _streaming_started:
                if self._sm.state == EngineState.THINKING:
                    await self._sm.transition(EngineState.STREAMING_RESPONSE, "llm_response_late")

        except asyncio.CancelledError:
            cancel_scope.cancel_all("turn_cancelled")
        except Exception as exc:
            log.error("turn_processing_error", error=str(exc))
            cancel_scope.cancel_all("turn_error")
        finally:
            # Signal TTS to flush remaining text
            try:
                tts_text_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass

        # ── Wait for TTS to finish ────────────────────────────────────────
        try:
            await asyncio.wait_for(tts_task, timeout=60.0)
        except asyncio.TimeoutError:
            log.warning("tts_task_timeout")
            tts_task.cancel()
        except asyncio.CancelledError:
            pass

        # Send audio end
        if self._playback and self._playback.has_audio:
            await self._emit({"type": "assistant_audio_end"})
            await self._emit({"type": "tts_done"})
            # NOTE: do NOT call self._echo.disable() here!
            # Echo suppression must remain active until the frontend confirms
            # playback is done (on_playback_complete). Otherwise the mic picks
            # up Genie's own voice during follow-up listening.
        else:
            # No audio produced (text-only or error) — ensure tts_done is
            # always sent so the frontend never stays stuck.
            await self._emit({"type": "tts_done"})
            self._echo.disable()  # Safe to disable — no audio was sent

        # ── Record context ────────────────────────────────────────────────
        if not cancel_token.is_cancelled and result.get("text"):
            context.add_assistant_turn(
                text=result["text"],
                tool_calls=result.get("tool_calls", []),
                interrupted=result.get("interrupted", False),
            )

        # ── Wait for playback (SHORT timeout — never block the pipeline) ──
        # Gemini Live-like: we wait briefly for playback to finish, but
        # if it doesn't arrive quickly we proceed anyway. The pipeline
        # must never get stuck waiting for frontend confirmation.
        if self._playback and self._playback.has_audio:
            playback_ok = False
            try:
                playback_ok = await asyncio.wait_for(
                    self._playback.wait_for_playback(),
                    timeout=60.0,
                )
            except asyncio.TimeoutError:
                log.warning("playback_wait_timeout_proceeding",
                            chunks=self._playback.chunks_sent)
                # Force-disable echo so follow-up listening isn't permanently blocked
                self._echo.disable()
            except asyncio.CancelledError:
                self._echo.disable()
            if not playback_ok and not self._echo.is_active:
                # playback_complete fired but echo already disabled — fine
                pass
            elif not playback_ok:
                # Timeout path — echo already disabled above
                log.info("playback_did_not_confirm_in_time")

        # ── Finish turn ──────────────────────────────────────────────────
        timer.finish()
        pipeline_metrics.record_turn()
        self._cancel_scope = None

        # ── Transition to follow-up or wake ───────────────────────────────
        if cancel_token.is_cancelled:
            return  # interrupted turns don't trigger follow-up

        if self._sm.state in (EngineState.SPEAKING, EngineState.STREAMING_RESPONSE,
                               EngineState.THINKING):
            await self._sm.force_transition(EngineState.RETURN_TO_LISTENING, "turn_complete")
        elif self._sm.can_transition_to(EngineState.RETURN_TO_LISTENING):
            await self._sm.transition(EngineState.RETURN_TO_LISTENING, "turn_complete")

        if self._settings.follow_up_mode:
            # Start follow-up timer (NON-BLOCKING!)
            self._start_follow_up_timer()
            await self._begin_listening("follow_up")
        else:
            await self._sm.transition(EngineState.WAIT_WAKE, "no_follow_up")
            await self._emit({"type": "orb_state", "state": "idle"})

    # ══════════════════════════════════════════════════════════════════════
    # FOLLOW-UP TIMER
    # ══════════════════════════════════════════════════════════════════════

    def _start_follow_up_timer(self) -> None:
        """Start a non-blocking follow-up timeout.

        If the user doesn't speak within the timeout, return to WAIT_WAKE.
        This is implemented as a separate async task — NOT a blocking sleep
        (fixing audit bug #1).
        """
        self._cancel_follow_up_timer()
        self._follow_up_timer = asyncio.create_task(
            self._follow_up_timeout_task()
        )

    def _cancel_follow_up_timer(self) -> None:
        """Cancel the follow-up timer if running."""
        if self._follow_up_timer and not self._follow_up_timer.done():
            self._follow_up_timer.cancel()
        self._follow_up_timer = None

    async def _follow_up_timeout_task(self) -> None:
        """Follow-up timeout — return to WAIT_WAKE after N seconds of silence."""
        try:
            await asyncio.sleep(self._settings.follow_up_timeout_seconds)
            # Timer expired — user didn't speak
            if self._sm.state == EngineState.LISTENING:
                log.info("follow_up_timeout")
                self._vad.stop_listening_session()
                self._mic.reset_speech_buffer()
                await self._sm.transition(EngineState.WAIT_WAKE, "follow_up_timeout")
                await self._emit({"type": "orb_state", "state": "idle"})
        except asyncio.CancelledError:
            pass  # timer was cancelled because user spoke

    # ══════════════════════════════════════════════════════════════════════
    # BARGE-IN
    # ══════════════════════════════════════════════════════════════════════

    async def _handle_bargein(self, reason: str) -> None:
        """Handle user interruption during response/playback."""
        log.info("barge_in", reason=reason, state=self._sm.state.value)

        # Cancel current turn
        if self._cancel_scope:
            self._cancel_scope.cancel_all("barge_in")

        # Interrupt playback
        if self._playback:
            self._playback.interrupt()

        # Tell frontend to stop audio
        await self._emit({"type": "stop_audio"})
        await self._emit({"type": "tts_done"})
        self._echo.disable()

        # Transition to LISTENING
        await self._sm.force_transition(EngineState.LISTENING, f"barge_in:{reason}")
        self._vad.start_listening_session()
        self._mic.reset_speech_buffer()
        await self._emit({"type": "orb_state", "state": "listening"})

        pipeline_metrics.increment("pipeline.barge_ins")

    # ══════════════════════════════════════════════════════════════════════
    # CANCELLATION
    # ══════════════════════════════════════════════════════════════════════

    async def _cancel_current_turn(self, reason: str) -> None:
        """Cancel any in-flight processing."""
        if self._cancel_scope:
            self._cancel_scope.cancel_all(reason)
            self._cancel_scope = None

        if self._playback:
            self._playback.interrupt()

        await self._emit({"type": "interrupt"})

        if self._current_turn_task and not self._current_turn_task.done():
            self._current_turn_task.cancel()
            try:
                await asyncio.wait_for(
                    asyncio.shield(self._current_turn_task), timeout=3.0
                )
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                pass
            self._current_turn_task = None

        self._echo.disable()
        self._mic.reset_speech_buffer()

    # ══════════════════════════════════════════════════════════════════════
    # WATCHDOG RECOVERY
    # ══════════════════════════════════════════════════════════════════════

    async def _on_worker_stuck(self, worker_name: str) -> None:
        """Called by the watchdog when a worker appears stuck."""
        log.error("pipeline_worker_stuck_recovery", worker=worker_name)

        if worker_name == "vad":
            # Restart VAD worker with a new subscriber queue
            await self._vad.stop()
            new_vad_queue = self._mic.create_subscriber_queue(maxsize=200)
            await self._vad.start(new_vad_queue)

        elif worker_name == "wake":
            # Restart wake detector with a new subscriber queue
            await self._wake.stop()
            new_wake_queue = self._mic.create_subscriber_queue(maxsize=200)
            await self._wake.start(new_wake_queue)

    # ══════════════════════════════════════════════════════════════════════
    # DIAGNOSTICS
    # ══════════════════════════════════════════════════════════════════════

    def snapshot(self) -> dict:
        """Full pipeline diagnostic snapshot."""
        return {
            "state": self._sm.snapshot(),
            "microphone": self._mic.stats,
            "metrics": pipeline_metrics.snapshot(),
        }
