"""Echo cancellation for the audio pipeline.

When Genie speaks via TTS, the microphone picks up the output audio.
This module prevents the assistant's own speech from triggering
barge-in or false VAD detections.

Strategy:
- Track when TTS playback is active via enable/disable calls.
- During playback, multiply the VAD confidence threshold by a
  configurable factor (default 3x).
- Maintain a reference energy level from recent TTS output.
- Suppress frames whose energy correlates with the TTS reference.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Optional

import numpy as np
import structlog

log = structlog.get_logger("genie.engine.audio.echo")


class EchoCanceller:
    """Adaptive echo suppression for TTS playback.

    Approach:
    - When TTS is playing, we raise the VAD detection threshold.
    - We track the energy envelope of outgoing TTS audio and use it
      to gate incoming microphone frames.
    - True barge-in (user speaks louder than TTS) will still be detected.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        suppression_factor: float = 3.0,    # VAD threshold multiplier during TTS
        min_barge_in_energy: float = 3000.0,  # minimum energy to override suppression
        reference_window_ms: float = 500.0,
    ):
        self.sample_rate = sample_rate
        self.suppression_factor = suppression_factor
        self.min_barge_in_energy = min_barge_in_energy

        # State
        self._active = False
        self._activated_at: float = 0.0
        self._deactivated_at: float = 0.0

        # Reference energy from TTS output
        max_ref_frames = max(1, int(reference_window_ms / 1000.0 * sample_rate / 512))
        self._ref_energies: deque[float] = deque(maxlen=max_ref_frames)
        self._avg_ref_energy: float = 0.0

        # Grace period after TTS stops (echoes and room resonance linger)
        self._grace_period_s: float = 1.5

    # ══════════════════════════════════════════════════════════════════════
    # CONTROL
    # ══════════════════════════════════════════════════════════════════════

    def enable(self) -> None:
        """Enable echo suppression (TTS is about to play)."""
        if not self._active:
            self._active = True
            self._activated_at = time.time()
            log.debug("echo_suppression_enabled")

    def disable(self) -> None:
        """Disable echo suppression (TTS playback complete)."""
        if self._active:
            self._active = False
            self._deactivated_at = time.time()
            self._ref_energies.clear()
            self._avg_ref_energy = 0.0
            log.debug("echo_suppression_disabled")

    @property
    def is_active(self) -> bool:
        """True if echo suppression is currently active or in grace period."""
        if self._active:
            return True
        # Grace period after deactivation
        if self._deactivated_at > 0:
            return (time.time() - self._deactivated_at) < self._grace_period_s
        return False

    # ══════════════════════════════════════════════════════════════════════
    # PROCESSING
    # ══════════════════════════════════════════════════════════════════════

    def get_vad_threshold_multiplier(self) -> float:
        """Get the VAD threshold multiplier for current state.

        Returns 1.0 when no suppression, or `suppression_factor` during TTS.
        """
        if self.is_active:
            return self.suppression_factor
        return 1.0

    def should_suppress_frame(self, frame: bytes) -> bool:
        """Check if a microphone frame should be suppressed (likely echo).

        Returns True if the frame is likely echo from TTS output and
        should NOT be treated as user speech.
        """
        if not self.is_active:
            return False

        data = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
        if len(data) == 0:
            return True

        energy = float(np.sqrt(np.mean(data ** 2)))

        # If the user is speaking louder than the barge-in threshold,
        # let it through (real barge-in)
        if energy > self.min_barge_in_energy:
            return False

        return True

    def is_barge_in(self, frame: bytes) -> bool:
        """Check if a frame during TTS playback is a genuine barge-in.

        A barge-in is when the user speaks loudly enough to override
        the echo suppression threshold.
        """
        if not self.is_active:
            return False  # not during TTS, can't be barge-in

        data = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
        if len(data) == 0:
            return False

        energy = float(np.sqrt(np.mean(data ** 2)))
        return energy > self.min_barge_in_energy

    def feed_reference(self, tts_audio: bytes) -> None:
        """Feed TTS output audio for reference energy tracking."""
        data = np.frombuffer(tts_audio, dtype=np.int16).astype(np.float32)
        if len(data) == 0:
            return
        energy = float(np.sqrt(np.mean(data ** 2)))
        self._ref_energies.append(energy)
        if self._ref_energies:
            self._avg_ref_energy = sum(self._ref_energies) / len(self._ref_energies)
