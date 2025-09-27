"""
System Startup Use Case - Hardware and Configuration Initialization

This use case handles the complete system startup sequence including
hardware detection, configuration validation, and workflow initialization.
Based on the 12-state workflow system with proper error handling.
"""

import asyncio
import logging
from typing import Dict, List, Set, Optional, Tuple
from pathlib import Path
from datetime import datetime

from domain.entities.workflow_state_machine import WorkflowStateMachine
from domain.value_objects.workflow_state import (
    WorkflowState, WorkflowTransition, HardwareRequirement
)
from domain.entities.parameter_manager import ParameterManager
from domain.value_objects.parameters import CombinedParameters, ParameterSource
from domain.value_objects.stream_config import StreamingProfile
from infrastructure.hardware.factory import HardwareFactory
from infrastructure.storage.session_repository import SessionRepository
from infrastructure.communication.ipc_server import IPCHandler

logger = logging.getLogger(__name__)


class SystemStartupUseCase:
    """Orchestrates complete system startup and initialization"""

    def __init__(
        self,
        hardware_factory: HardwareFactory,
        parameter_manager: ParameterManager,
        session_repository: SessionRepository,
        ipc_handler: IPCHandler
    ):
        self.hardware_factory = hardware_factory
        self.parameter_manager = parameter_manager
        self.session_repository = session_repository
        self.ipc_handler = ipc_handler

        # Initialize workflow state machine
        self.workflow = WorkflowStateMachine()

        # Startup state
        self.startup_errors: List[str] = []
        self.hardware_status: Dict[HardwareRequirement, bool] = {}
        self.initialization_complete = False

    async def initialize_system(self) -> SystemStartupResult:
        """
        Complete system initialization sequence

        Returns:
            SystemStartupResult with initialization status and any errors
        """
        logger.info("Starting ISI Macroscope Control System initialization")

        try:
            # Phase 1: Basic system validation
            await self._validate_environment()

            # Phase 2: Hardware discovery and initialization
            await self._initialize_hardware()

            # Phase 3: Parameter system initialization
            await self._initialize_parameters()

            # Phase 4: Session management initialization
            await self._initialize_session_management()

            # Phase 5: Communication system initialization
            await self._initialize_communication()

            # Phase 6: Workflow state machine setup
            await self._initialize_workflow()

            # Phase 7: Final validation
            startup_result = await self._validate_system_ready()

            if startup_result.success:
                self.initialization_complete = True
                logger.info("System initialization completed successfully")
            else:
                logger.error(f"System initialization failed: {startup_result.errors}")

            return startup_result

        except Exception as e:
            logger.exception("Critical error during system initialization")
            return SystemStartupResult(
                success=False,
                workflow_state=WorkflowState.ERROR,
                errors=[f"Critical initialization error: {str(e)}"],
                hardware_status=self.hardware_status
            )

    async def _validate_environment(self):
        """Validate basic environment requirements"""
        logger.info("Phase 1: Environment validation")

        # Check Python version
        import sys
        if sys.version_info < (3, 11):
            self.startup_errors.append("Python 3.11+ required")

        # Check required directories exist
        required_dirs = [
            Path.home() / ".isi_macroscope",
            Path.home() / ".isi_macroscope" / "parameters",
            Path.home() / ".isi_macroscope" / "sessions",
            Path.home() / ".isi_macroscope" / "logs"
        ]

        for dir_path in required_dirs:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Ensured directory exists: {dir_path}")
            except Exception as e:
                self.startup_errors.append(f"Cannot create directory {dir_path}: {e}")

        # Check disk space (require at least 10GB free)
        try:
            import shutil
            free_space_gb = shutil.disk_usage(Path.home()).free / (1024**3)
            if free_space_gb < 10:
                self.startup_errors.append(f"Insufficient disk space: {free_space_gb:.1f}GB available, 10GB required")
        except Exception as e:
            logger.warning(f"Could not check disk space: {e}")

    async def _initialize_hardware(self):
        """Initialize and validate hardware components"""
        logger.info("Phase 2: Hardware initialization")

        try:
            # Get hardware requirements from workflow
            required_hardware = {
                HardwareRequirement.DISPLAY_SYSTEM,
                HardwareRequirement.CAMERA_SYSTEM,
                HardwareRequirement.STORAGE_SYSTEM,
                HardwareRequirement.GPU_SYSTEM
            }

            # Initialize each hardware component
            for hardware_req in required_hardware:
                try:
                    logger.info(f"Initializing {hardware_req.value}")

                    if hardware_req == HardwareRequirement.DISPLAY_SYSTEM:
                        display_manager = await self.hardware_factory.create_display_manager()
                        available = await display_manager.is_available()
                        self.hardware_status[hardware_req] = available
                        if not available:
                            self.startup_errors.append("Display system not available")

                    elif hardware_req == HardwareRequirement.CAMERA_SYSTEM:
                        camera_manager = await self.hardware_factory.create_camera_manager()
                        available = await camera_manager.is_available()
                        self.hardware_status[hardware_req] = available
                        if not available:
                            self.startup_errors.append("Camera system not available")

                    elif hardware_req == HardwareRequirement.STORAGE_SYSTEM:
                        storage_manager = await self.hardware_factory.create_storage_manager()
                        available = await storage_manager.is_available()
                        self.hardware_status[hardware_req] = available
                        if not available:
                            self.startup_errors.append("Storage system not available")

                    elif hardware_req == HardwareRequirement.GPU_SYSTEM:
                        gpu_manager = await self.hardware_factory.create_gpu_manager()
                        available = await gpu_manager.is_available()
                        self.hardware_status[hardware_req] = available
                        if not available:
                            self.startup_errors.append("GPU system not available")

                    logger.info(f"{hardware_req.value}: {'Available' if self.hardware_status[hardware_req] else 'Unavailable'}")

                except Exception as e:
                    logger.exception(f"Error initializing {hardware_req.value}")
                    self.hardware_status[hardware_req] = False
                    self.startup_errors.append(f"{hardware_req.value} initialization failed: {str(e)}")

        except Exception as e:
            logger.exception("Critical error during hardware initialization")
            self.startup_errors.append(f"Hardware initialization failed: {str(e)}")

    async def _initialize_parameters(self):
        """Initialize parameter management system"""
        logger.info("Phase 3: Parameter system initialization")

        try:
            # Ensure default parameters exist
            defaults = self.parameter_manager.get_development_defaults()
            logger.info("Parameter system initialized with development defaults")

            # Validate parameter system integrity
            available_params = self.parameter_manager.list_available_parameters()
            logger.info(f"Available parameter sets: {available_params}")

            if len(available_params) == 0:
                self.startup_errors.append("No parameter sets available")

        except Exception as e:
            logger.exception("Error initializing parameter system")
            self.startup_errors.append(f"Parameter system initialization failed: {str(e)}")

    async def _initialize_session_management(self):
        """Initialize session and data management"""
        logger.info("Phase 4: Session management initialization")

        try:
            # Test session repository
            sessions = await self.session_repository.list_sessions()
            logger.info(f"Found {len(sessions)} existing sessions")

            # Verify write access
            test_session_id = f"startup_test_{datetime.now().isoformat()}"
            try:
                await self.session_repository.create_session_directory(test_session_id)
                await self.session_repository.delete_session_directory(test_session_id)
                logger.debug("Session directory write access verified")
            except Exception as e:
                self.startup_errors.append(f"Session directory access failed: {str(e)}")

        except Exception as e:
            logger.exception("Error initializing session management")
            self.startup_errors.append(f"Session management initialization failed: {str(e)}")

    async def _initialize_communication(self):
        """Initialize IPC communication system"""
        logger.info("Phase 5: Communication system initialization")

        try:
            # Test IPC handler
            if not self.ipc_handler.is_initialized():
                self.startup_errors.append("IPC handler not initialized")
            else:
                logger.info("IPC communication system ready")

        except Exception as e:
            logger.exception("Error initializing communication system")
            self.startup_errors.append(f"Communication system initialization failed: {str(e)}")

    async def _initialize_workflow(self):
        """Initialize workflow state machine"""
        logger.info("Phase 6: Workflow state machine initialization")

        try:
            # Determine available hardware
            available_hardware = {
                req for req, available in self.hardware_status.items()
                if available
            }

            # Initialize workflow with current hardware status
            current_state = self.workflow.get_current_state()
            logger.info(f"Workflow initialized in state: {current_state.value}")

            # Attempt to transition to SETUP_READY if hardware allows
            if len(available_hardware) >= 2:  # Need at least some hardware
                transition = self.workflow.transition_to(
                    WorkflowState.SETUP_READY,
                    available_hardware
                )
                if transition.success:
                    logger.info(f"Transitioned to {transition.new_state.value}")
                else:
                    logger.warning(f"Could not transition to SETUP_READY: {transition.error_message}")

        except Exception as e:
            logger.exception("Error initializing workflow")
            self.startup_errors.append(f"Workflow initialization failed: {str(e)}")

    async def _validate_system_ready(self) -> 'SystemStartupResult':
        """Final validation that system is ready for use"""
        logger.info("Phase 7: Final system validation")

        # Determine overall success
        critical_hardware = {
            HardwareRequirement.DISPLAY_SYSTEM,
            HardwareRequirement.STORAGE_SYSTEM
        }

        critical_hardware_available = all(
            self.hardware_status.get(req, False) for req in critical_hardware
        )

        # Success if no critical errors and critical hardware available
        success = len(self.startup_errors) == 0 and critical_hardware_available

        # Determine workflow state
        if success:
            workflow_state = self.workflow.get_current_state()
        else:
            workflow_state = WorkflowState.ERROR if len(self.startup_errors) > 0 else WorkflowState.DEGRADED

        return SystemStartupResult(
            success=success,
            workflow_state=workflow_state,
            errors=self.startup_errors.copy(),
            hardware_status=self.hardware_status.copy(),
            available_parameters=self.parameter_manager.list_available_parameters(),
            system_health=self._calculate_system_health()
        )

    def _calculate_system_health(self) -> SystemHealth:
        """Calculate overall system health based on hardware status"""
        total_hardware = len(HardwareRequirement)
        available_hardware = sum(1 for available in self.hardware_status.values() if available)

        if available_hardware == total_hardware:
            return SystemHealth.HEALTHY
        elif available_hardware >= total_hardware // 2:
            return SystemHealth.DEGRADED
        else:
            return SystemHealth.CRITICAL

    def get_startup_status(self) -> Dict:
        """Get current startup status for monitoring"""
        return {
            "initialization_complete": self.initialization_complete,
            "workflow_state": self.workflow.get_current_state().value,
            "hardware_status": {req.value: status for req, status in self.hardware_status.items()},
            "error_count": len(self.startup_errors),
            "errors": self.startup_errors.copy()
        }


class SystemStartupResult:
    """Result of system startup process"""

    def __init__(
        self,
        success: bool,
        workflow_state: WorkflowState,
        errors: List[str],
        hardware_status: Dict[HardwareRequirement, bool],
        available_parameters: Optional[List[str]] = None,
        system_health: Optional[SystemHealth] = None
    ):
        self.success = success
        self.workflow_state = workflow_state
        self.errors = errors
        self.hardware_status = hardware_status
        self.available_parameters = available_parameters or []
        self.system_health = system_health or SystemHealth.CRITICAL
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            "success": self.success,
            "workflow_state": self.workflow_state.value,
            "errors": self.errors,
            "hardware_status": {req.value: status for req, status in self.hardware_status.items()},
            "available_parameters": self.available_parameters,
            "system_health": self.system_health.value,
            "timestamp": self.timestamp.isoformat()
        }


class SystemStartupError(Exception):
    """Raised when system startup fails"""
    pass