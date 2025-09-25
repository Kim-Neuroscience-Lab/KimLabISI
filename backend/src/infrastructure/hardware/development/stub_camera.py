"""
Development Camera Stub Implementation

This is a functional stub implementation for camera operations during development,
providing a minimal but working implementation of the camera interface.
"""

import logging
import asyncio
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from abstract.camera_interface import CameraInterface, CameraStatus

logger = logging.getLogger(__name__)


class StubCamera(CameraInterface):
    """
    Development Camera stub implementation

    Provides minimal but functional camera operations for development
    across all platforms using simulated image generation.
    """

    def __init__(self):
        self._status = CameraStatus.DISCONNECTED
        self._capturing = False
        self._frame_count = 0
        self._settings = {
            "exposure_time": 0.01,  # 10ms
            "gain": 1.0,
            "resolution": (2048, 2048),
            "pixel_format": "mono16"
        }
        logger.info("Development Camera stub initialized")

    async def initialize(self) -> bool:
        """Initialize the camera stub"""
        try:
            self._status = CameraStatus.INITIALIZING

            # Simulate initialization delay
            await asyncio.sleep(0.1)

            self._status = CameraStatus.READY
            logger.info("Development Camera stub initialization complete")
            return True
        except Exception as e:
            logger.error(f"Development Camera stub initialization failed: {e}")
            self._status = CameraStatus.ERROR
            return False

    async def get_status(self) -> CameraStatus:
        """Get camera status"""
        return self._status

    async def start_capture(self) -> bool:
        """Start image capture"""
        if self._status != CameraStatus.READY:
            return False

        self._capturing = True
        self._status = CameraStatus.CAPTURING
        logger.info("Started development camera capture")
        return True

    async def stop_capture(self) -> bool:
        """Stop image capture"""
        if not self._capturing:
            return False

        self._capturing = False
        self._status = CameraStatus.READY
        logger.info("Stopped development camera capture")
        return True

    async def capture_frame(self) -> Optional[np.ndarray]:
        """Capture a single frame (generate test pattern)"""
        if self._status != CameraStatus.CAPTURING:
            return None

        try:
            # Generate a simple test pattern
            height, width = self._settings["resolution"]

            # Create a gradient pattern with some noise
            x = np.linspace(0, 2 * np.pi, width)
            y = np.linspace(0, 2 * np.pi, height)
            X, Y = np.meshgrid(x, y)

            # Generate pattern: sin wave + noise + frame counter effect
            pattern = (np.sin(X) * np.cos(Y) +
                      0.1 * np.random.random((height, width)) +
                      0.1 * np.sin(self._frame_count * 0.1))

            # Normalize to 16-bit range
            pattern = ((pattern + 1.2) / 2.4 * 65535).astype(np.uint16)

            self._frame_count += 1

            # Simulate exposure time delay
            exposure_delay = self._settings["exposure_time"]
            await asyncio.sleep(min(exposure_delay, 0.1))  # Cap at 100ms for development

            logger.debug(f"Captured development frame #{self._frame_count}")
            return pattern

        except Exception as e:
            logger.error(f"Frame capture failed: {e}")
            return None

    async def set_exposure_time(self, exposure_ms: float) -> bool:
        """Set camera exposure time"""
        if self._status == CameraStatus.DISCONNECTED:
            return False

        if not 0.1 <= exposure_ms <= 10000:  # 0.1ms to 10s range
            logger.warning(f"Exposure time {exposure_ms}ms out of range")
            return False

        self._settings["exposure_time"] = exposure_ms / 1000  # Convert to seconds
        logger.info(f"Set development camera exposure time to {exposure_ms}ms")
        return True

    async def set_gain(self, gain: float) -> bool:
        """Set camera gain"""
        if self._status == CameraStatus.DISCONNECTED:
            return False

        if not 1.0 <= gain <= 16.0:  # Typical gain range
            logger.warning(f"Gain {gain} out of range")
            return False

        self._settings["gain"] = gain
        logger.info(f"Set development camera gain to {gain}")
        return True

    async def set_resolution(self, width: int, height: int) -> bool:
        """Set camera resolution"""
        if self._status == CameraStatus.DISCONNECTED:
            return False

        # Validate resolution (common sensor sizes)
        valid_resolutions = [
            (640, 480), (1024, 768), (1920, 1080),
            (2048, 2048), (4096, 4096)
        ]

        if (width, height) not in valid_resolutions:
            logger.warning(f"Resolution {width}x{height} not in valid list")
            return False

        self._settings["resolution"] = (width, height)
        logger.info(f"Set development camera resolution to {width}x{height}")
        return True

    async def get_camera_info(self) -> Dict[str, Any]:
        """Get camera information"""
        return {
            "model": "Development Camera Stub",
            "serial_number": "DEV-STUB-001",
            "firmware_version": "1.0.0-dev",
            "sensor_type": "Simulated CMOS",
            "max_resolution": (4096, 4096),
            "pixel_size_um": 3.45,
            "bit_depth": 16,
            "color_mode": "monochrome",
            "cooling": False,
            "stub_implementation": True
        }

    async def get_capabilities(self) -> Dict[str, Any]:
        """Get camera capabilities"""
        return {
            "min_exposure_ms": 0.1,
            "max_exposure_ms": 10000.0,
            "min_gain": 1.0,
            "max_gain": 16.0,
            "supported_resolutions": [
                {"width": 640, "height": 480},
                {"width": 1024, "height": 768},
                {"width": 1920, "height": 1080},
                {"width": 2048, "height": 2048},
                {"width": 4096, "height": 4096}
            ],
            "pixel_formats": ["mono16"],
            "max_frame_rate": 30.0,
            "has_temperature_control": False,
            "has_mechanical_shutter": False
        }

    async def get_current_settings(self) -> Dict[str, Any]:
        """Get current camera settings"""
        return self._settings.copy()

    async def save_settings_profile(self, profile_name: str) -> bool:
        """Save current settings as a profile (simulated)"""
        if self._status == CameraStatus.DISCONNECTED:
            return False

        logger.info(f"Saved development camera settings profile: {profile_name}")
        return True

    async def load_settings_profile(self, profile_name: str) -> bool:
        """Load settings profile (simulated)"""
        if self._status == CameraStatus.DISCONNECTED:
            return False

        logger.info(f"Loaded development camera settings profile: {profile_name}")
        return True

    async def get_last_frame_metadata(self) -> Optional[Dict[str, Any]]:
        """Get metadata for the last captured frame"""
        if self._frame_count == 0:
            return None

        return {
            "frame_number": self._frame_count,
            "timestamp": asyncio.get_event_loop().time(),
            "exposure_time_ms": self._settings["exposure_time"] * 1000,
            "gain": self._settings["gain"],
            "resolution": self._settings["resolution"],
            "temperature_c": 25.0,  # Simulated room temperature
            "is_simulated": True
        }

    async def cleanup(self) -> bool:
        """Cleanup camera resources"""
        try:
            if self._capturing:
                await self.stop_capture()

            self._status = CameraStatus.DISCONNECTED
            self._frame_count = 0
            logger.info("Development Camera stub cleanup complete")
            return True
        except Exception as e:
            logger.error(f"Development Camera stub cleanup failed: {e}")
            self._status = CameraStatus.ERROR
            return False