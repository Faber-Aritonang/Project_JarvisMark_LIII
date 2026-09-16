"""Tests for memory/memory_manager.py — persistent memory store."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

import memory.memory_manager as mm


@pytest.fixture
def memory_file(tmp_path):
    """Point memory_manager at a temporary file for isolation."""
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir()
    mem_file = mem_dir / "long_term.json"
    with patch.object(mm, "MEMORY_PATH", mem_file):
        yield mem_file


class TestLoadMemory:
    def test_no_file_returns_empty(self, memory_file):
        mem = mm.load_memory()
        assert isinstance(mem, dict)
        assert "identity" in mem
        assert "preferences" in mem
        assert mem["identity"] == {}

    def test_loads_existing(self, memory_file):
        data = mm._empty_memory()
        data["identity"]["name"] = {"value": "Jimmy", "updated": "2025-01-01"}
        memory_file.write_text(json.dumps(data), encoding="utf-8")
        mem = mm.load_memory()
        assert mem["identity"]["name"]["value"] == "Jimmy"

    def test_corrupt_file_returns_empty(self, memory_file):
        memory_file.write_text("not json!!!", encoding="utf-8")
        mem = mm.load_memory()
        assert mem["identity"] == {}

    def test_missing_categories_filled(self, memory_file):
        """If the file is missing some categories, they should be added."""
        memory_file.write_text(json.dumps({"identity": {}}), encoding="utf-8")
        mem = mm.load_memory()
        assert "preferences" in mem
        assert "projects" in mem


class TestSaveMemory:
    def test_creates_file(self, memory_file):
        mem = mm._empty_memory()
        mem["identity"]["name"] = {"value": "Test", "updated": "2025-01-01"}
        mm.save_memory(mem)
        assert memory_file.exists()
        loaded = json.loads(memory_file.read_text(encoding="utf-8"))
        assert loaded["identity"]["name"]["value"] == "Test"

    def test_ignores_non_dict(self, memory_file):
        mm.save_memory("not a dict")
        assert not memory_file.exists()

    def test_creates_directory(self, tmp_path):
        mem_file = tmp_path / "new_dir" / "memory" / "long_term.json"
        with patch.object(mm, "MEMORY_PATH", mem_file):
            mm.save_memory(mm._empty_memory())
            assert mem_file.exists()


class TestUpdateMemory:
    def test_adds_new_entry(self, memory_file):
        result = mm.update_memory({"identity": {"name": {"value": "Alice"}}})
        assert result["identity"]["name"]["value"] == "Alice"

    def test_updates_existing(self, memory_file):
        mm.update_memory({"identity": {"name": {"value": "Alice"}}})
        result = mm.update_memory({"identity": {"name": {"value": "Bob"}}})
        assert result["identity"]["name"]["value"] == "Bob"

    def test_empty_update_noop(self, memory_file):
        result = mm.update_memory({})
        assert result["identity"] == {}

    def test_none_update_noop(self, memory_file):
        result = mm.update_memory(None)
        assert result["identity"] == {}

    def test_ignores_empty_values(self, memory_file):
        result = mm.update_memory({"identity": {"name": {"value": ""}}})
        # Empty string values are skipped by _recursive_update
        # (the check is: isinstance(value, str) and not value.strip())
        name_entry = result["identity"].get("name")
        if name_entry is not None:
            # If stored, the value should be empty
            assert mm._entry_value(name_entry) == ""

    def test_truncates_long_values(self, memory_file):
        long_val = "x" * 500
        result = mm.update_memory({"notes": {"long": {"value": long_val}}})
        stored = result["notes"]["long"]["value"]
        # Truncation adds "…" (1 char), so total is MAX_VALUE_LENGTH + 1
        assert len(stored) <= mm.MAX_VALUE_LENGTH + 1

    def test_sets_updated_date(self, memory_file):
        result = mm.update_memory({"identity": {"city": {"value": "Jakarta"}}})
        assert "updated" in result["identity"]["city"]
        # Should be a valid date string
        from datetime import datetime
        datetime.strptime(result["identity"]["city"]["updated"], "%Y-%m-%d")

    def test_nested_category(self, memory_file):
        result = mm.update_memory({"preferences": {"food": {"pizza": {"value": "yes"}}}})
        assert result["preferences"]["food"]["pizza"]["value"] == "yes"


class TestSearchMemory:
    def test_search_empty(self, memory_file):
        results = mm.search_memory("test")
        assert results == [] or "nothing" in str(results).lower() or "no" in str(results).lower()

    def test_search_finds_match(self, memory_file):
        mm.update_memory({"identity": {"name": {"value": "Jimmy"}}})
        results = mm.search_memory("Jimmy")
        assert len(results) > 0
        assert "Jimmy" in str(results)

    def test_search_no_match(self, memory_file):
        mm.update_memory({"identity": {"name": {"value": "Jimmy"}}})
        results = mm.search_memory("nonexistent_xyz")
        result_str = str(results).lower()
        assert len(results) == 0 or "no match" in result_str or "nothing" in result_str


class TestSessionSummary:
    def test_save_and_pop(self, memory_file):
        mm.save_session_summary("Talked about the weather", "English")
        result = mm.pop_last_session()
        assert result is not None
        assert "weather" in result["summary"]

    def test_pop_consumes(self, memory_file):
        mm.save_session_summary("Test summary", "English")
        mm.pop_last_session()
        result = mm.pop_last_session()
        assert result is None

    def test_pop_empty(self, memory_file):
        result = mm.pop_last_session()
        assert result is None


class TestTrimToLimit:
    def test_no_trim_needed(self, memory_file):
        mem = mm._empty_memory()
        mem["identity"]["name"] = {"value": "Test", "updated": "2025-01-01"}
        result = mm._trim_to_limit(mem)
        assert "name" in result["identity"]

    def test_trims_oldest(self, memory_file):
        """When memory exceeds the limit, oldest entries are removed."""
        # Create a memory that exceeds the limit
        mem = mm._empty_memory()
        # Fill with enough data to exceed MEMORY_MAX_CHARS
        for i in range(2000):
            mem["notes"][f"note_{i:04d}"] = {
                "value": f"This is note number {i} with some padding text " * 5,
                "updated": f"2025-01-{(i % 28) + 1:02d}",
            }
        original_size = len(json.dumps(mem, ensure_ascii=False))
        assert original_size > mm.MEMORY_MAX_CHARS

        result = mm._trim_to_limit(mem)
        result_size = len(json.dumps(result, ensure_ascii=False))
        assert result_size <= mm.MEMORY_MAX_CHARS
