"""Camera Interface - Abstract Camera Hardware Interface"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum


class CameraStatus(Enum):
    """Camera status enumeration"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    READY = "ready"
    ACQUIRING = "acquiring"
    ERROR = "error"


class CameraInterface(ABC):
    """Abstract interface for camera hardware"""

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to camera hardware"""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from camera hardware"""
        pass

    @abstractmethod
    async def get_status(self) -> CameraStatus:
        """Get current camera status"""
        pass

    @abstractmethod
    async def start_acquisition(self, parameters: Dict[str, Any]) -> bool:
        """Start image acquisition"""
        pass

    @abstractmethod
    async def stop_acquisition(self) -> bool:
        """Stop image acquisition"""
        pass

    @abstractmethod
    async def get_image(self) -> Optional[bytes]:
        """Get acquired image data"""
        pass