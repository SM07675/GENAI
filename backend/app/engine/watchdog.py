"""Watchdog service — heartbeat-based worker monitoring.

Design:
- Every worker sends heartbeat every ~1 second (via frame processing).
- Watchdog checks heartbeats every 5 seconds.
- If heartbeat missing for >10s: logs the incident.
- If heartbeat missing for >30s: requests pipeline restart for that worker.
- State-aware: different timeouts for different states.
- All incidents logged with structured logging.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Optional

import structlog

from .state_machine import ConversationStateMachine, EngineState
from .metrics import pipeline_metrics

log = structlog.get_logger("genie.engine.watchdog")


class WorkerInfo:
    """Tracked information about a single worker."""

    __slots__ = ("name", "heartbeat_fn", "warn_timeout", "restart_timeout", "last_warning")

    def __init__(
        self,
        name: str,
        heartbeat_fn: Callable[[], float],
        warn_timeout: float = 10.0,
        restart_timeout: float = 30.0,
    ):
        self.name = name
        self.heartbeat_fn = heartbeat_fn
        self.warn_timeout = warn_timeout
        self.restart_timeout = restart_timeout
        self.last_warning: float = 0.0


class PipelineWatchdog:
    """Monitors all pipeline workers via heartbeats.

    Started as an async task by the pipeline supervisor. Checks worker
    heartbeats periodically and logs warnings or requests restarts
    when workers appear to be stuck.
    """

    def __init__(
        self,
        state_machine: ConversationStateMachine,
        check_interval: float = 5.0,
        on_worker_stuck: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        self._sm = state_machine
        self._check_interval = check_interval
        self._on_worker_stuck = on_worker_stuck
        self._workers: list[WorkerInfo] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def register_worker(
        self,
        name: str,
        heartbeat_fn: Callable[[], float],
        warn_timeout: float = 10.0,
        restart_timeout: float = 30.0,
    ) -> None:
        """Register a worker for monitoring."""
        self._workers.append(WorkerInfo(name, heartbeat_fn, warn_timeout, restart_timeout))

    async def start(self) -> None:
        """Start the watchdog loop."""
        self._running = True
        self._task = asyncio.create_task(self._run())
        log.info("watchdog_started", workers=[w.name for w in self._workers])

    async def stop(self) -> None:
        """Stop the watchdog."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        log.info("watchdog_stopped")

    async def _run(self) -> None:
        """Main watchdog loop."""
        while self._running:
            try:
                await asyncio.sleep(self._check_interval)
                await self._check_all_workers()
                await self._check_state_timeout()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error("watchdog_error", error=str(exc))
                await asyncio.sleep(5.0)

    async def _check_all_workers(self) -> None:
        """Check heartbeats of all registered workers."""
        now = time.time()

        for worker in self._workers:
            try:
                last_heartbeat = worker.heartbeat_fn()
            except Exception:
                continue

            elapsed = now - last_heartbeat

            if elapsed > worker.restart_timeout:
                # Worker appears stuck
                if now - worker.last_warning > 30.0:  # don't spam logs
                    log.error(
                        "worker_stuck",
                        worker=worker.name,
                        elapsed_seconds=round(elapsed, 1),
                        state=self._sm.state.value,
                    )
                    pipeline_metrics.increment(f"watchdog.stuck.{worker.name}")
                    worker.last_warning = now

                    if self._on_worker_stuck:
                        try:
                            await self._on_worker_stuck(worker.name)
                        except Exception as e:
                            log.error("watchdog_recovery_error", worker=worker.name, error=str(e))

            elif elapsed > worker.warn_timeout:
                if now - worker.last_warning > 30.0:
                    log.warning(
                        "worker_slow",
                        worker=worker.name,
                        elapsed_seconds=round(elapsed, 1),
                        state=self._sm.state.value,
                    )
                    pipeline_metrics.increment(f"watchdog.slow.{worker.name}")
                    worker.last_warning = now

    async def _check_state_timeout(self) -> None:
        """Check if the state machine has been in one state too long."""
        timeout = self._sm.get_state_timeout()
        if timeout is None:
            return

        time_in_state = self._sm.time_in_state
        if time_in_state > timeout:
            current = self._sm.state
            log.error(
                "state_timeout",
                state=current.value,
                time_in_state=round(time_in_state, 1),
                timeout=timeout,
            )
            pipeline_metrics.increment("watchdog.state_timeouts")

            # Force recovery based on current state
            if current in (EngineState.LISTENING, EngineState.UNDERSTANDING,
                          EngineState.THINKING, EngineState.STREAMING_RESPONSE,
                          EngineState.SPEAKING):
                log.warning("state_timeout_recovery", from_state=current.value)
                await self._sm.force_transition(
                    EngineState.WAIT_WAKE,
                    reason=f"watchdog_timeout_{current.value}",
                )
            elif current == EngineState.RETURN_TO_LISTENING:
                await self._sm.force_transition(
                    EngineState.WAIT_WAKE,
                    reason="watchdog_timeout_return_to_listening",
                )
