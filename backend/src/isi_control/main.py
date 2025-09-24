#!/usr/bin/env python3
"""
ISI Macroscope Control System - Application Entry Point

This is the main entry point for the ISI Macroscope Control System backend
application package. It coordinates initialization of all components according
to the documented clean architecture.

Architecture Components Initialized:
- Domain Layer: Workflow state machine and business entities
- Application Layer: Use cases and command handlers
- Infrastructure Layer: Hardware, storage, and communication
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

# Import from our layered architecture
from ..domain.entities.workflow_state import WorkflowStateMachine, WorkflowState
from ..infrastructure.hardware.factory import HardwareFactory
from ..infrastructure.communication.ipc_server import IPCServer
from ..infrastructure.storage.hdf5_repository import HDF5Repository
from ..application.handlers.command_handler import CommandHandler
from ..application.use_cases.data_acquisition import DataAcquisitionUseCase
from ..application.use_cases.stimulus_generation import StimulusGenerationUseCase


class ISIMacroscopeBackend:
    """
    Main backend service for the ISI Macroscope Control System

    Coordinates all system components following clean architecture principles
    as documented in docs/ARCHITECTURE.md
    """

    def __init__(self, development_mode: bool = False, host: str = "localhost", port: int = 8765):
        """Initialize the backend system"""
        self.development_mode = development_mode
        self.host = host
        self.port = port

        # Core components following architecture layers
        self.workflow_state_machine = None
        self.hardware_factory = None

        # Infrastructure layer
        self.data_repository = None
        self.ipc_server = None

        # Application layer
        self.data_acquisition_use_case = None
        self.stimulus_generation_use_case = None
        self.command_handler = None

        # System state
        self.running = False

        logger.info(f"ISI Macroscope Backend initializing (dev_mode={development_mode})")

    async def initialize(self):
        """Initialize all system components according to clean architecture"""
        try:
            logger.info("=€ Initializing ISI Macroscope Control System Backend")

            # 1. Initialize Domain Layer
            logger.info("=Ë Initializing domain components...")
            self.workflow_state_machine = WorkflowStateMachine()
            logger.info(f"=Ë Workflow state machine initialized: {self.workflow_state_machine.current_state.value}")

            # 2. Initialize Infrastructure Layer - Hardware Factory
            logger.info("=' Initializing hardware abstraction...")
            self.hardware_factory = HardwareFactory()

            if self.development_mode:
                self.hardware_factory._development_mode = True
                logger.info("=' Development mode enabled - using mock hardware")

            capabilities = self.hardware_factory.detect_hardware_capabilities()
            logger.info(f"=' Hardware capabilities detected: {len(capabilities)} types")

            # 3. Initialize Infrastructure Layer - Data Repository
            logger.info("=¾ Initializing data storage...")
            storage_directory = Path("data/sessions")
            storage_directory.mkdir(parents=True, exist_ok=True)
            self.data_repository = HDF5Repository(storage_directory)
            logger.info(f"=¾ HDF5 data repository initialized: {storage_directory}")

            # 4. Initialize Application Layer - Use Cases
            logger.info("<¯ Initializing use cases...")

            # Stimulus generation use case (no dependencies)
            self.stimulus_generation_use_case = StimulusGenerationUseCase()
            logger.info("<¯ Stimulus generation use case initialized")

            # Data acquisition use case (depends on hardware and data storage)
            self.data_acquisition_use_case = DataAcquisitionUseCase(
                hardware_factory=self.hardware_factory,
                data_repository=self.data_repository,
                stimulus_use_case=self.stimulus_generation_use_case
            )
            logger.info("<¯ Data acquisition use case initialized")

            # 5. Initialize Application Layer - Command Handler
            logger.info("™ Initializing command handler...")
            self.command_handler = CommandHandler()
            logger.info("™ Command handler ready")

            # 6. Initialize Infrastructure Layer - Communication
            logger.info("< Initializing IPC server...")
            self.ipc_server = IPCServer()
            self.ipc_server.register_handler("command_handler", self.command_handler)
            logger.info("< IPC server initialized")

            # 7. System Health Check
            await self._perform_health_check()

            logger.info(" Backend initialization complete - ready for frontend connection")

        except Exception as e:
            logger.error(f"L Backend initialization failed: {e}")
            raise

    async def _perform_health_check(self):
        """Perform system health check"""
        logger.info("= Performing system health check...")

        try:
            # Check domain layer
            assert self.workflow_state_machine is not None
            assert self.workflow_state_machine.current_state == WorkflowState.STARTUP
            logger.info("    Domain layer healthy")

            # Check infrastructure layer
            assert self.hardware_factory is not None
            assert self.data_repository is not None
            assert self.ipc_server is not None
            logger.info("    Infrastructure layer healthy")

            # Check application layer
            assert self.command_handler is not None
            assert self.data_acquisition_use_case is not None
            assert self.stimulus_generation_use_case is not None
            logger.info("    Application layer healthy")

            logger.info("= Health check passed - all components operational")

        except Exception as e:
            logger.error(f"L Health check failed: {e}")
            raise

    async def start(self):
        """Start the backend server"""
        try:
            self.running = True
            logger.info("=€ Starting ISI Macroscope Backend Server")

            # Start IPC server
            await self.ipc_server.start()
            logger.info("< IPC Server started successfully")

            logger.info("<‰ ISI Macroscope Backend is ready!")
            logger.info("<‰ Waiting for frontend connection...")

            # Keep running until stopped
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"L Backend server error: {e}")
            raise

    async def stop(self):
        """Stop the backend server gracefully"""
        logger.info("=Ñ Stopping ISI Macroscope Backend...")

        self.running = False

        if self.ipc_server:
            await self.ipc_server.stop()
            logger.info("< IPC Server stopped")

        logger.info(" Backend stopped gracefully")


async def main():
    """Main entry point"""
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
        logger.info("=Ñ Shutdown signal received")
        asyncio.create_task(backend.stop())

    # Register signal handlers
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda s, f: signal_handler())

    try:
        # Initialize and start backend
        await backend.initialize()
        await backend.start()

    except KeyboardInterrupt:
        logger.info("=Ñ Interrupted by user")
    except Exception as e:
        logger.error(f"L Fatal error: {e}")
        sys.exit(1)
    finally:
        await backend.stop()


if __name__ == "__main__":
    print("=, ISI Macroscope Control System - Backend")
    print("=" * 50)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n=K Backend shutdown complete")
    except Exception as e:
        print(f"\nL Fatal error: {e}")
        sys.exit(1)