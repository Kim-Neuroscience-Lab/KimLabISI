"""Display/monitor detection utilities.

Cross-platform display detection, resolution detection, and multi-monitor
enumeration. Pure functions only - no global state.
NO service locator dependencies.
"""

from __future__ import annotations

import json
import logging
import platform
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DisplayInfo:
    """Information about a display/monitor."""

    name: str
    identifier: str
    width: int
    height: int
    refresh_rate: float
    is_primary: bool
    position_x: int = 0
    position_y: int = 0
    scale_factor: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "identifier": self.identifier,
            "width": self.width,
            "height": self.height,
            "refresh_rate": self.refresh_rate,
            "is_primary": self.is_primary,
            "position_x": self.position_x,
            "position_y": self.position_y,
            "scale_factor": self.scale_factor,
        }


def detect_displays() -> List[DisplayInfo]:
    """Detect all available displays.

    Returns:
        List of DisplayInfo for each detected display
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        return _detect_displays_macos()
    elif system == "Linux":
        return _detect_displays_linux()
    elif system == "Windows":
        return _detect_displays_windows()
    else:
        logger.warning("Unsupported platform: %s", system)
        return []


def get_primary_display() -> Optional[DisplayInfo]:
    """Get primary display information.

    Returns:
        DisplayInfo for primary display, or first display if no primary marked
    """
    displays = detect_displays()

    if not displays:
        return None

    # Find primary display
    for display in displays:
        if display.is_primary:
            return display

    # Return first display if no primary marked
    return displays[0]


def validate_display_config(
    required_width: int,
    required_height: int,
    required_refresh_rate: Optional[float] = None,
) -> Tuple[bool, str]:
    """Validate display configuration against available displays.

    Args:
        required_width: Required display width in pixels
        required_height: Required display height in pixels
        required_refresh_rate: Optional required refresh rate in Hz

    Returns:
        Tuple of (is_valid, error_message)
    """
    displays = detect_displays()

    if not displays:
        return (False, "No displays detected")

    # Check if any display meets requirements
    for display in displays:
        if display.width >= required_width and display.height >= required_height:
            if required_refresh_rate is None:
                return (True, "")
            elif display.refresh_rate >= required_refresh_rate:
                return (True, "")

    # Build error message
    if required_refresh_rate:
        return (
            False,
            f"No display found with resolution {required_width}x{required_height} "
            f"@ {required_refresh_rate}Hz",
        )
    else:
        return (
            False,
            f"No display found with resolution {required_width}x{required_height}",
        )


def get_display_by_identifier(identifier: str) -> Optional[DisplayInfo]:
    """Get display information by identifier.

    Args:
        identifier: Display identifier to search for

    Returns:
        DisplayInfo if found, None otherwise
    """
    displays = detect_displays()

    for display in displays:
        if display.identifier == identifier:
            return display

    return None


def get_display_by_name(name: str) -> Optional[DisplayInfo]:
    """Get display information by name.

    Args:
        name: Display name to search for

    Returns:
        DisplayInfo if found, None otherwise
    """
    displays = detect_displays()

    for display in displays:
        if display.name == name:
            return display

    return None


# Platform-specific detection functions


def _detect_displays_macos() -> List[DisplayInfo]:
    """Detect displays on macOS using system_profiler.

    Returns:
        List of DisplayInfo for detected displays
    """
    displays = []

    try:
        # Use system_profiler to get display information
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            logger.error("system_profiler failed: %s", result.stderr)
            return displays

        data = json.loads(result.stdout)
        display_data = data.get("SPDisplaysDataType", [])

        for idx, display_group in enumerate(display_data):
            # Each group represents a GPU with connected displays
            displays_list = display_group.get("spdisplays_ndrvs", [])

            for display_idx, display_item in enumerate(displays_list):
                name = display_item.get("_name", f"Display {idx}-{display_idx}")

                # Parse resolution
                resolution_str = display_item.get("_spdisplays_resolution", "")
                width, height = _parse_resolution(resolution_str)

                # Parse refresh rate
                refresh_str = display_item.get("spdisplays_refresh_rate", "60 Hz")
                refresh_rate = _parse_refresh_rate(refresh_str)

                # Determine if primary (first display is usually primary)
                is_primary = idx == 0 and display_idx == 0

                # Parse position if available
                position_x = 0
                position_y = 0

                # Scale factor
                scale_factor = 1.0
                pixel_ratio = display_item.get("spdisplays_pixelresolution", "")
                if pixel_ratio:
                    # macOS reports both physical and logical resolution
                    # Scale factor is physical/logical
                    scale_factor = 2.0 if "Retina" in name else 1.0

                display_info = DisplayInfo(
                    name=name,
                    identifier=f"macos_display_{idx}_{display_idx}",
                    width=width,
                    height=height,
                    refresh_rate=refresh_rate,
                    is_primary=is_primary,
                    position_x=position_x,
                    position_y=position_y,
                    scale_factor=scale_factor,
                )
                displays.append(display_info)

        logger.info("Detected %d displays on macOS", len(displays))

    except subprocess.TimeoutExpired:
        logger.error("Display detection timed out")
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse system_profiler output: %s", exc)
    except Exception as exc:
        logger.error("Error detecting macOS displays: %s", exc)

    return displays


def _detect_displays_linux() -> List[DisplayInfo]:
    """Detect displays on Linux using xrandr.

    Returns:
        List of DisplayInfo for detected displays
    """
    displays = []

    try:
        # Use xrandr to get display information
        result = subprocess.run(
            ["xrandr", "--query"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            logger.error("xrandr failed: %s", result.stderr)
            return displays

        lines = result.stdout.split("\n")
        current_display = None

        for line in lines:
            # Check for connected display
            if " connected" in line:
                parts = line.split()
                name = parts[0]
                is_primary = "primary" in line

                # Parse resolution from next line or current line
                resolution_match = re.search(r"(\d+)x(\d+)\+(\d+)\+(\d+)", line)
                if not resolution_match:
                    # Try to find resolution in format "1920x1080"
                    resolution_match = re.search(r"(\d+)x(\d+)", line)

                if resolution_match:
                    width = int(resolution_match.group(1))
                    height = int(resolution_match.group(2))
                    position_x = (
                        int(resolution_match.group(3))
                        if len(resolution_match.groups()) > 2
                        else 0
                    )
                    position_y = (
                        int(resolution_match.group(4))
                        if len(resolution_match.groups()) > 3
                        else 0
                    )

                    current_display = {
                        "name": name,
                        "width": width,
                        "height": height,
                        "position_x": position_x,
                        "position_y": position_y,
                        "is_primary": is_primary,
                    }

            # Check for refresh rate in mode line
            elif current_display and "*" in line:
                # Current mode marked with *
                refresh_match = re.search(r"(\d+\.\d+)\*", line)
                if refresh_match:
                    refresh_rate = float(refresh_match.group(1))

                    display_info = DisplayInfo(
                        name=current_display["name"],
                        identifier=current_display["name"],
                        width=current_display["width"],
                        height=current_display["height"],
                        refresh_rate=refresh_rate,
                        is_primary=current_display["is_primary"],
                        position_x=current_display["position_x"],
                        position_y=current_display["position_y"],
                        scale_factor=1.0,
                    )
                    displays.append(display_info)
                    current_display = None

        logger.info("Detected %d displays on Linux", len(displays))

    except subprocess.TimeoutExpired:
        logger.error("Display detection timed out")
    except Exception as exc:
        logger.error("Error detecting Linux displays: %s", exc)

    return displays


def _detect_displays_windows() -> List[DisplayInfo]:
    """Detect displays on Windows using win32api.

    Returns:
        List of DisplayInfo for detected displays
    """
    displays = []

    try:
        import win32api
        import win32con

        monitor_info = win32api.EnumDisplayMonitors()

        for idx, (hmon, hdc, rect) in enumerate(monitor_info):
            monitor = win32api.GetMonitorInfo(hmon)
            is_primary = bool(monitor["Flags"] & win32con.MONITORINFOF_PRIMARY)

            # Get device information
            device = win32api.EnumDisplayDevices(None, idx)
            device_name = device.DeviceName

            # Get current settings
            settings = win32api.EnumDisplaySettings(
                device_name, win32con.ENUM_CURRENT_SETTINGS
            )

            display_info = DisplayInfo(
                name=device.DeviceString + (" (Primary)" if is_primary else ""),
                identifier=device_name,
                width=settings.PelsWidth,
                height=settings.PelsHeight,
                refresh_rate=float(settings.DisplayFrequency),
                is_primary=is_primary,
                position_x=rect[0],
                position_y=rect[1],
                scale_factor=1.0,
            )
            displays.append(display_info)

        logger.info("Detected %d displays on Windows", len(displays))

    except ImportError:
        logger.warning("win32api not available for display detection")
    except Exception as exc:
        logger.error("Error detecting Windows displays: %s", exc)

    return displays


# Helper functions


def _parse_resolution(resolution_str: str) -> Tuple[int, int]:
    """Parse resolution string.

    Args:
        resolution_str: Resolution string like "1920 x 1080" or "1920x1080"

    Returns:
        Tuple of (width, height)
    """
    if not resolution_str:
        return (1920, 1080)  # Default

    # Try to extract numbers
    numbers = re.findall(r"\d+", resolution_str)

    if len(numbers) >= 2:
        return (int(numbers[0]), int(numbers[1]))

    return (1920, 1080)  # Default


def _parse_refresh_rate(refresh_str: str) -> float:
    """Parse refresh rate string.

    Args:
        refresh_str: Refresh rate string like "60 Hz" or "60.0"

    Returns:
        Refresh rate in Hz
    """
    if not refresh_str:
        return 60.0  # Default

    # Extract first number
    numbers = re.findall(r"\d+\.?\d*", refresh_str)

    if numbers:
        return float(numbers[0])

    return 60.0  # Default
