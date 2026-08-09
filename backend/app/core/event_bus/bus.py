"""
Event Bus for Genie OS.
Provides a simple in-memory Pub/Sub mechanism for decoupling components.

Thread-safety (L1 fix)
-----------------------
Added ``publish_sync`` for thread-safe publishing from OS-level audio
threads, and typed event constants so subscribers use consistent names.
"""
import asyncio
import logging
from typing import Callable, Awaitable, Any, Dict, List, Optional

log = logging.getLogger("genie_os.event_bus")

EventCallback = Callable[[Dict[str, Any]], Awaitable[None]]


# ── Typed event constants for the voice pipeline ─────────────────────────────

class VoicePipelineEvents:
    """Standard event names for the voice pipeline."""
    WAKE_WORD_DETECTED = "voice.wake_word_detected"
    SPEECH_STARTED = "voice.speech_started"
    SPEECH_ENDED = "voice.speech_ended"
    TRANSCRIPTION_COMPLETE = "voice.transcription_complete"
    RESPONSE_GENERATING = "voice.response_generating"
    TTS_STARTED = "voice.tts_started"
    TTS_COMPLETE = "voice.tts_complete"
    STATE_CHANGED = "voice.state_changed"
    ERROR = "voice.error"
    BARGE_IN = "voice.barge_in"
    FOLLOW_UP_TIMEOUT = "voice.follow_up_timeout"


class GenieEvents:
    """Standardized event names for Genie OS lifecycle and companion layer."""
    WAKE_WORD_DETECTED = "WakeWordDetected"
    LISTENING_STARTED = "ListeningStarted"
    SPEECH_RECOGNIZED = "SpeechRecognized"
    INTENT_RESOLVED = "IntentResolved"
    PLAN_CREATED = "PlanCreated"
    TOOL_STARTED = "ToolStarted"
    TOOL_FINISHED = "ToolFinished"
    MEMORY_UPDATED = "MemoryUpdated"
    RESPONSE_GENERATED = "ResponseGenerated"
    LISTENING_RESUMED = "ListeningResumed"
    PERMISSION_REQUESTED = "PermissionRequested"
    SUGGESTION_QUEUED = "SuggestionQueued"


class SystemEvents:
    """Standard event names for system-level operations."""
    STARTUP = "system.startup"
    SHUTDOWN = "system.shutdown"
    HEALTH_CHECK = "system.health_check"
    SUBSYSTEM_ERROR = "system.subsystem_error"
    SUBSYSTEM_RECOVERED = "system.subsystem_recovered"



class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[EventCallback]] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._event_count = 0
        
    def subscribe(self, event_type: str, callback: EventCallback) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        log.debug(f"Subscribed to event: {event_type}")

    def unsubscribe(self, event_type: str, callback: EventCallback) -> None:
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
                log.debug(f"Unsubscribed from event: {event_type}")
            except ValueError:
                pass

    async def publish(self, event_type: str, payload: Dict[str, Any] = None) -> None:
        if payload is None:
            payload = {}
        payload["type"] = event_type
        
        self._event_count += 1
        
        callbacks = self._subscribers.get(event_type, [])
        # Also notify wildcard subscribers
        wildcard_callbacks = self._subscribers.get("*", [])
        
        all_callbacks = callbacks + wildcard_callbacks
        
        if not all_callbacks:
            return
        
        # Log events for diagnostics (skip high-frequency frame events)
        if not event_type.endswith(".frame"):
            log.debug(f"Event published: {event_type} (subscribers: {len(all_callbacks)})")
            
        tasks = []
        for cb in all_callbacks:
            tasks.append(asyncio.create_task(self._safe_execute(cb, payload)))
            
        await asyncio.gather(*tasks, return_exceptions=True)

    def publish_sync(self, event_type: str, payload: Dict[str, Any] = None) -> None:
        """Thread-safe synchronous publish for use from OS-level threads.
        
        Schedules the async publish() on the event loop. If no loop is
        set or the loop is closed, the event is silently dropped.
        """
        if payload is None:
            payload = {}
        payload["type"] = event_type
        
        self._event_count += 1
        
        loop = self._loop
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                log.debug(f"No event loop for sync publish: {event_type}")
                return
        
        try:
            asyncio.run_coroutine_threadsafe(
                self._dispatch(event_type, payload), loop
            )
        except RuntimeError:
            pass  # loop is closed

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the event loop for thread-safe publishing."""
        self._loop = loop

    async def _dispatch(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Internal dispatch — resolves callbacks and runs them."""
        callbacks = self._subscribers.get(event_type, [])
        wildcard_callbacks = self._subscribers.get("*", [])
        all_callbacks = callbacks + wildcard_callbacks
        
        if not all_callbacks:
            return
        
        tasks = []
        for cb in all_callbacks:
            tasks.append(asyncio.create_task(self._safe_execute(cb, payload)))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_execute(self, callback: EventCallback, payload: Dict[str, Any]) -> None:
        try:
            await callback(payload)
        except Exception as e:
            log.error(f"Error in event callback for {payload.get('type')}: {e}", exc_info=True)

    @property
    def stats(self) -> Dict[str, Any]:
        """Return event bus statistics for diagnostics."""
        return {
            "total_events_published": self._event_count,
            "subscriber_count": sum(len(v) for v in self._subscribers.values()),
            "event_types": list(self._subscribers.keys()),
        }


# Global event bus instance
event_bus = EventBus()
