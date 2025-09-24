"""Mock Camera Implementation for Development"""

from typing import Dict, Any, Optional
from ..abstract.camera_interface import CameraInterface, CameraStatus


class MockCamera(CameraInterface):
    """Mock camera implementation for development and testing"""

    def __init__(self):
        self._status = CameraStatus.DISCONNECTED
        self._mock_image_counter = 0

    async def connect(self) -> bool:
        """Mock camera connection"""
        self._status = CameraStatus.CONNECTING
        # Simulate connection delay
        self._status = CameraStatus.READY
        return True

    async def disconnect(self) -> bool:
        """Mock camera disconnection"""
        self._status = CameraStatus.DISCONNECTED
        return True

    async def get_status(self) -> CameraStatus:
        """Get mock camera status"""
        return self._status

    async def start_acquisition(self, parameters: Dict[str, Any]) -> bool:
        """Start mock image acquisition"""
        if self._status == CameraStatus.READY:
            self._status = CameraStatus.ACQUIRING
            return True
        return False

    async def stop_acquisition(self) -> bool:
        """Stop mock image acquisition"""
        if self._status == CameraStatus.ACQUIRING:
            self._status = CameraStatus.READY
            return True
        return False

    async def get_image(self) -> Optional[bytes]:
        """Get mock image data"""
        if self._status == CameraStatus.ACQUIRING:
            self._mock_image_counter += 1
            # Return mock image data
            return f"mock_image_data_{self._mock_image_counter}".encode()
        return None