"""
Shared Memory Frame Streaming System
Provides ultra-high performance binary frame data transfer between backend and frontend
"""

from __future__ import annotations

import numpy as np
import time
import zmq
import mmap
import os
from typing import Dict, Any, Optional

from .service_locator import get_services
from dataclasses import dataclass
import threading

from .config import SharedMemoryConfig
from .logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class FrameMetadata:
    """Frame metadata for stimulus frames in shared memory streaming"""

    frame_id: int
    timestamp_us: int  # Hardware timestamp in microseconds
    frame_index: int
    direction: str
    angle_degrees: float
    width_px: int
    height_px: int
    data_size_bytes: int
    offset_bytes: int  # Offset in shared memory
    total_frames: int = 0  # Total frames in dataset for this direction
    start_angle: float = 0.0  # Dataset start angle
    end_angle: float = 0.0  # Dataset end angle

    def to_dict(self, shm_path: str) -> Dict[str, Any]:
        """Convert to dictionary for ZeroMQ transmission."""
        from dataclasses import asdict

        result = asdict(self)
        result["shm_path"] = shm_path
        return result


@dataclass
class CameraFrameMetadata:
    """Frame metadata for camera frames in shared memory streaming"""

    frame_id: int
    timestamp_us: int  # Capture timestamp in microseconds
    capture_timestamp_us: int  # Hardware capture timestamp if available
    width_px: int
    height_px: int
    data_size_bytes: int
    offset_bytes: int  # Offset in shared memory
    camera_name: str = "unknown"
    exposure_us: Optional[int] = None  # Exposure time in microseconds
    gain: Optional[float] = None  # Camera gain if available

    def to_dict(self, shm_path: str) -> Dict[str, Any]:
        """Convert to dictionary for ZeroMQ transmission."""
        from dataclasses import asdict

        result = asdict(self)
        result["shm_path"] = shm_path
        return result


class SharedMemoryFrameStream:
    """High-performance shared memory streaming for stimulus and camera frames"""

    def __init__(self, config: SharedMemoryConfig):
        self.config = config
        self.stream_name = config.stream_name
        self.buffer_size_bytes = config.buffer_size_mb * 1024 * 1024

        # Stimulus frame tracking
        self.frame_counter = 0
        self.write_offset = 0
        self.ring_buffer_frames = 100
        self.frame_registry = {}
        self.preview_frame_registry = {}

        # Camera frame tracking (separate from stimulus)
        self.camera_frame_counter = 0
        self.camera_write_offset = 0
        self.camera_ring_buffer_frames = 100
        self.camera_frame_registry = {}

        self.zmq_context = zmq.Context()
        self.metadata_socket = None  # Stimulus metadata
        self.camera_metadata_socket = None  # Camera metadata

        # Separate shared memory buffers for stimulus and camera
        self.stimulus_shm_fd = None
        self.stimulus_shm_mmap = None
        self.camera_shm_fd = None
        self.camera_shm_mmap = None

        self._lock = threading.RLock()
        self._running = False

    def initialize(self) -> None:
        try:
            with self._lock:
                # Initialize STIMULUS shared memory buffer
                stimulus_path = f"/tmp/{self.stream_name}_stimulus_shm"
                self.stimulus_shm_fd = os.open(
                    stimulus_path, os.O_CREAT | os.O_RDWR | os.O_TRUNC, 0o666
                )
                os.ftruncate(self.stimulus_shm_fd, self.buffer_size_bytes)

                self.stimulus_shm_mmap = mmap.mmap(
                    self.stimulus_shm_fd,
                    self.buffer_size_bytes,
                    access=mmap.ACCESS_WRITE,
                )

                # Initialize CAMERA shared memory buffer
                camera_path = f"/tmp/{self.stream_name}_camera_shm"
                self.camera_shm_fd = os.open(
                    camera_path, os.O_CREAT | os.O_RDWR | os.O_TRUNC, 0o666
                )
                os.ftruncate(self.camera_shm_fd, self.buffer_size_bytes)

                self.camera_shm_mmap = mmap.mmap(
                    self.camera_shm_fd,
                    self.buffer_size_bytes,
                    access=mmap.ACCESS_WRITE,
                )

                # Stimulus metadata socket
                self.metadata_socket = self.zmq_context.socket(zmq.PUB)
                self.metadata_socket.bind(f"tcp://*:{self.config.metadata_port}")

                # Camera metadata socket (separate channel)
                self.camera_metadata_socket = self.zmq_context.socket(zmq.PUB)
                self.camera_metadata_socket.bind(
                    f"tcp://*:{self.config.camera_metadata_port}"
                )

                time.sleep(0.1)

                self._running = True
                logger.info(
                    "SharedMemoryFrameStream initialised: stimulus=%s, camera=%s (stimulus port %d, camera port %d)",
                    stimulus_path,
                    camera_path,
                    self.config.metadata_port,
                    self.config.camera_metadata_port,
                )
        except Exception as exc:
            logger.error("Failed to initialise SharedMemoryFrameStream: %s", exc)
            self.cleanup()
            raise

    def write_frame(self, frame_data: np.ndarray, metadata: Dict[str, Any]) -> int:
        """Write frame to shared memory with zero-copy operation"""

        try:
            with self._lock:
                if not self._running:
                    raise RuntimeError("SharedMemoryFrameStream not initialized")

                if frame_data.dtype != np.uint8:
                    frame_data = frame_data.astype(np.uint8)

                frame_bytes = frame_data.tobytes()
                data_size = len(frame_bytes)

                if self.write_offset + data_size > self.buffer_size_bytes:
                    self.write_offset = 0  # Wrap to beginning

                self.stimulus_shm_mmap[
                    self.write_offset : self.write_offset + data_size
                ] = frame_bytes

                self.frame_counter += 1
                timestamp_us = int(time.time() * 1_000_000)

                # Validate critical metadata fields - no defaults for scientific validity
                frame_index = metadata.get("frame_index")
                if frame_index is None or not isinstance(frame_index, int):
                    raise ValueError(
                        f"frame_index is required in metadata for shared memory write. "
                        f"Received metadata: {metadata}"
                    )

                total_frames = metadata.get("total_frames")
                if total_frames is None or not isinstance(total_frames, int) or total_frames <= 0:
                    raise ValueError(
                        f"total_frames is required in metadata and must be > 0. "
                        f"Received metadata: {metadata}"
                    )

                # Other fields can have sensible defaults (NOT critical for scientific validity)
                # These are display/organizational fields - the ground truth is frame_index
                #
                # Scientific validity depends on:
                #   - frame_index (REQUIRED above) - determines actual stimulus position
                #   - total_frames (REQUIRED above) - determines sweep range
                #
                # Non-critical display metadata (defaults acceptable):
                #   - direction: Label for organization/display
                #   - angle_degrees: Computed from frame_index (derived field)
                #   - start_angle/end_angle: Display range indicators
                direction = metadata.get("direction", "LR")
                angle_degrees = metadata.get("angle_degrees", 0.0)
                start_angle = metadata.get("start_angle", 0.0)
                end_angle = metadata.get("end_angle", 0.0)

                frame_metadata = FrameMetadata(
                    frame_id=self.frame_counter,
                    timestamp_us=timestamp_us,
                    frame_index=frame_index,
                    direction=direction,
                    angle_degrees=angle_degrees,
                    width_px=frame_data.shape[1],
                    height_px=frame_data.shape[0],
                    data_size_bytes=data_size,
                    offset_bytes=self.write_offset,
                    total_frames=total_frames,
                    start_angle=start_angle,
                    end_angle=end_angle,
                )

                self.frame_registry[self.frame_counter] = frame_metadata

                if len(self.frame_registry) > self.ring_buffer_frames:
                    oldest_frame_id = min(self.frame_registry.keys())
                    del self.frame_registry[oldest_frame_id]

                metadata_msg = frame_metadata.to_dict(
                    f"/tmp/{self.stream_name}_stimulus_shm"
                )

                try:
                    self.metadata_socket.send_json(metadata_msg, zmq.NOBLOCK)
                except zmq.Again:
                    logger.warning("Metadata send queue full, dropping frame metadata")

                self.write_offset += data_size

                return frame_metadata.frame_id
        except Exception as e:
            logger.error(f"Error writing frame to shared memory: {e}")
            raise

    def write_preview_frame(
        self, frame_data: np.ndarray, metadata: Dict[str, Any]
    ) -> int:
        frame_id = self.write_frame(frame_data, metadata)
        with self._lock:
            self.preview_frame_registry[frame_id] = metadata
        return frame_id

    def write_camera_frame(
        self,
        frame_data: np.ndarray,
        camera_name: str = "unknown",
        capture_timestamp_us: Optional[int] = None,
        exposure_us: Optional[int] = None,
        gain: Optional[float] = None,
    ) -> int:
        """Write camera frame to shared memory on separate channel"""

        try:
            with self._lock:
                if not self._running:
                    raise RuntimeError("SharedMemoryFrameStream not initialized")

                if frame_data.dtype != np.uint8:
                    frame_data = frame_data.astype(np.uint8)

                frame_bytes = frame_data.tobytes()
                data_size = len(frame_bytes)

                # Use separate offset for camera frames to avoid collisions
                if self.camera_write_offset + data_size > self.buffer_size_bytes:
                    self.camera_write_offset = 0  # Wrap to beginning

                self.camera_shm_mmap[
                    self.camera_write_offset : self.camera_write_offset + data_size
                ] = frame_bytes

                self.camera_frame_counter += 1
                timestamp_us = int(time.time() * 1_000_000)

                # Use capture timestamp if provided, otherwise use current time
                if capture_timestamp_us is None:
                    capture_timestamp_us = timestamp_us

                camera_metadata = CameraFrameMetadata(
                    frame_id=self.camera_frame_counter,
                    timestamp_us=timestamp_us,
                    capture_timestamp_us=capture_timestamp_us,
                    width_px=frame_data.shape[1],
                    height_px=frame_data.shape[0],
                    data_size_bytes=data_size,
                    offset_bytes=self.camera_write_offset,
                    camera_name=camera_name,
                    exposure_us=exposure_us,
                    gain=gain,
                )

                self.camera_frame_registry[self.camera_frame_counter] = camera_metadata

                if len(self.camera_frame_registry) > self.camera_ring_buffer_frames:
                    oldest_frame_id = min(self.camera_frame_registry.keys())
                    del self.camera_frame_registry[oldest_frame_id]

                metadata_msg = camera_metadata.to_dict(
                    f"/tmp/{self.stream_name}_camera_shm"
                )

                try:
                    self.camera_metadata_socket.send_json(metadata_msg, zmq.NOBLOCK)
                except zmq.Again:
                    logger.warning(
                        "Camera metadata send queue full, dropping frame metadata"
                    )

                self.camera_write_offset += data_size

                return camera_metadata.frame_id
        except Exception as e:
            logger.error(f"Error writing camera frame to shared memory: {e}")
            raise

    def clear_stimulus_frames(self) -> None:
        """Clear stimulus shared memory buffer and metadata."""
        with self._lock:
            self.frame_counter = 0
            self.write_offset = 0
            self.frame_registry.clear()
            if self.stimulus_shm_mmap:
                self.stimulus_shm_mmap.seek(0)
        if self.stimulus_shm_mmap:
            self.stimulus_shm_mmap.write(b"\x00" * self.buffer_size_bytes)
            self.stimulus_shm_mmap.flush()
        logger.debug("Stimulus shared memory frames cleared")

    def publish_black_frame(self, width: int, height: int) -> int:
        """Publish a solid black RGBA frame to shared memory."""

        if width <= 0 or height <= 0:
            raise ValueError(
                "Width and height must be positive to publish baseline frame"
            )

        frame = np.zeros((height, width, 4), dtype=np.uint8)
        frame[:, :, 3] = 255

        metadata = {
            "frame_index": 0,
            "direction": "baseline",
            "angle_degrees": 0.0,
            "total_frames": 1,
            "start_angle": 0.0,
            "end_angle": 0.0,
        }

        return self.write_frame(frame, metadata)

    def get_frame_info(self, frame_id: int) -> Optional[FrameMetadata]:
        """Get stimulus frame metadata by ID"""
        with self._lock:
            return self.frame_registry.get(frame_id)

    def get_camera_frame_info(self, frame_id: int) -> Optional[CameraFrameMetadata]:
        """Get camera frame metadata by ID"""
        with self._lock:
            return self.camera_frame_registry.get(frame_id)

    def cleanup(self):
        """Clean up shared memory and ZeroMQ resources"""
        try:
            with self._lock:
                self._running = False

                # Close stimulus metadata socket
                if self.metadata_socket:
                    self.metadata_socket.close()
                    self.metadata_socket = None

                # Close camera metadata socket
                if self.camera_metadata_socket:
                    self.camera_metadata_socket.close()
                    self.camera_metadata_socket = None

                # Close stimulus shared memory
                if self.stimulus_shm_mmap:
                    self.stimulus_shm_mmap.close()
                    self.stimulus_shm_mmap = None

                if self.stimulus_shm_fd:
                    os.close(self.stimulus_shm_fd)
                    self.stimulus_shm_fd = None

                # Close camera shared memory
                if self.camera_shm_mmap:
                    self.camera_shm_mmap.close()
                    self.camera_shm_mmap = None

                if self.camera_shm_fd:
                    os.close(self.camera_shm_fd)
                    self.camera_shm_fd = None

                # Remove stimulus shared memory file
                stimulus_path = f"/tmp/{self.stream_name}_stimulus_shm"
                if os.path.exists(stimulus_path):
                    os.unlink(stimulus_path)

                # Remove camera shared memory file
                camera_path = f"/tmp/{self.stream_name}_camera_shm"
                if os.path.exists(camera_path):
                    os.unlink(camera_path)

                self.zmq_context.term()

                logger.info(
                    "SharedMemoryFrameStream cleaned up (stimulus and camera buffers)"
                )

        except Exception as e:
            logger.error(f"Error during SharedMemoryFrameStream cleanup: {e}")


class RealtimeFrameProducer(threading.Thread):
    """Real-time frame producer with hardware-level timing"""

    def __init__(
        self,
        stream: SharedMemoryFrameStream,
        stimulus_generator,
        target_fps: float = 60.0,
    ):
        super().__init__(daemon=True)
        self.stream = stream
        self.stimulus_generator = stimulus_generator
        self.target_fps = target_fps
        self.frame_interval_us = int(1_000_000 / target_fps)  # Microseconds

        self._stop_event = threading.Event()
        self._completion_event = threading.Event()
        self._state_lock = threading.RLock()  # Thread-safe access to stimulus state
        self._current_direction = "LR"
        self._dataset_info: Dict[str, Any] = {}
        self._frame_index = 0
        self._is_completed = False

        # Real-time priority (requires appropriate permissions)
        self.priority = -10  # High priority

    def set_stimulus_params(self, direction: str) -> None:
        with self._state_lock:
            self._current_direction = direction
            self._frame_index = 0
            self._is_completed = False
            self._completion_event.clear()
            try:
                self._dataset_info = self.stimulus_generator.get_dataset_info(direction)
            except Exception:
                logger.warning(
                    "Unable to fetch dataset info for direction %s; falling back to defaults",
                    direction,
                )
                self._dataset_info = {}

    def run(self):
        """High-precision frame generation loop"""
        try:
            try:
                os.nice(self.priority)
            except PermissionError:
                logger.warning("Could not set real-time priority (requires root)")

            start_time_us = int(time.time() * 1_000_000)
            next_frame_time_us = start_time_us

            logger.info(f"Real-time frame producer started: {self.target_fps} FPS")

            while not self._stop_event.is_set():
                current_time_us = int(time.time() * 1_000_000)

                if current_time_us >= next_frame_time_us:
                    # Take snapshot of state with lock
                    with self._state_lock:
                        current_direction = self._current_direction
                        current_frame_index = self._frame_index
                        dataset_info = self._dataset_info.copy()
                        total_frames = dataset_info.get("total_frames")

                        # Check if we've completed all frames for this stimulus
                        if total_frames and current_frame_index >= total_frames:
                            logger.info(
                                f"Stimulus presentation complete: {total_frames} frames presented for direction {current_direction}"
                            )
                            self._is_completed = True
                            self._completion_event.set()
                            break  # Exit loop after completing one full cycle

                    # Generate frame using snapshot (outside lock to avoid blocking)
                    frame, metadata = self.stimulus_generator.generate_frame_at_index(
                        direction=current_direction,
                        frame_index=current_frame_index,
                        show_bar_mask=True,
                        total_frames=total_frames,
                    )

                    # Ensure metadata has required fields for shared memory write
                    # Prefer dataset_info values, then metadata values, then fail
                    if "total_frames" in dataset_info:
                        final_total_frames = dataset_info["total_frames"]
                    elif "total_frames" in metadata:
                        final_total_frames = metadata["total_frames"]
                    else:
                        # This should not happen in normal operation
                        logger.error(
                            f"total_frames missing from both dataset_info and metadata. "
                            f"This indicates a stimulus generator error."
                        )
                        raise ValueError(
                            "total_frames is required but missing from stimulus metadata"
                        )

                    metadata.update(
                        {
                            "direction": current_direction,
                            "total_frames": final_total_frames,
                            "start_angle": dataset_info.get(
                                "start_angle", metadata.get("start_angle", 0.0)
                            ),
                            "end_angle": dataset_info.get(
                                "end_angle",
                                metadata.get(
                                    "end_angle", metadata.get("angle_degrees", 0.0)
                                ),
                            ),
                        }
                    )

                    frame_id = self.stream.write_frame(frame, metadata)

                    try:
                        from .service_locator import get_services

                        timestamp_us = int(time.time() * 1_000_000)
                        services = get_services()

                        # Send IPC message
                        services.ipc.send_control_message(
                            {
                                "type": "stimulus_frame_presented",
                                "frame_id": frame_id,
                                "timestamp_us": timestamp_us,
                                "direction": self._current_direction,
                                "frame_index": self._frame_index,
                                "angle_degrees": metadata.get("angle_degrees", 0.0),
                            }
                        )

                        # Store timestamp for camera correlation
                        if services.shared_memory:
                            services.shared_memory.set_stimulus_timestamp(
                                timestamp_us, frame_id
                            )

                    except Exception as e:
                        logger.warning(f"Failed to send stimulus frame event: {e}")

                    # Increment frame index with lock
                    with self._state_lock:
                        self._frame_index += 1
                    next_frame_time_us += self.frame_interval_us
                else:
                    sleep_us = next_frame_time_us - current_time_us
                    if sleep_us > 1000:
                        time.sleep(sleep_us / 1_000_000)

        except Exception as e:
            logger.error(f"Real-time frame producer error: {e}")
        finally:
            logger.info("Real-time frame producer stopped")

    def stop(self):
        self._stop_event.set()

    def is_completed(self) -> bool:
        """Check if stimulus presentation has completed all frames."""
        with self._state_lock:
            return self._is_completed

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for stimulus presentation to complete.

        Args:
            timeout: Maximum time to wait in seconds (None = wait forever)

        Returns:
            True if completed, False if timeout
        """
        return self._completion_event.wait(timeout=timeout)


class SharedMemoryService:
    """Service wrapper managing shared memory stream and realtime producer."""

    def __init__(self, config: SharedMemoryConfig):
        self._config = config
        self._stream: Optional[SharedMemoryFrameStream] = None
        self._producer: Optional[RealtimeFrameProducer] = None
        self._last_stimulus_timestamp: Optional[int] = None  # Microseconds
        self._last_stimulus_frame_id: Optional[int] = None
        self._timestamp_lock = threading.RLock()  # Thread-safe access to stimulus timestamps
        self._producer_lock = threading.RLock()  # Thread-safe access to producer

    @property
    def stream(self) -> SharedMemoryFrameStream:
        if self._stream is None:
            self._stream = SharedMemoryFrameStream(self._config)
            self._stream.initialize()
        return self._stream

    def start_realtime_streaming(
        self, stimulus_generator, fps: float = 60.0
    ) -> RealtimeFrameProducer:
        with self._producer_lock:
            if self._producer:
                self.stop_realtime_streaming()
            self._producer = RealtimeFrameProducer(self.stream, stimulus_generator, fps)
            self._producer.start()
            return self._producer

    def stop_realtime_streaming(self) -> None:
        with self._producer_lock:
            if self._producer:
                self._producer.stop()
                self._producer.join(timeout=1.0)
                self._producer = None

    def wait_for_stimulus_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for the current stimulus presentation to complete all frames.

        Args:
            timeout: Maximum time to wait in seconds (None = wait forever)

        Returns:
            True if completed, False if timeout or no producer active
        """
        with self._producer_lock:
            if self._producer:
                return self._producer.wait_for_completion(timeout=timeout)
            return False

    def cleanup(self) -> None:
        with self._producer_lock:
            if self._producer:
                self.stop_realtime_streaming()
        if self._stream:
            self._stream.cleanup()
            self._stream = None

    def write_frame(self, frame_data: np.ndarray, metadata: Dict[str, Any]) -> int:
        """Write stimulus frame to shared memory"""
        return self.stream.write_frame(frame_data, metadata)

    def write_preview_frame(
        self, frame_data: np.ndarray, metadata: Dict[str, Any]
    ) -> int:
        return self.stream.write_preview_frame(frame_data, metadata)

    def write_camera_frame(
        self,
        frame_data: np.ndarray,
        camera_name: str = "unknown",
        capture_timestamp_us: Optional[int] = None,
        exposure_us: Optional[int] = None,
        gain: Optional[float] = None,
    ) -> int:
        """Write camera frame to shared memory on separate channel"""
        return self.stream.write_camera_frame(
            frame_data, camera_name, capture_timestamp_us, exposure_us, gain
        )

    def publish_black_frame(self, width: int, height: int) -> int:
        """Publish a solid black RGBA frame to shared memory."""
        return self.stream.publish_black_frame(width, height)

    def clear_stimulus_frames(self) -> None:
        """Clear stimulus shared memory buffer and metadata."""
        self.stream.clear_stimulus_frames()

    def get_frame_info(self, frame_id: int):
        """Get stimulus frame metadata by ID"""
        return self.stream.get_frame_info(frame_id)

    def set_stimulus_timestamp(self, timestamp_us: int, frame_id: int) -> None:
        """Store the most recent stimulus frame timestamp for correlation."""
        with self._timestamp_lock:
            self._last_stimulus_timestamp = timestamp_us
            self._last_stimulus_frame_id = frame_id

    def get_stimulus_timestamp(self) -> tuple[Optional[int], Optional[int]]:
        """Get the most recent stimulus frame timestamp and frame_id."""
        with self._timestamp_lock:
            return self._last_stimulus_timestamp, self._last_stimulus_frame_id

    def clear_stimulus_timestamp(self) -> None:
        """Clear the stimulus timestamp (called when stimulus stops)."""
        with self._timestamp_lock:
            prev_ts = self._last_stimulus_timestamp
            self._last_stimulus_timestamp = None
            self._last_stimulus_frame_id = None
            logger.info(f"Stimulus timestamp cleared (was: {prev_ts})")


def get_shared_memory_stream() -> Optional[SharedMemoryFrameStream]:
    services = get_services()
    shared_memory = getattr(services, "shared_memory", None)
    if shared_memory is None:
        return None
    return shared_memory.stream


def get_realtime_producer() -> Optional[RealtimeFrameProducer]:
    services = get_services()
    shared_memory = getattr(services, "shared_memory", None)
    if shared_memory is None:
        return None
    return shared_memory._producer
