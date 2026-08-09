"""ObservationLoop — the main async observation cycle for Companion Mode.

Drives the ACTIVE → wait(interval) → capture → vision → context_diff
→ event → brain → (maybe speak) cycle.

Design
------
* Never continuous, never fixed-FPS: interval is mode-dependent and
  degrades automatically when VisionCallLimiter approaches its ceiling.
* Coding mode prefers structured IDE/terminal data over screenshots
  (vision is fallback, not primary channel, for coding).
* If mss cannot capture a DRM/anti-cheat surface, falls back to
  voice-only companion (observation stops, brain still runs on app-level context).
* stop() cancels cleanly with zero orphaned tasks.
* pause()/resume() freeze/unfreeze observation without stopping the task.
"""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Optional

import structlog

from ..config import Settings, get_settings
from .brain import CompanionBrain
from .capture import ScreenCaptureManager, screen_capture
from .context_engine import ContextEngine
from .events import EventManager
from .personality import PersonalityConfig, DEFAULT_PERSONALITY
from .vision import VisionService
from .manager import CompanionSubMode

log = structlog.get_logger("genie.companion.observation")

Emitter = Callable[[dict], Awaitable[None]]

# Mode-dependent base observation intervals (seconds)
_INTERVALS: dict[CompanionSubMode, float] = {
    CompanionSubMode.GAMING: 3.0,
    CompanionSubMode.CODING: 8.0,
    CompanionSubMode.WRITING: 12.0,
    CompanionSubMode.GENERAL: 10.0,
    CompanionSubMode.QUIET: 20.0,
}


class ObservationLoop:
    """Runs the observation cycle as a long-lived asyncio task.

    Lifecycle: run() → (capture → vision → diff → events → brain) × N → stop()
    """

    def __init__(
        self,
        context_engine: ContextEngine,
        emit: Emitter,
        settings: Optional[Settings] = None,
    ) -> None:
        self._context_engine = context_engine
        self._emit = emit
        self._settings = settings or get_settings()

        self._sub_mode = CompanionSubMode.GENERAL
        self._personality = DEFAULT_PERSONALITY
        self._running = False
        self._paused = False
        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # not paused initially

        self._vision = VisionService(settings=self._settings)
        self._capture = screen_capture
        self._event_manager = EventManager()
        self._brain: Optional[CompanionBrain] = None
        self._screen_aware = True  # can be set to False if capture fails repeatedly

        self._consecutive_capture_failures = 0
        self._MAX_CAPTURE_FAILURES = 3  # after this, degrade to voice-only

    def set_sub_mode(self, sub_mode: CompanionSubMode) -> None:
        self._sub_mode = sub_mode

    def set_personality(self, personality: PersonalityConfig) -> None:
        self._personality = personality
        if self._brain:
            self._brain.set_personality(personality)

    def set_emit(self, emit: Emitter) -> None:
        self._emit = emit
        if self._brain:
            self._brain.set_emit(emit)

    def pause(self) -> None:
        self._paused = True
        self._pause_event.clear()

    def resume(self) -> None:
        self._paused = False
        self._pause_event.set()

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        self._pause_event.set()  # unblock if paused

    async def run(self) -> None:
        """Main observation loop — runs until stop() is called."""
        self._running = True
        self._stop_event.clear()
        self._event_manager.reset_session_counters()

        # Lazy-init brain inside the loop so emit is already bound
        self._brain = CompanionBrain(emit=self._emit, settings=self._settings)
        self._brain.set_personality(self._personality)

        log.info("observation_loop_started", sub_mode=self._sub_mode.value)

        while self._running:
            try:
                # Wait for stop or next interval
                interval = self._compute_interval()
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=interval,
                    )
                    break  # stop() was called
                except asyncio.TimeoutError:
                    pass  # interval elapsed — proceed with observation

                # Wait if paused (blocks until resume())
                await self._pause_event.wait()
                if not self._running:
                    break

                await self._observe_once()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                # Companion failure must NOT propagate to base Genie
                log.error("observation_loop_error", error=str(exc))
                await asyncio.sleep(5.0)  # brief recovery pause

        self._running = False
        log.info("observation_loop_stopped")

    async def _observe_once(self) -> None:
        """Single observation cycle: capture → vision → diff → events → brain."""

        # Step 1: Active app identification (Win32, zero vision cost)
        app_info = self._capture.get_active_application()

        # Step 2: Auto-detect sub-mode from active app (if still GENERAL)
        # Import here to avoid circular
        from .manager import companion_manager
        if self._sub_mode == CompanionSubMode.GENERAL and app_info.category != "general":
            inferred = companion_manager.infer_sub_mode_from_app(app_info.process_name_stem)
            if inferred != self._sub_mode:
                self._sub_mode = inferred
                log.info("sub_mode_auto_detected", sub_mode=inferred.value, app=app_info.process_name_stem)

        # Step 3: Screen capture + vision (skip if degraded to voice-only)
        vision_dict: Optional[dict] = None
        if self._screen_aware and self._settings.companion_vision_enabled:
            vision_dict = await self._capture_and_analyze(app_info)

        # Step 4: Context diff (reflex layer — no LLM)
        deltas = self._context_engine.update(
            app_info=app_info,
            vision_context=vision_dict,
            mode=self._sub_mode.value,
        )

        if not deltas:
            return  # identical scene — nothing to process

        # Step 5: EventManager converts deltas to typed events
        events = self._event_manager.process_deltas(deltas)
        if not events:
            return

        # Step 6: CompanionBrain decides and (maybe) speaks
        context = self._context_engine.get_current()
        for event in events:
            if not self._running:
                break
            decision = await self._brain.process_event(event, context=context)
            if decision.line:
                self._context_engine.record_companion_response(decision.line)
                self._context_engine.record_event(event.to_dict())

    async def _capture_and_analyze(self, app_info) -> Optional[dict]:
        """Capture screen and run vision API. Returns structured dict or None."""

        # Coding mode: prefer structured data over vision when possible
        if self._sub_mode == CompanionSubMode.CODING:
            structured = await self._get_coding_structured_data()
            if structured:
                return structured
            # Fall through to vision as fallback for coding

        # Capture frame
        try:
            frame_bytes = await asyncio.to_thread(
                self._capture.capture_active_window
            )
        except Exception as exc:
            log.warning("capture_error", error=str(exc))
            frame_bytes = None

        if frame_bytes is None:
            self._consecutive_capture_failures += 1
            if self._consecutive_capture_failures >= self._MAX_CAPTURE_FAILURES:
                if self._screen_aware:
                    log.warning(
                        "capture_degraded_voice_only",
                        failures=self._consecutive_capture_failures,
                    )
                    self._screen_aware = False
                    await self._emit({
                        "type": "companion_privacy",
                        "screen_aware": False,
                        "mic_active": True,
                    })
            return None

        self._consecutive_capture_failures = 0

        # Run vision analysis
        try:
            vision_ctx = await self._vision.analyze(
                image_bytes=frame_bytes,
                mode=self._sub_mode.value,
                app_info={
                    "process_name_stem": app_info.process_name_stem,
                    "category": app_info.category,
                },
            )
            if vision_ctx.error:
                return None
            return {
                "scene": vision_ctx.scene,
                "entities": vision_ctx.entities,
                "events": vision_ctx.events,
                "changes": vision_ctx.changes,
                "confidence": vision_ctx.confidence,
            }
        except Exception as exc:
            log.warning("vision_analysis_error", error=str(exc))
            return None

    async def _get_coding_structured_data(self) -> Optional[dict]:
        """Coding mode: try to get structured IDE/terminal data instead of screenshot.

        Uses the existing engine event bus / tool system to pull structured signals.
        Returns a VisionContext-shaped dict or None (fallback to vision capture).
        """
        try:
            from ..engine.event_bus import engine_events, PipelineEvent
            # Check if there's a pending compiler error in the event bus
            # (emitted by tools/screen_context.py if available)
            coding_ctx = engine_events.get_latest(PipelineEvent.CODING_CONTEXT)
            if coding_ctx:
                return coding_ctx
        except Exception:
            pass
        return None  # signal caller to fall back to screenshot

    def _compute_interval(self) -> float:
        """Compute the current observation interval with VisionCallLimiter degradation."""
        base = _INTERVALS.get(self._sub_mode, 10.0)
        multiplier = 1.0
        if self._vision.limiter:
            multiplier = self._vision.limiter.suggested_interval_multiplier()
        return base * multiplier
