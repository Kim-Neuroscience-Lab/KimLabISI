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
from acquisition.recorder import create_session_recorder
from acquisition.modes import PlaybackModeController
from acquisition.unified_stimulus import UnifiedStimulusController
from analysis.manager import AnalysisManager
from analysis.pipeline import AnalysisPipeline
from analysis.renderer import AnalysisRenderer

# Import parameter manager
from parameters import ParameterManager

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
        sync_port=config.ipc.sync_port,
    )
    logger.info("  [1/11] MultiChannelIPC created")

    shared_memory = SharedMemoryService(
        stream_name=config.shared_memory.stream_name,
        buffer_size_mb=config.shared_memory.buffer_size_mb,
        metadata_port=config.shared_memory.metadata_port,
        camera_metadata_port=config.shared_memory.camera_metadata_port,
        analysis_metadata_port=config.shared_memory.analysis_metadata_port,
    )
    logger.info("  [2/11] SharedMemoryService created")

    # Parameter manager (refactored to use ParameterManager from parameters package)
    param_manager = ParameterManager(
        config_file=config.parameters.file_path.name,
        config_dir=str(config.parameters.file_path.parent),
    )
    logger.info("  [3/11] ParameterManager created")

    # =========================================================================
    # Layer 2: Core systems (depend on infrastructure)
    # =========================================================================

    stimulus_generator = StimulusGenerator(param_manager=param_manager, logger=logger)
    logger.info("  [4/11] StimulusGenerator created")

    # Create unified stimulus controller (replaces preview_stimulus_loop)
    unified_stimulus = UnifiedStimulusController(
        stimulus_generator=stimulus_generator,
        param_manager=param_manager,
        shared_memory=shared_memory,
        ipc=ipc,
    )
    logger.info("  [4.5/11] UnifiedStimulusController created")

    # Create acquisition subsystems needed by camera manager
    # (moved from Layer 4 to allow proper camera construction)
    sync_tracker = TimestampSynchronizationTracker()
    logger.info("  [5a/11] TimestampSynchronizationTracker created")

    camera = CameraManager(
        config=param_manager,  # CameraManager expects 'config' parameter (used to access parameters via get_parameter_group)
        ipc=ipc,
        shared_memory=shared_memory,
        synchronization_tracker=sync_tracker,
    )
    logger.info("  [5/11] CameraManager created")

    # =========================================================================
    # Layer 3: Analysis system (depends on infrastructure)
    # =========================================================================

    analysis_pipeline = AnalysisPipeline(config=config.analysis)
    logger.info("  [6/11] AnalysisPipeline created")

    analysis_renderer = AnalysisRenderer(
        config=config.analysis, shared_memory=shared_memory
    )
    logger.info("  [7/11] AnalysisRenderer created")

    analysis_manager = AnalysisManager(
        param_manager=param_manager,
        ipc=ipc,
        shared_memory=shared_memory,
        pipeline=analysis_pipeline,
    )
    # Note: Renderer callback can be wired later if needed for incremental visualization
    logger.info("  [8/11] AnalysisManager created")

    # =========================================================================
    # Layer 4: Acquisition subsystems (depend on core systems)
    # =========================================================================

    state_coordinator = AcquisitionStateCoordinator()
    logger.info("  [9/11] AcquisitionStateCoordinator created")

    # Playback controller (shared between IPC handlers and acquisition manager)
    playback_controller = PlaybackModeController(
        state_coordinator=state_coordinator, shared_memory=shared_memory, ipc=ipc
    )
    logger.info("  [10/11] PlaybackModeController created")

    # =========================================================================
    # Layer 5: Acquisition manager (depends on all acquisition subsystems)
    # =========================================================================

    acquisition = AcquisitionManager(
        ipc=ipc,
        shared_memory=shared_memory,
        stimulus_generator=stimulus_generator,
        camera=camera,
        synchronization_tracker=sync_tracker,
        state_coordinator=state_coordinator,
        unified_stimulus=unified_stimulus,  # NEW: Unified stimulus for both preview and record
        data_recorder=None,  # Created dynamically when acquisition starts
        param_manager=param_manager,
    )
    # Wire playback controller (property injection needed for circular dependency)
    acquisition.playback_controller = playback_controller
    logger.info("  [11/11] AcquisitionManager created")

    logger.info("All services created successfully")

    return {
        "config": config,
        "ipc": ipc,
        "shared_memory": shared_memory,
        "camera": camera,
        "stimulus_generator": stimulus_generator,
        "unified_stimulus": unified_stimulus,
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
    unified_stimulus = services["unified_stimulus"]
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
        "detect_cameras": lambda cmd: (
            lambda: {
                "success": True,
                "cameras": (
                    camera.get_camera_list()
                    if not cmd.get("force", False)
                    else [c.to_dict() for c in camera.detect_cameras(force=True)]
                ),
            }
        )(),
        "get_camera_capabilities": lambda cmd: {
            "success": True,
            "capabilities": camera.get_camera_capabilities(cmd.get("camera_name")),
        },
        "camera_stream_started": lambda cmd: {
            "success": True,
            "message": "Camera stream started",
        },
        "camera_stream_stopped": lambda cmd: {
            "success": True,
            "message": "Camera stream stopped",
        },
        "camera_capture": lambda cmd: {
            "success": True,
            "message": "Camera capture triggered",
        },
        "start_camera_acquisition": lambda cmd: (
            lambda result: {
                "success": result,
                "message": (
                    "Camera acquisition started"
                    if result
                    else "Failed to start camera acquisition"
                ),
            }
        )(camera.start_acquisition()),
        "stop_camera_acquisition": lambda cmd: (
            {"success": True, "message": "Camera acquisition stopped"}
            if not camera.stop_acquisition()
            else {"success": True}
        ),
        "get_camera_histogram": lambda cmd: (
            camera.generate_luminance_histogram(camera.get_latest_frame())
            if camera.get_latest_frame() is not None
            else {"error": "No frame available"}
        ),
        "get_synchronization_data": lambda cmd: {
            "success": True,
            **acquisition.get_synchronization_data(),
        },
        "get_correlation_data": lambda cmd: {
            "success": True,
            **acquisition.get_synchronization_data(),
        },  # Backward compatibility alias
        # =====================================================================
        # Acquisition commands
        # =====================================================================
        "start_acquisition": lambda cmd: acquisition.start_acquisition(
            param_manager=param_manager
        ),
        "stop_acquisition": lambda cmd: acquisition.stop_acquisition(),
        "get_acquisition_status": lambda cmd: {
            "success": True,
            **acquisition.get_status(),
        },
        "get_presentation_state": lambda cmd: acquisition.get_presentation_state(),
        "set_acquisition_mode": lambda cmd: acquisition.set_mode(
            mode=cmd.get("mode", "preview"),
            direction=cmd.get("direction"),
            frame_index=cmd.get("frame_index"),
            show_mask=cmd.get("show_mask"),
            param_manager=param_manager,
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
            direction=cmd.get("direction"), frame_index=cmd.get("frame_index", 0)
        ),
        "start_playback_sequence": lambda cmd: playback.start_playback_sequence(),
        "stop_playback_sequence": lambda cmd: playback.stop_playback_sequence(),
        # =====================================================================
        # Stimulus commands
        # =====================================================================
        "get_stimulus_parameters": lambda cmd: _get_stimulus_parameters(param_manager),
        "update_stimulus_parameters": lambda cmd: _update_stimulus_parameters(
            param_manager, cmd
        ),
        "get_spatial_configuration": lambda cmd: _get_spatial_configuration(
            param_manager
        ),
        "update_spatial_configuration": lambda cmd: _update_spatial_configuration(
            param_manager, cmd
        ),
        "get_stimulus_info": lambda cmd: _get_stimulus_info(stimulus_generator, cmd),
        "get_stimulus_frame": lambda cmd: _get_stimulus_frame(
            stimulus_generator, shared_memory, cmd
        ),
        "generate_stimulus_preview": lambda cmd: _generate_stimulus_preview(
            stimulus_generator, cmd
        ),
        "get_stimulus_status": lambda cmd: _get_stimulus_status(),
        "set_presentation_stimulus_enabled": lambda cmd: _set_presentation_stimulus_enabled(
            ipc, unified_stimulus, param_manager, cmd
        ),
        "display_timestamp": lambda cmd: _handle_display_timestamp(shared_memory, cmd),
        # Unified stimulus controller commands
        "unified_stimulus_pregenerate": lambda cmd: _unified_stimulus_pregenerate_handler(
            unified_stimulus, cmd
        ),
        "unified_stimulus_start_playback": lambda cmd: _unified_stimulus_start_playback_handler(
            unified_stimulus, param_manager, cmd
        ),
        "unified_stimulus_stop_playback": lambda cmd: unified_stimulus.stop_playback(),
        "unified_stimulus_get_status": lambda cmd: {
            "success": True,
            **unified_stimulus.get_status(),
        },
        "unified_stimulus_get_frame": lambda cmd: _unified_stimulus_get_frame(
            unified_stimulus, shared_memory, cmd
        ),
        "unified_stimulus_clear_log": lambda cmd: (
            {"success": True, "message": "Display log cleared"}
            if not unified_stimulus.clear_display_log(cmd.get("direction"))
            else {"success": True}
        ),
        "unified_stimulus_save_library": lambda cmd: unified_stimulus.save_library_to_disk(
            save_path=cmd.get("save_path")
        ),
        "unified_stimulus_load_library": lambda cmd: unified_stimulus.load_library_from_disk(
            load_path=cmd.get("load_path"), force=cmd.get("force", False)
        ),
        # Preview mode handlers (proper integration with acquisition sequence)
        "start_preview": lambda cmd: _start_preview_mode(
            acquisition, param_manager, cmd
        ),
        "stop_preview": lambda cmd: _stop_preview_mode(acquisition, cmd),
        # =====================================================================
        # Display commands
        # =====================================================================
        "detect_displays": lambda cmd: _detect_displays(param_manager, cmd),
        "get_display_capabilities": lambda cmd: _get_display_capabilities(cmd),
        "select_display": lambda cmd: _select_display(param_manager, cmd),
        "test_presentation_monitor": lambda cmd: _test_presentation_monitor(
            ipc, shared_memory, param_manager, cmd
        ),
        "stop_monitor_test": lambda cmd: _stop_monitor_test(ipc, cmd),
        # =====================================================================
        # Analysis commands
        # =====================================================================
        "start_analysis": lambda cmd: analysis.start_analysis(cmd.get("session_path")),
        "stop_analysis": lambda cmd: analysis.stop_analysis(),
        "get_analysis_status": lambda cmd: analysis.get_status(),
        "capture_anatomical": lambda cmd: _capture_anatomical(camera, param_manager),
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
        "get_parameter_group": lambda cmd: (
            {
                "success": True,
                "type": "parameter_group",
                "group_name": cmd.get("group_name"),
                "parameters": param_manager.get_parameter_group(cmd.get("group_name")),
            }
            if cmd.get("group_name")
            else {"success": False, "error": "group_name required"}
        ),
        "update_parameter_group": lambda cmd: _update_parameters(
            param_manager, ipc, cmd
        ),
        "reset_to_defaults": lambda cmd: _reset_parameters(param_manager, ipc),
        "reload_parameters": lambda cmd: _reload_parameters(param_manager, ipc),
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
            "services": list(services.keys()),
        },
        # =====================================================================
        # Frontend handshake
        # =====================================================================
        "frontend_ready": lambda cmd: _handle_frontend_ready(services, cmd),
        "shared_memory_readers_ready": lambda cmd: _handle_shared_memory_ready(
            services, cmd
        ),
        "camera_subscriber_confirmed": lambda cmd: _handle_camera_subscriber_confirmed(
            services, cmd
        ),
    }

    logger.info(f"Created {len(handlers)} command handlers")
    return handlers


# =============================================================================
# Stimulus Handler Helpers
# =============================================================================


def _get_stimulus_parameters(param_manager) -> Dict[str, Any]:
    """Get current stimulus parameters from ParameterManager (source of truth)."""
    stimulus_params = param_manager.get_parameter_group("stimulus")
    return {"parameters": stimulus_params}


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

    dataset_info = stimulus_generator.get_dataset_info(direction)

    if "error" in dataset_info:
        return {"success": False, "error": dataset_info["error"]}

    return dataset_info


def _get_stimulus_frame(
    stimulus_generator, shared_memory, cmd: Dict[str, Any]
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
        total_frames=total_frames,
    )

    # Write to shared memory
    frame_id = shared_memory.write_frame(frame, metadata)

    return {"success": True, "frame_id": frame_id, "frame_info": metadata}


def _generate_stimulus_preview(
    stimulus_generator, cmd: Dict[str, Any]
) -> Dict[str, Any]:
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
_stimulus_status = {
    "is_presenting": False,
    "current_session": None,
    "presentation_display_enabled": False,  # Controls whether stimulus shows on presentation monitor
}


def _get_stimulus_status() -> Dict[str, Any]:
    """Get stimulus status."""
    return {"status": _stimulus_status.copy()}


def _set_presentation_stimulus_enabled(
    ipc, unified_stimulus, param_manager, cmd: Dict[str, Any]
) -> Dict[str, Any]:
    """Enable or disable stimulus display on presentation monitor using UnifiedStimulusController.

    This controls whether the presentation window should show stimulus frames.
    Used to distinguish between preview mode (stimulus OFF on presentation)
    and record mode (stimulus ON on presentation).

    Args:
        ipc: IPC service for broadcasting state changes
        unified_stimulus: UnifiedStimulusController instance for playback
        param_manager: ParameterManager for getting monitor FPS
        cmd: Command with 'enabled' boolean parameter

    Returns:
        Success response
    """
    enabled = cmd.get("enabled", False)

    # Update global status
    _stimulus_status["presentation_display_enabled"] = enabled

    if enabled:
        # Check if library is loaded - ERROR if not (no auto-generation)
        status = unified_stimulus.get_status()
        if not status.get("library_loaded"):
            logger.warning(
                "Stimulus library not pre-generated - cannot enable presentation"
            )
            return {
                "success": False,
                "error": "Stimulus library not pre-generated. Please visit Stimulus Generation tab and click 'Pre-Generate All Directions' before enabling presentation display.",
            }

        # Get monitor FPS from parameters (ISSUE-012 FIX: No hardcoded defaults)
        monitor_params = param_manager.get_parameter_group("monitor")
        monitor_fps = monitor_params.get("monitor_fps")
        if (
            monitor_fps is None
            or not isinstance(monitor_fps, (int, float))
            or monitor_fps <= 0
        ):
            raise RuntimeError(
                "monitor_fps is required but not configured in param_manager. "
                "Please set monitor.monitor_fps parameter to match your hardware. "
                f"Received: {monitor_fps}"
            )
        monitor_fps = float(monitor_fps)

        # Start unified stimulus playback
        result = unified_stimulus.start_playback(
            direction="LR", monitor_fps=monitor_fps
        )
        if not result.get("success"):
            logger.error(f"Failed to start unified stimulus: {result.get('error')}")
            return {
                "success": False,
                "error": f"Failed to start stimulus: {result.get('error')}",
            }
        logger.info(
            f"Started unified stimulus playback: {result.get('total_frames')} frames at {result.get('fps')} fps"
        )
    else:
        # Stop unified stimulus playback
        result = unified_stimulus.stop_playback()
        if not result.get("success") and result.get("error") != "No playback running":
            logger.warning(f"Failed to stop unified stimulus: {result.get('error')}")
        logger.info("Unified stimulus playback stopped")

    # Broadcast state change via SYNC channel
    ipc.send_sync_message(
        {
            "type": "presentation_stimulus_state",
            "enabled": enabled,
            "timestamp": time.time(),
        }
    )

    return {"success": True, "enabled": enabled}


def _handle_display_timestamp(shared_memory, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Handle display timestamp from frontend."""
    frame_id = cmd.get("frame_id")
    display_timestamp_us = cmd.get("display_timestamp_us")

    if frame_id is None or display_timestamp_us is None:
        return {"success": False, "error": "Missing frame_id or display_timestamp_us"}

    # Store timestamp
    shared_memory.set_stimulus_timestamp(display_timestamp_us, frame_id)

    return {"success": True}


def _unified_stimulus_start_playback_handler(
    unified_stimulus, param_manager, cmd: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle unified_stimulus_start_playback command with proper parameter management.

    ISSUE-012 FIX: If monitor_fps is not provided in the command, get it from param_manager
    with NO hardcoded defaults.

    Args:
        unified_stimulus: UnifiedStimulusController instance
        param_manager: ParameterManager for getting monitor FPS
        cmd: Command with optional direction and monitor_fps

    Returns:
        Success response from unified_stimulus.start_playback()
    """
    direction = cmd.get("direction", "LR")

    # Get monitor_fps from command OR param_manager (ISSUE-012 FIX: No hardcoded defaults)
    monitor_fps = cmd.get("monitor_fps")
    if monitor_fps is None:
        # Command didn't provide it, get from param_manager
        monitor_params = param_manager.get_parameter_group("monitor")
        monitor_fps = monitor_params.get("monitor_fps")
        if (
            monitor_fps is None
            or not isinstance(monitor_fps, (int, float))
            or monitor_fps <= 0
        ):
            raise RuntimeError(
                "monitor_fps is required but not configured in param_manager and not provided in command. "
                "Please set monitor.monitor_fps parameter to match your hardware. "
                f"Received: {monitor_fps}"
            )
        monitor_fps = float(monitor_fps)

    return unified_stimulus.start_playback(direction=direction, monitor_fps=monitor_fps)


def _unified_stimulus_get_frame(
    unified_stimulus, shared_memory, cmd: Dict[str, Any]
) -> Dict[str, Any]:
    """Get frame from unified stimulus controller for viewport display.

    Args:
        unified_stimulus: UnifiedStimulusController instance
        shared_memory: SharedMemoryService for frame publishing
        cmd: Command with direction and frame_index

    Returns:
        Success response with frame_id
    """
    direction = cmd.get("direction")
    frame_index = cmd.get("frame_index", 0)

    if not direction:
        return {"success": False, "error": "direction is required"}

    # Get decompressed RGBA frame
    frame = unified_stimulus.get_frame_for_viewport(direction, frame_index)

    if frame is None:
        return {
            "success": False,
            "error": f"Frame not available: {direction}[{frame_index}]",
        }

    # Write to shared memory
    metadata = {
        "frame_index": frame_index,
        "direction": direction,
        "source": "unified_stimulus",
    }
    frame_id = shared_memory.write_frame(frame, metadata, channel="stimulus")

    return {
        "success": True,
        "frame_id": frame_id,
        "direction": direction,
        "frame_index": frame_index,
    }


def _unified_stimulus_pregenerate_handler(
    unified_stimulus, cmd: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle unified_stimulus_pregenerate command with automatic library saving.

    Pre-generates all stimulus directions and automatically saves to disk for persistence.
    This ensures the load feature always has a dataset available if one has ever been generated.

    Args:
        unified_stimulus: UnifiedStimulusController instance
        cmd: Command (no parameters needed)

    Returns:
        Success response with generation statistics and save status
    """
    # Pre-generate all directions
    result = unified_stimulus.pre_generate_all_directions()

    # If pre-generation succeeded, automatically save to disk IN BACKGROUND
    if result.get("success"):
        logger.info("Pre-generation successful, starting background auto-save...")

        # Start background save thread (non-blocking)
        def background_save():
            try:
                save_result = unified_stimulus.save_library_to_disk()
                if save_result.get("success"):
                    logger.info(
                        f"✅ Library auto-saved to: {save_result.get('save_path')}"
                    )
                else:
                    logger.warning(f"⚠️ Auto-save failed: {save_result.get('error')}")
            except Exception as e:
                logger.error(f"❌ Auto-save error: {e}", exc_info=True)

        import threading

        save_thread = threading.Thread(
            target=background_save, name="AutoSave", daemon=True
        )
        save_thread.start()

        # Return immediately without waiting for save to complete
        result["auto_save_started"] = True
        result["auto_save_note"] = "Saving in background (non-blocking)"
    else:
        # Pre-generation failed, no save attempted
        result["auto_save_started"] = False

    return result


def _start_preview_mode(
    acquisition, param_manager, cmd: Dict[str, Any]
) -> Dict[str, Any]:
    """Start preview mode - runs full acquisition sequence without data recording.

    Preview mode executes the complete experimental protocol:
    - Initial baseline
    - All directions × all cycles with between-trial intervals
    - Final baseline

    NO data is saved to disk. This allows testing the complete protocol before recording.

    Args:
        acquisition: AcquisitionManager instance
        param_manager: ParameterManager for acquisition parameters
        cmd: Command dictionary (unused for preview mode)

    Returns:
        Success response or error
    """
    # Check if library loaded - ERROR if not (no auto-generation)
    status = acquisition.unified_stimulus.get_status()
    if not status.get("library_loaded"):
        logger.warning("Stimulus library not pre-generated - cannot start preview")
        return {
            "success": False,
            "error": "Stimulus library not pre-generated. Please visit Stimulus Generation tab and click 'Pre-Generate All Directions' before starting preview mode.",
        }

    # Start acquisition sequence WITHOUT data recording
    result = acquisition.start_acquisition(
        param_manager=param_manager, record_data=False
    )

    if result.get("success"):
        logger.info(
            "Preview mode started - running full acquisition sequence without recording"
        )

    return result


def _stop_preview_mode(acquisition, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Stop preview mode by stopping the acquisition sequence.

    CRITICAL: Camera is NOT stopped here. Per docs/components/acquisition-system.md lines 49-58:
    - Camera preview should be "always showing when camera connected"
    - Camera runs continuously (not just during acquisition)
    - Camera provides best-effort preview at all times

    Args:
        acquisition: AcquisitionManager instance
        cmd: Command (no parameters needed)

    Returns:
        Success response
    """
    # Stop acquisition sequence (unified stimulus playback will stop)
    result = acquisition.stop_acquisition()

    # Camera continues streaming for continuous preview (per architecture docs)
    # DO NOT stop camera here - it should run continuously
    logger.info(
        "Preview mode stopped (camera continues streaming for continuous preview)"
    )

    return result


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
        "selected_display": displays[0].identifier if displays else None,
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

    return {"success": True, "capabilities": display.to_dict()}


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

    return {"success": True, "selected_display": display_id}


def _test_presentation_monitor(
    ipc, shared_memory, param_manager, cmd: Dict[str, Any]
) -> Dict[str, Any]:
    """Display test pattern on presentation monitor for verification."""
    import numpy as np

    try:
        # Get monitor parameters
        monitor_params = param_manager.get_parameter_group("monitor")

        # ISSUE-012 FIX: No hardcoded defaults for resolution
        monitor_width = monitor_params.get("monitor_width_px")
        if (
            monitor_width is None
            or not isinstance(monitor_width, (int, float))
            or monitor_width <= 0
        ):
            raise RuntimeError(
                "monitor_width_px is required but not configured in param_manager. "
                "Please set monitor.monitor_width_px parameter to match your hardware. "
                f"Received: {monitor_width}"
            )
        monitor_width = int(monitor_width)

        monitor_height = monitor_params.get("monitor_height_px")
        if (
            monitor_height is None
            or not isinstance(monitor_height, (int, float))
            or monitor_height <= 0
        ):
            raise RuntimeError(
                "monitor_height_px is required but not configured in param_manager. "
                "Please set monitor.monitor_height_px parameter to match your hardware. "
                f"Received: {monitor_height}"
            )
        monitor_height = int(monitor_height)

        monitor_name = monitor_params.get("selected_display", "Unknown")

        # ISSUE-012 FIX: No hardcoded defaults for FPS
        monitor_fps = monitor_params.get("monitor_fps")
        if (
            monitor_fps is None
            or not isinstance(monitor_fps, (int, float))
            or monitor_fps <= 0
        ):
            raise RuntimeError(
                "monitor_fps is required but not configured in param_manager. "
                "Please set monitor.monitor_fps parameter to match your hardware. "
                f"Received: {monitor_fps}"
            )
        monitor_fps = float(monitor_fps)

        logger.info(
            f"Creating monitor test pattern: {monitor_width}x{monitor_height} @ {monitor_fps}Hz on {monitor_name}"
        )

        # Create test pattern frame (RGBA)
        # Quadrants: Red (top-left), Green (top-right), Blue (bottom-left), White (bottom-right)
        test_frame = np.zeros((monitor_height, monitor_width, 4), dtype=np.uint8)

        half_h = monitor_height // 2
        half_w = monitor_width // 2

        # Red quadrant (top-left)
        test_frame[:half_h, :half_w, 0] = 255  # R
        test_frame[:half_h, :half_w, 3] = 255  # A

        # Green quadrant (top-right)
        test_frame[:half_h, half_w:, 1] = 255  # G
        test_frame[:half_h, half_w:, 3] = 255  # A

        # Blue quadrant (bottom-left)
        test_frame[half_h:, :half_w, 2] = 255  # B
        test_frame[half_h:, :half_w, 3] = 255  # A

        # White quadrant (bottom-right)
        test_frame[half_h:, half_w:, :] = 255  # All channels

        # Write test frame to stimulus shared memory channel
        metadata = {
            "frame_id": 0,
            "timestamp_us": int(time.time() * 1_000_000),
            "width_px": monitor_width,
            "height_px": monitor_height,
            "monitor_name": monitor_name,
            "monitor_fps": monitor_fps,
            "test_pattern": True,
        }

        frame_id = shared_memory.write_frame(
            frame=test_frame, metadata=metadata, channel="stimulus"
        )

        # Send sync message to frontend
        ipc.send_sync_message(
            {
                "type": "monitor_test_started",
                "monitor_name": monitor_name,
                "resolution": f"{monitor_width}x{monitor_height}",
                "refresh_rate": f"{monitor_fps} Hz",
                "frame_id": frame_id,
            }
        )

        logger.info(
            f"Monitor test pattern sent: frame_id={frame_id}, {monitor_width}x{monitor_height} @ {monitor_fps}Hz"
        )

        return {
            "success": True,
            "monitor_name": monitor_name,
            "resolution": f"{monitor_width}x{monitor_height}",
            "refresh_rate": f"{monitor_fps} Hz",
            "frame_id": frame_id,
        }

    except Exception as e:
        logger.error(f"Failed to start monitor test: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def _stop_monitor_test(ipc, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Stop monitor test pattern."""
    try:
        # Send sync message to clear test pattern
        ipc.send_sync_message({"type": "monitor_test_stopped"})

        logger.info("Monitor test stopped")

        return {"success": True}

    except Exception as e:
        logger.error(f"Failed to stop monitor test: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# =============================================================================
# Analysis Handler Helpers
# =============================================================================


def _capture_anatomical(camera, param_manager) -> Dict[str, Any]:
    """Capture anatomical reference frame and save immediately."""
    import numpy as np
    from pathlib import Path

    try:
        frame = camera.get_latest_frame()
        if frame is None:
            return {"success": False, "error": "No camera frame available"}

        # Determine session path (use current session or create default location)
        session_params = param_manager.get_parameter_group("session")
        session_name = session_params.get("session_name", f"session_{int(time.time())}")

        # Create session directory if it doesn't exist
        session_dir = Path(__file__).parent.parent / "data" / "sessions" / session_name
        session_dir.mkdir(parents=True, exist_ok=True)

        # Save anatomical frame as .npy file
        anatomical_path = session_dir / "anatomical.npy"
        np.save(str(anatomical_path), frame)

        logger.info(f"Anatomical frame captured and saved: {anatomical_path}")
        logger.info(f"  Shape: {frame.shape}, dtype: {frame.dtype}")

        return {
            "success": True,
            "message": "Anatomical frame captured and saved",
            "path": str(anatomical_path),
            "shape": list(frame.shape),
            "dtype": str(frame.dtype),
        }
    except Exception as e:
        logger.error(f"Error capturing anatomical frame: {e}", exc_info=True)
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
            return {
                "success": False,
                "error": f"Analysis results not found: {results_dir}",
            }

        # Scan for available layers
        primary_layers = []
        advanced_layers = []
        has_anatomical = False
        shape = None

        # Check for primary result layers
        for layer_file in [
            "azimuth_map.npy",
            "elevation_map.npy",
            "sign_map.npy",
            "boundary_map.npy",
        ]:
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
        for layer_file in [
            "magnitude_LR.npy",
            "phase_LR.npy",
            "magnitude_RL.npy",
            "phase_RL.npy",
            "magnitude_TB.npy",
            "phase_TB.npy",
            "magnitude_BT.npy",
            "phase_BT.npy",
        ]:
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
            "has_anatomical": has_anatomical,
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
        return {"success": True, "layer_name": layer_name, "layer_data": {}}
    except Exception as e:
        logger.error(f"Error getting analysis layer: {e}")
        return {"success": False, "error": str(e)}


def _get_analysis_composite_image(renderer, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Render composite analysis image with layer controls.

    Uses shared memory for efficient frame transfer (just like stimulus frames).
    Returns frame_id instead of base64-encoded image data.
    """
    import numpy as np
    import h5py
    from pathlib import Path

    logger.info(f"get_analysis_composite_image called with cmd: {cmd.keys()}")

    try:
        session_path = cmd.get("session_path")
        if not session_path:
            logger.error("session_path is required but not provided")
            return {"success": False, "error": "session_path is required"}

        logger.info(f"Loading analysis from: {session_path}")
        layers = cmd.get("layers", {})

        # Load analysis results from HDF5 file
        results_file = Path(session_path) / "analysis_results" / "analysis_results.h5"
        if not results_file.exists():
            return {
                "success": False,
                "error": f"Analysis results not found: {results_file}",
            }

        # Load result arrays (explicitly initialize to None)
        anatomical = None
        signal_layer = None
        overlay_layer = None

        with h5py.File(results_file, "r") as f:
            # Load anatomical if visible
            if layers.get("anatomical", {}).get("visible", True):
                anatomical_path = Path(session_path) / "anatomical.npy"
                if anatomical_path.exists():
                    anatomical = np.load(str(anatomical_path))

            # Load signal layer if visible
            signal_config = layers.get("signal", {})
            if signal_config.get("visible", True):
                signal_type = signal_config.get("type", "azimuth")

                # Map signal type to HDF5 dataset path and rendering type
                # Format: signal_type -> (hdf5_path, render_type)
                signal_mapping = {
                    # Primary retinotopy maps
                    "azimuth": ("azimuth_map", "azimuth"),
                    "elevation": ("elevation_map", "elevation"),
                    # VFS maps (visual field sign) - 3 variants
                    "raw_vfs_map": ("raw_vfs_map", "sign"),
                    "magnitude_vfs_map": ("magnitude_vfs_map", "sign"),
                    "statistical_vfs_map": ("statistical_vfs_map", "sign"),
                    "sign": ("sign_map", "sign"),  # Legacy fallback
                    # Individual direction phase maps
                    "LR_phase_map": ("phase_maps/LR", "phase"),
                    "RL_phase_map": ("phase_maps/RL", "phase"),
                    "TB_phase_map": ("phase_maps/TB", "phase"),
                    "BT_phase_map": ("phase_maps/BT", "phase"),
                    # Individual direction magnitude maps
                    "LR_magnitude_map": ("magnitude_maps/LR", "magnitude"),
                    "RL_magnitude_map": ("magnitude_maps/RL", "magnitude"),
                    "TB_magnitude_map": ("magnitude_maps/TB", "magnitude"),
                    "BT_magnitude_map": ("magnitude_maps/BT", "magnitude"),
                    # Individual direction coherence maps
                    "LR_coherence_map": ("coherence_maps/LR", "coherence"),
                    "RL_coherence_map": ("coherence_maps/RL", "coherence"),
                    "TB_coherence_map": ("coherence_maps/TB", "coherence"),
                    "BT_coherence_map": ("coherence_maps/BT", "coherence"),
                }

                # Get dataset path and render type
                dataset_info = signal_mapping.get(
                    signal_type, ("azimuth_map", "azimuth")
                )
                dataset_name, render_type = dataset_info

                # Try to load the dataset
                signal_data = None
                if dataset_name in f:
                    signal_data = f[dataset_name][:]
                    logger.info(
                        f"Loaded signal layer: {dataset_name}, shape: {signal_data.shape}"
                    )
                else:
                    logger.warning(f"Dataset not found: {dataset_name}")

                if signal_data is not None:
                    # CRITICAL: Ensure C-contiguous array from HDF5
                    # HDF5 may return Fortran-ordered arrays causing stride issues
                    if not signal_data.flags["C_CONTIGUOUS"]:
                        signal_data = np.ascontiguousarray(signal_data)

                    # Render signal layer based on render type
                    if render_type == "azimuth":
                        signal_layer = renderer.render_retinotopic_map(
                            signal_data, "azimuth"
                        )
                    elif render_type == "elevation":
                        signal_layer = renderer.render_retinotopic_map(
                            signal_data, "elevation"
                        )
                    elif render_type == "sign":
                        signal_layer = renderer.render_sign_map(signal_data)
                    elif render_type == "phase":
                        # Phase maps use HSV colormap (cyclic hue for phase angle)
                        signal_layer = renderer.render_phase_map(signal_data)
                    elif render_type == "magnitude":
                        signal_layer = renderer.render_amplitude_map(signal_data)
                    elif render_type == "coherence":
                        # Coherence maps use grayscale rendering (amplitude map also works for this)
                        signal_layer = renderer.render_amplitude_map(signal_data)
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
                    if "boundary_map" in f:
                        boundary_data = f["boundary_map"][:]

                        # CRITICAL: Ensure C-contiguous array from HDF5
                        if not boundary_data.flags["C_CONTIGUOUS"]:
                            boundary_data = np.ascontiguousarray(boundary_data)

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
            if anatomical is not None and layers.get("anatomical", {}).get(
                "visible", True
            ):
                anatomical_alpha = layers.get("anatomical", {}).get("alpha", 0.5)
                if anatomical.ndim == 2:
                    # Convert grayscale to RGB
                    anatomical_rgb = np.stack([anatomical] * 3, axis=-1).astype(
                        np.float32
                    )
                else:
                    anatomical_rgb = anatomical[:, :, :3].astype(np.float32)

                # Blend anatomical with black background
                composite = anatomical_rgb * anatomical_alpha

            # Blend signal layer on top if VISIBLE
            if layers.get("signal", {}).get("visible", True):
                signal_alpha = layers.get("signal", {}).get("alpha", 0.8)

                # Handle RGBA signal layers (with transparency for masked regions)
                if signal_layer.shape[-1] == 4:
                    # Extract alpha channel from signal layer (transparency for NaN/masked regions)
                    signal_layer_alpha = (
                        signal_layer[:, :, 3:4].astype(np.float32) / 255.0
                    )
                    signal_rgb = signal_layer[:, :, :3].astype(np.float32)

                    # Combine user alpha with layer alpha (multiply them)
                    combined_alpha = signal_layer_alpha * signal_alpha

                    # Blend with composite using combined alpha
                    composite = (
                        composite * (1.0 - combined_alpha) + signal_rgb * combined_alpha
                    )
                else:
                    # Legacy RGB handling (no transparency)
                    composite = (
                        composite * (1.0 - signal_alpha)
                        + signal_layer.astype(np.float32) * signal_alpha
                    )

            # Add overlay layer on top if VISIBLE
            if (
                overlay_layer is not None
                and overlay_layer.shape[-1] == 4
                and layers.get("overlay", {}).get("visible", True)
            ):
                overlay_alpha = layers.get("overlay", {}).get("alpha", 1.0)
                alpha_channel = (
                    overlay_layer[:, :, 3:4].astype(np.float32) / 255.0
                ) * overlay_alpha
                composite = (
                    composite * (1.0 - alpha_channel)
                    + overlay_layer[:, :, :3].astype(np.float32) * alpha_channel
                )

            # Convert back to uint8
            composite = np.clip(composite, 0, 255).astype(np.uint8)

            # CRITICAL: Ensure C-contiguous memory layout before writing to shared memory
            # Non-contiguous arrays cause horizontal tearing artifacts when read
            if not composite.flags["C_CONTIGUOUS"]:
                composite = np.ascontiguousarray(composite)

            # Write to shared memory on dedicated analysis channel
            frame_id = renderer.shared_memory.write_analysis_frame(
                composite, source="analysis_composite", session_path=session_path
            )

            logger.info(
                f"Composite written to shared memory: frame_id={frame_id}, size: {composite.shape}"
            )

            return {
                "success": True,
                "frame_id": frame_id,
                "width": width,
                "height": height,
                "format": "rgb24",
            }
        else:
            return {"success": False, "error": "No signal layer available to display"}

    except Exception as e:
        logger.error(f"Error rendering composite image: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# =============================================================================
# System Health Handler Helpers
# =============================================================================


def _get_system_health(
    camera,
    acquisition,
    analysis_manager,
    param_manager,
    ipc,
    shared_memory,
    cmd: Dict[str, Any],
) -> Dict[str, Any]:
    """Get comprehensive system health status."""
    try:
        # Component-level health checks
        hardware_status = {
            "multi_channel_ipc": (
                "online" if ipc and hasattr(ipc, "_running") else "offline"
            ),
            "parameters": "online" if param_manager else "offline",
            "display": "online",  # Display is always available if backend running
            "camera": (
                "online"
                if camera and camera.active_camera and camera.active_camera.isOpened()
                else "offline"
            ),
            "realtime_streaming": (
                "online"
                if shared_memory
                and shared_memory._stream
                and shared_memory._stream._running
                else "offline"
            ),
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
            },
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
    logger.info(
        f"Loaded camera parameters: selected='{camera_params.get('selected_camera')}', "
        f"fps={camera_params.get('camera_fps')}"
    )
    logger.info(
        f"Loaded monitor parameters: selected='{monitor_params.get('selected_display')}', "
        f"distance={monitor_params.get('monitor_distance_cm')}cm"
    )

    warnings = []
    errors = []

    # 1. Detect and verify cameras
    ipc.send_sync_message(
        {
            "type": "system_state",
            "state": "initializing",
            "is_ready": False,
            "display_text": "Detecting cameras...",
            "is_error": False,
            "timestamp": time.time(),
        }
    )

    try:
        # Detect cameras with force=True to ensure fresh detection
        detected_cameras = camera.detect_cameras(force=True)
        if not detected_cameras:
            error_msg = (
                "FATAL: No cameras detected - system requires a camera to operate"
            )
            logger.error(error_msg)
            ipc.send_sync_message(
                {
                    "type": "startup_error",
                    "error": error_msg,
                    "is_fatal": True,
                    "timestamp": time.time(),
                }
            )
            raise RuntimeError(error_msg)
        else:
            logger.info(
                f"Detected {len(detected_cameras)} camera(s): {[cam.name for cam in camera.detected_cameras]}"
            )

            # Get existing camera parameters from loaded JSON
            camera_params = param_manager.get_parameter_group("camera")
            selected_camera_name = camera_params.get("selected_camera")

            # Extract camera names for JSON serialization
            camera_names = [cam.name for cam in camera.detected_cameras]

            # Update available cameras list with names (not objects!)
            camera_updates = {"available_cameras": camera_names}

            # Try to open the selected camera from JSON or auto-select first available
            # OPTIMIZATION: Reuse camera that was kept open during detection
            camera_to_use = None

            # Check if the selected camera from JSON is available
            if selected_camera_name and selected_camera_name in camera_names:
                # Find camera index by name
                for cam_info in camera.detected_cameras:
                    if cam_info.name == selected_camera_name and cam_info.is_available:
                        camera_to_use = (cam_info.index, cam_info.name)
                        logger.info(
                            f"Using camera from parameters: {selected_camera_name}"
                        )
                        break

            # If no valid selection from JSON or not found, auto-select FIRST camera
            if not camera_to_use and camera.detected_cameras:
                first_cam = camera.detected_cameras[0]
                camera_to_use = (first_cam.index, first_cam.name)
                camera_updates["selected_camera"] = first_cam.name
                logger.info(f"Auto-selected first available camera: {first_cam.name}")

            # Open the selected camera (detection releases all cameras after checking)
            if camera_to_use:
                if camera.open_camera(camera_to_use[0]):
                    logger.info(
                        f"Camera '{camera_to_use[1]}' opened at index {camera_to_use[0]}"
                    )
                else:
                    error_msg = f"FATAL: Failed to open camera '{camera_to_use[1]}' at index {camera_to_use[0]}"
                    logger.error(error_msg)
                    ipc.send_sync_message(
                        {
                            "type": "startup_error",
                            "error": error_msg,
                            "is_fatal": True,
                            "timestamp": time.time(),
                        }
                    )
                    raise RuntimeError(error_msg)

                # Update camera properties from opened camera
                try:
                    caps = camera.get_camera_capabilities(camera_to_use[1])
                    if caps:
                        camera_updates["camera_width_px"] = caps.get(
                            "width", camera_params.get("camera_width_px", -1)
                        )
                        camera_updates["camera_height_px"] = caps.get(
                            "height", camera_params.get("camera_height_px", -1)
                        )
                        # Keep existing FPS from JSON, don't override with detected FPS
                        # (detected FPS is often wrong from OpenCV)
                        if camera_params.get("camera_fps", -1) <= 0:
                            camera_updates["camera_fps"] = int(
                                caps.get("frameRate", 30)
                            )
                except Exception as e:
                    error_msg = f"Failed to get camera capabilities for '{camera_to_use[1]}': {e}"
                    warnings.append(error_msg)
                    logger.warning(error_msg)

            # Store camera updates (will be batched with monitor updates below)
    except Exception as e:
        error_msg = f"Camera detection failed: {e}"
        warnings.append(error_msg)
        logger.error(error_msg, exc_info=True)

    # 2. Detect and verify displays
    ipc.send_sync_message(
        {
            "type": "system_state",
            "state": "initializing",
            "is_ready": False,
            "display_text": "Detecting displays...",
            "is_error": False,
            "timestamp": time.time(),
        }
    )

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

            logger.info(
                f"Selected display for stimulus: {selected_display.identifier} "
                f"({'secondary' if secondary else 'primary - no secondary available'})"
            )

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

            # Store monitor updates (will be batched below)
            logger.info(
                f"Display configuration prepared: {selected_display.identifier} "
                f"({selected_display.width}x{selected_display.height}@{selected_display.refresh_rate}Hz)"
            )
    except Exception as e:
        error_msg = f"Display detection failed: {e}"
        errors.append(error_msg)
        logger.error(error_msg, exc_info=True)

    # OPTIMIZATION: Batch parameter updates to write only ONCE
    # This avoids multiple atomic file writes (temp file + rename for each)
    try:
        if "camera_updates" in locals() and camera_updates:
            param_manager.update_parameter_group("camera", camera_updates)
            logger.info(f"Camera parameters updated: {list(camera_updates.keys())}")

        if "monitor_updates" in locals() and monitor_updates:
            param_manager.update_parameter_group("monitor", monitor_updates)
            logger.info(f"Monitor parameters updated: {list(monitor_updates.keys())}")
    except Exception as e:
        logger.error(f"Failed to update hardware parameters: {e}")

    # =========================================================================
    # ISSUE-005 FIX: Validate dynamic hardware detection enforcement
    # =========================================================================
    # Ensure selected hardware exists in dynamically detected available hardware
    # This prevents stale cached values and enforces scientific reproducibility

    try:
        # Get updated parameters after detection
        final_camera_params = param_manager.get_parameter_group("camera")
        final_monitor_params = param_manager.get_parameter_group("monitor")

        # Validate camera selection
        selected_camera = final_camera_params.get("selected_camera")
        available_cameras = final_camera_params.get("available_cameras", [])

        if selected_camera and available_cameras:
            if selected_camera not in available_cameras:
                error_msg = (
                    f"Hardware validation failed: Selected camera '{selected_camera}' "
                    f"not found in dynamically detected cameras {available_cameras}. "
                    f"This indicates stale cached parameters. "
                    f"System requires dynamic hardware detection for scientific reproducibility."
                )
                errors.append(error_msg)
                logger.error(error_msg)

        # Validate display selection
        selected_display = final_monitor_params.get("selected_display")
        available_displays = final_monitor_params.get("available_displays", [])

        if selected_display and available_displays:
            if selected_display not in available_displays:
                error_msg = (
                    f"Hardware validation failed: Selected display '{selected_display}' "
                    f"not found in dynamically detected displays {available_displays}. "
                    f"This indicates stale cached parameters. "
                    f"System requires dynamic hardware detection for scientific reproducibility."
                )
                errors.append(error_msg)
                logger.error(error_msg)

        # Log validation success
        if not errors:
            logger.info("Hardware validation passed:")
            logger.info(
                f"  Camera: '{selected_camera}' validated in {len(available_cameras)} available cameras"
            )
            logger.info(
                f"  Display: '{selected_display}' validated in {len(available_displays)} available displays"
            )

    except Exception as e:
        error_msg = f"Hardware validation check failed: {e}"
        errors.append(error_msg)
        logger.error(error_msg, exc_info=True)

    # Return results
    if errors:
        return {"success": False, "errors": errors, "warnings": warnings}
    else:
        return {"success": True, "warnings": warnings}


def _render_initial_stimulus_frame(stimulus_generator, shared_memory):
    """Render initial stimulus frame for startup preview.

    Renders the full checkerboard pattern WITHOUT bar mask to ensure
    the pattern is immediately visible at startup.

    Note: Bar mask defaults to OFF for initial preview because:
    - Frame 0 has bar positioned off-screen (by design for smooth entry)
    - Showing full checkerboard ensures pattern is immediately visible
    - User can enable bar overlay later via stimulus controls
    """
    try:
        # Generate full checkerboard WITHOUT bar mask
        # (bar starts off-screen at frame 0, so show_bar_mask=True would be blank)
        direction = "LR"  # Default direction
        frame, metadata = stimulus_generator.generate_frame_at_index(
            direction=direction,
            frame_index=0,
            show_bar_mask=False,  # FALSE: Show full checkerboard, not off-screen bar
            total_frames=None,
        )

        # Write to shared memory
        frame_id = shared_memory.write_frame(frame, metadata)

        logger.info(
            f"Initial stimulus frame rendered (full checkerboard): frame_id={frame_id}"
        )

    except Exception as e:
        logger.warning(f"Unable to render initial stimulus frame: {e}")
        raise


# =============================================================================
# Parameter Management Helpers
# =============================================================================


def _update_parameters(param_manager, ipc, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Helper for updating parameter group and publishing snapshot."""
    group_name = cmd.get("group_name")
    updates = cmd.get("parameters", {})

    if not group_name:
        return {"success": False, "error": "group_name is required"}

    try:
        # Update parameters (triggers subscriber notifications)
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


def _reload_parameters(param_manager, ipc) -> Dict[str, Any]:
    """Helper for reloading parameters from disk and publishing snapshot.

    Args:
        param_manager: Parameter manager instance
        ipc: IPC service for broadcasting updates

    Returns:
        Success/error response
    """
    try:
        param_manager.reload_from_disk()

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
            "type": "parameters_reloaded",
            "message": "Parameters reloaded from disk successfully",
        }
    except Exception as e:
        logger.error(f"Error reloading parameters: {e}")
        return {"success": False, "error": str(e)}


def _handle_frontend_ready(
    services: Dict[str, Any], cmd: Dict[str, Any]
) -> Dict[str, Any]:
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

        ipc.send_sync_message(
            {
                "type": "system_state",
                "state": "error",
                "is_ready": False,
                "display_text": f"Hardware error: {error_msg}",
                "is_error": True,
                "errors": hardware_check["errors"],
                "timestamp": time.time(),
            }
        )

        return {
            "success": False,
            "type": "handshake_failed",
            "error": error_msg,
            "errors": hardware_check["errors"],
        }

    # 2. Log any warnings but continue
    if hardware_check.get("warnings"):
        for warning in hardware_check["warnings"]:
            logger.warning(f"Hardware warning: {warning}")

    # BUG FIX: DO NOT reload_from_disk() here!
    # Hardware detection updates volatile parameters (camera/monitor) in RUNTIME MEMORY ONLY.
    # These are NOT written to disk (by design - see ParameterManager.VOLATILE_PARAMS).
    # Calling reload_from_disk() would load stale -1 values from JSON and overwrite
    # the valid runtime values we just detected.
    #
    # The sequence is:
    # 1. Hardware detection updates runtime parameters (monitor_width_px, monitor_fps, etc.)
    # 2. These parameters are used immediately by services (already subscribed)
    # 3. JSON file still contains -1 placeholders (intentionally - volatile params not persisted)
    # 4. reload_from_disk() would destroy step 1's work by loading -1 values
    #
    # Services are already notified via param_manager.update_parameter_group() which
    # triggers subscriber callbacks. No reload needed.
    logger.info("Hardware parameters updated in runtime memory (volatile params not persisted to disk)")

    # Note: Camera acquisition NOT started here
    # Will be started after frontend sends shared_memory_readers_ready signal
    # This prevents ZeroMQ "slow joiner" problem where frames are published before subscribers connect

    # 2.6. Render initial stimulus frame for Acquisition viewport preview
    # The presentation window will ignore it (presentationEnabled=false by default)
    # But Acquisition viewport needs it for its mini stimulus preview
    stimulus_generator = services["stimulus_generator"]
    shared_memory = services["shared_memory"]
    try:
        _render_initial_stimulus_frame(stimulus_generator, shared_memory)
    except Exception as e:
        logger.warning(f"Failed to render initial stimulus frame: {e}")

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

    ipc.send_sync_message(
        {
            "type": "system_state",
            "state": "ready",
            "is_ready": True,  # CRITICAL: Frontend needs this to transition to main UI
            "display_text": ready_msg,
            "is_error": False,
            "warnings": hardware_check.get("warnings", []),
            "timestamp": time.time(),
        }
    )
    logger.info("System ready - frontend can transition")

    logger.info("Hardware verification complete - system ready")

    return {
        "success": True,
        "type": "handshake_complete",
        "message": "Backend ready",
        "warnings": hardware_check.get("warnings", []),
    }


def _handle_shared_memory_ready(
    services: Dict[str, Any], cmd: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle shared_memory_readers_ready message and send test frame.

    This handler is called AFTER the frontend has initialized all shared memory frame readers.
    However, ZeroMQ subscription may not be fully active yet. We send a test message and wait
    for confirmation before starting camera acquisition.

    Modern ZeroMQ best practice: Explicit subscriber confirmation with test message
    - Frontend initializes subscribers
    - Frontend sends shared_memory_readers_ready signal
    - Backend sends test frame on camera channel
    - Frontend confirms receipt with camera_subscriber_confirmed
    - Backend starts camera acquisition ONLY after confirmation
    - Zero message loss guaranteed

    Args:
        services: Dictionary of all services (camera, ipc, etc.)
        cmd: Command (no parameters needed)

    Returns:
        Success response
    """
    logger.info(
        "Shared memory readers initialized - sending test message to verify subscription..."
    )

    shared_memory = services["shared_memory"]

    # Send metadata-only test message to camera channel to verify subscriber is connected
    # This is a ZeroMQ PUB/SUB handshake to ensure subscriber is ready before real frames
    # No fake frame data - just a simple JSON message for network synchronization
    try:
        # Get the camera metadata socket directly from shared memory service
        camera_metadata_socket = shared_memory.stream.camera_metadata_socket

        if camera_metadata_socket is None:
            raise RuntimeError("Camera metadata socket not initialized")

        # Send simple test metadata message (no frame data)
        test_metadata = {
            "type": "subscriber_test",
            "camera_name": "TEST",
            "timestamp_us": int(time.time() * 1_000_000),
        }

        import zmq

        camera_metadata_socket.send_json(test_metadata, zmq.NOBLOCK)

        logger.info(
            "Test message sent on camera channel - waiting for frontend confirmation..."
        )

    except Exception as e:
        logger.error(f"Failed to send test message: {e}")
        return {"success": False, "type": "test_message_failed", "error": str(e)}

    return {
        "success": True,
        "type": "test_frame_sent",
        "message": "Test frame sent, waiting for subscriber confirmation",
    }


def _handle_camera_subscriber_confirmed(
    services: Dict[str, Any], cmd: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle camera_subscriber_confirmed message - confirms ZeroMQ subscriber is ready.

    This handler is called AFTER frontend confirms it received the test frame,
    guaranteeing that the ZeroMQ subscriber is fully connected and ready.

    Per docs/components/acquisition-system.md lines 49-58:
    - Camera preview should be "always showing when camera connected"
    - Camera preview is "best-effort" (can drop frames)
    - Camera CAPTURE is essential, camera DISPLAY is nicety

    Therefore, we AUTO-START camera streaming here to provide continuous preview.
    This does NOT conflict with acquisition modes because:
    - acquisition.start_acquisition() defensively checks if camera is already running
    - If camera already streaming, it continues (no restart needed)
    - acquisition.stop_acquisition() does NOT stop camera (camera runs continuously)

    Args:
        services: Dictionary of all services (camera, ipc, etc.)
        cmd: Command (no parameters needed)

    Returns:
        Success response
    """
    logger.info("Camera subscriber confirmed - ZeroMQ connection established")

    camera = services["camera"]

    # AUTO-START camera for continuous preview (per architecture docs)
    if not camera.is_streaming:
        logger.info("Auto-starting camera for continuous preview (per docs/components)")
        if camera.start_acquisition():
            logger.info("Camera streaming started - preview will update continuously")
        else:
            logger.warning("Failed to auto-start camera - preview will not show")
            return {
                "success": False,
                "error": "Failed to start camera streaming",
                "type": "camera_subscriber_confirmed",
            }
    else:
        logger.info("Camera already streaming - continuous preview active")

    return {
        "success": True,
        "type": "camera_subscriber_confirmed",
        "message": "Camera subscriber ready - camera streaming for continuous preview",
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

        ipc.initialize_channels(
            {
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
            }
        )

        # Send zeromq_ready message to frontend via CONTROL channel
        ipc.send_control_message(
            {
                "type": "zeromq_ready",
                "health_port": ipc._health_port,
                "sync_port": ipc._sync_port,
            }
        )

        # CRITICAL: Allow frontend time to subscribe to SYNC channel before sending messages
        # ZeroMQ PUB/SUB has "slow joiner" problem where early messages can be lost
        # 100ms is enough for frontend to establish subscription
        time.sleep(0.1)
        logger.info("Allowing frontend time to subscribe to SYNC channel...")

        # Send initial system state
        ipc.send_sync_message(
            {
                "type": "system_state",
                "state": "initializing",
                "is_ready": False,
                "display_text": "Initializing backend systems...",
                "is_error": False,
                "timestamp": time.time(),
            }
        )

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
                    "camera": (
                        "online"
                        if camera.active_camera and camera.active_camera.isOpened()
                        else "offline"
                    ),
                    "realtime_streaming": (
                        "online"
                        if shared_memory._stream and shared_memory._stream._running
                        else "offline"
                    ),
                    "analysis": "online",
                }

                # Broadcast via SYNC channel (not HEALTH channel)
                ipc.send_sync_message(
                    {
                        "type": "system_health",
                        "timestamp": time.time(),
                        "hardware_status": hardware_status,
                    }
                )
            except Exception as e:
                logger.error(f"Error broadcasting component health: {e}", exc_info=True)

        ipc.start_health_monitoring(
            callback=broadcast_component_health, interval_sec=1.0
        )
        logger.info("Health monitoring started with component health broadcasting")

        # Note: Initial stimulus frame NOT rendered at startup
        # Frames are rendered on-demand when:
        # - User scrubs in Stimulus Generation viewport
        # - User enables presentation in Acquisition viewport
        # - Recording starts
        logger.info(
            "Skipping initial stimulus frame rendering (presentation window should be blank until explicitly enabled)"
        )

        # Wait for frontend_ready message before sending system_state
        # (The system_state message will be sent when we receive frontend_ready)
        self.frontend_ready = False
        self.running = True
        logger.info("Backend ready - waiting for frontend handshake...")

        # Broadcast waiting_frontend state
        ipc.send_sync_message(
            {
                "type": "system_state",
                "state": "waiting_frontend",
                "is_ready": False,
                "display_text": "Waiting for frontend connection...",
                "is_error": False,
                "timestamp": time.time(),
            }
        )

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
                    response = {"success": False, "error": f"Invalid JSON: {str(e)}"}
                    ipc.send_control_message(response)
                    continue

                # Extract command type
                command_type = command.get("type", "")
                message_id = command.get("messageId")

                if not command_type:
                    response = {"success": False, "error": "Command type is required"}
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
                        "error": f"Unknown command: {command_type}",
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
                        logger.error(
                            f"Handler error for {command_type}: {e}", exc_info=True
                        )
                        response = {
                            "success": False,
                            "error": str(e),
                            "type": f"{command_type}_response",
                        }

                # Add message ID for correlation
                if message_id:
                    response["messageId"] = message_id

                # Send response - check for serialization errors
                try:
                    success = ipc.send_control_message(response)
                    if not success:
                        # Serialization failed - send simpler error message
                        error_response = {
                            "success": False,
                            "error": "Failed to serialize response (check backend logs)",
                            "type": f"{command_type}_response",
                        }
                        if message_id:
                            error_response["messageId"] = message_id
                        # Try to send error response (using minimal data)
                        ipc.send_control_message(error_response)
                except Exception as e:
                    logger.error(f"Critical error sending response: {e}", exc_info=True)

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

        # Stop unified stimulus controller if running
        unified_stimulus = self.services.get("unified_stimulus")
        if unified_stimulus:
            unified_stimulus.cleanup()

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
    import os

    # Setup logging using centralized configuration
    from logging_config import configure_logging

    configure_logging(
        level=logging.WARNING
    )  # Only show warnings and errors (INFO logs too noisy in production)

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

        # 1.5. Check for development mode environment variable
        # This allows the --dev-mode flag from setup_and_run.sh to propagate to the backend
        if os.getenv("ISI_DEV_MODE") == "true":
            logger.info(
                "Development mode enabled via ISI_DEV_MODE environment variable"
            )

            # Create temporary ParameterManager to update dev mode flag
            from parameters import ParameterManager

            temp_param_manager = ParameterManager(
                config_file=config.parameters.file_path.name,
                config_dir=str(config.parameters.file_path.parent),
            )
            temp_param_manager.update_parameter_group(
                "system", {"development_mode": True}
            )
            logger.info("Set system.development_mode = true from environment variable")

            # Reload config to pick up the change
            config = AppConfig.from_file(str(config_path))

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
