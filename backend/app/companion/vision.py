"""VisionService — API-only vision pipeline for Companion Mode.

Design (per spec §6)
---------------------
* Provider-abstract: same philosophy as llm_client.py.
  Drop in LocalVisionProvider later with zero changes to CompanionBrain.
* Vision model returns ONLY structured JSON — no natural language.
  Natural language is generated downstream by the existing LLM + TTS pipeline.
* VisionCallLimiter tracks per-minute usage and degrades interval
  automatically instead of hard-failing.
* Never persists raw screenshots anywhere.
"""
from __future__ import annotations

import asyncio
import base64
import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

import structlog

from ..config import Settings, get_settings

log = structlog.get_logger("genie.companion.vision")


# ── Structured output schema ─────────────────────────────────────────────────

@dataclass
class VisionContext:
    """Structured context returned by the vision model — no natural language."""
    scene: dict = field(default_factory=dict)   # { type, activity }
    entities: list = field(default_factory=list)  # [{ type, position, confidence }]
    events: list = field(default_factory=list)    # [{ type, importance }]
    changes: list = field(default_factory=list)   # changes since last context
    confidence: float = 0.0
    raw_description: str = ""
    error: Optional[str] = None

    @classmethod
    def empty(cls) -> "VisionContext":
        return cls(scene={"type": "unknown", "activity": "unknown"})

    @classmethod
    def error_context(cls, error: str) -> "VisionContext":
        return cls(scene={"type": "unknown", "activity": "unknown"}, error=error)


# ── Provider protocol ─────────────────────────────────────────────────────────

class VisionProvider(Protocol):
    async def analyze(
        self,
        image_bytes: bytes,
        mode: str,
        app_info: Optional[dict] = None,
    ) -> VisionContext:
        ...


# ── VisionCallLimiter ─────────────────────────────────────────────────────────

class VisionCallLimiter:
    """Tracks vision API usage; degrades gracefully instead of hard-failing.

    Per spec §13: on approaching the ceiling, observation frequency degrades
    (interval increases) — never crashes.
    """

    def __init__(self, max_calls_per_minute: int = 6) -> None:
        self._max_per_minute = max_calls_per_minute
        self._call_timestamps: list[float] = []
        self._session_calls: int = 0
        self._session_start = time.time()

    def record_call(self) -> None:
        now = time.time()
        self._call_timestamps.append(now)
        self._session_calls += 1
        # Keep only last 60s
        self._call_timestamps = [t for t in self._call_timestamps if now - t < 60]

    def calls_this_minute(self) -> int:
        now = time.time()
        self._call_timestamps = [t for t in self._call_timestamps if now - t < 60]
        return len(self._call_timestamps)

    def is_over_limit(self) -> bool:
        return self.calls_this_minute() >= self._max_per_minute

    def reserve_for_quicklook(self) -> bool:
        """Dedicated Quick Look allowance check.

        Quick Look draws from a separate reserved quota (up to 2x normal max)
        so heavy ambient observation never blocks a direct user question.
        """
        # Allow up to 15 calls/min for direct Quick Look interactions
        return self.calls_this_minute() < max(self._max_per_minute * 2, 12)

    def suggested_interval_multiplier(self) -> float:
        """Return a multiplier (>= 1.0) for the observation interval.

        When approaching limit: gradually increase interval instead of dropping calls.
        """
        usage_fraction = self.calls_this_minute() / max(self._max_per_minute, 1)
        if usage_fraction >= 0.9:
            return 3.0   # slow down significantly
        if usage_fraction >= 0.7:
            return 1.8
        if usage_fraction >= 0.5:
            return 1.3
        return 1.0

    def last_call_time(self) -> Optional[float]:
        return self._call_timestamps[-1] if self._call_timestamps else None

    def session_usage(self) -> dict:
        _VISION_SYSTEM_PROMPT = """\
You are Genie's visual perception system.

Your job is to inspect the user's current screen and extract ONLY information that is useful for a proactive AI companion.

Do not chat with the user.
Do not generate jokes.
Do not generate commentary.
Do not provide long explanations.
Do not guess uncertain information.

Identify:
1. Current application or environment
2. Current user activity
3. Important visible UI elements
4. Important visible text
5. Errors or warnings
6. Game state when applicable
7. Important entities
8. Important changes
9. Potential events
10. Confidence

Focus on information that could help Genie decide whether it should assist, comment, warn, celebrate, or remain silent.

Return ONLY a concise structured JSON object with this exact schema:

{
  "application": {
    "name": null,
    "category": null
  },
  "activity": {
    "type": null,
    "description": null
  },
  "screen_state": {
    "important_text": [],
    "errors": [],
    "warnings": []
  },
  "entities": [],
  "events": [],
  "changes": [],
  "game_state": {
    "detected": false,
    "state": null,
    "player_status": null,
    "enemies": []
  },
  "writing_state": {
    "detected": false,
    "possible_errors": []
  },
  "coding_state": {
    "detected": false,
    "language": null,
    "errors": [],
    "warnings": []
  },
  "confidence": 0.0
}

If something cannot be determined confidently, return null or an empty list.
Never invent information.
"""

        return {
            "session_calls": self._session_calls,
            "calls_this_minute": self.calls_this_minute(),
            "limit_per_minute": self._max_per_minute,
            "session_uptime_seconds": round(time.time() - self._session_start),
        }


# ── API Vision Provider ───────────────────────────────────────────────────────

_VISION_SYSTEM_PROMPT = """\
You are Genie's visual perception system.

Your job is to inspect the user's current screen and extract ONLY information that is useful for a proactive AI companion.

Do not chat with the user.
Do not generate jokes.
Do not generate commentary.
Do not provide long explanations.
Do not guess uncertain information.

Identify:
1. Current application or environment
2. Current user activity
3. Important visible UI elements
4. Important visible text
5. Errors or warnings
6. Game state when applicable
7. Important entities
8. Important changes
9. Potential events
10. Confidence

Focus on information that could help Genie decide whether it should assist, comment, warn, celebrate, or remain silent.

Return ONLY a concise structured JSON object with this exact schema:

{
  "application": {
    "name": null,
    "category": null
  },
  "activity": {
    "type": null,
    "description": null
  },
  "screen_state": {
    "important_text": [],
    "errors": [],
    "warnings": []
  },
  "entities": [],
  "events": [],
  "changes": [],
  "game_state": {
    "detected": false,
    "state": null,
    "player_status": null,
    "enemies": []
  },
  "writing_state": {
    "detected": false,
    "possible_errors": []
  },
  "coding_state": {
    "detected": false,
    "language": null,
    "errors": [],
    "warnings": []
  },
  "confidence": 0.0
}

If something cannot be determined confidently, return null or an empty list.
Never invent information.
"""

_VISION_USER_PROMPT_TEMPLATE = """\
/no_think
Analyze this screenshot. Context: mode={mode}, active_app={app}.
Return the JSON structure only.
"""


class APIVisionProvider:
    """Vision via existing LLM providers that support image input.

    Uses the configured vision provider from settings (default: Nemotron 12B v2 VL via NVIDIA).
    Falls back gracefully if the API fails.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._limiter = VisionCallLimiter(
            max_calls_per_minute=self._settings.companion_max_vision_calls_per_minute
        )
        self._client: Any = None
        self._use_openai_format: bool = False
        self._last_logged_error: Optional[str] = None

    def _get_client(self) -> Any:
        """Lazy-initialize the vision API client."""
        if self._client is not None:
            return self._client

        provider = self._settings.companion_vision_provider
        if provider == "gemini":
            # First try native google.generativeai package if available
            try:
                import google.generativeai as genai
                if self._settings.gemini_api_key:
                    genai.configure(api_key=self._settings.gemini_api_key)
                    self._client = genai.GenerativeModel(self._settings.companion_vision_model)
                    return self._client
            except ImportError:
                pass

            # Fall back to OpenAI-compatible endpoint for Gemini (uses standard 'openai' package)
            try:
                from openai import AsyncOpenAI
                api_key = self._settings.gemini_api_key or self._settings.openrouter_api_key or "missing_key"
                base_url = self._settings.gemini_base_url
                self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
                self._use_openai_format = True
                return self._client
            except ImportError:
                return None

        elif provider in ("openai", "nvidia", "openrouter"):
            # OpenAI-compatible vision via standard AsyncOpenAI client
            try:
                from openai import AsyncOpenAI
                if provider == "openai":
                    api_key = self._settings.companion_vision_api_key or self._settings.openai_api_key
                    base_url = None
                elif provider == "nvidia":
                    api_key = self._settings.companion_vision_api_key or self._settings.nvidia_api_key
                    base_url = self._settings.nvidia_base_url
                else:
                    api_key = self._settings.companion_vision_api_key or self._settings.openrouter_api_key
                    base_url = self._settings.openrouter_base_url

                self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
                self._use_openai_format = True
                return self._client
            except ImportError:
                return None
        return None

    async def analyze(
        self,
        image_bytes: bytes,
        mode: str = "general",
        app_info: Optional[dict] = None,
    ) -> VisionContext:
        """Analyze a screenshot and return structured context.

        Never returns natural language — only the structured JSON schema above.
        """
        if self._limiter.is_over_limit():
            if self._last_logged_error != "rate_limit":
                log.warning("vision_rate_limit_exceeded", usage=self._limiter.session_usage())
                self._last_logged_error = "rate_limit"
            return VisionContext.empty()

        app_str = (app_info or {}).get("process_name_stem", "unknown")
        user_prompt = _VISION_USER_PROMPT_TEMPLATE.format(mode=mode, app=app_str)

        try:
            raw_text = await asyncio.wait_for(
                self._call_vision_api(image_bytes, user_prompt),
                timeout=15.0,
            )
            self._limiter.record_call()
            self._last_logged_error = None
            ctx = self._parse_response(raw_text)

            # Section 16: Confidence Thresholding (confidence < threshold -> ignore high priority events)
            threshold = getattr(self._settings, "companion_vision_confidence_threshold", 0.65)
            if ctx.confidence < threshold:
                ctx.events = [e for e in ctx.events if isinstance(e, dict) and e.get("importance") not in ("high", "critical")]

            return ctx

        except asyncio.TimeoutError:
            if self._last_logged_error != "timeout":
                log.warning("vision_api_timeout")
                self._last_logged_error = "timeout"
            return VisionContext.error_context("timeout")
        except Exception as exc:
            err_msg = str(exc)
            if self._last_logged_error != err_msg:
                log.warning("vision_api_error", error=err_msg)
                self._last_logged_error = err_msg
            return VisionContext.error_context(err_msg)

    async def _call_vision_api(
        self,
        image_bytes: bytes,
        user_prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Make the actual API call. Provider-specific logic here.

        system_prompt: if None, defaults to _VISION_SYSTEM_PROMPT (structured
        ambient extraction). Pass "" for Quick Look (conversational answer).
        """
        client = self._get_client()
        if client is None:
            raise RuntimeError("Vision client unavailable (missing API key or client package)")

        effective_system = _VISION_SYSTEM_PROMPT if system_prompt is None else system_prompt

        if self._use_openai_format or self._settings.companion_vision_provider != "gemini":
            return await self._call_openai_compatible(
                image_bytes, user_prompt, system_prompt=effective_system
            )
        else:
            try:
                return await self._call_gemini(image_bytes, user_prompt)
            except Exception:
                return await self._call_openai_compatible(
                    image_bytes, user_prompt, system_prompt=effective_system
                )


    async def _call_gemini(self, image_bytes: bytes, user_prompt: str) -> str:
        import google.generativeai as genai
        client = self._get_client()
        if client is None:
            raise RuntimeError("Gemini client unavailable")

        # Convert to PIL Image for Gemini
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(image_bytes))
        except ImportError:
            raise RuntimeError("Pillow not installed; pip install Pillow")

        response = await asyncio.to_thread(
            client.generate_content,
            [_VISION_SYSTEM_PROMPT + "\n\n" + user_prompt, img]
        )
        return response.text

    async def _call_openai_compatible(
        self,
        image_bytes: bytes,
        user_prompt: str,
        system_prompt: str = "",
    ) -> str:
        client = self._get_client()
        if client is None:
            raise RuntimeError("OpenAI-compatible vision client unavailable")

        # Compress to JPEG for smaller payload (faster over API)
        try:
            import io
            from PIL import Image
            img = Image.open(io.BytesIO(image_bytes))
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=75)
            jpeg_bytes = buf.getvalue()
            b64 = base64.b64encode(jpeg_bytes).decode("ascii")
            img_mime = "image/jpeg"
        except Exception:
            # Fallback: send raw bytes as-is (PNG)
            b64 = base64.b64encode(image_bytes).decode("ascii")
            img_mime = "image/png"

        provider = self._settings.companion_vision_provider

        # Determine effective text prefix:
        # - Ambient: system_prompt = _VISION_SYSTEM_PROMPT (structured JSON extraction)
        # - Quick Look: system_prompt = "" (prompt is already a full conversational question)
        prefix = (system_prompt + "\n\n") if system_prompt else ""

        # Nemotron VL (and most NVIDIA NIM VL models) do NOT support the
        # 'system' role — merge the system prompt into the user content block.
        if provider in ("nvidia",):
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prefix + user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{img_mime};base64,{b64}"},
                        },
                    ],
                },
            ]
        else:
            # OpenAI, OpenRouter, Gemini-via-openai — system role is fine
            if system_prompt:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{img_mime};base64,{b64}"},
                            },
                        ],
                    },
                ]
            else:
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{img_mime};base64,{b64}"},
                            },
                        ],
                    },
                ]

        response = await client.chat.completions.create(
            model=self._settings.companion_vision_model,
            messages=messages,
            max_tokens=1024,
            temperature=0.1,
        )
        return response.choices[0].message.content or ""

    def _parse_response(self, raw: str) -> VisionContext:
        """Parse JSON response from vision model."""
        try:
            text = raw.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
            text = text.strip()

            data: Any = json.loads(text)
            if not isinstance(data, dict):
                return VisionContext.empty()

            conf_val = data.get("confidence", 0.5)
            conf = float(conf_val) if isinstance(conf_val, (int, float, str)) and str(conf_val).replace('.', '', 1).isdigit() else 0.5

            # Legacy vs Nemotron 12B VL schema normalization
            scene_raw = data.get("scene")
            if isinstance(scene_raw, dict):
                scene = scene_raw
            elif isinstance(scene_raw, str) and scene_raw:
                scene = {"type": scene_raw, "activity": scene_raw}
            else:
                app_info = data.get("application") if isinstance(data.get("application"), dict) else {}
                act_info = data.get("activity") if isinstance(data.get("activity"), dict) else {}
                scene = {
                    "type": app_info.get("category") or app_info.get("name") or "unknown",
                    "activity": act_info.get("description") or act_info.get("type") or "unknown",
                }

            events: list[dict] = []
            raw_events = data.get("events")
            if isinstance(raw_events, list):
                for item in raw_events:
                    if isinstance(item, dict):
                        events.append(item)
                    elif isinstance(item, str) and item:
                        events.append({"type": item, "importance": "medium"})

            # Coding state errors
            coding = data.get("coding_state")
            if isinstance(coding, dict) and coding.get("detected"):
                errs = coding.get("errors")
                if isinstance(errs, list):
                    for err in errs:
                        events.append({"type": "CODE_ERROR", "importance": "high", "detail": str(err)})
                warns = coding.get("warnings")
                if isinstance(warns, list):
                    for warn in warns:
                        events.append({"type": "CODE_WARNING", "importance": "medium", "detail": str(warn)})

            # Writing state errors
            writing = data.get("writing_state")
            if isinstance(writing, dict) and writing.get("detected"):
                errs = writing.get("possible_errors")
                if isinstance(errs, list):
                    for err in errs:
                        events.append({"type": "SPELLING_ERROR", "importance": "low", "detail": str(err)})

            # Game state events
            game = data.get("game_state")
            if isinstance(game, dict) and game.get("detected"):
                if game.get("state") in ("combat", "boss_fight"):
                    events.append({"type": "COMBAT_STARTED", "importance": "high"})
                enemies = game.get("enemies")
                if isinstance(enemies, list):
                    for enemy in enemies:
                        events.append({"type": "ENEMY_DETECTED", "importance": "high", "detail": str(enemy)})

            # Screen state errors
            screen_state = data.get("screen_state")
            if isinstance(screen_state, dict):
                errs = screen_state.get("errors")
                if isinstance(errs, list):
                    for err in errs:
                        events.append({"type": "SCREEN_ERROR", "importance": "high", "detail": str(err)})

            entities: list[dict] = []
            raw_entities = data.get("entities")
            if isinstance(raw_entities, list):
                for ent in raw_entities:
                    if isinstance(ent, dict):
                        entities.append(ent)
                    elif isinstance(ent, str) and ent:
                        entities.append({"type": ent, "position": "screen", "confidence": 0.8})

            changes: list[dict] = []
            raw_changes = data.get("changes")
            if isinstance(raw_changes, list):
                for ch in raw_changes:
                    if isinstance(ch, dict):
                        changes.append(ch)
                    elif isinstance(ch, str) and ch:
                        changes.append({"type": ch})

            return VisionContext(
                scene=scene,
                entities=entities,
                events=events,
                changes=changes,
                confidence=conf,
                raw_description="",
            )
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            log.warning("vision_parse_error", error=str(exc), raw_snippet=raw[:200])
            return VisionContext.error_context(f"parse_error: {exc}")

    async def quick_look_analyze(
        self,
        image_bytes: bytes,
        user_question: str,
        mode: str = "general",
        app_info: Optional[dict] = None,
    ) -> str:
        """Quick Look combined vision + reasoning fast path.

        Sends the screenshot and user's question together in a single API call
        to get a direct natural language answer immediately.
        """
        if not self._limiter.reserve_for_quicklook():
            return "I'm receiving too many quick questions right now. Please wait a moment."

        app_str = (app_info or {}).get("process_name_stem", "unknown")
        prompt = (
            f"You are Genie, a helpful and friendly AI companion.\n"
            f"The user is asking about their screen surface ({app_str}, mode={mode}).\n"
            f"Question: \"{user_question}\"\n\n"
            f"Look closely at the image provided and answer the question directly, concisely, and specifically. "
            f"Mention exact error messages, line numbers, or visible details if applicable. Keep the reply under 3-4 sentences."
        )

        try:
            raw_answer = await asyncio.wait_for(
                self._call_vision_api(image_bytes, prompt, system_prompt=""),
                timeout=12.0,
            )
            self._limiter.record_call()
            return raw_answer.strip()
        except asyncio.TimeoutError:
            log.warning("quick_look_api_timeout")
            return "I looked at your screen, but the vision request timed out. Please try again."
        except Exception as exc:
            log.warning("quick_look_api_error", error=str(exc))
            return "I took a look at your screen, but couldn't analyze it right now."

    @property
    def limiter(self) -> VisionCallLimiter:
        return self._limiter


# ── Stub for future local provider ───────────────────────────────────────────

class LocalVisionProvider:
    """Placeholder — drop-in future local vision model.

    When a local model is available, implement this class and set
    COMPANION_VISION_PROVIDER=local in .env.  Zero changes to CompanionBrain.
    """

    async def analyze(
        self,
        image_bytes: bytes,
        mode: str = "general",
        app_info: Optional[dict] = None,
    ) -> VisionContext:
        raise NotImplementedError("Local vision provider not yet implemented")

    async def quick_look_analyze(
        self,
        image_bytes: bytes,
        user_question: str,
        mode: str = "general",
        app_info: Optional[dict] = None,
    ) -> str:
        raise NotImplementedError("Local vision provider quick look not yet implemented")


# ── VisionService facade ──────────────────────────────────────────────────────

class VisionService:
    """Facade that routes to the configured provider."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        if self._settings.companion_vision_provider == "local":
            self._provider: Any = LocalVisionProvider()
        else:
            self._provider = APIVisionProvider(settings=self._settings)

    async def analyze(
        self,
        image_bytes: bytes,
        mode: str = "general",
        app_info: Optional[dict] = None,
    ) -> VisionContext:
        if not self._settings.companion_vision_enabled:
            return VisionContext.empty()
        return await self._provider.analyze(image_bytes, mode=mode, app_info=app_info)

    async def quick_look_analyze(
        self,
        image_bytes: bytes,
        user_question: str,
        mode: str = "general",
        app_info: Optional[dict] = None,
    ) -> str:
        if not self._settings.companion_vision_enabled:
            return "Screen vision is currently disabled in settings."
        if hasattr(self._provider, "quick_look_analyze"):
            return await self._provider.quick_look_analyze(
                image_bytes=image_bytes,
                user_question=user_question,
                mode=mode,
                app_info=app_info,
            )
        return "Quick Look is unavailable for the current vision provider."

    @property
    def limiter(self) -> Optional[VisionCallLimiter]:
        if hasattr(self._provider, "limiter"):
            return self._provider.limiter
        return None
