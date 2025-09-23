"""Mock GPU Processing Implementation for Development"""

from typing import Dict, Any, Optional
from ..abstract.gpu_interface import GPUInterface, GPUStatus


class MockProcessing(GPUInterface):
    """Mock GPU processing implementation for development and testing"""

    def __init__(self):
        self._status = GPUStatus.UNAVAILABLE

    async def initialize(self) -> bool:
        """Mock GPU initialization"""
        self._status = GPUStatus.INITIALIZING
        # Simulate initialization
        self._status = GPUStatus.READY
        return True

    async def get_status(self) -> GPUStatus:
        """Get mock GPU status"""
        return self._status

    async def get_capabilities(self) -> Dict[str, Any]:
        """Get mock GPU capabilities"""
        return {
            "type": "mock_gpu",
            "memory": "8GB",
            "cores": "1024",
            "api": "mock_api",
            "version": "1.0.0"
        }

    async def process_data(self, data: bytes, parameters: Dict[str, Any]) -> Optional[bytes]:
        """Mock data processing"""
        if self._status == GPUStatus.READY:
            self._status = GPUStatus.PROCESSING
            # Simulate processing
            processed_data = f"processed_{len(data)}_bytes".encode()
            self._status = GPUStatus.READY
            return processed_data
        return None

    async def cleanup(self) -> bool:
        """Mock GPU cleanup"""
        self._status = GPUStatus.UNAVAILABLE
        return True