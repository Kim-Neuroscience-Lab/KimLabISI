#!/usr/bin/env python3
"""
ISI Macroscope Control System - Backend Main Entry Point

This is the main entry point for the ISI Macroscope Control System backend.
It initializes all components according to the documented architecture and
starts the IPC server for communication with the Electron frontend.

Architecture Components Initialized:
- Workflow State Machine (12-state system)
- Hardware Factory (cross-platform detection)
- IPC Server (thin client communication)
- Command Handler (frontend command processing)

Usage:
    python main.py [--dev] [--port PORT] [--host HOST]

Arguments:
    --dev: Run in development mode (forces hardware bypass)
    --port: IPC server port (default: 8765)
    --host: IPC server host (default: localhost)
"""

import asyncio
import argparse
import logging
import signal
import sys
from pathlib import Path

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('isi_macroscope.log')
    ]
)

logger = logging.getLogger(__name__)

# Import our components
from src.domain.entities.workflow_state import WorkflowStateMachine, WorkflowState
from src.infrastructure.hardware.factory import HardwareFactory
from src.infrastructure.communication.ipc_server import IPCServer
from src.application.handlers.command_handler import CommandHandler


class ISIMacroscopeBackend:
    """
    Main backend service for the ISI Macroscope Control System

    Coordinates all system components following clean architecture principles:
    - Domain: Workflow state machine and business logic
    - Application: Command handlers and use cases
    - Infrastructure: Hardware abstraction and communication
    """

    def __init__(self, development_mode: bool = False, host: str = "localhost", port: int = 8765):
        """
        Initialize the backend system

        Args:
            development_mode: Force development mode (hardware bypass)
            host: IPC server host
            port: IPC server port
        """
        self.development_mode = development_mode
        self.host = host
        self.port = port

        # Initialize core components
        self.workflow_state_machine = None
        self.hardware_factory = None
        self.ipc_server = None
        self.command_handler = None

        # System state
        self.running = False

        logger.info(f"ISI Macroscope Backend initializing (dev_mode={development_mode})")

    async def initialize(self):
        """Initialize all system components"""
        try:
            logger.info("🚀 Initializing ISI Macroscope Control System Backend")

            # 1. Initialize Hardware Factory (Infrastructure Layer)
            logger.info("🔧 Initializing hardware factory...")
            self.hardware_factory = HardwareFactory()

            # Force development mode if requested
            if self.development_mode:
                self.hardware_factory._development_mode = True
                logger.info("🔧 Development mode forced - hardware bypass enabled")

            # Detect available hardware
            capabilities = self.hardware_factory.detect_hardware_capabilities()
            logger.info(f"🔧 Hardware capabilities detected: {len(capabilities)} types")
            for hw_type, capability in capabilities.items():
                logger.info(f"   - {hw_type.value}: {'Available' if capability.available else 'Unavailable'}")

            # 2. Initialize Workflow State Machine (Domain Layer)
            logger.info("📋 Initializing workflow state machine...")
            self.workflow_state_machine = WorkflowStateMachine()
            logger.info(f"📋 Workflow initialized in state: {self.workflow_state_machine.current_state.value}")

            # 3. Initialize Command Handler (Application Layer)
            logger.info("⚙️ Initializing command handler...")
            self.command_handler = CommandHandler()
            logger.info("⚙️ Command handler ready for frontend commands")

            # 4. Initialize IPC Server (Infrastructure Layer)
            logger.info(f"🌐 Initializing IPC server...")
            self.ipc_server = IPCServer()

            # Register command handler with IPC server
            self.ipc_server.register_handler("command_handler", self.command_handler)
            logger.info("🌐 Command handler registered with IPC server")

            # 5. System Health Check
            await self._perform_health_check()

            logger.info("✅ Backend initialization complete - ready for frontend connection")

        except Exception as e:
            logger.error(f"❌ Backend initialization failed: {e}")
            raise

    async def _perform_health_check(self):
        """Perform system health check"""
        logger.info("🔍 Performing system health check...")

        try:
            # Check workflow state machine
            assert self.workflow_state_machine is not None
            assert self.workflow_state_machine.current_state == WorkflowState.STARTUP
            logger.info("   ✅ Workflow state machine healthy")

            # Check hardware factory
            assert self.hardware_factory is not None
            capabilities = self.hardware_factory.detect_hardware_capabilities()
            assert len(capabilities) > 0
            logger.info("   ✅ Hardware factory healthy")

            # Check command handler
            assert self.command_handler is not None
            logger.info("   ✅ Command handler healthy")

            # Check IPC server
            assert self.ipc_server is not None
            logger.info("   ✅ IPC server healthy")

            logger.info("🔍 Health check passed - all components operational")

        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            raise

    async def start(self):
        """Start the backend server"""
        try:
            self.running = True
            logger.info("🚀 Starting ISI Macroscope Backend Server")

            # Start IPC server
            await self.ipc_server.start()
            logger.info(f"🌐 IPC Server started successfully")

            # System is now ready
            logger.info("🎉 ISI Macroscope Backend is ready!")
            logger.info("🎉 Waiting for frontend connection...")

            # Keep running until stopped
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"❌ Backend server error: {e}")
            raise

    async def stop(self):
        """Stop the backend server gracefully"""
        logger.info("🛑 Stopping ISI Macroscope Backend...")

        self.running = False

        if self.ipc_server:
            await self.ipc_server.stop()
            logger.info("🌐 IPC Server stopped")

        logger.info("✅ Backend stopped gracefully")

    def get_system_info(self):
        """Get system information for debugging"""
        return {
            "backend_version": "1.0.0",
            "development_mode": self.development_mode,
            "host": self.host,
            "port": self.port,
            "current_state": self.workflow_state_machine.current_state.value if self.workflow_state_machine else None,
            "hardware_capabilities": len(self.hardware_factory.detect_hardware_capabilities()) if self.hardware_factory else 0
        }


async def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="ISI Macroscope Control System Backend")
    parser.add_argument("--dev", action="store_true", help="Run in development mode")
    parser.add_argument("--port", type=int, default=8765, help="IPC server port")
    parser.add_argument("--host", type=str, default="localhost", help="IPC server host")
    parser.add_argument("--version", action="version", version="ISI Macroscope Backend 1.0.0")

    args = parser.parse_args()

    # Create backend instance
    backend = ISIMacroscopeBackend(
        development_mode=args.dev,
        host=args.host,
        port=args.port
    )

    # Setup graceful shutdown
    def signal_handler():
        logger.info("🛑 Shutdown signal received")
        asyncio.create_task(backend.stop())

    # Register signal handlers
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda s, f: signal_handler())

    try:
        # Initialize and start backend
        await backend.initialize()
        await backend.start()

    except KeyboardInterrupt:
        logger.info("🛑 Interrupted by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
    finally:
        await backend.stop()


if __name__ == "__main__":
    print("🔬 ISI Macroscope Control System - Backend")
    print("=" * 50)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Backend shutdown complete")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)