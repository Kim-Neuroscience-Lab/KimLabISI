"""GPU Interface - Abstract GPU Processing Interface"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum


class GPUStatus(Enum):
    """GPU status enumeration"""
    UNAVAILABLE = "unavailable"
    INITIALIZING = "initializing"
    READY = "ready"
    PROCESSING = "processing"
    ERROR = "error"


class GPUInterface(ABC):
    """Abstract interface for GPU hardware"""

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize GPU for processing"""
        pass

    @abstractmethod
    async def get_status(self) -> GPUStatus:
        """Get current GPU status"""
        pass

    @abstractmethod
    async def get_capabilities(self) -> Dict[str, Any]:
        """Get GPU capabilities and specifications"""
        pass

    @abstractmethod
    async def process_data(self, data: bytes, parameters: Dict[str, Any]) -> Optional[bytes]:
        """Process data using GPU acceleration"""
        pass

    @abstractmethod
    async def cleanup(self) -> bool:
        """Cleanup GPU resources"""
        pass