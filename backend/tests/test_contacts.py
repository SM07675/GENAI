"""Unit tests for the contacts registry."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.contacts import lookup_contact, all_contacts


@pytest.fixture
def sample_registry(tmp_path):
    data = [
        {
            "name": "Alice Smith",
            "aliases": ["alice", "al"],
            "phone": "919876543210",
            "whatsapp": "919876543210",
            "instagram": "alice_smith_ig",
            "email": "alice@example.com",
        },
        {
            "name": "Bob",
            "aliases": [],
            "phone": "911234567890",
            "instagram": "bobofficial",
        },
    ]
    registry_file = tmp_path / "contacts.json"
    registry_file.write_text(json.dumps(data), encoding="utf-8")
    return registry_file


class TestLookupContact:
    def test_lookup_by_full_name(self, sample_registry):
        result = lookup_contact("Alice Smith", registry_path=sample_registry)
        assert result is not None
        assert result["instagram"] == "alice_smith_ig"

    def test_lookup_case_insensitive(self, sample_registry):
        result = lookup_contact("alice smith", registry_path=sample_registry)
        assert result is not None

    def test_lookup_by_alias(self, sample_registry):
        result = lookup_contact("alice", registry_path=sample_registry)
        assert result is not None
        assert result["phone"] == "919876543210"

    def test_lookup_short_alias(self, sample_registry):
        result = lookup_contact("al", registry_path=sample_registry)
        assert result is not None

    def test_lookup_not_found(self, sample_registry):
        result = lookup_contact("Unknown Person", registry_path=sample_registry)
        assert result is None

    def test_lookup_empty_name(self, sample_registry):
        result = lookup_contact("", registry_path=sample_registry)
        assert result is None

    def test_lookup_missing_file(self, tmp_path):
        result = lookup_contact("Alice", registry_path=tmp_path / "nonexistent.json")
        assert result is None

    def test_lookup_malformed_json(self, tmp_path):
        bad_file = tmp_path / "contacts.json"
        bad_file.write_text("NOT JSON {{{", encoding="utf-8")
        result = lookup_contact("Alice", registry_path=bad_file)
        assert result is None


class TestAllContacts:
    def test_returns_all(self, sample_registry):
        contacts = all_contacts(registry_path=sample_registry)
        assert len(contacts) == 2

    def test_empty_on_missing_file(self, tmp_path):
        contacts = all_contacts(registry_path=tmp_path / "no_file.json")
        assert contacts == []
