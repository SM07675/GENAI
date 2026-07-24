"""
Memory System for Genie OS.
Handles Episodic, Semantic, and Working memory using Qdrant as the vector store.
"""
import uuid
from typing import List, Dict, Any, Optional
import logging
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from datetime import datetime
from ..event_bus import event_bus

log = logging.getLogger("genie_os.memory")

# Configure Qdrant (in-memory or local persistent)
# For production, this should point to a real Qdrant instance.
try:
    qdrant = QdrantClient(":memory:") # Using in-memory for Phase 1 testing
    
    # Initialize collections
    collections = ["episodic_memory", "semantic_memory", "working_memory"]
    for coll in collections:
        if not qdrant.collection_exists(coll):
            qdrant.create_collection(
                collection_name=coll,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )
except Exception as e:
    log.error(f"Failed to initialize Qdrant: {e}")
    qdrant = None


class MemoryManager:
    def __init__(self):
        # Fallback to simple list if Qdrant fails
        self._fallback_memory = []
        event_bus.subscribe("memory.add", self._handle_add_memory)

    async def _handle_add_memory(self, event: Dict[str, Any]) -> None:
        content = event.get("content")
        mem_type = event.get("memory_type", "working_memory")
        metadata = event.get("metadata", {})
        if content:
            await self.add_memory(content, mem_type, metadata)

    async def add_memory(self, content: str, memory_type: str = "working_memory", metadata: Dict[str, Any] = None) -> str:
        """Adds a memory to the specified collection."""
        if metadata is None:
            metadata = {}
        metadata["timestamp"] = datetime.now().isoformat()
        
        mem_id = str(uuid.uuid4())
        
        if qdrant:
            try:
                # In a real system, we'd use an embedding model here.
                # For this scaffolding, we generate dummy vectors or rely on the caller to provide them.
                # Actually, Mem0 or LiteLLM embedding should be used.
                # We will simulate a vector for now until the LLM router is wired in.
                dummy_vector = [0.0] * 1536 
                
                qdrant.upsert(
                    collection_name=memory_type,
                    points=[
                        PointStruct(
                            id=mem_id,
                            vector=dummy_vector,
                            payload={"content": content, **metadata}
                        )
                    ]
                )
                log.debug(f"Added memory to {memory_type}: {mem_id}")
            except Exception as e:
                log.error(f"Error adding to Qdrant: {e}")
        else:
            self._fallback_memory.append({"id": mem_id, "content": content, "type": memory_type, "metadata": metadata})
            
        return mem_id

    async def search(self, query: str, memory_type: str = "working_memory", limit: int = 5) -> List[Dict[str, Any]]:
        """Search memories based on query."""
        if qdrant:
            try:
                # Dummy vector for search
                dummy_vector = [0.0] * 1536
                search_result = qdrant.search(
                    collection_name=memory_type,
                    query_vector=dummy_vector,
                    limit=limit
                )
                return [{"id": hit.id, "content": hit.payload.get("content"), "metadata": hit.payload} for hit in search_result]
            except Exception as e:
                log.error(f"Error searching Qdrant: {e}")
                return []
        else:
            # Basic substring fallback
            return [m for m in self._fallback_memory if m["type"] == memory_type and query.lower() in m["content"].lower()][:limit]

memory_manager = MemoryManager()
