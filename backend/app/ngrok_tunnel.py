"""Ngrok tunneling: expose the local FastAPI server over a public HTTPS URL.

The mobile web client connects to this URL (after entering the PIN), so you
can drive Genie from your phone from anywhere. A free ngrok authtoken gives
stable tunnels and removes the visitor warning page.
"""
from __future__ import annotations

import logging
from typing import Optional

from .config import Settings, get_settings

log = logging.getLogger("genie.ngrok")

_tunnel = None
_public_url: Optional[str] = None


def start_tunnel(port: int, settings: Settings | None = None) -> Optional[str]:
    """Open a tunnel to `port` and return the public HTTPS URL (or None)."""
    global _tunnel, _public_url
    settings = settings or get_settings()

    if not settings.ngrok_enabled:
        log.info("Ngrok disabled via NGROK_ENABLED=false.")
        return None

    try:
        from pyngrok import ngrok, conf
    except ImportError:
        log.warning("pyngrok not installed; skipping tunnel.")
        return None

    try:
        if settings.ngrok_authtoken:
            conf.get_default().auth_token = settings.ngrok_authtoken
        if settings.ngrok_region:
            conf.get_default().region = settings.ngrok_region

        # `connect` returns the public URL string in pyngrok 7.x.
        _public_url = ngrok.connect(
            addr=port,
            proto="http",
            bind_tls=True,            # HTTPS-only
        ).public_url
        _tunnel = True
        log.info("Ngrok tunnel live at %s", _public_url)
        return _public_url
    except Exception as e:  # noqa: BLE001
        log.error("Ngrok tunnel failed to start: %s", e)
        return None


def get_public_url() -> Optional[str]:
    """The current public URL, if a tunnel is open."""
    return _public_url


def stop_tunnel() -> None:
    """Tear down the tunnel (called on shutdown)."""
    global _tunnel, _public_url
    try:
        if _tunnel:
            from pyngrok import ngrok
            ngrok.kill()
    except Exception:  # noqa: BLE001
        pass
    _tunnel = None
    _public_url = None
