"""CompanionBrain — the conscious decision layer for Companion Mode.

This is the single most important module in Companion Mode (per spec §8).
It implements the AIRI reflex→conscious split:
  - Context Diff already filtered 95% of noise (reflex layer, no LLM).
  - CompanionBrain only runs on what's left, and IGNORE is still the
    most common output — checked with rule-based gates BEFORE any LLM call.

Critical rule (enforced in code)
---------------------------------
IGNORE path: rule-based only. Zero LLM calls.
COMMENT/HELP/WARN/etc. path: LLM called only AFTER all gates pass.

Gates (checked in order, cheapest first)
-----------------------------------------
1. Importance threshold × personality talkativeness
2. Cooldown (global + per-event-type)
3. Duplicate detection (is last_companion_response similar to what we'd say?)
4. User activity gate (coding: don't interrupt active typing)
5. Confidence threshold
Only then: LLM call for tone/phrasing.

Output
------
{ decision: IGNORE|COMMENT|HELP|WARN|SUGGEST|ASK|CELEBRATE|COACH,
  priority: 1-10, tone: str, reason: str }

Speech is submitted via engine_events (the existing event bus) into the
existing TTSStreamWorker priority queue. No second speech queue.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

import structlog

from ..config import Settings, get_settings
from .context_engine import ContextState
from .events import CompanionEvent, EventType
from .personality import PersonalityConfig, DEFAULT_PERSONALITY

log = structlog.get_logger("genie.companion.brain")

Emitter = Callable[[dict], Awaitable[None]]

# ── Tone presets by event type ────────────────────────────────────────────────
_EVENT_TONE: dict[EventType, str] = {
    EventType.ENEMY_DETECTED: "urgent_hype",
    EventType.MULTIPLE_ENEMIES: "urgent_hype",
    EventType.PLAYER_KILL: "celebratory",
    EventType.PLAYER_DEATH: "empathetic",
    EventType.LOW_HEALTH: "urgent_warning",
    EventType.BOSS_DETECTED: "dramatic_hype",
    EventType.CLUTCH: "ecstatic",
    EventType.ROUND_WIN: "celebratory",
    EventType.ROUND_LOSS: "empathetic",
    EventType.CODE_ERROR: "helpful_calm",
    EventType.RUNTIME_ERROR: "helpful_calm",
    EventType.BUILD_FAILURE: "helpful_calm",
    EventType.REPEATED_ERROR: "coaching",
    EventType.CODE_FIXED: "celebrating_quietly",
    EventType.TEST_SUCCESS: "warm_approval",
    EventType.SPELLING_ERROR: "gentle_correction",
    EventType.GRAMMAR_ERROR: "gentle_correction",
    EventType.TYPO: "tiny_nudge",
}

# ── Cooldown map: how long (seconds) between same-type comments ───────────────
_EVENT_COOLDOWNS: dict[EventType, float] = {
    EventType.ENEMY_DETECTED: 8.0,
    EventType.MULTIPLE_ENEMIES: 6.0,
    EventType.PLAYER_KILL: 5.0,
    EventType.PLAYER_DEATH: 10.0,
    EventType.LOW_HEALTH: 12.0,
    EventType.BOSS_DETECTED: 15.0,
    EventType.CLUTCH: 3.0,
    EventType.ROUND_WIN: 5.0,
    EventType.ROUND_LOSS: 8.0,
    EventType.CODE_ERROR: 15.0,
    EventType.RUNTIME_ERROR: 15.0,
    EventType.BUILD_FAILURE: 20.0,
    EventType.REPEATED_ERROR: 30.0,
    EventType.CODE_FIXED: 10.0,
    EventType.SPELLING_ERROR: 20.0,
    EventType.GRAMMAR_ERROR: 20.0,
    EventType.TYPO: 30.0,
    EventType.APP_CHANGED: 5.0,
}

_DEFAULT_COOLDOWN = 10.0
_GLOBAL_COOLDOWN = 4.0   # minimum seconds between ANY companion speech


@dataclass
class BrainDecision:
    decision: str       # IGNORE | COMMENT | HELP | WARN | SUGGEST | CELEBRATE | COACH
    priority: int = 5   # 1-10 (higher = more urgent, interrupts lower priority)
    tone: str = "neutral"
    reason: str = ""
    line: Optional[str] = None  # the generated speech line (None if IGNORE)


class CompanionBrain:
    """Conscious decision layer — runs only on events that passed the reflex filter.

    Created once per CompanionManager lifetime.
    """

    def __init__(
        self,
        emit: Emitter,
        settings: Optional[Settings] = None,
    ) -> None:
        self._emit = emit
        self._settings = settings or get_settings()
        self._personality = DEFAULT_PERSONALITY
        self._last_spoke_at: float = 0.0
        self._last_spoke_type: dict[str, float] = {}  # event_type → timestamp
        self._recent_lines: list[str] = []            # for duplicate detection
        self._session_lines: set[str] = set()         # exact duplicates guard

    def set_personality(self, personality: PersonalityConfig) -> None:
        self._personality = personality

    def set_emit(self, emit: Emitter) -> None:
        self._emit = emit

    # ── Main entry point ──────────────────────────────────────────────────────

    async def process_event(
        self,
        event: CompanionEvent,
        context: Optional[ContextState] = None,
    ) -> BrainDecision:
        """Decide what to do with a CompanionEvent.

        Gates are checked cheapest-first. IGNORE path: no LLM call.
        Only COMMENT/HELP/etc. paths call the LLM for phrasing.
        """

        # Gate 1: importance × talkativeness
        if not self._personality.speaks_for_importance(event.importance):
            return BrainDecision(
                decision="IGNORE",
                reason=f"importance_{event.importance}_below_talkativeness_threshold",
            )

        # Gate 2: global cooldown
        time_since_last = time.time() - self._last_spoke_at
        if time_since_last < _GLOBAL_COOLDOWN:
            return BrainDecision(
                decision="IGNORE",
                reason=f"global_cooldown_{_GLOBAL_COOLDOWN:.0f}s",
            )

        # Gate 3: per-event-type cooldown
        event_cooldown = _EVENT_COOLDOWNS.get(event.event_type, _DEFAULT_COOLDOWN)
        last_for_type = self._last_spoke_type.get(event.event_type.value, 0.0)
        if time.time() - last_for_type < event_cooldown:
            return BrainDecision(
                decision="IGNORE",
                reason=f"event_cooldown_{event.event_type.value}",
            )

        # Gate 4: confidence threshold
        if event.confidence < 0.6:
            return BrainDecision(
                decision="IGNORE",
                reason=f"confidence_too_low_{event.confidence:.2f}",
            )

        # Gate 5: user typing activity (coding gate — never interrupt active typing)
        if event.mode == "coding" and context and context.is_user_actively_typing(window_seconds=4.0):
            return BrainDecision(
                decision="IGNORE",
                reason="user_actively_typing",
            )

        # Gate 6: low-importance writing corrections only if confidence is high
        if event.mode == "writing" and event.importance == "low" and event.confidence < 0.85:
            return BrainDecision(
                decision="IGNORE",
                reason="writing_correction_low_confidence",
            )

        # ── All gates passed — determine decision type ─────────────────────────
        decision_type, priority = self._classify_decision(event)

        # ── Call LLM for phrasing (only when not IGNORE) ──────────────────────
        line = await self._generate_line(event, context, decision_type)
        if not line:
            return BrainDecision(decision="IGNORE", reason="empty_line_generated")

        # Gate 7: exact-duplicate guard (LLM generates variations, but just in case)
        if line in self._session_lines:
            return BrainDecision(decision="IGNORE", reason="duplicate_line")

        tone = _EVENT_TONE.get(event.event_type, "neutral")

        # Record state
        now = time.time()
        self._last_spoke_at = now
        self._last_spoke_type[event.event_type.value] = now
        self._recent_lines = (self._recent_lines + [line])[-20:]
        self._session_lines.add(line)

        # Submit to frontend for companion overlay
        await self._emit({
            "type": "companion_event",
            "event_type": event.event_type.value,
            "importance": event.importance,
            "payload": event.metadata,
        })

        # Emit overlay based on event type
        overlay = _event_to_overlay(event.event_type)
        if overlay:
            await self._emit({
                "type": "companion_overlay",
                "overlay": overlay,
                "intensity": self._personality.orb_intensity(
                    0.6 if event.importance == "critical" else 0.4
                ),
            })

        # Submit line to TTS via engine_events (the shared Interruption Manager)
        await self._submit_to_tts(line, priority=priority)

        log.info(
            "companion_brain_speaking",
            event=event.event_type.value,
            decision=decision_type,
            priority=priority,
            line_length=len(line),
        )

        return BrainDecision(
            decision=decision_type,
            priority=priority,
            tone=tone,
            reason=event.event_type.value,
            line=line,
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _classify_decision(self, event: CompanionEvent) -> tuple[str, int]:
        """Rule-based: classify decision type and priority without LLM."""
        etype = event.event_type
        imp = event.importance

        if etype in (EventType.LOW_HEALTH, EventType.MULTIPLE_ENEMIES, EventType.BOSS_DETECTED):
            return "WARN", 9
        if etype in (EventType.ENEMY_DETECTED,):
            return "WARN", 8
        if etype in (EventType.PLAYER_DEATH, EventType.ROUND_LOSS):
            return "COMMENT", 6
        if etype in (EventType.PLAYER_KILL, EventType.CLUTCH, EventType.ROUND_WIN):
            return "CELEBRATE", 7
        if etype in (EventType.REPEATED_ERROR,):
            return "COACH", 7
        if etype in (EventType.CODE_ERROR, EventType.RUNTIME_ERROR,
                     EventType.BUILD_FAILURE, EventType.TEST_FAILURE):
            return "HELP", 6
        if etype in (EventType.CODE_FIXED, EventType.TEST_SUCCESS):
            return "CELEBRATE", 4
        if etype in (EventType.SPELLING_ERROR, EventType.GRAMMAR_ERROR, EventType.TYPO):
            return "SUGGEST", 3
        if imp == "critical":
            return "WARN", 10
        if imp == "high":
            return "COMMENT", 7
        return "COMMENT", 4

    async def _generate_line(
        self,
        event: CompanionEvent,
        context: Optional[ContextState],
        decision_type: str,
    ) -> Optional[str]:
        """Call the existing LLM to generate a natural, varied companion line.

        Uses the existing llm_client infrastructure — no second LLM path.
        """
        try:
            from ..llm_client import create_client, get_provider_config
            settings = self._settings
            provider_config = get_provider_config(settings)
            client = create_client(provider_config)

            persona_modifier = self._personality.to_prompt_modifier()
            app_name = (context.application.process_name_stem if context else "app")
            window_title = (context.application.window_title[:80] if context else "")

            system = (
                f"You are Genie, a proactive AI companion sitting beside the user. "
                f"{persona_modifier} "
                f"React to what's happening on screen with a SHORT (max 2 sentences), "
                f"natural, VARIED response. Never say the same thing twice. "
                f"Do NOT use emoji. Do NOT use markdown. Speak conversationally."
            )

            recent = ", ".join(self._recent_lines[-3:]) if self._recent_lines else "none"
            user_msg = (
                f"Event: {event.event_type.value}\n"
                f"Mode: {event.mode}\n"
                f"Decision: {decision_type}\n"
                f"App: {app_name} ({window_title})\n"
                f"Details: {event.metadata}\n"
                f"Recent things I said: {recent}\n"
                f"Generate one short natural companion reaction (different from recent). "
                f"Output only the spoken line, nothing else."
            )

            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._call_llm_sync,
                    client,
                    system,
                    user_msg,
                    settings,
                ),
                timeout=10.0,
            )
            line = (response or "").strip()
            # Strip any cue tags the LLM might add
            import re
            line = re.sub(r'\[\[.*?\]\]', '', line).strip()
            return line if line else None

        except asyncio.TimeoutError:
            log.warning("companion_brain_llm_timeout")
            return None
        except Exception as exc:
            log.warning("companion_brain_llm_error", error=str(exc))
            return None

    @staticmethod
    def _call_llm_sync(client: Any, system: str, user_msg: str, settings: Any) -> str:
        """Synchronous LLM call — runs in a thread via asyncio.to_thread."""
        response = client.chat.completions.create(
            model=settings.nvidia_model if settings.llm_provider == "nvidia" else getattr(settings, f"{settings.llm_provider}_model", ""),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=120,
            temperature=0.9,  # high temperature for natural variation
        )
        return response.choices[0].message.content or ""

    async def _submit_to_tts(self, line: str, priority: int = 5) -> None:
        """Submit the companion line to the existing TTS pipeline.

        Routes through engine_events (the existing event bus) so it lands in
        the TTSStreamWorker priority queue — no second speech queue.
        """
        try:
            from ..engine.event_bus import engine_events, PipelineEvent
            # Emit a companion_speech event — pipeline.py listens and
            # forwards high-priority lines to TTSStreamWorker.
            engine_events.emit(PipelineEvent.COMPANION_SPEECH, {
                "text": line,
                "priority": priority,
            })
            log.debug("companion_speech_submitted", priority=priority, length=len(line))
        except Exception as exc:
            # Speech submission failure must not crash the companion or base Genie
            log.warning("companion_speech_submit_error", error=str(exc))


def _event_to_overlay(event_type: EventType) -> Optional[str]:
    """Map event type to companion orb overlay state."""
    mapping = {
        EventType.PLAYER_KILL: "EXCITED",
        EventType.CLUTCH: "EXCITED",
        EventType.ROUND_WIN: "HAPPY",
        EventType.PLAYER_DEATH: "SAD",
        EventType.ROUND_LOSS: "SAD",
        EventType.ENEMY_DETECTED: "WARNING",
        EventType.MULTIPLE_ENEMIES: "WARNING",
        EventType.LOW_HEALTH: "WARNING",
        EventType.BOSS_DETECTED: "WARNING",
        EventType.CODE_FIXED: "HAPPY",
        EventType.TEST_SUCCESS: "HAPPY",
        EventType.CODE_ERROR: "WATCHING",
        EventType.REPEATED_ERROR: "WATCHING",
    }
    return mapping.get(event_type)
