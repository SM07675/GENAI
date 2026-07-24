from __future__ import annotations

from app.core.context.peak_context import build_peak_context_packet, learn_explicit_memories


class FakeDB:
    def __init__(self):
        self.memories = [
            {
                "id": 1,
                "type": "project",
                "key": "genie",
                "value": "Genie is the user's AI assistant project.",
                "confidence": 0.9,
            }
        ]
        self.preferences = {"voice_style": "short, warm spoken replies"}
        self.projects = [{"name": "Genie", "description": "Local AI assistant"}]
        self.tasks = [{"title": "Improve memory retrieval", "deadline": "soon"}]
        self.profile = {}
        self.saved_preferences = {}
        self.upserts = []

    def search_memory(self, query: str, limit: int = 8):
        q = query.lower()
        if "genie" in q or "memory" in q:
            return self.memories[:limit]
        return []

    def get_preferences(self):
        return self.preferences

    def get_projects(self):
        return self.projects

    def get_tasks(self, status: str = "pending"):
        return self.tasks if status == "pending" else []

    def set_profile(self, field: str, value: str):
        self.profile[field] = value

    def set_preference(self, key: str, value: str, category: str = "general"):
        self.saved_preferences[key] = {"value": value, "category": category}

    def upsert_memory(self, type_, key, value, confidence=1.0, source="auto"):
        self.upserts.append({
            "type": type_,
            "key": key,
            "value": value,
            "confidence": confidence,
            "source": source,
        })
        return len(self.upserts)


def test_build_peak_context_packet_includes_relevant_operating_context():
    db = FakeDB()

    packet = build_peak_context_packet("Improve Genie memory", "session-1", db=db)

    assert "GENIE OS CONTEXT PACKET" in packet
    assert "Genie is the user's AI assistant project." in packet
    assert "short, warm spoken replies" in packet
    assert "Improve memory retrieval" in packet


def test_learn_explicit_memories_promotes_only_clear_user_signals():
    db = FakeDB()

    learned = learn_explicit_memories("Remember that I prefer concise Hindi replies.", db=db)

    assert any(item.startswith("preference:") for item in learned)
    assert any(memory["type"] == "preference" for memory in db.upserts)


def test_learn_explicit_memories_stores_name_profile():
    db = FakeDB()

    learned = learn_explicit_memories("Call me Sarvesh", db=db)

    assert learned == ["profile:name"]
    assert db.profile["name"] == "Sarvesh"
    assert db.upserts[0]["type"] == "profile"
