"""Camera detection and management using OpenCV.

Simplified from original implementation using constructor injection.
All dependencies passed explicitly - no service locator, no global singletons.
"""

import cv2
import numpy as np
import time
import threading
import logging
from typing import List, Dict, Optional, Any

from .utils import get_available_camera_indices, get_system_camera_names

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
    """Manages camera detection and access using OpenCV.

    Simplified implementation using constructor injection.
    All dependencies passed explicitly in __init__.
    """

    def __init__(
        self,
        config,
        ipc,
        shared_memory,
        synchronization_tracker=None,
    ):
        """Initialize camera manager with explicit dependencies.

        Args:
            config: Camera configuration (CameraConfig from config.py)
            ipc: IPC service (MultiChannelIPC from ipc/channels.py)
            shared_memory: Shared memory service (SharedMemoryService from ipc/shared_memory.py)
            synchronization_tracker: Optional timestamp synchronization tracker
        """
        # Injected dependencies (NO service_locator!)
        self.config = config
        self.ipc = ipc
        self.shared_memory = shared_memory
        self.synchronization_tracker = synchronization_tracker

        # Data recorder will be set later (Phase 4)
        self._data_recorder = None

        # Camera state
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

        # Timestamp tracking
        self.timestamp_source = "unknown"
        self.uses_hardware_timestamps = False

    def set_data_recorder(self, recorder) -> None:
        """Thread-safe setter for data recorder (will be used in Phase 4).

        Args:
            recorder: Data recorder instance
        """
        with self.acquisition_lock:
            self._data_recorder = recorder
            logger.info(
                f"Data recorder set: {recorder.session_path if recorder else 'None'}"
            )

    def get_data_recorder(self):
        """Thread-safe getter for data recorder."""
        with self.acquisition_lock:
            return self._data_recorder

    def detect_cameras(
        self, max_cameras: int = 10, force: bool = False
    ) -> List[CameraInfo]:
        """Detect available cameras using OpenCV with smart enumeration.

        Args:
            max_cameras: Maximum number of camera indices to check
            force: Force re-detection even if already detected

        Returns:
            List of detected cameras
        """
        if self._has_detected and not force:
            return self.detected_cameras

        logger.info("Starting camera detection...")
        self.detected_cameras.clear()

        # Get REAL camera names from system (not fake generated names)
        system_camera_names = get_system_camera_names()

        # Create lookup dict: index -> real_name
        name_lookup = {idx: name for idx, name in system_camera_names}

        # Get available camera indices using platform-specific methods
        available_indices = get_available_camera_indices()

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

                        # Get REAL camera name from system (not fake generated name)
                        name = name_lookup.get(i, f"Camera {i}")

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

    def get_camera_list(self) -> List[Dict[str, Any]]:
        """Get list of detected cameras as dictionaries.

        Returns:
            List of camera info dictionaries
        """
        if not self.detected_cameras:
            self.detect_cameras()

        return [camera.to_dict() for camera in self.detected_cameras]

    def get_available_cameras(self) -> List[Dict[str, Any]]:
        """Get list of only available cameras.

        Returns:
            List of available camera info dictionaries
        """
        return [
            camera.to_dict() for camera in self.detected_cameras if camera.is_available
        ]

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

    def capture_frame(self) -> Optional[np.ndarray]:
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
        """Get hardware timestamp from camera if available.

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
        """Check camera timestamp capabilities and report timestamp source.

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

    def crop_to_square(self, frame: np.ndarray) -> np.ndarray:
        """Crop frame to square centered on smaller dimension.

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
        """Generate luminance histogram from frame.

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
        """Record timestamp synchronization for analysis.

        Args:
            camera_timestamp: Camera capture timestamp (microseconds)
            stimulus_timestamp: Stimulus frame timestamp (microseconds)
            frame_id: Stimulus frame ID
        """
        if self.synchronization_tracker is None:
            logger.warning(
                "Synchronization tracker not available, skipping synchronization recording"
            )
            return

        self.synchronization_tracker.record_synchronization(
            camera_timestamp_us=int(camera_timestamp),
            stimulus_timestamp_us=(
                int(stimulus_timestamp) if stimulus_timestamp is not None else None
            ),
            frame_id=frame_id,
        )

    def get_synchronization_data(self) -> Dict[str, Any]:
        """Get timestamp synchronization data for plotting.

        Returns:
            Dictionary with synchronization statistics and plot data
        """
        if self.synchronization_tracker is None:
            logger.warning(
                "Synchronization tracker not available, returning empty data"
            )
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
        """Continuous camera frame capture loop (runs in separate thread)."""
        logger.info("Camera acquisition loop started")

        # Check timestamp capability and record for data provenance
        test_hardware_ts = self.get_camera_hardware_timestamp_us()
        uses_hardware_timestamps = test_hardware_ts is not None

        # Check development mode
        system_params = (
            self.config.get_parameter_group("system")
            if hasattr(self.config, "get_parameter_group")
            else {}
        )
        development_mode = system_params.get("development_mode", False)

        if uses_hardware_timestamps:
            logger.info(
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "✓ HARDWARE TIMESTAMPS AVAILABLE\n"
                "  Camera provides hardware timestamps\n"
                "  Timestamp accuracy: < 1ms (hardware-precise)\n"
                "  Suitable for scientific publication\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
        else:
            if development_mode:
                logger.warning(
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "⚠️  DEVELOPMENT MODE - SOFTWARE TIMESTAMPS\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "\n"
                    "  Camera: No hardware timestamps available\n"
                    "  Mode: DEVELOPMENT ONLY (system.development_mode = true)\n"
                    "  Timestamps: Python time.time() (~1-2ms jitter)\n"
                    "\n"
                    "  ⚠️  WARNING: NOT SUITABLE FOR PUBLICATION DATA\n"
                    "  ⚠️  Use for development, testing, and UI work only\n"
                    "  ⚠️  Production requires industrial camera (FLIR, Basler, PCO)\n"
                    "\n"
                    "  Timestamp source: 'software' (recorded in all data files)\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                )
            else:
                # This should not happen - the frame capture will raise RuntimeError
                logger.error(
                    "Camera does not support hardware timestamps and development_mode is disabled. "
                    "Acquisition will fail. Enable development_mode for testing with consumer cameras."
                )

        # Store timestamp source for metadata
        self.timestamp_source = (
            "hardware"
            if uses_hardware_timestamps
            else "software_dev_mode" if development_mode else "software"
        )
        self.uses_hardware_timestamps = uses_hardware_timestamps

        # Propagate timestamp source to data recorder metadata for scientific provenance
        data_recorder = self.get_data_recorder()
        if data_recorder and hasattr(data_recorder, "metadata"):
            if "timestamp_info" in data_recorder.metadata:
                data_recorder.metadata["timestamp_info"][
                    "camera_timestamp_source"
                ] = self.timestamp_source
                logger.info(
                    f"Data recorder metadata updated with camera timestamp source: {self.timestamp_source}"
                )
            else:
                logger.warning(
                    "Data recorder metadata does not contain 'timestamp_info' field. "
                    "Timestamp source will not be recorded."
                )

        # Track frame index for synchronization tracking
        camera_frame_index = 0

        while not self.stop_acquisition_event.is_set():
            try:
                # === STEP 1: CAPTURE CAMERA FRAME ===
                frame = self.capture_frame()

                if frame is not None:
                    # Get hardware timestamp if available, otherwise check development mode
                    hardware_timestamp = self.get_camera_hardware_timestamp_us()

                    if hardware_timestamp is not None:
                        # Hardware timestamp available - use it
                        capture_timestamp = hardware_timestamp
                    else:
                        # No hardware timestamp - check if development mode allows software timestamps
                        system_params = (
                            self.config.get_parameter_group("system")
                            if hasattr(self.config, "get_parameter_group")
                            else {}
                        )
                        development_mode = system_params.get("development_mode", False)

                        if not development_mode:
                            raise RuntimeError(
                                "Camera does not support hardware timestamps. "
                                "Hardware timestamps are REQUIRED for scientific validity.\n\n"
                                "To use this camera for DEVELOPMENT/TESTING ONLY:\n"
                                "1. Set system.development_mode = true in parameters\n"
                                "2. NEVER use development mode for publication data\n"
                                "3. Use industrial camera (FLIR, Basler, PCO) for production\n\n"
                                "Development mode enables software timestamps with explicit warnings."
                            )

                        # Development mode enabled - use software timestamp with warning
                        capture_timestamp = int(time.time() * 1_000_000)

                    # === STEP 2: PROCESS CAMERA FRAME ===
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

                    # === STEP 3: RECORD DATA (CAMERA ONLY) ===
                    # Thread-safe access to data recorder
                    data_recorder = self.get_data_recorder()
                    if data_recorder and data_recorder.is_recording:
                        # Convert to grayscale for recording (single channel)
                        # Intrinsic signal imaging requires grayscale data
                        if len(frame.shape) == 3:
                            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        else:
                            frame_gray = frame

                        # Record camera frame
                        data_recorder.record_camera_frame(
                            timestamp_us=capture_timestamp,
                            frame_index=camera_frame_index,
                            frame_data=frame_gray,  # Single-channel grayscale
                        )

                    # === STEP 4: WRITE TO SHARED MEMORY FOR FRONTEND DISPLAY ===
                    if self.shared_memory:
                        # Write camera frame
                        camera_name = "unknown"
                        for cam in self.detected_cameras:
                            if cam.index == getattr(self.active_camera, "index", -1):
                                camera_name = cam.name
                                break

                        self.shared_memory.write_camera_frame(
                            rgba,
                            camera_name=camera_name,
                            capture_timestamp_us=capture_timestamp,
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
                        exc_info=True,
                    )
                    # Re-raise to stop acquisition
                    raise RuntimeError(
                        f"Acquisition failed during record mode: {e}. "
                        f"System halted to preserve scientific validity."
                    ) from e
                else:
                    # PREVIEW MODE: Log error but continue (user can retry)
                    logger.error(
                        f"Error in acquisition loop (preview mode): {e}", exc_info=True
                    )
                    time.sleep(0.1)  # Prevent tight error loop

        logger.info("Camera acquisition loop stopped")

    def start_acquisition(self) -> bool:
        """Start continuous camera acquisition.

        Returns:
            True if started successfully
        """
        if self.active_camera is None:
            logger.warning("No active camera - cannot start acquisition")
            return False

        if self.is_streaming:
            logger.debug("Camera acquisition already running (no action needed)")
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
        """Stop continuous camera acquisition."""
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
        """Get current camera frame (cropped, RGBA format).

        Returns:
            Current frame as RGBA numpy array, or None if no frame available
        """
        with self.acquisition_lock:
            if self.current_frame_cropped is not None:
                return self.current_frame_cropped.copy()
        return None

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Get the latest captured frame.

        Returns:
            Latest frame or None if not available
        """
        with self.acquisition_lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
        return None

    def get_latest_frame_info(self) -> Dict[str, Any]:
        """Get information about the latest frame.

        Returns:
            Dictionary with frame information
        """
        with self.acquisition_lock:
            if self.current_frame is None:
                return {
                    "success": False,
                    "error": "No frame available",
                }

            return {
                "success": True,
                "timestamp_us": self.last_capture_timestamp,
                "shape": self.current_frame.shape,
                "is_streaming": self.is_streaming,
            }

    def shutdown(self):
        """Clean shutdown of camera manager."""
        logger.info("Shutting down camera manager...")
        self.stop_acquisition()
        self.close_camera()
        logger.info("Camera manager shutdown complete")

    def __del__(self):
        """Cleanup when object is destroyed."""
        self.shutdown()
