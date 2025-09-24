"""
Streaming Configuration Value Objects

Immutable value objects for configuring data streaming, display,
and real-time communication in the ISI Macroscope Control System.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
from joblib import hash as joblib_hash


class StreamProtocol(Enum):
    """Streaming protocol types"""
    IPC = "ipc"                    # Electron IPC (primary)
    TCP = "tcp"                    # TCP socket (fallback)
    UDP = "udp"                    # UDP socket (low-latency)
    SHARED_MEMORY = "shared_memory"  # Shared memory (high-throughput)


class CompressionLevel(Enum):
    """Compression levels for streaming data"""
    NONE = "none"                  # No compression
    LOW = "low"                    # Minimal compression, fastest
    MEDIUM = "medium"              # Balanced compression/speed
    HIGH = "high"                  # Maximum compression, slower
    ADAPTIVE = "adaptive"          # Dynamic compression based on content


class PixelFormat(Enum):
    """Pixel formats for stream data"""
    GRAYSCALE_8 = "grayscale_8"    # 8-bit grayscale
    GRAYSCALE_16 = "grayscale_16"  # 16-bit grayscale (PCO Panda native)
    RGB_24 = "rgb_24"              # 24-bit RGB
    RGBA_32 = "rgba_32"            # 32-bit RGBA


class StreamConfiguration(BaseModel):
    """Base configuration for data streaming"""

    stream_id: str = Field(description="Unique stream identifier")
    protocol: StreamProtocol = Field(
        default=StreamProtocol.IPC,
        description="Communication protocol for streaming"
    )
    buffer_size_frames: int = Field(
        default=30,
        gt=0,
        le=300,
        description="Buffer size in number of frames"
    )
    max_frame_rate_hz: float = Field(
        default=30.0,
        gt=0.0,
        le=120.0,
        description="Maximum frame rate for streaming in Hz"
    )
    timeout_seconds: float = Field(
        default=5.0,
        gt=0.0,
        le=60.0,
        description="Stream timeout in seconds"
    )

    model_config = {"frozen": True, "use_enum_values": True}

    @field_validator('stream_id')
    @classmethod
    def validate_stream_id(cls, v):
        """Validate stream ID format"""
        if not v or not isinstance(v, str):
            raise ValueError("Stream ID must be a non-empty string")
        if len(v) > 64:
            raise ValueError("Stream ID must be 64 characters or less")
        return v


class CameraStreamConfig(StreamConfiguration):
    """Configuration for camera data streaming"""

    # Camera-specific settings
    source_width: int = Field(
        default=2048,
        gt=0,
        description="Source image width in pixels"
    )
    source_height: int = Field(
        default=2048,
        gt=0,
        description="Source image height in pixels"
    )
    source_pixel_format: PixelFormat = Field(
        default=PixelFormat.GRAYSCALE_16,
        description="Source pixel format from camera"
    )

    # Streaming optimization
    downsample_factor: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Downsampling factor for streaming (1=full resolution)"
    )
    stream_pixel_format: PixelFormat = Field(
        default=PixelFormat.GRAYSCALE_8,
        description="Pixel format for streaming (may differ from source)"
    )
    compression: CompressionLevel = Field(
        default=CompressionLevel.MEDIUM,
        description="Compression level for stream data"
    )

    # Quality settings
    jpeg_quality: Optional[int] = Field(
        default=85,
        ge=10,
        le=100,
        description="JPEG quality for compressed streams (if applicable)"
    )
    adaptive_quality: bool = Field(
        default=True,
        description="Enable adaptive quality based on bandwidth"
    )

    model_config = {"frozen": True, "use_enum_values": True}

    @property
    def stream_width(self) -> int:
        """Calculate streaming width after downsampling"""
        return self.source_width // self.downsample_factor

    @property
    def stream_height(self) -> int:
        """Calculate streaming height after downsampling"""
        return self.source_height // self.downsample_factor

    @property
    def compression_ratio(self) -> float:
        """Estimate compression ratio based on settings"""
        base_ratios = {
            CompressionLevel.NONE: 1.0,
            CompressionLevel.LOW: 0.8,
            CompressionLevel.MEDIUM: 0.6,
            CompressionLevel.HIGH: 0.4,
            CompressionLevel.ADAPTIVE: 0.6,  # Average
        }
        return base_ratios[self.compression]


class DisplayStreamConfig(StreamConfiguration):
    """Configuration for display/stimulus streaming"""

    # Display settings
    target_width: int = Field(
        default=2048,
        gt=0,
        description="Target display width in pixels"
    )
    target_height: int = Field(
        default=2048,
        gt=0,
        description="Target display height in pixels"
    )
    target_pixel_format: PixelFormat = Field(
        default=PixelFormat.GRAYSCALE_8,
        description="Target pixel format for display"
    )

    # Synchronization
    vsync_enabled: bool = Field(
        default=True,
        description="Enable vertical synchronization"
    )
    target_frame_rate_hz: float = Field(
        default=60.0,
        gt=0.0,
        le=120.0,
        description="Target display frame rate in Hz"
    )

    # Preview streaming
    enable_preview: bool = Field(
        default=True,
        description="Enable preview streaming to frontend"
    )
    preview_downsample_factor: int = Field(
        default=8,
        ge=1,
        le=32,
        description="Downsampling factor for preview stream"
    )

    model_config = {"frozen": True, "use_enum_values": True}

    @property
    def preview_width(self) -> int:
        """Calculate preview width after downsampling"""
        return self.target_width // self.preview_downsample_factor

    @property
    def preview_height(self) -> int:
        """Calculate preview height after downsampling"""
        return self.target_height // self.preview_downsample_factor


class StatusStreamConfig(StreamConfiguration):
    """Configuration for status and telemetry streaming"""

    # Status update frequency
    update_interval_ms: int = Field(
        default=100,
        ge=10,
        le=5000,
        description="Status update interval in milliseconds"
    )

    # Status categories
    include_hardware_status: bool = Field(
        default=True,
        description="Include hardware status in stream"
    )
    include_performance_metrics: bool = Field(
        default=True,
        description="Include performance metrics in stream"
    )
    include_workflow_state: bool = Field(
        default=True,
        description="Include workflow state updates in stream"
    )
    include_error_logs: bool = Field(
        default=True,
        description="Include error logs in stream"
    )

    # Data retention
    history_buffer_size: int = Field(
        default=1000,
        gt=0,
        le=10000,
        description="Number of historical status updates to retain"
    )

    model_config = {"frozen": True, "use_enum_values": True}


class StreamingProfile(BaseModel):
    """Complete streaming configuration profile for the system"""

    profile_name: str = Field(description="Profile name")
    description: Optional[str] = Field(default=None, description="Profile description")

    # Stream configurations
    camera_stream: CameraStreamConfig = Field(description="Camera streaming configuration")
    display_stream: DisplayStreamConfig = Field(description="Display streaming configuration")
    status_stream: StatusStreamConfig = Field(description="Status streaming configuration")

    # Global settings
    enable_bandwidth_monitoring: bool = Field(
        default=True,
        description="Enable bandwidth monitoring and throttling"
    )
    max_total_bandwidth_mbps: float = Field(
        default=100.0,
        gt=0.0,
        le=1000.0,
        description="Maximum total bandwidth in Mbps"
    )
    priority_order: List[str] = Field(
        default=["display_stream", "status_stream", "camera_stream"],
        description="Stream priority order (highest to lowest)"
    )

    # Development settings
    development_mode: bool = Field(
        default=False,
        description="Enable development mode optimizations"
    )
    mock_hardware: bool = Field(
        default=False,
        description="Use mock hardware for development"
    )

    model_config = {"frozen": True, "use_enum_values": True}

    @field_validator('priority_order')
    @classmethod
    def validate_priority_order(cls, v):
        """Validate priority order contains expected stream names"""
        expected_streams = {"camera_stream", "display_stream", "status_stream"}
        provided_streams = set(v)
        if provided_streams != expected_streams:
            raise ValueError(f"Priority order must contain exactly: {expected_streams}")
        return v

    @property
    def profile_hash(self) -> str:
        """Generate deterministic hash for streaming profile comparison"""
        profile_data = {
            "camera_stream": {
                "source_width": self.camera_stream.source_width,
                "source_height": self.camera_stream.source_height,
                "downsample_factor": self.camera_stream.downsample_factor,
                "max_frame_rate_hz": self.camera_stream.max_frame_rate_hz,
                "compression": self.camera_stream.compression.value,
            },
            "display_stream": {
                "target_width": self.display_stream.target_width,
                "target_height": self.display_stream.target_height,
                "target_frame_rate_hz": self.display_stream.target_frame_rate_hz,
                "vsync_enabled": self.display_stream.vsync_enabled,
            },
            "status_stream": {
                "update_interval_ms": self.status_stream.update_interval_ms,
                "include_performance_metrics": self.status_stream.include_performance_metrics,
            },
            "max_total_bandwidth_mbps": self.max_total_bandwidth_mbps,
        }
        return joblib_hash(profile_data)

    def get_total_estimated_bandwidth_mbps(self) -> float:
        """Estimate total bandwidth usage"""
        # Camera stream bandwidth
        camera_bytes_per_frame = (
            self.camera_stream.stream_width *
            self.camera_stream.stream_height *
            (2 if self.camera_stream.stream_pixel_format == PixelFormat.GRAYSCALE_16 else 1)
        )
        camera_bandwidth = (
            camera_bytes_per_frame *
            self.camera_stream.max_frame_rate_hz *
            self.camera_stream.compression_ratio *
            8 / 1_000_000  # Convert to Mbps
        )

        # Display stream (preview only)
        if self.display_stream.enable_preview:
            preview_bytes_per_frame = (
                self.display_stream.preview_width *
                self.display_stream.preview_height
            )
            display_bandwidth = (
                preview_bytes_per_frame *
                30.0 *  # Preview frame rate
                8 / 1_000_000  # Convert to Mbps
            )
        else:
            display_bandwidth = 0.0

        # Status stream (minimal)
        status_bandwidth = 0.1  # Approximately 0.1 Mbps for status data

        return camera_bandwidth + display_bandwidth + status_bandwidth


