"""IPC handlers for analysis operations."""

import os
from typing import Dict, Any
from .ipc_utils import ipc_handler, format_success_response, format_error_response
from .logging_utils import get_logger

logger = get_logger(__name__)

# Dedicated shared memory path for analysis layers (separate from stimulus streaming)
ANALYSIS_SHM_PATH = "/tmp/isi_macroscope_analysis_shm"
ANALYSIS_BUFFER_SIZE = 50 * 1024 * 1024  # 50MB for large analysis layers


def ensure_analysis_shm_buffer():
    """Ensure analysis shared memory buffer exists and is properly sized."""
    if not os.path.exists(ANALYSIS_SHM_PATH):
        logger.info(f"Creating analysis shared memory buffer at {ANALYSIS_SHM_PATH}")
        with open(ANALYSIS_SHM_PATH, 'wb') as f:
            f.write(b'\x00' * ANALYSIS_BUFFER_SIZE)
    else:
        # Verify size
        size = os.path.getsize(ANALYSIS_SHM_PATH)
        if size < ANALYSIS_BUFFER_SIZE:
            logger.info(f"Resizing analysis shared memory buffer from {size} to {ANALYSIS_BUFFER_SIZE}")
            with open(ANALYSIS_SHM_PATH, 'ab') as f:
                f.write(b'\x00' * (ANALYSIS_BUFFER_SIZE - size))
    logger.debug(f"Analysis shared memory buffer ready: {ANALYSIS_SHM_PATH} ({ANALYSIS_BUFFER_SIZE} bytes)")


def cleanup_analysis_shm():
    """Remove analysis shared memory file."""
    try:
        if os.path.exists(ANALYSIS_SHM_PATH):
            os.unlink(ANALYSIS_SHM_PATH)
            logger.info("Analysis shared memory buffer cleaned up")
    except Exception as e:
        logger.warning(f"Failed to cleanup analysis shm: {e}")


def _get_analysis_manager():
    """Get analysis manager from service registry."""
    from .service_locator import get_services
    services = get_services()
    return services.analysis_manager


@ipc_handler("start_analysis")
def handle_start_analysis(command: Dict[str, Any]) -> Dict[str, Any]:
    """
    Start analysis on a recorded session.

    Args:
        command: IPC command containing session_path

    Returns:
        Success response with analysis info or error
    """
    manager = _get_analysis_manager()
    if manager is None:
        return format_error_response(
            "start_analysis",
            "Analysis manager not initialized"
        )

    session_path = command.get("session_path")
    if not session_path:
        return format_error_response(
            "start_analysis",
            "session_path is required"
        )

    # Get analysis parameters from parameter manager
    from .service_locator import get_services
    services = get_services()
    param_manager = services.parameter_manager

    try:
        analysis_params = param_manager.get_parameter_group("analysis")
    except Exception as e:
        logger.warning(f"Failed to load analysis parameters: {e}, using defaults")
        analysis_params = {}

    return manager.start_analysis(session_path, analysis_params)


@ipc_handler("stop_analysis")
def handle_stop_analysis(command: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stop running analysis.

    Note: Analysis cannot be truly cancelled mid-execution, but this
    will mark it as stopped and prevent results from being processed.

    Returns:
        Success response or error
    """
    manager = _get_analysis_manager()
    if manager is None:
        return format_error_response(
            "stop_analysis",
            "Analysis manager not initialized"
        )

    return manager.stop_analysis()


@ipc_handler("get_analysis_status")
def handle_get_analysis_status(command: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get current analysis status and progress.

    Returns:
        Status information including progress, current stage, errors
    """
    manager = _get_analysis_manager()
    if manager is None:
        return format_error_response(
            "get_analysis_status",
            "Analysis manager not initialized"
        )

    return manager.get_status()


@ipc_handler("capture_anatomical")
def handle_capture_anatomical(command: Dict[str, Any]) -> Dict[str, Any]:
    """
    Capture anatomical reference frame from camera.

    This should be called before starting a recording session to capture
    the anatomical baseline image for overlay with analysis results.

    Returns:
        Success response with frame info or error
    """
    from .camera_manager import camera_manager
    from .service_locator import get_services

    # Get latest frame from camera
    frame = camera_manager.get_latest_frame()
    if frame is None:
        return format_error_response(
            "capture_anatomical",
            "No camera frame available. Ensure camera is streaming."
        )

    # Store in data recorder if there's an active recording session
    services = get_services()
    data_recorder = services.data_recorder

    if data_recorder is None:
        return format_error_response(
            "capture_anatomical",
            "No active recording session. Start a recording session first."
        )

    # Save anatomical image
    data_recorder.set_anatomical_image(frame)

    return format_success_response(
        "capture_anatomical",
        message="Anatomical image captured successfully",
        shape=list(frame.shape),
        dtype=str(frame.dtype)
    )


@ipc_handler("get_analysis_results")
def handle_get_analysis_results(command: Dict[str, Any]) -> Dict[str, Any]:
    """
    Load analysis results from a completed session.

    This loads the HDF5 analysis results file and makes them available
    via shared memory for efficient frontend access.

    Args:
        command: IPC command containing session_path and optional layer name

    Returns:
        Success response with metadata (shape, num_areas, available layers)
    """
    import h5py
    import numpy as np
    from pathlib import Path
    from .service_locator import get_services

    session_path = command.get("session_path")
    if not session_path:
        return format_error_response(
            "get_analysis_results",
            "session_path is required"
        )

    # Find analysis results file
    results_path = Path(session_path) / "analysis_results" / "analysis_results.h5"
    if not results_path.exists():
        return format_error_response(
            "get_analysis_results",
            f"Analysis results not found: {results_path}"
        )

    try:
        # Load metadata only (no heavy arrays)
        with h5py.File(results_path, 'r') as f:
            shape = f['azimuth_map'].shape
            num_areas = int(np.max(f['area_map'][:]))

            # Primary result layers (final outputs for visualization)
            primary_layers = [
                'azimuth_map',
                'elevation_map',
                'sign_map',
                'area_map',
                'boundary_map'
            ]

            # Advanced/debugging layers (intermediate processing results)
            advanced_layers = []

            # Check for phase/magnitude maps (intermediate results)
            if 'phase_maps' in f:
                advanced_layers.extend([f'phase_{d}' for d in f['phase_maps'].keys()])
            if 'magnitude_maps' in f:
                advanced_layers.extend([f'magnitude_{d}' for d in f['magnitude_maps'].keys()])

        # Check for anatomical
        anatomical_path = Path(session_path) / "anatomical.npy"
        has_anatomical = anatomical_path.exists()
        if has_anatomical:
            primary_layers.append('anatomical')

        logger.info(
            f"Analysis results available from {session_path}: "
            f"shape={shape}, areas={num_areas}, "
            f"primary_layers={len(primary_layers)}, advanced_layers={len(advanced_layers)}"
        )

        return format_success_response(
            "get_analysis_results",
            message="Analysis results metadata loaded",
            session_path=session_path,
            shape=list(shape),
            num_areas=num_areas,
            primary_layers=primary_layers,
            advanced_layers=advanced_layers,
            has_anatomical=has_anatomical,
        )

    except Exception as e:
        logger.error(f"Failed to load analysis results: {e}", exc_info=True)
        return format_error_response(
            "get_analysis_results",
            f"Failed to load analysis results: {str(e)}"
        )


@ipc_handler("get_analysis_layer")
def handle_get_analysis_layer(command: Dict[str, Any]) -> Dict[str, Any]:
    """
    Load a specific analysis layer and send via shared memory.

    This is the efficient way to transfer large analysis arrays to the frontend.

    Args:
        command: IPC command containing session_path and layer_name

    Returns:
        Success response with shared memory details
    """
    import h5py
    import numpy as np
    from pathlib import Path
    from .service_locator import get_services

    session_path = command.get("session_path")
    layer_name = command.get("layer_name")

    if not session_path or not layer_name:
        return format_error_response(
            "get_analysis_layer",
            "session_path and layer_name are required"
        )

    results_path = Path(session_path) / "analysis_results" / "analysis_results.h5"
    if not results_path.exists():
        return format_error_response(
            "get_analysis_layer",
            f"Analysis results not found: {results_path}"
        )

    try:
        # Load the requested layer
        layer_data = None

        if layer_name == 'anatomical':
            anatomical_path = Path(session_path) / "anatomical.npy"
            if anatomical_path.exists():
                layer_data = np.load(anatomical_path)
        else:
            with h5py.File(results_path, 'r') as f:
                # Handle direct layers
                if layer_name in f:
                    layer_data = f[layer_name][:]
                # Handle phase maps
                elif layer_name.startswith('phase_'):
                    direction = layer_name.replace('phase_', '')
                    if 'phase_maps' in f and direction in f['phase_maps']:
                        layer_data = f['phase_maps'][direction][:]
                # Handle magnitude maps
                elif layer_name.startswith('magnitude_'):
                    direction = layer_name.replace('magnitude_', '')
                    if 'magnitude_maps' in f and direction in f['magnitude_maps']:
                        layer_data = f['magnitude_maps'][direction][:]

        if layer_data is None:
            return format_error_response(
                "get_analysis_layer",
                f"Layer not found: {layer_name}"
            )

        # Convert to float32 for consistency
        if layer_data.dtype != np.float32:
            layer_data = layer_data.astype(np.float32)

        # Ensure dedicated analysis shared memory buffer exists
        ensure_analysis_shm_buffer()

        # Write raw Float32 data directly to dedicated analysis shared memory file
        # This is separate from stimulus streaming to avoid collisions
        try:
            # Write directly to analysis shared memory file at offset 0
            with open(ANALYSIS_SHM_PATH, 'r+b') as f:
                f.seek(0)
                f.write(layer_data.tobytes())
                f.flush()
        except Exception as e:
            logger.error(f"Failed to write analysis layer to shared memory: {e}")
            return format_error_response(
                "get_analysis_layer",
                f"Failed to write to shared memory: {str(e)}"
            )

        logger.info(f"Loaded analysis layer '{layer_name}': shape={layer_data.shape}, dtype={layer_data.dtype}")

        return format_success_response(
            "get_analysis_layer",
            message=f"Layer '{layer_name}' loaded to shared memory",
            layer_name=layer_name,
            shm_path=ANALYSIS_SHM_PATH,
            shape=list(layer_data.shape),
            dtype=str(layer_data.dtype),
            data_min=float(np.nanmin(layer_data)),
            data_max=float(np.nanmax(layer_data)),
        )

    except Exception as e:
        logger.error(f"Failed to load analysis layer: {e}", exc_info=True)
        return format_error_response(
            "get_analysis_layer",
            f"Failed to load analysis layer: {str(e)}"
        )


@ipc_handler("get_analysis_composite_image")
def handle_get_analysis_composite_image(command: Dict[str, Any]) -> Dict[str, Any]:
    """
    Render analysis composite image with specified layers.

    This is the new backend-rendered approach where all visualization logic
    runs on the backend and the frontend receives a pre-rendered PNG image.

    Args:
        command: {
            'session_path': str,
            'layers': {
                'anatomical': {'visible': bool, 'alpha': float},
                'signal': {'visible': bool, 'type': str, 'alpha': float},
                'overlay': {'visible': bool, 'type': str, 'alpha': float}
            },
            'width': int (optional, for scaling - not yet implemented),
            'height': int (optional, for scaling - not yet implemented)
        }

    Returns:
        {
            'success': bool,
            'image_base64': str,  # Base64-encoded PNG
            'width': int,
            'height': int,
            'format': 'png'
        }
    """
    import base64
    from .analysis_image_renderer import generate_composite_image

    session_path = command.get("session_path")
    layer_config = command.get("layers", {})

    if not session_path:
        return format_error_response(
            "get_analysis_composite_image",
            "session_path is required"
        )

    try:
        # Generate the composite image as PNG bytes
        png_bytes = generate_composite_image(session_path, layer_config)

        # Encode as base64 for JSON transmission
        image_base64 = base64.b64encode(png_bytes).decode('utf-8')

        # Get image dimensions (decode to get metadata)
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(png_bytes))
        width, height = img.size

        logger.info(
            f"Generated composite image for {session_path}: "
            f"{width}x{height}, {len(png_bytes)} bytes"
        )

        return format_success_response(
            "get_analysis_composite_image",
            message="Composite image generated successfully",
            image_base64=image_base64,
            width=width,
            height=height,
            format="png"
        )

    except FileNotFoundError as e:
        logger.error(f"Analysis results not found: {e}")
        return format_error_response(
            "get_analysis_composite_image",
            str(e)
        )
    except Exception as e:
        logger.error(f"Failed to generate composite image: {e}", exc_info=True)
        return format_error_response(
            "get_analysis_composite_image",
            f"Failed to generate composite image: {str(e)}"
        )
