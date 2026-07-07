"""Speech-to-text abstraction.

Default engine: **faster-whisper** (local, offline, GPU-accelerated). Set
`STT_ENGINE=whisper_api` in `.env` to use OpenAI's cloud Whisper API instead
(requires OPENAI_API_KEY).
"""
from __future__ import annotations

import io
import logging
from typing import Optional

from .config import Settings, get_settings

log = logging.getLogger("genie.stt")

_fw_model = None  # cached faster-whisper model


# =====================================================================
# faster-whisper (local, default)
# =====================================================================
def _resolve_device_compute(settings: Settings) -> tuple[str, str]:
    device = settings.stt_device
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
    log.info("Loading faster-whisper '%s' on %s (%s)...",
             settings.whisper_model_size, device, compute)
    _fw_model = WhisperModel(
        settings.whisper_model_size,
        device=device,
        compute_type=compute,
    )
    log.info("faster-whisper ready.")
    return _fw_model


def transcribe_fw(audio_bytes: bytes, settings: Settings) -> str:
    """Transcribe raw audio bytes with faster-whisper. Accepts webm/wav/mp3."""
    model = _get_fw_model(settings)
    buf = io.BytesIO(audio_bytes)
    buf.name = "audio.webm"  # hint for ffmpeg-backed decoder
    segments, _info = model.transcribe(
        buf,
        language=settings.stt_language or None,
        vad_filter=True,
        beam_size=1,
    )
    text = "".join(seg.text for seg in segments).strip()
    return text


# =====================================================================
# OpenAI Whisper API (cloud, optional)
# =====================================================================
async def transcribe_whisper_api(audio_bytes: bytes, settings: Settings) -> str:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    buf = io.BytesIO(audio_bytes)
    buf.name = "audio.webm"
    resp = await client.audio.transcriptions.create(
        model="whisper-1",
        file=("audio.webm", buf, "audio/webm"),
    )
    return (resp.text or "").strip()


# =====================================================================
# Public facade
# =====================================================================
async def transcribe(audio_bytes: bytes, settings: Optional[Settings] = None) -> str:
    """Transcribe audio bytes using the configured engine.

    `faster_whisper` is sync/CPU-bound, so we run it in a worker thread to
    avoid blocking the event loop. The cloud Whisper API is natively async.
    """
    settings = settings or get_settings()
    if not audio_bytes:
        return ""

    try:
        if settings.stt_engine == "whisper_api":
            if not settings.openai_api_key:
                return ""
            return await transcribe_whisper_api(audio_bytes, settings)

        import asyncio
        return await asyncio.to_thread(transcribe_fw, audio_bytes, settings)
    except Exception as e:  # noqa: BLE001
        log.exception("STT failed: %s", e)
        return ""
