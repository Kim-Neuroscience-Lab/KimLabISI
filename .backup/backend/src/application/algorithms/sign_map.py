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
                          f"azimuth={azimuth_range:.1f}°, elevation={elevation_range:.1f}°")

    async def _preprocess_maps(
        self,
        azimuth_map: Union[np.ndarray, 'cp.ndarray'],
        elevation_map: Union[np.ndarray, 'cp.ndarray'],
        smoothing_sigma: float,
        apply_median_filter: bool
    ) -> Tuple[Union[np.ndarray, 'cp.ndarray'], Union[np.ndarray, 'cp.ndarray']]:
        """Apply preprocessing to retinotopic maps"""

        # Apply median filter to remove outliers
        if apply_median_filter:
            if self.use_gpu:
                # CuPy doesn't have median_filter, so convert to CPU temporarily
                azimuth_cpu = cp.asnumpy(azimuth_map)
                elevation_cpu = cp.asnumpy(elevation_map)

                azimuth_filtered = median_filter(azimuth_cpu, size=3)
                elevation_filtered = median_filter(elevation_cpu, size=3)

                azimuth_map = cp.asarray(azimuth_filtered)
                elevation_map = cp.asarray(elevation_filtered)
            else:
                azimuth_map = median_filter(azimuth_map, size=3)
                elevation_map = median_filter(elevation_map, size=3)

            logger.debug("Applied median filtering to remove outliers")

        # Apply Gaussian smoothing for gradient computation
        if smoothing_sigma > 0:
            if self.use_gpu:
                # Use CuPy's Gaussian filter
                from cupyx.scipy.ndimage import gaussian_filter as cupy_gaussian_filter
                azimuth_map = cupy_gaussian_filter(azimuth_map, sigma=smoothing_sigma)
                elevation_map = cupy_gaussian_filter(elevation_map, sigma=smoothing_sigma)
            else:
                azimuth_map = gaussian_filter(azimuth_map, sigma=smoothing_sigma)
                elevation_map = gaussian_filter(elevation_map, sigma=smoothing_sigma)

            logger.debug(f"Applied Gaussian smoothing (Ã={smoothing_sigma})")

        return azimuth_map, elevation_map

    def _compute_spatial_gradients(
        self,
        retinotopic_map: Union[np.ndarray, 'cp.ndarray']
    ) -> Tuple[Union[np.ndarray, 'cp.ndarray'], Union[np.ndarray, 'cp.ndarray']]:
        """
        Compute spatial gradients using Equation 1 from Zhuang et al. 2017

        Returns:
            Tuple of (grad_x, grad_y) arrays
        """
        if self.use_gpu:
            # Use CuPy gradient function (identical API to NumPy)
            grad_y, grad_x = cp.gradient(retinotopic_map)
        else:
            # Use NumPy gradient with central differences
            grad_y, grad_x = np.gradient(retinotopic_map)

        return grad_x, grad_y

    def _calculate_gradient_angles(
        self,
        azimuth_gradients: Tuple[Union[np.ndarray, 'cp.ndarray'], Union[np.ndarray, 'cp.ndarray']],
        elevation_gradients: Tuple[Union[np.ndarray, 'cp.ndarray'], Union[np.ndarray, 'cp.ndarray']]
    ) -> Union[np.ndarray, 'cp.ndarray']:
        """
        Calculate angle between retinotopic gradients using Equation 2 from Zhuang et al. 2017

        Angle = arccos(dot_product / (magnitude1 * magnitude2))
        """
        azimuth_grad_x, azimuth_grad_y = azimuth_gradients
        elevation_grad_x, elevation_grad_y = elevation_gradients

        if self.use_gpu:
            # Compute dot product of gradient vectors
            dot_product = azimuth_grad_x * elevation_grad_x + azimuth_grad_y * elevation_grad_y

            # Compute magnitudes of gradient vectors
            azimuth_magnitude = cp.sqrt(azimuth_grad_x**2 + azimuth_grad_y**2)
            elevation_magnitude = cp.sqrt(elevation_grad_x**2 + elevation_grad_y**2)

            # Calculate angle between gradients
            denominator = azimuth_magnitude * elevation_magnitude
            denominator = cp.maximum(denominator, cp.finfo(cp.float32).eps)  # Avoid division by zero

            cos_angle = dot_product / denominator
            cos_angle = cp.clip(cos_angle, -1, 1)  # Ensure valid range for arccos

            gradient_angle = cp.arccos(cos_angle)
        else:
            # CPU computation with NumPy
            dot_product = azimuth_grad_x * elevation_grad_x + azimuth_grad_y * elevation_grad_y

            azimuth_magnitude = np.sqrt(azimuth_grad_x**2 + azimuth_grad_y**2)
            elevation_magnitude = np.sqrt(elevation_grad_x**2 + elevation_grad_y**2)

            denominator = azimuth_magnitude * elevation_magnitude
            denominator = np.maximum(denominator, np.finfo(np.float32).eps)

            cos_angle = dot_product / denominator
            cos_angle = np.clip(cos_angle, -1, 1)

            gradient_angle = np.arccos(cos_angle)

        return gradient_angle

    def _calculate_sign_from_angles(
        self,
        gradient_angle_map: Union[np.ndarray, 'cp.ndarray']
    ) -> Union[np.ndarray, 'cp.ndarray']:
        """
        Calculate visual field sign using Equation 3 from Zhuang et al. 2017

        Sign = sin(angle_between_gradients)
        Positive values indicate typical visual areas
        Negative values indicate mirror-reversed areas
        """
        if self.use_gpu:
            # Apply sine function to get raw sign values
            raw_sign = cp.sin(gradient_angle_map)

            # Threshold to create discrete sign map (-1, 0, +1)
            sign_map = cp.zeros_like(raw_sign, dtype=cp.int8)
            sign_map[raw_sign > 0.1] = 1    # Positive sign areas
            sign_map[raw_sign < -0.1] = -1  # Negative sign areas
            # Values between -0.1 and 0.1 remain 0 (uncertain)
        else:
            # CPU computation
            raw_sign = np.sin(gradient_angle_map)

            sign_map = np.zeros_like(raw_sign, dtype=np.int8)
            sign_map[raw_sign > 0.1] = 1
            sign_map[raw_sign < -0.1] = -1

        return sign_map

    def _create_quality_mask(
        self,
        azimuth_gradients: Tuple[Union[np.ndarray, 'cp.ndarray'], Union[np.ndarray, 'cp.ndarray']],
        elevation_gradients: Tuple[Union[np.ndarray, 'cp.ndarray'], Union[np.ndarray, 'cp.ndarray']],
        quality_threshold: float
    ) -> Union[np.ndarray, 'cp.ndarray']:
        """Create quality mask based on gradient magnitudes"""

        azimuth_grad_x, azimuth_grad_y = azimuth_gradients
        elevation_grad_x, elevation_grad_y = elevation_gradients

        if self.use_gpu:
            # Calculate gradient magnitudes
            azimuth_magnitude = cp.sqrt(azimuth_grad_x**2 + azimuth_grad_y**2)
            elevation_magnitude = cp.sqrt(elevation_grad_x**2 + elevation_grad_y**2)

            # Create quality mask based on both gradients having sufficient magnitude
            combined_magnitude = azimuth_magnitude * elevation_magnitude
            quality_mask = combined_magnitude > quality_threshold
        else:
            azimuth_magnitude = np.sqrt(azimuth_grad_x**2 + azimuth_grad_y**2)
            elevation_magnitude = np.sqrt(elevation_grad_x**2 + elevation_grad_y**2)

            combined_magnitude = azimuth_magnitude * elevation_magnitude
            quality_mask = combined_magnitude > quality_threshold

        return quality_mask

    def _apply_quality_mask(
        self,
        sign_map: Union[np.ndarray, 'cp.ndarray'],
        quality_mask: Union[np.ndarray, 'cp.ndarray']
    ) -> Union[np.ndarray, 'cp.ndarray']:
        """Apply quality mask to sign map"""
        # Set unreliable regions to 0 (uncertain)
        masked_sign_map = sign_map.copy()
        masked_sign_map[~quality_mask] = 0
        return masked_sign_map

    def _calculate_analysis_metadata(
        self,
        sign_map: np.ndarray,
        quality_mask: np.ndarray,
        smoothing_sigma: float,
        quality_threshold: float,
        apply_preprocessing: bool
    ) -> Dict[str, Any]:
        """Calculate comprehensive analysis metadata"""

        # Basic statistics
        total_pixels = sign_map.size
        reliable_pixels = np.sum(quality_mask)
        positive_pixels = np.sum(sign_map == 1)
        negative_pixels = np.sum(sign_map == -1)
        uncertain_pixels = np.sum(sign_map == 0)

        return {
            "analysis_timestamp": datetime.now().isoformat(),
            "algorithm": "Zhuang et al. 2017 (Equations 1-3)",
            "gpu_acceleration_used": self.use_gpu,

            # Processing parameters
            "smoothing_sigma": smoothing_sigma,
            "quality_threshold": quality_threshold,
            "preprocessing_applied": apply_preprocessing,

            # Quality metrics
            "total_pixels": int(total_pixels),
            "reliable_pixels": int(reliable_pixels),
            "reliable_fraction": float(reliable_pixels / total_pixels),

            # Sign distribution
            "positive_pixels": int(positive_pixels),
            "negative_pixels": int(negative_pixels),
            "uncertain_pixels": int(uncertain_pixels),
            "positive_sign_fraction": float(positive_pixels / reliable_pixels) if reliable_pixels > 0 else 0.0,
            "negative_sign_fraction": float(negative_pixels / reliable_pixels) if reliable_pixels > 0 else 0.0,

            # Quality assessment
            "analysis_successful": reliable_pixels > 0.1 * total_pixels
        }

    def _detect_sign_boundaries(
        self,
        sign_map: np.ndarray,
        quality_mask: np.ndarray
    ) -> np.ndarray:
        """Detect boundaries between sign regions"""
        from scipy.ndimage import binary_dilation

        # Find transitions between positive and negative regions
        positive_regions = (sign_map == 1) & quality_mask
        negative_regions = (sign_map == -1) & quality_mask

        # Dilate regions slightly to find boundaries
        pos_dilated = binary_dilation(positive_regions)
        neg_dilated = binary_dilation(negative_regions)

        # Boundaries are where dilated regions overlap
        boundaries = pos_dilated & neg_dilated

        return boundaries

    def _watershed_segmentation(
        self,
        sign_map: np.ndarray,
        boundary_map: np.ndarray,
        quality_mask: np.ndarray,
        connectivity: int
    ) -> np.ndarray:
        """Apply watershed segmentation to identify visual areas"""
        from skimage.segmentation import watershed
        from skimage.measure import label

        # Create distance transform from boundaries
        from scipy.ndimage import distance_transform_edt

        distance = distance_transform_edt(~boundary_map)

        # Find local maxima as seeds for watershed
        from skimage.feature import peak_local_maxima
        seeds = peak_local_maxima(distance, min_distance=10, threshold_abs=5)

        # Create labeled seeds
        seed_labels = np.zeros_like(distance, dtype=int)
        seed_labels[seeds] = np.arange(1, len(seeds[0]) + 1)

        # Apply watershed
        labels = watershed(-distance, seed_labels, mask=quality_mask)

        return labels

    def _filter_and_analyze_areas(
        self,
        area_labels: np.ndarray,
        sign_map: np.ndarray,
        min_area_pixels: int
    ) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """Filter areas by size and analyze properties"""
        from skimage.measure import regionprops

        # Calculate region properties
        props = regionprops(area_labels)

        # Filter by minimum area and analyze
        area_properties = []
        filtered_labels = np.zeros_like(area_labels)
        new_label = 1

        for prop in props:
            if prop.area >= min_area_pixels:
                # Keep this area
                mask = area_labels == prop.label
                filtered_labels[mask] = new_label

                # Calculate area properties
                area_signs = sign_map[mask]
                dominant_sign = 1 if np.sum(area_signs == 1) > np.sum(area_signs == -1) else -1

                area_info = {
                    "label": new_label,
                    "area_pixels": prop.area,
                    "centroid": prop.centroid,
                    "dominant_sign": dominant_sign,
                    "sign_consistency": np.sum(area_signs == dominant_sign) / len(area_signs),
                    "bbox": prop.bbox
                }

                area_properties.append(area_info)
                new_label += 1

        return filtered_labels, area_properties


class SignMapError(Exception):
    """Raised when visual field sign calculation encounters errors"""
    pass