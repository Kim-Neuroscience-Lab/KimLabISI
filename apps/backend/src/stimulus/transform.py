"""Spherical coordinate transformation utilities.

Implements exact Marshel et al. 2011 methodology for converting screen coordinates
to spherical coordinates used in retinotopy experiments. Uses PyTorch tensors for
GPU acceleration.

Pure functions with no external dependencies - already KISS compliant!
"""

import torch
from typing import Tuple


class SphericalTransform:
    """Spherical coordinate transformation for retinotopy stimuli.

    Implements exact Marshel et al. equations using PyTorch for GPU acceleration.
    """

    def __init__(
        self,
        monitor_distance_cm: float,
        screen_width_cm: float,
        screen_height_cm: float
    ):
        """Initialize spherical transform with monitor geometry.

        Args:
            monitor_distance_cm: Distance from mouse to monitor
            screen_width_cm: Physical width of screen
            screen_height_cm: Physical height of screen
        """
        self.monitor_distance_cm = monitor_distance_cm
        self.screen_width_cm = screen_width_cm
        self.screen_height_cm = screen_height_cm

    def screen_to_spherical_coordinates(
        self,
        X_degrees: torch.Tensor,
        Y_degrees: torch.Tensor,
        spatial_config=None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Convert screen degree coordinates to spherical coordinates (GPU-accelerated).

        Following exact Marshel et al. SI equations from page 16

        Args:
            X_degrees: Horizontal position in degrees from screen center (PyTorch tensor)
            Y_degrees: Vertical position in degrees from screen center (PyTorch tensor)
            spatial_config: Optional spatial configuration for proper scaling

        Returns:
            Tuple of (azimuth_deg, altitude_deg) as PyTorch tensors
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

        # Calculate distance (r) - all GPU operations
        r = torch.sqrt(x0**2 + y**2 + z**2)

        # Apply exact Marshel equations from SI page 16
        # φ = tan⁻¹(-y/x₀) - azimuth angle (with negative y for mouse convention)
        azimuth = torch.atan2(-y, torch.full_like(y, x0))

        # θ = π/2 - cos⁻¹(z/√(x₀² + y² + z²)) - altitude angle
        altitude = torch.pi/2 - torch.acos(z / r)

        # Convert to degrees
        azimuth_deg = torch.rad2deg(azimuth)
        altitude_deg = torch.rad2deg(altitude)

        return azimuth_deg, altitude_deg
