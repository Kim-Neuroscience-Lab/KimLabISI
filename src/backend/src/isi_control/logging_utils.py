"""Structured logging helpers."""

from __future__ import annotations

import logging
from logging import Logger
from pathlib import Path
from typing import Optional


def configure_root_logger(log_path: Path) -> Logger:
    """Configure the root logger for the backend."""

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.FileHandler(log_path)
        formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def get_logger(name: Optional[str] = None) -> Logger:
    """Get a namespaced logger."""

    return logging.getLogger(name)
