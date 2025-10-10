"""Stimulus generation package.

Provides GPU-accelerated stimulus generation with spherical coordinate transformations
for retinotopy experiments. Uses PyTorch for efficient GPU operations.

Exports:
    StimulusGenerator: Main stimulus generator class
    SphericalTransform: Spherical coordinate transformation utilities
"""

from .generator import StimulusGenerator
from .transform import SphericalTransform

__all__ = ["StimulusGenerator", "SphericalTransform"]
