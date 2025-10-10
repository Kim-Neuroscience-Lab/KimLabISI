"""Centralized logging configuration for ISI Macroscope backend.

This is the SINGLE SOURCE OF TRUTH for all logging configuration.
Call configure_logging() ONCE at application startup.
"""

import logging
import sys
from typing import Optional


def configure_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None
) -> None:
    """Configure logging for the entire application.

    Args:
        level: Logging level (logging.DEBUG, logging.INFO, etc.)
        format_string: Custom format string (optional)
    """
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=level,
        format=format_string,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True  # Override any previous configuration
    )
