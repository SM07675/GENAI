"""STT Worker — speech-to-text with cancellation support.

Uses faster-whisper for local GPU-accelerated transcription.
Accepts raw PCM16 audio bytes from the audio pipeline and returns text.
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional

import structlog

from ..config import Settings, get_settings
from .cancellation import CancellationToken

log = structlog.get_logger("genie.engine.stt")

# Cached faster-whisper model
_fw_model = None


def _ensure_av_dlls() -> None:
    """Register av's bundled FFmpeg DLL directory and nvidia CUDA DLLs on Windows.

    Without this, av._core fails to load inside asyncio thread-pool workers
    because the DLL search path is not inherited correctly on Windows.
    Must be called before 'from faster_whisper import WhisperModel'.
    """
    if os.name != 'nt':
        return
    try:
        import importlib.util
        spec = importlib.util.find_spec('av')
        if spec and spec.submodule_search_locations:
            av_dir = list(spec.submodule_search_locations)[0]
            av_libs = os.path.abspath(os.path.join(av_dir, os.pardir, 'av.libs'))
            if os.path.exists(av_libs) and hasattr(os, 'add_dll_directory'):
                try:
                    os.add_dll_directory(av_libs)
                except (OSError, ValueError):
                    pass
            path_env = os.environ.get('PATH', '')
            if av_libs not in path_env:
                os.environ['PATH'] = av_libs + os.pathsep + path_env

        spec_nv = importlib.util.find_spec('nvidia')
        if spec_nv and spec_nv.submodule_search_locations:
            nvidia_dir = list(spec_nv.submodule_search_locations)[0]
            for root, dirs, files in os.walk(nvidia_dir):
                if os.path.basename(root) == 'bin':
                    try:
                        os.add_dll_directory(root)
                    except (OSError, ValueError):
                        pass
                    path_env = os.environ.get('PATH', '')
                    if root not in path_env:
                        os.environ['PATH'] = root + os.pathsep + path_env
        import av  # noqa: F401 - Preload av into sys.modules
    except Exception:
        pass  # Don't crash if av isn't installed yet



def _resolve_device_compute(settings: Settings) -> tuple[str, str]:
    device = settings.stt_device
    compute = settings.stt_compute_type
    if device == "auto":
        try:
            import ctranslate2
            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            device = "cpu"
    if compute == "auto":
        compute = "float16" if device == "cuda" else "int8"
    return device, compute


def _get_fw_model(settings: Settings):
    """Load (and cache) the faster-whisper model with automatic CPU fallback."""
    global _fw_model
    if _fw_model is not None:
        return _fw_model
    _ensure_av_dlls()
    from faster_whisper import WhisperModel

    device, compute = _resolve_device_compute(settings)
    log.info("stt_model_loading", model=settings.whisper_model_size, device=device, compute=compute)
    try:
        _fw_model = WhisperModel(
            settings.whisper_model_size,
            device=device,
            compute_type=compute,
        )
        log.info("stt_model_ready", device=device, compute=compute)
        return _fw_model
    except Exception as exc:
        log.warning("stt_cuda_failed_falling_back_to_cpu", error=str(exc))
        _fw_model = WhisperModel(
            settings.whisper_model_size,
            device="cpu",
            compute_type="int8",
        )
        log.info("stt_model_ready", device="cpu", compute="int8")
        return _fw_model


def _transcribe_sync(audio_bytes: bytes, settings: Settings) -> str:
    """Synchronous transcription — runs in a thread pool."""
    import numpy as np

    model = _get_fw_model(settings)
    audio_array = np.frombuffer(audio_bytes, np.int16).astype(np.float32) / 32768.0

    if len(audio_array) < 1600:  # less than 100ms
        return ""

    try:
        segments, info = model.transcribe(
            audio_array,
            language=settings.stt_language or None,
            vad_filter=True,
            vad_parameters={
                "threshold": settings.vad_threshold,
                "min_silence_duration_ms": settings.vad_min_silence_duration_ms,
                "min_speech_duration_ms": settings.vad_min_speech_duration_ms,
                "speech_pad_ms": settings.vad_speech_pad_ms,
            },
            beam_size=3,
            initial_prompt=(
                "Genie, YouTube, Spotify, GitHub, Google, Gmail, Chrome, "
                "Visual Studio Code, VS Code, Python, FastAPI, React, Next.js, "
                "OpenAI, Mistral, Groq, Qwen, Llama, WhatsApp, Windows."
            ),
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
        )
        text = "".join(seg.text for seg in segments).strip()
        if text:
            log.info("stt_transcribed", text=text[:100], language=info.language)
        return text
    except Exception as exc:
        log.warning("stt_transcribe_cuda_failed_trying_cpu", error=str(exc))
        try:
            from faster_whisper import WhisperModel
            cpu_model = WhisperModel(settings.whisper_model_size, device="cpu", compute_type="int8")
            segments, info = cpu_model.transcribe(audio_array, beam_size=3)
            text = "".join(seg.text for seg in segments).strip()
            if text:
                log.info("stt_transcribed_cpu_fallback", text=text[:100])
            return text
        except Exception as exc2:
            log.error("stt_cpu_transcribe_failed", error=str(exc2))
            return ""


class STTWorker:
    """Async STT worker with cancellation support."""

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()

    async def transcribe(
        self,
        audio_bytes: bytes,
        cancel_token: Optional[CancellationToken] = None,
    ) -> str:
        """Transcribe audio bytes. Returns empty string on cancellation or failure.

        Args:
            audio_bytes: Raw PCM16 16kHz mono audio.
            cancel_token: If set, abort before transcription starts.
        """
        if not audio_bytes or len(audio_bytes) < 1024:
            log.info("stt_audio_too_short", bytes=len(audio_bytes))
            return ""

        if cancel_token and cancel_token.is_cancelled:
            log.info("stt_cancelled_before_start")
            return ""

        try:
            result = await asyncio.to_thread(
                _transcribe_sync, audio_bytes, self._settings
            )

            if cancel_token and cancel_token.is_cancelled:
                log.info("stt_cancelled_after_transcription")
                return ""

            return result
        except Exception as exc:
            log.error("stt_transcription_failed", error=str(exc))
            return ""

    def preload_model(self) -> None:
        """Preload the Whisper model on startup (blocking)."""
        try:
            _get_fw_model(self._settings)
        except Exception as exc:
            log.error("stt_preload_failed", error=str(exc))
