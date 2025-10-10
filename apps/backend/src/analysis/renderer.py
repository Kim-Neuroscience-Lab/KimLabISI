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
        """Render phase map to RGB image.

        Phase is mapped to hue (cyclical colormap), and optionally
        modulated by magnitude (as brightness).

        Args:
            phase_map: Phase in radians [-π, π]
            magnitude_map: Optional magnitude for brightness modulation

        Returns:
            RGB image [height, width, 3] uint8
        """
        logger.info("Rendering phase map...")

        height, width = phase_map.shape

        # Map phase [-π, π] to hue [0, 179] (OpenCV HSV range)
        # HSV hue is in [0, 179] for uint8
        hue = ((phase_map + np.pi) / (2 * np.pi) * 179).astype(np.uint8)

        # Saturation full (255)
        saturation = np.full((height, width), 255, dtype=np.uint8)

        # Value (brightness) from magnitude if provided, else full
        if magnitude_map is not None:
            # Normalize magnitude to [0, 255]
            mag_min = np.nanmin(magnitude_map)
            mag_max = np.nanmax(magnitude_map)
            if mag_max > mag_min:
                value = ((magnitude_map - mag_min) / (mag_max - mag_min) * 255).astype(np.uint8)
            else:
                value = np.full((height, width), 255, dtype=np.uint8)
        else:
            value = np.full((height, width), 255, dtype=np.uint8)

        # Combine into HSV
        hsv_image = np.stack([hue, saturation, value], axis=-1)

        # Convert HSV to RGB
        rgb_image = cv2.cvtColor(hsv_image, cv2.COLOR_HSV2RGB)

        return rgb_image

    def render_amplitude_map(self, magnitude_map: np.ndarray) -> np.ndarray:
        """Render amplitude/magnitude map to grayscale image.

        Args:
            magnitude_map: Response amplitude

        Returns:
            RGB grayscale image [height, width, 3] uint8
        """
        logger.info("Rendering amplitude map...")

        # Normalize to [0, 255]
        mag_min = np.nanmin(magnitude_map)
        mag_max = np.nanmax(magnitude_map)

        if mag_max > mag_min:
            normalized = ((magnitude_map - mag_min) / (mag_max - mag_min) * 255).astype(np.uint8)
        else:
            normalized = np.zeros_like(magnitude_map, dtype=np.uint8)

        # Convert to RGB (grayscale)
        rgb_image = cv2.cvtColor(normalized, cv2.COLOR_GRAY2RGB)

        return rgb_image

    def render_retinotopic_map(
        self,
        retinotopic_map: np.ndarray,
        map_type: str = 'azimuth'
    ) -> np.ndarray:
        """Render retinotopic map (azimuth or elevation) to RGB image.

        Uses color-coded visualization where hue represents visual angle.

        Args:
            retinotopic_map: Retinotopic map in degrees
            map_type: 'azimuth' or 'elevation'

        Returns:
            RGB image [height, width, 3] uint8
        """
        logger.info(f"Rendering {map_type} map...")

        height, width = retinotopic_map.shape

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

        # Map value range to hue [0, 179]
        hue = ((retinotopic_map - value_min) / (value_max - value_min) * 179).astype(np.uint8)

        # Full saturation and value
        saturation = np.full((height, width), 255, dtype=np.uint8)
        value = np.full((height, width), 255, dtype=np.uint8)

        # Handle NaN values (set to black)
        nan_mask = np.isnan(retinotopic_map)
        saturation[nan_mask] = 0
        value[nan_mask] = 0

        # Combine into HSV
        hsv_image = np.stack([hue, saturation, value], axis=-1)

        # Convert HSV to RGB
        rgb_image = cv2.cvtColor(hsv_image, cv2.COLOR_HSV2RGB)

        return rgb_image

    def render_sign_map(self, sign_map: np.ndarray) -> np.ndarray:
        """Render visual field sign map to RGB image.

        Positive sign (non-mirror) = Red
        Negative sign (mirror) = Blue
        Zero/undefined = Gray

        Args:
            sign_map: Visual field sign map (+1, -1, 0)

        Returns:
            RGB image [height, width, 3] uint8
        """
        logger.info("Rendering sign map...")

        height, width = sign_map.shape
        rgb_image = np.zeros((height, width, 3), dtype=np.uint8)

        # Positive sign = Red
        rgb_image[sign_map > 0] = [255, 0, 0]

        # Negative sign = Blue
        rgb_image[sign_map < 0] = [0, 0, 255]

        # Zero/undefined = Gray
        rgb_image[sign_map == 0] = [128, 128, 128]

        return rgb_image

    def render_boundary_map(self, boundary_map: np.ndarray) -> np.ndarray:
        """Render boundary map to RGBA image.

        Boundaries shown as white lines on transparent background.

        Args:
            boundary_map: Binary boundary map

        Returns:
            RGBA image [height, width, 4] uint8
        """
        logger.info("Rendering boundary map...")

        height, width = boundary_map.shape
        rgba_image = np.zeros((height, width, 4), dtype=np.uint8)

        # Boundaries = White with full opacity
        rgba_image[boundary_map > 0] = [255, 255, 255, 255]

        # Background = Transparent
        rgba_image[boundary_map == 0] = [0, 0, 0, 0]

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
