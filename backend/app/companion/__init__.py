"""Companion Mode — Genie's proactive AI companion subsystem.

Architecture
------------
CompanionManager  <- lifecycle controller (start/stop/pause/resume)
    |-- ContextEngine     <- AIRI-style reflex layer (Win32 + mss + context diff)
    |-- VisionService     <- API-only vision, provider-abstract
    |-- EventManager      <- typed event catalog (Gaming/Coding/Writing/General)
    |-- CompanionBrain    <- conscious decision layer (IGNORE fast-path, LLM for phrasing)
    |-- PersonalityConfig <- energy/humor/hype/talkativeness knobs + presets
    +-- ObservationLoop   <- async observation cycle (interval, degradation, limiter)

Speech output routes through the existing TTSStreamWorker priority queue.
No second speech queue exists.
"""

from .manager import CompanionManager, CompanionMode, CompanionSubMode

__all__ = ["CompanionManager", "CompanionMode", "CompanionSubMode"]
