"""
Logging utilities for the Smart Automated Closet backend.

We configure a simple, production-style logging format that prints:
- timestamp
- log level
- logger name
- message
"""

from __future__ import annotations

import logging
from typing import Optional


def configure_logging(level: int = logging.INFO) -> None:
    """
    Configure the root logger once at application startup.
    """
    if logging.getLogger().handlers:
        # Already configured (avoid duplicate handlers in tests)
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

