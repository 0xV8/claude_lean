"""Logging setup. Uses rich for pretty output when stderr is a TTY."""

from __future__ import annotations

import logging
import os
import sys

_logger: logging.Logger | None = None


def get_logger(name: str = "claude_lean") -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger(name)
    logger.setLevel(os.environ.get("CLAUDE_LEAN_LOG_LEVEL", "WARNING"))

    try:
        from rich.logging import RichHandler
        handler: logging.Handler = RichHandler(
            show_time=False,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
        )
    except ImportError:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    logger.addHandler(handler)
    logger.propagate = False
    _logger = logger
    return logger
