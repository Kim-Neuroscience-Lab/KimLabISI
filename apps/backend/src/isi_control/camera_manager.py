"""Camera detection and management using OpenCV."""

import cv2
import logging
from typing import List, Dict, Optional, Any
import platform

logger = logging.getLogger(__name__)


class CameraInfo:
    """Information about a detected camera."""

    def __init__(self, index: int, name: str, backend: str = "OpenCV"):
        self.index = index
        self.name = name
        self.backend = backend
        self.is_available = False
        self.properties = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert camera info to dictionary."""
        return {
            "index": self.index,
            "name": self.name,
            "backend": self.backend,
            "is_available": self.is_available,
            "properties": self.properties
        }


class CameraManager:
    """Manages camera detection and access using OpenCV."""

    def __init__(self):
        self.detected_cameras: List[CameraInfo] = []
        self.active_camera: Optional[cv2.VideoCapture] = None

    def detect_cameras(self, max_cameras: int = 10) -> List[CameraInfo]:
        """Detect available cameras using OpenCV.

        Args:
            max_cameras: Maximum number of camera indices to check

        Returns:
            List of detected cameras
        """
        logger.info("Starting camera detection...")
        self.detected_cameras.clear()

        # Try to detect cameras by attempting to open each index
        for i in range(max_cameras):
            logger.debug(f"Checking camera index {i}")

            try:
                # Try to open the camera
                cap = cv2.VideoCapture(i)

                # Check if camera opened successfully
                if cap.isOpened():
                    # Try to read a frame to verify camera is actually working
                    ret, frame = cap.read()

                    if ret and frame is not None:
                        # Get camera properties
                        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        fps = cap.get(cv2.CAP_PROP_FPS)

                        # Generate camera name based on platform and index
                        name = self._generate_camera_name(i, width, height)

                        camera_info = CameraInfo(index=i, name=name, backend="OpenCV")
                        camera_info.is_available = True
                        camera_info.properties = {
                            "width": width,
                            "height": height,
                            "fps": fps,
                            "backend": cv2.getBuildInformation()
                        }

                        self.detected_cameras.append(camera_info)
                        logger.info(f"Detected camera: {name} at index {i} ({width}x{height})")

                    cap.release()

            except Exception as e:
                logger.debug(f"Failed to access camera index {i}: {e}")
                continue

        # Add PCO Camera as a mock entry if no real PCO camera is detected
        # This allows the UI to show the PCO option even when it's not connected
        pco_detected = any("PCO" in cam.name for cam in self.detected_cameras)
        if not pco_detected:
            pco_camera = CameraInfo(index=-1, name="PCO Camera", backend="PCO SDK")
            pco_camera.is_available = False  # Mark as unavailable since it's mock
            self.detected_cameras.insert(0, pco_camera)

        logger.info(f"Camera detection complete. Found {len([c for c in self.detected_cameras if c.is_available])} working cameras")
        return self.detected_cameras

    def _generate_camera_name(self, index: int, width: int, height: int) -> str:
        """Generate a user-friendly camera name."""
        system = platform.system()

        if system == "Darwin":  # macOS
            if index == 0:
                return "FaceTime HD Camera"
            else:
                return f"Camera {index}"
        elif system == "Windows":
            return f"Camera {index}"
        elif system == "Linux":
            return f"Video{index}"
        else:
            return f"Camera {index}"

    def get_camera_list(self) -> List[Dict[str, Any]]:
        """Get list of detected cameras as dictionaries."""
        if not self.detected_cameras:
            self.detect_cameras()

        return [camera.to_dict() for camera in self.detected_cameras]

    def get_available_cameras(self) -> List[Dict[str, Any]]:
        """Get list of only available cameras."""
        return [camera.to_dict() for camera in self.detected_cameras if camera.is_available]

    def open_camera(self, camera_index: int) -> bool:
        """Open a camera by index.

        Args:
            camera_index: Index of camera to open

        Returns:
            True if camera opened successfully
        """
        try:
            # Close existing camera if open
            if self.active_camera is not None:
                self.active_camera.release()
                self.active_camera = None

            # Open new camera
            self.active_camera = cv2.VideoCapture(camera_index)

            if self.active_camera.isOpened():
                logger.info(f"Successfully opened camera at index {camera_index}")
                return True
            else:
                logger.error(f"Failed to open camera at index {camera_index}")
                return False

        except Exception as e:
            logger.error(f"Error opening camera {camera_index}: {e}")
            return False

    def close_camera(self):
        """Close the active camera."""
        if self.active_camera is not None:
            self.active_camera.release()
            self.active_camera = None
            logger.info("Closed active camera")

    def capture_frame(self) -> Optional[any]:
        """Capture a frame from the active camera.

        Returns:
            Frame data if successful, None otherwise
        """
        if self.active_camera is None:
            logger.warning("No active camera to capture from")
            return None

        try:
            ret, frame = self.active_camera.read()
            if ret:
                return frame
            else:
                logger.warning("Failed to capture frame")
                return None
        except Exception as e:
            logger.error(f"Error capturing frame: {e}")
            return None

    def set_camera_property(self, property_id: int, value: float) -> bool:
        """Set a camera property.

        Args:
            property_id: OpenCV property ID (e.g., cv2.CAP_PROP_FRAME_WIDTH)
            value: Property value to set

        Returns:
            True if property was set successfully
        """
        if self.active_camera is None:
            logger.warning("No active camera to set property on")
            return False

        try:
            success = self.active_camera.set(property_id, value)
            if success:
                logger.info(f"Set camera property {property_id} to {value}")
            else:
                logger.warning(f"Failed to set camera property {property_id} to {value}")
            return success
        except Exception as e:
            logger.error(f"Error setting camera property: {e}")
            return False

    def get_camera_property(self, property_id: int) -> Optional[float]:
        """Get a camera property value.

        Args:
            property_id: OpenCV property ID

        Returns:
            Property value if successful, None otherwise
        """
        if self.active_camera is None:
            logger.warning("No active camera to get property from")
            return None

        try:
            value = self.active_camera.get(property_id)
            return value
        except Exception as e:
            logger.error(f"Error getting camera property: {e}")
            return None

    def get_camera_capabilities(self, camera_index: int) -> Optional[Dict[str, Any]]:
        """Get detailed camera capabilities by temporarily opening camera.

        Args:
            camera_index: Index of camera to get capabilities for

        Returns:
            Dictionary with camera capabilities or None if failed
        """
        try:
            cap = cv2.VideoCapture(camera_index)
            if not cap.isOpened():
                return None

            capabilities = {
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "frameRate": cap.get(cv2.CAP_PROP_FPS)
            }

            cap.release()
            return capabilities

        except Exception as e:
            logger.error(f"Error getting camera capabilities: {e}")
            return None

    def __del__(self):
        """Cleanup when object is destroyed."""
        self.close_camera()


def handle_detect_cameras(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle detect_cameras IPC command."""
    try:
        logger.info("Handling detect_cameras command")
        cameras = camera_manager.detect_cameras()

        camera_list = [camera.to_dict() for camera in cameras]

        return {
            "success": True,
            "cameras": camera_list
        }
    except Exception as e:
        logger.error(f"Camera detection failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "cameras": []
        }


def handle_get_camera_capabilities(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_camera_capabilities IPC command."""
    try:
        camera_name = command.get("camera_name")
        camera_index = command.get("camera_index")

        if not camera_name and camera_index is None:
            return {
                "success": False,
                "error": "Either camera_name or camera_index is required"
            }

        # Find camera by name or use index directly
        target_index = camera_index
        if camera_name and camera_index is None:
            cameras = camera_manager.detect_cameras()
            for camera in cameras:
                if camera.name == camera_name:
                    target_index = camera.index
                    break

            if target_index is None:
                return {
                    "success": False,
                    "error": f"Camera not found: {camera_name}"
                }

        capabilities = camera_manager.get_camera_capabilities(target_index)

        if capabilities is None:
            return {
                "success": False,
                "error": "Failed to retrieve camera capabilities"
            }

        return {
            "success": True,
            "capabilities": capabilities
        }

    except Exception as e:
        logger.error(f"Failed to get camera capabilities: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# Global camera manager instance
camera_manager = CameraManager()