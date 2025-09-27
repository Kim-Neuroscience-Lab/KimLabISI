"""
Visual Field Sign Calculation - Zhuang et al. 2017 Method

This module implements the exact visual field sign calculation from:
Zhuang et al. (2017) "Accurate Identification of Visual Cortical Areas
with Automated Visual Sign Calculation" Journal of Neuroscience.

Uses validated scientific packages:
- numpy.gradient for spatial gradient computation
- CuPy for optional GPU acceleration
- Maintains exact literature equation fidelity (Equations 1-3 from paper)
"""

import logging
import numpy as np
from typing import Dict, Optional, Tuple, Union, Any, List
from datetime import datetime
from scipy.ndimage import gaussian_filter, median_filter

# Optional GPU acceleration
try:
    import cupy as cp
    CUPY_AVAILABLE = True
except ImportError:
    cp = None
    CUPY_AVAILABLE = False

logger = logging.getLogger(__name__)


class SignMapCalculator:
    """
    Visual field sign calculation following Zhuang et al. 2017 method

    Implements the exact mathematical equations from the literature:
    - Equation 1: Gradient computation for azimuth and elevation maps
    - Equation 2: Angle calculation between retinotopic gradients
    - Equation 3: Sign determination using sine of gradient angle
    """

    def __init__(self, use_gpu: bool = True):
        """
        Initialize sign map calculator

        Args:
            use_gpu: Whether to use GPU acceleration if available
        """
        self.use_gpu = use_gpu and CUPY_AVAILABLE

        if self.use_gpu:
            try:
                # Test GPU availability
                cp.cuda.Device(0).use()
                logger.info("GPU acceleration enabled for visual field sign calculation")
            except Exception as e:
                logger.warning(f"GPU not available, falling back to CPU: {e}")
                self.use_gpu = False

    async def calculate_visual_field_sign(
        self,
        azimuth_map: np.ndarray,
        elevation_map: np.ndarray,
        smoothing_sigma: float = 1.0,
        apply_preprocessing: bool = True,
        quality_threshold: float = 0.1,
        apply_median_filter: bool = True
    ) -> Dict[str, Any]:
        """
        Calculate visual field sign using exact Zhuang et al. 2017 equations

        Args:
            azimuth_map: Horizontal retinotopic map in degrees
            elevation_map: Vertical retinotopic map in degrees
            smoothing_sigma: Gaussian smoothing parameter for gradient computation
            apply_preprocessing: Whether to apply preprocessing filters
            quality_threshold: Threshold for masking unreliable regions
            apply_median_filter: Whether to apply median filtering to reduce noise

        Returns:
            Dictionary containing:
            - sign_map: Visual field sign map (-1, 0, +1)
            - gradient_angle_map: Angle between gradients (intermediate result)
            - azimuth_gradients: Spatial gradients of azimuth map (grad_x, grad_y)
            - elevation_gradients: Spatial gradients of elevation map (grad_x, grad_y)
            - quality_mask: Mask for reliable sign values
            - analysis_metadata: Processing parameters and quality metrics
        """
        logger.info("Calculating visual field sign using Zhuang et al. 2017 method")

        try:
            # Validate inputs
            self._validate_inputs(azimuth_map, elevation_map)

            # Convert to GPU if requested
            if self.use_gpu:
                azimuth_proc = cp.asarray(azimuth_map, dtype=cp.float32)
                elevation_proc = cp.asarray(elevation_map, dtype=cp.float32)
                logger.debug("Processing on GPU with CuPy")
            else:
                azimuth_proc = np.asarray(azimuth_map, dtype=np.float32)
                elevation_proc = np.asarray(elevation_map, dtype=np.float32)
                logger.debug("Processing on CPU with NumPy")

            # Apply preprocessing if requested
            if apply_preprocessing:
                azimuth_proc, elevation_proc = await self._preprocess_maps(
                    azimuth_proc, elevation_proc, smoothing_sigma, apply_median_filter
                )

            # Equation 1: Compute spatial gradients (Zhuang et al. 2017)
            azimuth_gradients = self._compute_spatial_gradients(azimuth_proc)
            elevation_gradients = self._compute_spatial_gradients(elevation_proc)

            # Equation 2: Calculate angle between retinotopic gradients
            gradient_angle_map = self._calculate_gradient_angles(
                azimuth_gradients, elevation_gradients
            )

            # Equation 3: Determine visual field sign using sine function
            sign_map = self._calculate_sign_from_angles(gradient_angle_map)

            # Apply quality-based masking
            quality_mask = self._create_quality_mask(
                azimuth_gradients, elevation_gradients, quality_threshold
            )

            # Apply quality mask to sign map
            sign_map_masked = self._apply_quality_mask(sign_map, quality_mask)

            # Convert back to CPU if using GPU
            if self.use_gpu:
                sign_map_final = cp.asnumpy(sign_map_masked)
                gradient_angle_final = cp.asnumpy(gradient_angle_map)
                quality_mask_final = cp.asnumpy(quality_mask)
                azimuth_grad_final = (cp.asnumpy(azimuth_gradients[0]),
                                     cp.asnumpy(azimuth_gradients[1]))
                elevation_grad_final = (cp.asnumpy(elevation_gradients[0]),
                                       cp.asnumpy(elevation_gradients[1]))
            else:
                sign_map_final = sign_map_masked
                gradient_angle_final = gradient_angle_map
                quality_mask_final = quality_mask
                azimuth_grad_final = azimuth_gradients
                elevation_grad_final = elevation_gradients

            # Calculate analysis metadata
            analysis_metadata = self._calculate_analysis_metadata(
                sign_map_final, quality_mask_final, smoothing_sigma,
                quality_threshold, apply_preprocessing
            )

            logger.info(f"Visual field sign calculation completed. "
                       f"Reliable regions: {analysis_metadata['reliable_fraction']:.3f}, "
                       f"Positive sign fraction: {analysis_metadata['positive_sign_fraction']:.3f}")

            return {
                "sign_map": sign_map_final,
                "gradient_angle_map": gradient_angle_final,
                "azimuth_gradients": azimuth_grad_final,
                "elevation_gradients": elevation_grad_final,
                "quality_mask": quality_mask_final,
                "analysis_metadata": analysis_metadata
            }

        except Exception as e:
            logger.exception("Error in visual field sign calculation")
            raise SignMapError(f"Visual field sign calculation failed: {str(e)}")

    async def segment_visual_areas(
        self,
        sign_map: np.ndarray,
        quality_mask: np.ndarray,
        min_area_pixels: int = 100,
        connectivity: int = 8
    ) -> Dict[str, Any]:
        """
        Segment visual areas based on sign map boundaries

        Args:
            sign_map: Visual field sign map from calculate_visual_field_sign
            quality_mask: Quality mask for reliable regions
            min_area_pixels: Minimum area for valid visual area patches
            connectivity: Pixel connectivity for segmentation (4 or 8)

        Returns:
            Dictionary containing:
            - area_labels: Labeled image with area identifications
            - area_properties: Properties of each segmented area
            - boundary_map: Visual area boundary locations
            - segmentation_metadata: Processing parameters
        """
        logger.info("Segmenting visual areas based on sign reversals")

        try:
            from skimage.segmentation import watershed
            from skimage.measure import label, regionprops
            from skimage.feature import peak_local_maxima

            # Find sign boundaries (transitions between +1 and -1)
            boundary_map = self._detect_sign_boundaries(sign_map, quality_mask)

            # Watershed segmentation to identify coherent areas
            area_labels = self._watershed_segmentation(
                sign_map, boundary_map, quality_mask, connectivity
            )

            # Filter by minimum area and calculate properties
            area_labels_filtered, area_properties = self._filter_and_analyze_areas(
                area_labels, sign_map, min_area_pixels
            )

            segmentation_metadata = {
                "segmentation_timestamp": datetime.now().isoformat(),
                "min_area_pixels": min_area_pixels,
                "connectivity": connectivity,
                "total_areas_found": len(area_properties),
                "total_pixels_segmented": np.sum(area_labels_filtered > 0)
            }

            logger.info(f"Area segmentation completed: {len(area_properties)} areas identified")

            return {
                "area_labels": area_labels_filtered,
                "area_properties": area_properties,
                "boundary_map": boundary_map,
                "segmentation_metadata": segmentation_metadata
            }

        except Exception as e:
            logger.exception("Error in visual area segmentation")
            raise SignMapError(f"Visual area segmentation failed: {str(e)}")

    def _validate_inputs(self, azimuth_map: np.ndarray, elevation_map: np.ndarray):
        """Validate input retinotopic maps"""
        if azimuth_map.ndim != 2 or elevation_map.ndim != 2:
            raise ValueError("Azimuth and elevation maps must be 2D arrays")

        if azimuth_map.shape != elevation_map.shape:
            raise ValueError("Azimuth and elevation maps must have same shape")

        if not np.all(np.isfinite(azimuth_map)) or not np.all(np.isfinite(elevation_map)):
            raise ValueError("Retinotopic maps contain non-finite values")

        # Check for reasonable retinotopic values (degrees)
        azimuth_range = np.ptp(azimuth_map)
        elevation_range = np.ptp(elevation_map)

        if azimuth_range > 720 or elevation_range > 720:
            logger.warning(f"Large retinotopic range detected: "
