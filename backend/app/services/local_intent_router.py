"""Local intent router for deterministic short-circuiting of simple commands.

This avoids consuming OpenRouter tokens for basic requests.
"""
from __future__ import annotations

import re

# Simple commands that can bypass the LLM entirely
_INTENTS = {
    "stop_audio": r"^(stop|pause|quiet|shh|shut up|cancel)( audio| music| talking| speaking)?$",
    "play_music": r"^(play|resume)( some)?( music| songs?| audio)$",
    "clear_history": r"^(clear|forget|reset|delete)( my)?( history| memory| conversation| chat)$",
}

def route_intent(text: str) -> str | None:
    """Return an intent name if the text matches a known simple command, else None."""
    # Clean the text: lower case, remove punctuation
    clean_text = re.sub(r'[^\w\s]', '', text.lower()).strip()
    
    for intent, pattern in _INTENTS.items():
        if re.match(pattern, clean_text):
            return intent
            
    return None
