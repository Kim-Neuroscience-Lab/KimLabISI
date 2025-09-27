"""Display Interface - Abstract Display Hardware Interface"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
from enum import Enum


class DisplayStatus(Enum):
    """Display status enumeration"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    READY = "ready"
    DISPLAYING = "displaying"
    ERROR = "error"


class DisplayInterface(ABC):
    """Abstract interface for display hardware"""

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize display hardware"""
        pass

    @abstractmethod
    async def get_status(self) -> DisplayStatus:
        """Get current display status"""
        pass

    @abstractmethod
    async def get_capabilities(self) -> Dict[str, Any]:
        """Get display capabilities and specifications"""
        pass

    @abstractmethod
    async def set_resolution(self, width: int, height: int) -> bool:
        """Set display resolution"""
        pass

    @abstractmethod
    async def get_resolution(self) -> Tuple[int, int]:
        """Get current display resolution"""
        pass

    @abstractmethod
    async def display_pattern(self, pattern_data: bytes, parameters: Dict[str, Any]) -> bool:
        """Display a pattern on the screen"""
        pass

    @abstractmethod
    async def clear_display(self) -> bool:
        """Clear the display"""
        pass