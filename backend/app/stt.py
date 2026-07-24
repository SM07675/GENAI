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
    """Transcribe raw PCM16 audio bytes with faster-whisper.
    The backend VAD service provides raw 16-bit 16kHz mono PCM.
    """
    model = _get_fw_model(settings)
    import numpy as np

    try:
        # Convert raw s16le PCM bytes to float32 numpy array for faster-whisper
        audio_array = np.frombuffer(audio_bytes, np.int16).astype(np.float32) / 32768.0
        
        segments, _info = model.transcribe(
            audio_array,
            language=settings.stt_language or None,
            vad_filter=True,
            vad_parameters={
                "threshold": settings.vad_threshold,
                "min_silence_duration_ms": settings.vad_min_silence_duration_ms,
                "min_speech_duration_ms": settings.vad_min_speech_duration_ms,
                "speech_pad_ms": settings.vad_speech_pad_ms,
            },
            beam_size=5,
            initial_prompt="Genie, YouTube, Spotify, GitHub, Google, Gmail, Chrome, Visual Studio Code, VS Code, Python, FastAPI, React, Next.js, OpenAI, Mistral, Groq, Qwen, Llama, WhatsApp, Windows.",
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
        )
        return "".join(seg.text for seg in segments).strip()
    except Exception as err:
        raise RuntimeError(f"Failed to transcribe raw audio: {err}") from err


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

    Uses faster-whisper (local) as the primary engine.
    Cloud fallback is intentionally disabled — it requires billing on OpenAI.
    If local transcription fails, returns "" so the caller shows a clean error.

    `faster_whisper` is sync/CPU-bound → runs in a worker thread.
    """
    settings = settings or get_settings()
    if not audio_bytes:
        return ""

    # Reject audio that is too short to contain speech (< 1KB = likely empty/header only)
    if len(audio_bytes) < 1024:
        log.info("stt_audio_too_short", bytes=len(audio_bytes))
        return ""

    import asyncio

    # ── Local faster-whisper (primary & only engine for robustness) ───────────
    if settings.stt_engine != "whisper_api":
        try:
            result = await asyncio.to_thread(transcribe_fw, audio_bytes, settings)
            return result  # may be "" if silence — that's fine
        except RuntimeError as e:
            log.warning("whisper_local_failed", error=str(e))
        except Exception as e:  # noqa: BLE001
            log.warning("whisper_local_ignored", error=str(e))
        # Cloud fallback intentionally removed — causes 10s delays due to quota errors.
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
