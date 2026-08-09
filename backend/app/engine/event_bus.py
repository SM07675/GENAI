"""Typed async event bus for the Genie voice pipeline.

Design:
- Bounded subscriber lists with dedup.
- Async dispatch with error isolation per subscriber.
- Thread-safe ``publish_sync`` for use from audio capture threads.
- Typed event constants prevent typos.
- High-frequency events (frames) can be filtered to reduce log noise.
"""
from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Any, Awaitable, Callable, Optional

import structlog

log = structlog.get_logger("genie.engine.event_bus")


# ═══════════════════════════════════════════════════════════════════════════════
# EVENT TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class PipelineEvent(str, Enum):
    """All events in the voice pipeline."""

    # Audio events
    AUDIO_FRAME = "audio.frame"                       # raw PCM frame
    SPEECH_START = "audio.speech_start"                # VAD detected speech
    SPEECH_END = "audio.speech_end"                    # VAD detected silence after speech
    SILENCE_TIMEOUT = "audio.silence_timeout"          # no speech within timeout
    MAX_DURATION = "audio.max_duration"                # speech exceeded max length

    # Wake events
    WAKE_DETECTED = "wake.detected"                    # wake word recognized

    # STT events
    STT_PARTIAL = "stt.partial"                        # partial transcript
    STT_FINAL = "stt.final"                            # final transcript
    STT_ERROR = "stt.error"                            # STT failure

    # LLM events
    LLM_TEXT_DELTA = "llm.text_delta"                  # streaming text token
    LLM_TOOL_CALL = "llm.tool_call"                    # tool invocation
    LLM_COMPLETE = "llm.complete"                      # generation finished
    LLM_ERROR = "llm.error"                            # LLM failure

    # TTS events
    TTS_AUDIO_CHUNK = "tts.audio_chunk"                # synthesized audio ready
    TTS_COMPLETE = "tts.complete"                      # all TTS done
    TTS_ERROR = "tts.error"                            # TTS failure

    # Playback events
    PLAYBACK_STARTED = "playback.started"              # first chunk playing
    PLAYBACK_COMPLETE = "playback.complete"             # all audio played
    PLAYBACK_INTERRUPTED = "playback.interrupted"       # user interrupted

    # State events
    STATE_CHANGED = "state.changed"                    # state machine transition

    # Pipeline control events
    BARGE_IN = "pipeline.barge_in"                     # interrupt everything
    CANCEL = "pipeline.cancel"                         # cancel current turn
    MANUAL_WAKE = "pipeline.manual_wake"               # user pressed mic button
    TEXT_INPUT = "pipeline.text_input"                  # typed text input

    # System events
    WORKER_HEARTBEAT = "system.heartbeat"              # worker alive signal
    WORKER_ERROR = "system.worker_error"               # worker crashed
    WORKER_RESTARTED = "system.worker_restarted"       # worker recovered
    METRICS = "system.metrics"                         # performance snapshot

    # Companion Mode events (orthogonal to the voice pipeline)
    COMPANION_SPEECH = "companion.speech"              # companion brain → TTS priority queue
    CODING_CONTEXT = "companion.coding_context"        # structured IDE/terminal data (coding mode)


# High-frequency events that should not be logged individually.
_QUIET_EVENTS = frozenset({
    PipelineEvent.AUDIO_FRAME,
    PipelineEvent.WORKER_HEARTBEAT,
})


# ═══════════════════════════════════════════════════════════════════════════════
# EVENT BUS
# ═══════════════════════════════════════════════════════════════════════════════

EventCallback = Callable[["Event"], Awaitable[None]]


class Event:
    """A typed pipeline event with payload."""

    __slots__ = ("type", "data", "timestamp")

    def __init__(self, event_type: PipelineEvent, data: Optional[dict[str, Any]] = None):
        self.type = event_type
        self.data = data or {}
        self.timestamp = time.time()

    def __repr__(self) -> str:
        return f"Event({self.type.value}, {self.data})"

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


class EngineEventBus:
    """In-process async event bus for the voice pipeline.

    Subscribers receive ``Event`` objects. Each subscriber is called
    independently — one subscriber's failure does not affect others.

    Thread-safe publishing via ``publish_sync()``.
    """

    def __init__(self) -> None:
        self._subscribers: dict[PipelineEvent, list[EventCallback]] = {}
        self._wildcard_subscribers: list[EventCallback] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._event_count: int = 0
        self._error_count: int = 0
        self._latest: dict[PipelineEvent, dict] = {}  # latest payload per event type

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the event loop for thread-safe publishing."""
        self._loop = loop

    # ── Subscribe ─────────────────────────────────────────────────────────

    def subscribe(self, event_type: PipelineEvent, callback: EventCallback) -> None:
        """Subscribe to a specific event type."""
        subs = self._subscribers.setdefault(event_type, [])
        if callback not in subs:
            subs.append(callback)

    def subscribe_all(self, callback: EventCallback) -> None:
        """Subscribe to ALL events (wildcard)."""
        if callback not in self._wildcard_subscribers:
            self._wildcard_subscribers.append(callback)

    def unsubscribe(self, event_type: PipelineEvent, callback: EventCallback) -> None:
        """Remove a subscription."""
        subs = self._subscribers.get(event_type, [])
        try:
            subs.remove(callback)
        except ValueError:
            pass

    # ── Publish ───────────────────────────────────────────────────────────

    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers (async)."""
        self._event_count += 1

        callbacks = list(self._subscribers.get(event.type, []))
        callbacks.extend(self._wildcard_subscribers)

        if not callbacks:
            return

        if event.type not in _QUIET_EVENTS:
            log.debug("event_published", event_type=event.type.value, subscribers=len(callbacks))

        # Fire all callbacks concurrently, isolated
        results = await asyncio.gather(
            *(self._safe_call(cb, event) for cb in callbacks),
            return_exceptions=True,
        )

        for r in results:
            if isinstance(r, Exception):
                self._error_count += 1

    async def emit(self, event_type: PipelineEvent, **data: Any) -> None:
        """Convenience: create and publish an event."""
        self._latest[event_type] = data
        await self.publish(Event(event_type, data))

    def get_latest(self, event_type: PipelineEvent) -> Optional[dict[str, Any]]:
        """Return the most recently published payload for an event type, or None.

        Used by the companion ObservationLoop to poll for structured coding context
        without subscribing to the event stream.
        """
        return self._latest.get(event_type)

    def publish_sync(self, event_type: PipelineEvent, data: Optional[dict[str, Any]] = None) -> None:
        """Thread-safe synchronous publish for use from OS-level threads.

        Schedules the async publish on the event loop. If no loop is set
        or the loop is closed, the event is silently dropped.
        """
        loop = self._loop
        if loop is None or loop.is_closed():
            return

        event = Event(event_type, data)
        self._event_count += 1

        try:
            asyncio.run_coroutine_threadsafe(self.publish(event), loop)
        except RuntimeError:
            pass  # loop is closed

    # ── Internals ─────────────────────────────────────────────────────────

    async def _safe_call(self, callback: EventCallback, event: Event) -> None:
        """Call a subscriber with full error isolation."""
        try:
            await callback(event)
        except Exception as e:
            self._error_count += 1
            if event.type not in _QUIET_EVENTS:
                log.error(
                    "event_callback_error",
                    event_type=event.type.value,
                    error=str(e),
                    exc_info=True,
                )

    # ── Diagnostics ───────────────────────────────────────────────────────

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_events": self._event_count,
            "total_errors": self._error_count,
            "subscriber_count": sum(len(v) for v in self._subscribers.values())
                                + len(self._wildcard_subscribers),
            "event_types_subscribed": [
                k.value for k, v in self._subscribers.items() if v
            ],
        }


# Global engine event bus instance — created once, never destroyed.
engine_events = EngineEventBus()
