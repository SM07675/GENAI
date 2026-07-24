"""Noise gate and Automatic Gain Control for the audio pipeline.

Provides:
- Noise floor estimation via exponential moving average (EMA)
- High-pass filter at 80Hz to remove hum and low-frequency rumble
- Automatic Gain Control: normalize to target RMS level
"""
from __future__ import annotations

import numpy as np
import structlog

log = structlog.get_logger("genie.engine.audio.noise_gate")


class NoiseGate:
    """Real-time noise reduction and gain control.

    Processes raw PCM16 audio frames in-place. All operations are
    vectorized numpy for speed.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        noise_ema_alpha: float = 0.05,
        noise_init_frames: int = 20,
        high_pass_cutoff_hz: float = 80.0,
        agc_target_rms: float = 2000.0,    # target RMS for int16 audio
        agc_max_gain: float = 5.0,
        agc_attack: float = 0.1,            # fast gain increase
        agc_release: float = 0.01,          # slow gain decrease
    ):
        self.sample_rate = sample_rate
        self._noise_alpha = noise_ema_alpha
        self._noise_init_frames = noise_init_frames
        self._high_pass_cutoff = high_pass_cutoff_hz
        self._agc_target = agc_target_rms
        self._agc_max_gain = agc_max_gain
        self._agc_attack = agc_attack
        self._agc_release = agc_release

        # State
        self._baseline_rms: float = 0.0
        self._noise_initialized = False
        self._noise_init_count = 0
        self._current_gain: float = 1.0
        self._prev_sample: float = 0.0  # for high-pass filter

        # Pre-compute high-pass coefficient
        rc = 1.0 / (2.0 * np.pi * self._high_pass_cutoff)
        dt = 1.0 / self.sample_rate
        self._hp_alpha = rc / (rc + dt)

    # ══════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════════════

    def process(self, frame: bytes) -> bytes:
        """Process a raw PCM16 frame through the noise pipeline.

        Returns the processed frame (same length).
        """
        data = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
        if len(data) == 0:
            return frame

        # 1. High-pass filter (remove hum)
        data = self._high_pass_filter(data)

        # 2. Update noise baseline
        self._update_noise_baseline(data)

        # 3. Automatic Gain Control
        data = self._apply_agc(data)

        # Clip and convert back to int16
        data = np.clip(data, -32768, 32767).astype(np.int16)
        return data.tobytes()

    def get_noise_floor(self) -> float:
        """Current estimated noise floor RMS."""
        return self._baseline_rms

    def is_noise_calibrated(self) -> bool:
        """True if the noise floor has been calibrated."""
        return self._noise_initialized

    def reset(self) -> None:
        """Reset all state (call on microphone reconnect)."""
        self._baseline_rms = 0.0
        self._noise_initialized = False
        self._noise_init_count = 0
        self._current_gain = 1.0
        self._prev_sample = 0.0

    # ══════════════════════════════════════════════════════════════════════
    # INTERNALS
    # ══════════════════════════════════════════════════════════════════════

    def _high_pass_filter(self, data: np.ndarray) -> np.ndarray:
        """First-order IIR high-pass filter to remove low-frequency hum."""
        alpha = self._hp_alpha
        output = np.empty_like(data)
        prev_in = self._prev_sample
        prev_out = 0.0

        for i in range(len(data)):
            output[i] = alpha * (prev_out + data[i] - prev_in)
            prev_in = data[i]
            prev_out = output[i]

        self._prev_sample = float(data[-1])
        return output

    def _update_noise_baseline(self, data: np.ndarray) -> None:
        """Update noise floor estimate using EMA."""
        rms = float(np.sqrt(np.mean(data ** 2)))

        if not self._noise_initialized:
            self._noise_init_count += 1
            self._baseline_rms = (
                (self._baseline_rms * (self._noise_init_count - 1) + rms)
                / self._noise_init_count
            )
            if self._noise_init_count >= self._noise_init_frames:
                self._noise_initialized = True
                log.info("noise_floor_calibrated", rms=round(self._baseline_rms, 1))
        else:
            # Only update on "quiet" frames (not during speech)
            if rms < self._baseline_rms * 3.0:
                self._baseline_rms = (
                    self._noise_alpha * rms
                    + (1 - self._noise_alpha) * self._baseline_rms
                )

    def _apply_agc(self, data: np.ndarray) -> np.ndarray:
        """Apply automatic gain control."""
        rms = float(np.sqrt(np.mean(data ** 2)))
        if rms < 1.0:
            return data  # silence, don't amplify noise

        desired_gain = self._agc_target / rms
        desired_gain = min(desired_gain, self._agc_max_gain)

        # Smooth gain changes
        if desired_gain > self._current_gain:
            self._current_gain += self._agc_attack * (desired_gain - self._current_gain)
        else:
            self._current_gain += self._agc_release * (desired_gain - self._current_gain)

        return data * self._current_gain
