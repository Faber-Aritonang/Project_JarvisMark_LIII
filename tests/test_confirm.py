"""Tests for core/confirm.py — confirmation gate system."""

import time
import threading
from unittest.mock import MagicMock

import pytest

from core import confirm


@pytest.fixture(autouse=True)
def _reset_confirm():
    """Reset global state between tests."""
    confirm._pending = None
    confirm._show_cb = None
    confirm._hide_cb = None
    confirm._log_cb = None
    yield
    confirm._pending = None


class TestBind:
    def test_sets_callbacks(self):
        show, hide, log = MagicMock(), MagicMock(), MagicMock()
        confirm.bind(show, hide, log)
        assert confirm._show_cb is show
        assert confirm._hide_cb is hide
        assert confirm._log_cb is log

    def test_bind_without_log(self):
        show, hide = MagicMock(), MagicMock()
        confirm.bind(show, hide)
        assert confirm._show_cb is show
        assert confirm._hide_cb is hide
        assert confirm._log_cb is None


class TestRequest:
    def test_no_ui_bound(self):
        result = confirm.request("test", "Shutdown", "Are you sure?", lambda: "ok")
        assert "cannot confirm" in result.lower()
        assert confirm._pending is None

    def test_creates_pending(self):
        confirm.bind(MagicMock(), MagicMock())
        result = confirm.request("test", "Shutdown", "Are you sure?", lambda: "ok")
        assert "[CONFIRMATION_PENDING]" in result
        assert confirm._pending is not None
        assert confirm._pending.key == "test"
        assert confirm._pending.title == "Shutdown"

    def test_calls_show_callback(self):
        show = MagicMock()
        confirm.bind(show, MagicMock())
        confirm.request("test", "Shutdown", "Shutting down", lambda: "ok")
        show.assert_called_once_with("Shutdown", "Shutting down")

    def test_show_callback_raises(self):
        show = MagicMock(side_effect=RuntimeError("no display"))
        confirm.bind(show, MagicMock())
        result = confirm.request("test", "Shutdown", "desc", lambda: "ok")
        assert "Could not ask" in result
        assert confirm._pending is None

    def test_replaces_previous_pending(self):
        confirm.bind(MagicMock(), MagicMock())
        confirm.request("a", "First", "desc", lambda: "a")
        confirm.request("b", "Second", "desc", lambda: "b")
        assert confirm._pending.key == "b"


class TestResolve:
    def test_no_pending(self):
        confirm.bind(MagicMock(), MagicMock())
        confirm.resolve(True)  # should not raise

    def test_hide_called(self):
        hide = MagicMock()
        confirm.bind(MagicMock(), hide)
        confirm.request("test", "Shutdown", "desc", lambda: "ok")
        confirm.resolve(True)
        hide.assert_called_once()

    def test_cancel_does_not_run(self):
        ran = []
        confirm.bind(MagicMock(), MagicMock())
        confirm.request("test", "Shutdown", "desc", lambda: ran.append(1) or "ok")
        confirm.resolve(False)
        time.sleep(0.1)
        assert ran == []

    def test_accept_runs_on_thread(self):
        ran = []
        confirm.bind(MagicMock(), MagicMock())
        confirm.request("test", "Shutdown", "desc", lambda: ran.append(1) or "ok")
        confirm.resolve(True)
        time.sleep(0.2)
        assert ran == [1]

    def test_expired_does_not_run(self):
        ran = []
        confirm.bind(MagicMock(), MagicMock())
        confirm.request("test", "Shutdown", "desc", lambda: ran.append(1) or "ok")
        confirm._pending.at = time.monotonic() - confirm.TIMEOUT_SECONDS - 1
        confirm.resolve(True)
        time.sleep(0.1)
        assert ran == []

    def test_hide_callback_error_ignored(self):
        hide = MagicMock(side_effect=RuntimeError("fail"))
        confirm.bind(MagicMock(), hide)
        confirm.request("test", "Shutdown", "desc", lambda: "ok")
        confirm.resolve(True)  # should not raise

    def test_clears_pending_after_resolve(self):
        confirm.bind(MagicMock(), MagicMock())
        confirm.request("test", "Shutdown", "desc", lambda: "ok")
        confirm.resolve(True)
        assert confirm._pending is None


class TestPendingTitle:
    def test_empty_when_nothing(self):
        assert confirm.pending_title() == ""

    def test_returns_title(self):
        confirm.bind(MagicMock(), MagicMock())
        confirm.request("test", "Shutdown PC", "desc", lambda: "ok")
        assert confirm.pending_title() == "Shutdown PC"

    def test_empty_when_expired(self):
        confirm.bind(MagicMock(), MagicMock())
        confirm.request("test", "Shutdown", "desc", lambda: "ok")
        confirm._pending.at = time.monotonic() - confirm.TIMEOUT_SECONDS - 1
        assert confirm.pending_title() == ""
