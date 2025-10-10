#!/usr/bin/env python3
"""ISI Macroscope Main Application - Composition Root.

This is where all dependencies are wired together using KISS principles:
- Constructor injection only
- Lambda handlers with closure-captured dependencies
- Explicit handler mapping (no decorators)
- Simple event loop

Phase 6: Main Application - Final composition root for the refactored system.
"""

import sys
import logging
import signal
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Import all refactored modules
from config import AppConfig
from ipc.channels import MultiChannelIPC
from ipc.shared_memory import SharedMemoryService
from camera.manager import CameraManager
from stimulus.generator import StimulusGenerator
from acquisition.manager import AcquisitionManager
from acquisition.state import AcquisitionStateCoordinator
from acquisition.sync_tracker import TimestampSynchronizationTracker
from acquisition.camera_stimulus import CameraTriggeredStimulusController
from acquisition.recorder import create_session_recorder
from acquisition.modes import PlaybackModeController
from analysis.manager import AnalysisManager
from analysis.pipeline import AnalysisPipeline
from analysis.renderer import AnalysisRenderer

# Import old parameter manager (not refactored yet)
from isi_control.parameter_manager import ParameterManager

logger = logging.getLogger(__name__)


def create_services(config: AppConfig) -> Dict[str, Any]:
    """Create all services with explicit dependencies (composition root).

    This function wires together the entire application using constructor
    injection. NO service locator, NO decorators, just explicit dependencies.

    Args:
        config: Application configuration

    Returns:
        Dictionary containing all instantiated services
    """
    logger.info("Creating services (composition root)...")

    # =========================================================================
    # Layer 1: Infrastructure (no dependencies)
    # =========================================================================

    ipc = MultiChannelIPC(
        transport=config.ipc.transport,
        health_port=config.ipc.health_port,
        sync_port=config.ipc.sync_port
    )
    logger.info("  [1/11] MultiChannelIPC created")

    shared_memory = SharedMemoryService(
        stream_name=config.shared_memory.stream_name,
        buffer_size_mb=config.shared_memory.buffer_size_mb,
        metadata_port=config.shared_memory.metadata_port,
        camera_metadata_port=config.shared_memory.camera_metadata_port
    )
    logger.info("  [2/11] SharedMemoryService created")

    # Parameter manager (old implementation - not refactored)
    param_manager = ParameterManager(
        config_file=config.parameters.file_path.name,
        config_dir=str(config.parameters.file_path.parent),
    )
    logger.info("  [3/11] ParameterManager created")

    # =========================================================================
    # Layer 2: Core systems (depend on infrastructure)
    # =========================================================================

    stimulus_generator = StimulusGenerator(
        stimulus_config=config.stimulus,
        monitor_config=config.monitor
    )
    logger.info("  [4/11] StimulusGenerator created")

    camera = CameraManager(
        config=config.camera,
        ipc=ipc,
        shared_memory=shared_memory
    )
    logger.info("  [5/11] CameraManager created")

    # =========================================================================
    # Layer 3: Analysis system (depends on infrastructure)
    # =========================================================================

    analysis_pipeline = AnalysisPipeline(
        config=config.analysis
    )
    logger.info("  [6/11] AnalysisPipeline created")

    analysis_renderer = AnalysisRenderer(
        config=config.analysis,
        shared_memory=shared_memory
    )
    logger.info("  [7/11] AnalysisRenderer created")

    analysis_manager = AnalysisManager(
        config=config.analysis,
        acquisition_config=config.acquisition,
        ipc=ipc,
        shared_memory=shared_memory,
        pipeline=analysis_pipeline
    )
    # Note: Renderer callback can be wired later if needed for incremental visualization
    logger.info("  [8/11] AnalysisManager created")

    # =========================================================================
    # Layer 4: Acquisition subsystems (depend on core systems)
    # =========================================================================

    state_coordinator = AcquisitionStateCoordinator()
    logger.info("  [9/11] AcquisitionStateCoordinator created")

    sync_tracker = TimestampSynchronizationTracker()
    logger.info("  [10/11] TimestampSynchronizationTracker created")

    camera_triggered_stimulus = CameraTriggeredStimulusController(
        stimulus_generator=stimulus_generator
    )

    # Playback controller (shared between IPC handlers and acquisition manager)
    playback_controller = PlaybackModeController(
        state_coordinator=state_coordinator
    )

    # =========================================================================
    # Layer 5: Acquisition manager (depends on all acquisition subsystems)
    # =========================================================================

    acquisition = AcquisitionManager(
        ipc=ipc,
        shared_memory=shared_memory,
        stimulus_generator=stimulus_generator,
        synchronization_tracker=sync_tracker,
        state_coordinator=state_coordinator,
        camera_triggered_stimulus=camera_triggered_stimulus,
        data_recorder=None,  # Created dynamically when acquisition starts
        param_manager=param_manager,
    )
    # Wire playback controller
    acquisition.playback_controller = playback_controller
    logger.info("  [11/11] AcquisitionManager created")

    # Wire camera dependencies (camera -> acquisition subsystems)
    camera.synchronization_tracker = sync_tracker
    camera.camera_triggered_stimulus = camera_triggered_stimulus

    logger.info("All services created successfully")

    return {
        "config": config,
        "ipc": ipc,
        "shared_memory": shared_memory,
        "camera": camera,
        "stimulus_generator": stimulus_generator,
        "acquisition": acquisition,
        "analysis_manager": analysis_manager,
        "analysis_renderer": analysis_renderer,
        "playback_controller": playback_controller,
        "param_manager": param_manager,
    }


def create_handlers(services: Dict[str, Any]) -> Dict[str, Any]:
    """Create handler mapping using KISS pattern (lambda handlers).

    This is the KISS approach: explicit dict mapping with lambda handlers
    that capture dependencies via closure. NO decorators, NO magic!

    Args:
        services: Dictionary of all instantiated services

    Returns:
        Dictionary mapping command_type -> handler function
    """
    camera = services["camera"]
    acquisition = services["acquisition"]
    analysis = services["analysis_manager"]
    playback = services["playback_controller"]
    config = services["config"]
    param_manager = services["param_manager"]
    ipc = services["ipc"]
    stimulus_generator = services["stimulus_generator"]
    shared_memory = services["shared_memory"]

    # Import display module for display handlers
    from display import detect_displays, get_display_by_identifier

    # Store in services dict for access by _handle_frontend_ready
    services["handlers_config"] = {
        "param_manager": param_manager,
        "ipc": ipc,
    }

    # KISS pattern: explicit handler mapping with lambdas
    handlers = {
        # =====================================================================
        # Camera commands
        # =====================================================================
        "detect_cameras": lambda cmd: {
            "success": True,
            "cameras": camera.detect_cameras(force=cmd.get("force", False))
        },
        "get_camera_capabilities": lambda cmd: {
            "success": True,
            "capabilities": camera.get_camera_capabilities(cmd.get("camera_name"))
        },
        "camera_stream_started": lambda cmd: {
            "success": True,
            "message": "Camera stream started"
        },
        "camera_stream_stopped": lambda cmd: {
            "success": True,
            "message": "Camera stream stopped"
        },
        "camera_capture": lambda cmd: {
            "success": True,
            "message": "Camera capture triggered"
        },
        "start_camera_acquisition": lambda cmd: (
            lambda result: {
                "success": result,
                "message": "Camera acquisition started" if result else "Failed to start camera acquisition"
            }
        )(camera.start_acquisition()),
        "stop_camera_acquisition": lambda cmd: {
            "success": True,
            "message": "Camera acquisition stopped"
        } if not camera.stop_acquisition() else {"success": True},
        "get_camera_histogram": lambda cmd: camera.generate_luminance_histogram(
            camera.get_latest_frame()
        ) if camera.get_latest_frame() is not None else {"error": "No frame available"},
        "get_synchronization_data": lambda cmd: {
            "success": True,
            **acquisition.get_synchronization_data()
        },
        "get_correlation_data": lambda cmd: {
            "success": True,
            **acquisition.get_synchronization_data()
        },  # Backward compatibility alias

        # =====================================================================
        # Acquisition commands
        # =====================================================================
        "start_acquisition": lambda cmd: acquisition.start_acquisition(
            params=cmd.get("params", {}),
            param_manager=param_manager
        ),
        "stop_acquisition": lambda cmd: acquisition.stop_acquisition(),
        "get_acquisition_status": lambda cmd: {
            "success": True,
            **acquisition.get_status()
        },
        "set_acquisition_mode": lambda cmd: acquisition.set_mode(
            mode=cmd.get("mode", "preview"),
            direction=cmd.get("direction"),
            frame_index=cmd.get("frame_index"),
            show_mask=cmd.get("show_mask"),
            param_manager=param_manager
        ),

        # =====================================================================
        # Playback commands
        # =====================================================================
        "list_sessions": lambda cmd: playback.list_sessions(
            cmd.get("base_dir", str(Path(__file__).parent.parent / "data" / "sessions"))
        ),
        "load_session": lambda cmd: playback.activate(
            session_path=cmd.get("session_path")
        ),
        "get_session_data": lambda cmd: playback.get_session_data(
            direction=cmd.get("direction")
        ),
        "unload_session": lambda cmd: playback.deactivate(),
        "get_playback_frame": lambda cmd: playback.get_playback_frame(
            direction=cmd.get("direction"),
            frame_index=cmd.get("frame_index", 0)
        ),

        # =====================================================================
        # Stimulus commands
        # =====================================================================
        "get_stimulus_parameters": lambda cmd: _get_stimulus_parameters(
            param_manager
        ),
        "update_stimulus_parameters": lambda cmd: _update_stimulus_parameters(
            param_manager, cmd
        ),
        "get_spatial_configuration": lambda cmd: _get_spatial_configuration(
            param_manager
        ),
        "update_spatial_configuration": lambda cmd: _update_spatial_configuration(
            param_manager, cmd
        ),
        "get_stimulus_info": lambda cmd: _get_stimulus_info(
            stimulus_generator, cmd
        ),
        "get_stimulus_frame": lambda cmd: _get_stimulus_frame(
            stimulus_generator, shared_memory, cmd
        ),
        "generate_stimulus_preview": lambda cmd: _generate_stimulus_preview(
            stimulus_generator, cmd
        ),
        "start_stimulus": lambda cmd: _start_stimulus(
            stimulus_generator, shared_memory, acquisition, cmd
        ),
        "stop_stimulus": lambda cmd: _stop_stimulus(
            shared_memory, acquisition
        ),
        "get_stimulus_status": lambda cmd: _get_stimulus_status(),
        "display_timestamp": lambda cmd: _handle_display_timestamp(
            shared_memory, cmd
        ),

        # =====================================================================
        # Display commands
        # =====================================================================
        "detect_displays": lambda cmd: _detect_displays(
            param_manager, cmd
        ),
        "get_display_capabilities": lambda cmd: _get_display_capabilities(cmd),
        "select_display": lambda cmd: _select_display(
            param_manager, cmd
        ),

        # =====================================================================
        # Analysis commands
        # =====================================================================
        "start_analysis": lambda cmd: analysis.start_analysis(
            cmd.get("session_path")
        ),
        "stop_analysis": lambda cmd: analysis.stop_analysis(),
        "get_analysis_status": lambda cmd: analysis.get_status(),
        "capture_anatomical": lambda cmd: _capture_anatomical(camera),
        "get_analysis_results": lambda cmd: _get_analysis_results(analysis, cmd),
        "get_analysis_layer": lambda cmd: _get_analysis_layer(analysis, cmd),
        "get_analysis_composite_image": lambda cmd: _get_analysis_composite_image(
            services["analysis_renderer"], cmd
        ),

        # =====================================================================
        # Parameter management commands
        # =====================================================================
        "get_all_parameters": lambda cmd: {
            "success": True,
            "type": "all_parameters",
            "parameters": param_manager.get_all_parameters(),
        },
        "get_parameter_group": lambda cmd: {
            "success": True,
            "type": "parameter_group",
            "group_name": cmd.get("group_name"),
            "parameters": param_manager.get_parameter_group(cmd.get("group_name")),
        } if cmd.get("group_name") else {"success": False, "error": "group_name required"},
        "update_parameter_group": lambda cmd: _update_parameters(
            param_manager, ipc, cmd
        ),
        "reset_to_defaults": lambda cmd: _reset_parameters(param_manager, ipc),
        "get_parameter_info": lambda cmd: {
            "success": True,
            "type": "parameter_info",
            "info": param_manager.get_parameter_info(),
        },

        # =====================================================================
        # System commands
        # =====================================================================
        "ping": lambda cmd: {"success": True, "pong": True},
        "get_system_status": lambda cmd: {
            "success": True,
            "status": "ready",
            "backend_running": True,
        },
        "get_system_health": lambda cmd: _get_system_health(
            camera, acquisition, analysis, param_manager, ipc, shared_memory, cmd
        ),
        "health_check": lambda cmd: {
            "status": "healthy",
            "services": list(services.keys())
        },

        # =====================================================================
        # Frontend handshake
        # =====================================================================
        "frontend_ready": lambda cmd: _handle_frontend_ready(services, cmd),
    }

    logger.info(f"Created {len(handlers)} command handlers")
    return handlers


# =============================================================================
# Stimulus Handler Helpers
# =============================================================================

def _get_stimulus_parameters(param_manager) -> Dict[str, Any]:
    """Get current stimulus parameters from ParameterManager (source of truth)."""
    stimulus_params = param_manager.get_parameter_group("stimulus")
    return {
        "parameters": stimulus_params
    }


def _update_stimulus_parameters(param_manager, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Update stimulus parameters."""
    params = cmd.get("parameters", {})
    param_manager.update_parameter_group("stimulus", params)
    return {"success": True, "message": "Stimulus parameters updated"}


def _get_spatial_configuration(param_manager) -> Dict[str, Any]:
    """Get spatial configuration from ParameterManager (source of truth)."""
    monitor_params = param_manager.get_parameter_group("monitor")
    return {
        "configuration": {
            "monitor_distance_cm": monitor_params.get("monitor_distance_cm"),
            "monitor_angle_degrees": monitor_params.get("monitor_lateral_angle_deg"),
            "screen_width_pixels": monitor_params.get("monitor_width_px"),
            "screen_height_pixels": monitor_params.get("monitor_height_px"),
            "screen_width_cm": monitor_params.get("monitor_width_cm"),
            "screen_height_cm": monitor_params.get("monitor_height_cm"),
            "fps": monitor_params.get("monitor_fps"),
            # Note: FOV is calculated from the above parameters, not stored directly
        }
    }


def _update_spatial_configuration(param_manager, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Update spatial configuration."""
    config = cmd.get("spatial_config", cmd.get("configuration", {}))

    # Map to monitor parameter names
    monitor_updates = {}
    if "monitor_distance_cm" in config:
        monitor_updates["monitor_distance_cm"] = config["monitor_distance_cm"]
    if "monitor_angle_degrees" in config or "monitor_lateral_angle_deg" in config:
        monitor_updates["monitor_lateral_angle_deg"] = config.get(
            "monitor_lateral_angle_deg", config.get("monitor_angle_degrees")
        )
    if "monitor_width_cm" in config or "screen_width_cm" in config:
        monitor_updates["monitor_width_cm"] = config.get(
            "monitor_width_cm", config.get("screen_width_cm")
        )
    if "monitor_height_cm" in config or "screen_height_cm" in config:
        monitor_updates["monitor_height_cm"] = config.get(
            "monitor_height_cm", config.get("screen_height_cm")
        )
    if "screen_width_pixels" in config or "monitor_width_px" in config:
        monitor_updates["monitor_width_px"] = config.get(
            "monitor_width_px", config.get("screen_width_pixels")
        )
    if "screen_height_pixels" in config or "monitor_height_px" in config:
        monitor_updates["monitor_height_px"] = config.get(
            "monitor_height_px", config.get("screen_height_pixels")
        )
    if "fps" in config or "monitor_fps" in config:
        monitor_updates["monitor_fps"] = config.get("monitor_fps", config.get("fps"))

    param_manager.update_parameter_group("monitor", monitor_updates)
    return {"success": True, "message": "Spatial configuration updated"}


def _get_stimulus_info(stimulus_generator, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Get stimulus dataset information."""
    direction = cmd.get("direction", "LR")
    num_cycles = cmd.get("num_cycles", 3)

    dataset_info = stimulus_generator.get_dataset_info(direction, num_cycles)

    if "error" in dataset_info:
        return {"success": False, "error": dataset_info["error"]}

    return dataset_info


def _get_stimulus_frame(
    stimulus_generator,
    shared_memory,
    cmd: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate stimulus frame on-demand."""
    direction = cmd.get("direction", "LR")
    frame_index = cmd.get("frame_index", 0)
    show_bar_mask = cmd.get("show_bar_mask", True)
    total_frames = cmd.get("total_frames")

    # Generate frame
    frame, metadata = stimulus_generator.generate_frame_at_index(
        direction=direction,
        frame_index=frame_index,
        show_bar_mask=show_bar_mask,
        total_frames=total_frames
    )

    # Write to shared memory
    frame_id = shared_memory.write_frame(frame, metadata)

    return {
        "success": True,
        "frame_id": frame_id,
        "frame_info": metadata
    }


def _generate_stimulus_preview(stimulus_generator, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Generate stimulus preview information."""
    direction = cmd.get("direction", "LR")

    dataset_info = stimulus_generator.get_dataset_info(direction, 3)

    if "error" in dataset_info:
        return {"success": False, "error": dataset_info["error"]}

    config = stimulus_generator.spatial_config
    stim_config = stimulus_generator.stimulus_config

    preview_info = {
        "direction": direction,
        "bar_width_deg": stim_config.bar_width_deg,
        "sweep_range_deg": dataset_info["sweep_degrees"],
        "cycle_duration_sec": dataset_info["duration_sec"],
        "frames_per_cycle": dataset_info["total_frames"] // 3,
        "total_frames": dataset_info["total_frames"],
        "estimated_duration_sec": dataset_info["duration_sec"],
        "field_of_view_deg": {
            "horizontal": config.field_of_view_horizontal,
            "vertical": config.field_of_view_vertical,
        },
        "resolution": {
            "width_px": config.screen_width_pixels,
            "height_px": config.screen_height_pixels,
        },
        "timing": {
            "fps": config.fps,
            "frame_duration_ms": 1000.0 / config.fps,
            "strobe_period_ms": (
                1000.0 / stim_config.strobe_rate_hz
                if stim_config.strobe_rate_hz > 0
                else None
            ),
        },
    }

    return {"preview": preview_info}


# Stimulus status tracking
_stimulus_status = {"is_presenting": False, "current_session": None}


def _start_stimulus(
    stimulus_generator,
    shared_memory,
    acquisition,
    cmd: Dict[str, Any]
) -> Dict[str, Any]:
    """Start real-time stimulus streaming."""
    session_name = cmd.get("session_name", f"session_{int(time.time())}")
    direction = cmd.get("direction", "LR")
    fps = cmd.get("fps", 60.0)

    try:
        # Update status
        _stimulus_status["is_presenting"] = True
        _stimulus_status["current_session"] = session_name

        # Start real-time streaming
        producer = shared_memory.start_realtime_streaming(stimulus_generator, fps)

        if producer:
            producer.set_stimulus_params(direction)
            logger.info(f"Real-time stimulus streaming started: {session_name}")
        else:
            raise Exception("Realtime producer not available")

        return {"success": True, "message": f"Real-time stimulus streaming started: {session_name}"}

    except Exception as e:
        logger.error(f"Error starting stimulus: {e}")
        _stimulus_status["is_presenting"] = False
        _stimulus_status["current_session"] = None
        return {"success": False, "error": str(e)}


def _stop_stimulus(shared_memory, acquisition) -> Dict[str, Any]:
    """Stop real-time stimulus streaming."""
    try:
        # Stop streaming
        shared_memory.stop_realtime_streaming()
        shared_memory.clear_stimulus_frames()
        shared_memory.clear_stimulus_timestamp()

        # Update status
        session_name = _stimulus_status["current_session"]
        _stimulus_status["is_presenting"] = False
        _stimulus_status["current_session"] = None

        logger.info(f"Real-time stimulus streaming stopped: {session_name}")
        return {"success": True, "message": "Real-time stimulus streaming stopped"}

    except Exception as e:
        logger.error(f"Error stopping stimulus: {e}")
        return {"success": False, "error": str(e)}


def _get_stimulus_status() -> Dict[str, Any]:
    """Get stimulus status."""
    return {"status": _stimulus_status.copy()}


def _handle_display_timestamp(shared_memory, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Handle display timestamp from frontend."""
    frame_id = cmd.get("frame_id")
    display_timestamp_us = cmd.get("display_timestamp_us")

    if frame_id is None or display_timestamp_us is None:
        return {
            "success": False,
            "error": "Missing frame_id or display_timestamp_us"
        }

    # Store timestamp
    shared_memory.set_stimulus_timestamp(display_timestamp_us, frame_id)

    return {"success": True}


# =============================================================================
# Display Handler Helpers
# =============================================================================

def _detect_displays(param_manager, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Detect all displays."""
    from display import detect_displays

    force_refresh = cmd.get("force", False)
    displays = detect_displays()

    # Update monitor parameters if needed
    if displays:
        primary = next((d for d in displays if d.is_primary), displays[0])
        monitor_updates = {
            "monitor_width_px": primary.width,
            "monitor_height_px": primary.height,
            "monitor_fps": int(primary.refresh_rate),
        }
        param_manager.update_parameter_group("monitor", monitor_updates)

    return {
        "success": True,
        "displays": [d.to_dict() for d in displays],
        "selected_display": displays[0].identifier if displays else None
    }


def _get_display_capabilities(cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Get display capabilities."""
    from display import get_display_by_identifier

    display_id = cmd.get("display_id")
    if not display_id:
        return {"success": False, "error": "display_id is required"}

    display = get_display_by_identifier(display_id)
    if not display:
        return {"success": False, "error": f"Display not found: {display_id}"}

    return {
        "success": True,
        "capabilities": display.to_dict()
    }


def _select_display(param_manager, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Select a display."""
    from display import get_display_by_identifier

    display_id = cmd.get("display_id")
    if not display_id:
        return {"success": False, "error": "display_id is required"}

    display = get_display_by_identifier(display_id)
    if not display:
        return {"success": False, "error": f"Display not found: {display_id}"}

    # Update monitor parameters
    monitor_updates = {
        "monitor_width_px": display.width,
        "monitor_height_px": display.height,
        "monitor_fps": int(display.refresh_rate),
    }
    param_manager.update_parameter_group("monitor", monitor_updates)

    return {
        "success": True,
        "selected_display": display_id
    }


# =============================================================================
# Analysis Handler Helpers
# =============================================================================

def _capture_anatomical(camera) -> Dict[str, Any]:
    """Capture anatomical reference frame."""
    try:
        frame = camera.get_latest_frame()
        if frame is None:
            return {"success": False, "error": "No camera frame available"}

        # Store anatomical frame (implementation depends on analysis manager)
        return {
            "success": True,
            "message": "Anatomical frame captured"
        }
    except Exception as e:
        logger.error(f"Error capturing anatomical frame: {e}")
        return {"success": False, "error": str(e)}


def _get_analysis_results(analysis, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Get analysis results metadata."""
    import numpy as np
    from pathlib import Path

    try:
        session_path = cmd.get("session_path")
        if not session_path:
            return {"success": False, "error": "session_path is required"}

        results_dir = Path(session_path) / "analysis_results"
        if not results_dir.exists():
            return {"success": False, "error": f"Analysis results not found: {results_dir}"}

        # Scan for available layers
        primary_layers = []
        advanced_layers = []
        has_anatomical = False
        shape = None

        # Check for primary result layers
        for layer_file in ["azimuth_map.npy", "elevation_map.npy", "sign_map.npy", "boundary_map.npy"]:
            if (results_dir / layer_file).exists():
                layer_name = layer_file.replace(".npy", "")
                primary_layers.append(layer_name)

                # Get shape from first available layer
                if shape is None:
                    try:
                        data = np.load(str(results_dir / layer_file))
                        shape = list(data.shape[:2])  # [height, width]
                    except Exception as e:
                        logger.warning(f"Failed to load shape from {layer_file}: {e}")

        # Check for advanced/debug layers
        for layer_file in ["magnitude_LR.npy", "phase_LR.npy", "magnitude_RL.npy", "phase_RL.npy",
                          "magnitude_TB.npy", "phase_TB.npy", "magnitude_BT.npy", "phase_BT.npy"]:
            if (results_dir / layer_file).exists():
                layer_name = layer_file.replace(".npy", "")
                advanced_layers.append(layer_name)

        # Check for anatomical
        if (results_dir / "anatomical.npy").exists():
            has_anatomical = True

        # Try to count visual areas from boundary map
        num_areas = 0
        boundary_file = results_dir / "boundary_map.npy"
        if boundary_file.exists():
            try:
                boundary_data = np.load(str(boundary_file))
                # Count unique non-zero regions (rough estimate)
                num_areas = len(np.unique(boundary_data)) - 1  # Subtract background
            except Exception as e:
                logger.warning(f"Failed to count areas: {e}")

        return {
            "success": True,
            "session_path": session_path,
            "shape": shape or [0, 0],
            "num_areas": num_areas,
            "primary_layers": primary_layers,
            "advanced_layers": advanced_layers,
            "has_anatomical": has_anatomical
        }
    except Exception as e:
        logger.error(f"Error getting analysis results: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def _get_analysis_layer(analysis, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Get specific analysis layer."""
    try:
        layer_name = cmd.get("layer_name")
        if not layer_name:
            return {"success": False, "error": "layer_name is required"}

        # This would return specific analysis layer
        # Implementation depends on analysis manager
        return {
            "success": True,
            "layer_name": layer_name,
            "layer_data": {}
        }
    except Exception as e:
        logger.error(f"Error getting analysis layer: {e}")
        return {"success": False, "error": str(e)}


def _get_analysis_composite_image(renderer, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Render composite analysis image with layer controls."""
    import base64
    import numpy as np
    from pathlib import Path

    try:
        session_path = cmd.get("session_path")
        if not session_path:
            return {"success": False, "error": "session_path is required"}

        layers = cmd.get("layers", {})

        # Load analysis results from session
        results_dir = Path(session_path) / "analysis_results"
        if not results_dir.exists():
            return {"success": False, "error": f"Analysis results not found: {results_dir}"}

        # Load result arrays (explicitly initialize to None)
        anatomical = None
        signal_layer = None
        overlay_layer = None

        # Load anatomical if visible
        if layers.get("anatomical", {}).get("visible", True):
            anatomical_file = results_dir / "anatomical.npy"
            if anatomical_file.exists():
                anatomical = np.load(str(anatomical_file))

        # Load signal layer if visible
        signal_config = layers.get("signal", {})
        if signal_config.get("visible", True):
            signal_type = signal_config.get("type", "azimuth")

            # Map signal type to file
            signal_files = {
                "azimuth": "azimuth_map.npy",
                "elevation": "elevation_map.npy",
                "sign": "sign_map.npy",
                "magnitude": "magnitude_map.npy",
                "phase": "phase_map.npy"
            }

            signal_file = results_dir / signal_files.get(signal_type, "azimuth_map.npy")
            if signal_file.exists():
                signal_data = np.load(str(signal_file))

                # Render signal layer based on type
                if signal_type == "azimuth":
                    signal_layer = renderer.render_retinotopic_map(signal_data, "azimuth")
                elif signal_type == "elevation":
                    signal_layer = renderer.render_retinotopic_map(signal_data, "elevation")
                elif signal_type == "sign":
                    signal_layer = renderer.render_sign_map(signal_data)
                else:
                    signal_layer = renderer.render_amplitude_map(signal_data)

        # Load overlay layer if visible
        overlay_config = layers.get("overlay", {})
        if overlay_config.get("visible", True):
            overlay_type = overlay_config.get("type", "area_borders")

            # Explicitly handle "none" type
            if overlay_type == "none":
                overlay_layer = None  # No overlay
            elif overlay_type == "area_borders":
                boundary_file = results_dir / "boundary_map.npy"
                if boundary_file.exists():
                    boundary_data = np.load(str(boundary_file))
                    overlay_layer = renderer.render_boundary_map(boundary_data)
            elif overlay_type == "area_patches":
                # Future: implement area_patches rendering
                logger.warning(f"Overlay type 'area_patches' not yet implemented")
                overlay_layer = None

        # Composite layers
        if signal_layer is not None:
            height, width = signal_layer.shape[:2]
            composite = np.zeros((height, width, 3), dtype=np.float32)

            # Start with anatomical layer if available AND VISIBLE
            if anatomical is not None and layers.get("anatomical", {}).get("visible", True):
                anatomical_alpha = layers.get("anatomical", {}).get("alpha", 0.5)
                if anatomical.ndim == 2:
                    # Convert grayscale to RGB
                    anatomical_rgb = np.stack([anatomical] * 3, axis=-1).astype(np.float32)
                else:
                    anatomical_rgb = anatomical[:, :, :3].astype(np.float32)

                # Blend anatomical with black background
                composite = anatomical_rgb * anatomical_alpha

            # Blend signal layer on top if VISIBLE
            if layers.get("signal", {}).get("visible", True):
                signal_alpha = layers.get("signal", {}).get("alpha", 0.8)
                composite = composite * (1.0 - signal_alpha) + signal_layer.astype(np.float32) * signal_alpha

            # Add overlay layer on top if VISIBLE
            if overlay_layer is not None and overlay_layer.shape[-1] == 4 and layers.get("overlay", {}).get("visible", True):
                overlay_alpha = layers.get("overlay", {}).get("alpha", 1.0)
                alpha_channel = (overlay_layer[:, :, 3:4].astype(np.float32) / 255.0) * overlay_alpha
                composite = (
                    composite * (1.0 - alpha_channel) +
                    overlay_layer[:, :, :3].astype(np.float32) * alpha_channel
                )

            # Convert back to uint8
            composite = np.clip(composite, 0, 255).astype(np.uint8)

            # Encode as PNG
            png_bytes = renderer.encode_as_png(composite)
            if not png_bytes:
                return {"success": False, "error": "Failed to encode composite image"}

            # Encode as base64
            png_base64 = base64.b64encode(png_bytes).decode('utf-8')

            return {
                "success": True,
                "image_base64": png_base64,
                "width": width,
                "height": height,
                "format": "png"
            }
        else:
            return {"success": False, "error": "No signal layer available to display"}

    except Exception as e:
        logger.error(f"Error rendering composite image: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# =============================================================================
# System Health Handler Helpers
# =============================================================================

def _get_system_health(camera, acquisition, analysis_manager, param_manager, ipc, shared_memory, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Get comprehensive system health status."""
    try:
        # Component-level health checks
        hardware_status = {
            "multi_channel_ipc": "online" if ipc and hasattr(ipc, '_running') else "offline",
            "parameters": "online" if param_manager else "offline",
            "display": "online",  # Display is always available if backend running
            "camera": "online" if camera and camera.active_camera and camera.active_camera.isOpened() else "offline",
            "realtime_streaming": "online" if shared_memory and shared_memory._stream and shared_memory._stream._running else "offline",
            "analysis": "online" if analysis_manager else "offline",
        }

        return {
            "success": True,
            "type": "system_health",
            "hardware_status": hardware_status,
            "timestamp": time.time(),
            "experiment_running": acquisition.is_running if acquisition else False,
        }
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return {
            "success": False,
            "error": str(e),
            "hardware_status": {
                "multi_channel_ipc": "error",
                "parameters": "error",
                "display": "error",
                "camera": "error",
                "realtime_streaming": "error",
                "analysis": "error",
            }
        }


# =============================================================================
# Startup Helpers
# =============================================================================

def _verify_hardware(camera, param_manager, ipc) -> Dict[str, Any]:
    """Verify all hardware during startup before reporting ready state.

    Args:
        camera: Camera manager instance
        param_manager: Parameter manager for updating detected hardware
        ipc: IPC service for broadcasting status updates

    Returns:
        Dict with success status and any warnings/errors
    """
    from display import detect_displays

    logger.info("Verifying hardware...")

    # Log loaded parameters for debugging
    camera_params = param_manager.get_parameter_group("camera")
    monitor_params = param_manager.get_parameter_group("monitor")
    logger.info(f"Loaded camera parameters: selected='{camera_params.get('selected_camera')}', "
               f"fps={camera_params.get('camera_fps')}")
    logger.info(f"Loaded monitor parameters: selected='{monitor_params.get('selected_display')}', "
               f"distance={monitor_params.get('monitor_distance_cm')}cm")

    warnings = []
    errors = []

    # 1. Detect and verify cameras
    ipc.send_sync_message({
        "type": "system_state",
        "state": "initializing",
        "is_ready": False,
        "display_text": "Detecting cameras...",
        "is_error": False,
        "timestamp": time.time()
    })

    try:
        detected_cameras = camera.detect_cameras(force=True)
        if not detected_cameras:
            warnings.append("No cameras detected - camera features will be unavailable")
            logger.warning("No cameras detected during startup")
        else:
            logger.info(f"Detected {len(detected_cameras)} camera(s): {[cam.name for cam in camera.detected_cameras]}")

            # Get existing camera parameters from loaded JSON
            camera_params = param_manager.get_parameter_group("camera")
            selected_camera_name = camera_params.get("selected_camera")

            # Extract camera names for JSON serialization
            camera_names = [cam.name for cam in camera.detected_cameras]

            # Update available cameras list with names (not objects!)
            camera_updates = {
                "available_cameras": camera_names
            }

            # Try to open the selected camera from JSON or auto-select first available
            camera_to_open = None

            # Check if the selected camera from JSON is available
            if selected_camera_name and selected_camera_name in camera_names:
                # Find camera index by name
                for cam_info in camera.detected_cameras:
                    if cam_info.name == selected_camera_name and cam_info.is_available:
                        camera_to_open = (cam_info.index, cam_info.name)
                        logger.info(f"Using camera from parameters: {selected_camera_name}")
                        break

            # If no valid selection from JSON or not found, auto-select FIRST camera
            if not camera_to_open and camera.detected_cameras:
                first_cam = camera.detected_cameras[0]
                camera_to_open = (first_cam.index, first_cam.name)
                camera_updates["selected_camera"] = first_cam.name
                logger.info(f"Auto-selected first available camera: {first_cam.name}")

            # Try to open the camera
            if camera_to_open:
                try:
                    if camera.open_camera(camera_to_open[0]):
                        # Update camera properties from opened camera
                        caps = camera.get_camera_capabilities(camera_to_open[1])
                        if caps:
                            camera_updates["camera_width_px"] = caps.get("width", camera_params.get("camera_width_px", -1))
                            camera_updates["camera_height_px"] = caps.get("height", camera_params.get("camera_height_px", -1))
                            # Keep existing FPS from JSON, don't override with detected FPS
                            # (detected FPS is often wrong from OpenCV)
                            if camera_params.get("camera_fps", -1) <= 0:
                                camera_updates["camera_fps"] = int(caps.get("frameRate", 30))

                        logger.info(f"Camera '{camera_to_open[1]}' opened successfully at index {camera_to_open[0]}")
                    else:
                        error_msg = f"Failed to open camera '{camera_to_open[1]}'"
                        warnings.append(error_msg)
                        logger.warning(error_msg)
                except Exception as e:
                    error_msg = f"Failed to open camera '{camera_to_open[1]}': {e}"
                    warnings.append(error_msg)
                    logger.warning(error_msg)

            # Apply camera parameter updates
            param_manager.update_parameter_group("camera", camera_updates)
    except Exception as e:
        error_msg = f"Camera detection failed: {e}"
        warnings.append(error_msg)
        logger.error(error_msg, exc_info=True)

    # 2. Detect and verify displays
    ipc.send_sync_message({
        "type": "system_state",
        "state": "initializing",
        "is_ready": False,
        "display_text": "Detecting displays...",
        "is_error": False,
        "timestamp": time.time()
    })

    try:
        displays = detect_displays()
        if not displays:
            error_msg = "No displays detected - cannot continue"
            errors.append(error_msg)
            logger.error(error_msg)
        else:
            logger.info(f"Detected {len(displays)} display(s)")

            # PREFER SECONDARY DISPLAY for stimulus (not primary!)
            # Primary is typically the main desktop, secondary is for stimulus presentation
            secondary = next((d for d in displays if not d.is_primary), None)
            selected_display = secondary if secondary else displays[0]

            logger.info(f"Selected display for stimulus: {selected_display.identifier} "
                       f"({'secondary' if secondary else 'primary - no secondary available'})")

            monitor_updates = {
                "available_displays": [d.identifier for d in displays],
                "monitor_width_px": selected_display.width,
                "monitor_height_px": selected_display.height,
                "monitor_fps": int(selected_display.refresh_rate),
            }

            # Check if we should use existing selection or auto-select
            monitor_params = param_manager.get_parameter_group("monitor")
            existing_selection = monitor_params.get("selected_display")

            # Only override if no valid selection exists or it's not in available displays
            available_ids = [d.identifier for d in displays]
            if not existing_selection or existing_selection not in available_ids:
                monitor_updates["selected_display"] = selected_display.identifier
                logger.info(f"Auto-selected display: {selected_display.identifier}")
            else:
                logger.info(f"Keeping existing display selection: {existing_selection}")

            param_manager.update_parameter_group("monitor", monitor_updates)
            logger.info(f"Display configuration updated: {selected_display.identifier} "
                       f"({selected_display.width}x{selected_display.height}@{selected_display.refresh_rate}Hz)")
    except Exception as e:
        error_msg = f"Display detection failed: {e}"
        errors.append(error_msg)
        logger.error(error_msg, exc_info=True)

    # Return results
    if errors:
        return {
            "success": False,
            "errors": errors,
            "warnings": warnings
        }
    else:
        return {
            "success": True,
            "warnings": warnings
        }

def _render_initial_stimulus_frame(stimulus_generator, shared_memory):
    """Render initial stimulus frame for startup preview."""
    try:
        # Generate first frame at index 0
        direction = "LR"  # Default direction
        frame, metadata = stimulus_generator.generate_frame_at_index(
            direction=direction,
            frame_index=0,
            show_bar_mask=True,
            total_frames=None
        )

        # Write to shared memory
        frame_id = shared_memory.write_frame(frame, metadata)

        logger.info(f"Initial stimulus frame rendered: frame_id={frame_id}")

    except Exception as e:
        logger.warning(f"Unable to render initial stimulus frame: {e}")
        raise


# =============================================================================
# Parameter Management Helpers
# =============================================================================

def _update_parameters(param_manager, ipc, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Helper for updating parameter group and publishing snapshot.

    Args:
        param_manager: Parameter manager instance
        ipc: IPC service for broadcasting updates
        cmd: Command with group_name and parameters

    Returns:
        Success/error response
    """
    group_name = cmd.get("group_name")
    updates = cmd.get("parameters", {})

    if not group_name:
        return {"success": False, "error": "group_name is required"}

    try:
        param_manager.update_parameter_group(group_name, updates)

        # Publish snapshot to frontend
        snapshot = {
            "type": "parameters_snapshot",
            "timestamp": time.time(),
            "parameters": param_manager.get_all_parameters(),
            "parameter_config": param_manager.get_parameter_info().get(
                "parameter_config", {}
            ),
        }
        ipc.send_sync_message(snapshot)

        return {
            "success": True,
            "type": "parameter_group_updated",
            "group_name": group_name,
            "message": f"Updated {group_name} parameters",
        }
    except Exception as e:
        logger.error(f"Error updating parameter group: {e}")
        return {"success": False, "error": str(e)}


def _reset_parameters(param_manager, ipc) -> Dict[str, Any]:
    """Helper for resetting parameters to defaults and publishing snapshot.

    Args:
        param_manager: Parameter manager instance
        ipc: IPC service for broadcasting updates

    Returns:
        Success/error response
    """
    try:
        param_manager.reset_to_defaults()

        # Publish snapshot to frontend
        snapshot = {
            "type": "parameters_snapshot",
            "timestamp": time.time(),
            "parameters": param_manager.get_all_parameters(),
            "parameter_config": param_manager.get_parameter_info().get(
                "parameter_config", {}
            ),
        }
        ipc.send_sync_message(snapshot)

        return {
            "success": True,
            "type": "parameters_reset",
            "message": "Parameters reset to defaults successfully",
        }
    except Exception as e:
        logger.error(f"Error resetting parameters: {e}")
        return {"success": False, "error": str(e)}


def _handle_frontend_ready(services: Dict[str, Any], cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Handle frontend_ready message, verify hardware, and send system_state: ready.

    This ensures:
    1. Frontend has subscribed to the SYNC channel
    2. All hardware is detected and verified
    3. Only then do we report ready state

    Args:
        services: Dictionary of all services (camera, ipc, param_manager, etc.)
        cmd: Command containing optional ping_id

    Returns:
        Success response
    """
    logger.info("Frontend ready - verifying hardware before sending ready state...")

    ipc = services["ipc"]
    param_manager = services["param_manager"]
    camera = services["camera"]

    # 1. Verify hardware (cameras, displays)
    hardware_check = _verify_hardware(camera, param_manager, ipc)

    if not hardware_check["success"]:
        # Hardware verification failed - send error state
        error_msg = "; ".join(hardware_check["errors"])
        logger.error(f"Hardware verification failed: {error_msg}")

        ipc.send_sync_message({
            "type": "system_state",
            "state": "error",
            "is_ready": False,
            "display_text": f"Hardware error: {error_msg}",
            "is_error": True,
            "errors": hardware_check["errors"],
            "timestamp": time.time()
        })

        return {
            "success": False,
            "type": "handshake_failed",
            "error": error_msg,
            "errors": hardware_check["errors"]
        }

    # 2. Log any warnings but continue
    if hardware_check.get("warnings"):
        for warning in hardware_check["warnings"]:
            logger.warning(f"Hardware warning: {warning}")

    # 3. Send initial parameters snapshot FIRST via SYNC channel (now with detected hardware)
    try:
        snapshot = {
            "type": "parameters_snapshot",
            "timestamp": time.time(),
            "parameters": param_manager.get_all_parameters(),
            "parameter_config": param_manager.get_parameter_info().get(
                "parameter_config", {}
            ),
        }
        ipc.send_sync_message(snapshot)
        logger.info("Sent initial parameters snapshot with detected hardware")
    except Exception as e:
        logger.error(f"Failed to send parameters snapshot: {e}")

    # 4. THEN send system_state ready message via SYNC channel WITH is_ready flag
    ready_msg = "System ready for experiments"
    if hardware_check.get("warnings"):
        ready_msg += f" (warnings: {len(hardware_check['warnings'])})"

    ipc.send_sync_message({
        "type": "system_state",
        "state": "ready",
        "is_ready": True,  # CRITICAL: Frontend needs this to transition to main UI
        "display_text": ready_msg,
        "is_error": False,
        "warnings": hardware_check.get("warnings", []),
        "timestamp": time.time()
    })
    logger.info("System ready - frontend can transition")

    logger.info("Hardware verification complete - system ready")

    return {
        "success": True,
        "type": "handshake_complete",
        "message": "Backend ready",
        "warnings": hardware_check.get("warnings", [])
    }


class ISIMacroscopeBackend:
    """Main backend application - simple event loop with handler dispatch."""

    def __init__(self, services: Dict[str, Any], handlers: Dict[str, Any]):
        """Initialize backend with services and handlers.

        Args:
            services: All instantiated services
            handlers: Command handler mapping
        """
        self.services = services
        self.handlers = handlers
        self.running = False

        logger.info("ISI Macroscope Backend initialized")

    def start(self):
        """Start the backend event loop."""
        logger.info("Starting ISI Macroscope Backend...")

        # Initialize IPC channels
        ipc = self.services["ipc"]
        from ipc.channels import ChannelType, ChannelConfig
        import zmq

        ipc.initialize_channels({
            ChannelType.CONTROL: ChannelConfig(
                channel_type=ChannelType.CONTROL,
                transport="stdin",
            ),
            ChannelType.HEALTH: ChannelConfig(
                channel_type=ChannelType.HEALTH,
                transport=ipc._transport,
                port=ipc._health_port,
                socket_type=zmq.PUB,
            ),
            ChannelType.SYNC: ChannelConfig(
                channel_type=ChannelType.SYNC,
                transport=ipc._transport,
                port=ipc._sync_port,
                socket_type=zmq.PUB,
            ),
        })

        # Send zeromq_ready message to frontend via CONTROL channel
        ipc.send_control_message({
            "type": "zeromq_ready",
            "health_port": ipc._health_port,
            "sync_port": ipc._sync_port,
        })

        # Send initial system state
        ipc.send_sync_message({
            "type": "system_state",
            "state": "initializing",
            "is_ready": False,
            "display_text": "Initializing backend systems...",
            "is_error": False,
            "timestamp": time.time()
        })

        # Start health monitoring with component health callback
        def broadcast_component_health(health_status):
            """Collect and broadcast component health status."""
            try:
                camera = self.services["camera"]
                shared_memory = self.services["shared_memory"]
                hardware_status = {
                    "multi_channel_ipc": "online",
                    "parameters": "online",
                    "display": "online",
                    "camera": "online" if camera.active_camera and camera.active_camera.isOpened() else "offline",
                    "realtime_streaming": "online" if shared_memory._stream and shared_memory._stream._running else "offline",
                    "analysis": "online",
                }

                # Broadcast via SYNC channel (not HEALTH channel)
                ipc.send_sync_message({
                    "type": "system_health",
                    "timestamp": time.time(),
                    "hardware_status": hardware_status
                })
            except Exception as e:
                logger.error(f"Error broadcasting component health: {e}", exc_info=True)

        ipc.start_health_monitoring(callback=broadcast_component_health, interval_sec=1.0)
        logger.info("Health monitoring started with component health broadcasting")

        # Render initial stimulus frame
        try:
            _render_initial_stimulus_frame(
                self.services["stimulus_generator"],
                self.services["shared_memory"]
            )
            logger.info("Initial stimulus frame rendered")
        except Exception as e:
            logger.warning(f"Failed to render initial stimulus frame: {e}")

        # Wait for frontend_ready message before sending system_state
        # (The system_state message will be sent when we receive frontend_ready)
        self.frontend_ready = False
        self.running = True
        logger.info("Backend ready - waiting for frontend handshake...")

        # Broadcast waiting_frontend state
        ipc.send_sync_message({
            "type": "system_state",
            "state": "waiting_frontend",
            "is_ready": False,
            "display_text": "Waiting for frontend connection...",
            "is_error": False,
            "timestamp": time.time()
        })

        # Simple event loop: receive → lookup → execute → respond
        while self.running:
            try:
                # Read command from stdin (IPC control channel)
                line = sys.stdin.readline()

                if not line:
                    # EOF - exit gracefully
                    break

                line = line.strip()
                if not line:
                    continue

                # Parse JSON command
                try:
                    command = json.loads(line)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    response = {
                        "success": False,
                        "error": f"Invalid JSON: {str(e)}"
                    }
                    ipc.send_control_message(response)
                    continue

                # Extract command type
                command_type = command.get("type", "")
                message_id = command.get("messageId")

                if not command_type:
                    response = {
                        "success": False,
                        "error": "Command type is required"
                    }
                    if message_id:
                        response["messageId"] = message_id
                    ipc.send_control_message(response)
                    continue

                # Lookup handler
                handler = self.handlers.get(command_type)

                if handler is None:
                    logger.warning(f"Unknown command type: {command_type}")
                    response = {
                        "success": False,
                        "error": f"Unknown command: {command_type}"
                    }
                else:
                    # Execute handler
                    try:
                        logger.info(f"Processing command: {command_type}")
                        result = handler(command)

                        # Ensure response has type field
                        if "type" not in result:
                            result["type"] = f"{command_type}_response"

                        response = result
                        logger.info(f"Command {command_type} completed")

                    except Exception as e:
                        logger.error(f"Handler error for {command_type}: {e}", exc_info=True)
                        response = {
                            "success": False,
                            "error": str(e),
                            "type": f"{command_type}_response"
                        }

                # Add message ID for correlation
                if message_id:
                    response["messageId"] = message_id

                # Send response
                ipc.send_control_message(response)

            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                break
            except Exception as e:
                logger.error(f"Event loop error: {e}", exc_info=True)
                continue

        # Cleanup
        self.shutdown()

    def shutdown(self):
        """Shutdown the backend gracefully."""
        logger.info("Shutting down ISI Macroscope Backend...")
        self.running = False

        # Stop services
        camera = self.services.get("camera")
        if camera:
            camera.shutdown()

        acquisition = self.services.get("acquisition")
        if acquisition and acquisition.is_running:
            acquisition.stop_acquisition()

        ipc = self.services.get("ipc")
        if ipc:
            ipc.cleanup()

        shared_memory = self.services.get("shared_memory")
        if shared_memory:
            shared_memory.cleanup()

        logger.info("Backend shutdown complete")

    def handle_signal(self, signum, frame):
        """Handle system signals for graceful shutdown."""
        logger.info(f"Received signal {signum} - shutting down...")
        self.running = False


def main():
    """Main entry point - composition root and event loop."""
    # Setup logging using centralized configuration
    from logging_config import configure_logging
    configure_logging(level=logging.WARNING)  # Only show warnings and errors

    logger.info("=" * 80)
    logger.info("ISI Macroscope Control System - Refactored Backend")
    logger.info("=" * 80)

    try:
        # 1. Load configuration
        config_path = Path(__file__).parent.parent / "config" / "isi_parameters.json"

        if not config_path.exists():
            logger.error(f"Configuration file not found: {config_path}")
            logger.info("Using default configuration")
            config = AppConfig.default()
        else:
            config = AppConfig.from_file(str(config_path))
            logger.info(f"Loaded configuration from {config_path}")

        # 2. Create all services (composition root)
        services = create_services(config)

        # 3. Create handler mapping (KISS pattern)
        handlers = create_handlers(services)

        # 4. Create backend instance
        backend = ISIMacroscopeBackend(services, handlers)

        # 5. Setup signal handlers
        signal.signal(signal.SIGINT, backend.handle_signal)
        signal.signal(signal.SIGTERM, backend.handle_signal)

        # 6. Start event loop
        backend.start()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
