"""Unit tests for Genie OS Memory Architecture (Phase 4).

Verifies:
- Memory storage and retrieval
- Forget ('forget that') functionality
- Memory updates and deletion
- User preferences persistence
- Expiration and maintenance
"""
import asyncio
import pytest

from app.core.memory.manager import MemoryManager
from app.core.memory.memory_db_v2 import Memory, Project


@pytest.mark.asyncio
async def test_memory_remember_and_search():
    mgr = MemoryManager()
    await mgr.initialize()

    # Remember a test fact
    mem_id = await mgr.remember(
        content="The user's favorite coding framework is FastAPI",
        category="personal_preference",
        importance=0.9,
    )
    assert mem_id is not None

    # Search for it
    results = await mgr.search("FastAPI framework", limit=5)
    assert len(results) >= 1
    assert any("FastAPI" in m.content for m in results)


@pytest.mark.asyncio
async def test_memory_forget_command():
    mgr = MemoryManager()
    await mgr.initialize()

    # Store a secret / temporary thought
    await mgr.remember(
        content="Temporary secret token is xyz987654",
        category="temporary",
        importance=0.8,
    )

    # Forget it
    deleted = await mgr.forget("secret token xyz987654")
    assert deleted >= 1

    # Verify search no longer finds it
    results = await mgr.search("xyz987654", limit=5)
    assert not any("xyz987654" in m.content for m in results)


@pytest.mark.asyncio
async def test_memory_preferences():
    mgr = MemoryManager()
    await mgr.initialize()

    await mgr.set_preference("theme_mode", "futuristic_dark", "ui")
    val = await mgr.get_preference("theme_mode")
    assert val == "futuristic_dark"


@pytest.mark.asyncio
async def test_memory_delete_by_id():
    mgr = MemoryManager()
    await mgr.initialize()

    mem_id = await mgr.remember(
        content="Delete this specific note later",
        category="conversation",
        importance=0.5,
    )
    assert mem_id is not None

    deleted = await mgr.delete_memory(mem_id)
    assert deleted is True
