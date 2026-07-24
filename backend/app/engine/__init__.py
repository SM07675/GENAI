"""Genie v2 Voice Pipeline — production-quality conversation engine.

This package implements a fault-tolerant, event-driven, async voice pipeline
with isolated workers communicating via bounded async queues.

Architecture:
    MicrophoneService (thread) → VADWorker → WakeDetector
        → StreamingSTT → LLMStream → TTSStreamWorker → PlaybackTracker

Supervised by VoicePipeline with PipelineWatchdog for self-healing.

Modules:
    state_machine  — 8-state FSM (IDLE → WAIT_WAKE → LISTENING → ...)
    event_bus      — Typed async event bus with thread-safe publishing
    pipeline       — Main supervisor (VoicePipeline)
    watchdog       — Heartbeat-based worker monitoring
    metrics        — Structured latency + resource logging
    cancellation   — Cooperative cancellation tokens
    audio/         — Microphone, VAD, noise gate, echo cancellation
    wake/          — Wake word detection (Vosk)
    stt/           — Streaming speech-to-text (faster-whisper)
    brain/         — Context, intent routing, LLM streaming
    speech/        — TTS streaming, playback tracking
"""
from __future__ import annotations

from .pipeline import VoicePipeline

# Singleton pipeline instance
_pipeline_instance: VoicePipeline | None = None


def get_voice_pipeline() -> VoicePipeline:
    """Get or create the singleton VoicePipeline instance."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = VoicePipeline()
    return _pipeline_instance


# Backward compatibility aliases
ConversationEngine = VoicePipeline
get_conversation_engine = get_voice_pipeline


__all__ = [
    "VoicePipeline",
    "get_voice_pipeline",
    "ConversationEngine",
    "get_conversation_engine",
]
