"""Production TTS Engine — Genie Voice Synthesizer.

Architecture
------------
Singleton ``ProductionTTS`` class loads the TTS model ONCE at startup,
keeps it resident in GPU VRAM, and reuses it for every request.

Engine priority (config-driven):
  1. Kokoro TTS  — local, ONNX/GPU, ~100 ms/sentence, no internet needed
  2. Edge TTS    — cloud, Microsoft Neural, ~150 ms/sentence, needs internet

Thread/async safety
--------------------
- ``_kokoro_semaphore``: asyncio.Semaphore(1) — prevents concurrent GPU calls
  without blocking the event loop (unlike a threading.Lock).
- All Kokoro inference runs in ``asyncio.to_thread`` so the event loop stays
  responsive during synthesis.

GPU optimization (RTX 4060)
-----------------------------
- Kokoro uses ONNX Runtime with CUDA EP when available.
- No FP16 toggles needed — ONNX Runtime handles precision internally.
- Voice prompt bytes loaded ONCE at init, never re-read from disk.
- ``torch.cuda.empty_cache()`` called only on OOM, not every request.

Logging
-------
Every synthesis call logs: engine, text_len, synthesis_ms, real_time_factor.
End-of-session: GPU memory usage snapshot.
"""
from __future__ import annotations

import asyncio
import io
import os
import re
import time
import threading
from typing import Optional

import structlog

log = structlog.get_logger("genie.tts")

# ── Module-level state ────────────────────────────────────────────────────────
# Kokoro pipeline (loaded once, never reloaded)
_kokoro_pipeline: Optional[object] = None
_kokoro_init_lock = threading.Lock()
_kokoro_semaphore: Optional[asyncio.Semaphore] = None  # created lazily (needs event loop)

# Compatibility aliases
_tts_init_lock = _kokoro_init_lock
_tts_inference_lock = threading.Lock()

def _install_numba_shim() -> None:
    """Safe numba shim for environments without numba installed."""
    import sys
    import types
    if "numba" not in sys.modules:
        sys.modules["numba"] = types.ModuleType("numba")

# Chatterbox pipeline (loaded once, never reloaded)
_chatterbox_pipeline: Optional[object] = None
_chatterbox_init_lock = threading.Lock()
_chatterbox_semaphore: Optional[asyncio.Semaphore] = None

# These are populated from settings during init_tts_model()
_kokoro_voice: str = "af_heart"
_kokoro_speed: float = 1.0
_kokoro_lang: str = "a"
_kokoro_sample_rate: int = 24000

# GPU availability
_cuda_available: bool = False
_gpu_name: str = "CPU"
_model_load_time_ms: float = 0.0


def _detect_gpu() -> tuple[bool, str]:
    """Detect GPU availability without importing torch at module load."""
    try:
        import torch
        if torch.cuda.is_available():
            return True, torch.cuda.get_device_name(0)
    except Exception:
        pass
    return False, "CPU"


def init_tts_model() -> None:
    """Load Kokoro TTS model ONCE at application startup.

    Called by the FastAPI lifespan. Subsequent calls are no-ops.
    """
    global _kokoro_pipeline, _chatterbox_pipeline, _cuda_available, _gpu_name, _model_load_time_ms
    global _kokoro_voice, _kokoro_speed, _kokoro_lang, _kokoro_sample_rate


    with _kokoro_init_lock:
        if _kokoro_pipeline is not None:
            return  # already loaded — never reload

        # Load settings for voice configuration
        try:
            from .config import get_settings
            _s = get_settings()
            _kokoro_voice = getattr(_s, "tts_kokoro_voice", "af_heart")
            _kokoro_speed = getattr(_s, "tts_kokoro_speed", 1.0)
            _kokoro_lang = getattr(_s, "tts_kokoro_lang", "a")
            _kokoro_sample_rate = getattr(_s, "tts_sample_rate", 24000)
        except Exception:
            pass

        _cuda_available, _gpu_name = _detect_gpu()
        log.info(
            "tts_init_starting",
            gpu=_gpu_name,
            cuda=_cuda_available,
            voice=_kokoro_voice,
        )

        t0 = time.perf_counter()
        
        # Load Chatterbox if enabled or auto
        chatterbox_enabled = getattr(_s, "tts_chatterbox_enabled", True) if _s else True
        if chatterbox_enabled:
            with _chatterbox_init_lock:
                if _chatterbox_pipeline is None:
                    try:
                        log.info("tts_loading_chatterbox", gpu=_gpu_name, cuda=_cuda_available)
                        _chatterbox_pipeline = _load_chatterbox()
                        log.info("tts_chatterbox_loaded", load_ms=round((time.perf_counter() - t0) * 1000))
                    except Exception as exc:
                        log.warning("tts_chatterbox_load_failed", error=str(exc))
                        _chatterbox_pipeline = None

        try:
            _kokoro_pipeline = _load_kokoro()
            _model_load_time_ms = (time.perf_counter() - t0) * 1000
            log.info(
                "tts_model_loaded",
                engine="kokoro",
                gpu=_gpu_name,
                load_ms=round(_model_load_time_ms),
                voice=_kokoro_voice,
                cuda=_cuda_available,
            )
        except Exception as exc:
            _model_load_time_ms = (time.perf_counter() - t0) * 1000
            log.warning(
                "tts_kokoro_load_failed",
                error=str(exc),
                fallback="edge_tts",
            )
            _kokoro_pipeline = None  # will fall back to Edge TTS


def _load_kokoro() -> object:
    """Load the Kokoro KPipeline. Raises on failure."""
    from kokoro import KPipeline  # type: ignore[import]

    pipeline = KPipeline(lang_code=_kokoro_lang)
    log.info("kokoro_pipeline_created", lang_code=_kokoro_lang)
    return pipeline


def _get_semaphore() -> asyncio.Semaphore:
    """Return (creating if needed) the per-event-loop Kokoro semaphore."""
    global _kokoro_semaphore
    if _kokoro_semaphore is None:
        _kokoro_semaphore = asyncio.Semaphore(1)
    return _kokoro_semaphore


def _get_chatterbox_semaphore() -> asyncio.Semaphore:
    """Return (creating if needed) the per-event-loop Chatterbox semaphore."""
    global _chatterbox_semaphore
    if _chatterbox_semaphore is None:
        _chatterbox_semaphore = asyncio.Semaphore(1)
    return _chatterbox_semaphore


def _load_chatterbox() -> object:
    """Load the Chatterbox Multilingual TTS model. Raises on failure."""
    from chatterbox import ChatterboxMultilingualTTS  # type: ignore[import]
    import torch
    device = torch.device("cuda" if _cuda_available else "cpu")
    pipeline = ChatterboxMultilingualTTS.from_pretrained(device=device)
    log.info("chatterbox_pipeline_created", device=str(device))
    return pipeline


# ── Core synthesis ────────────────────────────────────────────────────────────

def _synthesize_kokoro_sync(text: str, voice: str, speed: float) -> bytes:
    """Run Kokoro inference synchronously (called via asyncio.to_thread).

    Returns WAV bytes at 24 kHz, 16-bit PCM, mono.
    """
    import numpy as np
    import soundfile as sf  # type: ignore[import]

    pipeline = _kokoro_pipeline
    if pipeline is None:
        raise RuntimeError("Kokoro pipeline not initialized")

    # Kokoro KPipeline.generate() is a generator that yields (gs, ps, audio)
    # where audio is a numpy float32 array at 24 kHz.
    audio_chunks: list[object] = []
    for _, _, audio in pipeline(text, voice=voice, speed=speed, split_pattern=None):
        audio_chunks.append(audio)

    if not audio_chunks:
        return b""

    # Concatenate all chunks
    import numpy as np  # noqa: F811
    full_audio = np.concatenate(audio_chunks, axis=0)

    # Encode to WAV in memory
    buf = io.BytesIO()
    sf.write(buf, full_audio, _kokoro_sample_rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()


async def _synthesize_kokoro_async(text: str) -> bytes:
    """Async wrapper around Kokoro synthesis with semaphore protection."""
    sem = _get_semaphore()
    async with sem:
        return await asyncio.to_thread(
            _synthesize_kokoro_sync, text, _kokoro_voice, _kokoro_speed
        )


async def _synthesize_edge_async(text: str, voice: str = "en-IN-NeerjaNeural") -> tuple[bytes, str]:
    """Synthesize using Microsoft Edge TTS (cloud fallback).

    Returns (audio_bytes, mime_type).
    """
    import edge_tts  # type: ignore[import]

    communicate = edge_tts.Communicate(text, voice)
    audio_data = bytearray()
    async for message in communicate.stream():
        if message["type"] == "audio":
            audio_data.extend(message["data"])
    return bytes(audio_data), "audio/mpeg"


async def _synthesize_elevenlabs_async(
    text: str,
    voice_id: str,
    model: str,
    api_key: str,
    cue: str = "neutral",
) -> tuple[bytes, str]:
    """Synthesize using ElevenLabs TTS — most human-sounding, multilingual.

    Voice settings are tuned for a warm, natural assistant voice.
    The ``cue`` delivery tag from the system prompt drives slight style shifts
    (e.g. [[warm]] boosts expressiveness, [[urgent]] tightens stability).
    """
    import aiohttp

    # Map system-prompt delivery cues → ElevenLabs style / stability tweaks
    _CUE_STYLE: dict[str, dict] = {
        "neutral":     {"stability": 0.55, "similarity_boost": 0.80, "style": 0.20, "use_speaker_boost": True},
        "warm":        {"stability": 0.45, "similarity_boost": 0.82, "style": 0.40, "use_speaker_boost": True},
        "cheerful":    {"stability": 0.40, "similarity_boost": 0.78, "style": 0.55, "use_speaker_boost": True},
        "empathetic":  {"stability": 0.50, "similarity_boost": 0.85, "style": 0.35, "use_speaker_boost": True},
        "apologetic":  {"stability": 0.52, "similarity_boost": 0.83, "style": 0.30, "use_speaker_boost": True},
        "urgent":      {"stability": 0.70, "similarity_boost": 0.90, "style": 0.10, "use_speaker_boost": True},
        "focused":     {"stability": 0.65, "similarity_boost": 0.85, "style": 0.15, "use_speaker_boost": True},
        "reassuring":  {"stability": 0.48, "similarity_boost": 0.84, "style": 0.38, "use_speaker_boost": True},
    }
    voice_settings = _CUE_STYLE.get(cue.lower(), _CUE_STYLE["neutral"])

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": model,
        "output_format": "mp3_44100_192",   # 192 kbps — highest clarity
        "voice_settings": voice_settings,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                audio_bytes = await resp.read()
                return audio_bytes, "audio/mpeg"
            else:
                err = await resp.text()
                raise Exception(f"ElevenLabs API error: {resp.status} - {err}")


def _synthesize_chatterbox_sync(text: str) -> bytes:
    """Run Chatterbox inference synchronously (called via asyncio.to_thread)."""
    import numpy as np
    import soundfile as sf
    import re

    pipeline = _chatterbox_pipeline
    if pipeline is None:
        raise RuntimeError("Chatterbox pipeline not initialized")

    # Detect language: if Devanagari characters are present, use Hindi, otherwise English
    has_hindi = bool(re.search(r'[\u0900-\u097F]', text))
    lang_id = "hi" if has_hindi else "en"

    # Generate audio
    # generate() returns a PyTorch tensor of shape (1, audio_len)
    audio_tensor = pipeline.generate(text, language_id=lang_id)
    audio_np = audio_tensor.squeeze().detach().cpu().numpy()

    # Encode to WAV in memory
    buf = io.BytesIO()
    sf.write(buf, audio_np, pipeline.sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


async def _synthesize_chatterbox_async(text: str) -> bytes:
    """Async wrapper around Chatterbox synthesis with semaphore protection."""
    sem = _get_chatterbox_semaphore()
    async with sem:
        return await asyncio.to_thread(_synthesize_chatterbox_sync, text)


# ── Public API ────────────────────────────────────────────────────────────────

async def synthesize_with_mime(
    text: str,
    settings=None,
    cue: str = "neutral",
) -> tuple[bytes, str, list[dict]]:
    """Synthesize ``text`` → ``(audio_bytes, mime_type, word_timings)``.

    Engine selection:
      - ``tts_engine = "kokoro"``  → Kokoro only
      - ``tts_engine = "edge"``    → Edge TTS only
      - ``tts_engine = "auto"``    → try Kokoro, fall back to Edge TTS
    """
    from .config import get_settings

    settings = settings or get_settings()
    text = (text or "").strip()
    text = re.sub(r'\[\[?[^\]]*\]?\]?', '', text)
    text = re.sub(r'\[\s*(neutral|warm|cheerful|empathetic|apologetic|urgent|focused|reassuring)\s*\]', '', text, flags=re.IGNORECASE).strip()
    if not text:
        return b"", "audio/wav", []

    engine = getattr(settings, "tts_engine", "auto")
    t0 = time.perf_counter()

    # ── Chatterbox path ────────────────────────────────────────────────────────
    if engine in ("chatterbox", "auto") and _chatterbox_pipeline is not None:
        try:
            audio_bytes = await _synthesize_chatterbox_async(text)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            
            audio_dur_s = max(0.0, (len(audio_bytes) - 44) / (_chatterbox_pipeline.sr * 2))
            rtf = elapsed_ms / 1000.0 / audio_dur_s if audio_dur_s > 0 else 0.0

            log.info(
                "tts_synthesis_complete",
                engine="chatterbox",
                text_len=len(text),
                synthesis_ms=round(elapsed_ms),
                audio_dur_s=round(audio_dur_s, 2),
                rtf=round(rtf, 3),
                gpu=_gpu_name,
            )
            return audio_bytes, "audio/wav", []

        except Exception as exc:
            log.warning(
                "tts_chatterbox_synthesis_failed",
                error=str(exc),
                text=text[:60],
                fallback="kokoro" if engine == "auto" else "none",
            )
            if engine != "auto":
                raise

    # ── ElevenLabs path ────────────────────────────────────────────────────────
    has_elevenlabs = bool(getattr(settings, "elevenlabs_api_key", ""))
    if engine == "elevenlabs" or (engine == "auto" and has_elevenlabs):
        try:
            voice_id = getattr(settings, "tts_elevenlabs_voice_id", "21m00Tcm4TlvDq8ikWAM")
            model = getattr(settings, "tts_elevenlabs_model", "eleven_turbo_v2_5")
            audio_bytes, mime = await _synthesize_elevenlabs_async(
                text, voice_id, model, settings.elevenlabs_api_key, cue=cue
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            log.info(
                "tts_synthesis_complete",
                engine="elevenlabs",
                text_len=len(text),
                synthesis_ms=round(elapsed_ms),
            )
            return audio_bytes, mime, []
        except Exception as exc:
            log.warning(
                "tts_elevenlabs_synthesis_failed",
                error=str(exc),
                text=text[:60],
                fallback="kokoro/edge_tts"
            )
            # Do NOT raise here. We want to fall through to Kokoro or Edge TTS.
            pass

    # ── Kokoro path ──────────────────────────────────────────────────────────
    if engine in ("kokoro", "auto") and _kokoro_pipeline is not None:
        try:
            audio_bytes = await _synthesize_kokoro_async(text)
            elapsed_ms = (time.perf_counter() - t0) * 1000

            # Estimate audio duration: WAV header is 44 bytes, 16-bit mono 24kHz
            # duration = (bytes - 44) / (24000 * 2)
            audio_dur_s = max(0.0, (len(audio_bytes) - 44) / (24000 * 2))
            rtf = elapsed_ms / 1000.0 / audio_dur_s if audio_dur_s > 0 else 0.0

            log.info(
                "tts_synthesis_complete",
                engine="kokoro",
                text_len=len(text),
                synthesis_ms=round(elapsed_ms),
                audio_dur_s=round(audio_dur_s, 2),
                rtf=round(rtf, 3),
                gpu=_gpu_name,
            )

            if _cuda_available:
                try:
                    import torch
                    used = torch.cuda.memory_allocated() / 1e6
                    log.debug("gpu_vram_used_mb", mb=round(used, 1))
                except Exception:
                    pass

            return audio_bytes, "audio/wav", []

        except Exception as exc:
            log.warning(
                "tts_kokoro_synthesis_failed",
                error=str(exc),
                text=text[:60],
                fallback="edge_tts" if engine == "auto" else "none",
            )
            if engine != "auto":
                raise

    # ── Edge TTS path (primary or fallback) ──────────────────────────────────
    default_voice = getattr(settings, "tts_edge_voice", "en-US-JennyNeural") if settings else "en-US-JennyNeural"
    if bool(re.search(r'[\u0900-\u097F]', text)):
        edge_voice = "hi-IN-SwaraNeural"
    else:
        edge_voice = default_voice

    try:
        audio_bytes, mime = await _synthesize_edge_async(text, edge_voice)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        log.info(
            "tts_synthesis_complete",
            engine="edge_tts",
            text_len=len(text),
            synthesis_ms=round(elapsed_ms),
        )
        return audio_bytes, mime, []

    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        log.error(
            "tts_synthesis_failed",
            engine="edge_tts",
            error=str(exc),
            text=text[:60],
            elapsed_ms=round(elapsed_ms),
        )
        return b"", "audio/wav", []


async def synthesize(text: str, settings=None) -> bytes:
    """Legacy wrapper — returns audio bytes only."""
    audio, _, _ = await synthesize_with_mime(text, settings)
    return audio


# ── Startup helpers ───────────────────────────────────────────────────────────

def _run_synthesis_sync(text: str, settings) -> bytes:
    """Synchronous synthesis for thread pool callers (legacy compat)."""
    # This path is used by tts_streamer in some older code paths.
    # We synthesize via Kokoro synchronously.
    if _kokoro_pipeline is not None:
        try:
            return _synthesize_kokoro_sync(text, _kokoro_voice, _kokoro_speed)
        except Exception as exc:
            log.warning("tts_sync_kokoro_failed", error=str(exc))
    # Edge TTS cannot be called synchronously — return empty to signal failure
    return b""
