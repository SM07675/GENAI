"""Text-to-speech engine with delivery-cue prosody control.

Priority order:
  1. ElevenLabs  — if TTS_ENGINE=elevenlabs and key is set (best quality)
  2. Edge TTS    — always available, free, no key needed (solid fallback)
  3. Gemini Live — if TTS_ENGINE=gemini_live and key is set

Delivery cues ([[warm]], [[urgent]], etc.) parsed from the orchestrator
are mapped to rate/volume adjustments for Edge TTS and audio tags for
ElevenLabs v3 (when available).

Edge TTS word-boundary events are captured and returned alongside audio
so the frontend can do karaoke-style word highlighting.
"""
from __future__ import annotations

import logging
import re
import wave
from io import BytesIO
from typing import Any, Optional

import structlog

from .config import Settings, get_settings

log = structlog.get_logger("genie.tts")

# ── Delivery cue → prosody mapping ──────────────────────────────────────────

CUE_PROSODY: dict[str, dict[str, str]] = {
    "neutral":     {"rate": "+0%",  "volume": "+0%"},
    "warm":        {"rate": "+0%",  "volume": "+5%"},
    "cheerful":    {"rate": "+8%",  "volume": "+8%"},
    "empathetic":  {"rate": "-8%",  "volume": "-5%"},
    "apologetic":  {"rate": "-10%", "volume": "-5%"},
    "urgent":      {"rate": "+15%", "volume": "+10%"},
    "focused":     {"rate": "+0%",  "volume": "+0%"},
    "reassuring":  {"rate": "-5%",  "volume": "+0%"},
}


def _cue_rate(cue: str) -> str:
    return CUE_PROSODY.get(cue, CUE_PROSODY["neutral"])["rate"]


def _cue_volume(cue: str) -> str:
    return CUE_PROSODY.get(cue, CUE_PROSODY["neutral"])["volume"]


# ── Edge TTS (free, always available) ────────────────────────────────────────

async def synthesize_edge(
    text: str,
    settings: Settings,
    cue: str = "neutral",
) -> tuple[bytes, list[dict]]:
    """Microsoft Edge TTS → (MP3 bytes, word_timings).

    Word timings are [{word, offset_ms, duration_ms}, ...] from
    Edge's WordBoundary events — used for karaoke-style sync.
    """
    import edge_tts

    is_hindi = bool(re.search(r"[\u0900-\u097F]", text))
    voice = "hi-IN-SwaraNeural" if is_hindi else settings.edge_voice

    rate = _cue_rate(cue)
    volume = _cue_volume(cue)

    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
    audio_chunks: list[bytes] = []
    word_timings: list[dict] = []

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])
        elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
            word_timings.append({
                "word": chunk.get("text", ""),
                "offset_ms": chunk.get("offset", 0) / 10_000,
                "duration_ms": chunk.get("duration", 0) / 10_000,
            })

    return b"".join(audio_chunks), word_timings


# ── ElevenLabs (premium, optional) ───────────────────────────────────────────

async def synthesize_elevenlabs(text: str, settings: Settings) -> bytes:
    """ElevenLabs TTS → MP3 bytes. Raises on any error including 429."""
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
        "voice_settings": {
            "stability":        0.35,
            "similarity_boost": 0.85,
            "style":            0.4,
            "use_speaker_boost": True,
        },
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code == 429:
            raise RuntimeError("ElevenLabs quota/rate-limit (429) — falling back to Edge TTS")
        resp.raise_for_status()
        return resp.content


# ── Gemini Live TTS (optional, lowest latency) ───────────────────────────────

def _pcm16_to_wav(pcm: bytes, *, sample_rate: int = 24000) -> bytes:
    buf = BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buf.getvalue()


async def synthesize_gemini_live(text: str, settings: Settings) -> bytes:
    import asyncio
    from google import genai

    client = genai.Client(api_key=settings.gemini_api_key)
    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": settings.gemini_live_style,
        "speech_config": {
            "voice_config": {
                "prebuilt_voice_config": {"voice_name": settings.gemini_live_voice_name}
            }
        },
    }
    prompt = f"Speak this text naturally:\n{text}"
    pcm: list[bytes] = []
    async with asyncio.timeout(20):
        async with client.aio.live.connect(model=settings.gemini_live_model, config=config) as s:
            await s.send_realtime_input(text=prompt)
            async for r in s.receive():
                c = getattr(r, "server_content", None)
                if c and getattr(c, "model_turn", None):
                    for part in c.model_turn.parts:
                        inline = getattr(part, "inline_data", None)
                        if inline and getattr(inline, "data", None):
                            pcm.append(inline.data)
                if c and (getattr(c, "turn_complete", False) or getattr(c, "generation_complete", False)):
                    break
    if not pcm:
        return b""
    return _pcm16_to_wav(b"".join(pcm))


# ── Public API ────────────────────────────────────────────────────────────────

async def synthesize_with_mime(
    text: str,
    settings: Optional[Settings] = None,
    cue: str = "neutral",
) -> tuple[bytes, str, list[dict]]:
    """Synthesize `text` → (audio_bytes, mime_type, word_timings).

    Fallback chain:
      elevenlabs → edge  (if elevenlabs fails for any reason, including 429)
      gemini_live → edge (if gemini_live fails)
      edge → silence     (edge itself failed — very rare)

    word_timings is only populated for the Edge TTS path (which provides
    WordBoundary events). Empty list for other engines.
    """
    settings = settings or get_settings()
    text = (text or "").strip()
    if not text:
        return b"", "audio/mpeg", []

    engine = (settings.tts_engine or "edge").lower()

    # ── ElevenLabs path ──────────────────────────────────────────────────────
    if engine == "elevenlabs" and settings.elevenlabs_api_key:
        try:
            audio = await synthesize_elevenlabs(text, settings)
            return audio, "audio/mpeg", []
        except Exception as e:
            log.warning("elevenlabs_tts_failed", error=str(e))
            # Fall through to Edge below

    # ── Gemini Live path ─────────────────────────────────────────────────────
    elif engine == "gemini_live" and settings.gemini_api_key:
        try:
            audio = await synthesize_gemini_live(text, settings)
            if audio:
                return audio, "audio/wav", []
        except Exception as e:
            log.warning("gemini_live_tts_failed", error=str(e))
        # Fall through to Edge below

    # ── Edge TTS (default / fallback) ────────────────────────────────────────
    try:
        audio, word_timings = await synthesize_edge(text, settings, cue=cue)
        return audio, "audio/mpeg", word_timings
    except Exception as e:
        log.error("edge_tts_failed", error=str(e))
        return b"", "audio/mpeg", []


async def synthesize(text: str, settings: Optional[Settings] = None) -> bytes:
    """Legacy sync-compatible wrapper — returns audio bytes only."""
    audio, _, _ = await synthesize_with_mime(text, settings)
    return audio
