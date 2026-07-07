"""Text-to-speech with Edge TTS (default) and ElevenLabs (optional).

`synthesize(text)` returns MP3 bytes. We prefer Edge TTS because it's free and
needs no API key. If `TTS_ENGINE=elevenlabs` and a key is set, ElevenLabs is
used instead with higher-fidelity voices.
"""
from __future__ import annotations

import logging
from typing import Optional

from .config import Settings, get_settings

log = logging.getLogger("genie.tts")


async def synthesize_edge(text: str, settings: Settings) -> bytes:
    """Synthesize speech via Microsoft Edge TTS. Returns MP3 bytes."""
    import edge_tts
    import re

    # Detect Devanagari to dynamically set TTS voice
    is_hindi = bool(re.search(r'[\u0900-\u097F]', text))
    voice = "hi-IN-SwaraNeural" if is_hindi else settings.edge_voice

    communicate = edge_tts.Communicate(text, voice)
    chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)


async def synthesize_elevenlabs(text: str, settings: Settings) -> bytes:
    """Synthesize speech via ElevenLabs. Returns MP3 bytes."""
    import httpx

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": settings.elevenlabs_model,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.content


async def synthesize(text: str, settings: Optional[Settings] = None) -> bytes:
    """Synthesize `text` to MP3 bytes using the configured engine.

    Falls back to gTTS if ElevenLabs is selected but unconfigured.
    """
    settings = settings or get_settings()
    text = (text or "").strip()
    if not text:
        return b""

    # Engine selection with a graceful fallback.
    use_eleven = (
        settings.tts_engine == "elevenlabs"
        and bool(settings.elevenlabs_api_key)
    )

    try:
        if use_eleven:
            return await synthesize_elevenlabs(text, settings)
        return await synthesize_edge(text, settings)
    except Exception as e:  # noqa: BLE001
        log.warning("Primary TTS failed (%s); trying Edge fallback.", e)
        if use_eleven:
            try:
                return await synthesize_edge(text, settings)
            except Exception as e2:  # noqa: BLE001
                log.error("Edge TTS fallback also failed: %s", e2)
        return b""
