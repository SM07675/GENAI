"""Web & social tools: open direct URLs and deep-link into chats.

`open_url` is the browser fallback target for the "Instagram problem"
guardrail — when a native app isn't installed, the orchestrator (per the
system prompt) chains here instead of failing.

Contacts are resolved via the configurable registry in `contacts.py`
(data/contacts.json), so no personal names are hardcoded here.
"""
from __future__ import annotations

import urllib.parse
import webbrowser

from ..contacts import lookup_contact
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
    except OSError as e:
        return ToolResult(status="error", message=f"Couldn't open {target}: {e}")


@tool
def open_whatsapp_chat(contact: str | None = None) -> ToolResult:
    """Open WhatsApp Web, optionally jumping straight into a contact's chat using a wa.me deep link. Caller still needs to press Send.

    Accepts a phone number in international format (e.g. 919876543210) or a
    contact name that matches an entry in your contacts registry
    (data/contacts.json).

    :param contact: Phone number or contact name/alias from your contacts list.
    """
    try:
        phone: str | None = None

        if contact:
            contact = contact.strip()
            # If it's a digit string, use directly.
            if contact.isdigit():
                phone = contact
            else:
                # Try contacts registry first.
                entry = lookup_contact(contact)
                if entry:
                    phone = entry.get("whatsapp") or entry.get("phone")
                    if phone:
                        phone = "".join(c for c in phone if c.isdigit())

        if phone:
            url = f"https://wa.me/{phone}"
            msg = f"Opening WhatsApp chat with {contact or phone}."
        else:
            url = "https://web.whatsapp.com"
            extra = f" for {contact}" if contact else ""
            msg = (
                f"Opening WhatsApp Web{extra}. I couldn't resolve a phone "
                f"number, so pick the chat yourself."
            )
        _open(url)
        return ToolResult(status="ok", message=msg, data={"url": url, "contact": contact})
    except OSError as e:
        return ToolResult(status="error", message=f"Couldn't open WhatsApp: {e}")


@tool
def open_instagram_chat(contact: str | None = None) -> ToolResult:
    """Open Instagram, optionally to a user's profile/direct chat. Native app first, web fallback handled by the orchestrator.

    Accepts an Instagram username (without @) or a contact name that matches
    an entry in your contacts registry (data/contacts.json).

    :param contact: Instagram username or contact name/alias from your contacts list.
    """
    try:
        username: str | None = None

        if contact:
            contact_str = contact.strip().lstrip("@")
            # Try contacts registry for a friendly name lookup.
            entry = lookup_contact(contact_str)
            if entry and entry.get("instagram"):
                username = entry["instagram"].lstrip("@")
            else:
                # Treat as a direct username.
                username = contact_str

        if username:
            # Direct thread deep link works in both app and web.
            url = f"https://www.instagram.com/direct/new/?recipient={username}"
            msg = f"Opening Instagram chat with @{username}."
        else:
            url = "https://www.instagram.com/direct/inbox/"
            msg = "Opening Instagram Direct inbox."
        _open(url)
        return ToolResult(status="ok", message=msg, data={"url": url, "contact": contact})
    except OSError as e:
        return ToolResult(status="error", message=f"Couldn't open Instagram: {e}")
