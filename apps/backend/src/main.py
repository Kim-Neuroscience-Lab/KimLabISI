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
        "start_camera_acquisition": lambda cmd: {
            "success": camera.start_acquisition(),
            "message": "Camera acquisition started" if camera.start_acquisition() else "Failed to start"
        },
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
            cmd.get("base_dir", str(Path.home() / "ISI_Data"))
        ),
        "load_session": lambda cmd: playback.load_session(
            cmd.get("session_path")
        ),
        "get_session_data": lambda cmd: playback.get_session_info(),
        "unload_session": lambda cmd: playback.unload_session(),
        "get_playback_frame": lambda cmd: playback.get_frame(
            direction=cmd.get("direction"),
            frame_index=cmd.get("frame_index", 0)
        ),

        # =====================================================================
        # Analysis commands
        # =====================================================================
        "start_analysis": lambda cmd: analysis.start_analysis(
            cmd.get("session_path")
        ),
        "stop_analysis": lambda cmd: analysis.stop_analysis(),
        "get_analysis_status": lambda cmd: analysis.get_status(),

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
        "health_check": lambda cmd: {
            "status": "healthy",
            "services": list(services.keys())
        },
    }

    logger.info(f"Created {len(handlers)} command handlers")
    return handlers


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

        # Start IPC channels
        ipc = self.services["ipc"]
        ipc.start()

        self.running = True
        logger.info("Backend ready - entering event loop")

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
            ipc.stop()

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
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

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
