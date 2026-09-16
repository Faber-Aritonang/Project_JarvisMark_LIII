"""Tests for core/logger.py — centralised logging."""
from __future__ import annotations

import logging

from core.logger import get_logger


class TestGetLogger:
    def test_returns_logger(self):
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)

    def test_logger_name_format(self):
        logger = get_logger("my_module")
        assert logger.name == "dodol.my_module"

    def test_strips_dodol_prefix(self):
        logger = get_logger("dodol.actions.web_search")
        assert logger.name == "dodol.actions.web_search"
        assert not logger.name == "dodol.dodol.actions.web_search"

    def test_child_loggers_share_root(self):
        l1 = get_logger("module_a")
        l2 = get_logger("module_b")
        # Both should be children of the 'dodol' root
        assert l1.parent.name == "dodol"
        assert l2.parent.name == "dodol"

    def test_logger_has_handlers(self):
        logger = get_logger("handler_test")
        # The root 'dodol' logger should have at least a console handler
        root = logging.getLogger("dodol")
        assert len(root.handlers) >= 1
