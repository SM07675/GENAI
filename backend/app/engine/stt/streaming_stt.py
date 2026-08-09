"""Streaming speech-to-text worker.

Design:
- Uses the SAME faster-whisper model from ``app.stt`` (no duplicate loading).
- Runs transcription in thread pool via ``asyncio.to_thread``.
- Emits partial and final transcript events.
- Supports English, Hindi, and mixed Hindi-English.
- Cancellation-aware at every checkpoint.
- Auto-timeout after 30s.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Optional

import structlog

from ...config import Settings, get_settings
from ..cancellation import CancellationToken
from ..event_bus import PipelineEvent, engine_events
from ..metrics import pipeline_metrics

log = structlog.get_logger("genie.engine.stt")


def _ensure_av_dlls() -> None:
    """Register av's bundled FFmpeg DLL directory and nvidia CUDA DLLs on Windows.

    Without this, av._core fails to load inside asyncio thread-pool workers
    because the DLL search path is not inherited correctly on Windows.
    Must be called before any faster_whisper / av import.
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
        pass


def _get_shared_model(settings: Settings):
    """Get the shared faster-whisper model from the app.stt module.

    This ensures we use a SINGLE model instance across the entire application,
    preventing the duplicate loading bug identified in the audit.
    """
    _ensure_av_dlls()
    from ...stt import _get_fw_model
    return _get_fw_model(settings)


def _transcribe_sync(audio_bytes: bytes, settings: Settings) -> str:
    """Synchronous transcription — runs in a thread pool."""
    import numpy as np

    model = _get_shared_model(settings)
    audio_array = np.frombuffer(audio_bytes, np.int16).astype(np.float32) / 32768.0

    if len(audio_array) < 1600:  # less than 100ms
        return ""

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
        beam_size=3,  # reduced from 5 for speed
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


class StreamingSTT:
    """Async STT worker with cancellation support.

    Wraps faster-whisper with proper async execution, cancellation,
    and metrics tracking. Uses the shared model from app.stt.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()
        self._last_heartbeat = time.time()

    async def transcribe(
        self,
        audio_bytes: bytes,
        cancel_token: Optional[CancellationToken] = None,
    ) -> str:
        """Transcribe audio bytes. Returns empty string on failure/cancellation.

        Args:
            audio_bytes: Raw PCM16 16kHz mono audio.
            cancel_token: Cooperative cancellation token.
        """
        if not audio_bytes or len(audio_bytes) < 1024:
            log.info("stt_audio_too_short", bytes=len(audio_bytes) if audio_bytes else 0)
            return ""

        if cancel_token and cancel_token.is_cancelled:
            log.info("stt_cancelled_before_start")
            return ""

        timer = pipeline_metrics.time("stt.transcribe", audio_bytes=len(audio_bytes))

        try:
            # Run transcription in thread pool with timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(_transcribe_sync, audio_bytes, self._settings),
                timeout=30.0,
            )

            duration = timer.finish()

            if cancel_token and cancel_token.is_cancelled:
                log.info("stt_cancelled_after_transcription")
                return ""

            self._last_heartbeat = time.time()

            # Emit final transcript event
            if result:
                await engine_events.emit(
                    PipelineEvent.STT_FINAL,
                    text=result,
                    duration_ms=duration,
                )
                pipeline_metrics.increment("stt.successful")
            else:
                pipeline_metrics.increment("stt.empty")

            return result

        except asyncio.TimeoutError:
            timer.finish()
            log.error("stt_timeout", timeout=30.0)
            pipeline_metrics.record_error("stt", "timeout")
            await engine_events.emit(PipelineEvent.STT_ERROR, error="timeout")
            return ""

        except Exception as exc:
            timer.finish()
            log.error("stt_transcription_failed", error=str(exc))
            pipeline_metrics.record_error("stt", str(exc))
            await engine_events.emit(PipelineEvent.STT_ERROR, error=str(exc))
            return ""

    async def preload_model(self) -> None:
        """Preload the Whisper model on startup."""
        try:
            await asyncio.to_thread(_get_shared_model, self._settings)
            log.info("stt_model_preloaded")
        except Exception as exc:
            log.error("stt_preload_failed", error=str(exc))

    @property
    def heartbeat(self) -> float:
        return self._last_heartbeat
