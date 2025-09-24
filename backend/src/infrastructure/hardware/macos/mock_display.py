"""Mock Display Implementation for Development"""

from typing import Dict, Any, Tuple
from ..abstract.display_interface import DisplayInterface, DisplayStatus


class MockDisplay(DisplayInterface):
    """Mock display implementation for development and testing"""

    def __init__(self):
        self._status = DisplayStatus.DISCONNECTED
        self._resolution = (1920, 1080)

    async def initialize(self) -> bool:
        """Mock display initialization"""
        self._status = DisplayStatus.CONNECTING
        # Simulate initialization
        self._status = DisplayStatus.READY
        return True

    async def get_status(self) -> DisplayStatus:
        """Get mock display status"""
        return self._status

    async def get_capabilities(self) -> Dict[str, Any]:
        """Get mock display capabilities"""
        return {
            "type": "mock_display",
            "max_resolution": "3840x2160",
            "refresh_rate": "60Hz",
            "color_depth": "24-bit",
            "api": "mock_display_api"
        }

    async def set_resolution(self, width: int, height: int) -> bool:
        """Set mock display resolution"""
        if self._status == DisplayStatus.READY:
            self._resolution = (width, height)
            return True
        return False

    async def get_resolution(self) -> Tuple[int, int]:
        """Get current mock display resolution"""
        return self._resolution

    async def display_pattern(self, pattern_data: bytes, parameters: Dict[str, Any]) -> bool:
        """Display mock pattern"""
        if self._status == DisplayStatus.READY:
            self._status = DisplayStatus.DISPLAYING
            # Simulate pattern display
            self._status = DisplayStatus.READY
            return True
        return False

    async def clear_display(self) -> bool:
        """Clear mock display"""
        if self._status in [DisplayStatus.READY, DisplayStatus.DISPLAYING]:
            self._status = DisplayStatus.READY
            return True
        return False