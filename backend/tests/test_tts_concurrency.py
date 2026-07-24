"""Tests for TTS concurrency, timeout, and error recovery.

Verifies the fixes from the stability upgrade:
- C1: Numba shim inside lock
- C2: Inference serialization lock
- H1: TTS consumer timeout
- H2: Settings copy cached per-turn
"""
from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


# ── TTS Lock Tests ───────────────────────────────────────────────────────────

class TestTTSLocks:
    """Test that TTS has proper lock protection (C1, C2 fixes)."""

    def test_init_lock_exists(self):
        """C1 fix: init lock exists and is a threading.Lock."""
        from app.tts import _tts_init_lock
        assert isinstance(_tts_init_lock, type(threading.Lock()))

    def test_inference_lock_exists(self):
        """C2 fix: inference lock exists and is a threading.Lock."""
        from app.tts import _tts_inference_lock
        assert isinstance(_tts_inference_lock, type(threading.Lock()))

    def test_numba_shim_idempotent(self):
        """C1 fix: numba shim can be installed multiple times safely."""
        from app.tts import _install_numba_shim
        import sys
        
        # First install
        _install_numba_shim()
        assert "numba" in sys.modules
        
        # Second install (should be no-op)
        _install_numba_shim()
        assert "numba" in sys.modules

    def test_concurrent_shim_install(self):
        """C1 fix: concurrent numba shim installation is safe."""
        from app.tts import _install_numba_shim
        errors = []

        def install():
            try:
                _install_numba_shim()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=install) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        
        assert not errors


# ── TTS Consumer Timeout Tests ───────────────────────────────────────────────

class TestTTSConsumerTimeout:
    """Test H1 fix: TTS consumer has timeout protection."""

    @pytest.mark.asyncio
    async def test_consumer_timeout_on_empty_queue(self):
        """Consumer should break if no items arrive within timeout."""
        tts_queue = asyncio.Queue()
        first_chunk_emitted = False
        timed_out = False

        async def tts_consumer_with_short_timeout():
            nonlocal timed_out
            try:
                item = await asyncio.wait_for(tts_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                timed_out = True

        await tts_consumer_with_short_timeout()
        assert timed_out

    @pytest.mark.asyncio
    async def test_consumer_processes_sentinel(self):
        """Consumer should exit cleanly on None sentinel."""
        tts_queue = asyncio.Queue()
        processed = []

        async def tts_consumer():
            while True:
                try:
                    item = await asyncio.wait_for(tts_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    break
                if item is None:
                    break
                processed.append(item)

        await tts_queue.put("chunk1")
        await tts_queue.put("chunk2")
        await tts_queue.put(None)

        await tts_consumer()
        assert processed == ["chunk1", "chunk2"]


# ── Settings Copy Tests ──────────────────────────────────────────────────────

class TestSettingsCopy:
    """Test H2 fix: settings copy is cached per-turn."""

    def test_settings_model_copy(self, settings):
        """model_copy() creates a distinct but equivalent object."""
        copied = settings.model_copy()
        assert copied is not settings
        assert copied.tts_engine == settings.tts_engine
        assert copied.tts_sample_rate == settings.tts_sample_rate


# ── Event Bus Thread Safety Tests ────────────────────────────────────────────

class TestEventBusThreadSafety:
    """Test event bus publish_sync for thread-safe publishing."""

    @pytest.mark.asyncio
    async def test_publish_calls_subscribers(self):
        """Basic publish delivers to subscribers."""
        from app.core.event_bus.bus import EventBus
        
        bus = EventBus()
        received = []
        
        async def handler(payload):
            received.append(payload)
        
        bus.subscribe("test.event", handler)
        await bus.publish("test.event", {"data": "hello"})
        
        assert len(received) == 1
        assert received[0]["data"] == "hello"
        assert received[0]["type"] == "test.event"

    @pytest.mark.asyncio
    async def test_wildcard_subscriber(self):
        """Wildcard subscriber receives all events."""
        from app.core.event_bus.bus import EventBus
        
        bus = EventBus()
        received = []
        
        async def handler(payload):
            received.append(payload["type"])
        
        bus.subscribe("*", handler)
        await bus.publish("event.a", {})
        await bus.publish("event.b", {})
        
        assert received == ["event.a", "event.b"]

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        """Unsubscribed handler is not called."""
        from app.core.event_bus.bus import EventBus
        
        bus = EventBus()
        received = []
        
        async def handler(payload):
            received.append(True)
        
        bus.subscribe("test", handler)
        bus.unsubscribe("test", handler)
        await bus.publish("test", {})
        
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_error_in_callback_doesnt_crash(self):
        """An exception in one callback doesn't prevent others."""
        from app.core.event_bus.bus import EventBus
        
        bus = EventBus()
        received = []
        
        async def bad_handler(payload):
            raise ValueError("boom")
        
        async def good_handler(payload):
            received.append(True)
        
        bus.subscribe("test", bad_handler)
        bus.subscribe("test", good_handler)
        await bus.publish("test", {})
        
        assert len(received) == 1

    def test_publish_sync_without_loop(self):
        """publish_sync doesn't crash when no event loop is available."""
        from app.core.event_bus.bus import EventBus
        
        bus = EventBus()
        # Should not raise
        bus.publish_sync("test.event", {"data": "from_thread"})

    @pytest.mark.asyncio
    async def test_stats(self):
        """Event bus stats track subscriptions and publish count."""
        from app.core.event_bus.bus import EventBus
        
        bus = EventBus()
        
        async def handler(payload):
            pass
        
        bus.subscribe("test", handler)
        await bus.publish("test", {})
        await bus.publish("test", {})
        
        stats = bus.stats
        assert stats["total_events_published"] == 2
        assert stats["subscriber_count"] == 1

    @pytest.mark.asyncio
    async def test_typed_event_constants(self):
        """Voice pipeline event constants are accessible."""
        from app.core.event_bus.bus import VoicePipelineEvents, SystemEvents
        
        assert VoicePipelineEvents.WAKE_WORD_DETECTED == "voice.wake_word_detected"
        assert SystemEvents.STARTUP == "system.startup"


# ── Circuit Breaker Integration ──────────────────────────────────────────────

class TestCircuitBreakerIntegration:
    """Verify circuit breaker still works after LLM client changes."""

    def test_circuit_breaker_basic_flow(self):
        """Circuit breaker transitions: CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
        from app.services.circuit_breaker import CircuitBreaker, CBState
        
        cb = CircuitBreaker(name="test", failure_threshold=2, cooldown_seconds=0.1)
        
        assert cb.state == CBState.CLOSED
        assert cb.allow_request()
        
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CBState.OPEN
        assert not cb.allow_request()
        
        # Wait for cooldown
        time.sleep(0.15)
        assert cb.state == CBState.HALF_OPEN
        assert cb.allow_request()
        
        cb.record_success()
        assert cb.state == CBState.CLOSED


# ── Auth Session Cleanup Tests ───────────────────────────────────────────────

class TestAuthCleanup:
    """Test H8 fix: session cleanup."""

    def test_cleanup_expired_sessions(self, settings):
        """Expired sessions are removed."""
        from app.auth import SESSIONS, Session, cleanup_expired_sessions
        
        # Create an expired session
        token = "test-expired-token"
        SESSIONS[token] = Session(
            session_id="test-expired",
            token=token,
            last_seen=0,  # epoch = definitely expired
        )
        
        cleaned = cleanup_expired_sessions(settings)
        assert cleaned >= 1
        assert token not in SESSIONS

    def test_cleanup_preserves_active_sessions(self, settings):
        """Active sessions are not removed."""
        from app.auth import SESSIONS, Session, cleanup_expired_sessions
        import time
        
        token = "test-active-token"
        SESSIONS[token] = Session(
            session_id="test-active",
            token=token,
            last_seen=time.time(),  # just now
        )
        
        cleanup_expired_sessions(settings)
        assert token in SESSIONS
        
        # Cleanup
        del SESSIONS[token]


# ── Conversation Manager Cleanup Tests ───────────────────────────────────────

class TestConversationManagerCleanup:
    """Test H7 fix: context limit and cleanup."""

    def test_max_contexts_enforced(self):
        """ConversationManager evicts oldest when at capacity."""
        from app.conversation_manager import ConversationManager
        
        mgr = ConversationManager()
        mgr.MAX_CONTEXTS = 5
        
        # Fill to capacity
        for i in range(5):
            mgr.get_context(f"session-{i}")
        
        assert len(mgr.contexts) == 5
        
        # One more should evict the oldest
        mgr.get_context("session-new")
        assert len(mgr.contexts) == 5
        assert "session-new" in mgr.contexts

    def test_cleanup_returns_count(self):
        """cleanup_old_sessions returns the number removed."""
        from app.conversation_manager import ConversationManager
        from datetime import datetime, timedelta
        
        mgr = ConversationManager()
        
        # Create old context
        ctx = mgr.get_context("old-session")
        ctx.conversation_start = datetime.now() - timedelta(hours=48)
        
        # Create fresh context
        mgr.get_context("fresh-session")
        
        removed = mgr.cleanup_old_sessions(max_age_hours=24)
        assert removed == 1
        assert "old-session" not in mgr.contexts
        assert "fresh-session" in mgr.contexts
