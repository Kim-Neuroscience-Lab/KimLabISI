"""Analysis Renderer - Visualization and data formatting for analysis results.

Provides rendering functions for phase maps, magnitude maps, retinotopic maps,
and visual field sign maps. Pure visualization logic with no service dependencies.
All dependencies injected via constructor.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple
import numpy as np
import cv2

from config import AnalysisConfig
from ipc.shared_memory import SharedMemoryService

logger = logging.getLogger(__name__)


class AnalysisRenderer:
    """Renders analysis results for visualization.

    Handles colormapping, normalization, and formatting of analysis data
    for display in the frontend. All dependencies injected via constructor.
    """

    def __init__(
        self,
        config: AnalysisConfig,
        shared_memory: SharedMemoryService
    ):
        """Initialize analysis renderer.

        Args:
            config: Analysis configuration
            shared_memory: Shared memory service for frame streaming
        """
        self.config = config
        self.shared_memory = shared_memory

        logger.info("AnalysisRenderer initialized")

    def render_phase_map(
        self,
        phase_map: np.ndarray,
        magnitude_map: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """Render phase map to RGBA image.

        Phase is mapped to hue (cyclical colormap), and optionally
        modulated by magnitude (as brightness).
        NaN/masked regions are rendered as transparent.

        Args:
            phase_map: Phase in radians [-π, π]
            magnitude_map: Optional magnitude for brightness modulation

        Returns:
            RGBA image [height, width, 4] uint8 with alpha channel for transparency
        """
        logger.info("Rendering phase map with transparency for NaN...")

        # CRITICAL: Ensure C-contiguous before processing
        # Fortran-order arrays cause artifacts in HSV conversion
        if not phase_map.flags['C_CONTIGUOUS']:
            logger.info("  Phase map NOT C-contiguous, converting...")
            phase_map = np.ascontiguousarray(phase_map)

        height, width = phase_map.shape

        # Identify NaN/invalid regions for transparency
        nan_mask = np.isnan(phase_map)

        # Replace NaN with 0 for processing
        phase_clean = np.nan_to_num(phase_map, nan=0.0)

        # Map phase [-π, π] to hue [0, 179] (OpenCV HSV range)
        # HSV hue is in [0, 179] for uint8
        hue = ((phase_clean + np.pi) / (2 * np.pi) * 179).astype(np.uint8)

        # Saturation full (255)
        saturation = np.full((height, width), 255, dtype=np.uint8)

        # Value (brightness) from magnitude if provided, else full
        if magnitude_map is not None:
            # Normalize magnitude to [0, 255]
            mag_min = np.nanmin(magnitude_map)
            mag_max = np.nanmax(magnitude_map)
            if mag_max > mag_min:
                magnitude_clean = np.nan_to_num(magnitude_map, nan=0.0)
                value = ((magnitude_clean - mag_min) / (mag_max - mag_min) * 255).astype(np.uint8)
            else:
                value = np.full((height, width), 255, dtype=np.uint8)
        else:
            value = np.full((height, width), 255, dtype=np.uint8)

        # Combine into HSV
        hsv_image = np.stack([hue, saturation, value], axis=-1)

        # Convert HSV to RGB
        rgb_image = cv2.cvtColor(hsv_image, cv2.COLOR_HSV2RGB)

        # Add alpha channel
        rgba_image = np.zeros((height, width, 4), dtype=np.uint8)
        rgba_image[:, :, :3] = rgb_image
        rgba_image[:, :, 3] = 255  # Fully opaque by default

        # Make NaN/masked regions transparent
        rgba_image[nan_mask, 3] = 0

        return rgba_image

    def render_amplitude_map(self, magnitude_map: np.ndarray) -> np.ndarray:
        """Render amplitude/magnitude map with colorful colormap and transparency for NaN.

        Args:
            magnitude_map: Response amplitude

        Returns:
            RGBA image [height, width, 4] uint8 with alpha channel for transparency
        """
        logger.info("Rendering amplitude map with JET colormap...")

        height, width = magnitude_map.shape

        # Identify NaN/invalid regions for transparency
        nan_mask = np.isnan(magnitude_map)

        # Replace NaN with 0 for processing
        magnitude_clean = np.nan_to_num(magnitude_map, nan=0.0)

        # Normalize to [0, 255]
        mag_min = np.nanmin(magnitude_map)
        mag_max = np.nanmax(magnitude_map)

        if mag_max > mag_min:
            normalized = ((magnitude_clean - mag_min) / (mag_max - mag_min) * 255).astype(np.uint8)
        else:
            normalized = np.zeros_like(magnitude_clean, dtype=np.uint8)

        # Apply JET colormap (blue → cyan → green → yellow → red)
        colored_bgr = cv2.applyColorMap(normalized, cv2.COLORMAP_JET)

        # Convert BGR to RGB
        rgb_image = cv2.cvtColor(colored_bgr, cv2.COLOR_BGR2RGB)

        # Add alpha channel
        rgba_image = np.zeros((height, width, 4), dtype=np.uint8)
        rgba_image[:, :, :3] = rgb_image
        rgba_image[:, :, 3] = 255  # Fully opaque by default

        # Make NaN/masked regions transparent
        rgba_image[nan_mask, 3] = 0

        return rgba_image

    def render_retinotopic_map(
        self,
        retinotopic_map: np.ndarray,
        map_type: str = 'azimuth'
    ) -> np.ndarray:
        """Render retinotopic map (azimuth or elevation) to RGBA image.

        Uses color-coded visualization where hue represents visual angle.
        NaN/masked regions are rendered as transparent.

        Args:
            retinotopic_map: Retinotopic map in degrees
            map_type: 'azimuth' or 'elevation'

        Returns:
            RGBA image [height, width, 4] uint8 with alpha channel for transparency
        """
        logger.info(f"Rendering {map_type} map with transparency for NaN...")

        # CRITICAL: Ensure C-contiguous before processing
        # Fortran-order arrays cause artifacts in HSV conversion and stacking
        if not retinotopic_map.flags['C_CONTIGUOUS']:
            logger.info(f"  {map_type} map NOT C-contiguous, converting...")
            retinotopic_map = np.ascontiguousarray(retinotopic_map)

        height, width = retinotopic_map.shape

        # Identify NaN/invalid regions for transparency
        nan_mask = np.isnan(retinotopic_map)

        # Determine value range based on map type
        if map_type == 'azimuth':
            # Azimuth: -60° to +60°
            value_min, value_max = -60.0, 60.0
        elif map_type == 'elevation':
            # Elevation: -30° to +30°
            value_min, value_max = -30.0, 30.0
        else:
            # Auto-detect range
            value_min = np.nanmin(retinotopic_map)
            value_max = np.nanmax(retinotopic_map)

        # Replace NaN with midpoint for processing
        retinotopic_clean = np.nan_to_num(retinotopic_map, nan=(value_min + value_max) / 2.0)

        # Map value range to hue [0, 179]
        hue = ((retinotopic_clean - value_min) / (value_max - value_min) * 179).astype(np.uint8)

        # Full saturation and value
        saturation = np.full((height, width), 255, dtype=np.uint8)
        value = np.full((height, width), 255, dtype=np.uint8)

        # Combine into HSV
        hsv_image = np.stack([hue, saturation, value], axis=-1)

        # Convert HSV to RGB
        rgb_image = cv2.cvtColor(hsv_image, cv2.COLOR_HSV2RGB)

        # Add alpha channel
        rgba_image = np.zeros((height, width, 4), dtype=np.uint8)
        rgba_image[:, :, :3] = rgb_image
        rgba_image[:, :, 3] = 255  # Fully opaque by default

        # Make NaN/masked regions transparent
        rgba_image[nan_mask, 3] = 0

        return rgba_image

    def render_sign_map(self, sign_map: np.ndarray) -> np.ndarray:
        """Render visual field sign map to RGBA image.

        Uses JET colormap to visualize VFS values:
        - Negative values (mirror representation) = Blue
        - Zero = Cyan/Green
        - Positive values (non-mirror representation) = Red

        Zero values from thresholding are rendered as transparent to show
        the underlying anatomical image.

        Args:
            sign_map: Visual field sign map (raw Jacobian determinant values)

        Returns:
            RGBA image [height, width, 4] uint8 with alpha channel for transparency
        """
        logger.info("Rendering sign map with JET colormap and transparency for thresholded regions...")
        logger.info(f"  VFS range: [{np.nanmin(sign_map):.3f}, {np.nanmax(sign_map):.3f}]")

        height, width = sign_map.shape

        # CRITICAL: Ensure C-contiguous before processing
        if not sign_map.flags['C_CONTIGUOUS']:
            logger.info("  Sign map NOT C-contiguous, converting...")
            sign_map = np.ascontiguousarray(sign_map)

        # Identify thresholded/masked regions for transparency
        # The pipeline sets thresholded regions to exactly 0.0
        nan_mask = np.isnan(sign_map)
        zero_mask = (sign_map == 0.0)
        masked_regions = nan_mask | zero_mask

        logger.info(f"  Masked regions: NaN={np.sum(nan_mask)}, Zero={np.sum(zero_mask)}, Total={np.sum(masked_regions)}")

        # Replace NaN with 0 for processing
        sign_clean = np.nan_to_num(sign_map, nan=0.0)

        # Normalize to [0, 255] for colormap using symmetric range around zero
        # Find the max absolute value for symmetric colormap
        max_abs = np.max(np.abs(sign_clean[~masked_regions])) if np.any(~masked_regions) else 1.0
        if max_abs == 0:
            max_abs = 1.0

        # Map [-max_abs, +max_abs] to [0, 255] symmetrically around 127 (green/cyan)
        sign_normalized = ((sign_clean / max_abs + 1.0) / 2.0 * 255).astype(np.uint8)
        logger.info(f"  Normalized using max_abs={max_abs:.3f}")

        # Apply JET colormap (blue → cyan → green → yellow → red)
        colored_bgr = cv2.applyColorMap(sign_normalized, cv2.COLORMAP_JET)

        # Convert BGR to RGB
        rgb_image = cv2.cvtColor(colored_bgr, cv2.COLOR_BGR2RGB)

        # Add alpha channel
        rgba_image = np.zeros((height, width, 4), dtype=np.uint8)
        rgba_image[:, :, :3] = rgb_image
        rgba_image[:, :, 3] = 255  # Fully opaque by default

        # Make thresholded regions transparent (zero values from magnitude/statistical thresholding)
        rgba_image[masked_regions, 3] = 0

        return rgba_image

    def render_boundary_map(self, boundary_map: np.ndarray) -> np.ndarray:
        """Render boundary map to RGBA image.

        Boundaries shown as black lines on transparent background.

        Args:
            boundary_map: Binary boundary map

        Returns:
            RGBA image [height, width, 4] uint8
        """
        logger.info("Rendering boundary map...")

        height, width = boundary_map.shape

        # Debug: Check boundary_map statistics
        unique_values = np.unique(boundary_map)
        logger.info(f"Boundary map shape: {boundary_map.shape}, dtype: {boundary_map.dtype}")
        logger.info(f"Boundary map unique values: {unique_values}")
        logger.info(f"Boundary map range: [{np.min(boundary_map)}, {np.max(boundary_map)}]")

        # Threshold to binary if needed
        # Note: boundary_map might be inverted (0 = boundary, nonzero = non-boundary)
        # or it might be a labeled map where boundaries are between regions
        binary_boundaries = (boundary_map > 0).astype(np.uint8)

        num_nonzero_before = np.sum(binary_boundaries > 0)
        logger.info(f"Non-zero pixels: {num_nonzero_before}/{height*width} ({100*num_nonzero_before/(height*width):.1f}%)")

        # Boundary map is already processed by pipeline - use as-is
        # No need for morphological operations here (separation of concerns)
        thinned_boundaries = binary_boundaries

        # Log how many pixels are boundaries (for debugging)
        num_boundary_pixels = np.sum(thinned_boundaries > 0)
        total_pixels = height * width
        boundary_percentage = (num_boundary_pixels / total_pixels) * 100
        logger.info(f"Boundary pixels: {num_boundary_pixels}/{total_pixels} ({boundary_percentage:.1f}%)")

        # If most of the image is boundaries, the logic might be inverted
        if boundary_percentage > 50:
            logger.warning(f"More than 50% of pixels are boundaries - this seems wrong!")
            logger.warning("Boundary map might be inverted or incorrectly formatted")

        rgba_image = np.zeros((height, width, 4), dtype=np.uint8)

        # Boundaries = Black with full opacity
        rgba_image[thinned_boundaries > 0] = [0, 0, 0, 255]

        # Background = Transparent (alpha = 0)
        # Note: Already initialized to zeros above

        return rgba_image

    def render_area_map(self, area_map: np.ndarray) -> np.ndarray:
        """Render segmented area map to RGB image.

        Each area gets a distinct color. Background (label 0) is black.

        Args:
            area_map: Labeled area map (integer labels)

        Returns:
            RGB image [height, width, 3] uint8
        """
        logger.info("Rendering area map...")

        height, width = area_map.shape
        num_areas = int(np.max(area_map))

        # Generate distinct colors for each area using HSV
        rgb_image = np.zeros((height, width, 3), dtype=np.uint8)

        for label in range(1, num_areas + 1):
            # Map label to hue
            hue = int((label / num_areas) * 179)
            color = np.array([hue, 255, 255], dtype=np.uint8)

            # Convert single HSV color to RGB
            color_rgb = cv2.cvtColor(color.reshape(1, 1, 3), cv2.COLOR_HSV2RGB)[0, 0]

            # Apply color to this area
            rgb_image[area_map == label] = color_rgb

        return rgb_image

    def create_composite_view(
        self,
        azimuth_map: Optional[np.ndarray] = None,
        elevation_map: Optional[np.ndarray] = None,
        sign_map: Optional[np.ndarray] = None,
        boundary_map: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """Create composite visualization of multiple analysis layers.

        Combines azimuth, elevation, sign, and boundaries into a single image.

        Args:
            azimuth_map: Azimuth retinotopic map
            elevation_map: Elevation retinotopic map
            sign_map: Visual field sign map
            boundary_map: Area boundary map

        Returns:
            Composite RGB image [height, width, 3] uint8
        """
        logger.info("Creating composite view...")

        # Use first available map to determine size
        base_map = azimuth_map if azimuth_map is not None else elevation_map
        if base_map is None:
            base_map = sign_map if sign_map is not None else boundary_map

        if base_map is None:
            logger.warning("No maps provided for composite view")
            return np.zeros((100, 100, 3), dtype=np.uint8)

        height, width = base_map.shape

        # Start with sign map or black background
        if sign_map is not None:
            composite = self.render_sign_map(sign_map)
        else:
            composite = np.zeros((height, width, 3), dtype=np.uint8)

        # Overlay boundaries if provided
        if boundary_map is not None:
            boundary_rgba = self.render_boundary_map(boundary_map)
            # Blend boundaries onto composite
            alpha = boundary_rgba[:, :, 3:4].astype(np.float32) / 255.0
            composite = (
                composite.astype(np.float32) * (1 - alpha) +
                boundary_rgba[:, :, :3].astype(np.float32) * alpha
            ).astype(np.uint8)

        return composite

    def normalize_to_uint8(
        self,
        data: np.ndarray,
        vmin: Optional[float] = None,
        vmax: Optional[float] = None
    ) -> np.ndarray:
        """Normalize array to uint8 range [0, 255].

        Args:
            data: Input data array
            vmin: Minimum value for normalization (auto if None)
            vmax: Maximum value for normalization (auto if None)

        Returns:
            Normalized uint8 array
        """
        if vmin is None:
            vmin = np.nanmin(data)
        if vmax is None:
            vmax = np.nanmax(data)

        if vmax > vmin:
            normalized = ((data - vmin) / (vmax - vmin) * 255).astype(np.uint8)
        else:
            normalized = np.zeros_like(data, dtype=np.uint8)

        return normalized

    def apply_colormap(
        self,
        data: np.ndarray,
        colormap: int = cv2.COLORMAP_JET
    ) -> np.ndarray:
        """Apply OpenCV colormap to grayscale data.

        Args:
            data: Grayscale data [height, width]
            colormap: OpenCV colormap constant (default: JET)

        Returns:
            RGB image [height, width, 3] uint8
        """
        # Normalize to uint8
        data_uint8 = self.normalize_to_uint8(data)

        # Apply colormap
        colored = cv2.applyColorMap(data_uint8, colormap)

        # Convert BGR to RGB
        rgb_image = cv2.cvtColor(colored, cv2.COLOR_BGR2RGB)

        return rgb_image

    def prepare_for_shared_memory(
        self,
        rgb_image: np.ndarray,
        stream_name: str = "analysis_stream"
    ) -> bool:
        """Write RGB image to shared memory for frontend display.

        Args:
            rgb_image: RGB image to write [height, width, 3] uint8
            stream_name: Name of shared memory stream

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure correct format
            if rgb_image.dtype != np.uint8:
                rgb_image = rgb_image.astype(np.uint8)

            if len(rgb_image.shape) != 3 or rgb_image.shape[2] != 3:
                logger.error(f"Invalid image shape for shared memory: {rgb_image.shape}")
                return False

            # Write to shared memory
            # Note: This would use the shared_memory service's write method
            # For now, just log that we would write it
            logger.info(f"Would write {rgb_image.shape} image to shared memory: {stream_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to write to shared memory: {e}")
            return False

    def encode_as_png(self, rgb_image: np.ndarray) -> Optional[bytes]:
        """Encode RGB image as PNG bytes.

        Args:
            rgb_image: RGB image [height, width, 3] uint8

        Returns:
            PNG-encoded bytes, or None if encoding failed
        """
        try:
            # Convert RGB to BGR for OpenCV
            bgr_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)

            # Encode as PNG
            success, buffer = cv2.imencode('.png', bgr_image)

            if success:
                return buffer.tobytes()
            else:
                logger.error("PNG encoding failed")
                return None

        except Exception as e:
            logger.error(f"Failed to encode PNG: {e}")
            return None
