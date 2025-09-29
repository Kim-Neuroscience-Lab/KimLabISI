"""
Hardware Utilities - Shared patterns for hardware detection and management

This module extracts common patterns used across camera and display managers
to reduce duplication and provide consistent hardware abstractions.
"""

import logging
import platform
import subprocess
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


@dataclass
class HardwareDevice:
    """Base class for hardware device information"""
    name: str
    identifier: str
    is_available: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HardwareDetector(ABC):
    """Abstract base class for hardware detection"""

    @abstractmethod
    def detect_devices(self) -> List[HardwareDevice]:
        """Detect all available devices of this type"""
        pass

    @abstractmethod
    def get_device_capabilities(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed capabilities of a specific device"""
        pass


def run_system_command(command: List[str], timeout: int = 10) -> Tuple[bool, str, str]:
    """
    Run a system command and return success status, stdout, and stderr

    Args:
        command: Command and arguments as list
        timeout: Command timeout in seconds

    Returns:
        (success, stdout, stderr)
    """
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return (result.returncode == 0, result.stdout, result.stderr)
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out: {' '.join(command)}")
        return (False, "", "Command timed out")
    except Exception as e:
        logger.error(f"Command failed: {' '.join(command)}: {e}")
        return (False, "", str(e))


def parse_system_profiler_displays() -> List[Dict[str, Any]]:
    """
    Parse macOS system_profiler display data

    Returns:
        List of display dictionaries with parsed information
    """
    success, stdout, stderr = run_system_command(
        ['system_profiler', 'SPDisplaysDataType', '-json']
    )

    if not success:
        logger.error(f"system_profiler failed: {stderr}")
        return []

    try:
        data = json.loads(stdout)
        displays = []

        if 'SPDisplaysDataType' in data:
            for item in data['SPDisplaysDataType']:
                if 'spdisplays_ndrvs' in item:
                    for idx, display in enumerate(item['spdisplays_ndrvs']):
                        parsed_display = parse_display_info(display, idx)
                        if parsed_display:
                            displays.append(parsed_display)

        return displays
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse system_profiler JSON: {e}")
        return []


def parse_display_info(display: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
    """
    Parse individual display information from system_profiler

    Args:
        display: Raw display data from system_profiler
        index: Display index for fallback naming

    Returns:
        Parsed display information or None if parsing fails
    """
    try:
        # Parse resolution string like "1728 x 1117 @ 120.00Hz"
        resolution = display.get('_spdisplays_resolution', '1920 x 1080 @ 60.00Hz')

        if ' @ ' in resolution:
            res_part, refresh_part = resolution.split(' @ ')
            refresh_rate = float(refresh_part.replace('Hz', ''))
        else:
            res_part = resolution
            refresh_rate = 60.0

        # Parse width x height
        parts = res_part.replace(' ', '').split('x')
        width = int(parts[0]) if len(parts) > 0 else 1920
        height = int(parts[1]) if len(parts) > 1 else 1080

        # Check if primary display
        is_primary = display.get('spdisplays_main') == 'spdisplays_yes'

        # Check for Retina/HiDPI
        pixel_resolution = display.get('spdisplays_pixelresolution', '')
        is_retina = 'Retina' in pixel_resolution
        scale_factor = 2.0 if is_retina else 1.0

        return {
            'name': display.get('_name', f'Display {index + 1}'),
            'width': width,
            'height': height,
            'refresh_rate': refresh_rate,
            'is_primary': is_primary,
            'scale_factor': scale_factor,
            'identifier': f"display_{display.get('_spdisplays_displayID', index)}",
            'position_x': 0,  # system_profiler doesn't provide position
            'position_y': 0,
        }

    except (ValueError, IndexError, KeyError) as e:
        logger.warning(f"Failed to parse display info: {e}")
        return None


def create_ipc_handler(handler_func, command_type: str):
    """
    Create a standardized IPC handler wrapper

    Args:
        handler_func: The actual handler function
        command_type: Type string for responses

    Returns:
        Wrapped handler function
    """
    def wrapper(command: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = handler_func(command)
            if isinstance(result, dict) and 'success' in result:
                return result
            else:
                # Wrap non-standard responses
                return {
                    "success": True,
                    "type": command_type,
                    "data": result
                }
        except Exception as e:
            logger.error(f"Error in {command_type} handler: {e}")
            return {
                "success": False,
                "type": command_type,
                "error": str(e)
            }

    return wrapper


def get_platform_info() -> Dict[str, str]:
    """Get basic platform information for hardware detection"""
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor()
    }


def estimate_device_capabilities(device_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Estimate device capabilities based on basic information

    Args:
        device_info: Basic device information

    Returns:
        Extended capabilities dictionary
    """
    capabilities = device_info.copy()

    # Add computed fields if this is a display
    if 'width' in device_info and 'height' in device_info:
        width, height = device_info['width'], device_info['height']
        capabilities.update({
            "aspect_ratio": f"{width}:{height}",
            "pixel_count": width * height,
            "diagonal_estimate": _estimate_diagonal_inches(width, height)
        })

    return capabilities


def _estimate_diagonal_inches(width: int, height: int) -> float:
    """Estimate diagonal size in inches based on common resolutions"""
    common_sizes = {
        (1920, 1080): 24.0,
        (2560, 1440): 27.0,
        (3840, 2160): 32.0,
        (1366, 768): 15.6,
        (1728, 1117): 13.3,  # MacBook Air
        (2560, 1600): 13.3,  # MacBook Pro
    }

    diagonal = common_sizes.get((width, height))
    if diagonal:
        return diagonal

    # Rough estimate based on pixel density
    pixels = (width ** 2 + height ** 2) ** 0.5
    return round(pixels / 100, 1)