"""Structured metrics for the Genie voice pipeline.

Tracks latency, throughput, and resource usage across all pipeline stages.
All metrics are stored in-memory for the lifetime of the process.
"""
from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

log = structlog.get_logger("genie.engine.metrics")


@dataclass
class TimingRecord:
    """A single timing measurement."""
    stage: str
    start: float
    end: float = 0.0
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def finish(self) -> float:
        self.end = time.time()
        self.duration_ms = (self.end - self.start) * 1000.0
        return self.duration_ms


class StageTimer:
    """Context manager for timing a pipeline stage."""

    def __init__(self, metrics: "PipelineMetrics", stage: str, **metadata: Any):
        self._metrics = metrics
        self._record = TimingRecord(stage=stage, start=time.time(), metadata=metadata)

    def __enter__(self) -> "StageTimer":
        return self

    def __exit__(self, *args: Any) -> None:
        self.finish()

    def finish(self) -> float:
        """Finish timing and record the result. Returns duration in ms."""
        duration = self._record.finish()
        self._metrics._record_timing(self._record)
        return duration

    @property
    def elapsed_ms(self) -> float:
        return (time.time() - self._record.start) * 1000.0


class PipelineMetrics:
    """Central metrics collector for the voice pipeline.

    Tracks:
    - Per-stage latencies (wake, STT, LLM, TTS, playback)
    - Total turn latency (end-to-end)
    - Queue depths
    - Dropped frames
    - Error counts
    - Resource usage (CPU, memory)
    """

    MAX_HISTORY = 500  # keep last N timing records per stage

    def __init__(self) -> None:
        self._timings: dict[str, deque[TimingRecord]] = {}
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}
        self._turn_count: int = 0
        self._error_count: int = 0
        self._start_time: float = time.time()

    # ── Timing ────────────────────────────────────────────────────────────

    def time(self, stage: str, **metadata: Any) -> StageTimer:
        """Start timing a pipeline stage. Use as context manager or call .finish()."""
        return StageTimer(self, stage, **metadata)

    def _record_timing(self, record: TimingRecord) -> None:
        """Record a completed timing measurement."""
        q = self._timings.setdefault(record.stage, deque(maxlen=self.MAX_HISTORY))
        q.append(record)

        # Log non-trivial timings
        if record.duration_ms > 5.0:
            log.info(
                "pipeline_timing",
                stage=record.stage,
                duration_ms=round(record.duration_ms, 1),
                **record.metadata,
            )

    def record_latency(self, stage: str, duration_ms: float, **metadata: Any) -> None:
        """Record a pre-computed latency measurement."""
        record = TimingRecord(
            stage=stage,
            start=time.time() - duration_ms / 1000.0,
            end=time.time(),
            duration_ms=duration_ms,
            metadata=metadata,
        )
        self._record_timing(record)

    # ── Counters ──────────────────────────────────────────────────────────

    def increment(self, name: str, amount: int = 1) -> None:
        """Increment a counter."""
        self._counters[name] = self._counters.get(name, 0) + amount

    def count(self, name: str) -> int:
        """Get a counter value."""
        return self._counters.get(name, 0)

    # ── Gauges ────────────────────────────────────────────────────────────

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge value (e.g., queue depth)."""
        self._gauges[name] = value

    def gauge(self, name: str) -> float:
        """Get a gauge value."""
        return self._gauges.get(name, 0.0)

    # ── Turn tracking ─────────────────────────────────────────────────────

    def record_turn(self) -> None:
        self._turn_count += 1

    def record_error(self, stage: str, error: str) -> None:
        self._error_count += 1
        self.increment(f"errors.{stage}")
        log.warning("pipeline_error_recorded", stage=stage, error=error)

    # ── Aggregation ───────────────────────────────────────────────────────

    def get_stage_stats(self, stage: str) -> dict[str, Any]:
        """Get statistics for a pipeline stage."""
        records = list(self._timings.get(stage, []))
        if not records:
            return {"count": 0}

        durations = [r.duration_ms for r in records]
        durations.sort()
        n = len(durations)

        return {
            "count": n,
            "min_ms": round(durations[0], 1),
            "max_ms": round(durations[-1], 1),
            "avg_ms": round(sum(durations) / n, 1),
            "p50_ms": round(durations[n // 2], 1),
            "p95_ms": round(durations[int(n * 0.95)], 1) if n >= 20 else None,
            "p99_ms": round(durations[int(n * 0.99)], 1) if n >= 100 else None,
        }

    def get_resource_usage(self) -> dict[str, Any]:
        """Get current resource usage."""
        try:
            import psutil
            proc = psutil.Process(os.getpid())
            mem = proc.memory_info()
            return {
                "cpu_percent": proc.cpu_percent(interval=0),
                "memory_rss_mb": round(mem.rss / 1024 / 1024, 1),
                "memory_vms_mb": round(mem.vms / 1024 / 1024, 1),
                "threads": proc.num_threads(),
            }
        except Exception:
            return {}

    def get_gpu_usage(self) -> dict[str, Any]:
        """Get GPU usage if available."""
        try:
            import torch
            if torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated() / 1024 / 1024
                reserved = torch.cuda.memory_reserved() / 1024 / 1024
                return {
                    "gpu_memory_allocated_mb": round(allocated, 1),
                    "gpu_memory_reserved_mb": round(reserved, 1),
                    "gpu_device": torch.cuda.get_device_name(0),
                }
        except Exception:
            pass
        return {}

    # ── Snapshot ───────────────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """Full metrics snapshot for diagnostics."""
        return {
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "total_turns": self._turn_count,
            "total_errors": self._error_count,
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "stages": {
                stage: self.get_stage_stats(stage)
                for stage in self._timings
            },
            "resources": self.get_resource_usage(),
            "gpu": self.get_gpu_usage(),
        }


# Global metrics instance — created once, never destroyed.
pipeline_metrics = PipelineMetrics()
