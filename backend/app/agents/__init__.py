"""Genie Agent Package — specialized agents for the agent runtime.

Each agent is a self-contained unit that handles a specific domain of tasks.
Agents register themselves with the AgentRouter at startup.

Agent registry pattern:
    All agent classes are imported here and collected in AGENT_CLASSES.
    The runtime creates instances and registers them with the router.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .base_agent import BaseAgent
from .general_agent import GeneralAgent
from .research_agent import ResearchAgent
from .file_agent import FileAgent
from .system_agent import SystemAgent
from .media_agent import MediaAgent
from .coding_agent import CodingAgent
from .data_agent import DataAgent
from .document_agent import DocumentAgent
from .browser_agent import BrowserAgent
from .productivity_agent import ProductivityAgent

__all__ = [
    "BaseAgent",
    "GeneralAgent",
    "ResearchAgent",
    "FileAgent",
    "SystemAgent",
    "MediaAgent",
    "CodingAgent",
    "DataAgent",
    "DocumentAgent",
    "BrowserAgent",
    "ProductivityAgent",
    "get_all_agents",
]


def get_all_agents() -> list[BaseAgent]:
    """Create instances of all registered agents."""
    return [
        GeneralAgent(),
        ResearchAgent(),
        FileAgent(),
        SystemAgent(),
        MediaAgent(),
        CodingAgent(),
        DataAgent(),
        DocumentAgent(),
        BrowserAgent(),
        ProductivityAgent(),
    ]

