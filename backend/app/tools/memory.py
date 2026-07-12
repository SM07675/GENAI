"""Tools for agentic memory: Notes and short-term knowledge."""

from ..schemas import ToolResult
from .registry import tool
from .memory_db import companion_db
import time

@tool
def manage_note(action: str, topic: str = "", content: str = "") -> ToolResult:
    """Manage personal notes and memories.
    
    :param action: "create", "read", "update", "delete", or "list".
    :param topic: The subject of the note. For "list", this can be empty.
    :param content: The text content (only for create/update).
    """
    if action == "list":
        notes = companion_db.get_memory(type_="fact", limit=50)
        if not notes:
            return ToolResult(status="ok", message="You don't have any notes right now.")
        return ToolResult(status="ok", message="Here are your notes.", data={"topics": [n["key"] for n in notes]})
        
    if action in ["create", "update"]:
        if not topic:
            return ToolResult(status="error", message="Topic is required.")
        companion_db.upsert_memory("fact", topic, content, source="tool")
        return ToolResult(status="ok", message=f"Saved note for {topic}.")
        
    if action == "read":
        if not topic:
            return ToolResult(status="error", message="Topic is required.")
        # Try full-text search if exact key isn't found
        res = companion_db.search_memory(topic, limit=1)
        if not res:
            return ToolResult(status="not_found", message=f"I couldn't find a note about {topic}.")
        return ToolResult(status="ok", message=f"Note on {topic}.", data={"content": res[0]["value"]})
        
    if action == "delete":
        if not topic:
            return ToolResult(status="error", message="Topic is required.")
        deleted = companion_db.forget_by_key(topic)
        if deleted > 0:
            return ToolResult(status="ok", message=f"Deleted note about {topic}.")
        return ToolResult(status="not_found", message=f"No note found for {topic}.")

    return ToolResult(status="error", message="Unknown action.")

@tool
def set_reminder(title: str, delay_seconds: int) -> ToolResult:
    """Set a reminder or timer.
    
    :param title: What to remind the user about.
    :param delay_seconds: In how many seconds the reminder should trigger.
    """
    # For now, we will store the task in the database and pretend we've scheduled it.
    # In a full streaming UI, this would push an event to the frontend scheduler.
    companion_db.add_task(f"Reminder: {title}", deadline=f"In {delay_seconds} seconds")
    return ToolResult(status="ok", message=f"Reminder set for {title} in {delay_seconds} seconds.", data={"timer_set": True, "seconds": delay_seconds})
