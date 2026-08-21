"""
Memory Database v2 — SQLite-backed long-term memory for Genie.

Schema designed for the full Companion Mode memory system:
  - memories: All stored memories with importance scoring
  - preferences: User preferences (persistent)
  - projects: Project-specific memory
  - conversation_sessions: Session bookkeeping
  - context_snapshots: Temporal context records

Architecture:
  MemoryDB (SQLite) ← structured storage
  Qdrant (in-process)  ← semantic vector search
  EmbeddingService  ← real sentence-transformers vectors

Design rules:
  - Raw screenshots / audio NEVER written to storage
  - Importance scoring gates all writes
  - TTL-based expiry for temporary context
  - All async reads/writes via asyncio.to_thread (SQLite is sync)
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from .embeddings import get_embedding_service

log = structlog.get_logger("genie.memory.db")

# Path to the SQLite database (in backend/data/)
_DEFAULT_DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "genie_memory_v2.db"

# Minimum importance to persist to DB (0.0–1.0)
MIN_IMPORTANCE_TO_STORE = 0.3
# TTL for temporary context memories (seconds)
TEMPORARY_CONTEXT_TTL_S = 3600  # 1 hour


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class Memory:
    content: str
    category: str          # personal_preference | project | conversation | behavioral | temporary
    importance: float      # 0.0–1.0
    tags: List[str] = field(default_factory=list)
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    last_accessed_at: float = field(default_factory=time.time)
    access_count: int = 0
    expires_at: Optional[float] = None  # None = permanent

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    @classmethod
    def temporary(cls, content: str, importance: float = 0.5, **kwargs) -> "Memory":
        return cls(
            content=content,
            category="temporary",
            importance=importance,
            expires_at=time.time() + TEMPORARY_CONTEXT_TTL_S,
            **kwargs,
        )


@dataclass
class UserPreference:
    key: str
    value: Any
    category: str = "general"   # general | ui | voice | workflow | privacy
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    updated_at: float = field(default_factory=time.time)


@dataclass
class Project:
    name: str
    description: str = ""
    technology: List[str] = field(default_factory=list)
    status: str = "active"    # active | paused | completed
    known_bugs: List[str] = field(default_factory=list)
    next_tasks: List[str] = field(default_factory=list)
    architecture_notes: str = ""
    root_path: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════════════════════
# Qdrant process-wide singleton
# One QdrantClient per process — local file-backed Qdrant cannot be opened
# by more than one client instance at a time.
# ═══════════════════════════════════════════════════════════════════════════════

_qdrant_singleton = None
_qdrant_singleton_path: Optional[Path] = None
_qdrant_singleton_lock = asyncio.Lock()


async def _get_qdrant_client(index_path: Path):
    """Return (or create) the process-wide Qdrant client for index_path.

    If the client was already created for a different path, it is reused
    because all MemoryDatabase instances share the same data directory.
    A lock prevents two concurrent initializations.
    """
    global _qdrant_singleton, _qdrant_singleton_path
    async with _qdrant_singleton_lock:
        if _qdrant_singleton is not None:
            return _qdrant_singleton
        try:
            from qdrant_client import QdrantClient
            index_path.mkdir(parents=True, exist_ok=True)
            _qdrant_singleton = QdrantClient(path=str(index_path))
            _qdrant_singleton_path = index_path
            log.info("qdrant_singleton_created", path=str(index_path))
        except Exception as exc:
            log.warning("qdrant_singleton_failed", error=str(exc))
            _qdrant_singleton = None
        return _qdrant_singleton


# ═══════════════════════════════════════════════════════════════════════════════
# MemoryDatabase
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryDatabase:
    """SQLite-backed memory store with semantic search via sentence-transformers + Qdrant."""

    def __init__(self, db_path: Path = _DEFAULT_DB_PATH):
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._qdrant = None
        self._collection = "genie_memories"
        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Create tables, initialize Qdrant, load embedding model."""
        async with self._init_lock:
            if self._initialized:
                return

            # Create SQLite tables
            await asyncio.to_thread(self._create_schema)

            # Initialize Qdrant in-process for semantic search
            await self._init_qdrant()

            # Initialize embedding service
            emb = get_embedding_service()
            await emb.initialize()

            self._initialized = True
            log.info("memory_db_initialized",
                     db_path=str(self._db_path),
                     embedding_provider=emb.provider,
                     qdrant_available=self._qdrant is not None)

    def _create_schema(self) -> None:
        """Create all SQLite tables with proper indexes."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id              TEXT PRIMARY KEY,
                content         TEXT NOT NULL,
                category        TEXT NOT NULL DEFAULT 'general',
                importance      REAL NOT NULL DEFAULT 0.5,
                tags            TEXT DEFAULT '[]',
                project_id      TEXT,
                session_id      TEXT,
                created_at      REAL NOT NULL,
                last_accessed_at REAL NOT NULL,
                access_count    INTEGER NOT NULL DEFAULT 0,
                expires_at      REAL,
                has_vector      INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
            CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
            CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project_id);
            CREATE INDEX IF NOT EXISTS idx_memories_expires ON memories(expires_at);

            CREATE TABLE IF NOT EXISTS preferences (
                id          TEXT PRIMARY KEY,
                key         TEXT NOT NULL UNIQUE,
                value       TEXT NOT NULL,
                category    TEXT NOT NULL DEFAULT 'general',
                updated_at  REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_pref_key ON preferences(key);
            CREATE INDEX IF NOT EXISTS idx_pref_category ON preferences(category);

            CREATE TABLE IF NOT EXISTS projects (
                id                  TEXT PRIMARY KEY,
                name                TEXT NOT NULL UNIQUE,
                description         TEXT DEFAULT '',
                technology          TEXT DEFAULT '[]',
                status              TEXT DEFAULT 'active',
                known_bugs          TEXT DEFAULT '[]',
                next_tasks          TEXT DEFAULT '[]',
                architecture_notes  TEXT DEFAULT '',
                root_path           TEXT,
                created_at          REAL NOT NULL,
                updated_at          REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversation_sessions (
                id          TEXT PRIMARY KEY,
                started_at  REAL NOT NULL,
                ended_at    REAL,
                summary     TEXT,
                topics      TEXT DEFAULT '[]',
                turn_count  INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS context_snapshots (
                id              TEXT PRIMARY KEY,
                session_id      TEXT,
                current_app     TEXT,
                window_title    TEXT,
                current_project TEXT,
                open_file       TEXT,
                activity        TEXT,
                snapshot_data   TEXT,
                created_at      REAL NOT NULL
            );
        """)
        conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create a thread-local SQLite connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    async def _init_qdrant(self) -> None:
        """Initialize Qdrant in-process for vector search (singleton-safe)."""
        try:
            from qdrant_client.http.models import Distance, VectorParams

            emb = get_embedding_service()
            await emb.initialize()
            dim = emb.dimension

            self._qdrant = await _get_qdrant_client(self._db_path.parent / "qdrant_index")
            if self._qdrant is None:
                return  # singleton creation failed — already logged

            exists = await asyncio.to_thread(
                lambda: self._qdrant.collection_exists(self._collection)
            )
            if not exists:
                await asyncio.to_thread(
                    lambda: self._qdrant.create_collection(
                        collection_name=self._collection,
                        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
                    )
                )
            log.info("qdrant_initialized", collection=self._collection, dim=dim)
        except ImportError:
            log.warning("qdrant_not_installed", msg="Semantic search unavailable")
        except Exception as exc:
            log.warning("qdrant_init_failed", error=str(exc))


    # ── Memory CRUD ────────────────────────────────────────────────────────

    async def add_memory(self, memory: Memory) -> Optional[str]:
        """Add a memory. Returns the ID or None if below importance threshold."""
        if not self._initialized:
            await self.initialize()

        # Gate: don't store low-importance memories
        if memory.importance < MIN_IMPORTANCE_TO_STORE:
            log.debug("memory_skipped_low_importance", importance=memory.importance)
            return None

        # Don't store expired memories
        if memory.is_expired:
            return None

        # Write to SQLite
        await asyncio.to_thread(self._write_memory, memory)

        # Embed and write to Qdrant
        if self._qdrant is not None:
            try:
                emb = get_embedding_service()
                vec = await emb.embed(memory.content)
                if any(v != 0.0 for v in vec):
                    await asyncio.to_thread(self._write_to_qdrant, memory.id, vec, memory)
                    await asyncio.to_thread(self._mark_has_vector, memory.id)
            except Exception as exc:
                log.warning("memory_vector_write_failed", error=str(exc))

        log.debug("memory_added", id=memory.id, category=memory.category, importance=memory.importance)
        return memory.id

    def _write_memory(self, memory: Memory) -> None:
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO memories
               (id, content, category, importance, tags, project_id, session_id,
                created_at, last_accessed_at, access_count, expires_at, has_vector)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                memory.id, memory.content, memory.category, memory.importance,
                json.dumps(memory.tags), memory.project_id, memory.session_id,
                memory.created_at, memory.last_accessed_at, memory.access_count,
                memory.expires_at,
            ),
        )
        conn.commit()

    def _write_to_qdrant(self, mem_id: str, vec: List[float], memory: Memory) -> None:
        from qdrant_client.http.models import PointStruct
        self._qdrant.upsert(
            collection_name=self._collection,
            points=[PointStruct(
                id=mem_id,
                vector=vec,
                payload={
                    "content": memory.content,
                    "category": memory.category,
                    "importance": memory.importance,
                    "tags": memory.tags,
                    "project_id": memory.project_id,
                    "created_at": memory.created_at,
                },
            )],
        )

    def _mark_has_vector(self, mem_id: str) -> None:
        conn = self._get_conn()
        conn.execute("UPDATE memories SET has_vector=1 WHERE id=?", (mem_id,))
        conn.commit()

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 5,
        min_importance: float = 0.0,
    ) -> List[Memory]:
        """Semantic search over memories.

        Falls back to keyword search if embeddings unavailable.
        """
        if not self._initialized:
            await self.initialize()

        emb = get_embedding_service()

        if emb.is_functional and self._qdrant is not None:
            return await self._semantic_search(query, category, project_id, limit, min_importance)
        else:
            return await self._keyword_search(query, category, project_id, limit, min_importance)

    async def _semantic_search(self, query: str, category, project_id, limit, min_importance) -> List[Memory]:
        emb = get_embedding_service()
        q_vec = await emb.embed(query)

        filter_conditions = []
        if category:
            filter_conditions.append({"key": "category", "match": {"value": category}})
        if project_id:
            filter_conditions.append({"key": "project_id", "match": {"value": project_id}})

        try:
            from qdrant_client.http.models import Filter, FieldCondition, MatchValue
            qdrant_filter = None
            if filter_conditions:
                conditions = [
                    FieldCondition(key=c["key"], match=MatchValue(value=c["match"]["value"]))
                    for c in filter_conditions
                ]
                qdrant_filter = Filter(must=conditions)

            results = await asyncio.to_thread(
                lambda: self._qdrant.search(
                    collection_name=self._collection,
                    query_vector=q_vec,
                    query_filter=qdrant_filter,
                    limit=limit * 2,  # over-fetch then filter by importance
                )
            )

            memories = []
            for hit in results:
                if hit.payload.get("importance", 0) >= min_importance:
                    mem = await self.get_memory(hit.id)
                    if mem and not mem.is_expired:
                        memories.append(mem)
                        if len(memories) >= limit:
                            break

            if not memories:
                # Fallback to keyword search if vector search found nothing
                return await self._keyword_search(query, category, project_id, limit, min_importance)

            return memories
        except Exception as exc:
            log.warning("semantic_search_failed", error=str(exc))
            return await self._keyword_search(query, category, project_id, limit, min_importance)

    async def _keyword_search(self, query: str, category, project_id, limit, min_importance) -> List[Memory]:
        """Fallback tokenized keyword search."""
        import re

        def _search():
            conn = self._get_conn()
            words = [w for w in re.findall(r"\w+", query) if len(w) >= 2]
            if not words:
                words = [query.strip()] if query.strip() else [""]

            clauses = ["content LIKE ?" for _ in words]
            sql = f"""
                SELECT * FROM memories
                WHERE ({" OR ".join(clauses)})
                  AND importance >= ?
                  AND (expires_at IS NULL OR expires_at > ?)
            """
            params: List[Any] = [f"%{w}%" for w in words] + [min_importance, time.time()]
            if category:
                sql += " AND category = ?"
                params.append(category)
            if project_id:
                sql += " AND project_id = ?"
                params.append(project_id)
            sql += " ORDER BY importance DESC, last_accessed_at DESC LIMIT ?"
            params.append(limit)
            return conn.execute(sql, params).fetchall()

        rows = await asyncio.to_thread(_search)
        return [self._row_to_memory(r) for r in rows]

    async def get_memory(self, mem_id: str) -> Optional[Memory]:
        """Get a memory by ID and update access stats."""
        def _get():
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
            if row:
                conn.execute(
                    "UPDATE memories SET last_accessed_at=?, access_count=access_count+1 WHERE id=?",
                    (time.time(), mem_id)
                )
                conn.commit()
            return row

        row = await asyncio.to_thread(_get)
        return self._row_to_memory(row) if row else None

    async def get_recent(
        self,
        category: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Memory]:
        """Get recently accessed memories."""
        def _get():
            conn = self._get_conn()
            sql = """
                SELECT * FROM memories
                WHERE (expires_at IS NULL OR expires_at > ?)
            """
            params: List[Any] = [time.time()]
            if category:
                sql += " AND category = ?"
                params.append(category)
            if project_id:
                sql += " AND project_id = ?"
                params.append(project_id)
            sql += " ORDER BY last_accessed_at DESC LIMIT ?"
            params.append(limit)
            return conn.execute(sql, params).fetchall()

        rows = await asyncio.to_thread(_get)
        return [self._row_to_memory(r) for r in rows]

    async def delete_expired(self) -> int:
        """Delete all expired temporary memories. Returns count deleted."""
        def _delete():
            conn = self._get_conn()
            cur = conn.execute(
                "DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (time.time(),)
            )
            conn.commit()
            return cur.rowcount

        count = await asyncio.to_thread(_delete)
        if count > 0:
            log.info("memory_expired_deleted", count=count)
        return count

    async def delete_memory(self, mem_id: str) -> bool:
        """Delete a single memory by ID. Removes from SQLite and Qdrant."""
        def _delete():
            conn = self._get_conn()
            cur = conn.execute("DELETE FROM memories WHERE id = ?", (mem_id,))
            conn.commit()
            return cur.rowcount > 0

        success = await asyncio.to_thread(_delete)
        if success and self._qdrant is not None:
            try:
                await asyncio.to_thread(
                    lambda: self._qdrant.delete(
                        collection_name=self._collection,
                        points_selector=[mem_id],
                    )
                )
            except Exception as exc:
                log.debug("qdrant_delete_point_failed", error=str(exc))
        return success

    async def delete_matching(self, query: str) -> int:
        """Delete memories matching a query pattern (for 'forget that' requests)."""
        matching = await self.search(query=query, limit=10)
        deleted_count = 0
        for mem in matching:
            if await self.delete_memory(mem.id):
                deleted_count += 1
        return deleted_count

    async def update_memory(self, mem_id: str, content: str, importance: Optional[float] = None) -> bool:
        """Update the content and optionally importance of an existing memory."""
        def _update():
            conn = self._get_conn()
            if importance is not None:
                cur = conn.execute(
                    "UPDATE memories SET content = ?, importance = ?, last_accessed_at = ? WHERE id = ?",
                    (content, importance, time.time(), mem_id),
                )
            else:
                cur = conn.execute(
                    "UPDATE memories SET content = ?, last_accessed_at = ? WHERE id = ?",
                    (content, time.time(), mem_id),
                )
            conn.commit()
            return cur.rowcount > 0

        success = await asyncio.to_thread(_update)
        # Update vector embedding if possible
        if success and self._qdrant is not None:
            try:
                emb = get_embedding_service()
                vector = await emb.embed_text(content)
                from qdrant_client.http.models import PointStruct
                await asyncio.to_thread(
                    lambda: self._qdrant.upsert(
                        collection_name=self._collection,
                        points=[PointStruct(id=mem_id, vector=vector, payload={"content": content})],
                    )
                )
            except Exception as exc:
                log.debug("qdrant_update_point_failed", error=str(exc))
        return success

    async def clear_all(self) -> int:
        """Clear all memories and preferences for privacy reset."""
        def _clear():
            conn = self._get_conn()
            cur = conn.execute("DELETE FROM memories")
            conn.execute("DELETE FROM preferences")
            conn.commit()
            return cur.rowcount

        count = await asyncio.to_thread(_clear)
        if self._qdrant is not None:
            try:
                from qdrant_client.http.models import Filter
                await asyncio.to_thread(
                    lambda: self._qdrant.delete(
                        collection_name=self._collection,
                        points_selector=Filter(),
                    )
                )
            except Exception:
                pass
        log.info("memory_cleared_all", count=count)
        return count

    # ── Preferences ────────────────────────────────────────────────────────

    async def set_preference(self, key: str, value: Any, category: str = "general") -> None:
        pref = UserPreference(key=key, value=value, category=category)

        def _set():
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO preferences (id, key, value, category, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (pref.id, pref.key, json.dumps(pref.value), pref.category, pref.updated_at),
            )
            conn.commit()

        await asyncio.to_thread(_set)

    async def get_preference(self, key: str, default: Any = None) -> Any:
        def _get():
            conn = self._get_conn()
            row = conn.execute("SELECT value FROM preferences WHERE key = ?", (key,)).fetchone()
            return json.loads(row["value"]) if row else default

        return await asyncio.to_thread(_get)

    async def get_all_preferences(self, category: Optional[str] = None) -> Dict[str, Any]:
        def _get():
            conn = self._get_conn()
            if category:
                rows = conn.execute(
                    "SELECT key, value FROM preferences WHERE category = ?", (category,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT key, value FROM preferences").fetchall()
            return {r["key"]: json.loads(r["value"]) for r in rows}

        return await asyncio.to_thread(_get)

    # ── Projects ───────────────────────────────────────────────────────────

    async def save_project(self, project: Project) -> None:
        def _save():
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO projects
                   (id, name, description, technology, status, known_bugs, next_tasks,
                    architecture_notes, root_path, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    project.id, project.name, project.description,
                    json.dumps(project.technology), project.status,
                    json.dumps(project.known_bugs), json.dumps(project.next_tasks),
                    project.architecture_notes, project.root_path,
                    project.created_at, time.time(),
                ),
            )
            conn.commit()

        await asyncio.to_thread(_save)

    async def get_projects(self, status: Optional[str] = None) -> List[Project]:
        def _get():
            conn = self._get_conn()
            if status:
                rows = conn.execute(
                    "SELECT * FROM projects WHERE status = ? ORDER BY updated_at DESC", (status,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM projects ORDER BY updated_at DESC"
                ).fetchall()
            return rows

        rows = await asyncio.to_thread(_get)
        return [self._row_to_project(r) for r in rows]

    # ── Session management ─────────────────────────────────────────────────

    async def start_session(self) -> str:
        session_id = str(uuid.uuid4())

        def _start():
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO conversation_sessions (id, started_at) VALUES (?, ?)",
                (session_id, time.time()),
            )
            conn.commit()

        await asyncio.to_thread(_start)
        return session_id

    async def end_session(self, session_id: str, summary: str = "", topics: List[str] = None) -> None:
        def _end():
            conn = self._get_conn()
            conn.execute(
                "UPDATE conversation_sessions SET ended_at=?, summary=?, topics=? WHERE id=?",
                (time.time(), summary, json.dumps(topics or []), session_id),
            )
            conn.commit()

        await asyncio.to_thread(_end)

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_memory(row) -> Memory:
        if row is None:
            return None
        r = dict(row) if not isinstance(row, dict) else row
        return Memory(
            id=r["id"],
            content=r["content"],
            category=r.get("category", "general"),
            importance=r.get("importance", 0.5),
            tags=json.loads(r.get("tags", "[]")),
            project_id=r.get("project_id"),
            session_id=r.get("session_id"),
            created_at=r.get("created_at", time.time()),
            last_accessed_at=r.get("last_accessed_at", time.time()),
            access_count=r.get("access_count", 0),
            expires_at=r.get("expires_at"),
        )

    @staticmethod
    def _row_to_project(row) -> Project:
        r = dict(row) if not isinstance(row, dict) else row
        return Project(
            id=r["id"],
            name=r["name"],
            description=r.get("description", ""),
            technology=json.loads(r.get("technology", "[]")),
            status=r.get("status", "active"),
            known_bugs=json.loads(r.get("known_bugs", "[]")),
            next_tasks=json.loads(r.get("next_tasks", "[]")),
            architecture_notes=r.get("architecture_notes", ""),
            root_path=r.get("root_path"),
            created_at=r.get("created_at", time.time()),
            updated_at=r.get("updated_at", time.time()),
        )


# ── Global singleton ─────────────────────────────────────────────────────────

_memory_db: Optional[MemoryDatabase] = None


def get_memory_db() -> MemoryDatabase:
    """Get or create the global memory database."""
    global _memory_db
    if _memory_db is None:
        _memory_db = MemoryDatabase()
    return _memory_db
