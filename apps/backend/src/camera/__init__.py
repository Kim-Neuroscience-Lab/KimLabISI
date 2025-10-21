"""Camera system for ISI Macroscope.

This package provides camera detection, configuration, and capture functionality.
Uses constructor injection pattern - all dependencies passed explicitly.
"""

from .manager import CameraManager, CameraInfo
from .utils import (
    get_available_camera_indices,
    get_system_camera_names,
    run_system_command,
)

__all__ = [
    "CameraManager",
    "CameraInfo",
    "get_available_camera_indices",
    "get_system_camera_names",
    "run_system_command",
]
