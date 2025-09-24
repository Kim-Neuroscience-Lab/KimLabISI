"""
Stimulus Parameters Value Object - Retinotopy Stimulus Configuration

This module defines the value objects for configuring retinotopy stimuli
including phase-encoded bars, polar wedges, and checkerboard patterns.

Domain Rules:
- Immutable parameter objects
- Validation of stimulus timing and spatial parameters
- Support for multiple retinotopy mapping paradigms
"""

from enum import Enum
from typing import Optional, Tuple
from pydantic import BaseModel, Field, field_validator


class StimulusType(Enum):
    """Types of retinotopy stimuli"""
    HORIZONTAL_BAR = "horizontal_bar"
    VERTICAL_BAR = "vertical_bar"
    POLAR_WEDGE = "polar_wedge"
    EXPANDING_RING = "expanding_ring"
    CHECKERBOARD = "checkerboard"
    FIXATION_CROSS = "fixation_cross"


class MovementDirection(Enum):
    """Direction of stimulus movement"""
    LEFT_TO_RIGHT = "left_to_right"
    RIGHT_TO_LEFT = "right_to_left"
    TOP_TO_BOTTOM = "top_to_bottom"
    BOTTOM_TO_TOP = "bottom_to_top"
    CLOCKWISE = "clockwise"
    COUNTERCLOCKWISE = "counterclockwise"
    EXPANDING = "expanding"
    CONTRACTING = "contracting"


class StimulusParams(BaseModel):
    """Parameters for retinotopy stimulus generation"""

    # Stimulus type and movement
    stimulus_type: StimulusType = Field(description="Type of retinotopy stimulus")
    direction: MovementDirection = Field(description="Direction of stimulus movement")

    # Spatial parameters (in degrees of visual angle)
    width_degrees: float = Field(gt=0, le=180, description="Stimulus width in degrees")
    height_degrees: float = Field(gt=0, le=180, description="Stimulus height in degrees")
    bar_width_degrees: float = Field(gt=0, le=45, description="Bar width in degrees")

    # Temporal parameters
    cycle_duration_sec: float = Field(gt=0, le=300, description="Duration of one complete cycle in seconds")
    frame_rate: float = Field(gt=1, le=120, description="Display frame rate in Hz")
    num_cycles: int = Field(gt=0, le=20, description="Number of stimulus cycles")

    # Visual properties
    contrast: float = Field(ge=0, le=1, description="Stimulus contrast (0-1)")
    background_luminance: float = Field(ge=0, le=1, description="Background luminance (0-1)")
    checkerboard_size_degrees: float = Field(gt=0, le=50, description="Checkerboard square size in degrees")

    # Phase encoding
    phase_steps: int = Field(gt=1, le=64, description="Number of phase steps per cycle")

    # Optional fixation cross
    fixation_cross: bool = Field(default=False, description="Show fixation cross")
    fixation_size_degrees: float = Field(gt=0, le=5, description="Fixation cross size in degrees")
    fixation_color: Tuple[float, float, float] = Field(default=(1.0, 0.0, 0.0), description="Fixation cross RGB color")

    model_config = {"use_enum_values": True, "frozen": True}

    @field_validator('phase_steps')
    @classmethod
    def validate_phase_steps(cls, v, info):
        """Ensure phase steps is reasonable for the cycle duration"""
        if info.data and 'cycle_duration_sec' in info.data and 'frame_rate' in info.data:
            frames_per_cycle = info.data['cycle_duration_sec'] * info.data['frame_rate']
            if v > frames_per_cycle:
                raise ValueError(f"Phase steps ({v}) cannot exceed frames per cycle ({frames_per_cycle})")
        return v

    @property
    def frames_per_cycle(self) -> int:
        """Calculate frames per cycle"""
        return int(self.cycle_duration_sec * self.frame_rate)

    @property
    def total_frames(self) -> int:
        """Calculate total frames for all cycles"""
        return self.frames_per_cycle * self.num_cycles

    @property
    def total_duration_sec(self) -> float:
        """Calculate total stimulus duration"""
        return self.cycle_duration_sec * self.num_cycles


class VisualFieldParams(BaseModel):
    """Parameters defining the visual field setup"""

    # Display properties
    screen_width_pixels: int = Field(gt=0, description="Screen width in pixels")
    screen_height_pixels: int = Field(gt=0, description="Screen height in pixels")
    screen_width_cm: float = Field(gt=0, description="Physical screen width in cm")
    screen_distance_cm: float = Field(gt=0, description="Distance from eye to screen in cm")

    # Field of view
    field_of_view_degrees: float = Field(gt=0, le=180, description="Total field of view in degrees")

    model_config = {"use_enum_values": True, "frozen": True}

    @property
    def pixels_per_degree(self) -> float:
        """Calculate pixels per degree of visual angle"""
        import math
        # Calculate degrees per pixel using the display geometry
        screen_width_degrees = 2 * math.degrees(math.atan(self.screen_width_cm / (2 * self.screen_distance_cm)))
        return self.screen_width_pixels / screen_width_degrees

    @property
    def degrees_per_pixel(self) -> float:
        """Calculate degrees per pixel"""
        return 1.0 / self.pixels_per_degree


class RetinotopyProtocol(BaseModel):
    """Complete retinotopy mapping protocol"""

    # Protocol identification
    protocol_name: str = Field(description="Name of the retinotopy protocol")
    description: str = Field(description="Description of the protocol")

    # Stimulus parameters
    stimulus_params: StimulusParams = Field(description="Stimulus generation parameters")
    visual_field: VisualFieldParams = Field(description="Visual field setup parameters")

    # Acquisition timing
    pre_stimulus_baseline_sec: float = Field(ge=0, description="Baseline recording before stimulus")
    post_stimulus_baseline_sec: float = Field(ge=0, description="Baseline recording after stimulus")

    model_config = {"use_enum_values": True, "frozen": True}

    @property
    def total_protocol_duration_sec(self) -> float:
        """Calculate total protocol duration including baselines"""
        return (self.pre_stimulus_baseline_sec +
                self.stimulus_params.total_duration_sec +
                self.post_stimulus_baseline_sec)