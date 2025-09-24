"""
Pattern Generation Algorithms - Retinotopy Stimulus Patterns

This module implements algorithms for generating retinotopy mapping stimuli
including phase-encoded bars, polar coordinates, and checkerboard patterns.

Key Features:
- GPU-accelerated pattern generation using NumPy
- Support for multiple retinotopy paradigms
- Proper visual angle calculations
- Anti-aliased pattern rendering
"""

import numpy as np
import math
from typing import Tuple, Optional
from enum import Enum

from ...domain.value_objects.stimulus_params import (
    StimulusType, MovementDirection, StimulusParams, VisualFieldParams
)
from ...domain.entities.parameters import ParameterManager
from ...domain.value_objects.parameters import CombinedParameters
from .spherical_transform import SphericalTransform, create_spherical_transform_from_spatial_config


class PatternGenerator:
    """Core pattern generation engine for retinotopy stimuli"""

    def __init__(self, combined_parameters: CombinedParameters):
        """
        Initialize pattern generator with combined parameters

        Args:
            combined_parameters: Complete parameter set from parameter system
        """
        self.parameters = combined_parameters
        self.spatial_config = combined_parameters.spatial_config
        self.stimulus_params = combined_parameters.stimulus_params

        # Calculate pixels per degree from spatial configuration
        self.pixels_per_degree = self.spatial_config.pixels_per_degree

        # Create spherical transform for coordinate conversions
        self.spherical_transform = create_spherical_transform_from_spatial_config(self.spatial_config)

        # Create coordinate grids
        self._setup_coordinate_grids()

    def _setup_coordinate_grids(self):
        """Setup coordinate grids for pattern generation"""
        width = self.spatial_config.screen_width_pixels
        height = self.spatial_config.screen_height_pixels

        # Pixel coordinates
        x_pixels = np.arange(width)
        y_pixels = np.arange(height)
        self.X_pixels, self.Y_pixels = np.meshgrid(x_pixels, y_pixels)

        # Convert to degrees from center
        center_x = width / 2
        center_y = height / 2

        self.X_degrees = (self.X_pixels - center_x) / self.pixels_per_degree
        self.Y_degrees = (self.Y_pixels - center_y) / self.pixels_per_degree

        # Polar coordinates
        self.R_degrees = np.sqrt(self.X_degrees**2 + self.Y_degrees**2)
        self.Theta_radians = np.arctan2(self.Y_degrees, self.X_degrees)
        self.Theta_degrees = np.degrees(self.Theta_radians)

    def generate_frame(self, stimulus_params: StimulusParams, frame_index: int) -> np.ndarray:
        """
        Generate a single stimulus frame

        Args:
            stimulus_params: Stimulus parameters
            frame_index: Current frame index (0-based)

        Returns:
            Frame as numpy array with values 0-1
        """
        # Handle both enum objects and string values
        stimulus_type = stimulus_params.stimulus_type
        if isinstance(stimulus_type, str):
            stimulus_type = StimulusType(stimulus_type)

        if stimulus_type == StimulusType.HORIZONTAL_BAR:
            return self._generate_horizontal_bar(stimulus_params, frame_index)
        elif stimulus_type == StimulusType.VERTICAL_BAR:
            return self._generate_vertical_bar(stimulus_params, frame_index)
        elif stimulus_type == StimulusType.POLAR_WEDGE:
            return self._generate_polar_wedge(stimulus_params, frame_index)
        elif stimulus_type == StimulusType.EXPANDING_RING:
            return self._generate_expanding_ring(stimulus_params, frame_index)
        elif stimulus_type == StimulusType.CHECKERBOARD:
            return self._generate_checkerboard(stimulus_params, frame_index)
        elif stimulus_type == StimulusType.FIXATION_CROSS:
            return self._generate_fixation_cross(stimulus_params)
        else:
            raise ValueError(f"Unsupported stimulus type: {stimulus_type}")

    def _generate_horizontal_bar(self, params: StimulusParams, frame_index: int) -> np.ndarray:
        """Generate horizontal bar stimulus with spherical altitude correction (Marshel et al.)"""
        # Calculate bar position for this frame
        progress = (frame_index % params.frames_per_cycle) / params.frames_per_cycle

        # Handle both enum objects and string values
        direction = params.direction
        if isinstance(direction, str):
            direction = MovementDirection(direction)

        # Spherical coordinate transformation for altitude (horizontal bars)
        # Following Marshel et al. Supplemental Experimental Procedures
        # Horizontal bars sweep through altitude coordinates (vertical position)

        # Calculate total vertical sweep range in degrees (based on visual field)
        max_altitude = self.spatial_config.field_of_view_vertical_degrees / 2

        if direction == MovementDirection.TOP_TO_BOTTOM:
            current_altitude = max_altitude - (progress * 2 * max_altitude)
        elif direction == MovementDirection.BOTTOM_TO_TOP:
            current_altitude = -max_altitude + (progress * 2 * max_altitude)
        else:
            raise ValueError(f"Invalid direction for horizontal bar: {direction}")

        # Convert screen coordinates to spherical coordinates using dedicated transform
        _, pixel_altitude = self.spherical_transform.screen_to_spherical_coordinates(
            self.X_degrees, self.Y_degrees
        )

        # Create bar mask based on altitude coordinates
        bar_half_width = params.bar_width_degrees / 2
        bar_mask = np.abs(pixel_altitude - current_altitude) <= bar_half_width

        # Generate checkerboard pattern within bar
        frame = np.full_like(self.X_degrees, params.background_luminance)
        if np.any(bar_mask):
            checkerboard = self._generate_checkerboard_pattern(params, frame_index)
            frame[bar_mask] = checkerboard[bar_mask]

        return np.clip(frame, 0, 1)

    def _generate_vertical_bar(self, params: StimulusParams, frame_index: int) -> np.ndarray:
        """Generate vertical bar stimulus with spherical azimuth correction (Marshel et al.)"""
        # Calculate bar position for this frame
        progress = (frame_index % params.frames_per_cycle) / params.frames_per_cycle

        # Handle both enum objects and string values
        direction = params.direction
        if isinstance(direction, str):
            direction = MovementDirection(direction)

        # Spherical coordinate transformation for azimuth (vertical bars)
        # Following Marshel et al. Supplemental Experimental Procedures
        # Vertical bars sweep through azimuth coordinates (horizontal position)

        # Calculate total horizontal sweep range in degrees (based on visual field)
        max_azimuth = self.spatial_config.field_of_view_horizontal_degrees / 2

        if direction == MovementDirection.LEFT_TO_RIGHT:
            current_azimuth = -max_azimuth + (progress * 2 * max_azimuth)
        elif direction == MovementDirection.RIGHT_TO_LEFT:
            current_azimuth = max_azimuth - (progress * 2 * max_azimuth)
        else:
            raise ValueError(f"Invalid direction for vertical bar: {direction}")

        # Convert screen coordinates to spherical coordinates using dedicated transform
        pixel_azimuth, _ = self.spherical_transform.screen_to_spherical_coordinates(
            self.X_degrees, self.Y_degrees
        )

        # Create bar mask based on azimuth coordinates
        bar_half_width = params.bar_width_degrees / 2
        bar_mask = np.abs(pixel_azimuth - current_azimuth) <= bar_half_width

        # Generate checkerboard pattern within bar
        frame = np.full_like(self.X_degrees, params.background_luminance)
        if np.any(bar_mask):
            checkerboard = self._generate_checkerboard_pattern(params, frame_index)
            frame[bar_mask] = checkerboard[bar_mask]

        return np.clip(frame, 0, 1)

    def _generate_polar_wedge(self, params: StimulusParams, frame_index: int) -> np.ndarray:
        """Generate polar wedge stimulus"""
        # Calculate wedge angle for this frame
        progress = (frame_index % params.frames_per_cycle) / params.frames_per_cycle

        # Handle both enum objects and string values
        direction = params.direction
        if isinstance(direction, str):
            direction = MovementDirection(direction)

        if direction == MovementDirection.CLOCKWISE:
            wedge_center_angle = progress * 360
        elif direction == MovementDirection.COUNTERCLOCKWISE:
            wedge_center_angle = (1 - progress) * 360
        else:
            raise ValueError(f"Invalid direction for polar wedge: {direction}")

        # Create wedge mask
        wedge_half_width = params.bar_width_degrees  # Use bar_width as wedge angular width

        # Handle angle wrapping
        angle_diff = np.abs(self.Theta_degrees - wedge_center_angle)
        angle_diff = np.minimum(angle_diff, 360 - angle_diff)
        wedge_mask = angle_diff <= wedge_half_width / 2

        # Generate checkerboard pattern within wedge (full screen)
        frame = np.full_like(self.X_degrees, params.background_luminance)
        if np.any(wedge_mask):
            checkerboard = self._generate_checkerboard_pattern(params, frame_index)
            frame[wedge_mask] = checkerboard[wedge_mask]

        return np.clip(frame, 0, 1)

    def _generate_expanding_ring(self, params: StimulusParams, frame_index: int) -> np.ndarray:
        """Generate expanding/contracting ring stimulus"""
        # Calculate ring radius for this frame
        progress = (frame_index % params.frames_per_cycle) / params.frames_per_cycle
        # Use screen diagonal as max radius for full coverage
        screen_width_degrees = self.spatial_config.screen_width_pixels / self.pixels_per_degree
        screen_height_degrees = self.spatial_config.screen_height_pixels / self.pixels_per_degree
        max_radius = np.sqrt(screen_width_degrees**2 + screen_height_degrees**2) / 2

        # Handle both enum objects and string values
        direction = params.direction
        if isinstance(direction, str):
            direction = MovementDirection(direction)

        if direction == MovementDirection.EXPANDING:
            ring_radius = progress * max_radius
        elif direction == MovementDirection.CONTRACTING:
            ring_radius = (1 - progress) * max_radius
        else:
            raise ValueError(f"Invalid direction for expanding ring: {direction}")

        # Create ring mask
        ring_half_width = params.bar_width_degrees / 2
        ring_mask = np.abs(self.R_degrees - ring_radius) <= ring_half_width

        # Generate checkerboard pattern within ring (full screen)
        frame = np.full_like(self.X_degrees, params.background_luminance)
        if np.any(ring_mask):
            checkerboard = self._generate_checkerboard_pattern(params, frame_index)
            frame[ring_mask] = checkerboard[ring_mask]

        return np.clip(frame, 0, 1)

    def _generate_checkerboard_pattern(self, params: StimulusParams, frame_index: int) -> np.ndarray:
        """Generate counter-phase checkerboard pattern using parameter system"""
        # Use checkerboard size from parameter system
        checker_size_degrees = self.stimulus_params.checkerboard_size_degrees
        checker_size_pixels = checker_size_degrees * self.pixels_per_degree

        # Standard checkerboard grid in screen coordinates
        center_x = self.spatial_config.screen_width_pixels / 2
        center_y = self.spatial_config.screen_height_pixels / 2

        # Create regular grid pattern
        x_checks = ((self.X_pixels - center_x) / checker_size_pixels).astype(int)
        y_checks = ((self.Y_pixels - center_y) / checker_size_pixels).astype(int)
        checkerboard = (x_checks + y_checks) % 2

        # Counter-phase flickering using parameter system
        flicker_frequency_hz = self.stimulus_params.flicker_frequency_hz
        flicker_period_frames = int(params.frame_rate / flicker_frequency_hz)
        phase_flip = (frame_index // flicker_period_frames) % 2
        if phase_flip:
            checkerboard = 1 - checkerboard

        # Apply contrast - alternating between black and white
        pattern = np.where(checkerboard,
                          params.background_luminance + params.contrast,
                          params.background_luminance - params.contrast)

        return pattern

    def _generate_checkerboard(self, params: StimulusParams, frame_index: int) -> np.ndarray:
        """Generate full-field checkerboard stimulus"""
        # Generate full-screen checkerboard with counter-phase flickering
        checkerboard = self._generate_checkerboard_pattern(params, frame_index)
        return np.clip(checkerboard, 0, 1)

    def _generate_fixation_cross(self, params: StimulusParams) -> np.ndarray:
        """Generate fixation cross only"""
        frame = np.full_like(self.X_degrees, params.background_luminance)
        return self._add_fixation_cross(frame, params)

    def _add_fixation_cross(self, frame: np.ndarray, params: StimulusParams) -> np.ndarray:
        """Add fixation cross to existing frame"""
        cross_size_pixels = params.fixation_size_degrees * self.pixels_per_degree / 2

        # Create cross masks
        horizontal_mask = (np.abs(self.Y_degrees) <= 0.1) & (np.abs(self.X_degrees) <= params.fixation_size_degrees/2)
        vertical_mask = (np.abs(self.X_degrees) <= 0.1) & (np.abs(self.Y_degrees) <= params.fixation_size_degrees/2)

        cross_mask = horizontal_mask | vertical_mask

        # Apply fixation cross color (convert RGB to grayscale)
        fixation_luminance = 0.299 * params.fixation_color[0] + 0.587 * params.fixation_color[1] + 0.114 * params.fixation_color[2]
        frame[cross_mask] = fixation_luminance

        return frame


def create_horizontal_bar_params_from_parameter_system(parameter_set_id: str = "marshel_2011_defaults") -> StimulusParams:
    """Create horizontal bar stimulus parameters using parameter system

    Args:
        parameter_set_id: Parameter set ID to load from parameter store

    Returns:
        StimulusParams configured for horizontal bar stimulus
    """
    # Load parameters from parameter system
    pm = ParameterManager()
    combined_params = pm.get_parameters(parameter_set_id)

    # Calculate cycle duration based on field size and drift speed
    vertical_field = combined_params.spatial_config.field_of_view_vertical_degrees
    drift_speed = combined_params.stimulus_params.drift_speed_degrees_per_sec
    cycle_duration = vertical_field / drift_speed

    return StimulusParams(
        stimulus_type=StimulusType.HORIZONTAL_BAR,
        direction=MovementDirection.TOP_TO_BOTTOM,
        width_degrees=combined_params.spatial_config.field_of_view_vertical_degrees,
        height_degrees=combined_params.spatial_config.field_of_view_horizontal_degrees,
        bar_width_degrees=combined_params.stimulus_params.bar_width_degrees,
        cycle_duration_sec=cycle_duration,
        frame_rate=combined_params.protocol_params.frame_rate,
        num_cycles=combined_params.protocol_params.num_cycles,
        contrast=combined_params.stimulus_params.contrast,
        background_luminance=combined_params.stimulus_params.background_luminance,
        checkerboard_size_degrees=combined_params.stimulus_params.checkerboard_size_degrees,
        phase_steps=8,  # Phase encoding steps for analysis
        fixation_cross=False,  # No fixation during retinotopy
        fixation_size_degrees=0.5,
        fixation_color=(1.0, 0.0, 0.0)
    )


def create_vertical_bar_params_from_parameter_system(parameter_set_id: str = "marshel_2011_defaults") -> StimulusParams:
    """Create vertical bar stimulus parameters using parameter system

    Args:
        parameter_set_id: Parameter set ID to load from parameter store

    Returns:
        StimulusParams configured for vertical bar stimulus
    """
    # Load parameters from parameter system
    pm = ParameterManager()
    combined_params = pm.get_parameters(parameter_set_id)

    # Calculate cycle duration based on field size and drift speed
    horizontal_field = combined_params.spatial_config.field_of_view_horizontal_degrees
    drift_speed = combined_params.stimulus_params.drift_speed_degrees_per_sec
    cycle_duration = horizontal_field / drift_speed

    return StimulusParams(
        stimulus_type=StimulusType.VERTICAL_BAR,
        direction=MovementDirection.LEFT_TO_RIGHT,
        width_degrees=combined_params.spatial_config.field_of_view_vertical_degrees,
        height_degrees=combined_params.spatial_config.field_of_view_horizontal_degrees,
        bar_width_degrees=combined_params.stimulus_params.bar_width_degrees,
        cycle_duration_sec=cycle_duration,
        frame_rate=combined_params.protocol_params.frame_rate,
        num_cycles=combined_params.protocol_params.num_cycles,
        contrast=combined_params.stimulus_params.contrast,
        background_luminance=combined_params.stimulus_params.background_luminance,
        checkerboard_size_degrees=combined_params.stimulus_params.checkerboard_size_degrees,
        phase_steps=8,  # Phase encoding steps for analysis
        fixation_cross=False,  # No fixation during retinotopy
        fixation_size_degrees=0.5,
        fixation_color=(1.0, 0.0, 0.0)
    )


def create_polar_wedge_params_from_parameter_system(parameter_set_id: str = "marshel_2011_defaults") -> StimulusParams:
    """Create polar wedge stimulus parameters using parameter system

    Args:
        parameter_set_id: Parameter set ID to load from parameter store

    Returns:
        StimulusParams configured for polar wedge stimulus
    """
    # Load parameters from parameter system
    pm = ParameterManager()
    combined_params = pm.get_parameters(parameter_set_id)

    # Polar wedge rotates through full 360°, typically slower than bar stimuli
    # Common values: 40-60 seconds for full rotation
    cycle_duration = 40.0  # 40 seconds for full 360° rotation

    return StimulusParams(
        stimulus_type=StimulusType.POLAR_WEDGE,
        direction=MovementDirection.CLOCKWISE,
        width_degrees=combined_params.spatial_config.field_of_view_vertical_degrees,
        height_degrees=combined_params.spatial_config.field_of_view_horizontal_degrees,
        bar_width_degrees=30.0,  # 30° wedge width (standard for polar mapping)
        cycle_duration_sec=cycle_duration,
        frame_rate=combined_params.protocol_params.frame_rate,
        num_cycles=2,  # Fewer cycles due to longer duration
        contrast=combined_params.stimulus_params.contrast,
        background_luminance=combined_params.stimulus_params.background_luminance,
        checkerboard_size_degrees=combined_params.stimulus_params.checkerboard_size_degrees,
        phase_steps=8,  # Phase encoding steps for analysis
        fixation_cross=False,  # No fixation during retinotopy
        fixation_size_degrees=0.5,
        fixation_color=(1.0, 0.0, 0.0)
    )