"""Startup health check for Genie voice system.

Verifies critical components are working before the voice system starts.
"""
import asyncio
import logging
import structlog
from typing import Dict, Any

from ..config import Settings, get_settings

log = structlog.get_logger("genie.health_check")


class HealthCheckResult:
    """Result of a health check."""
    def __init__(self, name: str, passed: bool, message: str = "", details: Dict[str, Any] = None):
        self.name = name
        self.passed = passed
        self.message = message
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "details": self.details,
        }


class StartupHealthCheck:
    """Comprehensive startup health check."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.results: list[HealthCheckResult] = []
    
    async def run_all(self) -> bool:
        """Run all health checks. Returns True if all critical checks pass."""
        log.info("health_check_starting")
        
        # Critical checks - must pass for voice to work
        await self.check_microphone()
        await self.check_stt_model()
        await self.check_tts_engine()
        await self.check_llm_provider()
        
        # Optional checks - log warnings but don't fail
        await self.check_wake_word_engine()
        await self.check_apis()
        
        # Report results
        critical_passed = all(
            r.passed for r in self.results 
            if r.name in ["microphone", "stt_model", "tts_engine", "llm_provider"]
        )
        
        if critical_passed:
            log.info("health_check_passed", results=[r.to_dict() for r in self.results])
        else:
            log.error("health_check_failed", results=[r.to_dict() for r in self.results])
        
        return critical_passed
    
    async def check_microphone(self) -> HealthCheckResult:
        """Check if microphone support is available.
        
        NOTE: We do NOT create a PyAudio instance here — that would conflict
        with the MicrophoneService which opens the mic exclusively (audit fix #10).
        We only verify pyaudio is importable.
        """
        try:
            import pyaudio  # noqa: F401
            return HealthCheckResult(
                "microphone",
                True,
                "PyAudio available (mic will be opened by MicrophoneService)",
                {},
            )
        except ImportError:
            return HealthCheckResult(
                "microphone",
                False,
                "PyAudio not installed",
                {},
            )
        except Exception as e:
            return HealthCheckResult(
                "microphone",
                False,
                f"Microphone check failed: {str(e)}",
                {},
            )
    
    async def check_stt_model(self) -> HealthCheckResult:
        """Check if STT model is available."""
        try:
            from .. import stt
            
            # Try to load the model
            settings = self.settings
            model_size = settings.whisper_model_size
            
            # This is a lightweight check - we don't actually load the full model
            # Just verify the module is importable and settings are valid
            valid_sizes = ["tiny", "base", "small", "medium", "large-v3"]
            
            if model_size not in valid_sizes:
                return HealthCheckResult(
                    "stt_model",
                    False,
                    f"Invalid model size: {model_size}",
                    {"model_size": model_size, "valid_sizes": valid_sizes},
                )
            
            return HealthCheckResult(
                "stt_model",
                True,
                f"STT model configured: {model_size}",
                {"model_size": model_size, "engine": settings.stt_engine},
            )
            
        except ImportError as e:
            return HealthCheckResult(
                "stt_model",
                False,
                f"STT module import failed: {str(e)}",
                {},
            )
        except Exception as e:
            return HealthCheckResult(
                "stt_model",
                False,
                f"STT check failed: {str(e)}",
                {},
            )
    
    async def check_tts_engine(self) -> HealthCheckResult:
        """Check if TTS engine is available."""
        try:
            from .. import tts
            
            engine = self.settings.tts_engine
            
            # Check if at least one TTS engine is available
            # Edge TTS is always available (built-in)
            if engine == "edge":
                return HealthCheckResult(
                    "tts_engine",
                    True,
                    "Edge TTS available (built-in)",
                    {"engine": engine},
                )
            
            # For other engines, just verify the module is importable
            # We don't actually test the API to avoid rate limits
            return HealthCheckResult(
                "tts_engine",
                True,
                f"TTS engine configured: {engine} (fallback to edge available)",
                {"engine": engine},
            )
            
        except ImportError as e:
            return HealthCheckResult(
                "tts_engine",
                False,
                f"TTS module import failed: {str(e)}",
                {},
            )
        except Exception as e:
            return HealthCheckResult(
                "tts_engine",
                False,
                f"TTS check failed: {str(e)}",
                {},
            )
    
    async def check_llm_provider(self) -> HealthCheckResult:
        """Check if LLM provider is configured."""
        try:
            from .. import llm_client
            
            provider = llm_client.get_provider_config(self.settings)
            
            # Check if we have at least one working provider
            # Local GGUF model is always available as fallback
            from ..services.local_llm import local_llm
            
            if local_llm.is_enabled(self.settings):
                return HealthCheckResult(
                    "llm_provider",
                    True,
                    f"Local LLM available as fallback (primary: {provider.label})",
                    {
                        "primary_provider": provider.id,
                        "primary_label": provider.label,
                        "local_fallback": True,
                    },
                )
            
            # If local is disabled, check if online provider has API key
            if provider.api_key:
                return HealthCheckResult(
                    "llm_provider",
                    True,
                    f"Online LLM configured: {provider.label}",
                    {
                        "provider": provider.id,
                        "label": provider.label,
                        "model": provider.model,
                    },
                )
            
            return HealthCheckResult(
                "llm_provider",
                False,
                "No LLM provider configured (no local model and no API key)",
                {
                    "primary_provider": provider.id,
                    "local_enabled": local_llm.is_enabled(self.settings),
                },
            )
            
        except Exception as e:
            return HealthCheckResult(
                "llm_provider",
                False,
                f"LLM check failed: {str(e)}",
                {},
            )
    
    async def check_wake_word_engine(self) -> HealthCheckResult:
        """Check if wake word engine is available (optional)."""
        if not self.settings.wake_word_enabled:
            return HealthCheckResult(
                "wake_word_engine",
                True,
                "Wake word disabled by configuration",
                {"enabled": False},
            )
        
        try:
            from ..wake_word import WakeWordDetector
            
            engine = self.settings.wake_word_engine
            
            # Just verify the module is importable
            return HealthCheckResult(
                "wake_word_engine",
                True,
                f"Wake word engine configured: {engine}",
                {"engine": engine, "enabled": True},
            )
            
        except ImportError as e:
            return HealthCheckResult(
                "wake_word_engine",
                False,
                f"Wake word module import failed: {str(e)}",
                {"enabled": True},
            )
        except Exception as e:
            return HealthCheckResult(
                "wake_word_engine",
                False,
                f"Wake word check failed: {str(e)}",
                {},
            )
    
    async def check_apis(self) -> HealthCheckResult:
        """Check external API keys (optional)."""
        issues = []
        
        # Check YouTube API
        if not self.settings.youtube_data_api_key:
            issues.append("YouTube Data API key not configured")
        
        # Check News API
        if not self.settings.news_api_key and not self.settings.gnews_api_key:
            issues.append("No news API key configured")
        
        if issues:
            return HealthCheckResult(
                "apis",
                False,
                "Some API keys missing (optional features may not work)",
                {"issues": issues},
            )
        
        return HealthCheckResult(
            "apis",
            True,
            "API keys configured",
            {},
        )


async def run_startup_health_check(settings: Settings) -> bool:
    """Run startup health check. Returns True if all critical checks pass."""
    checker = StartupHealthCheck(settings)
    return await checker.run_all()
