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
from typing import Dict, Any

# Configure logging to file only (don't pollute stdout for IPC)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('isi_macroscope.log')
    ]
)

logger = logging.getLogger(__name__)

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


class ISIMacroscopeBackend:
    """ISI camera detection and control backend - IPC only."""

    def __init__(self, development_mode: bool = False):
        self.development_mode = development_mode
        self.running = False
        self.health_monitor_thread = None

        # Command handlers
        self.command_handlers = {
            'detect_cameras': handle_detect_cameras,
            'get_camera_capabilities': handle_get_camera_capabilities,
            'camera_stream_started': handle_camera_stream_started,
            'camera_stream_stopped': handle_camera_stream_stopped,
            'camera_capture': handle_camera_capture,
            'ping': self.handle_ping,
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
        self.send_log_message("Backend initialization complete")


    def handle_ping(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping request for health checks."""
        return {
            "success": True,
            "pong": True
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
        """Send IPC message to Electron via stdout."""
        json_str = json.dumps(message)
        sys.stdout.write(json_str + '\n')
        sys.stdout.flush()
        logger.info(f"Sent IPC message: {message.get('type', 'unknown')}")

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

        # Use centralized startup coordinator instead of ad-hoc initialization
        try:
            from .startup_coordinator import get_startup_coordinator
            import asyncio

            startup_coordinator = get_startup_coordinator()

            # Run coordinated startup sequence
            async def run_startup():
                result = await startup_coordinator.coordinate_startup(
                    send_message_callback=self.send_ipc_message
                )

                if result.success:
                    logger.info("Centralized startup completed successfully")
                    # Only declare IPC_READY after coordinated startup is complete
                    print("IPC_READY", flush=True)
                else:
                    logger.error(f"Centralized startup failed: {result.error}")
                    # Don't declare ready if startup failed
                    return False
                return True

            # Run the async startup in a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            startup_success = loop.run_until_complete(run_startup())
            loop.close()

            if not startup_success:
                logger.error("Startup failed - not starting IPC communication")
                return

        except Exception as e:
            logger.error(f"Startup coordination failed: {e}")
            return

        self.running = True

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
                    self.send_ipc_message(response)

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    self.send_ipc_message({
                        "success": False,
                        "error": f"Invalid JSON: {str(e)}"
                    })

            except Exception as e:
                logger.error(f"IPC error: {e}")
                self.send_ipc_message({
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

        # Wait for health monitor thread to finish if it exists
        if self.health_monitor_thread and self.health_monitor_thread.is_alive():
            self.health_monitor_thread.join(timeout=2)

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
    backend = ISIMacroscopeBackend(development_mode=False)

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