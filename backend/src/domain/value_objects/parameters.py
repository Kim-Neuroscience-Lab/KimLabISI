"""
Parameter Value Objects - Generation and Acquisition Parameter Separation

This module implements the core parameter system following ADR-0007:
Parameter Separation: Generation vs Acquisition.

Generation-time parameters affect stimulus content and enable dataset reuse.
Acquisition-time parameters control experimental execution and protocol.
"""

from enum import Enum
from typing import Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field, field_validator
import hashlib
import json


class ParameterSource(Enum):
    """Source of parameter values"""
    DEFAULT = "default"  # Literature defaults (Marshel et al.)
    USER_CONFIG = "user_config"  # User-defined configuration
    PARAMETER_STORE = "parameter_store"  # Production parameter store
    SESSION_LOADED = "session_loaded"  # Loaded from saved session


class SpatialConfiguration(BaseModel):
    """Spatial configuration parameters for monitor setup (generation-time)

    These parameters affect stimulus visual field mapping and coordinate transformation.
    Changes to these parameters invalidate existing stimulus datasets.
    """

    # Monitor geometry
    monitor_distance_cm: float = Field(
        default=10.0,
        ge=5.0,
        le=20.0,
        description="Distance from mouse eye to monitor in cm (Marshel et al.: 10cm)"
    )
    monitor_angle_degrees: float = Field(
        default=20.0,
        ge=0.0,
        le=45.0,
        description="Monitor angle inward toward nose in degrees (Marshel et al.: 20 degrees)"
    )
    monitor_height_degrees: float = Field(
        default=0.0,
        ge=-15.0,
        le=15.0,
        description="Monitor elevation relative to eye level in degrees"
    )
    monitor_roll_degrees: float = Field(
        default=0.0,
        ge=-10.0,
        le=10.0,
        description="Monitor roll rotation in degrees"
    )

    # Screen physical properties
    screen_width_cm: float = Field(
        default=52.0,
        gt=0.0,
        description="Physical screen width in cm"
    )
    screen_height_cm: float = Field(
        default=52.0,
        gt=0.0,
        description="Physical screen height in cm"
    )
    screen_width_pixels: int = Field(
        default=2048,
        gt=0,
        description="Screen resolution width in pixels"
    )
    screen_height_pixels: int = Field(
        default=2048,
        gt=0,
        description="Screen resolution height in pixels"
    )

    # Visual field coverage (derived from Marshel et al.)
    field_of_view_horizontal_degrees: float = Field(
        default=147.0,
        gt=0.0,
        le=180.0,
        description="Horizontal visual field coverage in degrees (Marshel et al.: 147 degrees)"
    )
    field_of_view_vertical_degrees: float = Field(
        default=153.0,
        gt=0.0,
        le=180.0,
        description="Vertical visual field coverage in degrees (Marshel et al.: 153 degrees)"
    )

    model_config = {"frozen": True}

    @property
    def config_hash(self) -> str:
        """Generate MD5 hash for parameter comparison and dataset reuse validation"""
        # Create canonical parameter dict in sorted order
        params = {
            "monitor_distance_cm": self.monitor_distance_cm,
            "monitor_angle_degrees": self.monitor_angle_degrees,
            "monitor_height_degrees": self.monitor_height_degrees,
            "monitor_roll_degrees": self.monitor_roll_degrees,
            "screen_width_cm": self.screen_width_cm,
            "screen_height_cm": self.screen_height_cm,
            "screen_width_pixels": self.screen_width_pixels,
            "screen_height_pixels": self.screen_height_pixels,
            "field_of_view_horizontal_degrees": self.field_of_view_horizontal_degrees,
            "field_of_view_vertical_degrees": self.field_of_view_vertical_degrees,
        }
        canonical_json = json.dumps(params, sort_keys=True, separators=(',', ':'))
        return hashlib.md5(canonical_json.encode()).hexdigest()

    @property
    def pixels_per_degree(self) -> float:
        """Calculate pixels per degree of visual angle"""
        import math
        # Calculate degrees per pixel using display geometry
        screen_width_degrees = 2 * math.degrees(math.atan(self.screen_width_cm / (2 * self.monitor_distance_cm)))
        return self.screen_width_pixels / screen_width_degrees


class StimulusGenerationParams(BaseModel):
    """Stimulus generation parameters (generation-time)

    These parameters affect the visual content of generated stimuli.
    Changes to these parameters invalidate existing stimulus datasets.
    Based on Marshel et al. 2011 Supplemental Experimental Procedures.
    """

    # Bar stimulus properties
    bar_width_degrees: float = Field(
        default=20.0,
        gt=0.0,
        le=45.0,
        description="Bar width in degrees of visual angle (Marshel et al.: 20 degrees)"
    )

    # Movement and timing
    drift_speed_degrees_per_sec: float = Field(
        default=9.0,
        gt=0.0,
        le=50.0,
        description="Bar drift speed in degrees per second (Marshel et al.: 8.5-9.5 degrees/s)"
    )

    # Checkerboard pattern properties
    pattern_type: str = Field(
        default="counter_phase_checkerboard",
        description="Type of pattern within stimulus (Marshel et al.: counter-phase checkerboard)"
    )
    checkerboard_size_degrees: float = Field(
        default=25.0,
        gt=0.0,
        le=50.0,
        description="Checkerboard square size in degrees (Marshel et al.: 25 degrees)"
    )
    flicker_frequency_hz: float = Field(
        default=6.0,
        gt=0.0,
        le=30.0,
        description="Counter-phase flicker frequency in Hz (Marshel et al.: 166ms period = 6Hz)"
    )

    # Visual properties
    contrast: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Stimulus contrast (0-1, full black to white)"
    )
    background_luminance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Background luminance (0-1)"
    )

    # Coordinate transformation
    spherical_correction: bool = Field(
        default=True,
        description="Apply spherical coordinate correction (Marshel et al. method)"
    )
    coordinate_system: str = Field(
        default="spherical",
        description="Coordinate system for stimulus generation"
    )

    # Generation quality
    bit_depth: int = Field(
        default=8,
        ge=8,
        le=16,
        description="Bit depth for stimulus frames"
    )
    compression_level: int = Field(
        default=6,
        ge=0,
        le=9,
        description="HDF5 compression level (0=none, 9=max)"
    )

    model_config = {"frozen": True}

    @property
    def params_hash(self) -> str:
        """Generate MD5 hash for parameter comparison and dataset reuse validation"""
        # Create canonical parameter dict in sorted order
        params = {
            "bar_width_degrees": self.bar_width_degrees,
            "drift_speed_degrees_per_sec": self.drift_speed_degrees_per_sec,
            "pattern_type": self.pattern_type,
            "checkerboard_size_degrees": self.checkerboard_size_degrees,
            "flicker_frequency_hz": self.flicker_frequency_hz,
            "contrast": self.contrast,
            "background_luminance": self.background_luminance,
            "spherical_correction": self.spherical_correction,
            "coordinate_system": self.coordinate_system,
            "bit_depth": self.bit_depth,
            "compression_level": self.compression_level,
        }
        canonical_json = json.dumps(params, sort_keys=True, separators=(',', ':'))
        return hashlib.md5(canonical_json.encode()).hexdigest()


class AcquisitionProtocolParams(BaseModel):
    """Acquisition protocol parameters (acquisition-time)

    These parameters control experimental execution but do not affect
    stimulus content. Changes do NOT invalidate existing stimulus datasets.
    """

    # Protocol control
    num_cycles: int = Field(
        default=10,
        gt=0,
        le=20,
        description="Number of stimulus cycles (Marshel et al.: 10 drifts per direction)"
    )
    repetitions_per_direction: int = Field(
        default=1,
        gt=0,
        le=10,
        description="Number of repetitions for each direction"
    )

    # Timing control
    frame_rate: float = Field(
        default=60.0,
        gt=1.0,
        le=120.0,
        description="Display frame rate in Hz"
    )
    inter_trial_interval_sec: float = Field(
        default=2.0,
        ge=0.0,
        le=30.0,
        description="Interval between trials in seconds"
    )
    pre_stimulus_baseline_sec: float = Field(
        default=10.0,
        ge=0.0,
        le=60.0,
        description="Baseline recording before stimulus"
    )
    post_stimulus_baseline_sec: float = Field(
        default=10.0,
        ge=0.0,
        le=60.0,
        description="Baseline recording after stimulus"
    )

    # Session management
    session_name_pattern: str = Field(
        default="ISI_Mapping_{timestamp}",
        description="Session naming pattern with placeholders"
    )
    export_formats: list[str] = Field(
        default=["hdf5", "png"],
        description="Data export formats for analysis"
    )

    # Real-time control
    buffer_size_frames: int = Field(
        default=120,
        gt=0,
        le=1000,
        description="Frame buffer size for real-time acquisition"
    )
    error_recovery_mode: str = Field(
        default="continue",
        description="Error recovery behavior (continue, pause, abort)"
    )

    model_config = {"frozen": True}


class CombinedParameters(BaseModel):
    """Combined parameter set for complete experiment configuration

    Maintains separation between generation and acquisition parameters
    while providing unified access for workflow coordination.
    """

    spatial_config: SpatialConfiguration = Field(description="Spatial/monitor configuration")
    stimulus_params: StimulusGenerationParams = Field(description="Stimulus generation parameters")
    protocol_params: AcquisitionProtocolParams = Field(description="Acquisition protocol parameters")

    # Parameter metadata
    parameter_source: ParameterSource = Field(default=ParameterSource.DEFAULT)
    created_timestamp: Optional[str] = Field(default=None)
    modified_timestamp: Optional[str] = Field(default=None)
    version: str = Field(default="1.0")

    model_config = {"frozen": True, "use_enum_values": True}

    @property
    def combined_hash(self) -> str:
        """Generate combined hash for complete parameter set validation"""
        combined = f"{self.spatial_config.config_hash}:{self.stimulus_params.params_hash}"
        return hashlib.sha256(combined.encode()).hexdigest()

    @property
    def generation_hash(self) -> str:
        """Generate hash for generation-time parameters only (for dataset reuse)"""
        combined = f"{self.spatial_config.config_hash}:{self.stimulus_params.params_hash}"
        return hashlib.sha256(combined.encode()).hexdigest()


class ParameterValidationError(Exception):
    """Raised when parameter validation fails"""
    pass


class ParameterCompatibilityError(Exception):
    """Raised when parameters are incompatible with existing datasets"""
    pass