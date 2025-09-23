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


class PatternGenerator:
    """Core pattern generation engine for retinotopy stimuli"""

    def __init__(self, visual_field: VisualFieldParams):
        """
        Initialize pattern generator with visual field parameters

        Args:
            visual_field: Visual field setup parameters
        """
        self.visual_field = visual_field
        self.pixels_per_degree = visual_field.pixels_per_degree

        # Create coordinate grids
        self._setup_coordinate_grids()

    def _setup_coordinate_grids(self):
        """Setup coordinate grids for pattern generation"""
        width = self.visual_field.screen_width_pixels
        height = self.visual_field.screen_height_pixels

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
        max_altitude = 75.0  # degrees, approximately half of 153° vertical from paper

        if direction == MovementDirection.TOP_TO_BOTTOM:
            current_altitude = max_altitude - (progress * 2 * max_altitude)
        elif direction == MovementDirection.BOTTOM_TO_TOP:
            current_altitude = -max_altitude + (progress * 2 * max_altitude)
        else:
            raise ValueError(f"Invalid direction for horizontal bar: {direction}")

        # Convert screen coordinates to spherical coordinates
        # Eye is at origin, screen is at distance (using simplified geometry)
        screen_distance = 10.0  # cm, from paper

        # Convert pixels to visual angle properly
        r_visual_angle = np.sqrt(self.X_degrees**2 + self.Y_degrees**2)

        # Calculate altitude for each pixel (spherical coordinate)
        # Altitude is the angle above/below the horizontal plane
        pixel_altitude = np.degrees(np.arcsin(self.Y_degrees / np.sqrt(self.X_degrees**2 + self.Y_degrees**2 + screen_distance**2)))

        # For pixels at screen center, use direct Y coordinate as altitude approximation
        pixel_altitude = np.where(r_visual_angle > 0.1, pixel_altitude, self.Y_degrees)

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
        max_azimuth = 73.5  # degrees, approximately half of 147° horizontal from paper

        if direction == MovementDirection.LEFT_TO_RIGHT:
            current_azimuth = -max_azimuth + (progress * 2 * max_azimuth)
        elif direction == MovementDirection.RIGHT_TO_LEFT:
            current_azimuth = max_azimuth - (progress * 2 * max_azimuth)
        else:
            raise ValueError(f"Invalid direction for vertical bar: {direction}")

        # Convert screen coordinates to spherical coordinates
        # Eye is at origin, screen is at distance
        screen_distance = 10.0  # cm, from paper

        # Convert pixels to visual angle properly
        r_visual_angle = np.sqrt(self.X_degrees**2 + self.Y_degrees**2)

        # Calculate azimuth for each pixel (spherical coordinate)
        # Azimuth is the angle left/right from the center
        pixel_azimuth = np.degrees(np.arctan2(self.X_degrees, np.sqrt(self.Y_degrees**2 + screen_distance**2)))

        # For pixels near screen center, use direct X coordinate as azimuth approximation
        pixel_azimuth = np.where(r_visual_angle > 0.1, pixel_azimuth, self.X_degrees)

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
        screen_width_degrees = self.visual_field.screen_width_pixels / self.pixels_per_degree
        screen_height_degrees = self.visual_field.screen_height_pixels / self.pixels_per_degree
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
        """Generate counter-phase checkerboard pattern following Marshel et al."""
        # Use 25° squares with 166ms period from Marshel et al. paper
        # Converting to our coordinate system
        checker_size_degrees = 25.0  # From paper: "25° squares"
        checker_size_pixels = checker_size_degrees * self.pixels_per_degree

        # Standard checkerboard grid in screen coordinates
        center_x = self.visual_field.screen_width_pixels / 2
        center_y = self.visual_field.screen_height_pixels / 2

        # Create regular grid pattern
        x_checks = ((self.X_pixels - center_x) / checker_size_pixels).astype(int)
        y_checks = ((self.Y_pixels - center_y) / checker_size_pixels).astype(int)
        checkerboard = (x_checks + y_checks) % 2

        # Counter-phase flickering with 166ms period from paper
        # 166ms = 0.166s, so frequency = 1/0.166 = ~6 Hz
        flicker_period_frames = int(0.166 * params.frame_rate)  # 166ms in frames
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


def create_default_horizontal_bar_params(visual_field: VisualFieldParams) -> StimulusParams:
    """Create default parameters for horizontal bar stimulus following Marshel et al. 2011

    Based on Marshel et al. Supplemental Experimental Procedures:
    - Bar width: 20° wide (page 13-14)
    - Visual field: 153° vertical, 147° horizontal (page 12)
    - Counter-phase checkerboard: 25° squares with 166ms period (page 14)
    - Bar drift speed: 8.5-9.5°/s for intrinsic imaging (page 14)
    - Flicker frequency: 166ms period ≈ 6 Hz (page 14)
    """
    # Calculate cycle duration based on field size and drift speed
    # 153° vertical field / 9.0°/s = 17 seconds for full sweep
    cycle_duration = 153.0 / 9.0  # ~17 seconds per cycle

    return StimulusParams(
        stimulus_type=StimulusType.HORIZONTAL_BAR,
        direction=MovementDirection.TOP_TO_BOTTOM,
        width_degrees=153.0,  # 153° vertical from Marshel et al.
        height_degrees=147.0,  # 147° horizontal from Marshel et al.
        bar_width_degrees=20.0,  # 20° wide from Marshel et al.
        cycle_duration_sec=cycle_duration,  # Based on field size and drift speed
        frame_rate=60.0,  # Standard display frame rate
        num_cycles=10,  # 10 drifts in each direction from Marshel et al.
        contrast=0.5,  # Full contrast (black to white)
        background_luminance=0.5,  # Mid gray background
        checkerboard_size_degrees=25.0,  # 25° squares from Marshel et al.
        phase_steps=8,  # Phase encoding steps for analysis
        fixation_cross=False,  # No fixation during retinotopy
        fixation_size_degrees=0.5,
        fixation_color=(1.0, 0.0, 0.0)
    )


def create_default_vertical_bar_params(visual_field: VisualFieldParams) -> StimulusParams:
    """Create default parameters for vertical bar stimulus following Marshel et al. 2011

    Based on Marshel et al. Supplemental Experimental Procedures:
    - Bar width: 20° wide (page 13-14)
    - Visual field: 153° vertical, 147° horizontal (page 12)
    - Counter-phase checkerboard: 25° squares with 166ms period (page 14)
    - Bar drift speed: 8.5-9.5°/s for intrinsic imaging (page 14)
    - Flicker frequency: 166ms period ≈ 6 Hz (page 14)
    """
    # Calculate cycle duration based on field size and drift speed
    # 147° horizontal field / 9.0°/s = 16.3 seconds for full sweep
    cycle_duration = 147.0 / 9.0  # ~16.3 seconds per cycle

    return StimulusParams(
        stimulus_type=StimulusType.VERTICAL_BAR,
        direction=MovementDirection.LEFT_TO_RIGHT,
        width_degrees=153.0,  # 153° vertical from Marshel et al.
        height_degrees=147.0,  # 147° horizontal from Marshel et al.
        bar_width_degrees=20.0,  # 20° wide from Marshel et al.
        cycle_duration_sec=cycle_duration,  # Based on field size and drift speed
        frame_rate=60.0,  # Standard display frame rate
        num_cycles=10,  # 10 drifts in each direction from Marshel et al.
        contrast=0.5,  # Full contrast (black to white)
        background_luminance=0.5,  # Mid gray background
        checkerboard_size_degrees=25.0,  # 25° squares from Marshel et al.
        phase_steps=8,  # Phase encoding steps for analysis
        fixation_cross=False,  # No fixation during retinotopy
        fixation_size_degrees=0.5,
        fixation_color=(1.0, 0.0, 0.0)
    )


def create_default_polar_wedge_params(visual_field: VisualFieldParams) -> StimulusParams:
    """Create default parameters for polar wedge stimulus following Marshel et al. 2011

    Based on Marshel et al. Supplemental Experimental Procedures:
    - Visual field: 153° vertical, 147° horizontal (page 12)
    - Counter-phase checkerboard: 25° squares with 166ms period (page 14)
    - Wedge parameters adapted for polar angle mapping
    """
    # Polar wedge rotates through full 360°, typically slower than bar stimuli
    # Common values: 40-60 seconds for full rotation
    cycle_duration = 40.0  # 40 seconds for full 360° rotation

    return StimulusParams(
        stimulus_type=StimulusType.POLAR_WEDGE,
        direction=MovementDirection.CLOCKWISE,
        width_degrees=153.0,  # 153° vertical from Marshel et al.
        height_degrees=147.0,  # 147° horizontal from Marshel et al.
        bar_width_degrees=30.0,  # 30° wedge width (standard for polar mapping)
        cycle_duration_sec=cycle_duration,  # Full rotation duration
        frame_rate=60.0,  # Standard display frame rate
        num_cycles=2,  # Fewer cycles due to longer duration
        contrast=0.5,  # Full contrast (black to white)
        background_luminance=0.5,  # Mid gray background
        checkerboard_size_degrees=25.0,  # 25° squares from Marshel et al.
        phase_steps=8,  # Phase encoding steps for analysis
        fixation_cross=False,  # No fixation during retinotopy
        fixation_size_degrees=0.5,
        fixation_color=(1.0, 0.0, 0.0)
    )