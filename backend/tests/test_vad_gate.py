"""Unit tests for VADGate (v12 barge-in detector).

Tests the core VAD gate logic:
- Does NOT fire before min_speech_ms of continuous voiced audio.
- Fires on_speech_start after exactly min_speech_ms of voiced frames.
- Resets the counter on unvoiced frames (requires continuous speech).
- Respects the cooldown_ms and does not re-fire immediately.
- Calls on_speech_start only while active() returns True.
- Handles ONNX unavailability gracefully (energy fallback).
"""
from __future__ import annotations

import asyncio
import struct
import time
import pytest
import numpy as np

from app.engine.audio.vad_gate import VADGate, BargeInConfig, _FRAME_SAMPLES


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_frame(amplitude: float) -> bytes:
    """Create a 512-sample PCM int16 frame with given amplitude (0.0–1.0)."""
    samples = (np.ones(_FRAME_SAMPLES) * amplitude * 32767).astype(np.int16)
    return samples.tobytes()


VOICED_FRAME = _make_frame(0.5)     # loud enough to exceed most thresholds
SILENT_FRAME = _make_frame(0.0001) # near-silence


async def _feed_frames(gate: VADGate, frames: list[bytes], on_speech_start, active=lambda: True):
    """Feed a list of frames through gate.watch() using a test async iterator."""

    async def _iter():
        for f in frames:
            yield f

    await gate.watch(_iter(), on_speech_start, active)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestVADGateEnergyFallback:
    """Tests that work without the ONNX model (energy fallback path)."""

    def _make_gate(self, min_speech_ms=200, cooldown_ms=400, threshold=0.5) -> VADGate:
        gate = VADGate(config=BargeInConfig(
            threshold=threshold,
            min_speech_ms=min_speech_ms,
            cooldown_ms=cooldown_ms,
        ))
        # Force energy fallback — don't try to load ONNX model in unit tests
        gate._loaded = True
        gate._session = None
        return gate

    @pytest.mark.asyncio
    async def test_does_not_fire_before_threshold(self):
        """VADGate must NOT fire if voiced frames are fewer than min_speech_ms."""
        gate = self._make_gate(min_speech_ms=200)
        fired = []

        async def on_speech_start():
            fired.append(time.time())

        # Feed only 1 voiced frame (~32ms) — well under 200ms threshold
        await _feed_frames(gate, [VOICED_FRAME], on_speech_start)

        assert not fired, "Should not fire with only 32ms of voiced audio"

    @pytest.mark.asyncio
    async def test_fires_after_enough_voiced_frames(self):
        """VADGate fires after continuous voiced audio ≥ min_speech_ms."""
        gate = self._make_gate(min_speech_ms=64)  # 2 frames at 32ms each
        fired = []

        async def on_speech_start():
            fired.append(time.time())

        # 2 voiced frames = 64ms ≥ 64ms threshold → should fire
        await _feed_frames(gate, [VOICED_FRAME, VOICED_FRAME], on_speech_start)

        assert len(fired) == 1, f"Expected exactly 1 fire, got {len(fired)}"

    @pytest.mark.asyncio
    async def test_resets_on_unvoiced_frame(self):
        """An unvoiced frame resets the continuity counter."""
        gate = self._make_gate(min_speech_ms=64)
        fired = []

        async def on_speech_start():
            fired.append(time.time())

        # 1 voiced, 1 silent (reset), 1 voiced — only 32ms of continuous speech
        frames = [VOICED_FRAME, SILENT_FRAME, VOICED_FRAME]
        await _feed_frames(gate, frames, on_speech_start)

        assert not fired, "Counter should reset on silent frame — should not fire"

    @pytest.mark.asyncio
    async def test_inactive_gate_does_not_fire(self):
        """When active() returns False, gate drains frames but never fires."""
        gate = self._make_gate(min_speech_ms=32)
        fired = []

        async def on_speech_start():
            fired.append(time.time())

        frames = [VOICED_FRAME] * 10
        await _feed_frames(gate, frames, on_speech_start, active=lambda: False)

        assert not fired, "Gate should not fire when active() is False"

    @pytest.mark.asyncio
    async def test_active_gate_fires_then_goes_inactive(self):
        """Gate fires when active, subsequent frames while inactive are ignored."""
        gate = self._make_gate(min_speech_ms=32, cooldown_ms=0)
        fired = []

        active_flag = [True]

        async def on_speech_start():
            fired.append(time.time())
            active_flag[0] = False  # Deactivate when speech start triggers barge-in

        async def _iter():
            for _ in range(6):
                yield VOICED_FRAME

        await gate.watch(_iter(), on_speech_start, lambda: active_flag[0])

        assert len(fired) == 1, f"Should fire exactly once, got {len(fired)}"

    @pytest.mark.asyncio
    async def test_cooldown_prevents_double_fire(self):
        """Gate must not fire again within cooldown_ms of the last fire."""
        gate = self._make_gate(min_speech_ms=32, cooldown_ms=10_000)  # 10s cooldown
        fired = []

        async def on_speech_start():
            fired.append(time.time())

        # First batch — should fire once
        await _feed_frames(gate, [VOICED_FRAME, VOICED_FRAME], on_speech_start)
        # Second batch immediately — still within cooldown
        await _feed_frames(gate, [VOICED_FRAME, VOICED_FRAME], on_speech_start)

        assert len(fired) == 1, f"Cooldown should prevent second fire, got {len(fired)}"

    @pytest.mark.asyncio
    async def test_fires_again_after_cooldown_expires(self):
        """Gate fires again after cooldown_ms elapses."""
        gate = self._make_gate(min_speech_ms=32, cooldown_ms=50)  # 50ms cooldown
        fired = []

        async def on_speech_start():
            fired.append(time.time())

        # First fire
        await _feed_frames(gate, [VOICED_FRAME, VOICED_FRAME], on_speech_start)
        assert len(fired) == 1

        # Wait for cooldown to expire, then fire again
        await asyncio.sleep(0.06)  # 60ms > 50ms cooldown
        gate._voiced_ms = 0  # reset continuity
        await _feed_frames(gate, [VOICED_FRAME, VOICED_FRAME], on_speech_start)

        assert len(fired) == 2, f"Should fire again after cooldown, got {len(fired)}"

    @pytest.mark.asyncio
    async def test_empty_stream_no_fire(self):
        """Empty frame stream — gate should do nothing."""
        gate = self._make_gate()
        fired = []

        async def on_speech_start():
            fired.append(time.time())

        await _feed_frames(gate, [], on_speech_start)
        assert not fired

    @pytest.mark.asyncio
    async def test_reset_clears_state(self):
        """Calling reset() clears the voiced_ms counter."""
        gate = self._make_gate(min_speech_ms=64)
        fired = []

        async def on_speech_start():
            fired.append(time.time())

        # Feed 1 voiced frame (32ms, not enough to fire)
        await _feed_frames(gate, [VOICED_FRAME], on_speech_start)
        assert gate._voiced_ms == 32

        gate.reset()
        assert gate._voiced_ms == 0, "reset() should clear voiced_ms counter"
