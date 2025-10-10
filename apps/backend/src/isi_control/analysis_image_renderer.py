"""
Analysis Image Renderer - Backend rendering of analysis visualizations.

This module contains all rendering logic for analysis layers, moving
business logic from frontend to backend. The frontend becomes a thin client
that simply displays pre-rendered images.

Architecture:
- All colormap application happens on backend
- All layer compositing happens on backend
- All alpha blending happens on backend
- Frontend receives PNG/JPEG images ready for display

This ensures:
- Zero business logic in frontend
- Scientific algorithms stay in backend
- Faster image display (PNG decode vs pixel manipulation)
- Better separation of concerns
"""

import numpy as np
import h5py
from pathlib import Path
from PIL import Image
import io
from typing import Dict, List, Tuple, Optional
from .logging_utils import get_logger

logger = get_logger(__name__)


def jet_colormap(value: float) -> Tuple[int, int, int]:
    """
    Apply jet colormap to normalized value.

    Ported from AnalysisViewport.tsx lines 652-674.

    Args:
        value: Normalized value in range [0, 1]

    Returns:
        RGB tuple (r, g, b) with values in range [0, 255]
    """
    v = max(0.0, min(1.0, value))

    r = 0.0
    g = 0.0
    b = 0.0

    if v < 0.125:
        b = 0.5 + v / 0.125 * 0.5
    elif v < 0.375:
        b = 1.0
        g = (v - 0.125) / 0.25
    elif v < 0.625:
        g = 1.0
        b = 1.0 - (v - 0.375) / 0.25
    elif v < 0.875:
        g = 1.0
        r = (v - 0.625) / 0.25
    else:
        r = 1.0
        g = 1.0 - (v - 0.875) / 0.125

    return (int(r * 255), int(g * 255), int(b * 255))


def hsl_to_rgb(h: float, s: float, l: float) -> Tuple[int, int, int]:
    """
    Convert HSL color to RGB.

    Ported from AnalysisViewport.tsx lines 688-711.

    Args:
        h: Hue in range [0, 1]
        s: Saturation in range [0, 1]
        l: Lightness in range [0, 1]

    Returns:
        RGB tuple (r, g, b) with values in range [0, 255]
    """
    if s == 0:
        # Achromatic (gray)
        rgb_val = int(l * 255)
        return (rgb_val, rgb_val, rgb_val)

    def hue2rgb(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1/6:
            return p + (q - p) * 6 * t
        if t < 1/2:
            return q
        if t < 2/3:
            return p + (q - p) * (2/3 - t) * 6
        return p

    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q

    r = hue2rgb(p, q, h + 1/3)
    g = hue2rgb(p, q, h)
    b = hue2rgb(p, q, h - 1/3)

    return (int(r * 255), int(g * 255), int(b * 255))


def generate_distinct_colors(count: int) -> List[Tuple[int, int, int]]:
    """
    Generate perceptually distinct colors for area labels.

    Ported from AnalysisViewport.tsx lines 677-685.

    Args:
        count: Number of distinct colors to generate

    Returns:
        List of RGB tuples
    """
    colors = []
    for i in range(count):
        hue = (i * 360 / count) % 360
        r, g, b = hsl_to_rgb(hue / 360, 0.7, 0.5)
        colors.append((r, g, b))
    return colors


def render_signal_map(
    data: np.ndarray,
    signal_type: str,
    data_min: float,
    data_max: float
) -> np.ndarray:
    """
    Render signal map with appropriate colormap.

    Ported from AnalysisViewport.tsx lines 531-583.

    Args:
        data: 2D array of signal values (height, width)
        signal_type: Type of signal ('azimuth', 'elevation', 'sign', 'magnitude', 'phase')
        data_min: Minimum data value for normalization
        data_max: Maximum data value for normalization

    Returns:
        RGB image array (height, width, 3) with dtype uint8
    """
    height, width = data.shape
    rgb_image = np.zeros((height, width, 3), dtype=np.uint8)

    if signal_type in ['azimuth', 'elevation']:
        # Jet colormap for retinotopy
        for y in range(height):
            for x in range(width):
                value = data[y, x]
                # Normalize to [0, 1] using data range
                if data_max > data_min:
                    normalized = (value - data_min) / (data_max - data_min)
                else:
                    normalized = 0.5
                r, g, b = jet_colormap(normalized)
                rgb_image[y, x] = [r, g, b]

    elif signal_type == 'sign':
        # Red/blue for sign map
        for y in range(height):
            for x in range(width):
                value = data[y, x]
                if value > 0:
                    rgb_image[y, x] = [255, 0, 0]  # Red
                elif value < 0:
                    rgb_image[y, x] = [0, 0, 255]  # Blue
                else:
                    rgb_image[y, x] = [128, 128, 128]  # Gray

    else:
        # Grayscale for magnitude/phase
        for y in range(height):
            for x in range(width):
                value = data[y, x]
                if data_max > data_min:
                    normalized = (value - data_min) / (data_max - data_min)
                else:
                    normalized = 0.5
                gray = int(normalized * 255)
                rgb_image[y, x] = [gray, gray, gray]

    logger.info(f"Rendered {signal_type} signal map: {width}x{height}")
    return rgb_image


def render_anatomical(data: np.ndarray) -> np.ndarray:
    """
    Render anatomical image (grayscale to RGB).

    Ported from AnalysisViewport.tsx lines 509-528.

    Args:
        data: 2D grayscale array (height, width) with values in range [0, 255]

    Returns:
        RGB image array (height, width, 3) with dtype uint8
    """
    height, width = data.shape
    rgb_image = np.zeros((height, width, 3), dtype=np.uint8)

    for y in range(height):
        for x in range(width):
            # Clamp to 0-255
            value = max(0, min(255, int(data[y, x])))
            rgb_image[y, x] = [value, value, value]

    logger.info(f"Rendered anatomical image: {width}x{height}")
    return rgb_image


def render_boundaries(data: np.ndarray) -> np.ndarray:
    """
    Render white boundaries on transparent background.

    Ported from AnalysisViewport.tsx lines 604-619.

    Args:
        data: 2D boundary map (height, width) where >0 indicates boundary

    Returns:
        RGBA image array (height, width, 4) with dtype uint8
    """
    height, width = data.shape
    rgba_image = np.zeros((height, width, 4), dtype=np.uint8)

    for y in range(height):
        for x in range(width):
            if data[y, x] > 0:
                # White boundary pixel
                rgba_image[y, x] = [255, 255, 255, 255]
            else:
                # Transparent background
                rgba_image[y, x] = [0, 0, 0, 0]

    logger.info(f"Rendered boundary map: {width}x{height}")
    return rgba_image


def render_area_patches(data: np.ndarray, num_areas: int) -> np.ndarray:
    """
    Render colored area patches with semi-transparent overlay.

    Ported from AnalysisViewport.tsx lines 622-649.

    Args:
        data: 2D area label map (height, width) with integer labels
        num_areas: Number of distinct areas

    Returns:
        RGBA image array (height, width, 4) with dtype uint8
    """
    height, width = data.shape
    rgba_image = np.zeros((height, width, 4), dtype=np.uint8)

    # Generate distinct colors for each area
    colors = generate_distinct_colors(num_areas)

    for y in range(height):
        for x in range(width):
            area_label = int(round(data[y, x]))

            if area_label > 0 and area_label <= num_areas:
                # Apply area color with semi-transparency
                color = colors[area_label - 1]
                rgba_image[y, x] = [color[0], color[1], color[2], 128]
            else:
                # Fully transparent for background
                rgba_image[y, x] = [0, 0, 0, 0]

    logger.info(f"Rendered area patches: {width}x{height}, {num_areas} areas")
    return rgba_image


def composite_layers(layers: List[Dict], width: int, height: int) -> np.ndarray:
    """
    Composite multiple layers with alpha blending.

    This performs the same alpha blending that was done in the frontend
    via canvas globalAlpha and putImageData operations.

    Args:
        layers: List of layer dictionaries with keys:
                - 'image': np.ndarray (RGB or RGBA)
                - 'alpha': float in range [0, 1]
        width: Output image width
        height: Output image height

    Returns:
        Final RGB image array (height, width, 3) with dtype uint8
    """
    # Start with black background
    composite = np.zeros((height, width, 3), dtype=np.float32)

    for layer in layers:
        image = layer['image']
        alpha = layer['alpha']

        if image is None:
            continue

        # Ensure image dimensions match
        if image.shape[0] != height or image.shape[1] != width:
            logger.warning(
                f"Layer size mismatch: expected {height}x{width}, "
                f"got {image.shape[0]}x{image.shape[1]}"
            )
            continue

        # Convert to float for blending
        if image.dtype != np.float32:
            image_float = image.astype(np.float32)
        else:
            image_float = image.copy()

        # Handle RGBA vs RGB
        if len(image.shape) == 3 and image.shape[2] == 4:
            # RGBA: use per-pixel alpha channel
            rgb = image_float[:, :, :3]
            pixel_alpha = image_float[:, :, 3:4] / 255.0  # Normalize to [0, 1]

            # Combine layer alpha with pixel alpha
            effective_alpha = pixel_alpha * alpha

            # Alpha blend: composite = composite * (1 - alpha) + rgb * alpha
            composite = composite * (1 - effective_alpha) + rgb * effective_alpha
        else:
            # RGB: use layer alpha only
            # Alpha blend with layer alpha
            composite = composite * (1 - alpha) + image_float * alpha

    # Clamp and convert to uint8
    composite = np.clip(composite, 0, 255).astype(np.uint8)

    logger.info(f"Composited {len(layers)} layers to {width}x{height} image")
    return composite


def generate_composite_image(
    session_path: str,
    layer_config: Dict[str, Any]
) -> bytes:
    """
    Main entry point: Generate composite analysis image.

    This is the complete backend rendering pipeline:
    1. Load requested layers from HDF5
    2. Render each layer with appropriate colormap
    3. Composite layers with specified alpha values
    4. Encode as PNG
    5. Return PNG bytes

    Args:
        session_path: Path to analysis session directory
        layer_config: Configuration dictionary with keys:
            - 'anatomical': {'visible': bool, 'alpha': float}
            - 'signal': {'visible': bool, 'type': str, 'alpha': float}
            - 'overlay': {'visible': bool, 'type': str, 'alpha': float}

    Returns:
        PNG-encoded image as bytes

    Raises:
        FileNotFoundError: If analysis results not found
        ValueError: If required layers missing
    """
    logger.info(f"Generating composite image for session: {session_path}")
    logger.debug(f"Layer configuration: {layer_config}")

    # Locate analysis results
    results_path = Path(session_path) / "analysis_results" / "analysis_results.h5"
    if not results_path.exists():
        raise FileNotFoundError(f"Analysis results not found: {results_path}")

    # Load metadata to determine image dimensions
    with h5py.File(results_path, 'r') as f:
        # Get dimensions from any available layer
        if 'azimuth_map' in f:
            shape = f['azimuth_map'].shape
        elif 'elevation_map' in f:
            shape = f['elevation_map'].shape
        else:
            raise ValueError("No valid analysis layers found")

        height, width = shape
        logger.info(f"Analysis image dimensions: {width}x{height}")

    # List to hold layers for compositing (order matters: bottom to top)
    composite_layers = []

    # Layer 1: Anatomical underlay (if visible)
    anatomical_config = layer_config.get('anatomical', {})
    if anatomical_config.get('visible', False):
        anatomical_path = Path(session_path) / "anatomical.npy"
        if anatomical_path.exists():
            logger.info("Loading anatomical layer...")
            anatomical_data = np.load(anatomical_path)
            anatomical_rgb = render_anatomical(anatomical_data)
            composite_layers.append({
                'image': anatomical_rgb,
                'alpha': anatomical_config.get('alpha', 0.5)
            })
        else:
            logger.warning("Anatomical layer requested but not found")

    # Layer 2: Signal map (if visible)
    signal_config = layer_config.get('signal', {})
    if signal_config.get('visible', False):
        signal_type = signal_config.get('type', 'azimuth')
        logger.info(f"Loading signal layer: {signal_type}")

        # Map signal type to layer name
        layer_map = {
            'azimuth': 'azimuth_map',
            'elevation': 'elevation_map',
            'sign': 'sign_map',
            'magnitude': 'magnitude_LR',
            'phase': 'phase_LR'
        }

        layer_name = layer_map.get(signal_type, 'azimuth_map')

        # Load the signal layer
        with h5py.File(results_path, 'r') as f:
            if layer_name in f:
                signal_data = f[layer_name][:]
            elif layer_name.startswith('magnitude_'):
                # Handle magnitude maps in nested group
                direction = layer_name.replace('magnitude_', '')
                if 'magnitude_maps' in f and direction in f['magnitude_maps']:
                    signal_data = f['magnitude_maps'][direction][:]
                else:
                    logger.warning(f"Signal layer not found: {layer_name}")
                    signal_data = None
            elif layer_name.startswith('phase_'):
                # Handle phase maps in nested group
                direction = layer_name.replace('phase_', '')
                if 'phase_maps' in f and direction in f['phase_maps']:
                    signal_data = f['phase_maps'][direction][:]
                else:
                    logger.warning(f"Signal layer not found: {layer_name}")
                    signal_data = None
            else:
                logger.warning(f"Signal layer not found: {layer_name}")
                signal_data = None

        if signal_data is not None:
            # Convert to float32 if needed
            if signal_data.dtype != np.float32:
                signal_data = signal_data.astype(np.float32)

            # Get data range
            data_min = float(np.nanmin(signal_data))
            data_max = float(np.nanmax(signal_data))

            # Render signal map
            signal_rgb = render_signal_map(signal_data, signal_type, data_min, data_max)
            composite_layers.append({
                'image': signal_rgb,
                'alpha': signal_config.get('alpha', 0.8)
            })

    # Layer 3: Overlay (if visible)
    overlay_config = layer_config.get('overlay', {})
    if overlay_config.get('visible', False):
        overlay_type = overlay_config.get('type', 'area_borders')
        logger.info(f"Loading overlay layer: {overlay_type}")

        if overlay_type == 'area_borders':
            # Load boundary map
            with h5py.File(results_path, 'r') as f:
                if 'boundary_map' in f:
                    boundary_data = f['boundary_map'][:]
                    boundary_rgba = render_boundaries(boundary_data)
                    composite_layers.append({
                        'image': boundary_rgba,
                        'alpha': overlay_config.get('alpha', 1.0)
                    })
                else:
                    logger.warning("Boundary map not found")

        elif overlay_type == 'area_patches':
            # Load area map
            with h5py.File(results_path, 'r') as f:
                if 'area_map' in f:
                    area_data = f['area_map'][:]
                    num_areas = int(np.max(area_data))
                    area_rgba = render_area_patches(area_data, num_areas)
                    composite_layers.append({
                        'image': area_rgba,
                        'alpha': overlay_config.get('alpha', 1.0)
                    })
                else:
                    logger.warning("Area map not found")

    # Composite all layers
    if composite_layers:
        final_image = composite_layers(composite_layers, width, height)
    else:
        # No layers visible, return black image
        logger.warning("No visible layers, returning black image")
        final_image = np.zeros((height, width, 3), dtype=np.uint8)

    # Encode as PNG
    logger.info("Encoding composite image as PNG...")
    img = Image.fromarray(final_image, mode='RGB')
    buf = io.BytesIO()
    img.save(buf, format='PNG', compress_level=6)  # Balanced compression
    png_bytes = buf.getvalue()

    logger.info(f"Generated composite image: {len(png_bytes)} bytes")
    return png_bytes
