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
# Domain Layer
from ..domain.entities.workflow_state import WorkflowStateMachine, WorkflowState
from ..domain.services.workflow_orchestrator import WorkflowOrchestrator
from ..domain.services.error_handler import ErrorHandlingService

# Application Layer - Services
from ..application.services.communication_service import CommunicationService
from ..application.services.monitoring_service import MonitoringService
from ..application.services.state_persistence import StatePersistenceService
from ..application.services.error_orchestrator import ErrorOrchestrator

# Application Layer - Handlers
from ..application.handlers.command_handler import CommandHandler
from ..application.handlers.query_handler import QueryHandler
from ..application.handlers.state_broadcaster import StateBroadcaster

# Application Layer - Use Cases
from ..application.use_cases.data_acquisition import DataAcquisitionUseCase
from ..application.use_cases.session_management import SessionManagementUseCase
from ..application.use_cases.hardware_calibration import HardwareCalibrationUseCase
from ..application.use_cases.error_recovery import ErrorRecoveryUseCase

# Infrastructure Layer
from ..infrastructure.hardware.factory import HardwareFactory
from ..infrastructure.communication.ipc_server import IPCServer
from ..infrastructure.storage.hdf5_repository import HDF5Repository
from ..infrastructure.storage.session_repository import SessionRepository
from ..infrastructure.monitoring.system_monitor import SystemMonitor


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

        # Domain Layer
        self.workflow_state_machine = None
        self.workflow_orchestrator = None
        self.error_handler = None

        # Application Layer - Services
        self.communication_service = None
        self.monitoring_service = None
        self.state_persistence = None
        self.error_orchestrator = None

        # Application Layer - Handlers
        self.command_handler = None
        self.query_handler = None
        self.state_broadcaster = None

        # Application Layer - Use Cases
        self.data_acquisition_use_case = None
        self.session_management_use_case = None
        self.hardware_calibration_use_case = None
        self.error_recovery_use_case = None

        # Infrastructure Layer
        self.hardware_factory = None
        self.ipc_server = None
        self.data_repository = None
        self.session_repository = None
        self.system_monitor = None

        # System state
        self.running = False

        logger.info(f"ISI Macroscope Backend initializing (dev_mode={development_mode})")

    async def initialize(self):
        """Initialize all system components according to clean architecture"""
        try:
            logger.info(">>> Initializing ISI Macroscope Control System Backend")

            # 1. Initialize Domain Layer
            logger.info(">>> Initializing domain components...")
            self.error_handler = ErrorHandlingService()
            self.workflow_state_machine = WorkflowStateMachine()
            self.workflow_orchestrator = WorkflowOrchestrator(
                error_handler=self.error_handler
            )
            logger.info(f">>> Domain layer initialized - State: {self.workflow_state_machine.current_state.value}")

            # 2. Initialize Infrastructure Layer
            logger.info(">>> Initializing infrastructure components...")

            # Hardware Factory
            self.hardware_factory = HardwareFactory()
            if self.development_mode:
                self.hardware_factory._development_mode = True
                logger.info(">>> Development mode enabled - using mock hardware")

            # System Monitor
            self.system_monitor = SystemMonitor()

            # Data Repositories
            storage_directory = Path("data/sessions")
            storage_directory.mkdir(parents=True, exist_ok=True)
            self.data_repository = HDF5Repository(storage_directory)
            self.session_repository = SessionRepository(storage_directory)

            # IPC Server
            self.ipc_server = IPCServer()

            logger.info(">>> Infrastructure layer initialized")

            # 3. Initialize Application Layer - Services
            logger.info(">>> Initializing application services...")

            # Error Orchestrator (bridge between domain and infrastructure)
            self.error_orchestrator = ErrorOrchestrator(
                domain_handler=self.error_handler
            )

            # State Persistence Service
            self.state_persistence = StatePersistenceService(
                storage_path=storage_directory / "state",
                error_handler=self.error_handler
            )

            # Monitoring Service
            self.monitoring_service = MonitoringService(
                system_monitor=self.system_monitor,
                error_handler=self.error_handler
            )

            # Communication Service
            self.communication_service = CommunicationService(
                ipc_server=self.ipc_server,
                error_handler=self.error_handler
            )

            logger.info(">>> Application services initialized")

            # 4. Initialize Application Layer - Handlers
            logger.info(">>> Initializing message handlers...")

            # Query Handler
            self.query_handler = QueryHandler(
                workflow_orchestrator=self.workflow_orchestrator,
                hardware_factory=self.hardware_factory,
                session_repository=self.session_repository,
                error_handler=self.error_handler
            )

            # State Broadcaster
            self.state_broadcaster = StateBroadcaster(
                communication_service=self.communication_service,
                error_handler=self.error_handler
            )

            # Command Handler
            self.command_handler = CommandHandler(
                workflow_orchestrator=self.workflow_orchestrator,
                state_broadcaster=self.state_broadcaster,
                error_handler=self.error_handler
            )

            logger.info(">>> Message handlers initialized")

            # 5. Initialize Application Layer - Use Cases
            logger.info(">>> Initializing use cases...")

            # Hardware Calibration Use Case
            from ..infrastructure.hardware.calibration.camera_calibrator import CameraCalibrator
            from ..infrastructure.hardware.calibration.display_calibrator import DisplayCalibrator

            self.hardware_calibration_use_case = HardwareCalibrationUseCase(
                hardware_factory=self.hardware_factory,
                camera_calibrator=CameraCalibrator(),
                display_calibrator=DisplayCalibrator(),
                error_handler=self.error_handler
            )

            # Error Recovery Use Case
            self.error_recovery_use_case = ErrorRecoveryUseCase(
                workflow_orchestrator=self.workflow_orchestrator,
                monitoring_service=self.monitoring_service,
                state_persistence=self.state_persistence,
                error_handler=self.error_handler
            )

            # Data Acquisition Use Case
            self.data_acquisition_use_case = DataAcquisitionUseCase(
                hardware_factory=self.hardware_factory,
                data_repository=self.data_repository,
                error_handler=self.error_handler
            )

            # Session Management Use Case
            self.session_management_use_case = SessionManagementUseCase(
                session_repository=self.session_repository,
                state_persistence=self.state_persistence,
                error_handler=self.error_handler
            )

            logger.info(">>> Use cases initialized")

            # 6. Wire Services Together
            logger.info(">>> Wiring services together...")

            # Register handlers with communication service
            self.communication_service.register_handler("command", self.command_handler)
            self.communication_service.register_handler("query", self.query_handler)

            # Register use cases with command handler
            self.command_handler.register_use_case("data_acquisition", self.data_acquisition_use_case)
            self.command_handler.register_use_case("session_management", self.session_management_use_case)
            self.command_handler.register_use_case("hardware_calibration", self.hardware_calibration_use_case)
            self.command_handler.register_use_case("error_recovery", self.error_recovery_use_case)

            logger.info(">>> Service wiring complete")

            # 7. System Health Check
            await self._perform_health_check()

            logger.info(">>> Backend initialization complete - ready for frontend connection")

        except Exception as e:
            logger.error(f">>> Backend initialization failed: {e}")
            raise

    async def _perform_health_check(self):
        """Perform system health check"""
        logger.info(">>> Performing system health check...")

        try:
            # Check domain layer
            assert self.workflow_state_machine is not None
            assert self.workflow_orchestrator is not None
            assert self.error_handler is not None
            logger.info("    Domain layer healthy")

            # Check infrastructure layer
            assert self.hardware_factory is not None
            assert self.data_repository is not None
            assert self.session_repository is not None
            assert self.ipc_server is not None
            assert self.system_monitor is not None
            logger.info("    Infrastructure layer healthy")

            # Check application services
            assert self.communication_service is not None
            assert self.monitoring_service is not None
            assert self.state_persistence is not None
            assert self.error_orchestrator is not None
            logger.info("    Application services healthy")

            # Check application handlers
            assert self.command_handler is not None
            assert self.query_handler is not None
            assert self.state_broadcaster is not None
            logger.info("    Application handlers healthy")

            # Check use cases
            assert self.data_acquisition_use_case is not None
            assert self.session_management_use_case is not None
            assert self.hardware_calibration_use_case is not None
            assert self.error_recovery_use_case is not None
            logger.info("    Use cases healthy")

            logger.info(">>> System health check passed - all components initialized")

        except AssertionError as e:
            logger.error(f">>> Health check failed: {e}")
            raise
        except Exception as e:
            logger.error(f">>> Health check error: {e}")
            raise

    async def start(self):
        """Start the backend server"""
        try:
            logger.info(">>> Starting ISI Macroscope Backend Server...")

            # Start infrastructure services
            await self.system_monitor.start()
            await self.communication_service.start()

            # Start application services
            await self.monitoring_service.start()
            await self.state_persistence.start()

            self.running = True
            logger.info(f">>> Backend server running on {self.host}:{self.port}")

            # Main server loop
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f">>> Server error: {e}")
            await self.shutdown()
            raise

    async def shutdown(self):
        """Shutdown the backend server gracefully"""
        logger.info(">>> Shutting down ISI Macroscope Backend...")

        try:
            self.running = False

            # Shutdown application services
            if self.monitoring_service:
                await self.monitoring_service.stop()
            if self.state_persistence:
                await self.state_persistence.stop()

            # Shutdown infrastructure services
            if self.communication_service:
                await self.communication_service.stop()
            if self.system_monitor:
                await self.system_monitor.stop()

            logger.info(">>> Backend shutdown complete")

        except Exception as e:
            logger.error(f">>> Shutdown error: {e}")

    def handle_signal(self, signum, frame):
        """Handle system signals for graceful shutdown"""
        logger.info(f">>> Received signal {signum} - initiating shutdown...")
        asyncio.create_task(self.shutdown())


async def main():
    """Main application entry point"""
    parser = argparse.ArgumentParser(description='ISI Macroscope Control System Backend')
    parser.add_argument('--dev', action='store_true', help='Run in development mode')
    parser.add_argument('--host', default='localhost', help='Server host')
    parser.add_argument('--port', type=int, default=8765, help='Server port')
    args = parser.parse_args()

    # Create and initialize backend
    backend = ISIMacroscopeBackend(
        development_mode=args.dev,
        host=args.host,
        port=args.port
    )

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, backend.handle_signal)
    signal.signal(signal.SIGTERM, backend.handle_signal)

    try:
        # Initialize all components
        await backend.initialize()

        # Start the server
        await backend.start()

    except KeyboardInterrupt:
        logger.info(">>> Keyboard interrupt received")
    except Exception as e:
        logger.error(f">>> Fatal error: {e}")
        sys.exit(1)
    finally:
        await backend.shutdown()


if __name__ == "__main__":
    asyncio.run(main())