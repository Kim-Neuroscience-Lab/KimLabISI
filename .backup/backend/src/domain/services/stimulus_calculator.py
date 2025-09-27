"""
Stimulus Calculator Domain Service for ISI Macroscope System

Generates drifting bar stimulus patterns based on Marshel et al. 2011 specification.
Focuses purely on spatial pattern generation - no timing or acquisition concerns.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional
import numpy as np

from application.algorithms.spherical_transform import (
    SphericalTransform,
    create_spherical_transform_from_spatial_config,
)


class StimulusDirection(Enum):
    """Stimulus movement directions for drifting bars"""

    LEFT_TO_RIGHT = "LR"
    RIGHT_TO_LEFT = "RL"
    TOP_TO_BOTTOM = "TB"
    BOTTOM_TO_TOP = "BT"


class StimulusPattern:
    """Spatial pattern data for drifting bar stimulus"""

    def __init__(
        self,
        pattern: np.ndarray,
        bar_position: float,
        direction: StimulusDirection,
    ):
        self.pattern = pattern
        self.bar_position = bar_position
        self.direction = direction

    def __repr__(self) -> str:
        return (
            f"StimulusPattern(shape={self.pattern.shape}, "
            f"pos={self.bar_position:.1f}deg, dir={self.direction.value})"
        )


class StimulusCalculator:
    """
    Domain service for calculating drifting bar stimulus patterns

    Generates spatial patterns for retinotopic mapping stimuli following
    Marshel et al. 2011 ISI methodology. Only handles spatial pattern generation,
    not timing or acquisition sequencing.
    """

    def __init__(self):
        """Initialize stimulus calculator"""
        self.spherical_transform: Optional[SphericalTransform] = None

    def generate_drifting_bar_pattern(
        self,
        bar_position_degrees: float,
        direction: StimulusDirection,
        spatial_config: dict,
        stimulus_params: dict,
        flicker_phase: float = 0.0,
    ) -> StimulusPattern:
        """
        Generate drifting bar pattern at specified position

        Args:
            bar_position_degrees: Position of bar center in degrees
            direction: Direction of bar movement
            spatial_config: Spatial configuration parameters
            stimulus_params: Stimulus generation parameters
            flicker_phase: Phase for counter-phase checkerboard (0-1)

        Returns:
            StimulusPattern with spatial pattern array
        """
        # Initialize spherical transform if needed
        if self.spherical_transform is None:
            self.spherical_transform = create_spherical_transform_from_spatial_config(
                spatial_config
            )

        # Calculate screen dimensions
        screen_width_px = spatial_config["screen_width_pixels"]
        screen_height_px = spatial_config["screen_height_pixels"]

        # Create coordinate grids
        x_pixels, y_pixels = np.meshgrid(
            np.arange(screen_width_px), np.arange(screen_height_px), indexing="xy"
        )

        # Apply Marshel spherical correction based on direction
        correction_type = (
            "azimuth"
            if direction in [StimulusDirection.LEFT_TO_RIGHT, StimulusDirection.RIGHT_TO_LEFT]
            else "altitude"
        )

        azimuth, altitude = self.spherical_transform.apply_marshel_spherical_correction(
            x_pixels, y_pixels, screen_width_px, screen_height_px, correction_type
        )

        # Generate bar mask based on direction
        bar_mask = self._generate_bar_mask(
            azimuth, altitude, bar_position_degrees, direction, stimulus_params
        )

        # Apply counter-phase checkerboard pattern
        pattern = self._apply_checkerboard_pattern(
            bar_mask, azimuth, altitude, stimulus_params, flicker_phase
        )

        # Apply contrast and background luminance
        pattern = self._apply_luminance_contrast(pattern, stimulus_params)

        return StimulusPattern(pattern, bar_position_degrees, direction)

    def _generate_bar_mask(
        self,
        azimuth: np.ndarray,
        altitude: np.ndarray,
        bar_position_degrees: float,
        direction: StimulusDirection,
        stimulus_params: dict,
    ) -> np.ndarray:
        """Generate bar mask for specified direction and position"""
        bar_width_deg = stimulus_params["bar_width_degrees"]
        half_width = bar_width_deg / 2

        if direction in [StimulusDirection.LEFT_TO_RIGHT, StimulusDirection.RIGHT_TO_LEFT]:
            # Horizontal bar movement - use azimuth coordinate
            bar_mask = np.abs(azimuth - bar_position_degrees) <= half_width
        else:
            # Vertical bar movement - use altitude coordinate
            bar_mask = np.abs(altitude - bar_position_degrees) <= half_width

        return bar_mask

    def _apply_checkerboard_pattern(
        self,
        bar_mask: np.ndarray,
        azimuth: np.ndarray,
        altitude: np.ndarray,
        stimulus_params: dict,
        flicker_phase: float,
    ) -> np.ndarray:
        """Apply counter-phase checkerboard pattern to bar"""
        checkerboard_size_deg = stimulus_params["checkerboard_size_degrees"]

        # Create checkerboard pattern
        checker_x = np.floor(azimuth / checkerboard_size_deg)
        checker_y = np.floor(altitude / checkerboard_size_deg)
        checkerboard = (checker_x + checker_y) % 2

        # Apply flicker phase (counter-phase)
        if flicker_phase >= 0.5:
            checkerboard = 1 - checkerboard

        # Apply checkerboard only within bar mask
        pattern = np.zeros_like(bar_mask, dtype=float)
        pattern[bar_mask] = checkerboard[bar_mask]

        return pattern

    def _apply_luminance_contrast(self, pattern: np.ndarray, stimulus_params: dict) -> np.ndarray:
        """Apply contrast and background luminance to pattern"""
        contrast = stimulus_params["contrast"]
        background_luminance = stimulus_params["background_luminance"]

        # Scale pattern from 0-1 to contrast range around background
        scaled_pattern = background_luminance + (pattern - 0.5) * contrast

        # Clip to valid luminance range
        scaled_pattern = np.clip(scaled_pattern, 0.0, 1.0)

        return scaled_pattern

    def calculate_bar_positions_for_sweep(
        self,
        direction: StimulusDirection,
        spatial_config: dict,
        bar_width_degrees: float = 0.0,
        stimulus_params: Optional[dict] = None,
        num_positions: Optional[int] = None,
    ) -> np.ndarray:
        """
        Calculate bar positions for complete sweep across visual field

        Positions are extended beyond the field of view by half the bar width
        on each side so the stimulus starts and ends with an empty screen.

        Args:
            direction: Direction of bar movement
            spatial_config: Spatial configuration parameters
            bar_width_degrees: Width of the bar in degrees (for proper start/end positioning)
            stimulus_params: Stimulus parameters
            (if provided, calculates positions based on drift speed)
            num_positions: Number of positions in sweep (optional, calculated from drift speed if not provided)

        Returns:
            Array of bar positions in degrees
        """
        # Calculate field of view based on screen size and distance
        if direction in [StimulusDirection.LEFT_TO_RIGHT, StimulusDirection.RIGHT_TO_LEFT]:
            # Horizontal sweep - use screen width
            screen_size_cm = spatial_config["screen_width_cm"]
        else:
            # Vertical sweep - use screen height
            screen_size_cm = spatial_config["screen_height_cm"]

        monitor_distance_cm = spatial_config["monitor_distance_cm"]
        field_of_view_rad = 2 * np.arctan(screen_size_cm / (2 * monitor_distance_cm))
        field_of_view_deg = np.degrees(field_of_view_rad)

        # Extend positions beyond field of view by half bar width on each side
        # This ensures the stimulus starts and ends with an empty screen
        half_bar_width = bar_width_degrees / 2
        start_pos = -field_of_view_deg / 2 - half_bar_width
        end_pos = field_of_view_deg / 2 + half_bar_width

        # Adjust for direction
        if direction in [StimulusDirection.RIGHT_TO_LEFT, StimulusDirection.BOTTOM_TO_TOP]:
            start_pos, end_pos = end_pos, start_pos

        # Calculate positions based on drift speed if stimulus params provided
        if (
            stimulus_params
            and "drift_speed_degrees_per_sec" in stimulus_params
            and "frame_rate_fps" in stimulus_params
        ):
            # Use drift speed for time-based positioning
            drift_speed_degrees_per_sec = stimulus_params["drift_speed_degrees_per_sec"]
            fps = stimulus_params["frame_rate_fps"]
            time_step_sec = 1.0 / fps

            if num_positions is None:
                # Calculate number of positions needed for complete sweep based on drift speed
                total_sweep_distance = abs(end_pos - start_pos)
                sweep_duration_sec = total_sweep_distance / drift_speed_degrees_per_sec
                num_positions = int(sweep_duration_sec * fps) + 1  # +1 to include final position

            times = np.arange(num_positions) * time_step_sec
            if direction in [StimulusDirection.RIGHT_TO_LEFT, StimulusDirection.BOTTOM_TO_TOP]:
                # Reverse direction
                positions = start_pos - times * drift_speed_degrees_per_sec
            else:
                # Forward direction
                positions = start_pos + times * drift_speed_degrees_per_sec
        else:
            # Linear spacing (legacy behavior) - requires num_positions
            if num_positions is None:
                raise ValueError(
                    "num_positions must be provided when stimulus_params are not given"
                )
            positions = np.linspace(start_pos, end_pos, num_positions)

        return positions

    def get_supported_directions(self) -> list[StimulusDirection]:
        """Get list of supported stimulus directions"""
        return list(StimulusDirection)
