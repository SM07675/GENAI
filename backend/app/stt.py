"""Speech-to-text abstraction with fallback chain.

Fallback ladder
---------------
1. faster-whisper (local, offline, GPU-accelerated)  — default
2. OpenAI Whisper API (cloud)                        — if STT_ENGINE=whisper_api and OPENAI_API_KEY set
3. Typed-input prompt                                — if both fail, returns "" so the
   orchestrator emits a clean "I didn't catch any speech" error to the user.

No bare `except Exception` — specific exception types are caught and logged.
"""
from __future__ import annotations

import io
import logging
from typing import Optional

import structlog

from .config import Settings, get_settings

log = structlog.get_logger("genie.stt")

_fw_model = None  # cached faster-whisper model


# ─────────────────────────────────────────────────────────────────────────────
# faster-whisper (local, default)
# ─────────────────────────────────────────────────────────────────────────────
def _resolve_device_compute(settings: Settings) -> tuple[str, str]:
    device  = settings.stt_device
    compute = settings.stt_compute_type
    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
    if compute == "auto":
        compute = "int8_float16" if device == "cuda" else "int8"
    return device, compute


def _get_fw_model(settings: Settings):
    """Load (and cache) the faster-whisper model."""
    global _fw_model
    if _fw_model is not None:
        return _fw_model
    from faster_whisper import WhisperModel

    device, compute = _resolve_device_compute(settings)
    log.info("whisper_loading", model=settings.whisper_model_size, device=device, compute=compute)
    _fw_model = WhisperModel(
        settings.whisper_model_size,
        device=device,
        compute_type=compute,
    )
    log.info("whisper_ready")
    return _fw_model


def transcribe_fw(audio_bytes: bytes, settings: Settings) -> str:
    """Transcribe raw audio bytes with faster-whisper. Accepts webm/wav/mp3."""
    model = _get_fw_model(settings)
    buf   = io.BytesIO(audio_bytes)
    buf.name = "audio.webm"  # hint for ffmpeg-backed decoder
    segments, _info = model.transcribe(
        buf,
        language=settings.stt_language or None,
        vad_filter=True,
        beam_size=1,
    )
    return "".join(seg.text for seg in segments).strip()


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI Whisper API (cloud, optional)
# ─────────────────────────────────────────────────────────────────────────────
async def transcribe_whisper_api(audio_bytes: bytes, settings: Settings) -> str:
    from openai import AsyncOpenAI, AuthenticationError, APIConnectionError

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    buf    = io.BytesIO(audio_bytes)
    buf.name = "audio.webm"
    resp = await client.audio.transcriptions.create(
        model="whisper-1",
        file=("audio.webm", buf, "audio/webm"),
    )
    return (resp.text or "").strip()


# ─────────────────────────────────────────────────────────────────────────────
# Public facade with fallback
# ─────────────────────────────────────────────────────────────────────────────
async def transcribe(audio_bytes: bytes, settings: Optional[Settings] = None) -> str:
    """Transcribe audio bytes using the configured engine.

    Fallback: if the primary engine fails, try the other engine. If both fail,
    return "" so the caller can surface a clean error to the user.

    `faster_whisper` is sync/CPU-bound → runs in a worker thread.
    The cloud Whisper API is natively async.
    """
    settings = settings or get_settings()
    if not audio_bytes:
        return ""

    import asyncio

    # ── Primary: faster-whisper ───────────────────────────────────────────────
    if settings.stt_engine != "whisper_api":
        try:
            result = await asyncio.to_thread(transcribe_fw, audio_bytes, settings)
            if result:
                return result
        except RuntimeError as e:
            log.warning("whisper_local_failed", error=str(e))
        except Exception as e:  # noqa: BLE001 - PyAV InvalidDataError etc.
            log.warning("whisper_local_ignored", error=str(e))

        # Fallback to cloud API if key is available
        if settings.openai_api_key:
            log.info("stt_fallback_to_cloud")
            try:
                return await transcribe_whisper_api(audio_bytes, settings)
            except Exception as e:
                log.warning("whisper_api_also_failed", error=str(e))
        return ""

    # ── Primary: Whisper API ──────────────────────────────────────────────────
    if not settings.openai_api_key:
        log.warning("whisper_api_selected_but_no_key")
        return ""

    try:
        return await transcribe_whisper_api(audio_bytes, settings)
    except Exception as e:
        log.warning("whisper_api_failed_trying_local", error=str(e))
        try:
            return await asyncio.to_thread(transcribe_fw, audio_bytes, settings)
        except Exception as e2:
            log.warning("stt_both_engines_failed", error=str(e2))
            return ""
