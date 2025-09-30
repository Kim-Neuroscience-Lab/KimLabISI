#!/usr/bin/env python3
"""
ISI Macroscope Control System - Simple Backend

Minimal backend implementation for ISI camera detection and control with IPC support.
"""

import asyncio
import logging
import signal
import sys
import json
import threading
import time
import struct
from typing import Dict, Any

# Configure logging to file only (don't pollute stdout for IPC)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('isi_macroscope.log')
    ]
)

logger = logging.getLogger(__name__)

# Global backend instance for binary streaming access
_backend_instance = None

# Use proper relative imports for package structure
from .camera_manager import (
    handle_detect_cameras,
    handle_get_camera_capabilities,
    handle_camera_stream_started,
    handle_camera_stream_stopped,
    handle_camera_capture
)
from .stimulus_manager import (
    handle_get_stimulus_parameters,
    handle_update_stimulus_parameters,
    handle_update_spatial_configuration,
    handle_get_spatial_configuration,
    handle_start_stimulus,
    handle_stop_stimulus,
    handle_get_stimulus_status,
    handle_generate_stimulus_preview,
    handle_get_stimulus_info,
    handle_get_stimulus_frame
)
from .display_manager import (
    handle_detect_displays,
    handle_get_display_capabilities,
    handle_select_display
)
from .parameter_manager import (
    get_parameter_manager,
    ParameterValidationError
)
from .health_monitor import get_health_monitor
from .multi_channel_ipc import get_multi_channel_ipc, cleanup_multi_channel_ipc
from .shared_memory_stream import get_shared_memory_stream, start_realtime_streaming, stop_realtime_streaming, cleanup_shared_memory


class ISIMacroscopeBackend:
    """ISI camera detection and control backend - IPC only."""

    def __init__(self, development_mode: bool = False):
        self.development_mode = development_mode
        self.running = False
        self.health_monitor_thread = None

        # Multi-channel IPC system - DO NOT initialize here, let startup coordinator handle it
        self.multi_channel_ipc = None
        self.shared_memory_stream = None
        self.realtime_producer = None

        # Startup coordination
        self.startup_ping_responses = {}  # Track ping responses for handshake

        # Command handlers
        self.command_handlers = {
            'detect_cameras': handle_detect_cameras,
            'get_camera_capabilities': handle_get_camera_capabilities,
            'camera_stream_started': handle_camera_stream_started,
            'camera_stream_stopped': handle_camera_stream_stopped,
            'camera_capture': handle_camera_capture,
            'ping': self.handle_ping,
            'frontend_ready': self.handle_frontend_ready,
            'get_system_status': self.handle_get_system_status,
            # Stimulus handlers
            'get_stimulus_parameters': handle_get_stimulus_parameters,
            'update_stimulus_parameters': handle_update_stimulus_parameters,
            'update_spatial_configuration': handle_update_spatial_configuration,
            'get_spatial_configuration': handle_get_spatial_configuration,
            'start_stimulus': handle_start_stimulus,
            'stop_stimulus': handle_stop_stimulus,
            'get_stimulus_status': handle_get_stimulus_status,
            'generate_stimulus_preview': handle_generate_stimulus_preview,
            'get_stimulus_info': handle_get_stimulus_info,
            'get_stimulus_frame': handle_get_stimulus_frame,
            # Display handlers
            'detect_displays': handle_detect_displays,
            'get_display_capabilities': handle_get_display_capabilities,
            'select_display': handle_select_display,
            # Parameter management handlers
            'get_all_parameters': self.handle_get_all_parameters,
            'get_parameter_group': self.handle_get_parameter_group,
            'update_parameter_group': self.handle_update_parameter_group,
            'reset_to_defaults': self.handle_reset_to_defaults,
            'export_parameters': self.handle_export_parameters,
            'import_parameters': self.handle_import_parameters,
            'get_parameter_info': self.handle_get_parameter_info,
            # Health monitoring handlers
            'get_system_health': self.handle_get_system_health,
        }

        logger.info(f"ISI Backend initialized (dev_mode={development_mode})")

        # Initialize health monitor with backend reference for console logging
        health_monitor = get_health_monitor()
        health_monitor.backend_instance = self

        # DO NOT initialize multi-channel IPC here - let the startup coordinator handle it
        # This ensures proper sequenced initialization with progress updates

    def _handle_health_update(self, health_status):
        """Handle health updates from multi-channel IPC system"""
        # Optional: forward health updates to frontend
        pass

    def handle_ping(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping request for health checks."""
        return {
            "success": True,
            "pong": True
        }

    def handle_frontend_ready(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle frontend_ready command - frontend signals it has connected to ZeroMQ.

        This is the handshake mechanism:
        1. Backend initializes ZeroMQ and broadcasts WAITING_FRONTEND state
        2. Frontend connects to ZeroMQ channels
        3. Frontend sends this frontend_ready command via CONTROL channel (stdin)
        4. Backend receives this and sets frontend_ready flag in startup coordinator
        5. Startup coordinator proceeds with remaining phases
        """
        logger.info("Frontend ready signal received")

        # Notify startup coordinator that frontend is ready
        from .startup_coordinator import get_startup_coordinator
        startup_coordinator = get_startup_coordinator()
        startup_coordinator.frontend_ready = True

        return {
            "success": True,
            "message": "Frontend ready acknowledged"
        }

    def handle_get_system_status(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_system_status request to confirm backend is ready."""
        return {
            "success": True,
            "status": "ready",
            "backend_running": self.running,
            "development_mode": self.development_mode
        }

    def send_ipc_message(self, message: Dict[str, Any]):
        """Send IPC message to frontend via SYNC channel only."""
        from .multi_channel_ipc import get_multi_channel_ipc

        try:
            multi_channel_ipc = get_multi_channel_ipc()
            success = multi_channel_ipc.send_startup_message(message)
            if success:
                logger.info(f"Sent SYNC message: {message.get('type', 'unknown')}")
            else:
                logger.warning(f"Failed to send SYNC message: {message.get('type', 'unknown')}")
        except Exception as e:
            logger.error(f"Error sending SYNC message: {e}")
            # Do not fallback to stdout - only use proper ZeroMQ architecture

    def start_realtime_streaming(self, stimulus_generator, fps: float = 60.0):
        """Start real-time frame streaming using shared memory"""
        if self.shared_memory_stream:
            try:
                self.realtime_producer = start_realtime_streaming(stimulus_generator, fps)
                logger.info(f"Real-time streaming started at {fps} FPS")
                return True
            except Exception as e:
                logger.error(f"Failed to start real-time streaming: {e}")
                return False
        return False

    def stop_realtime_streaming(self):
        """Stop real-time frame streaming"""
        if self.realtime_producer:
            stop_realtime_streaming()
            self.realtime_producer = None
            logger.info("Real-time streaming stopped")

    def send_log_message(self, message: str, level: str = "info"):
        """Send a log message to the frontend console."""
        self.send_ipc_message({
            "type": "log_message",
            "message": message,
            "level": level
        })

    def background_health_monitor(self):
        """Background task to periodically check and broadcast system health (ongoing monitoring only)."""
        # Wait for startup to complete before starting ongoing monitoring
        from .startup_coordinator import get_startup_coordinator
        startup_coordinator = get_startup_coordinator()

        # Wait for startup to complete
        while self.running and not startup_coordinator.is_ready():
            time.sleep(1)

        logger.info("Starting background health monitoring (startup complete)")

        while self.running:
            try:
                # Perform health check for ongoing monitoring only (no console output)
                health_monitor = get_health_monitor()
                health_results = health_monitor.check_all_systems_health(use_cache=False)
                simple_status = {name: result.status.value for name, result in health_results.items()}

                # Send health update to frontend (not displayed in console)
                self.send_ipc_message({
                    "type": "system_health",
                    "status": "ready",
                    "hardware_status": simple_status,
                    "overall_status": health_monitor.get_overall_health_status(use_cache=False).value,
                    "experiment_running": False
                })

                # Wait before next check (5 seconds)
                time.sleep(5)

            except Exception as e:
                logger.error(f"Background health monitor error: {e}")
                time.sleep(5)  # Wait before retrying

    def process_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming command and return response."""
        command_type = command.get('type', '')
        message_id = command.get('messageId')  # Preserve messageId for response correlation

        base_response = {}
        if message_id:
            base_response['messageId'] = message_id

        if not command_type:
            return {
                **base_response,
                "success": False,
                "error": "Command type is required"
            }

        # Check if system is ready for non-essential commands
        # Backend validates readiness, not frontend
        from .startup_coordinator import get_startup_coordinator
        startup_coordinator = get_startup_coordinator()

        # Allow certain commands during startup
        startup_allowed_commands = {'ping', 'frontend_ready', 'get_system_status',
                                   'get_all_parameters', 'get_parameter_group', 'get_parameter_info'}

        if not startup_coordinator.is_ready() and command_type not in startup_allowed_commands:
            current_state = startup_coordinator.current_state.value
            logger.warning(f"Command {command_type} rejected - system not ready (state: {current_state})")
            return {
                **base_response,
                "success": False,
                "error": f"System not ready for this operation. Current state: {current_state}. Please wait for system to be ready."
            }

        handler = self.command_handlers.get(command_type)
        if not handler:
            return {
                **base_response,
                "success": False,
                "error": f"Unknown command type: {command_type}"
            }

        try:
            logger.info(f"Processing command: {command_type}")
            response = handler(command)
            logger.info(f"Command {command_type} completed")
            # Merge messageId with the handler response
            return {**base_response, **response}
        except Exception as e:
            logger.error(f"Error handling command {command_type}: {e}")
            return {
                **base_response,
                "success": False,
                "error": str(e)
            }

    def start_ipc_sync(self):
        """Start IPC communication mode with coordinated startup."""
        logger.info("Starting ISI Backend in IPC mode with centralized startup coordination")

        # Start IPC processing immediately so frontend can get parameter info during startup
        self.running = True

        # Start background startup coordination in a separate thread
        def run_startup_coordination():
            try:
                from .startup_coordinator import get_startup_coordinator
                import asyncio

                startup_coordinator = get_startup_coordinator()

                # Run coordinated startup sequence
                async def run_startup():
                    # Pass backend instance to startup coordinator for initialization
                    result = await startup_coordinator.coordinate_startup(
                        backend_instance=self
                    )
                    if result.success:
                        logger.info("Centralized startup completed successfully - system ready")
                    else:
                        logger.error(f"Centralized startup failed: {result.error}")
                    return result.success

                # Run the async startup in a new event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success = loop.run_until_complete(run_startup())
                loop.close()
                return success

            except Exception as e:
                logger.error(f"Startup coordination failed: {e}")
                return False

        # Start startup coordination in background thread
        startup_thread = threading.Thread(target=run_startup_coordination, daemon=True)
        startup_thread.start()

        # Start background health monitoring thread (only for ongoing monitoring, not startup)
        self.health_monitor_thread = threading.Thread(target=self.background_health_monitor, daemon=True)
        self.health_monitor_thread.start()

        while self.running:
            try:
                line = sys.stdin.readline()
                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                logger.info(f"Received IPC message: {line}")

                try:
                    command = json.loads(line)
                    response = self.process_command(command)
                    # Send command responses via CONTROL channel (stdout), not SYNC
                    from .multi_channel_ipc import get_multi_channel_ipc
                    ipc = get_multi_channel_ipc()
                    ipc.send_control_message(response)

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    from .multi_channel_ipc import get_multi_channel_ipc
                    ipc = get_multi_channel_ipc()
                    ipc.send_control_message({
                        "success": False,
                        "error": f"Invalid JSON: {str(e)}"
                    })

            except Exception as e:
                logger.error(f"IPC error: {e}")
                from .multi_channel_ipc import get_multi_channel_ipc
                ipc = get_multi_channel_ipc()
                ipc.send_control_message({
                    "success": False,
                    "error": str(e)
                })

    async def start_ipc(self):
        """Start IPC communication mode."""
        # Use the synchronous version that actually works
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.start_ipc_sync)

    async def shutdown(self):
        """Shutdown the backend gracefully."""
        logger.info("Shutting down ISI Backend...")
        self.running = False

        # Stop real-time streaming
        self.stop_realtime_streaming()

        # Cleanup multi-channel IPC and shared memory
        cleanup_multi_channel_ipc()
        cleanup_shared_memory()

        # Wait for health monitor thread to finish if it exists
        if self.health_monitor_thread and self.health_monitor_thread.is_alive():
            self.health_monitor_thread.join(timeout=2)

        logger.info("Backend shutdown complete")

    def handle_signal(self, signum, frame):
        """Handle system signals for graceful shutdown."""
        logger.info(f"Received signal {signum} - shutting down...")
        self.running = False

    # Parameter Management Command Handlers
    def handle_get_all_parameters(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_all_parameters command."""
        try:
            param_manager = get_parameter_manager()
            return {
                "success": True,
                "type": "all_parameters",
                "parameters": param_manager.get_all_parameters()
            }
        except Exception as e:
            logger.error(f"Error getting all parameters: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def handle_get_parameter_group(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_parameter_group command."""
        try:
            group_name = command.get('group_name')

            if not group_name:
                return {
                    "success": False,
                    "error": "group_name is required"
                }

            param_manager = get_parameter_manager()
            parameters = param_manager.get_parameter_group(group_name)

            return {
                "success": True,
                "type": "parameter_group",
                "group_name": group_name,
                "parameters": parameters
            }
        except ParameterValidationError as e:
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error getting parameter group: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def handle_update_parameter_group(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle update_parameter_group command."""
        try:
            group_name = command.get('group_name')
            updates = command.get('parameters', {})

            if not group_name:
                return {
                    "success": False,
                    "error": "group_name is required"
                }

            param_manager = get_parameter_manager()
            param_manager.update_parameter_group(group_name, updates)

            # Send parameter update notification to frontend
            self.send_ipc_message({
                "type": "parameters_updated",
                "parameters": param_manager.get_all_parameters()
            })

            return {
                "success": True,
                "type": "parameter_group_updated",
                "group_name": group_name,
                "message": f"Updated {group_name} parameters"
            }
        except ParameterValidationError as e:
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error updating parameter group: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def handle_reset_to_defaults(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle reset_to_defaults command."""
        try:
            param_manager = get_parameter_manager()
            param_manager.reset_to_defaults()

            return {
                "success": True,
                "type": "parameters_reset",
                "message": "Parameters reset to defaults successfully"
            }
        except Exception as e:
            logger.error(f"Error resetting parameters to defaults: {e}")
            return {
                "success": False,
                "error": str(e)
            }



    def handle_export_parameters(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle export_parameters command."""
        try:
            param_manager = get_parameter_manager()
            json_data = param_manager.export_parameters()

            return {
                "success": True,
                "type": "parameters_exported",
                "json_data": json_data
            }
        except Exception as e:
            logger.error(f"Error exporting parameters: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def handle_import_parameters(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle import_parameters command."""
        try:
            json_data = command.get('json_data')

            if not json_data:
                return {
                    "success": False,
                    "error": "json_data is required"
                }

            param_manager = get_parameter_manager()
            param_manager.import_parameters(json_data)

            return {
                "success": True,
                "type": "parameters_imported",
                "message": "Parameters imported successfully"
            }
        except ParameterValidationError as e:
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error importing parameters: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def handle_get_parameter_info(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_parameter_info command."""
        try:
            param_manager = get_parameter_manager()
            info = param_manager.get_parameter_info()

            return {
                "success": True,
                "type": "parameter_info",
                "info": info
            }
        except Exception as e:
            logger.error(f"Error getting parameter info: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def handle_get_system_health(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_system_health command - primary system status endpoint."""
        try:
            use_cache = command.get('use_cache', True)
            include_details = command.get('include_details', False)

            health_monitor = get_health_monitor()

            if include_details:
                # Return full health summary with detailed diagnostics
                health_summary = health_monitor.get_health_summary(use_cache)
                return {
                    "success": True,
                    "type": "system_health_detailed",
                    "status": "ready",
                    "backend_running": self.running,
                    "development_mode": self.development_mode,
                    "experiment_running": False,  # TODO: Track actual experiment state
                    "hardware_status": health_summary.get("systems", {}),  # Frontend compatibility
                    **health_summary
                }
            else:
                # Return simple status for compatibility
                # Never send console messages - startup coordinator handles all startup messaging
                health_results = health_monitor.check_all_systems_health(use_cache)
                simple_status = {name: result.status.value for name, result in health_results.items()}

                return {
                    "success": True,
                    "type": "system_health",
                    "status": "ready",
                    "backend_running": self.running,
                    "development_mode": self.development_mode,
                    "hardware_status": simple_status,
                    "overall_status": health_monitor.get_overall_health_status(use_cache).value,
                    "experiment_running": False  # TODO: Track actual experiment state
                }
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {
                "success": False,
                "error": str(e)
            }


async def main():
    """Main application entry point - IPC communication with Electron"""
    global _backend_instance
    backend = ISIMacroscopeBackend(development_mode=False)
    _backend_instance = backend  # Make available for binary streaming

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, backend.handle_signal)
    signal.signal(signal.SIGTERM, backend.handle_signal)

    try:
        # Start IPC communication
        await backend.start_ipc()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        await backend.shutdown()


if __name__ == "__main__":
    asyncio.run(main())