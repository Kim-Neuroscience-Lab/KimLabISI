"""
ISI Control System Backend Package

A comprehensive system for controlling and managing ISI (Inter-Stimulus Interval)
experiments with camera management, display control, and stimulus generation.

This package provides:
- Camera detection and management
- Display detection and configuration
- Stimulus parameter management and generation
- IPC communication for frontend integration
- Hardware abstraction utilities

Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "ISI Control System"
__description__ = "ISI Control System Backend Package"

# Core modules
from . import camera_manager
from . import display_manager
from . import stimulus_manager
from . import hardware_utils

__all__ = [
    "camera_manager",
    "display_manager",
    "stimulus_manager",
    "hardware_utils",
    "__version__",
    "__author__",
    "__description__"
]