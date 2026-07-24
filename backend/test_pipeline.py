"""Quick smoke test for the new voice pipeline components."""
import asyncio
import sys

async def test_state_machine():
    from app.engine.state_machine import ConversationStateMachine, EngineState

    sm = ConversationStateMachine()
    assert sm.state == EngineState.IDLE

    # Valid transitions
    assert await sm.transition(EngineState.WAIT_WAKE, "test")
    assert sm.state == EngineState.WAIT_WAKE

    assert await sm.transition(EngineState.LISTENING, "wake")
    assert sm.state == EngineState.LISTENING

    # Invalid transition should be rejected
    assert not await sm.transition(EngineState.SPEAKING, "invalid")
    assert sm.state == EngineState.LISTENING

    # Full cycle
    assert await sm.transition(EngineState.UNDERSTANDING, "speech")
    assert await sm.transition(EngineState.THINKING, "transcript")
    assert await sm.transition(EngineState.STREAMING_RESPONSE, "llm")
    assert await sm.transition(EngineState.SPEAKING, "audio")
    assert await sm.transition(EngineState.RETURN_TO_LISTENING, "done")
    assert await sm.transition(EngineState.LISTENING, "follow_up")
    assert await sm.transition(EngineState.WAIT_WAKE, "timeout")

    # Force transition works regardless
    await sm.force_transition(EngineState.LISTENING, "force_test")
    assert sm.state == EngineState.LISTENING

    print(f"  State machine: {sm.transition_count} transitions, {len(sm.history.all_entries)} history entries")
    print("  [PASS] State machine tests passed")


async def test_event_bus():
    from app.engine.event_bus import EngineEventBus, PipelineEvent, Event

    bus = EngineEventBus()
    bus.set_loop(asyncio.get_running_loop())

    received = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe(PipelineEvent.WAKE_DETECTED, handler)
    await bus.emit(PipelineEvent.WAKE_DETECTED)
    assert len(received) == 1
    assert received[0].type == PipelineEvent.WAKE_DETECTED

    # Wildcard
    bus.subscribe_all(handler)
    await bus.emit(PipelineEvent.SPEECH_START)
    assert len(received) == 2  # 1 from WAKE_DETECTED + 1 from wildcard on SPEECH_START

    print(f"  Event bus: {bus.stats}")
    print("  [PASS] Event bus tests passed")


async def test_intent_router():
    from app.engine.brain.intent_router import IntentRouter, IntentType

    router = IntentRouter()

    # Wake phrase stripping
    assert router.strip_wake_phrase("Hey Genie, open YouTube") == "open YouTube"
    assert router.strip_wake_phrase("hey genie what time is it") == "what time is it"
    assert router.strip_wake_phrase("Hello Genie") == ""

    # Intent classification
    assert router.classify("stop") == IntentType.STOP_AUDIO
    assert router.classify("Hey Genie") == IntentType.WAKE_ONLY
    assert router.classify("what's the weather in London") == IntentType.NONE
    assert router.classify("repeat") == IntentType.REPEAT
    assert router.classify("volume up") == IntentType.VOLUME_UP

    print("  [PASS] Intent router tests passed")


async def test_context():
    from app.engine.brain.context import UnifiedContext, context_store

    ctx = context_store.get("test_session")
    ctx.add_user_turn("What's the weather in London?")
    assert ctx.turn_count == 1
    assert ctx.last_entity.get("location") == "London"

    # Reference resolution
    resolved = ctx.resolve_references("what about there")
    assert "London" in resolved

    ctx.add_assistant_turn("It's sunny in London.", tool_calls=[
        {"name": "get_weather", "arguments": {"location": "London"}}
    ])
    assert ctx.last_action == "get_weather"

    print("  [PASS] Context tests passed")


async def test_playback_tracker():
    from app.engine.speech.playback import PlaybackTracker

    pt = PlaybackTracker(playback_timeout=2.0)
    assert not pt.has_audio
    assert pt.chunks_sent == 0

    pt.record_chunk_sent(1024)
    pt.record_chunk_sent(2048)
    assert pt.chunks_sent == 2
    assert pt.has_audio

    pt.mark_playback_complete()
    completed = await pt.wait_for_playback()
    assert completed

    print("  [PASS] Playback tracker tests passed")


async def test_metrics():
    from app.engine.metrics import pipeline_metrics

    timer = pipeline_metrics.time("test.stage")
    import time; time.sleep(0.01)
    duration = timer.finish()
    assert duration > 5  # at least 5ms

    pipeline_metrics.increment("test.counter")
    pipeline_metrics.increment("test.counter")
    assert pipeline_metrics.count("test.counter") == 2

    stats = pipeline_metrics.get_stage_stats("test.stage")
    assert stats["count"] == 1
    assert stats["avg_ms"] > 5

    print("  [PASS] Metrics tests passed")


async def test_cancellation():
    from app.engine.cancellation import CancellationToken, CancellationScope

    scope = CancellationScope("test_turn")
    t1 = scope.create_token()
    t2 = scope.create_token()

    assert not t1.is_cancelled
    assert not t2.is_cancelled

    scope.cancel_all("test")
    assert t1.is_cancelled
    assert t2.is_cancelled
    assert t1.reason == "test"

    # New tokens from cancelled scope should be pre-cancelled
    t3 = scope.create_token()
    assert t3.is_cancelled

    print("  [PASS] Cancellation tests passed")


async def main():
    print("=" * 60)
    print("Genie Voice Pipeline - Smoke Tests")
    print("=" * 60)

    tests = [
        ("State Machine", test_state_machine),
        ("Event Bus", test_event_bus),
        ("Intent Router", test_intent_router),
        ("Context Manager", test_context),
        ("Playback Tracker", test_playback_tracker),
        ("Metrics", test_metrics),
        ("Cancellation", test_cancellation),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            await test_fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name} FAILED: {e}")
            import traceback; traceback.print_exc()
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
