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
    gemini_temperature: float = 0.4    # lower = more accurate, less hallucination
    gemini_max_tokens: int = 8192      # higher = complete answers, no truncation

    # --- Offline LLM fallback --------------------------------------------
    local_llm_enabled: bool = True
    local_llm_model_path: str = ""          # blank = auto-scan data/models/*.gguf
    local_llm_legacy_site_packages: str = r"D:\GenieAI\backend\.venv\Lib\site-packages"
    local_llm_n_ctx: int = 4096
    local_llm_max_tokens: int = 700
    local_llm_temperature: float = 0.55
    local_llm_top_p: float = 0.9
    local_llm_n_gpu_layers: int = 0         # CPU-safe default; set -1 for GPU build

    # --- Speech-to-text (faster-whisper, local by default) ----------------
    stt_engine: str = "faster_whisper"     # or "whisper_api"
    whisper_model_size: str = "small"      # tiny|base|small|medium|large-v3
    stt_device: str = "auto"               # auto -> cuda if available else cpu
    stt_compute_type: str = "auto"         # auto -> int8_float16 on GPU else int8
    stt_language: Optional[str] = None     # None = auto-detect; e.g. "en", "hi"
    openai_api_key: str = ""               # only if stt_engine == "whisper_api"

    # --- Text-to-speech ---------------------------------------------------
    tts_engine: str = "elevenlabs"         # "edge", "elevenlabs", or "gemini_live"
    edge_voice: str = "en-US-AriaNeural"   # female, expressive
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "Xb7hH8MSUJpSbSDYk0k2"
    elevenlabs_model: str = "eleven_multilingual_v2"
    tts_sample_rate: int = 24000
    gemini_live_model: str = "gemini-3.1-flash-live-preview"
    gemini_live_voice_name: str = "Aoede"
    gemini_live_style: str = (
        "Speak naturally, warmly, and briefly. Use human pacing, small pauses, "
        "and the same language as the text. Do not add extra content."
    )

    # --- Ngrok / mobile tunnel -------------------------------------------
    ngrok_enabled: bool = True
    ngrok_authtoken: str = ""              # recommended for stable tunnels
    ngrok_region: str = ""                 # "" = auto; e.g. "us", "eu", "ap"

    # --- External APIs ----------------------------------------------------
    # YouTube Music has no official public API; we use YouTube Data API for
    # official search metadata and optionally ytmusicapi for richer metadata.
    youtube_data_api_key: str = ""
    youtube_region_code: str = "IN"
    youtube_music_provider: str = "auto"      # auto|youtube_data|ytmusicapi|browser
    news_api_key: str = ""                 # NewsAPI.org
    gnews_api_key: str = ""                # GNews.io
    thenewsapi_key: str = ""               # TheNewsAPI.com
    google_cse_api_key: str = ""           # Google Custom Search JSON API
    google_cse_cx: str = ""                # Programmable Search Engine ID
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    news_default_country: str = "in"
    news_default_language: str = "en"
    api_timeout_seconds: int = 10
    api_cache_ttl_seconds: int = 300
    api_rate_limit_per_minute: int = 45
    api_circuit_failure_threshold: int = 3
    api_circuit_cooldown_seconds: int = 60

    # --- Security: 4-digit PIN -------------------------------------------
    # If not provided, a fresh one is generated at startup and printed/logged.
    genie_pin: str = ""

    # --- Session tokens ---------------------------------------------------
    session_token_ttl_seconds: int = 60 * 60 * 12  # 12h per authenticated WS

    # --- Wake word detection (optional, hands-free activation) -----------
    wake_word_enabled: bool = False        # set to True to enable
    wake_word_engine: str = "simple"       # "porcupine", "vosk", or "simple"
    wake_word_keywords: list[str] = ["hey genie", "okay genie", "hi genie", "genie"]

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
