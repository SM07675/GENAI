"""
Speech-to-Text Engine.

Provides a swappable STT interface. The concrete implementation uses
faster-whisper for low-latency, CPU-friendly local transcription.

Architecture
------------
STTProvider (ABC)
  └─ WhisperSTTProvider  — local faster-whisper (default)
  └─ DeepgramSTTProvider — cloud STT stub (drop-in when API key is set)

STTEngine wraps a provider and adds:
  - Audio buffer accumulation (frames collected during a speech segment)
  - Partial transcript callbacks (emitted during transcription)
  - Language auto-detection support

Usage::

    engine = STTEngine.from_settings()
    result = await engine.transcribe(audio_frames)
    print(result.text, result.confidence)
"""

from __future__ import annotations

import asyncio
import io
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Awaitable

from app.core.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class TranscriptResult:
    """Result of a transcription request."""
    text: str
    confidence: float
    language: str
    is_final: bool
    duration_ms: float


PartialCallback = Callable[[str, float], Awaitable[None]]


# ── Abstract Base ─────────────────────────────────────────────────────────────

class STTProvider(ABC):
    """Abstract speech-to-text provider.

    Implementors must be stateless — all audio state is managed by STTEngine.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        ...

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """True if provider dependencies are installed/configured."""
        ...

    @abstractmethod
    async def transcribe(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16_000,
        language: str = "en",
    ) -> TranscriptResult:
        """Transcribe raw PCM bytes into text.

        Args:
            audio_bytes: Raw 16-bit signed little-endian PCM.
            sample_rate: Audio sample rate (typically 16000 Hz).
            language: ISO 639-1 language code or "auto".

        Returns:
            TranscriptResult with text and confidence.
        """
        ...


# ── Whisper Provider ──────────────────────────────────────────────────────────

class WhisperSTTProvider(STTProvider):
    """Local speech-to-text using faster-whisper.

    The model is loaded lazily on first use to avoid blocking application
    startup. It is cached as a class-level singleton.

    Args:
        model_size: One of: tiny, tiny.en, base, base.en, small, medium, large-v3.
        compute_type: int8 (CPU), float16 (CUDA), or auto.
    """

    _model = None  # class-level singleton
    _model_lock = asyncio.Lock()

    def __init__(self, model_size: str = "tiny", compute_type: str = "int8") -> None:
        self._model_size = model_size
        self._compute_type = compute_type

    @property
    def name(self) -> str:
        return "faster_whisper"

    @property
    def is_configured(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False

    async def _get_model(self):
        """Lazily load and cache the Whisper model."""
        async with WhisperSTTProvider._model_lock:
            if WhisperSTTProvider._model is None:
                logger.info(
                    "Loading Whisper model",
                    model_size=self._model_size,
                    compute_type=self._compute_type,
                )
                loop = asyncio.get_event_loop()
                WhisperSTTProvider._model = await loop.run_in_executor(
                    None, self._load_model
                )
                logger.info("Whisper model loaded", model_size=self._model_size)
        return WhisperSTTProvider._model

    def _load_model(self):
        from faster_whisper import WhisperModel
        return WhisperModel(
            self._model_size,
            compute_type=self._compute_type,
            cpu_threads=4,
        )

    @staticmethod
    def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
        """Wrap raw PCM bytes in a WAV container for Whisper."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        return buf.getvalue()

    async def transcribe(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16_000,
        language: str = "en",
    ) -> TranscriptResult:
        import time
        start = time.monotonic()

        if len(audio_bytes) < 1600:  # < 50ms of audio
            return TranscriptResult(
                text="", confidence=0.0, language=language,
                is_final=True, duration_ms=0.0,
            )

        model = await self._get_model()
        wav_bytes = self._pcm_to_wav(audio_bytes, sample_rate)

        # Run inference in executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        segments, info = await loop.run_in_executor(
            None,
            lambda: model.transcribe(
                io.BytesIO(wav_bytes),
                language=None if language == "auto" else language,
                beam_size=3,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 200},
            ),
        )

        texts = []
        avg_confidence = 0.0
        count = 0
        for seg in segments:
            text = seg.text.strip()
            if text:
                texts.append(text)
                # faster-whisper returns avg_logprob, convert to ~confidence
                avg_confidence += min(1.0, max(0.0, (seg.avg_logprob + 1.0)))
                count += 1

        full_text = " ".join(texts).strip()
        confidence = (avg_confidence / count) if count > 0 else 0.0
        elapsed_ms = (time.monotonic() - start) * 1000

        logger.debug(
            "STT transcription complete",
            text_preview=full_text[:60],
            confidence=round(confidence, 3),
            duration_ms=round(elapsed_ms, 1),
        )

        return TranscriptResult(
            text=full_text,
            confidence=confidence,
            language=info.language if info else language,
            is_final=True,
            duration_ms=elapsed_ms,
        )


# ── Deepgram Stub ─────────────────────────────────────────────────────────────

class DeepgramSTTProvider(STTProvider):
    """Cloud STT via Deepgram (stub — requires DEEPGRAM_API_KEY env var)."""

    @property
    def name(self) -> str:
        return "deepgram"

    @property
    def is_configured(self) -> bool:
        import os
        return bool(os.getenv("DEEPGRAM_API_KEY"))

    async def transcribe(
        self, audio_bytes: bytes, sample_rate: int = 16_000, language: str = "en"
    ) -> TranscriptResult:
        raise NotImplementedError(
            "Deepgram STT provider is a stub. Implement using the deepgram-sdk package."
        )


# ── Engine (DI wrapper) ───────────────────────────────────────────────────────

class STTEngine:
    """Stateful STT engine that accumulates frames and calls the provider.

    Args:
        provider: Any STTProvider implementation.
        language: Default transcription language.
    """

    def __init__(self, provider: STTProvider, language: str = "en") -> None:
        self._provider = provider
        self._language = language
        self._buffer = bytearray()

    @classmethod
    def from_settings(cls) -> "STTEngine":
        """Construct an STTEngine from application settings."""
        settings = get_settings()
        provider = WhisperSTTProvider(
            model_size=settings.stt_model_size,
            compute_type=settings.stt_compute_type,
        )
        return cls(provider=provider, language=settings.stt_language)

    def accumulate(self, frame: bytes) -> None:
        """Add a PCM frame to the internal buffer."""
        self._buffer.extend(frame)

    def clear_buffer(self) -> None:
        """Discard buffered audio (e.g. after interruption)."""
        self._buffer.clear()

    async def transcribe_buffer(
        self,
        on_partial: PartialCallback | None = None,
    ) -> TranscriptResult:
        """Transcribe all buffered audio and clear the buffer.

        Args:
            on_partial: Optional async callback(text, confidence) invoked
                        once with an interim result (if supported by provider).

        Returns:
            Final TranscriptResult.
        """
        audio = bytes(self._buffer)
        self.clear_buffer()

        if not audio:
            return TranscriptResult(
                text="", confidence=0.0, language=self._language,
                is_final=True, duration_ms=0.0,
            )

        result = await self._provider.transcribe(
            audio_bytes=audio,
            sample_rate=16_000,
            language=self._language,
        )

        if on_partial and result.text:
            await on_partial(result.text, result.confidence)

        return result

    @property
    def buffer_bytes(self) -> int:
        """Number of bytes currently in the audio buffer."""
        return len(self._buffer)

    @property
    def provider_name(self) -> str:
        return self._provider.name
