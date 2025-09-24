"""
Spherical Coordinate Transformation Algorithms

This module implements spherical coordinate transformations for retinotopy
stimulus generation, based on Marshel et al. 2011 methodology.

Key Functions:
- Screen pixel coordinates to spherical visual angle coordinates
- Altitude and azimuth calculations for proper stimulus positioning
- Visual angle correction for non-planar stimuli
"""

import numpy as np
from typing import Tuple, Optional
import math


class SphericalTransform:
    """
    Spherical coordinate transformation for retinotopy stimuli

    Converts screen pixel coordinates to spherical visual angle coordinates
    following the Marshel et al. 2011 methodology for retinotopy mapping.
    """

    def __init__(self, screen_distance_cm: float, pixels_per_degree: float):
        """
        Initialize spherical transform

        Args:
            screen_distance_cm: Distance from eye to screen in centimeters
            pixels_per_degree: Pixels per degree of visual angle
        """
        self.screen_distance_cm = screen_distance_cm
        self.pixels_per_degree = pixels_per_degree

    def screen_to_spherical_coordinates(self,
                                     x_degrees: np.ndarray,
                                     y_degrees: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convert screen coordinates (in visual degrees) to spherical coordinates

        Args:
            x_degrees: X coordinates in degrees of visual angle
            y_degrees: Y coordinates in degrees of visual angle

        Returns:
            Tuple of (azimuth, altitude) in degrees
        """
        # Calculate distance from center in visual angle
        r_visual_angle = np.sqrt(x_degrees**2 + y_degrees**2)

        # Calculate azimuth (horizontal angle from center)
        azimuth = self._calculate_azimuth(x_degrees, y_degrees, r_visual_angle)

        # Calculate altitude (vertical angle from horizontal plane)
        altitude = self._calculate_altitude(x_degrees, y_degrees, r_visual_angle)

        return azimuth, altitude

    def _calculate_azimuth(self,
                          x_degrees: np.ndarray,
                          y_degrees: np.ndarray,
                          r_visual_angle: np.ndarray) -> np.ndarray:
        """
        Calculate spherical azimuth coordinate

        Azimuth is the angle left/right from the center line.
        Uses spherical projection to account for screen curvature effects.

        Args:
            x_degrees: X coordinates in degrees of visual angle
            y_degrees: Y coordinates in degrees of visual angle
            r_visual_angle: Distance from center in visual angle

        Returns:
            Azimuth angles in degrees
        """
        # Spherical azimuth calculation
        # For points far from center, use proper spherical projection
        pixel_azimuth = np.degrees(
            np.arctan2(x_degrees, np.sqrt(y_degrees**2 + self.screen_distance_cm**2))
        )

        # For pixels near screen center (< 0.1 degrees), use linear approximation
        # This avoids numerical instabilities at the center
        pixel_azimuth = np.where(r_visual_angle > 0.1, pixel_azimuth, x_degrees)

        return pixel_azimuth

    def _calculate_altitude(self,
                           x_degrees: np.ndarray,
                           y_degrees: np.ndarray,
                           r_visual_angle: np.ndarray) -> np.ndarray:
        """
        Calculate spherical altitude coordinate

        Altitude is the angle above/below the horizontal plane.
        Uses spherical projection to account for screen curvature effects.

        Args:
            x_degrees: X coordinates in degrees of visual angle
            y_degrees: Y coordinates in degrees of visual angle
            r_visual_angle: Distance from center in visual angle

        Returns:
            Altitude angles in degrees
        """
        # Spherical altitude calculation
        # For points far from center, use proper spherical projection
        pixel_altitude = np.degrees(
            np.arcsin(y_degrees / np.sqrt(x_degrees**2 + y_degrees**2 + self.screen_distance_cm**2))
        )

        # For pixels near screen center (< 0.1 degrees), use linear approximation
        # This avoids numerical instabilities at the center
        pixel_altitude = np.where(r_visual_angle > 0.1, pixel_altitude, y_degrees)

        return pixel_altitude

    def pixels_to_visual_degrees(self,
                                x_pixels: np.ndarray,
                                y_pixels: np.ndarray,
                                screen_center_x: float,
                                screen_center_y: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convert pixel coordinates to visual angle coordinates

        Args:
            x_pixels: X pixel coordinates
            y_pixels: Y pixel coordinates
            screen_center_x: Screen center X coordinate in pixels
            screen_center_y: Screen center Y coordinate in pixels

        Returns:
            Tuple of (x_degrees, y_degrees) in visual angle coordinates
        """
        # Convert to centered pixel coordinates
        x_centered = x_pixels - screen_center_x
        y_centered = y_pixels - screen_center_y

        # Convert to visual degrees
        x_degrees = x_centered / self.pixels_per_degree
        y_degrees = y_centered / self.pixels_per_degree

        return x_degrees, y_degrees

    def visual_degrees_to_pixels(self,
                                x_degrees: np.ndarray,
                                y_degrees: np.ndarray,
                                screen_center_x: float,
                                screen_center_y: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convert visual angle coordinates to pixel coordinates

        Args:
            x_degrees: X coordinates in degrees of visual angle
            y_degrees: Y coordinates in degrees of visual angle
            screen_center_x: Screen center X coordinate in pixels
            screen_center_y: Screen center Y coordinate in pixels

        Returns:
            Tuple of (x_pixels, y_pixels) in pixel coordinates
        """
        # Convert to pixels
        x_pixels = x_degrees * self.pixels_per_degree + screen_center_x
        y_pixels = y_degrees * self.pixels_per_degree + screen_center_y

        return x_pixels, y_pixels

    def calculate_visual_angle_distance(self,
                                      x1_degrees: float, y1_degrees: float,
                                      x2_degrees: float, y2_degrees: float) -> float:
        """
        Calculate the angular distance between two points in visual space

        Uses spherical trigonometry for accurate distance calculation.

        Args:
            x1_degrees, y1_degrees: First point in visual degrees
            x2_degrees, y2_degrees: Second point in visual degrees

        Returns:
            Angular distance in degrees
        """
        # Convert to radians
        x1_rad, y1_rad = math.radians(x1_degrees), math.radians(y1_degrees)
        x2_rad, y2_rad = math.radians(x2_degrees), math.radians(y2_degrees)

        # Spherical distance formula (great circle distance)
        cos_distance = (math.sin(y1_rad) * math.sin(y2_rad) +
                       math.cos(y1_rad) * math.cos(y2_rad) * math.cos(x1_rad - x2_rad))

        # Clamp to avoid numerical errors
        cos_distance = max(-1.0, min(1.0, cos_distance))

        distance_rad = math.acos(cos_distance)
        return math.degrees(distance_rad)


def create_spherical_transform_from_spatial_config(spatial_config) -> SphericalTransform:
    """
    Create SphericalTransform from spatial configuration

    Args:
        spatial_config: SpatialConfiguration object with monitor setup

    Returns:
        Configured SphericalTransform instance
    """
    return SphericalTransform(
        screen_distance_cm=spatial_config.monitor_distance_cm,
        pixels_per_degree=spatial_config.pixels_per_degree
    )


def apply_spherical_correction_to_coordinates(x_degrees: np.ndarray,
                                            y_degrees: np.ndarray,
                                            screen_distance_cm: float) -> Tuple[np.ndarray, np.ndarray]:
    """
    Apply spherical coordinate correction to flat screen coordinates

    This is a convenience function for applying Marshel et al. style
    spherical corrections to stimulus coordinates.

    Args:
        x_degrees: X coordinates in degrees of visual angle
        y_degrees: Y coordinates in degrees of visual angle
        screen_distance_cm: Distance from eye to screen

    Returns:
        Tuple of (corrected_azimuth, corrected_altitude) in degrees
    """
    transform = SphericalTransform(
        screen_distance_cm=screen_distance_cm,
        pixels_per_degree=1.0  # Not used in this calculation
    )

    return transform.screen_to_spherical_coordinates(x_degrees, y_degrees)