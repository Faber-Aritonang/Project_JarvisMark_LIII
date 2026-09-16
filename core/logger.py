"""
core/logger.py — Centralised logging for Dodol.

Every module gets its own named logger via `get_logger(__name__)`. Logs go to
both the console (readable, coloured where supported) and a rotating file
(logs/dodol.log, 5 MB × 3 backups) so nothing is lost between sessions.

Usage:
    from core.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Session connected")
    logger.warning("Mic unavailable — falling back to default")
    logger.error("Gemini API failed: %s", exc)
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "dodol.log"

# Console format — short, readable in a terminal
_CONSOLE_FMT = "[%(asctime)s] %(name)s %(levelname)s: %(message)s"
_CONSOLE_DATE = "%H:%M:%S"

# File format — full timestamp for post-mortem debugging
_FILE_FMT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
_FILE_DATE = "%Y-%m-%d %H:%M:%S"

_initialised = False


def _ensure_root() -> None:
    """Set up the root 'dodol' logger once. Idempotent."""
    global _initialised
    if _initialised:
        return
    _initialised = True

    root = logging.getLogger("dodol")
    root.setLevel(logging.DEBUG)

    # ── Console handler ───────────────────────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(_CONSOLE_FMT, datefmt=_CONSOLE_DATE))
    root.addHandler(console)

    # ── Rotating file handler ─────────────────────────────────────────────
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3,
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(_FILE_FMT, datefmt=_FILE_DATE))
        root.addHandler(fh)
    except Exception:
        # If the log directory can't be created (permissions, read-only FS),
        # the console handler still works — never crash on logging setup.
        console.warning("Could not create log file at %s — console-only mode.", _LOG_FILE)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the 'dodol' namespace.

    >>> logger = get_logger(__name__)
    >>> logger.info("Hello")
    [12:00:00] my_module INFO: Hello
    """
    _ensure_root()
    # Strip leading 'dodol.' if the caller passes a fully-qualified name
    # (e.g. 'dodol.actions.web_search') to avoid 'dodol.dodol.actions…'
    if name.startswith("dodol."):
        name = name[6:]
    return logging.getLogger(f"dodol.{name}")
