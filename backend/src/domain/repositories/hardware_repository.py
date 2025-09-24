"""
Domain Hardware Repository Interface

Abstract interface for hardware management following clean architecture.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Set
from enum import Enum

from ..value_objects.workflow_state import HardwareRequirement


class HardwareFactoryInterface(ABC):
    """Abstract interface for hardware factory"""

    @abstractmethod
    def detect_hardware_capabilities(self) -> Dict[HardwareRequirement, Any]:
        """Detect available hardware capabilities"""
        pass

    @abstractmethod
    def create_camera_interface(self):
        """Create camera interface"""
        pass

    @abstractmethod
    def create_display_interface(self):
        """Create display interface"""
        pass

    @abstractmethod
    def create_timing_interface(self):
        """Create timing interface"""
        pass

    @abstractmethod
    def create_gpu_interface(self):
        """Create GPU interface"""
        pass


class CameraInterface(ABC):
    """Abstract camera interface"""

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to camera hardware"""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from camera hardware"""
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


class DisplayInterface(ABC):
    """Abstract display interface"""

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to display hardware"""
        pass

    @abstractmethod
    async def start_presentation(self) -> bool:
        """Start stimulus presentation"""
        pass

    @abstractmethod
    async def stop_presentation(self) -> bool:
        """Stop stimulus presentation"""
        pass

    @abstractmethod
    async def update_frame(self, frame: Any) -> bool:
        """Update displayed frame"""
        pass


class TimingInterface(ABC):
    """Abstract timing interface"""

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to timing system"""
        pass

    @abstractmethod
    async def start_timing(self) -> bool:
        """Start timing synchronization"""
        pass

    @abstractmethod
    async def stop_timing(self) -> bool:
        """Stop timing synchronization"""
        pass