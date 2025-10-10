"""
ISI Display Management - Streamlined display detection and selection

Focused module for display detection and selection for stimulus presentation.
Uses shared hardware utilities to minimize duplication.
"""

import platform
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from .hardware_utils import (
    HardwareDevice,
    HardwareDetector,
    parse_system_profiler_displays,
    estimate_device_capabilities,
)
from .service_locator import get_services
from .logging_utils import get_logger
from .ipc_utils import ipc_handler

logger = get_logger(__name__)


@dataclass
class DisplayInfo(HardwareDevice):
    """Display device information"""

    width: int = 1920
    height: int = 1080
    refresh_rate: float = 60.0
    is_primary: bool = False
    position_x: int = 0
    position_y: int = 0
    scale_factor: float = 1.0


class DisplayDetector(HardwareDetector):
    """Cross-platform display detection"""

    def detect_devices(self) -> List[DisplayInfo]:
        """Detect all connected displays"""
        displays = []

        try:
            if platform.system() == "Darwin":  # macOS
                displays = self._detect_displays_macos()
            elif platform.system() == "Windows":
                displays = self._detect_displays_windows()
            elif platform.system() == "Linux":
                displays = self._detect_displays_linux()
            else:
                logger.warning(f"Unsupported platform: {platform.system()}")
                displays = []

            return displays

        except Exception as e:
            logger.error(f"Error detecting displays: {e}")
            return []

    def get_device_capabilities(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed capabilities of a specific display"""
        displays = self.detect_devices()

        # First try to match by identifier
        display = next((d for d in displays if d.identifier == device_id), None)

        # If no match by identifier, try matching by name
        if not display:
            display = next((d for d in displays if d.name == device_id), None)

        if not display:
            return None

        return estimate_device_capabilities(display.to_dict())

    def _detect_displays_macos(self) -> List[DisplayInfo]:
        """Detect displays on macOS using system_profiler"""
        displays = []

        try:
            display_data = parse_system_profiler_displays()
            for data in display_data:
                display_info = DisplayInfo(
                    name=data["name"],
                    identifier=data["identifier"],
                    width=data["width"],
                    height=data["height"],
                    refresh_rate=data["refresh_rate"],
                    is_primary=data["is_primary"],
                    position_x=data["position_x"],
                    position_y=data["position_y"],
                    scale_factor=data["scale_factor"],
                    is_available=True,
                )
                displays.append(display_info)

        except Exception as e:
            logger.error(f"Error detecting macOS displays: {e}")

        return displays

    def _detect_displays_windows(self) -> List[DisplayInfo]:
        """Detect displays on Windows - simplified implementation"""
        displays = []

        try:
            import win32api
            import win32con

            monitor_info = win32api.EnumDisplayMonitors()

            for idx, (hmon, hdc, rect) in enumerate(monitor_info):
                monitor = win32api.GetMonitorInfo(hmon)
                is_primary = monitor["Flags"] & win32con.MONITORINFOF_PRIMARY

                device = win32api.EnumDisplayDevices(None, idx)
                settings = win32api.EnumDisplaySettings(
                    device.DeviceName, win32con.ENUM_CURRENT_SETTINGS
                )

                display_info = DisplayInfo(
                    name=device.DeviceString + (" (Primary)" if is_primary else ""),
                    identifier=device.DeviceName,
                    width=settings.PelsWidth,
                    height=settings.PelsHeight,
                    refresh_rate=float(settings.DisplayFrequency),
                    is_primary=bool(is_primary),
                    position_x=rect[0],
                    position_y=rect[1],
                    scale_factor=1.0,
                    is_available=True,
                )
                displays.append(display_info)

        except ImportError:
            logger.warning("win32api not available")
        except Exception as e:
            logger.error(f"Error detecting Windows displays: {e}")

        return displays

    def _detect_displays_linux(self) -> List[DisplayInfo]:
        """Detect displays on Linux - simplified implementation"""
        displays = []

        try:
            import subprocess
            import re

            result = subprocess.run(["xrandr"], capture_output=True, text=True)
            if result.returncode != 0:
                return displays

            lines = result.stdout.split("\n")
            for line in lines:
                if " connected" in line:
                    parts = line.split()
                    name = parts[0]
                    is_primary = "primary" in line

                    # Simple resolution parsing
                    for part in parts:
                        match = re.match(r"(\d+)x(\d+)", part)
                        if match:
                            width = int(match.group(1))
                            height = int(match.group(2))

                            display_info = DisplayInfo(
                                name=name + (" (Primary)" if is_primary else ""),
                                identifier=name,
                                width=width,
                                height=height,
                                refresh_rate=60.0,
                                is_primary=is_primary,
                                position_x=0,
                                position_y=0,
                                scale_factor=1.0,
                                is_available=True,
                            )
                            displays.append(display_info)
                            break

        except Exception as e:
            logger.error(f"Error detecting Linux displays: {e}")

        return displays


class DisplayManager:
    """Simple display manager for ISI experiments"""

    def __init__(self):
        self.detector = DisplayDetector()
        self.displays: List[DisplayInfo] = []
        self.selected_display: Optional[str] = None
        self._cached_monitor_state: Optional[Dict[str, Any]] = None
        logger.info("DisplayManager initialized")

    def detect_displays(self, force: bool = False) -> List[DisplayInfo]:
        """Detect and cache available displays"""
        if self.displays and not force:
            return self.displays

        self.displays = self.detector.detect_devices()

        # Auto-select primary display if none selected
        if not self.selected_display and self.displays:
            primary = next((d for d in self.displays if d.is_primary), self.displays[0])
            self.selected_display = primary.identifier
            logger.info(f"Auto-selected primary display: {primary.name}")

        self._update_monitor_parameters_if_needed(force=force)
        return self.displays

    def select_display(self, display_id: str) -> bool:
        """Select a display for stimulus presentation"""
        if not any(d.identifier == display_id for d in self.displays):
            self.detect_displays(force=True)

        if any(d.identifier == display_id for d in self.displays):
            self.selected_display = display_id
            logger.info(f"Selected display: {display_id}")
            self._update_monitor_parameters_if_needed(force=True)
            return True
        else:
            logger.error(f"Display not found: {display_id}")
            return False

    def get_display_capabilities(self, display_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed capabilities of a specific display"""
        return self.detector.get_device_capabilities(display_id)

    def _build_monitor_state(self) -> Optional[Dict[str, Any]]:
        if not self.displays:
            return None

        selected = next(
            (
                display
                for display in self.displays
                if display.identifier == self.selected_display
            ),
            None,
        )

        if selected is None:
            selected = self.displays[0]

        return {
            "selected_display": selected.identifier,
            "available_displays": [display.identifier for display in self.displays],
            "monitor_width_px": selected.width,
            "monitor_height_px": selected.height,
            "monitor_fps": int(selected.refresh_rate),
        }

    def _update_monitor_parameters_if_needed(self, force: bool = False) -> None:
        monitor_state = self._build_monitor_state()

        if monitor_state is None:
            return

        if not force and monitor_state == self._cached_monitor_state:
            return

        param_manager = get_services().parameter_manager
        param_manager.update_parameter_group("monitor", monitor_state)
        self._cached_monitor_state = monitor_state


# Global display manager instance
display_manager = DisplayManager()


# IPC Handler Functions
@ipc_handler("detect_displays")
def handle_detect_displays(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle detect_displays IPC command"""
    force_refresh = bool(command.get("force", False))
    displays = display_manager.detect_displays(force=force_refresh)
    return {
        "displays": [d.to_dict() for d in displays],
        "selected_display": display_manager.selected_display,
    }


@ipc_handler("get_display_capabilities")
def handle_get_display_capabilities(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_display_capabilities IPC command"""
    display_id = command.get("display_id")
    if not display_id:
        return {
            "success": False,
            "error": "display_id is required",
        }

    capabilities = display_manager.get_display_capabilities(display_id)
    if capabilities:
        return {"capabilities": capabilities}
    else:
        return {
            "success": False,
            "error": f"Display not found: {display_id}",
        }


@ipc_handler("select_display")
def handle_select_display(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle select_display IPC command"""
    display_id = command.get("display_id")
    if not display_id:
        return {
            "success": False,
            "error": "display_id is required",
        }

    success = display_manager.select_display(display_id)
    return {
        "success": success,
        "selected_display": display_manager.selected_display if success else None,
        "error": None if success else f"Failed to select display: {display_id}",
    }
