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

        self.camera_frame_counter = 0
        self.camera_write_offset = 0

        self.zmq_context = zmq.Context()
        self.metadata_socket = None
        self.channel_sockets = {}

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

                if frame_data.dtype != np.uint8:
                    frame_data = frame_data.astype(np.uint8)

                frame_bytes = frame_data.tobytes()
                data_size = len(frame_bytes)

                if self.write_offset + data_size > self.buffer_size_bytes:
                    self.write_offset = 0  # Wrap to beginning

                self.shm_mmap[self.write_offset : self.write_offset + data_size] = (
                    frame_bytes
                )

                self.frame_counter += 1
                timestamp_us = int(time.time() * 1_000_000)

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

                self.frame_registry[self.frame_counter] = frame_metadata

                if len(self.frame_registry) > self.ring_buffer_frames:
                    oldest_frame_id = min(self.frame_registry.keys())
                    del self.frame_registry[oldest_frame_id]

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

                try:
                    self.metadata_socket.send_json(metadata_msg, zmq.NOBLOCK)
                except zmq.Again:
                    logger.warning("Metadata send queue full, dropping frame metadata")

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
                    self.metadata_socket = None

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

    def _ensure_channel_socket(
        self, channel: Literal["stimulus", "camera"]
    ) -> zmq.Socket:
        if channel == "stimulus":
            if self.metadata_socket is None:
                self.metadata_socket = self.zmq_context.socket(zmq.PUB)
                self.metadata_socket.bind(f"tcp://*:{self.config.metadata_port}")
            return self.metadata_socket

        if channel not in self.channel_sockets:
            socket = self.zmq_context.socket(zmq.PUB)
            port = (
                self.config.metadata_port + 1
                if channel == "camera"
                else self.config.metadata_port
            )
            socket.bind(f"tcp://*:{port}")
            self.channel_sockets[channel] = socket
        return self.channel_sockets[channel]


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
        self._dataset_info: Dict[str, Any] = {}
        self._frame_index = 0

        # Real-time priority (requires appropriate permissions)
        self.priority = -10  # High priority

    def set_stimulus_params(self, direction: str) -> None:
        self._current_direction = direction
        self._frame_index = 0
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
                    total_frames = self._dataset_info.get("total_frames")
                    if total_frames and self._frame_index >= total_frames:
                        self._frame_index = 0

                    frame, metadata = self.stimulus_generator.generate_frame_at_index(
                        direction=self._current_direction,
                        frame_index=self._frame_index,
                        show_bar_mask=True,
                        total_frames=total_frames,
                    )

                    metadata.update(
                        {
                            "direction": self._current_direction,
                            "total_frames": self._dataset_info.get(
                                "total_frames", metadata.get("total_frames", 0)
                            ),
                            "start_angle": self._dataset_info.get(
                                "start_angle", metadata.get("start_angle", 0.0)
                            ),
                            "end_angle": self._dataset_info.get(
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


class SharedMemoryService:
    """Service wrapper managing shared memory stream and realtime producer."""

    def __init__(self, config: SharedMemoryConfig):
        self._config = config
        self._stream: Optional[SharedMemoryFrameStream] = None
        self._producer: Optional[RealtimeFrameProducer] = None
        self._last_stimulus_timestamp: Optional[int] = None  # Microseconds
        self._last_stimulus_frame_id: Optional[int] = None

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

    def set_stimulus_timestamp(self, timestamp_us: int, frame_id: int) -> None:
        """Store the most recent stimulus frame timestamp for correlation."""
        self._last_stimulus_timestamp = timestamp_us
        self._last_stimulus_frame_id = frame_id

    def get_stimulus_timestamp(self) -> tuple[Optional[int], Optional[int]]:
        """Get the most recent stimulus frame timestamp and frame_id."""
        return self._last_stimulus_timestamp, self._last_stimulus_frame_id


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
