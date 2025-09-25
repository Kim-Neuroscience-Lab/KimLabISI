"""
Stimulus Parameter Value Objects - Legacy Support Module

This module provides backward compatibility support for the test suite.
These enums and classes were consolidated into the main parameters.py module
but are maintained here for test compatibility.

Note: New code should use the consolidated parameter system in parameters.py
"""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class StimulusType(Enum):
    """Types of visual stimuli for retinotopy mapping"""
    HORIZONTAL_BAR = "horizontal_bar"
    VERTICAL_BAR = "vertical_bar"
    POLAR_WEDGE = "polar_wedge"
    EXPANDING_RING = "expanding_ring"
    CHECKERBOARD = "checkerboard"
    FIXATION_CROSS = "fixation_cross"


class MovementDirection(Enum):
    """Stimulus movement directions"""
    LEFT_TO_RIGHT = "left_to_right"
    RIGHT_TO_LEFT = "right_to_left"
    TOP_TO_BOTTOM = "top_to_bottom"
    BOTTOM_TO_TOP = "bottom_to_top"
    CLOCKWISE = "clockwise"
    COUNTERCLOCKWISE = "counterclockwise"
    EXPANDING = "expanding"
    CONTRACTING = "contracting"


class StimulusParams(BaseModel):
    """Legacy stimulus parameters - use StimulusGenerationParams in new code"""
    stimulus_type: StimulusType = StimulusType.HORIZONTAL_BAR
    direction: MovementDirection = MovementDirection.TOP_TO_BOTTOM
    bar_width_degrees: float = Field(default=20.0, gt=0.0, le=45.0)
    drift_speed_degrees_per_sec: float = Field(default=9.0, gt=0.0, le=50.0)
    cycle_duration_sec: float = Field(default=25.0, gt=0.0, le=300.0)
    num_cycles: int = Field(default=10, ge=1, le=50)
    frame_rate: float = Field(default=60.0, gt=0.0, le=240.0)
    contrast: float = Field(default=0.5, ge=0.0, le=1.0)
    background_luminance: float = Field(default=0.5, ge=0.0, le=1.0)
    checkerboard_size_degrees: float = Field(default=25.0, gt=0.0, le=50.0)
    flicker_frequency_hz: float = Field(default=6.0, gt=0.0, le=30.0)

    model_config = {"frozen": True}

    @property
    def total_duration_sec(self) -> float:
        """Total duration of stimulus sequence"""
        return self.cycle_duration_sec * self.num_cycles

    @property
    def total_frames(self) -> int:
        """Total number of frames in sequence"""
        return int(self.total_duration_sec * self.frame_rate)


class VisualFieldParams(BaseModel):
    """Visual field display parameters"""
    screen_width_pixels: int = Field(default=1920, gt=0)
    screen_height_pixels: int = Field(default=1080, gt=0)
    screen_width_cm: float = Field(default=50.0, gt=0.0)
    screen_distance_cm: float = Field(default=60.0, gt=0.0)
    field_of_view_degrees: float = Field(default=30.0, gt=0.0, le=180.0)

    model_config = {"frozen": True}

    @property
    def pixels_per_degree(self) -> float:
        """Calculate pixels per degree of visual angle"""
        import math
        visual_angle_rad = math.atan(self.screen_width_cm / (2 * self.screen_distance_cm)) * 2
        visual_angle_deg = math.degrees(visual_angle_rad)
        return self.screen_width_pixels / visual_angle_deg


class RetinotopyProtocol(BaseModel):
    """Complete retinotopy stimulus protocol"""
    stimulus_params: StimulusParams
    visual_field_params: VisualFieldParams
    protocol_name: str = Field(default="retinotopy_protocol")
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}

    @property
    def total_duration_sec(self) -> float:
        """Total protocol duration"""
        return self.stimulus_params.total_duration_sec

    @property
    def total_frames(self) -> int:
        """Total frames in protocol"""
        return self.stimulus_params.total_frames