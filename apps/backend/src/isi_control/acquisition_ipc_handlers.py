"""IPC handlers for acquisition orchestration commands."""

from typing import Dict, Any

from .ipc_utils import ipc_handler
from .logging_utils import get_logger

logger = get_logger(__name__)


def get_acquisition_manager():
    """Get the global acquisition manager instance."""
    from .acquisition_manager import get_acquisition_manager as _get_mgr
    return _get_mgr()


@ipc_handler("start_acquisition")
def handle_start_acquisition(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle start_acquisition IPC command."""
    from .service_locator import get_services

    services = get_services()
    param_manager = services.parameter_manager

    # Get acquisition parameters
    acq_params = param_manager.get_parameter_group("acquisition")

    # Add camera FPS from camera parameters - REQUIRED for scientifically valid acquisition
    camera_params = param_manager.get_parameter_group("camera")
    camera_fps = camera_params.get("camera_fps")
    if camera_fps is None or camera_fps <= 0:
        return {
            "success": False,
            "error": (
                "camera_fps is required but not configured in camera parameters. "
                "Camera FPS must be set to the actual frame rate of your camera hardware "
                "for scientifically valid acquisition timing."
            )
        }
    acq_params["camera_fps"] = camera_fps

    manager = get_acquisition_manager()
    return manager.start_acquisition(acq_params, param_manager=param_manager)


@ipc_handler("stop_acquisition")
def handle_stop_acquisition(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle stop_acquisition IPC command."""
    manager = get_acquisition_manager()
    return manager.stop_acquisition()


@ipc_handler("get_acquisition_status")
def handle_get_acquisition_status(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_acquisition_status IPC command."""
    manager = get_acquisition_manager()
    status = manager.get_status()
    return {"status": status}


@ipc_handler("set_acquisition_mode")
def handle_set_acquisition_mode(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle set_acquisition_mode IPC command."""
    from .service_locator import get_services

    services = get_services()
    param_manager = services.parameter_manager
    manager = get_acquisition_manager()

    payload = dict(command)
    mode = payload.get("mode", "preview")
    direction = payload.get("direction")
    frame_index = payload.get("frame_index")
    show_mask = payload.get("show_bar_mask")

    return manager.set_mode(
        mode=mode,
        direction=direction,
        frame_index=frame_index,
        show_mask=show_mask,
        param_manager=param_manager,
    )


@ipc_handler("display_black_screen")
def handle_display_black_screen(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle display_black_screen IPC command."""
    manager = get_acquisition_manager()
    return manager.display_black_screen()


@ipc_handler("format_elapsed_time")
def handle_format_elapsed_time(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle format_elapsed_time IPC command - format elapsed time as HH:MM:SS:FF"""
    from .acquisition_data_formatter import format_elapsed_time
    from .service_locator import get_services

    start_time_ms = command.get("start_time_ms")
    current_frame_count = command.get("current_frame_count", 0)

    if start_time_ms is None:
        return {
            "success": False,
            "error": "start_time_ms is required"
        }

    # Get camera FPS from parameters
    services = get_services()
    param_manager = services.parameter_manager
    camera_params = param_manager.get_parameter_group("camera")
    camera_fps = camera_params.get("camera_fps", 30.0)

    formatted_time = format_elapsed_time(
        start_time_ms=start_time_ms,
        current_frame_count=current_frame_count,
        camera_fps=camera_fps
    )

    return {
        "success": True,
        "formatted_time": formatted_time
    }
