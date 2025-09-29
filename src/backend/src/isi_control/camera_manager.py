"""Camera detection and management using OpenCV."""

import cv2
import logging
from typing import List, Dict, Optional, Any
import platform
import subprocess
import json

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

    def _get_available_camera_indices(self) -> List[int]:
        """Get list of available camera indices using platform-specific methods."""
        available_indices = []

        try:
            system = platform.system()

            if system == "Darwin":  # macOS
                # Use system_profiler to get actual camera devices
                result = subprocess.run(
                    ["system_profiler", "SPCameraDataType", "-json"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    cameras = data.get("SPCameraDataType", [])
                    # Add index for each detected camera
                    for i, camera in enumerate(cameras):
                        available_indices.append(i)
                        logger.debug(f"Found camera via system_profiler: {camera.get('_name', 'Unknown')}")
                else:
                    # Fallback: assume index 0 exists if we can't enumerate
                    available_indices = [0]

            elif system == "Linux":
                # Check /dev/video* devices
                try:
                    result = subprocess.run(
                        ["ls", "/dev/video*"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        video_devices = result.stdout.strip().split('\n')
                        for device in video_devices:
                            if device.startswith('/dev/video'):
                                try:
                                    index = int(device.split('video')[1])
                                    available_indices.append(index)
                                except (ValueError, IndexError):
                                    continue
                except subprocess.TimeoutExpired:
                    available_indices = [0]  # Fallback

            else:  # Windows or other
                # For Windows/other systems, use conservative approach
                available_indices = [0]  # Most systems have at least one camera at index 0

        except Exception as e:
            logger.debug(f"Failed to enumerate cameras via system methods: {e}")
            # Fallback to checking just index 0
            available_indices = [0]

        logger.debug(f"Available camera indices: {available_indices}")
        return available_indices

    def detect_cameras(self, max_cameras: int = 10) -> List[CameraInfo]:
        """Detect available cameras using OpenCV with smart enumeration.

        Args:
            max_cameras: Maximum number of camera indices to check

        Returns:
            List of detected cameras
        """
        logger.info("Starting camera detection...")
        self.detected_cameras.clear()

        # Get available camera indices using platform-specific methods
        available_indices = self._get_available_camera_indices()

        # Only check the indices that are known to exist
        for i in available_indices:
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

    def get_camera_capabilities(self, camera_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed camera capabilities from already-detected camera info.

        Args:
            camera_name: Name of camera to get capabilities for

        Returns:
            Dictionary with camera capabilities or None if failed
        """
        try:
            # If no cameras detected yet, trigger detection
            if not self.detected_cameras:
                logger.info("No detected cameras available, triggering camera detection")
                self.detect_cameras()

            # First try exact match by name
            camera = next((c for c in self.detected_cameras if c.name == camera_name and c.is_available), None)

            # If no exact match, try partial match (handles device IDs in parentheses)
            if not camera:
                camera = next((c for c in self.detected_cameras if
                              (camera_name.startswith(c.name) or c.name in camera_name) and c.is_available), None)

            if not camera:
                logger.warning(f"Camera not found in detected cameras: {camera_name}")
                return None

            if not camera.properties:
                logger.warning(f"No properties available for camera: {camera_name}")
                return None

            # Return capabilities in same format expected by frontend
            capabilities = {
                "width": camera.properties.get("width", -1),
                "height": camera.properties.get("height", -1),
                "frameRate": camera.properties.get("fps", -1)
            }

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

        # Return only available camera names as strings for frontend dropdown
        camera_list = [camera.name for camera in cameras if camera.is_available]

        return {
            "success": True,
            "type": "detect_cameras",
            "cameras": camera_list
        }
    except Exception as e:
        logger.error(f"Camera detection failed: {e}")
        return {
            "success": False,
            "type": "detect_cameras",
            "error": str(e),
            "cameras": []
        }


def handle_get_camera_capabilities(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_camera_capabilities IPC command."""
    try:
        camera_name = command.get("camera_name")

        if not camera_name:
            return {
                "success": False,
                "type": "get_camera_capabilities",
                "error": "camera_name is required"
            }

        capabilities = camera_manager.get_camera_capabilities(camera_name)

        if capabilities is None:
            return {
                "success": False,
                "type": "get_camera_capabilities",
                "error": f"Camera not found: {camera_name}"
            }

        return {
            "success": True,
            "type": "get_camera_capabilities",
            "capabilities": capabilities
        }

    except Exception as e:
        logger.error(f"Failed to get camera capabilities: {e}")
        return {
            "success": False,
            "type": "get_camera_capabilities",
            "error": str(e)
        }


def handle_camera_stream_started(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle camera_stream_started IPC command"""
    try:
        camera_name = command.get('camera_name', 'unknown')
        logger.info(f"Camera stream started: {camera_name}")
        return {
            "success": True,
            "type": "camera_stream_started",
            "message": f"Camera stream started for {camera_name}"
        }
    except Exception as e:
        logger.error(f"Error in handle_camera_stream_started: {e}")
        return {
            "success": False,
            "type": "camera_stream_started",
            "error": str(e)
        }


def handle_camera_stream_stopped(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle camera_stream_stopped IPC command"""
    try:
        camera_name = command.get('camera_name', 'unknown')
        logger.info(f"Camera stream stopped: {camera_name}")
        return {
            "success": True,
            "type": "camera_stream_stopped",
            "message": f"Camera stream stopped for {camera_name}"
        }
    except Exception as e:
        logger.error(f"Error in handle_camera_stream_stopped: {e}")
        return {
            "success": False,
            "type": "camera_stream_stopped",
            "error": str(e)
        }


def handle_camera_capture(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle camera_capture IPC command"""
    try:
        camera_name = command.get('camera_name', 'unknown')
        timestamp = command.get('timestamp', 'unknown')
        logger.info(f"Camera capture from {camera_name} at {timestamp}")
        return {
            "success": True,
            "type": "camera_capture",
            "message": f"Camera capture logged for {camera_name}"
        }
    except Exception as e:
        logger.error(f"Error in handle_camera_capture: {e}")
        return {
            "success": False,
            "type": "camera_capture",
            "error": str(e)
        }


# Global camera manager instance
camera_manager = CameraManager()