"""QuickLookEngine — Stateless, fast-path out-of-band screen question execution.

Implements real-time "Look & Answer" per spec §5:
  - Collapses vision capture + reasoning into a single direct combined call.
  - Bypasses ambient observation intervals and rate limits (uses reserved quota).
  - Immediately signals THINKING overlay within 0-300ms.
  - Streams answer into speech and suggestion bubble simultaneously.
  - Logs event into ContextEngine so ambient loop doesn't re-detect/re-comment.
  - Independent of CompanionMode lifecycle (works whether companion is OFF or ACTIVE).
"""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Optional

import structlog

from ..config import Settings, get_settings
from .capture import screen_capture
from .vision import VisionService

log = structlog.get_logger("genie.companion.quick_look")

Emitter = Callable[[dict], Awaitable[None]]


class QuickLookEngine:
    """Handles single-shot Quick Look requests."""

    def __init__(
        self,
        emit: Emitter,
        settings: Optional[Settings] = None,
    ) -> None:
        self._emit = emit
        self._settings = settings or get_settings()
        self._vision = VisionService(settings=self._settings)

    def set_emit(self, emit: Emitter) -> None:
        self._emit = emit

    async def execute(
        self,
        question: Optional[str] = None,
        mode: str = "general",
        context_engine: Optional[Any] = None,
    ) -> str:
        """Run single-shot Quick Look question."""
        user_text = (question or "").strip() or "What's on my screen right now?"
        log.info("quick_look_trigger", question=user_text, mode=mode)

        try:
            # 1. 0-300ms response: set THINKING overlay and signal privacy indicator
            await self._emit({
                "type": "companion_overlay",
                "overlay": "THINKING",
                "intensity": 0.9,
            })
            await self._emit({
                "type": "companion_privacy",
                "screen_aware": True,
                "mic_active": True,
            })
            await self._emit({
                "type": "companion_bubble",
                "text": "Analyzing your screen…",
                "action": "show",
                "typing": True,
            })

            # 2. Immediate capture (bypasses ambient scheduler and cooldown)
            app_info = screen_capture.get_active_application()
            frame_bytes = await asyncio.to_thread(screen_capture.capture_now)

            if not frame_bytes:
                answer = f"I tried to look at {app_info.process_name_stem}, but couldn't capture the screen surface right now."
            else:
                # 3. Combined vision + reasoning fast path call
                answer = await self._vision.quick_look_analyze(
                    image_bytes=frame_bytes,
                    user_question=user_text,
                    mode=mode,
                    app_info={
                        "process_name_stem": app_info.process_name_stem,
                        "category": app_info.category,
                    },
                )

            log.info("quick_look_answer_ready", answer_len=len(answer))

            # 4. Stream response to callout suggestion bubble & spoken TTS
            await self._emit({
                "type": "companion_bubble",
                "text": answer,
                "action": "show",
                "typing": True,
            })

            await self._emit({"type": "assistant_text", "delta": answer})
            await self._emit({"type": "assistant_text", "final": True})

            # 5. Log in context engine so ambient loop doesn't duplicate
            if context_engine:
                context_engine.record_companion_response(answer)
                context_engine.record_event({
                    "type": "QUICK_LOOK",
                    "question": user_text,
                    "answer": answer,
                })

            # 6. Reset overlay state
            from .manager import companion_manager
            active = companion_manager.is_active
            await self._emit({
                "type": "companion_overlay",
                "overlay": "WATCHING" if active else "NONE",
                "intensity": 0.5,
            })
            await self._emit({
                "type": "companion_privacy",
                "screen_aware": companion_manager._settings.companion_vision_enabled if active else False,
                "mic_active": True if active else False,
            })

            return answer

        except Exception as exc:
            log.warning("quick_look_error", error=str(exc))
            err_msg = "I had trouble analyzing your screen right now."
            await self._emit({"type": "companion_bubble", "text": err_msg, "action": "show"})
            await self._emit({"type": "assistant_text", "delta": err_msg})
            await self._emit({"type": "assistant_text", "final": True})
            return err_msg
