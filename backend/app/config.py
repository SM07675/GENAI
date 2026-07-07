"""Central configuration for Genie's backend.

All secrets and tunables are loaded from environment variables (optionally a
`.env` file via pydantic-settings). Nothing sensitive is hard-coded.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed app settings.

    All fields can be overridden by environment variables of the same (upper)
    name, or via a `.env` file in `backend/`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Server -----------------------------------------------------------
    host: str = "127.0.0.1"          # bind address; 0.0.0.0 if exposing LAN
    port: int = 8765                  # FastAPI / WS port
    cors_origins: list[str] = ["*"]   # tightened in prod

    # --- Gemini (OpenAI-compatible endpoint) -----------------------------
    gemini_api_key: str = ""             # required at runtime; checked in main
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.6
    gemini_max_tokens: int = 4096

    # --- Speech-to-text (faster-whisper, local by default) ----------------
    stt_engine: str = "faster_whisper"     # or "whisper_api"
    whisper_model_size: str = "small"      # tiny|base|small|medium|large-v3
    stt_device: str = "auto"               # auto -> cuda if available else cpu
    stt_compute_type: str = "auto"         # auto -> int8_float16 on GPU else int8
    stt_language: Optional[str] = None     # None = auto-detect; e.g. "en", "hi"
    openai_api_key: str = ""               # only if stt_engine == "whisper_api"

    # --- Text-to-speech ---------------------------------------------------
    tts_engine: str = "edge"               # "edge" (default) or "elevenlabs"
    edge_voice: str = "en-US-AriaNeural"   # female, expressive
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    elevenlabs_model: str = "eleven_multilingual_v2"
    tts_sample_rate: int = 24000

    # --- Ngrok / mobile tunnel -------------------------------------------
    ngrok_enabled: bool = True
    ngrok_authtoken: str = ""              # recommended for stable tunnels
    ngrok_region: str = ""                 # "" = auto; e.g. "us", "eu", "ap"

    # --- Security: 4-digit PIN -------------------------------------------
    # If not provided, a fresh one is generated at startup and printed/logged.
    genie_pin: str = ""

    # --- Session tokens ---------------------------------------------------
    session_token_ttl_seconds: int = 60 * 60 * 12  # 12h per authenticated WS

    @property
    def effective_pin(self) -> str:
        """PIN to use, generating a random one if none was configured."""
        return self.genie_pin or _get_generated_pin()


# Module-level PIN cache: generated once per process, outside Pydantic's
# attribute machinery (which intercepts __setattr__ on model instances).
_PIN_CACHE: dict[str, str] = {}


def _get_generated_pin() -> str:
    """Return the process-lifetime auto-generated 4-digit PIN."""
    if "pin" not in _PIN_CACHE:
        import secrets
        _PIN_CACHE["pin"] = f"{secrets.randbelow(10000):04d}"
    return _PIN_CACHE["pin"]


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
