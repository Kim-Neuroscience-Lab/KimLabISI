"""
Frame Manager for Timestamping and Preview Generation

Manages frame timestamping, ordering, and preview generation for the streaming system.
Coordinates between full-resolution scientific data and downsampled monitoring previews.

Key Design Principles:
- Scientific data (full resolution) never passes through frontend
- Preview generation is non-blocking and quality-degradation acceptable
- Hardware timestamps preserved for all scientific frames
- Independent processing paths for critical vs monitoring data
"""

import numpy as np
import time
from typing import Optional, Dict, Any, Protocol, Tuple
from dataclasses import dataclass, field
from threading import RLock
import logging

from .preview_generator import PreviewGenerator, create_preview_generator
from domain.value_objects.stream_config import DisplayStreamConfig

logger = logging.getLogger(__name__)


@dataclass
class FrameMetadata:
    """Metadata for a single frame"""
    frame_number: int
    timestamp_us: int  # Microsecond timestamp
    source_type: str  # 'stimulus', 'camera', etc.
    resolution: Tuple[int, int]  # (width, height)
    format: str  # Frame format (e.g., 'uint8', 'float32')
    hardware_timestamp: Optional[int] = None  # Hardware-specific timestamp
    processing_timestamp: Optional[int] = None  # When frame was processed
    additional_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessedFrame:
    """A processed frame with metadata and optional preview"""
    metadata: FrameMetadata
    full_frame: np.ndarray  # Full resolution frame (for scientific storage)
    preview_frame: Optional[np.ndarray] = None  # Downsampled preview (for monitoring)


class FrameProcessor(Protocol):
    """Protocol for frame processing implementations"""

    def process_frame(
        self,
        frame: np.ndarray,
        frame_number: int,
        source_type: str,
        hardware_timestamp: Optional[int] = None
    ) -> ProcessedFrame:
        """Process a frame with timestamping and preview generation"""
        ...


class FrameManager:
    """
    Manages frame timestamping, ordering, and preview generation

    This class coordinates between full-resolution scientific data paths
    and downsampled preview generation for frontend monitoring.
    """

    def __init__(
        self,
        preview_config: DisplayStreamConfig,
        enable_previews: bool = True,
        hardware_accelerated: bool = True
    ):
        """
        Initialize frame manager

        Args:
            preview_config: Display stream configuration for preview generation
            enable_previews: Generate preview frames for monitoring
            hardware_accelerated: Use hardware acceleration for previews
        """
        self._preview_config = preview_config
        self._enable_previews = enable_previews
        self._frame_counter = 0
        self._lock = RLock()

        # Initialize preview generator if previews enabled
        self._preview_generator: Optional[PreviewGenerator] = None
        if self._enable_previews:
            self._preview_generator = create_preview_generator(
                preview_config,
                hardware_accelerated
            )

        # Frame statistics
        self._stats = {
            'frames_processed': 0,
            'frames_with_previews': 0,
            'processing_errors': 0,
            'average_processing_time_us': 0.0
        }

    def process_stimulus_frame(
        self,
        frame: np.ndarray,
        hardware_timestamp: Optional[int] = None
    ) -> ProcessedFrame:
        """
        Process a stimulus frame with timestamping and optional preview

        Args:
            frame: Full resolution stimulus frame
            hardware_timestamp: Hardware-specific timestamp if available

        Returns:
            ProcessedFrame with metadata and optional preview
        """
        return self._process_frame_internal(
            frame=frame,
            source_type='stimulus',
            hardware_timestamp=hardware_timestamp
        )

    def process_camera_frame(
        self,
        frame: np.ndarray,
        hardware_timestamp: Optional[int] = None
    ) -> ProcessedFrame:
        """
        Process a camera frame with timestamping and optional preview

        Args:
            frame: Full resolution camera frame
            hardware_timestamp: Hardware-specific timestamp if available

        Returns:
            ProcessedFrame with metadata and optional preview
        """
        return self._process_frame_internal(
            frame=frame,
            source_type='camera',
            hardware_timestamp=hardware_timestamp
        )

    def _process_frame_internal(
        self,
        frame: np.ndarray,
        source_type: str,
        hardware_timestamp: Optional[int] = None
    ) -> ProcessedFrame:
        """Internal frame processing implementation"""

        start_time_us = int(time.perf_counter() * 1_000_000)

        try:
            with self._lock:
                # Generate frame number and timestamp
                frame_number = self._frame_counter
                self._frame_counter += 1
                timestamp_us = int(time.time() * 1_000_000)

            # Create metadata
            metadata = FrameMetadata(
                frame_number=frame_number,
                timestamp_us=timestamp_us,
                source_type=source_type,
                resolution=(frame.shape[1], frame.shape[0]),
                format=str(frame.dtype),
                hardware_timestamp=hardware_timestamp,
                processing_timestamp=start_time_us
            )

            # Generate preview if enabled
            preview_frame = None
            if self._enable_previews and self._preview_generator is not None:
                try:
                    if source_type == 'stimulus':
                        preview_frame = self._preview_generator.generate_stimulus_preview(frame)
                    elif source_type == 'camera':
                        preview_frame = self._preview_generator.generate_camera_preview(frame)
                    else:
                        # Generic preview generation
                        target_size = (
                            self._preview_config.preview_width,
                            self._preview_config.preview_height
                        )
                        preview_frame = self._preview_generator._backend.downsample_frame(
                            frame, target_size
                        )

                    if preview_frame is not None:
                        with self._lock:
                            self._stats['frames_with_previews'] += 1

                except Exception as e:
                    logger.warning(f"Failed to generate preview for {source_type} frame {frame_number}: {e}")
                    preview_frame = None

            # Update statistics
            processing_time_us = int(time.perf_counter() * 1_000_000) - start_time_us
            with self._lock:
                self._stats['frames_processed'] += 1
                # Rolling average of processing time
                count = self._stats['frames_processed']
                current_avg = self._stats['average_processing_time_us']
                self._stats['average_processing_time_us'] = (
                    (current_avg * (count - 1) + processing_time_us) / count
                )

            return ProcessedFrame(
                metadata=metadata,
                full_frame=frame,
                preview_frame=preview_frame
            )

        except Exception as e:
            with self._lock:
                self._stats['processing_errors'] += 1
            logger.error(f"Error processing {source_type} frame: {e}")
            raise

    def get_statistics(self) -> Dict[str, Any]:
        """Get frame processing statistics"""
        with self._lock:
            return self._stats.copy()

    def reset_statistics(self) -> None:
        """Reset frame processing statistics"""
        with self._lock:
            self._stats = {
                'frames_processed': 0,
                'frames_with_previews': 0,
                'processing_errors': 0,
                'average_processing_time_us': 0.0
            }

    def update_preview_config(self, config: DisplayStreamConfig) -> None:
        """Update preview generation configuration"""
        self._preview_config = config
        if self._preview_generator is not None:
            self._preview_generator.update_config(config)

    def enable_previews(self, enable: bool, hardware_accelerated: bool = True) -> None:
        """Enable or disable preview generation"""
        self._enable_previews = enable

        if enable and self._preview_generator is None:
            # Initialize preview generator
            self._preview_generator = create_preview_generator(
                self._preview_config,
                hardware_accelerated
            )
        elif not enable:
            # Disable preview generator
            self._preview_generator = None

    def is_previews_enabled(self) -> bool:
        """Check if preview generation is enabled"""
        return self._enable_previews and self._preview_generator is not None


class StreamingFrameManager:
    """
    Extended frame manager for real-time streaming applications

    Provides additional functionality for streaming scenarios including
    frame buffering, rate limiting, and quality adaptation.
    """

    def __init__(
        self,
        base_manager: FrameManager,
        max_buffer_size: int = 100,
        target_fps: Optional[float] = None
    ):
        """
        Initialize streaming frame manager

        Args:
            base_manager: Base frame manager for core functionality
            max_buffer_size: Maximum number of frames to buffer
            target_fps: Target frame rate for streaming (None = unlimited)
        """
        self._base_manager = base_manager
        self._max_buffer_size = max_buffer_size
        self._target_fps = target_fps
        self._frame_buffer: list[ProcessedFrame] = []
        self._last_frame_time = 0.0
        self._lock = RLock()

    def process_frame_for_streaming(
        self,
        frame: np.ndarray,
        source_type: str,
        hardware_timestamp: Optional[int] = None
    ) -> Optional[ProcessedFrame]:
        """
        Process frame with streaming optimizations

        Args:
            frame: Input frame
            source_type: Type of frame source
            hardware_timestamp: Hardware timestamp if available

        Returns:
            ProcessedFrame if frame should be streamed, None if dropped
        """
        current_time = time.time()

        # Rate limiting check
        if self._target_fps is not None:
            min_interval = 1.0 / self._target_fps
            if current_time - self._last_frame_time < min_interval:
                # Drop frame to maintain target FPS
                return None

        # Process frame using base manager
        if source_type == 'stimulus':
            processed_frame = self._base_manager.process_stimulus_frame(
                frame, hardware_timestamp
            )
        elif source_type == 'camera':
            processed_frame = self._base_manager.process_camera_frame(
                frame, hardware_timestamp
            )
        else:
            processed_frame = self._base_manager._process_frame_internal(
                frame, source_type, hardware_timestamp
            )

        # Buffer management
        with self._lock:
            self._frame_buffer.append(processed_frame)

            # Remove old frames if buffer is full
            if len(self._frame_buffer) > self._max_buffer_size:
                self._frame_buffer.pop(0)

        self._last_frame_time = current_time
        return processed_frame

    def get_latest_frames(self, count: int = 1) -> list[ProcessedFrame]:
        """Get the latest processed frames from buffer"""
        with self._lock:
            return self._frame_buffer[-count:]

    def clear_buffer(self) -> None:
        """Clear the frame buffer"""
        with self._lock:
            self._frame_buffer.clear()


def create_frame_manager(
    preview_config: DisplayStreamConfig,
    enable_previews: bool = True,
    hardware_accelerated: bool = True,
    streaming_mode: bool = False,
    **streaming_kwargs
) -> FrameManager:
    """
    Factory function to create appropriate frame manager

    Args:
        preview_config: Display stream configuration for preview generation
        enable_previews: Enable preview generation
        hardware_accelerated: Use hardware acceleration
        streaming_mode: Create streaming-optimized manager
        **streaming_kwargs: Additional arguments for streaming manager

    Returns:
        Configured frame manager instance
    """
    base_manager = FrameManager(
        preview_config=preview_config,
        enable_previews=enable_previews,
        hardware_accelerated=hardware_accelerated
    )

    if streaming_mode:
        return StreamingFrameManager(base_manager, **streaming_kwargs)
    else:
        return base_manager