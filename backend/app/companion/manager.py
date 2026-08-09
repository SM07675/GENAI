"""CompanionManager — lifecycle controller for Companion Mode.

Implements the orthogonal top-level toggle described in the spec (§3):
  CompanionMode: OFF → STARTING → ACTIVE → PAUSED → STOPPING → OFF
  ActiveSubMode (only while ACTIVE): GENERAL | GAMING | CODING | WRITING | QUIET

Key invariants
--------------
* Companion Mode is an orthogonal layer over the existing EngineState machine —
  it does NOT control or replace the base voice pipeline state machine.
* stop() guarantees zero orphaned background tasks or timers.
* Any companion subsystem failure degrades to "companion feature degrades",
  never to "Genie stops responding to normal commands".
* Speech output routes through the existing engine_events bus →
  TTSStreamWorker priority queue.  No second speech queue.
"""
from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Any, Awaitable, Callable, Optional

import structlog

from ..config import get_settings
from .personality import PersonalityConfig, DEFAULT_PERSONALITY, PRESETS

log = structlog.get_logger("genie.companion.manager")

Emitter = Callable[[dict], Awaitable[None]]


class CompanionMode(str, Enum):
    OFF = "off"
    STARTING = "starting"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPING = "stopping"


class CompanionSubMode(str, Enum):
    GENERAL = "general"
    GAMING = "gaming"
    CODING = "coding"
    WRITING = "writing"
    QUIET = "quiet"


# App-category → sub-mode heuristic (Win32 process names)
_APP_TO_SUBMODE: dict[str, CompanionSubMode] = {
    # Games (common launchers/engines)
    "GameBar": CompanionSubMode.GAMING,
    "EpicGamesLauncher": CompanionSubMode.GAMING,
    "steam": CompanionSubMode.GAMING,
    "RiotClientServices": CompanionSubMode.GAMING,
    "Minecraft.Windows": CompanionSubMode.GAMING,
    # IDEs / editors
    "Code": CompanionSubMode.CODING,
    "code": CompanionSubMode.CODING,
    "devenv": CompanionSubMode.CODING,
    "idea64": CompanionSubMode.CODING,
    "pycharm64": CompanionSubMode.CODING,
    "WindowsTerminal": CompanionSubMode.CODING,
    "powershell": CompanionSubMode.CODING,
    "cmd": CompanionSubMode.CODING,
    "jupyter": CompanionSubMode.CODING,
    # Writing
    "WINWORD": CompanionSubMode.WRITING,
    "notepad": CompanionSubMode.WRITING,
    "Typora": CompanionSubMode.WRITING,
    "Obsidian": CompanionSubMode.WRITING,
}


class CompanionManager:
    """Singleton lifecycle controller for Genie Companion Mode.

    Created once at startup.  Never destroyed.  The start/stop/pause/resume
    methods are safe to call from any coroutine.
    """

    def __init__(self) -> None:
        self._mode: CompanionMode = CompanionMode.OFF
        self._sub_mode: CompanionSubMode = CompanionSubMode.GENERAL
        self._personality: PersonalityConfig = DEFAULT_PERSONALITY

        # Emitter — set when a WebSocket session is active
        self._emit: Emitter = _noop_emit

        # Background task handles — all cancelled on stop()
        self._tasks: list[asyncio.Task] = []

        # Lazy-imported subsystems (avoid import cost when companion is off)
        self._context_engine: Any = None
        self._observation_loop: Any = None

        self._settings = get_settings()
        self._started_at: Optional[float] = None
        self._lock = asyncio.Lock()

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def mode(self) -> CompanionMode:
        return self._mode

    @property
    def sub_mode(self) -> CompanionSubMode:
        return self._sub_mode

    @property
    def personality(self) -> PersonalityConfig:
        return self._personality

    @property
    def is_active(self) -> bool:
        return self._mode == CompanionMode.ACTIVE

    def set_emit(self, emit: Emitter) -> None:
        """Bind the current WebSocket emitter."""
        self._emit = emit
        if hasattr(self, "_observation_loop") and self._observation_loop:
            self._observation_loop.set_emit(emit)

    async def quick_look(self, question: Optional[str] = None) -> str:
        """Execute stateless Quick Look request ("Look & Answer" fast path)."""
        from .quick_look import QuickLookEngine
        engine = QuickLookEngine(emit=self._emit, settings=self._settings)
        return await engine.execute(
            question=question,
            mode=self._sub_mode.value if self._mode == CompanionMode.ACTIVE else "general",
            context_engine=self._context_engine,
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(
        self,
        sub_mode: CompanionSubMode = CompanionSubMode.GENERAL,
        personality_preset: str = "default",
    ) -> None:
        """Activate companion mode.  Safe to call while already ACTIVE (changes sub_mode)."""
        async with self._lock:
            if self._mode == CompanionMode.STOPPING:
                log.warning("companion_start_blocked_stopping")
                return

            prev_mode = self._mode
            self._mode = CompanionMode.STARTING
            self._sub_mode = sub_mode
            self._personality = PRESETS.get(personality_preset, DEFAULT_PERSONALITY)

        log.info("companion_starting", sub_mode=sub_mode.value, prev=prev_mode.value)

        try:
            # Sequence per spec §15: UI show → Context Engine → Screen Awareness
            # → Vision → Event Manager → Companion Brain
            await self._emit({
                "type": "companion_state",
                "mode": CompanionMode.STARTING.value,
                "sub_mode": sub_mode.value,
                "screen_aware": False,
                "voice_active": True,
            })
            await self._emit({
                "type": "companion_overlay",
                "overlay": "WATCHING",
                "intensity": self._personality.orb_intensity(),
            })

            # Lazy-import to avoid startup cost when companion is off
            from .context_engine import ContextEngine
            from .observation_loop import ObservationLoop

            if self._context_engine is None:
                self._context_engine = ContextEngine(settings=self._settings)

            if self._observation_loop is None:
                self._observation_loop = ObservationLoop(
                    context_engine=self._context_engine,
                    emit=self._emit,
                    settings=self._settings,
                )

            self._observation_loop.set_sub_mode(sub_mode)
            self._observation_loop.set_personality(self._personality)

            # Start observation as background task (non-blocking)
            obs_task = asyncio.create_task(
                self._observation_loop.run(),
                name="companion_observation",
            )
            self._tasks.append(obs_task)

            async with self._lock:
                self._mode = CompanionMode.ACTIVE
                self._started_at = time.monotonic()

            await self._emit({
                "type": "companion_state",
                "mode": CompanionMode.ACTIVE.value,
                "sub_mode": sub_mode.value,
                "screen_aware": self._settings.companion_vision_enabled,
                "voice_active": True,
            })
            await self._emit({
                "type": "companion_privacy",
                "screen_aware": self._settings.companion_vision_enabled,
                "mic_active": True,
            })

            log.info("companion_active", sub_mode=sub_mode.value)

        except Exception as exc:
            log.error("companion_start_failed", error=str(exc))
            await self._cleanup_tasks()
            async with self._lock:
                self._mode = CompanionMode.OFF
            await self._emit({
                "type": "companion_state",
                "mode": CompanionMode.OFF.value,
                "sub_mode": self._sub_mode.value,
                "screen_aware": False,
                "voice_active": False,
            })

    async def stop(self) -> None:
        """Deactivate companion mode.  Reverses start() cleanly with zero orphaned tasks."""
        async with self._lock:
            if self._mode == CompanionMode.OFF:
                return
            prev = self._mode
            self._mode = CompanionMode.STOPPING

        log.info("companion_stopping", prev=prev.value)

        await self._cleanup_tasks()

        async with self._lock:
            self._mode = CompanionMode.OFF
            self._started_at = None

        await self._emit({
            "type": "companion_state",
            "mode": CompanionMode.OFF.value,
            "sub_mode": self._sub_mode.value,
            "screen_aware": False,
            "voice_active": False,
        })
        await self._emit({
            "type": "companion_overlay",
            "overlay": "NONE",
        })
        await self._emit({
            "type": "companion_privacy",
            "screen_aware": False,
            "mic_active": False,
        })

        log.info("companion_stopped")

    async def pause(self) -> None:
        """Pause observation (overlays freeze; base orb state machine keeps running)."""
        async with self._lock:
            if self._mode != CompanionMode.ACTIVE:
                return
            self._mode = CompanionMode.PAUSED

        if self._observation_loop:
            self._observation_loop.pause()

        await self._emit({
            "type": "companion_state",
            "mode": CompanionMode.PAUSED.value,
            "sub_mode": self._sub_mode.value,
            "screen_aware": False,
            "voice_active": False,
        })
        await self._emit({
            "type": "companion_overlay",
            "overlay": "PAUSED",
            "intensity": 0.3,
        })
        await self._emit({
            "type": "companion_privacy",
            "screen_aware": False,
            "mic_active": False,
        })
        log.info("companion_paused")

    async def resume(self) -> None:
        """Resume from PAUSED state."""
        async with self._lock:
            if self._mode != CompanionMode.PAUSED:
                return
            self._mode = CompanionMode.ACTIVE

        if self._observation_loop:
            self._observation_loop.resume()

        await self._emit({
            "type": "companion_state",
            "mode": CompanionMode.ACTIVE.value,
            "sub_mode": self._sub_mode.value,
            "screen_aware": self._settings.companion_vision_enabled,
            "voice_active": True,
        })
        await self._emit({
            "type": "companion_overlay",
            "overlay": "WATCHING",
            "intensity": self._personality.orb_intensity(),
        })
        await self._emit({
            "type": "companion_privacy",
            "screen_aware": self._settings.companion_vision_enabled,
            "mic_active": True,
        })
        log.info("companion_resumed")

    async def set_mode(self, sub_mode: CompanionSubMode) -> None:
        """Change sub-mode while ACTIVE (e.g. user switches from coding to gaming)."""
        if self._mode != CompanionMode.ACTIVE:
            return
        self._sub_mode = sub_mode
        if self._observation_loop:
            self._observation_loop.set_sub_mode(sub_mode)
        await self._emit({
            "type": "companion_state",
            "mode": CompanionMode.ACTIVE.value,
            "sub_mode": sub_mode.value,
            "screen_aware": self._settings.companion_vision_enabled,
            "voice_active": True,
        })
        log.info("companion_mode_changed", sub_mode=sub_mode.value)

    def infer_sub_mode_from_app(self, process_name: str) -> CompanionSubMode:
        """Heuristically infer sub-mode from the active Win32 process name."""
        for key, sub in _APP_TO_SUBMODE.items():
            if key.lower() in process_name.lower():
                return sub
        return CompanionSubMode.GENERAL

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _cleanup_tasks(self) -> None:
        """Cancel and await all background companion tasks — zero orphans guaranteed."""
        if self._observation_loop:
            self._observation_loop.stop()

        for task in self._tasks:
            if not task.done():
                task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self._tasks.clear()
        log.debug("companion_tasks_cleaned")

    def snapshot(self) -> dict:
        """Diagnostic snapshot for /health endpoint."""
        return {
            "mode": self._mode.value,
            "sub_mode": self._sub_mode.value,
            "uptime_seconds": (
                round(time.monotonic() - self._started_at, 1)
                if self._started_at else 0
            ),
            "active_tasks": len(self._tasks),
        }


async def _noop_emit(msg: dict) -> None:
    pass


# ── Module-level singleton ─────────────────────────────────────────────────────
companion_manager = CompanionManager()
