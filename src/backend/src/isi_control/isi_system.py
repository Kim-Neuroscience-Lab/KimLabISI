"""
ISI System - Clean Implementation with Correct Spherical Stimulus Generation
Following exact old backend pattern_generators.py approach
"""

import numpy as np
import time
import os
import json
import h5py
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from hardware_mock import MockHardware
from spherical_transform import SphericalTransform


@dataclass
class SpatialConfiguration:
    """3D spatial configuration between mouse and monitor"""

    monitor_distance_cm: float = 10.0
    monitor_angle_degrees: float = 20.0
    screen_width_pixels: int = 512  # 2560 * 0.2 for testing
    screen_height_pixels: int = 288  # 1440 * 0.2 for testing
    screen_width_cm: float = 60.96
    screen_height_cm: float = 36.195
    fps: int = 60

    @property
    def field_of_view_horizontal(self) -> float:
        """Calculate horizontal field of view from screen width and distance"""
        return 2 * np.degrees(
            np.arctan(self.screen_width_cm / (2 * self.monitor_distance_cm))
        )

    @property
    def field_of_view_vertical(self) -> float:
        """Calculate vertical field of view from screen height and distance"""
        return 2 * np.degrees(
            np.arctan(self.screen_height_cm / (2 * self.monitor_distance_cm))
        )

    @property
    def pixels_per_degree_horizontal(self) -> float:
        return self.screen_width_pixels / self.field_of_view_horizontal

    @property
    def pixels_per_degree_vertical(self) -> float:
        return self.screen_height_pixels / self.field_of_view_vertical


@dataclass
class StimulusParameters:
    """Stimulus generation parameters"""

    bar_width_degrees: float = 20.0
    drift_speed_degrees_per_sec: float = 9.0
    num_cycles: int = 10
    checkerboard_size_degrees: float = 25.0
    flicker_frequency_hz: float = 6.0
    contrast: float = 0.8
    background_luminance: float = 0.0


class ISISystem:
    """ISI System with correct spherical coordinate stimulus generation"""

    def __init__(self, use_mock_hardware: bool = True):
        self.use_mock = use_mock_hardware
        self.hardware = MockHardware() if use_mock_hardware else None
        self.spatial_config = SpatialConfiguration()
        self.stimulus_params = StimulusParameters()
        self.session_dir = None

        # Initialize spherical transform and coordinate grids
        self.spherical_transform = None
        self.X_pixels = None
        self.Y_pixels = None
        self.X_degrees = None
        self.Y_degrees = None
        self._setup_spherical_transform()
        self._setup_coordinate_grids()

        if self.use_mock:
            print("Initializing ISI System with MOCK hardware...")
            self.hardware.initialize()

    def _setup_spherical_transform(self):
        """Initialize spherical transform with spatial configuration"""
        self.spherical_transform = SphericalTransform(
            monitor_distance_cm=self.spatial_config.monitor_distance_cm,
            screen_width_cm=self.spatial_config.screen_width_cm,
            screen_height_cm=self.spatial_config.screen_height_cm,
        )

    def _setup_coordinate_grids(self):
        """Setup coordinate grids exactly like old backend pattern generator"""
        width = self.spatial_config.screen_width_pixels
        height = self.spatial_config.screen_height_pixels

        # Pixel coordinates
        x_pixels = np.arange(width)
        y_pixels = np.arange(height)
        self.X_pixels, self.Y_pixels = np.meshgrid(x_pixels, y_pixels)

        # Convert to degrees from center - exact old backend approach
        center_x = width / 2
        center_y = height / 2

        pixels_per_degree_h = self.spatial_config.pixels_per_degree_horizontal
        pixels_per_degree_v = self.spatial_config.pixels_per_degree_vertical

        self.X_degrees = (self.X_pixels - center_x) / pixels_per_degree_h
        self.Y_degrees = (self.Y_pixels - center_y) / pixels_per_degree_v

    def setup_spatial_configuration(self, config: Dict[str, Any]):
        """Update spatial configuration and reinitialize coordinate systems"""
        for key, value in config.items():
            if hasattr(self.spatial_config, key):
                setattr(self.spatial_config, key, value)

        # Reinitialize systems with new config
        self._setup_spherical_transform()
        self._setup_coordinate_grids()

        print(f"\\nSpatial configuration updated:")
        print(f"  Monitor distance: {self.spatial_config.monitor_distance_cm} cm")
        print(
            f"  Field of view: {self.spatial_config.field_of_view_horizontal}° x {self.spatial_config.field_of_view_vertical}°"
        )

    def generate_drifting_bars(
        self, direction: str
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate drifting bar stimulus following exact old backend approach
        """
        print(f"\\nGenerating {direction} drifting bar stimulus...")
        print("  Following old backend pattern_generators.py approach...")

        # Calculate the actual total sweep distance including off-screen portions
        bar_full_width = self.stimulus_params.bar_width_degrees

        if direction in ["LR", "RL"]:
            # Vertical bars - sweep through azimuth plus off-screen extensions
            fov_half = self.spatial_config.field_of_view_horizontal / 2
            total_sweep_degrees = 2 * (
                fov_half + bar_full_width
            )  # Full sweep with off-screen
        else:  # TB, BT
            # Horizontal bars - sweep through altitude plus off-screen extensions
            fov_half = self.spatial_config.field_of_view_vertical / 2
            total_sweep_degrees = 2 * (
                fov_half + bar_full_width
            )  # Full sweep with off-screen

        cycle_duration = (
            total_sweep_degrees / self.stimulus_params.drift_speed_degrees_per_sec
        )
        total_duration = cycle_duration * self.stimulus_params.num_cycles
        total_frames = int(total_duration * fps)

        print(f"  Generated {total_frames} frames, Duration: {total_duration:.1f}s")

        # Calculate angle progression - bars start/end completely off-screen
        # Need full bar width off-screen so first/last frames are all black
        bar_full_width = self.stimulus_params.bar_width_degrees

        if direction in ["LR", "RL"]:
            max_angle = self.spatial_config.field_of_view_horizontal / 2
            # Start with entire bar off-screen, end with entire bar off-screen
            start_angle = (
                (max_angle + bar_full_width)
                if direction == "LR"
                else -(max_angle + bar_full_width)
            )
            end_angle = (
                -(max_angle + bar_full_width)
                if direction == "LR"
                else (max_angle + bar_full_width)
            )
        else:  # TB, BT
            max_angle = self.spatial_config.field_of_view_vertical / 2
            # Start with entire bar off-screen, end with entire bar off-screen
            start_angle = (
                -(max_angle + bar_full_width)
                if direction == "TB"
                else (max_angle + bar_full_width)
            )
            end_angle = (
                (max_angle + bar_full_width)
                if direction == "TB"
                else -(max_angle + bar_full_width)
            )

        angles = np.linspace(start_angle, end_angle, total_frames)
        timestamps = np.arange(total_frames) * (1_000_000 // fps)

        print(f"  Angle range: {start_angle:.0f}° to {end_angle:.0f}°")

        # Generate frames using exact old backend approach
        frames = self._generate_frames_old_backend_approach(
            direction, angles, total_frames
        )

        return frames, angles, timestamps

    def _generate_frames_old_backend_approach(
        self, direction: str, angles: np.ndarray, total_frames: int
    ) -> np.ndarray:
        """Generate frames following exact old backend pattern generator approach"""
        h, w = (
            self.spatial_config.screen_height_pixels,
            self.spatial_config.screen_width_pixels,
        )
        frames = np.zeros((total_frames, h, w), dtype=np.uint8)

        # Convert screen coordinates to spherical coordinates using dedicated transform
        # This is the key step from the old backend
        pixel_azimuth, pixel_altitude = (
            self.spherical_transform.screen_to_spherical_coordinates(
                self.X_degrees, self.Y_degrees, self.spatial_config
            )
        )

        print(f"  Spherical coordinate ranges:")
        print(f"    Azimuth: {pixel_azimuth.min():.1f}° to {pixel_azimuth.max():.1f}°")
        print(
            f"    Altitude: {pixel_altitude.min():.1f}° to {pixel_altitude.max():.1f}°"
        )

        for i, current_angle in enumerate(angles):
            # Start with background
            frame = np.full(
                (h, w), self.stimulus_params.background_luminance, dtype=np.float32
            )

            # Create bar mask based on spherical coordinates - exact old backend approach
            if direction in ["LR", "RL"]:
                # Vertical bar moving horizontally - use azimuth coordinates (old backend approach)
                coordinate_map = pixel_azimuth
            else:  # TB, BT
                # Horizontal bar moving vertically - use altitude coordinates (old backend approach)
                coordinate_map = pixel_altitude

            # Create bar mask in spherical space
            bar_half_width = self.stimulus_params.bar_width_degrees / 2
            bar_mask = np.abs(coordinate_map - current_angle) <= bar_half_width

            # Generate checkerboard pattern within bar - exact old backend approach
            if np.any(bar_mask):
                checkerboard = self._generate_checkerboard_pattern_old_backend(w, h, i)
                frame[bar_mask] = checkerboard[bar_mask]

            # Convert to uint8
            frames[i] = np.clip(frame * 255, 0, 255).astype(np.uint8)

        return frames

    def _generate_checkerboard_pattern_old_backend(
        self, w: int, h: int, frame_index: int
    ) -> np.ndarray:
        """
        Generate counter-phase checkerboard pattern in spherical coordinates
        Both bar AND checkerboard must be transformed to spherical space
        """
        # Get spherical coordinates for checkerboard pattern
        pixel_azimuth, pixel_altitude = (
            self.spherical_transform.screen_to_spherical_coordinates(
                self.X_degrees, self.Y_degrees, self.spatial_config
            )
        )

        # Use checkerboard size in degrees directly in spherical space
        checker_size_degrees = self.stimulus_params.checkerboard_size_degrees

        # Create checkerboard pattern in spherical coordinates
        # This is the key fix - use spherical coordinates instead of pixel coordinates
        azimuth_checks = (pixel_azimuth / checker_size_degrees).astype(int)
        altitude_checks = (pixel_altitude / checker_size_degrees).astype(int)
        checkerboard = (azimuth_checks + altitude_checks) % 2

        # Counter-phase flickering using parameter system - old backend approach
        fps = 60
        flicker_frequency_hz = self.stimulus_params.flicker_frequency_hz
        flicker_period_frames = int(fps / flicker_frequency_hz)
        phase_flip = (frame_index // flicker_period_frames) % 2
        if phase_flip:
            checkerboard = 1 - checkerboard

        # Apply contrast - alternating between black and white - old backend approach
        pattern = np.where(
            checkerboard,
            self.stimulus_params.background_luminance + self.stimulus_params.contrast,
            self.stimulus_params.background_luminance - self.stimulus_params.contrast,
        )

        return np.clip(pattern, 0, 1)

    # Basic session management
    def start_session(self, session_name: str):
        """Start a new session"""
        self.session_dir = os.path.join("sessions", session_name)
        os.makedirs(self.session_dir, exist_ok=True)
        print(f"Session started: {session_name}")

    def stop_session(self):
        """Stop current session"""
        if self.session_dir:
            print(f"Session stopped")
            self.session_dir = None
