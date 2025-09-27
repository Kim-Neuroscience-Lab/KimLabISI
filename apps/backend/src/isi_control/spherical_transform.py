"""
Minimal Spherical Coordinate Transformation
Following exact Marshel et al. 2011 methodology
"""

import numpy as np
from typing import Tuple


class SphericalTransform:
    """
    Spherical coordinate transformation for retinotopy stimuli
    Implements exact Marshel et al. equations without external dependencies
    """

    def __init__(self, monitor_distance_cm: float, screen_width_cm: float, screen_height_cm: float):
        self.monitor_distance_cm = monitor_distance_cm
        self.screen_width_cm = screen_width_cm
        self.screen_height_cm = screen_height_cm

    def screen_to_spherical_coordinates(self, X_degrees: np.ndarray, Y_degrees: np.ndarray, spatial_config=None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convert screen degree coordinates to spherical coordinates
        Following exact Marshel et al. SI equations from page 16

        Args:
            X_degrees: Horizontal position in degrees from screen center
            Y_degrees: Vertical position in degrees from screen center
            spatial_config: Optional spatial configuration for proper scaling

        Returns:
            Tuple of (azimuth_deg, altitude_deg) in degrees
        """
        # Use provided spatial config or estimate based on field of view
        if spatial_config:
            # Use actual spatial configuration
            fov_h = spatial_config.field_of_view_horizontal
            fov_v = spatial_config.field_of_view_vertical
            screen_w_cm = spatial_config.screen_width_cm
            screen_h_cm = spatial_config.screen_height_cm
        else:
            # Fall back to defaults
            fov_h, fov_v = 120.0, 90.0
            screen_w_cm, screen_h_cm = 33.6, 25.2

        # Convert degrees to cm on screen - proper scaling
        # X_degrees and Y_degrees are already in visual angle degrees
        # Convert to physical cm using field of view mapping
        y_screen_cm = X_degrees * (screen_w_cm / fov_h)  # Horizontal position on screen
        z_screen_cm = Y_degrees * (screen_h_cm / fov_v)  # Vertical position on screen

        # Create 3D Cartesian coordinates (x₀, y, z) per Marshel paper
        x0 = self.monitor_distance_cm  # Distance to screen
        y = y_screen_cm               # Horizontal screen coordinate
        z = z_screen_cm               # Vertical screen coordinate

        # Calculate distance (r)
        r = np.sqrt(x0**2 + y**2 + z**2)

        # Apply exact Marshel equations from SI page 16
        # φ = tan⁻¹(-y/x₀) - azimuth angle (with negative y for mouse convention)
        azimuth = np.arctan2(-y, x0)

        # θ = π/2 - cos⁻¹(z/√(x₀² + y² + z²)) - altitude angle
        altitude = np.pi/2 - np.arccos(z / r)

        # Convert to degrees
        azimuth_deg = np.degrees(azimuth)
        altitude_deg = np.degrees(altitude)

        return azimuth_deg, altitude_deg