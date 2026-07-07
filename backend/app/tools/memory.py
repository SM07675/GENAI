"""Tools for agentic memory: Notes and short-term knowledge."""

import json
from pathlib import Path
from ..schemas import ToolResult
from .registry import tool

_MEMORY_FILE = Path(__file__).parent.parent.parent / "memory.json"

def _load_notes() -> dict:
    if not _MEMORY_FILE.exists():
        return {}
    try:
        return json.loads(_MEMORY_FILE.read_text("utf-8"))
    except Exception:
        return {}

def _save_notes(notes: dict) -> None:
    _MEMORY_FILE.write_text(json.dumps(notes, indent=2), "utf-8")

@tool
def manage_note(action: str, topic: str = "", content: str = "") -> ToolResult:
    """Manage personal notes and memories.
    
    :param action: "create", "read", "update", "delete", or "list".
    :param topic: The subject of the note. For "list", this can be empty.
    :param content: The text content (only for create/update).
    """
    notes = _load_notes()
    
    if action == "list":
        if not notes:
            return ToolResult(status="ok", message="You don't have any notes right now.")
        return ToolResult(status="ok", message="Here are your notes.", data={"topics": list(notes.keys())})
        
    if action in ["create", "update"]:
        if not topic:
            return ToolResult(status="error", message="Topic is required.")
        notes[topic] = content
        _save_notes(notes)
        return ToolResult(status="ok", message=f"Saved note for {topic}.")
        
    if action == "read":
        if topic not in notes:
            return ToolResult(status="not_found", message=f"I couldn't find a note about {topic}.")
        return ToolResult(status="ok", message=f"Note on {topic}.", data={"content": notes[topic]})
        
    if action == "delete":
        if topic in notes:
            del notes[topic]
            _save_notes(notes)
            return ToolResult(status="ok", message=f"Deleted note about {topic}.")
        return ToolResult(status="not_found", message=f"No note found for {topic}.")

    return ToolResult(status="error", message="Unknown action.")
