"""
Phase Unwrapping for Retinotopic Mapping - Marshel et al. 2011 Method

This module implements the phase unwrapping method from:
Marshel et al. (2011) "Functional specialization of seven mouse
visual cortical areas" Neuron + Supplemental Methods.

Uses validated scientific packages:
- scikit-image.restoration.unwrap_phase for robust 2D phase unwrapping
- NumPy/CuPy for bidirectional analysis and coordinate generation
- Maintains exact literature algorithm fidelity
"""

import logging
import numpy as np
from typing import Dict, Optional, Tuple, Union, Any, List
from datetime import datetime

# Validated scientific packages
from skimage.restoration import unwrap_phase
import numpy.ma as ma

# Optional GPU acceleration
try:
    import cupy as cp
    CUPY_AVAILABLE = True
except ImportError:
    cp = None
    CUPY_AVAILABLE = False

logger = logging.getLogger(__name__)


class PhaseUnwrapper:
    """
    Phase unwrapping for retinotopic coordinate generation following Marshel et al. 2011

    Implements the exact bidirectional analysis method from literature
    with validated scikit-image phase unwrapping backend.
    """

    def __init__(self, use_gpu: bool = True):
        """
        Initialize phase unwrapper

        Args:
            use_gpu: Whether to use GPU acceleration if available
        """
        self.use_gpu = use_gpu and CUPY_AVAILABLE

        if self.use_gpu:
            try:
                # Test GPU availability
                cp.cuda.Device(0).use()
                logger.info("GPU acceleration enabled for phase unwrapping")
            except Exception as e:
                logger.warning(f"GPU not available, falling back to CPU: {e}")
                self.use_gpu = False

    async def unwrap_phase_maps(
        self,
        phase_map: np.ndarray,
        amplitude_map: np.ndarray,
        coherence_threshold: float = 0.3,
        apply_quality_weighting: bool = True,
        wrap_around: Tuple[bool, bool] = (False, False)
    ) -> Dict[str, Any]:
        """
        Unwrap phase maps using scikit-image + Marshel bidirectional method

        Args:
