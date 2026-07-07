"""Web & social tools: open direct URLs and deep-link into chats.

`open_url` is the browser fallback target for the "Instagram problem"
guardrail — when a native app isn't installed, the orchestrator (per the
system prompt) chains here instead of failing.
"""
from __future__ import annotations

import urllib.parse
import webbrowser

from ..schemas import ToolResult
from .registry import tool


def _open(url: str) -> None:
    """Open `url` in the user's default browser, non-blocking."""
    # webbrowser.open returns once the launch command is dispatched.
    webbrowser.open(url, new=2)  # new=2 -> new tab when possible


@tool
def open_url(url: str) -> ToolResult:
    """Open a specific website by its exact URL (e.g. instagram.com, lmarena.ai). Use this when the user wants a direct site, not a search.

    :param url: Fully-qualified URL or bare domain (we normalize it).
    """
    if not url:
        return ToolResult(status="error", message="No URL provided.")
    # Normalize: add scheme if the user said "instagram.com".
    target = url.strip()
    if not target.startswith(("http://", "https://")):
        target = "https://" + target
    try:
        _open(target)
        return ToolResult(
            status="ok",
            message=f"Opening {target}.",
            data={"url": target},
        )
    except Exception as e:  # noqa: BLE001
        return ToolResult(status="error", message=f"Couldn't open {target}: {e}")


@tool
def open_whatsapp_chat(contact: str | None = None) -> ToolResult:
    """Open WhatsApp Web, optionally jumping straight into a contact's chat using a wa.me deep link. Caller still needs to press Send.

    :param contact: Optional phone number in international format (e.g. 919876543210) or contact name. Numbers deep-link; names just open WhatsApp Web.
    """
    try:
        if contact and contact.strip().isdigit():
            # wa.me requires full international number, no '+' or spaces.
            phone = "".join(c for c in contact if c.isdigit())
            url = f"https://wa.me/{phone}"
            msg = f"Opening WhatsApp chat with {phone}."
        else:
            url = "https://web.whatsapp.com"
            extra = f" for {contact}" if contact else ""
            msg = (
                f"Opening WhatsApp Web{extra}. I couldn't resolve a phone "
                f"number, so pick the chat yourself."
            )
        _open(url)
        return ToolResult(status="ok", message=msg, data={"url": url, "contact": contact})
    except Exception as e:  # noqa: BLE001
        return ToolResult(status="error", message=f"Couldn't open WhatsApp: {e}")


@tool
def open_instagram_chat(contact: str | None = None) -> ToolResult:
    """Open Instagram, optionally to a user's profile/direct chat. Native app first, web fallback handled by the orchestrator.

    :param contact: Optional Instagram username (without @). Opens their profile/DM thread; you still hit Send.
    """
    try:
        if contact:
            username = contact.strip().lstrip("@")
            # Direct thread deep link works in both app and web.
            url = f"https://www.instagram.com/direct/new/?recipient={username}"
            msg = f"Opening Instagram chat with @{username}."
        else:
            url = "https://www.instagram.com/direct/inbox/"
            msg = "Opening Instagram Direct inbox."
        _open(url)
        return ToolResult(status="ok", message=msg, data={"url": url, "contact": contact})
    except Exception as e:  # noqa: BLE001
        return ToolResult(status="error", message=f"Couldn't open Instagram: {e}")
