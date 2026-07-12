"""Centralized API access for official third-party integrations.

This module keeps API keys, retries, timeouts, small in-memory caching, and
basic local rate limiting in one place so tools do not each reinvent network
handling.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

from ..config import get_settings

logger = logging.getLogger(__name__)


class APIManagerError(RuntimeError):
    """Raised when a configured API request fails."""


@dataclass
class CachedResponse:
    expires_at: float
    data: dict[str, Any]


@dataclass
class CircuitState:
    failures: int = 0
    opened_at: float = 0.0
    state: str = "closed"


class APIManager:
    """Small synchronous API manager for tool calls.

    Tools run in a worker thread, so synchronous requests are acceptable here.
    """

    _KEY_FIELDS = {
        "youtube": "youtube_data_api_key",
        "newsapi": "news_api_key",
        "gnews": "gnews_api_key",
        "thenewsapi": "thenewsapi_key",
        "google_cse": "google_cse_api_key",
        "spotify": "spotify_client_id",
    }

    _ALLOWED_HOSTS = {
        "www.googleapis.com",
        "googleapis.com",
        "newsapi.org",
        "gnews.io",
        "api.thenewsapi.com",
        "news.google.com",
        "duckduckgo.com",
        "api.duckduckgo.com",
        "music.youtube.com",
        "www.youtube.com",
        "youtube.com",
        "accounts.spotify.com",
        "api.spotify.com",
    }

    def __init__(self) -> None:
        self._cache: dict[str, CachedResponse] = {}
        self._calls: dict[str, list[float]] = {}
        self._health: dict[str, dict[str, Any]] = {}
        self._circuits: dict[str, CircuitState] = {}

    @property
    def settings(self):
        return get_settings()

    def api_key(self, provider: str) -> str:
        """Return the configured key for a provider, or an empty string."""
        field = self._KEY_FIELDS.get(provider.lower())
        if not field:
            return ""
        return str(getattr(self.settings, field, "") or "").strip()

    def is_configured(self, provider: str) -> bool:
        provider = provider.lower()
        if provider == "google_cse":
            return bool(self.api_key(provider) and self.settings.google_cse_cx)
        if provider == "spotify":
            return bool(self.settings.spotify_client_id and self.settings.spotify_client_secret)
        return bool(self.api_key(provider))

    def status(self) -> dict[str, Any]:
        """Return provider configuration and recent health state."""
        return {
            provider: {
                "configured": self.is_configured(provider),
                "last_status": self._health.get(provider, {}).get("status", "unknown"),
                "last_error": self._health.get(provider, {}).get("error", ""),
                "last_checked": self._health.get(provider, {}).get("checked_at", ""),
                "circuit": self._circuit(provider).state,
            }
            for provider in self._KEY_FIELDS
        }

    def get_json(
        self,
        provider: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        cache_ttl: int | None = None,
        retries: int = 1,
    ) -> dict[str, Any]:
        """GET a JSON endpoint with cache, timeout, retry, and rate checks."""
        provider = provider.lower()
        params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        cache_ttl = self.settings.api_cache_ttl_seconds if cache_ttl is None else cache_ttl
        cache_key = self._cache_key(provider, url, params)

        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if cached and cached.expires_at > now:
            return cached.data

        self._check_allowed(url)
        self._check_circuit(provider)
        self._enforce_rate_limit(provider)
        timeout = max(1, int(self.settings.api_timeout_seconds))
        last_error: Exception | None = None

        for attempt in range(retries + 1):
            try:
                response = requests.get(url, params=params, headers=headers, timeout=timeout)
                if response.status_code == 429:
                    raise APIManagerError(f"{provider} rate limit reached")
                response.raise_for_status()
                data = response.json()
                if cache_ttl > 0:
                    self._cache[cache_key] = CachedResponse(now + cache_ttl, data)
                self._health[provider] = {
                    "status": "ok",
                    "error": "",
                    "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                self._record_success(provider)
                return data
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < retries:
                    time.sleep(0.25 * (attempt + 1))

        message = str(last_error) if last_error else "unknown error"
        self._health[provider] = {
            "status": "error",
            "error": message[:300],
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._record_failure(provider)
        logger.warning("%s API request failed: %s", provider, message)
        raise APIManagerError(message)

    def get_text(
        self,
        provider: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        cache_ttl: int | None = None,
        retries: int = 1,
    ) -> str:
        """GET a text endpoint with the same controls as `get_json`."""
        provider = provider.lower()
        params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        cache_ttl = self.settings.api_cache_ttl_seconds if cache_ttl is None else cache_ttl
        cache_key = self._cache_key(provider, url, {**params, "_format": "text"})

        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if cached and cached.expires_at > now:
            return str(cached.data.get("text", ""))

        self._check_allowed(url)
        self._check_circuit(provider)
        self._enforce_rate_limit(provider)
        timeout = max(1, int(self.settings.api_timeout_seconds))
        last_error: Exception | None = None

        for attempt in range(retries + 1):
            try:
                response = requests.get(url, params=params, headers=headers, timeout=timeout)
                if response.status_code == 429:
                    raise APIManagerError(f"{provider} rate limit reached")
                response.raise_for_status()
                text = response.text
                if cache_ttl > 0:
                    self._cache[cache_key] = CachedResponse(now + cache_ttl, {"text": text})
                self._health[provider] = {
                    "status": "ok",
                    "error": "",
                    "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                self._record_success(provider)
                return text
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < retries:
                    time.sleep(0.25 * (attempt + 1))

        message = str(last_error) if last_error else "unknown error"
        self._health[provider] = {
            "status": "error",
            "error": message[:300],
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._record_failure(provider)
        logger.warning("%s API text request failed: %s", provider, message)
        raise APIManagerError(message)

    def _check_allowed(self, url: str) -> None:
        host = (urlparse(url).hostname or "").lower()
        if not host:
            raise APIManagerError(f"Could not parse API URL: {url!r}")
        for allowed in self._ALLOWED_HOSTS:
            if host == allowed or host.endswith("." + allowed):
                return
        raise APIManagerError(f"Outbound API host '{host}' is not allowlisted.")

    def _enforce_rate_limit(self, provider: str) -> None:
        limit = max(1, int(self.settings.api_rate_limit_per_minute))
        now = time.monotonic()
        calls = [t for t in self._calls.get(provider, []) if now - t < 60]
        if len(calls) >= limit:
            raise APIManagerError(f"Local {provider} API rate limit reached.")
        calls.append(now)
        self._calls[provider] = calls

    def _circuit(self, provider: str) -> CircuitState:
        if provider not in self._circuits:
            self._circuits[provider] = CircuitState()
        return self._circuits[provider]

    def _check_circuit(self, provider: str) -> None:
        circuit = self._circuit(provider)
        if circuit.state != "open":
            return
        cooldown = max(1, int(self.settings.api_circuit_cooldown_seconds))
        if time.monotonic() - circuit.opened_at >= cooldown:
            circuit.state = "half_open"
            return
        raise APIManagerError(f"{provider} API circuit is temporarily open.")

    def _record_success(self, provider: str) -> None:
        circuit = self._circuit(provider)
        circuit.failures = 0
        circuit.opened_at = 0.0
        circuit.state = "closed"

    def _record_failure(self, provider: str) -> None:
        circuit = self._circuit(provider)
        circuit.failures += 1
        threshold = max(1, int(self.settings.api_circuit_failure_threshold))
        if circuit.failures >= threshold:
            circuit.state = "open"
            circuit.opened_at = time.monotonic()

    @staticmethod
    def _cache_key(provider: str, url: str, params: dict[str, Any]) -> str:
        raw = json.dumps(
            {"provider": provider, "url": url, "params": params},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


api_manager = APIManager()
