"""IPC handlers for playback mode operations."""

from typing import Dict, Any
from .ipc_utils import ipc_handler
from .logging_utils import get_logger

logger = get_logger(__name__)

# Global playback controller instance (will be set by main.py)
# NOTE: This global is maintained for backward compatibility, but handlers now
# use service registry as the primary source
playback_controller = None


def _get_playback_controller():
    """Get playback controller from service registry, fallback to module global."""
    try:
        from .service_locator import get_services
        services = get_services()
        controller = services.playback_controller

        if controller is not None:
            return controller

        # Fallback to module global if service registry not available
        logger.warning("Playback controller not in service registry, using module global")
        return playback_controller

    except RuntimeError:
        # Service registry not initialized yet, use module global
        logger.debug("Service registry not initialized, using module global playback controller")
        return playback_controller


@ipc_handler("list_sessions")
def handle_list_sessions(command: Dict[str, Any]) -> Dict[str, Any]:
    """List all available recorded sessions."""
    controller = _get_playback_controller()
    if controller is None:
        return {"success": False, "error": "Playback controller not initialized"}

    return controller.activate(session_path=None)


@ipc_handler("load_session")
def handle_load_session(command: Dict[str, Any]) -> Dict[str, Any]:
    """Load a specific session for playback."""
    controller = _get_playback_controller()
    if controller is None:
        return {"success": False, "error": "Playback controller not initialized"}

    session_path = command.get("session_path")
    if not session_path:
        return {"success": False, "error": "session_path is required"}

    return controller.activate(session_path=session_path)


@ipc_handler("get_session_data")
def handle_get_session_data(command: Dict[str, Any]) -> Dict[str, Any]:
    """Get data from loaded session."""
    controller = _get_playback_controller()
    if controller is None:
        return {"success": False, "error": "Playback controller not initialized"}

    direction = command.get("direction")
    return controller.get_session_data(direction=direction)


@ipc_handler("unload_session")
def handle_unload_session(command: Dict[str, Any]) -> Dict[str, Any]:
    """Unload current playback session."""
    controller = _get_playback_controller()
    if controller is None:
        return {"success": False, "error": "Playback controller not initialized"}

    return controller.deactivate()


@ipc_handler("get_playback_frame")
def handle_get_playback_frame(command: Dict[str, Any]) -> Dict[str, Any]:
    """Get a specific frame from loaded session."""
    controller = _get_playback_controller()
    if controller is None:
        return {"success": False, "error": "Playback controller not initialized"}

    direction = command.get("direction")
    frame_index = command.get("frame_index")

    if direction is None:
        return {"success": False, "error": "direction is required"}
    if frame_index is None:
        return {"success": False, "error": "frame_index is required"}

    return controller.get_playback_frame(direction, frame_index)
