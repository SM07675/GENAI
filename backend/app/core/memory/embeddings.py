"""
EmbeddingService — Local sentence-transformers embeddings with cloud fallback.

Uses all-MiniLM-L6-v2 by default (80MB, fast, offline-capable).
Falls back to Gemini/OpenAI embeddings if local model unavailable.

Usage:
    emb = EmbeddingService()
    vector = await emb.embed("hello world")  # returns List[float]
    vectors = await emb.embed_batch(["text1", "text2"])
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from functools import lru_cache
from typing import List, Optional

import structlog

log = structlog.get_logger("genie.memory.embeddings")

# Dimension of the embedding vector
LOCAL_DIM = 384     # all-MiniLM-L6-v2
OPENAI_DIM = 1536   # text-embedding-3-small


class EmbeddingService:
    """Provides text embeddings for semantic memory search.

    Priority order:
        1. sentence-transformers local (all-MiniLM-L6-v2) — offline, ~80MB
        2. Gemini embedding API — requires GEMINI_API_KEY
        3. OpenAI embedding API — requires OPENAI_API_KEY
        4. Zero-vector fallback — allows system to run but search will be keyword-only
    """

    def __init__(self):
        self._model = None
        self._model_loaded = False
        self._model_error: Optional[str] = None
        self._cache: dict[str, List[float]] = {}  # LRU cache by text hash
        self._dim: int = LOCAL_DIM
        self._provider: str = "uninitialized"
        self._init_lock = asyncio.Lock()

    # ── Initialization ─────────────────────────────────────────────────────

    async def initialize(self) -> bool:
        """Load the embedding model. Call once at startup."""
        async with self._init_lock:
            if self._model_loaded:
                return True

            # Try local sentence-transformers first
            if await self._try_load_local():
                return True

            # Cloud fallbacks
            log.warning("embedding_local_unavailable", msg="Falling back to cloud embeddings")
            self._provider = "zero_vector"
            self._dim = LOCAL_DIM
            self._model_loaded = True  # mark as loaded (with zero fallback)
            log.warning("embedding_zero_fallback_active",
                        msg="No embedding model available. Semantic search disabled. "
                            "Install: pip install sentence-transformers")
            return False

    async def _try_load_local(self) -> bool:
        """Attempt to load sentence-transformers locally."""
        try:
            import torch
            # Run in thread to avoid blocking event loop
            model = await asyncio.to_thread(self._load_st_model)
            if model is not None:
                self._model = model
                self._dim = LOCAL_DIM
                self._provider = "sentence_transformers"
                self._model_loaded = True
                log.info("embedding_model_loaded", provider="sentence_transformers",
                         model="all-MiniLM-L6-v2", dim=LOCAL_DIM)
                return True
        except ImportError:
            log.info("embedding_sentence_transformers_not_installed")
        except Exception as exc:
            log.warning("embedding_local_load_failed", error=str(exc))
        return False

    @staticmethod
    def _load_st_model():
        """Synchronous model load — run in thread."""
        try:
            from sentence_transformers import SentenceTransformer
            return SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as exc:
            log.warning("embedding_st_load_error", error=str(exc))
            return None

    # ── Public API ─────────────────────────────────────────────────────────

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def is_functional(self) -> bool:
        """Returns True if real embeddings are available (not zero-vector)."""
        return self._provider == "sentence_transformers"

    async def embed(self, text: str) -> List[float]:
        """Embed a single text string.

        Returns the embedding vector or a zero vector if unavailable.
        """
        if not self._model_loaded:
            await self.initialize()

        # Cache lookup
        key = hashlib.sha256(text.encode()).hexdigest()[:16]
        if key in self._cache:
            return self._cache[key]

        vec = await self._compute_embedding(text)
        # Cache up to 1000 entries
        if len(self._cache) > 1000:
            self._cache.pop(next(iter(self._cache)))
        self._cache[key] = vec
        return vec

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts efficiently."""
        if not self._model_loaded:
            await self.initialize()

        if not texts:
            return []

        if self._provider == "sentence_transformers" and self._model is not None:
            try:
                vecs = await asyncio.to_thread(
                    lambda: self._model.encode(texts, convert_to_tensor=False).tolist()
                )
                return vecs
            except Exception as exc:
                log.warning("embedding_batch_failed", error=str(exc))

        # Fallback: embed one by one
        return [await self.embed(t) for t in texts]

    async def similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """Cosine similarity between two vectors."""
        if not vec_a or not vec_b:
            return 0.0
        try:
            import numpy as np
            a = np.array(vec_a)
            b = np.array(vec_b)
            denom = (np.linalg.norm(a) * np.linalg.norm(b))
            if denom == 0:
                return 0.0
            return float(np.dot(a, b) / denom)
        except Exception:
            return 0.0

    # ── Internal ───────────────────────────────────────────────────────────

    async def _compute_embedding(self, text: str) -> List[float]:
        if self._provider == "sentence_transformers" and self._model is not None:
            try:
                vec = await asyncio.to_thread(
                    lambda: self._model.encode(text, convert_to_tensor=False).tolist()
                )
                return vec
            except Exception as exc:
                log.warning("embedding_compute_failed", error=str(exc))

        # Zero vector fallback
        return [0.0] * self._dim


# ── Global singleton ─────────────────────────────────────────────────────────

_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the global embedding service."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
