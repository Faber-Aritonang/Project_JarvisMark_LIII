"""Tests for core/undo.py — the shared undo stack."""
from __future__ import annotations

import pytest

from core import undo


@pytest.fixture(autouse=True)
def _clean_stack():
    """Ensure each test starts with an empty undo stack."""
    undo.clear()
    yield
    undo.clear()


class TestPushUndo:
    def test_basic_push(self):
        undo.push_undo("moved a.txt", lambda: "reversed")
        assert undo.can_undo()
        assert undo.peek() == "moved a.txt"

    def test_push_non_callable_ignored(self):
        undo.push_undo("bad", "not a function")
        assert not undo.can_undo()

    def test_max_depth(self):
        for i in range(undo.MAX_DEPTH + 5):
            undo.push_undo(f"op-{i}", lambda: "ok")
        assert len(undo.history()) == undo.MAX_DEPTH
        # Most recent is first in history
        assert undo.history()[0] == f"op-{undo.MAX_DEPTH + 5 - 1}"

    def test_label_truncated(self):
        long_label = "x" * 200
        undo.push_undo(long_label, lambda: "ok")
        assert len(undo.peek()) <= 120


class TestCanUndo:
    def test_empty_stack(self):
        assert not undo.can_undo()

    def test_after_push(self):
        undo.push_undo("test", lambda: "")
        assert undo.can_undo()


class TestPeek:
    def test_empty(self):
        assert undo.peek() == ""

    def test_returns_last_label(self):
        undo.push_undo("first", lambda: "")
        undo.push_undo("second", lambda: "")
        assert undo.peek() == "second"


class TestHistory:
    def test_empty(self):
        assert undo.history() == []

    def test_most_recent_first(self):
        undo.push_undo("first", lambda: "")
        undo.push_undo("second", lambda: "")
        undo.push_undo("third", lambda: "")
        h = undo.history()
        assert h == ["third", "second", "first"]


class TestUndoLast:
    def test_empty_stack(self):
        result = undo.undo_last()
        assert "nothing to undo" in result.lower()

    def test_successful_undo(self):
        undone = []
        undo.push_undo("test action", lambda: undone.append(1) or "reversed")
        result = undo.undo_last()
        assert "Undone: test action" in result
        assert "reversed" in result
        assert len(undone) == 1
        assert not undo.can_undo()

    def test_undo_with_error(self):
        def bad_undo():
            raise ValueError("disk full")

        undo.push_undo("failing write", bad_undo)
        result = undo.undo_last()
        assert "Could not undo" in result
        assert "disk full" in result

    def test_undo_removes_entry(self):
        undo.push_undo("first", lambda: "")
        undo.push_undo("second", lambda: "")
        undo.undo_last()
        assert undo.peek() == "first"


class TestClear:
    def test_clears_stack(self):
        undo.push_undo("test", lambda: "")
        undo.push_undo("test2", lambda: "")
        undo.clear()
        assert not undo.can_undo()
        assert undo.history() == []
