from __future__ import annotations

import io
import logging
import os
from typing import Optional

import structlog

from .config import Settings, get_settings

log = structlog.get_logger("genie.stt")

_fw_model = None  # cached faster-whisper model


def _ensure_av_dlls() -> None:
    """Register av's bundled FFmpeg DLL directory and nvidia CUDA DLLs on Windows.

    av._core is a C extension that links against FFmpeg DLLs bundled inside
    the av.libs package directory. On Windows, these DLLs and CUDA DLLs (cublas, cudnn)
    must be explicitly registered via os.add_dll_directory() before importing faster_whisper.
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




# ─────────────────────────────────────────────────────────────────────────────
# faster-whisper (local, default)
# ─────────────────────────────────────────────────────────────────────────────
def _resolve_device_compute(settings: Settings) -> tuple[str, str]:
    device  = settings.stt_device
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
    log.info("whisper_loading", model=settings.whisper_model_size, device=device, compute=compute)

    try:
        _fw_model = WhisperModel(
            settings.whisper_model_size,
            device=device,
            compute_type=compute,
        )
        log.info("whisper_ready", device=device, compute=compute)
        return _fw_model
    except Exception as exc:
        log.warning("whisper_cuda_failed_falling_back_to_cpu", error=str(exc))
        _fw_model = WhisperModel(
            settings.whisper_model_size,
            device="cpu",
            compute_type="int8",
        )
        log.info("whisper_ready", device="cpu", compute="int8")
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

        # Noise gate: reject frames that are pure silence/noise after conversion.
        # RMS < 0.002 is below the noise floor of any real utterance.
        rms = float(np.sqrt(np.mean(audio_array ** 2)))
        if rms < 0.002:
            log.info("stt_rejected_silent_audio", rms=round(rms, 5))
            return ""

        try:
            segments, _info = model.transcribe(
                audio_array,
                language=settings.stt_language or None,
                vad_filter=True,
                vad_parameters={
                    "threshold": max(0.3, settings.vad_threshold - 0.05),
                    "min_silence_duration_ms": settings.vad_min_silence_duration_ms,
                    "min_speech_duration_ms": max(100, settings.vad_min_speech_duration_ms),
                    "speech_pad_ms": settings.vad_speech_pad_ms,
                },
                beam_size=5,
                best_of=3,
                temperature=0.0,
                initial_prompt=(
                    "Genie, YouTube, Spotify, GitHub, Google, Gmail, Chrome, "
                    "Visual Studio Code, VS Code, Python, FastAPI, React, Next.js, "
                    "OpenAI, Mistral, Groq, Qwen, Llama, WhatsApp, Windows, "
                    "Hey Genie, okay Genie, play music, open app, set reminder."
                ),
                condition_on_previous_text=False,
                no_speech_threshold=0.45,
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,
            )
            # Get raw segments list and info — evaluate language confidence
            segments_list = list(segments)
            result = "".join(seg.text for seg in segments_list).strip()

            # Language confidence enforcement: if Whisper's auto-detection is below
            # the confidence threshold, fall back to the user's preferred language.
            # This prevents English audio from being mis-labelled as Hindi (etc.)
            # with low confidence (~0.57) which can corrupt the transcript meaning.
            LANG_CONFIDENCE_THRESHOLD = 0.75
            detected_lang = getattr(_info, "language", None) or "en"
            lang_prob = getattr(_info, "language_probability", 1.0)

            preferred_lang = (settings.stt_language or "").strip().lower() or "en"

            if lang_prob < LANG_CONFIDENCE_THRESHOLD and detected_lang != preferred_lang:
                log.info(
                    "stt_language_detection_low_confidence",
                    detected=detected_lang,
                    probability=round(lang_prob, 3),
                    overriding_to=preferred_lang,
                )
                detected_lang = preferred_lang

            log.info(
                "stt_transcribed",
                text=result[:200],
                language=detected_lang,
                language_probability=round(lang_prob, 3),
            )

        except Exception as exc:
            log.warning("stt_transcribe_cuda_failed_trying_cpu", error=str(exc))
            from faster_whisper import WhisperModel
            cpu_model = WhisperModel(settings.whisper_model_size, device="cpu", compute_type="int8")
            segments2, _info2 = cpu_model.transcribe(audio_array, beam_size=3)
            result = "".join(seg.text for seg in segments2).strip()

        # Post-filter: reject common hallucination artifacts from silence
        _HALLUCINATIONS = {
            "you", ".", "thanks for watching", "thank you", "thank you.",
            "thanks.", "bye", "bye.", "[music]", "[applause]", "[noise]",
            "[blank_audio]", "[ Silence ]",
        }
        if result.lower().strip(" .") in _HALLUCINATIONS or len(result) < 2:
            log.info("stt_hallucination_filtered", text=result)
            return ""

        return result
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
