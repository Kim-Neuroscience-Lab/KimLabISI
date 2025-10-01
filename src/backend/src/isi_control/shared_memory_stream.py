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
import struct
from typing import Dict, Any, Optional, Tuple

from .service_locator import get_services
from dataclasses import dataclass
import threading

from .config import SharedMemoryConfig
from .logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class FrameMetadata:
    """Frame metadata for shared memory streaming"""

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


class SharedMemoryFrameStream:
    """High-performance shared memory streaming for stimulus frames"""

    def __init__(self, config: SharedMemoryConfig):
        self.config = config
        self.stream_name = config.stream_name
        self.buffer_size_bytes = config.buffer_size_mb * 1024 * 1024
        self.frame_counter = 0
        self.write_offset = 0

        self.zmq_context = zmq.Context()
        self.metadata_socket = None

        self.shm_fd = None
        self.shm_mmap = None

        self._lock = threading.RLock()
        self._running = False

        self.ring_buffer_frames = 100
        self.frame_registry = {}

    def initialize(self) -> None:
        try:
            with self._lock:
                shm_path = f"/tmp/{self.stream_name}_shm"
                self.shm_fd = os.open(
                    shm_path, os.O_CREAT | os.O_RDWR | os.O_TRUNC, 0o666
                )
                os.ftruncate(self.shm_fd, self.buffer_size_bytes)

                self.shm_mmap = mmap.mmap(
                    self.shm_fd,
                    self.buffer_size_bytes,
                    access=mmap.ACCESS_WRITE,
                )

                self.metadata_socket = self.zmq_context.socket(zmq.PUB)
                self.metadata_socket.bind(f"tcp://*:{self.config.metadata_port}")

                time.sleep(0.1)

                self._running = True
                logger.info(
                    "SharedMemoryFrameStream initialised: %s (port %d)",
                    shm_path,
                    self.config.metadata_port,
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

                # Convert frame to bytes
                if frame_data.dtype != np.uint8:
                    frame_data = frame_data.astype(np.uint8)

                frame_bytes = frame_data.tobytes()
                data_size = len(frame_bytes)

                # Check if we need to wrap around ring buffer
                if self.write_offset + data_size > self.buffer_size_bytes:
                    self.write_offset = 0  # Wrap to beginning

                # Write frame data directly to shared memory
                self.shm_mmap[self.write_offset : self.write_offset + data_size] = (
                    frame_bytes
                )

                # Create frame metadata
                self.frame_counter += 1
                timestamp_us = int(time.time() * 1_000_000)  # Microsecond precision

                frame_metadata = FrameMetadata(
                    frame_id=self.frame_counter,
                    timestamp_us=timestamp_us,
                    frame_index=metadata.get("frame_index", 0),
                    direction=metadata.get("direction", "LR"),
                    angle_degrees=metadata.get("angle_degrees", 0.0),
                    width_px=frame_data.shape[1],
                    height_px=frame_data.shape[0],
                    data_size_bytes=data_size,
                    offset_bytes=self.write_offset,
                    total_frames=metadata.get("total_frames", 0),
                    start_angle=metadata.get("start_angle", 0.0),
                    end_angle=metadata.get("end_angle", 0.0),
                )

                # Register frame in ring buffer
                self.frame_registry[self.frame_counter] = frame_metadata

                # Maintain ring buffer size limit
                if len(self.frame_registry) > self.ring_buffer_frames:
                    oldest_frame_id = min(self.frame_registry.keys())
                    del self.frame_registry[oldest_frame_id]

                # Send metadata via ZeroMQ
                metadata_msg = {
                    "frame_id": frame_metadata.frame_id,
                    "timestamp_us": frame_metadata.timestamp_us,
                    "frame_index": frame_metadata.frame_index,
                    "direction": frame_metadata.direction,
                    "angle_degrees": frame_metadata.angle_degrees,
                    "width_px": frame_metadata.width_px,
                    "height_px": frame_metadata.height_px,
                    "data_size_bytes": frame_metadata.data_size_bytes,
                    "offset_bytes": frame_metadata.offset_bytes,
                    "total_frames": frame_metadata.total_frames,
                    "start_angle": frame_metadata.start_angle,
                    "end_angle": frame_metadata.end_angle,
                    "shm_path": f"/tmp/{self.stream_name}_shm",
                }

                # Non-blocking send to avoid blocking frame generation
                try:
                    payload = metadata_msg
                    self.metadata_socket.send_json(payload, zmq.NOBLOCK)
                except zmq.Again:
                    logger.warning("Metadata send queue full, dropping frame metadata")

                # Update write offset for next frame
                self.write_offset += data_size

                return frame_metadata.frame_id

        except Exception as e:
            logger.error(f"Error writing frame to shared memory: {e}")
            raise

    def get_frame_info(self, frame_id: int) -> Optional[FrameMetadata]:
        """Get frame metadata by ID"""
        with self._lock:
            return self.frame_registry.get(frame_id)

    def cleanup(self):
        """Clean up shared memory and ZeroMQ resources"""
        try:
            with self._lock:
                self._running = False

                if self.metadata_socket:
                    self.metadata_socket.close()

                if self.shm_mmap:
                    self.shm_mmap.close()

                if self.shm_fd:
                    os.close(self.shm_fd)

                # Remove shared memory file
                shm_path = f"/tmp/{self.stream_name}_shm"
                if os.path.exists(shm_path):
                    os.unlink(shm_path)

                self.zmq_context.term()

                logger.info("SharedMemoryFrameStream cleaned up")

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
        self._current_direction = "LR"
        self._current_angle = 0.0
        self._frame_index = 0

        # Real-time priority (requires appropriate permissions)
        self.priority = -10  # High priority

    def set_stimulus_params(self, direction: str, start_angle: float = 0.0):
        """Update stimulus parameters"""
        self._current_direction = direction
        self._current_angle = start_angle
        self._frame_index = 0

    def run(self):
        """High-precision frame generation loop"""
        try:
            # Attempt to set real-time priority
            try:
                os.nice(self.priority)
            except PermissionError:
                logger.warning("Could not set real-time priority (requires root)")

            start_time_us = int(time.time() * 1_000_000)
            next_frame_time_us = start_time_us

            logger.info(f"Real-time frame producer started: {self.target_fps} FPS")

            while not self._stop_event.is_set():
                current_time_us = int(time.time() * 1_000_000)

                # Skip if we're behind schedule
                if current_time_us >= next_frame_time_us:
                    # Generate frame
                    frame = self.stimulus_generator.generate_frame_at_angle(
                        direction=self._current_direction,
                        angle=self._current_angle,
                        show_bar_mask=True,
                        frame_index=self._frame_index,
                    )

                    # Write to shared memory
                    metadata = {
                        "frame_index": self._frame_index,
                        "direction": self._current_direction,
                        "angle_degrees": self._current_angle,
                    }

                    frame_id = self.stream.write_frame(frame, metadata)

                    # Send stimulus frame event for timing correlation
                    try:
                        from .service_locator import get_services

                        ipc = get_services().ipc
                        ipc.send_control_message(
                            {
                                "type": "stimulus_frame_presented",
                                "frame_id": frame_id,
                                "timestamp_us": int(time.time() * 1_000_000),
                                "direction": self._current_direction,
                                "frame_index": self._frame_index,
                                "angle_degrees": self._current_angle,
                            }
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send stimulus frame event: {e}")

                    # Update for next frame
                    self._frame_index += 1
                    self._current_angle += 1.0  # Example progression

                    # Schedule next frame
                    next_frame_time_us += self.frame_interval_us
                else:
                    # Precise sleep until next frame time
                    sleep_us = next_frame_time_us - current_time_us
                    if sleep_us > 1000:  # Only sleep if > 1ms
                        time.sleep(sleep_us / 1_000_000)

        except Exception as e:
            logger.error(f"Real-time frame producer error: {e}")
        finally:
            logger.info("Real-time frame producer stopped")

    def stop(self):
        """Stop the frame producer"""
        self._stop_event.set()


class SharedMemoryService:
    """Service wrapper managing shared memory stream and realtime producer."""

    def __init__(self, config: SharedMemoryConfig):
        self._config = config
        self._stream: Optional[SharedMemoryFrameStream] = None
        self._producer: Optional[RealtimeFrameProducer] = None

    @property
    def stream(self) -> SharedMemoryFrameStream:
        if self._stream is None:
            self._stream = SharedMemoryFrameStream(self._config)
            self._stream.initialize()
        return self._stream

    def start_realtime_streaming(
        self, stimulus_generator, fps: float = 60.0
    ) -> RealtimeFrameProducer:
        if self._producer:
            self.stop_realtime_streaming()
        self._producer = RealtimeFrameProducer(self.stream, stimulus_generator, fps)
        self._producer.start()
        return self._producer

    def stop_realtime_streaming(self) -> None:
        if self._producer:
            self._producer.stop()
            self._producer.join(timeout=1.0)
            self._producer = None

    def cleanup(self) -> None:
        if self._producer:
            self.stop_realtime_streaming()
        if self._stream:
            self._stream.cleanup()
            self._stream = None

    def write_frame(self, frame_data: np.ndarray, metadata: Dict[str, Any]) -> int:
        return self.stream.write_frame(frame_data, metadata)


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
