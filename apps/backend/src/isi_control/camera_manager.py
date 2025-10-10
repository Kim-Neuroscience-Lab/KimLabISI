"""Camera detection and management using OpenCV."""

import cv2
import numpy as np
from typing import List, Dict, Optional, Any
import platform
import subprocess
import json
import time
import threading

from .logging_utils import get_logger
from .ipc_utils import ipc_handler
from .timestamp_synchronization_tracker import TimestampSynchronizationTracker

logger = get_logger(__name__)


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

    def __init__(
        self,
        synchronization_tracker: Optional[TimestampSynchronizationTracker] = None,
        camera_triggered_stimulus_controller=None,
        data_recorder=None,
    ):
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

        # Timestamp synchronization tracker (dependency injection)
        self.synchronization_tracker = synchronization_tracker

        # Camera-triggered stimulus controller (dependency injection)
        self.camera_triggered_stimulus = camera_triggered_stimulus_controller

        # Data recorder (dependency injection - protected by acquisition_lock)
        self._data_recorder = data_recorder

    def set_data_recorder(self, recorder) -> None:
        """Thread-safe setter for data recorder."""
        with self.acquisition_lock:
            self._data_recorder = recorder
            logger.info(f"Data recorder set: {recorder.session_path if recorder else 'None'}")

    def get_data_recorder(self):
        """Thread-safe getter for data recorder."""
        with self.acquisition_lock:
            return self._data_recorder

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

    def get_camera_hardware_timestamp_us(self) -> Optional[int]:
        """
        Get hardware timestamp from camera if available.

        Returns:
            Hardware timestamp in microseconds, or None if not available

        Note:
            This method REQUIRES hardware timestamps for scientific accuracy.
            Returns None if camera does not support hardware timestamps.
        """
        if self.active_camera is None:
            return None

        try:
            # Try to get hardware timestamp (CAP_PROP_POS_MSEC in milliseconds)
            # Note: This may not be supported by all cameras/backends
            timestamp_ms = self.active_camera.get(cv2.CAP_PROP_POS_MSEC)

            if timestamp_ms > 0:
                # Convert milliseconds to microseconds
                return int(timestamp_ms * 1000)

            # If CAP_PROP_POS_MSEC doesn't work, try timestamp property
            # (backend-specific, may require USB camera with timestamp support)
            try:
                timestamp_us = self.active_camera.get(cv2.CAP_PROP_TIMESTAMP)
                if timestamp_us > 0:
                    return int(timestamp_us)
            except:
                pass

            return None

        except Exception as e:
            logger.debug(f"Hardware timestamp not available: {e}")
            return None

    def validate_hardware_timestamps(self) -> Dict[str, Any]:
        """
        Check camera timestamp capabilities and report timestamp source.

        Returns:
            Dictionary with timestamp capability information

        This method provides transparency about timestamp accuracy.
        Scientific rigor is maintained through explicit reporting of
        timestamp source in data provenance.
        """
        if self.active_camera is None:
            return {
                "success": False,
                "error": "No active camera",
                "has_hardware_timestamps": False,
                "timestamp_source": "none",
            }

        # Capture a test frame to check timestamp availability
        test_frame = self.capture_frame()
        if test_frame is None:
            return {
                "success": False,
                "error": "Failed to capture test frame from camera",
                "has_hardware_timestamps": False,
                "timestamp_source": "none",
            }

        # Check if hardware timestamp is available
        test_timestamp = self.get_camera_hardware_timestamp_us()

        if test_timestamp is None:
            return {
                "success": True,
                "has_hardware_timestamps": False,
                "timestamp_source": "software",
                "timestamp_accuracy": "~1-2ms jitter",
                "warning": (
                    "Camera does not provide hardware timestamps. "
                    "Using software timestamps (Python time.time()). "
                    "For publication-quality data, use industrial camera with hardware timestamp support."
                ),
                "message": "Software timestamps will be used (timestamp source recorded in data)",
            }

        return {
            "success": True,
            "has_hardware_timestamps": True,
            "timestamp_source": "hardware",
            "timestamp_accuracy": "< 1ms (hardware-precise)",
            "test_timestamp_us": test_timestamp,
            "message": "Camera hardware timestamps available - optimal accuracy",
        }

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

    def record_synchronization(
        self,
        camera_timestamp: float,
        stimulus_timestamp: Optional[float] = None,
        frame_id: Optional[int] = None,
    ):
        """
        Record timestamp synchronization for analysis.

        Args:
            camera_timestamp: Camera capture timestamp (microseconds)
            stimulus_timestamp: Stimulus frame timestamp (microseconds)
            frame_id: Stimulus frame ID
        """
        if self.synchronization_tracker is None:
            logger.warning("Synchronization tracker not available, skipping synchronization recording")
            return

        self.synchronization_tracker.record_synchronization(
            camera_timestamp_us=int(camera_timestamp),
            stimulus_timestamp_us=(
                int(stimulus_timestamp) if stimulus_timestamp is not None else None
            ),
            frame_id=frame_id,
        )

    def get_synchronization_data(self) -> Dict[str, Any]:
        """
        Get timestamp synchronization data for plotting.

        Returns:
            Dictionary with synchronization statistics and plot data
        """
        if self.synchronization_tracker is None:
            logger.warning("Synchronization tracker not available, returning empty data")
            return {
                "synchronization": [],
                "statistics": {
                    "count": 0,
                    "matched_count": 0,
                    "mean_diff_ms": 0.0,
                    "std_diff_ms": 0.0,
                    "min_diff_ms": 0.0,
                    "max_diff_ms": 0.0,
                    "histogram": [],
                    "bin_edges": [],
                },
            }

        return self.synchronization_tracker.get_synchronization_data()

    def _acquisition_loop(self):
        """Continuous camera frame capture loop (runs in separate thread)"""
        logger.info("Camera acquisition loop started")

        # Get shared memory service
        from .service_locator import get_services

        services = get_services()
        shared_memory = services.shared_memory

        # Check timestamp capability and record for data provenance
        test_hardware_ts = self.get_camera_hardware_timestamp_us()
        uses_hardware_timestamps = test_hardware_ts is not None

        if uses_hardware_timestamps:
            logger.info(
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "✓ HARDWARE TIMESTAMPS AVAILABLE\n"
                "  Camera provides hardware timestamps (CAP_PROP_POS_MSEC)\n"
                "  Timestamp accuracy: < 1ms (hardware-precise)\n"
                "  Suitable for scientific publication\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
        else:
            logger.warning(
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "⚠️  SOFTWARE TIMESTAMPS ONLY\n"
                "  Camera does not provide hardware timestamps\n"
                "  Using Python time.time() at frame capture\n"
                "  Timestamp accuracy: ~1-2ms jitter (software timing)\n"
                "  \n"
                "  For scientific publication, use industrial camera with\n"
                "  hardware timestamp support (FLIR, Basler, etc.)\n"
                "  \n"
                "  TIMESTAMP SOURCE WILL BE RECORDED IN DATA FILES\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )

        # Store timestamp source for metadata
        self.timestamp_source = "hardware" if uses_hardware_timestamps else "software"
        self.uses_hardware_timestamps = uses_hardware_timestamps

        # Propagate timestamp source to data recorder metadata for scientific provenance
        data_recorder = self.get_data_recorder()
        if data_recorder and hasattr(data_recorder, 'metadata'):
            if 'timestamp_info' in data_recorder.metadata:
                data_recorder.metadata['timestamp_info']['camera_timestamp_source'] = self.timestamp_source
                logger.info(
                    f"Data recorder metadata updated with camera timestamp source: {self.timestamp_source}"
                )
            else:
                logger.warning(
                    "Data recorder metadata does not contain 'timestamp_info' field. "
                    "Timestamp source will not be recorded."
                )

        # Track frame index for camera-triggered stimulus
        camera_frame_index = 0

        while not self.stop_acquisition_event.is_set():
            try:
                # === STEP 1: CAPTURE CAMERA FRAME ===
                frame = self.capture_frame()

                if frame is not None:
                    # Get hardware timestamp if available, otherwise use software timestamp
                    hardware_timestamp = self.get_camera_hardware_timestamp_us()

                    if hardware_timestamp is not None:
                        # Hardware timestamp available - use it
                        capture_timestamp = hardware_timestamp
                    else:
                        # No hardware timestamp - use software timing
                        # Timestamp captured as close to frame.read() as possible
                        capture_timestamp = int(time.time() * 1_000_000)

                    # === STEP 2: TRIGGER STIMULUS GENERATION (CAMERA-TRIGGERED) ===
                    stimulus_frame = None
                    stimulus_metadata = None
                    stimulus_angle = None

                    if self.camera_triggered_stimulus:
                        stimulus_frame, stimulus_metadata = (
                            self.camera_triggered_stimulus.generate_next_frame()
                        )
                        if stimulus_metadata:
                            # Fail-hard if angle_degrees missing (indicates stimulus generator error)
                            stimulus_angle = stimulus_metadata["angle_degrees"]

                    # === STEP 3: PROCESS CAMERA FRAME ===
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
                        self.last_capture_timestamp = capture_timestamp

                    # === STEP 4: RECORD DATA (CAMERA + STIMULUS) ===
                    # Thread-safe access to data recorder
                    data_recorder = self.get_data_recorder()
                    if data_recorder and data_recorder.is_recording:
                        # Record camera frame
                        data_recorder.record_camera_frame(
                            timestamp_us=capture_timestamp,
                            frame_index=camera_frame_index,
                            frame_data=frame,  # Original uncropped frame
                        )

                        # Record stimulus event (if generated)
                        if stimulus_metadata:
                            # Fail-hard if required metadata fields missing
                            # (indicates stimulus generator error - better to crash than save corrupted data)
                            data_recorder.record_stimulus_event(
                                timestamp_us=capture_timestamp,  # Same timestamp as camera
                                frame_id=stimulus_metadata["frame_index"],
                                frame_index=stimulus_metadata["camera_frame_index"],
                                direction=stimulus_metadata["direction"],
                                angle_degrees=stimulus_angle,  # Already validated above (line 701)
                            )

                    # === STEP 5: WRITE TO SHARED MEMORY FOR FRONTEND DISPLAY ===
                    if shared_memory:
                        # Write camera frame
                        camera_name = "unknown"
                        for cam in self.detected_cameras:
                            if cam.index == getattr(self.active_camera, 'index', -1):
                                camera_name = cam.name
                                break

                        shared_memory.write_camera_frame(
                            rgba,
                            camera_name=camera_name,
                            capture_timestamp_us=capture_timestamp,
                        )

                        # Write stimulus frame (if generated)
                        if stimulus_frame is not None and stimulus_metadata:
                            frame_id = shared_memory.write_frame(stimulus_frame, stimulus_metadata)
                            # Set stimulus timestamp for timing QA
                            shared_memory.set_stimulus_timestamp(capture_timestamp, frame_id)

                    # === STEP 6: TIMING QA (Frame interval monitoring) ===
                    if self.synchronization_tracker and stimulus_metadata:
                        # Track frame timing for QA (not synchronization anymore)
                        self.record_synchronization(
                            camera_timestamp=capture_timestamp,
                            stimulus_timestamp=capture_timestamp,  # Same in camera-triggered mode
                            frame_id=camera_frame_index,
                        )

                    camera_frame_index += 1

                # Small sleep to control frame rate (30 FPS)
                time.sleep(1.0 / 30.0)

            except Exception as e:
                # Check if we're in record mode (scientifically rigorous mode)
                data_recorder = self.get_data_recorder()
                is_recording = data_recorder and data_recorder.is_recording

                if is_recording:
                    # RECORD MODE: Fail hard to preserve scientific validity
                    # Do NOT continue on errors - acquisition must stop immediately
                    logger.critical(
                        f"FATAL ERROR in acquisition loop during RECORD mode: {e}\n"
                        f"Acquisition MUST stop to prevent corrupted data.\n"
                        f"System will NOT continue with invalid/partial data.",
                        exc_info=True
                    )
                    # Re-raise to stop acquisition
                    raise RuntimeError(
                        f"Acquisition failed during record mode: {e}. "
                        f"System halted to preserve scientific validity."
                    ) from e
                else:
                    # PREVIEW MODE: Log error but continue (user can retry)
                    logger.error(f"Error in acquisition loop (preview mode): {e}", exc_info=True)
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

        # Update state coordinator
        from .service_locator import get_services
        services = get_services()
        if hasattr(services, 'acquisition_state') and services.acquisition_state:
            services.acquisition_state.set_camera_active(True)

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

        # Update state coordinator
        from .service_locator import get_services
        services = get_services()
        if hasattr(services, 'acquisition_state') and services.acquisition_state:
            services.acquisition_state.set_camera_active(False)

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


@ipc_handler("detect_cameras")
def handle_detect_cameras(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle detect_cameras IPC command."""
    logger.info("Handling detect_cameras command")
    cameras = camera_manager.detect_cameras()

    # Return only available camera names as strings for frontend dropdown
    camera_list = [camera.name for camera in cameras if camera.is_available]

    return {"cameras": camera_list}


@ipc_handler("get_camera_capabilities")
def handle_get_camera_capabilities(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_camera_capabilities IPC command."""
    camera_name = command.get("camera_name")

    if not camera_name:
        return {
            "success": False,
            "error": "camera_name is required",
        }

    capabilities = camera_manager.get_camera_capabilities(camera_name)

    if capabilities is None:
        return {
            "success": False,
            "error": f"Camera not found: {camera_name}",
        }

    return {"capabilities": capabilities}


@ipc_handler("camera_stream_started")
def handle_camera_stream_started(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle camera_stream_started IPC command"""
    camera_name = command.get("camera_name", "unknown")
    logger.info(f"Camera stream started: {camera_name}")
    return {"message": f"Camera stream started for {camera_name}"}


@ipc_handler("camera_stream_stopped")
def handle_camera_stream_stopped(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle camera_stream_stopped IPC command"""
    camera_name = command.get("camera_name", "unknown")
    logger.info(f"Camera stream stopped: {camera_name}")
    return {"message": f"Camera stream stopped for {camera_name}"}


@ipc_handler("camera_capture")
def handle_camera_capture(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle camera_capture IPC command"""
    camera_name = command.get("camera_name", "unknown")
    timestamp = command.get("timestamp", "unknown")
    logger.info(f"Camera capture from {camera_name} at {timestamp}")
    return {"message": f"Camera capture logged for {camera_name}"}


@ipc_handler("get_camera_histogram")
def handle_get_camera_histogram(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_camera_histogram IPC command - generate luminance histogram formatted for Chart.js"""
    from .acquisition_data_formatter import format_histogram_chart_data

    if camera_manager.current_frame is None:
        return {
            "success": False,
            "error": "No camera frame available",
        }

    # Generate raw histogram data
    histogram_data = camera_manager.generate_luminance_histogram(
        camera_manager.current_frame
    )

    # Format for Chart.js
    formatted_data = format_histogram_chart_data(
        histogram=np.array(histogram_data['histogram']),
        bin_edges=np.array(histogram_data['bin_edges']),
        statistics=histogram_data['statistics']
    )

    return {
        "success": True,
        "data": formatted_data
    }


@ipc_handler("get_correlation_data")  # Keep IPC command name for backward compatibility
def handle_get_synchronization_data(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_correlation_data IPC command - get timestamp correlation data formatted for Chart.js"""
    from .acquisition_data_formatter import format_correlation_chart_data

    # Get raw synchronization data
    synchronization_data = camera_manager.get_synchronization_data()

    # Format for Chart.js
    formatted_data = format_correlation_chart_data(
        synchronization=synchronization_data.get('synchronization', []),
        statistics=synchronization_data.get('statistics')
    )

    return {
        "success": True,
        "data": formatted_data
    }


@ipc_handler("start_camera_acquisition")
def handle_start_camera_acquisition(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle start_camera_acquisition IPC command - start continuous camera capture"""
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
                "error": f"Camera not found: {camera_name}",
            }

        success = camera_manager.open_camera(camera_index)
        if not success:
            return {
                "success": False,
                "error": f"Failed to open camera: {camera_name}",
            }

    # Start acquisition
    success = camera_manager.start_acquisition()

    return {
        "success": success,
        "message": (
            "Camera acquisition started"
            if success
            else "Failed to start acquisition"
        ),
    }


@ipc_handler("stop_camera_acquisition")
def handle_stop_camera_acquisition(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle stop_camera_acquisition IPC command - stop continuous camera capture"""
    camera_manager.stop_acquisition()
    return {"message": "Camera acquisition stopped"}


@ipc_handler("validate_camera_timestamps")
def handle_validate_camera_timestamps(command: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that camera provides hardware timestamps.

    CRITICAL: This should be called before starting acquisition to ensure
    hardware timestamps are available. For scientific rigor, we REQUIRE
    hardware timestamps - no software fallbacks allowed.

    Returns:
        Dictionary with validation results
    """
    return camera_manager.validate_hardware_timestamps()


# Global camera manager instance
camera_manager = CameraManager()
