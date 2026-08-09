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

    # --- Main LLM Provider ------------------------------------------------
    llm_provider: str = "nvidia"         # "nvidia" (default), "openrouter", "gemini", "grok"/"xai", or "groq"

    # --- OpenRouter (OpenAI-compatible, access to 100s of models) ---------
    # Get a free key from https://openrouter.ai/keys
    # Free tier: many models at $0/token (e.g. deepseek, qwen, mistral, llama)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    
    # Model fallback pool
    openrouter_primary_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    openrouter_fallback_models: list[str] = ["qwen/qwen-2.5-72b-instruct:free", "google/gemini-2.0-flash-exp:free"]
    
    # Rate limiting and cooldowns
    openrouter_rpm: int = 5
    openrouter_max_retries_per_model: int = 1
    openrouter_cooldown_seconds: int = 120
    
    openrouter_temperature: float = 0.4
    openrouter_max_tokens: int = 8192
    openrouter_timeout_seconds: float = 25.0
    openrouter_site_url: str = "http://localhost:8765"
    openrouter_site_name: str = "Genie AI Assistant"

    # --- Gemini (OpenAI-compatible endpoint) -----------------------------
    gemini_api_key: str = ""             # required at runtime if provider is gemini; checked in main
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.4    # lower = more accurate, less hallucination
    gemini_max_tokens: int = 8192      # higher = complete answers, no truncation
    gemini_timeout_seconds: float = 60.0

    # --- Grok / xAI (OpenAI-compatible endpoint) -------------------------
    # xAI documents XAI_API_KEY; GROK_API_KEY is accepted as a convenient alias.
    xai_api_key: str = ""
    grok_api_key: str = ""
    grok_base_url: str = "https://api.x.ai/v1"
    grok_model: str = "grok-4.5"
    grok_temperature: float = 0.35
    grok_max_tokens: int = 8192
    grok_timeout_seconds: float = 120.0

    # --- Groq Cloud (OpenAI-compatible endpoint) -------------------------
    groq_api_key: str = ""               # required at runtime if provider is groq; checked in main
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"
    groq_temperature: float = 0.4
    groq_max_tokens: int = 4096
    groq_timeout_seconds: float = 60.0

    # --- Nvidia (OpenAI-compatible endpoint) -----------------------------
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "google/gemma-4-31b-it"
    nvidia_temperature: float = 1.0
    nvidia_max_tokens: int = 16384
    nvidia_timeout_seconds: float = 60.0
    nvidia_enable_thinking: bool = False   # False = instant fast voice response, True = deep reasoning

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
    
    # --- VAD (Voice Activity Detection) Parameters ------------------------
    vad_threshold: float = 0.35
    vad_min_speech_duration_ms: int = 150
    vad_min_silence_duration_ms: int = 500
    vad_speech_pad_ms: int = 300

    # --- Text-to-speech ---------------------------------------------------
    # Engine priority:
    #   "auto"    → try Kokoro (local GPU) first, fall back to Edge TTS
    #   "kokoro"  → local GPU only (ONNX, no numba, no DLL issues)
    #   "edge"    → Microsoft Edge TTS cloud only
    tts_engine: str = "auto"

    # Kokoro TTS settings
    tts_kokoro_voice: str = "af_heart"    # warm natural female (af_heart, af_nova, af_sky)
    tts_kokoro_speed: float = 1.0          # 1.0 = normal; 0.8 = slower; 1.2 = faster
    tts_kokoro_lang: str = "a"             # "a"=American EN, "b"=British EN, "h"=Hindi(exp)

    # Edge TTS fallback voice (hi-IN-SwaraNeural supports English and Hindi seamlessly)
    tts_edge_voice: str = "hi-IN-SwaraNeural"

    # Chatterbox TTS settings (best bilingual human voice)
    tts_chatterbox_enabled: bool = True

    # ElevenLabs TTS settings (best humanized, multilingual)
    elevenlabs_api_key: str = ""
    tts_elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb" # George (or any preferred ID)
    tts_elevenlabs_model: str = "eleven_multilingual_v2" # Supports English and Hindi natively

    # Audio output
    tts_sample_rate: int = 24000
    tts_use_fp16: bool = True              # enable FP16 if model supports it

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
    tavily_api_key: str = ""           # Tavily Search API (https://tavily.com) — priority-1 web search
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
    wake_word_enabled: bool = True         # enabled by default
    wake_word_engine: str = "vosk"         # "porcupine", "vosk", or "simple"
    wake_word_keywords: list[str] = ["hey genie", "okay genie", "hi genie", "hello genie", "ok genie", "genie", "wake up"]
    wake_word_cooldown_ms: int = 1500

    # --- Continuous Conversation ---
    follow_up_mode: bool = True
    follow_up_timeout_seconds: int = 8
    
    # --- Recovery ---
    voice_recovery_enabled: bool = True
    voice_max_retries: int = 3

    # --- Companion Mode ---------------------------------------------------
    # Observation intervals per sub-mode (seconds between screen captures)
    companion_observation_interval_gaming: int = 3
    companion_observation_interval_coding: int = 8
    companion_observation_interval_writing: int = 12
    companion_observation_interval_general: int = 10
    # Vision API rate control (degrades interval, never crashes on ceiling)
    companion_max_vision_calls_per_minute: int = 20
    companion_observation_interval: int = 3
    companion_vision_enabled: bool = True
    # Vision provider: "nvidia" (default: Nemotron 12B v2 VL), "gemini", "openai", "local" (future)
    companion_vision_provider: str = "nvidia"
    companion_vision_model: str = "nvidia/nemotron-nano-12b-v2-vl"
    companion_vision_api_key: str = ""
    companion_vision_confidence_threshold: float = 0.65
    # Default personality preset: friendly | hype | funny | coach | quiet | default
    companion_default_personality: str = "default"

    # --- v12: Barge-In Feature Flag (instant rollback to v11 behaviour) ----
    # Set ENABLE_BARGE_IN=false in .env to revert to manual-only cancellation.
    enable_barge_in: bool = True

    # --- v12: Two-Tier VAD Endpointing ------------------------------------
    # Short timeout fires when the last words sound like a finished sentence.
    # Long timeout fires when the utterance might still continue (trailing thought).
    vad_endpointing_short_ms: int = 500    # e.g. "What's the time?" → 500ms
    vad_endpointing_long_ms: int = 900     # e.g. "and... actually—" → 900ms

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
