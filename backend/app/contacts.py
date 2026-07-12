"""Contacts/shortcuts registry for Genie.

Maps friendly contact names to social/messaging handles, phone numbers, and
email addresses.  This replaces any hardcoded personal data in the tool modules
and makes the system configurable per user.

The registry is backed by `data/contacts.json` (relative to the project root)
and hot-reloads on every call so edits don't require a backend restart.

Schema (contacts.json):
    [
      {
        "name": "Alice",                        // display name (required)
        "aliases": ["al", "alice smith"],       // alternative names to match
        "phone": "919876543210",                // international format, no + or spaces
        "whatsapp": "919876543210",             // if different from phone
        "instagram": "alice_username",          // without @
        "email": "alice@example.com",
        "telegram": "alicehandle"
      }
    ]
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("genie.contacts")

# Resolve path relative to the repo root (two levels up from this file).
_DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "contacts.json"


def _load_registry(path: Path) -> list[dict]:
    """Load the contacts JSON file; return empty list on any error."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            log.warning("contacts.json must be a JSON array; ignoring.")
            return []
        return data
    except json.JSONDecodeError as e:
        log.warning("contacts.json is malformed (%s); no contacts loaded.", e)
        return []


def lookup_contact(
    name: str,
    registry_path: Optional[Path] = None,
) -> Optional[dict]:
    """Find a contact by name or alias (case-insensitive).

    Returns the first matching contact dict, or None if no match found.

    :param name: Friendly name or alias to search for.
    :param registry_path: Override path; defaults to data/contacts.json.
    """
    path = registry_path or _DEFAULT_REGISTRY_PATH
    contacts = _load_registry(path)
    needle = (name or "").strip().lower()
    if not needle:
        return None

    for contact in contacts:
        # Match against name
        if (contact.get("name") or "").lower() == needle:
            return contact
        # Match against aliases list
        aliases = [str(a).lower() for a in (contact.get("aliases") or [])]
        if needle in aliases:
            return contact
    return None


def all_contacts(registry_path: Optional[Path] = None) -> list[dict]:
    """Return every contact in the registry."""
    path = registry_path or _DEFAULT_REGISTRY_PATH
    return _load_registry(path)
