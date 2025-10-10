"""Shared Memory Frame Streaming System.

Provides ultra-high performance binary frame data transfer between backend and frontend.
Simplified from original implementation: accepts config in constructor, no service locator or globals.
"""

from __future__ import annotations

import logging
import mmap
import os
import threading
import time
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

import numpy as np
import zmq

logger = logging.getLogger(__name__)


@dataclass
class FrameMetadata:
    """Frame metadata for stimulus frames in shared memory streaming."""

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
        result = asdict(self)
        result["shm_path"] = shm_path
        return result


@dataclass
class CameraFrameMetadata:
    """Frame metadata for camera frames in shared memory streaming."""

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
        result = asdict(self)
        result["shm_path"] = shm_path
        return result


class SharedMemoryFrameStream:
    """High-performance shared memory streaming for stimulus and camera frames.

    Simplified implementation using constructor injection.
    """

    def __init__(
        self,
        stream_name: str = "stimulus_stream",
        buffer_size_mb: int = 100,
        metadata_port: int = 5557,
        camera_metadata_port: int = 5559
    ):
        """Initialize shared memory stream with explicit configuration.

        Args:
            stream_name: Name for the shared memory stream
            buffer_size_mb: Size of shared memory buffer in megabytes
            metadata_port: Port for stimulus frame metadata
            camera_metadata_port: Port for camera frame metadata
        """
        self.stream_name = stream_name
        self.buffer_size_bytes = buffer_size_mb * 1024 * 1024
        self.metadata_port = metadata_port
        self.camera_metadata_port = camera_metadata_port

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
        """Initialize shared memory buffers and ZeroMQ sockets."""
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
                self.metadata_socket.bind(f"tcp://*:{self.metadata_port}")

                # Camera metadata socket (separate channel)
                self.camera_metadata_socket = self.zmq_context.socket(zmq.PUB)
                self.camera_metadata_socket.bind(
                    f"tcp://*:{self.camera_metadata_port}"
                )

                time.sleep(0.1)

                self._running = True
                logger.info(
                    "SharedMemoryFrameStream initialised: stimulus=%s, camera=%s (stimulus port %d, camera port %d)",
                    stimulus_path,
                    camera_path,
                    self.metadata_port,
                    self.camera_metadata_port,
                )
        except Exception as exc:
            logger.error("Failed to initialise SharedMemoryFrameStream: %s", exc)
            self.cleanup()
            raise

    def write_frame(self, frame_data: np.ndarray, metadata: Dict[str, Any]) -> int:
        """Write frame to shared memory with zero-copy operation.

        Args:
            frame_data: Frame data as numpy array
            metadata: Frame metadata dictionary

        Returns:
            Frame ID
        """
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

                # Validate critical metadata fields
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

                # Other fields can have sensible defaults
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
        """Write preview frame to shared memory.

        Args:
            frame_data: Frame data as numpy array
            metadata: Frame metadata dictionary

        Returns:
            Frame ID
        """
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
        """Write camera frame to shared memory on separate channel.

        Args:
            frame_data: Frame data as numpy array
            camera_name: Name of the camera
            capture_timestamp_us: Hardware capture timestamp in microseconds
            exposure_us: Exposure time in microseconds
            gain: Camera gain

        Returns:
            Frame ID
        """
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
                self.stimulus_shm_mmap.write(b"\x00" * self.buffer_size_bytes)
                self.stimulus_shm_mmap.flush()
        logger.debug("Stimulus shared memory frames cleared")

    def publish_black_frame(self, width: int, height: int) -> int:
        """Publish a solid black RGBA frame to shared memory.

        Args:
            width: Frame width in pixels
            height: Frame height in pixels

        Returns:
            Frame ID
        """
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
        """Get stimulus frame metadata by ID.

        Args:
            frame_id: Frame ID

        Returns:
            Frame metadata or None if not found
        """
        with self._lock:
            return self.frame_registry.get(frame_id)

    def get_camera_frame_info(self, frame_id: int) -> Optional[CameraFrameMetadata]:
        """Get camera frame metadata by ID.

        Args:
            frame_id: Frame ID

        Returns:
            Camera frame metadata or None if not found
        """
        with self._lock:
            return self.camera_frame_registry.get(frame_id)

    def cleanup(self):
        """Clean up shared memory and ZeroMQ resources."""
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


class SharedMemoryService:
    """Service wrapper managing shared memory stream.

    Simplified implementation using constructor injection.
    """

    def __init__(
        self,
        stream_name: str = "stimulus_stream",
        buffer_size_mb: int = 100,
        metadata_port: int = 5557,
        camera_metadata_port: int = 5559
    ):
        """Initialize shared memory service with explicit configuration.

        Args:
            stream_name: Name for the shared memory stream
            buffer_size_mb: Size of shared memory buffer in megabytes
            metadata_port: Port for stimulus frame metadata
            camera_metadata_port: Port for camera frame metadata
        """
        self._stream_name = stream_name
        self._buffer_size_mb = buffer_size_mb
        self._metadata_port = metadata_port
        self._camera_metadata_port = camera_metadata_port

        self._stream: Optional[SharedMemoryFrameStream] = None
        self._last_stimulus_timestamp: Optional[int] = None  # Microseconds
        self._last_stimulus_frame_id: Optional[int] = None
        self._timestamp_lock = threading.RLock()

    @property
    def stream(self) -> SharedMemoryFrameStream:
        """Get or create the shared memory stream."""
        if self._stream is None:
            self._stream = SharedMemoryFrameStream(
                stream_name=self._stream_name,
                buffer_size_mb=self._buffer_size_mb,
                metadata_port=self._metadata_port,
                camera_metadata_port=self._camera_metadata_port
            )
            self._stream.initialize()
        return self._stream

    def cleanup(self) -> None:
        """Clean up resources."""
        if self._stream:
            self._stream.cleanup()
            self._stream = None

    def write_frame(self, frame_data: np.ndarray, metadata: Dict[str, Any]) -> int:
        """Write stimulus frame to shared memory."""
        return self.stream.write_frame(frame_data, metadata)

    def write_preview_frame(
        self, frame_data: np.ndarray, metadata: Dict[str, Any]
    ) -> int:
        """Write preview frame to shared memory."""
        return self.stream.write_preview_frame(frame_data, metadata)

    def write_camera_frame(
        self,
        frame_data: np.ndarray,
        camera_name: str = "unknown",
        capture_timestamp_us: Optional[int] = None,
        exposure_us: Optional[int] = None,
        gain: Optional[float] = None,
    ) -> int:
        """Write camera frame to shared memory on separate channel."""
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
        """Get stimulus frame metadata by ID."""
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
        """Clear the stimulus timestamp."""
        with self._timestamp_lock:
            prev_ts = self._last_stimulus_timestamp
            self._last_stimulus_timestamp = None
            self._last_stimulus_frame_id = None
            logger.info(f"Stimulus timestamp cleared (was: {prev_ts})")
