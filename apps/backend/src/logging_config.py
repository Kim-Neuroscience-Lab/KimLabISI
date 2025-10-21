"""Centralized logging configuration for ISI Macroscope backend.

This is the SINGLE SOURCE OF TRUTH for all logging configuration.
Call configure_logging() ONCE at application startup.
"""

import logging
import sys
from typing import Optional


def configure_logging(
    level: int = logging.WARNING,
    format_string: Optional[str] = None
) -> None:
    """Configure logging for the entire application.

    Args:
        level: Logging level (logging.DEBUG, logging.INFO, etc.)
        format_string: Custom format string (optional)
    """
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # CRITICAL FIX: Set root logger level explicitly to enforce across all child loggers
    # This ensures that logger.info() calls are silenced when level=WARNING
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    logging.basicConfig(
        level=level,
        format=format_string,
        force=True  # Override any previous configuration
    )
