"""Camera detection and management using OpenCV."""

import cv2
import numpy as np
import logging
from typing import List, Dict, Optional, Any, Tuple
import platform
import subprocess
import json
import time
import threading

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
            "properties": self.properties,
        }


class CameraManager:
    """Manages camera detection and access using OpenCV."""

    def __init__(self):
        self.detected_cameras: List[CameraInfo] = []
        self.active_camera: Optional[cv2.VideoCapture] = None
        self._has_detected = False

        # Acquisition state
        self.is_streaming = False
        self.current_frame = None
        self.current_frame_cropped = None  # Square cropped version
        self.last_capture_timestamp = None
        self.acquisition_thread: Optional[threading.Thread] = None
        self.acquisition_lock = threading.Lock()
        self.stop_acquisition_event = threading.Event()

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
                    timeout=5,
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    cameras = data.get("SPCameraDataType", [])
                    # Add index for each detected camera
                    for i, camera in enumerate(cameras):
                        available_indices.append(i)
                        logger.debug(
                            f"Found camera via system_profiler: {camera.get('_name', 'Unknown')}"
                        )
                else:
                    # Fallback: assume index 0 exists if we can't enumerate
                    available_indices = [0]

            elif system == "Linux":
                # Check /dev/video* devices
                try:
                    result = subprocess.run(
                        ["ls", "/dev/video*"], capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        video_devices = result.stdout.strip().split("\n")
                        for device in video_devices:
                            if device.startswith("/dev/video"):
                                try:
                                    index = int(device.split("video")[1])
                                    available_indices.append(index)
                                except (ValueError, IndexError):
                                    continue
                except subprocess.TimeoutExpired:
                    available_indices = [0]  # Fallback

            else:  # Windows or other
                # For Windows/other systems, use conservative approach
                available_indices = [
                    0
                ]  # Most systems have at least one camera at index 0

        except Exception as e:
            logger.debug(f"Failed to enumerate cameras via system methods: {e}")
            # Fallback to checking just index 0
            available_indices = [0]

        logger.debug(f"Available camera indices: {available_indices}")
        return available_indices

    def detect_cameras(
        self, max_cameras: int = 10, force: bool = False
    ) -> List[CameraInfo]:
        """Detect available cameras using OpenCV with smart enumeration.

        Args:
            max_cameras: Maximum number of camera indices to check

        Returns:
            List of detected cameras
        """
        if self._has_detected and not force:
            return self.detected_cameras

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
                            "backend": cv2.getBuildInformation(),
                        }

                        self.detected_cameras.append(camera_info)
                        logger.info(
                            f"Detected camera: {name} at index {i} ({width}x{height})"
                        )

                    cap.release()

            except Exception as e:
                logger.debug(f"Failed to access camera index {i}: {e}")
                continue

        logger.info(
            f"Camera detection complete. Found {len([c for c in self.detected_cameras if c.is_available])} working cameras"
        )
        self._has_detected = True
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
        return [
            camera.to_dict() for camera in self.detected_cameras if camera.is_available
        ]

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
                logger.warning(
                    f"Failed to set camera property {property_id} to {value}"
                )
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
                logger.info(
                    "No detected cameras available, triggering camera detection"
                )
                self.detect_cameras()

            # First try exact match by name
            camera = next(
                (
                    c
                    for c in self.detected_cameras
                    if c.name == camera_name and c.is_available
                ),
                None,
            )

            # If no exact match, try partial match (handles device IDs in parentheses)
            if not camera:
                camera = next(
                    (
                        c
                        for c in self.detected_cameras
                        if (camera_name.startswith(c.name) or c.name in camera_name)
                        and c.is_available
                    ),
                    None,
                )

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
                "frameRate": camera.properties.get("fps", -1),
            }

            return capabilities

        except Exception as e:
            logger.error(f"Error getting camera capabilities: {e}")
            return None

    def crop_to_square(self, frame: np.ndarray) -> np.ndarray:
        """
        Crop frame to square centered on smaller dimension.

        Args:
            frame: Input frame (height, width, channels)

        Returns:
            Square cropped frame
        """
        if frame is None:
            return None

        height, width = frame.shape[:2]
        size = min(height, width)

        # Calculate center crop coordinates
        y_start = (height - size) // 2
        x_start = (width - size) // 2

        # Crop to square
        cropped = frame[y_start : y_start + size, x_start : x_start + size]

        logger.debug(f"Cropped frame from {width}x{height} to {size}x{size}")
        return cropped

    def generate_luminance_histogram(
        self, frame: np.ndarray, bins: int = 256
    ) -> Dict[str, Any]:
        """
        Generate luminance histogram from frame.

        Args:
            frame: Input frame (RGB or grayscale)
            bins: Number of histogram bins

        Returns:
            Dictionary with histogram data and statistics
        """
        if frame is None:
            return {"error": "No frame provided"}

        # Convert to grayscale if needed
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        # Calculate histogram
        hist, bin_edges = np.histogram(gray, bins=bins, range=(0, 256))

        # Calculate statistics
        stats = {
            "mean": float(np.mean(gray)),
            "std": float(np.std(gray)),
            "min": int(np.min(gray)),
            "max": int(np.max(gray)),
            "median": float(np.median(gray)),
        }

        return {
            "histogram": hist.tolist(),
            "bin_edges": bin_edges.tolist(),
            "statistics": stats,
            "timestamp": int(time.time() * 1_000_000),  # microseconds
        }

    def record_correlation(
        self,
        camera_timestamp: float,
        stimulus_timestamp: Optional[float] = None,
        frame_id: Optional[int] = None,
    ):
        """
        Record timing correlation for analysis.

        Args:
            camera_timestamp: Camera capture timestamp (microseconds)
            stimulus_timestamp: Stimulus frame timestamp (microseconds)
            frame_id: Stimulus frame ID
        """
        from .acquisition_manager import get_acquisition_manager

        acquisition_manager = get_acquisition_manager()
        acquisition_manager.record_correlation(
            camera_timestamp_us=int(camera_timestamp),
            stimulus_timestamp_us=(
                int(stimulus_timestamp) if stimulus_timestamp is not None else None
            ),
            frame_id=frame_id,
        )

        logger.debug(
            "Recorded correlation via acquisition manager: cam=%s stim=%s frame=%s",
            camera_timestamp,
            stimulus_timestamp,
            frame_id,
        )

    def get_correlation_data(self) -> Dict[str, Any]:
        """
        Get correlation data for plotting.

        Returns:
            Dictionary with correlation statistics and plot data
        """
        from .acquisition_manager import get_acquisition_manager

        acquisition_manager = get_acquisition_manager()
        return acquisition_manager.get_correlation_data()

    def _acquisition_loop(self):
        """Continuous camera frame capture loop (runs in separate thread)"""
        logger.info("Camera acquisition loop started")

        # Get shared memory service
        from .service_locator import get_services

        services = get_services()
        shared_memory = services.shared_memory

        while not self.stop_acquisition_event.is_set():
            try:
                # Capture frame
                frame = self.capture_frame()

                if frame is not None:
                    # Crop to square
                    cropped = self.crop_to_square(frame)

                    # Convert BGR (OpenCV) to RGBA for frontend
                    if len(cropped.shape) == 3 and cropped.shape[2] == 3:
                        rgba = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGBA)
                    else:
                        # Grayscale - convert to RGBA
                        rgba = cv2.cvtColor(cropped, cv2.COLOR_GRAY2RGBA)

                    # Store original frame with thread safety
                    with self.acquisition_lock:
                        self.current_frame = frame  # Original frame for histogram
                        self.last_capture_timestamp = int(
                            time.time() * 1_000_000
                        )  # microseconds

                    # Record timestamp correlation with stimulus
                    if shared_memory:
                        stimulus_timestamp, stimulus_frame_id = (
                            shared_memory.get_stimulus_timestamp()
                        )
                        if stimulus_timestamp is not None:
                            self.record_correlation(
                                camera_timestamp=self.last_capture_timestamp,
                                stimulus_timestamp=stimulus_timestamp,
                                frame_id=stimulus_frame_id,
                            )

                    # Write RGBA frame to shared memory
                    if shared_memory:
                        shared_memory.write_frame(
                            rgba,
                            {
                                "frame_index": 0,
                                "direction": "CAMERA",  # Use special direction to identify camera frames
                                "angle_degrees": 0.0,
                                "total_frames": 0,
                                "start_angle": 0.0,
                                "end_angle": 0.0,
                            },
                        )

                # Small sleep to control frame rate (30 FPS)
                time.sleep(1.0 / 30.0)

            except Exception as e:
                logger.error(f"Error in acquisition loop: {e}")
                time.sleep(0.1)  # Prevent tight error loop

        logger.info("Camera acquisition loop stopped")

    def start_acquisition(self) -> bool:
        """
        Start continuous camera acquisition.

        Returns:
            True if started successfully
        """
        if self.active_camera is None:
            logger.warning("No active camera - cannot start acquisition")
            return False

        if self.is_streaming:
            logger.warning("Acquisition already running")
            return True

        # Reset stop event
        self.stop_acquisition_event.clear()

        # Start acquisition thread
        self.acquisition_thread = threading.Thread(
            target=self._acquisition_loop, daemon=True, name="CameraAcquisition"
        )
        self.acquisition_thread.start()
        self.is_streaming = True

        logger.info("Camera acquisition started")
        return True

    def stop_acquisition(self):
        """Stop continuous camera acquisition"""
        if not self.is_streaming:
            return

        # Signal thread to stop
        self.stop_acquisition_event.set()

        # Wait for thread to finish
        if self.acquisition_thread and self.acquisition_thread.is_alive():
            self.acquisition_thread.join(timeout=2.0)

        self.is_streaming = False
        logger.info("Camera acquisition stopped")

    def get_current_frame_rgba(self) -> Optional[np.ndarray]:
        """
        Get current camera frame (cropped, RGBA format).

        Returns:
            Current frame as RGBA numpy array, or None if no frame available
        """
        with self.acquisition_lock:
            if self.current_frame_cropped is not None:
                return self.current_frame_cropped.copy()
        return None

    def __del__(self):
        """Cleanup when object is destroyed."""
        self.stop_acquisition()
        self.close_camera()


def handle_detect_cameras(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle detect_cameras IPC command."""
    try:
        logger.info("Handling detect_cameras command")
        cameras = camera_manager.detect_cameras()

        # Return only available camera names as strings for frontend dropdown
        camera_list = [camera.name for camera in cameras if camera.is_available]

        return {"success": True, "type": "detect_cameras", "cameras": camera_list}
    except Exception as e:
        logger.error(f"Camera detection failed: {e}")
        return {
            "success": False,
            "type": "detect_cameras",
            "error": str(e),
            "cameras": [],
        }


def handle_get_camera_capabilities(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_camera_capabilities IPC command."""
    try:
        camera_name = command.get("camera_name")

        if not camera_name:
            return {
                "success": False,
                "type": "get_camera_capabilities",
                "error": "camera_name is required",
            }

        capabilities = camera_manager.get_camera_capabilities(camera_name)

        if capabilities is None:
            return {
                "success": False,
                "type": "get_camera_capabilities",
                "error": f"Camera not found: {camera_name}",
            }

        return {
            "success": True,
            "type": "get_camera_capabilities",
            "capabilities": capabilities,
        }

    except Exception as e:
        logger.error(f"Failed to get camera capabilities: {e}")
        return {"success": False, "type": "get_camera_capabilities", "error": str(e)}


def handle_camera_stream_started(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle camera_stream_started IPC command"""
    try:
        camera_name = command.get("camera_name", "unknown")
        logger.info(f"Camera stream started: {camera_name}")
        return {
            "success": True,
            "type": "camera_stream_started",
            "message": f"Camera stream started for {camera_name}",
        }
    except Exception as e:
        logger.error(f"Error in handle_camera_stream_started: {e}")
        return {"success": False, "type": "camera_stream_started", "error": str(e)}


def handle_camera_stream_stopped(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle camera_stream_stopped IPC command"""
    try:
        camera_name = command.get("camera_name", "unknown")
        logger.info(f"Camera stream stopped: {camera_name}")
        return {
            "success": True,
            "type": "camera_stream_stopped",
            "message": f"Camera stream stopped for {camera_name}",
        }
    except Exception as e:
        logger.error(f"Error in handle_camera_stream_stopped: {e}")
        return {"success": False, "type": "camera_stream_stopped", "error": str(e)}


def handle_camera_capture(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle camera_capture IPC command"""
    try:
        camera_name = command.get("camera_name", "unknown")
        timestamp = command.get("timestamp", "unknown")
        logger.info(f"Camera capture from {camera_name} at {timestamp}")
        return {
            "success": True,
            "type": "camera_capture",
            "message": f"Camera capture logged for {camera_name}",
        }
    except Exception as e:
        logger.error(f"Error in handle_camera_capture: {e}")
        return {"success": False, "type": "camera_capture", "error": str(e)}


def handle_get_camera_histogram(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_camera_histogram IPC command - generate luminance histogram from current camera frame"""
    try:
        if camera_manager.current_frame is None:
            return {
                "success": False,
                "type": "get_camera_histogram",
                "error": "No camera frame available",
            }

        histogram_data = camera_manager.generate_luminance_histogram(
            camera_manager.current_frame
        )

        return {"success": True, "type": "get_camera_histogram", "data": histogram_data}
    except Exception as e:
        logger.error(f"Error in handle_get_camera_histogram: {e}")
        return {"success": False, "type": "get_camera_histogram", "error": str(e)}


def handle_get_correlation_data(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_correlation_data IPC command - get timing correlation statistics"""
    try:
        correlation_data = camera_manager.get_correlation_data()

        return {
            "success": True,
            "type": "get_correlation_data",
            "data": correlation_data,
        }
    except Exception as e:
        logger.error(f"Error in handle_get_correlation_data: {e}")
        return {"success": False, "type": "get_correlation_data", "error": str(e)}


def handle_start_camera_acquisition(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle start_camera_acquisition IPC command - start continuous camera capture"""
    try:
        camera_name = command.get("camera_name")

        # Open camera if not already open
        if camera_manager.active_camera is None and camera_name:
            # Ensure cameras are detected
            if not camera_manager.detected_cameras:
                camera_manager.detect_cameras()

            # Find camera index from name
            camera_index = None
            for camera in camera_manager.detected_cameras:
                if camera.name == camera_name:
                    camera_index = camera.index
                    break

            if camera_index is None:
                return {
                    "success": False,
                    "type": "start_camera_acquisition",
                    "error": f"Camera not found: {camera_name}",
                }

            success = camera_manager.open_camera(camera_index)
            if not success:
                return {
                    "success": False,
                    "type": "start_camera_acquisition",
                    "error": f"Failed to open camera: {camera_name}",
                }

        # Start acquisition
        success = camera_manager.start_acquisition()

        return {
            "success": success,
            "type": "start_camera_acquisition",
            "message": (
                "Camera acquisition started"
                if success
                else "Failed to start acquisition"
            ),
        }
    except Exception as e:
        logger.error(f"Error in handle_start_camera_acquisition: {e}")
        return {"success": False, "type": "start_camera_acquisition", "error": str(e)}


def handle_stop_camera_acquisition(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle stop_camera_acquisition IPC command - stop continuous camera capture"""
    try:
        camera_manager.stop_acquisition()

        return {
            "success": True,
            "type": "stop_camera_acquisition",
            "message": "Camera acquisition stopped",
        }
    except Exception as e:
        logger.error(f"Error in handle_stop_camera_acquisition: {e}")
        return {"success": False, "type": "stop_camera_acquisition", "error": str(e)}


def handle_get_camera_frame(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_camera_frame IPC command - deprecated, frames now sent via shared memory"""
    # This handler is no longer needed - frames are sent via shared memory
    # Kept for backwards compatibility
    return {
        "success": True,
        "type": "get_camera_frame",
        "message": "Camera frames are now streamed via shared memory",
    }


# Global camera manager instance
camera_manager = CameraManager()
