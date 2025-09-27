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

# Import camera handlers
from camera_manager import handle_detect_cameras, handle_get_camera_capabilities


class ISIMacroscopeBackend:
    """Simple backend for ISI camera detection and control via IPC."""

    def __init__(self, use_ipc: bool = False, development_mode: bool = False):
        self.use_ipc = use_ipc
        self.development_mode = development_mode
        self.running = False

        # Command handlers
        self.command_handlers = {
            'detect_cameras': handle_detect_cameras,
            'get_camera_capabilities': handle_get_camera_capabilities,
            'get_system_status': self.handle_get_system_status,
            'ping': self.handle_ping,
        }

        logger.info(f"ISI Backend initialized (ipc={use_ipc}, dev_mode={development_mode})")

    def handle_get_system_status(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle system status request."""
        # Check actual hardware status
        hardware_status = self._check_hardware_status()

        return {
            "success": True,
            "type": "system_status",
            "status": "ready",
            "backend_running": self.running,
            "ipc_mode": self.use_ipc,
            "development_mode": self.development_mode,
            "hardware_status": hardware_status,
            "experiment_running": False  # TODO: Track actual experiment state
        }

    def _check_hardware_status(self) -> Dict[str, str]:
        """Check the actual status of hardware components."""
        from camera_manager import camera_manager

        # Check camera status by attempting detection
        camera_status = "offline"
        try:
            cameras = camera_manager.detect_cameras()
            available_cameras = [cam for cam in cameras if cam.is_available]
            camera_status = "online" if len(available_cameras) > 0 else "offline"
        except Exception as e:
            logger.error(f"Camera detection failed during status check: {e}")
            camera_status = "error"

        # Display status (for now, assume online if backend is running)
        display_status = "online" if self.running else "offline"

        return {
            "camera": camera_status,
            "display": display_status
        }

    def handle_ping(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping request for health checks."""
        return {
            "success": True,
            "pong": True
        }

    def send_ipc_message(self, message: Dict[str, Any]):
        """Send IPC message to Electron via stdout."""
        json_str = json.dumps(message)
        sys.stdout.write(json_str + '\n')
        sys.stdout.flush()
        logger.info(f"Sent IPC message: {message.get('type', 'unknown')}")

    def process_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming command and return response."""
        command_type = command.get('type', '')

        if not command_type:
            return {
                "success": False,
                "error": "Command type is required"
            }

        handler = self.command_handlers.get(command_type)
        if not handler:
            return {
                "success": False,
                "error": f"Unknown command type: {command_type}"
            }

        try:
            logger.info(f"Processing command: {command_type}")
            response = handler(command)
            logger.info(f"Command {command_type} completed")
            return response
        except Exception as e:
            logger.error(f"Error handling command {command_type}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def start_ipc(self):
        """Start IPC communication mode."""
        logger.info("Starting ISI Backend in IPC mode")

        # Send ready signal
        print("IPC_READY", flush=True)
        logger.info("Sent IPC_READY signal")

        self.running = True

        # Read commands from stdin
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        while self.running:
            try:
                # Read line from stdin
                line_bytes = await reader.readline()
                if not line_bytes:
                    break

                line = line_bytes.decode().strip()
                if not line:
                    continue

                logger.info(f"Received IPC message: {line}")

                try:
                    command = json.loads(line)
                    response = self.process_command(command)

                    # Send response via stdout
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

    async def start(self):
        """Start the backend in appropriate mode."""
        if self.use_ipc:
            await self.start_ipc()
        else:
            logger.info("No communication mode specified - exiting")

    async def shutdown(self):
        """Shutdown the backend gracefully."""
        logger.info("Shutting down ISI Backend...")
        self.running = False

    def handle_signal(self, signum, frame):
        """Handle system signals for graceful shutdown."""
        logger.info(f"Received signal {signum} - shutting down...")
        self.running = False


async def main():
    """Main application entry point - runs in IPC mode for Electron"""
    # Always run in IPC mode - this backend is only meant to be run through Electron
    backend = ISIMacroscopeBackend(use_ipc=True, development_mode=False)

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, backend.handle_signal)
    signal.signal(signal.SIGTERM, backend.handle_signal)

    try:
        # Start the IPC server
        await backend.start()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        await backend.shutdown()


if __name__ == "__main__":
    asyncio.run(main())