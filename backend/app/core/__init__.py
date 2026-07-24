"""
Core abstractions for Genie OS.
"""

__all__ = ["event_bus", "context_engine", "memory_manager", "llm_router"]


def __getattr__(name: str):
    if name == "event_bus":
        from .event_bus import event_bus

        return event_bus
    if name == "context_engine":
        from .context import context_engine

        return context_engine
    if name == "memory_manager":
        from .memory import memory_manager

        return memory_manager
    if name == "llm_router":
        from .llm import llm_router

        return llm_router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
