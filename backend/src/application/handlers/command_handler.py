"""
Command Handler - Frontend Command Processing

This module implements the command handler for processing frontend commands
as specified in ADR-0003 (Thin Client Architecture). All business logic
remains in the backend; frontend only sends commands and receives responses.

Command Handler Responsibilities:
- Process commands from frontend via IPC
- Route commands to appropriate use cases
- Maintain thin client architecture
- Provide structured responses using Pydantic V2
- Handle errors gracefully with user-friendly messages
"""

import logging
from typing import Dict, Any, Optional, Set
from enum import Enum
from pydantic import BaseModel, Field, ValidationError

from ...domain.entities.workflow_state import (
    WorkflowStateMachine,
    WorkflowState,
    HardwareRequirement,
    WorkflowTransition
)
from ...infrastructure.hardware.factory import HardwareFactory
from ...infrastructure.communication.ipc_server import IPCHandler, CommandMessage

logger = logging.getLogger(__name__)


class CommandType(Enum):
    """Available command types from frontend"""

    # Workflow commands
    WORKFLOW_START = "workflow.start"
    WORKFLOW_TRANSITION = "workflow.transition"
    WORKFLOW_GET_STATE = "workflow.get_state"
    WORKFLOW_GET_HISTORY = "workflow.get_history"

    # Hardware commands
    HARDWARE_DETECT = "hardware.detect"
    HARDWARE_GET_STATUS = "hardware.get_status"

    # System commands
    SYSTEM_HEALTH_CHECK = "system.health_check"
    SYSTEM_GET_INFO = "system.get_info"


class CommandRequest(BaseModel):
    """Structured command request using Pydantic V2"""
    command_type: CommandType
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Command parameters")

    model_config = {"use_enum_values": True}


class CommandResponse(BaseModel):
    """Structured command response using Pydantic V2"""
    success: bool = Field(description="Whether command succeeded")
    data: Dict[str, Any] = Field(default_factory=dict, description="Response data")
    error_message: Optional[str] = Field(None, description="Error message if command failed")
    timestamp: float = Field(description="Response timestamp")

    model_config = {"use_enum_values": True}


class WorkflowStateResponse(BaseModel):
    """Workflow state response data using Pydantic V2"""
    current_state: WorkflowState
    valid_transitions: list[WorkflowState] = Field(description="Available state transitions")
    hardware_requirements: HardwareRequirement = Field(description="Hardware required for current state")
    hardware_available: bool = Field(description="Whether required hardware is available")

    model_config = {"use_enum_values": True}


class HardwareStatusResponse(BaseModel):
    """Hardware status response data using Pydantic V2"""
    platform_type: str = Field(description="Platform type (windows/macos)")
    development_mode: bool = Field(description="Whether in development mode")
    hardware_capabilities: Dict[str, Any] = Field(description="Available hardware capabilities")

    model_config = {"use_enum_values": True}


class CommandHandler(IPCHandler):
    """
    Command Handler for Frontend Commands

    Processes all commands from the Electron frontend following the thin client
    architecture. Business logic remains in domain entities and use cases.

    Design Principles:
    - Frontend sends structured commands
    - Backend processes and returns structured responses
    - No business logic in the handler - delegates to domain entities
    - Type-safe validation using Pydantic V2
    - Graceful error handling with user-friendly messages
    """

    def __init__(self):
        """Initialize command handler with dependencies"""
        self._workflow_state_machine = WorkflowStateMachine()
        self._hardware_factory = HardwareFactory()

        logger.info("Command handler initialized")

    async def handle_command(self, command: CommandMessage) -> Dict[str, Any]:
        """
        Handle command from frontend

        Args:
            command: Command message from frontend

        Returns:
            Dictionary containing command response
        """
        try:
            # Validate and parse command
            command_request = CommandRequest(
                command_type=CommandType(command.command),
                parameters=command.parameters
            )

            # Route to appropriate command handler
            response = await self._route_command(command_request)

            # Return structured response
            return response.model_dump()

        except ValueError as e:
            # Invalid command type
            return self._create_error_response(f"Unknown command: {command.command}", str(e))
        except ValidationError as e:
            # Invalid command parameters
            return self._create_error_response("Invalid command parameters", str(e))
        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error handling command {command.command}: {e}")
            return self._create_error_response("Command processing failed", str(e))

    async def handle_query(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle query from frontend

        Args:
            query: Query data from frontend

        Returns:
            Dictionary containing query response
        """
        try:
            # For now, treat queries as get_state commands
            query_command = CommandRequest(
                command_type=CommandType.WORKFLOW_GET_STATE,
                parameters=query
            )

            response = await self._route_command(query_command)
            return response.model_dump()

        except Exception as e:
            logger.error(f"Error handling query: {e}")
            return self._create_error_response("Query processing failed", str(e))

    async def _route_command(self, command_request: CommandRequest) -> CommandResponse:
        """Route command to appropriate handler method"""

        command_handlers = {
            CommandType.WORKFLOW_START.value: self._handle_workflow_start,
            CommandType.WORKFLOW_TRANSITION.value: self._handle_workflow_transition,
            CommandType.WORKFLOW_GET_STATE.value: self._handle_workflow_get_state,
            CommandType.WORKFLOW_GET_HISTORY.value: self._handle_workflow_get_history,
            CommandType.HARDWARE_DETECT.value: self._handle_hardware_detect,
            CommandType.HARDWARE_GET_STATUS.value: self._handle_hardware_get_status,
            CommandType.SYSTEM_HEALTH_CHECK.value: self._handle_system_health_check,
            CommandType.SYSTEM_GET_INFO.value: self._handle_system_get_info,
        }

        handler = command_handlers.get(command_request.command_type)
        if not handler:
            raise ValueError(f"No handler for command: {command_request.command_type}")

        return await handler(command_request.parameters)

    async def _handle_workflow_start(self, parameters: Dict[str, Any]) -> CommandResponse:
        """Handle workflow start command"""
        try:
            # Detect available hardware
            hardware_capabilities = self._hardware_factory.detect_hardware_capabilities()
            available_hardware = set(hardware_capabilities.keys())

            # Initialize workflow state machine to STARTUP
            self._workflow_state_machine = WorkflowStateMachine(WorkflowState.STARTUP)

            # Try to transition to SETUP_READY
            try:
                transition = self._workflow_state_machine.transition_to(
                    WorkflowState.SETUP_READY,
                    available_hardware,
                    user_initiated=True
                )

                return CommandResponse(
                    success=True,
                    data={
                        "workflow_started": True,
                        "current_state": self._workflow_state_machine.current_state.value,
                        "transition": transition.model_dump()
                    },
                    timestamp=transition.timestamp.timestamp()
                )

            except ValueError as e:
                # Hardware not available - stay in STARTUP
                return CommandResponse(
                    success=False,
                    data={
                        "workflow_started": False,
                        "current_state": self._workflow_state_machine.current_state.value,
                        "hardware_capabilities": {k.value: v.model_dump() for k, v in hardware_capabilities.items()}
                    },
                    error_message=str(e),
                    timestamp=self._get_current_timestamp()
                )

        except Exception as e:
            logger.error(f"Error starting workflow: {e}")
            return CommandResponse(
                success=False,
                data={},
                error_message=f"Failed to start workflow: {str(e)}",
                timestamp=self._get_current_timestamp()
            )

    async def _handle_workflow_transition(self, parameters: Dict[str, Any]) -> CommandResponse:
        """Handle workflow state transition command"""
        try:
            target_state_str = parameters.get("target_state")
            if not target_state_str:
                raise ValueError("target_state parameter required")

            target_state = WorkflowState(target_state_str)

            # Get available hardware
            hardware_capabilities = self._hardware_factory.detect_hardware_capabilities()
            available_hardware = set(hardware_capabilities.keys())

            # Attempt transition
            transition = self._workflow_state_machine.transition_to(
                target_state,
                available_hardware,
                user_initiated=True
            )

            return CommandResponse(
                success=True,
                data={
                    "transition_successful": True,
                    "from_state": transition.from_state,
                    "to_state": transition.to_state,
                    "current_state": self._workflow_state_machine.current_state.value,
                    "transition": transition.model_dump()
                },
                timestamp=transition.timestamp.timestamp()
            )

        except ValueError as e:
            return CommandResponse(
                success=False,
                data={
                    "transition_successful": False,
                    "current_state": self._workflow_state_machine.current_state.value
                },
                error_message=str(e),
                timestamp=self._get_current_timestamp()
            )
        except Exception as e:
            logger.error(f"Error in workflow transition: {e}")
            return CommandResponse(
                success=False,
                data={},
                error_message=f"Transition failed: {str(e)}",
                timestamp=self._get_current_timestamp()
            )

    async def _handle_workflow_get_state(self, parameters: Dict[str, Any]) -> CommandResponse:
        """Handle get current workflow state command"""
        try:
            # Get current state information
            current_state = self._workflow_state_machine.current_state
            valid_transitions = self._workflow_state_machine.get_valid_transitions(current_state)
            hardware_requirements = self._workflow_state_machine.get_hardware_requirements(current_state)

            # Check hardware availability
            hardware_capabilities = self._hardware_factory.detect_hardware_capabilities()
            available_hardware = set(hardware_capabilities.keys())
            hardware_available = hardware_requirements in available_hardware or HardwareRequirement.DEV_MODE_BYPASS in available_hardware

            state_response = WorkflowStateResponse(
                current_state=current_state,
                valid_transitions=list(valid_transitions),
                hardware_requirements=hardware_requirements,
                hardware_available=hardware_available
            )

            return CommandResponse(
                success=True,
                data=state_response.model_dump(),
                timestamp=self._get_current_timestamp()
            )

        except Exception as e:
            logger.error(f"Error getting workflow state: {e}")
            return CommandResponse(
                success=False,
                data={},
                error_message=f"Failed to get workflow state: {str(e)}",
                timestamp=self._get_current_timestamp()
            )

    async def _handle_workflow_get_history(self, parameters: Dict[str, Any]) -> CommandResponse:
        """Handle get workflow transition history command"""
        try:
            history = self._workflow_state_machine.transition_history

            return CommandResponse(
                success=True,
                data={
                    "transition_history": [transition.model_dump() for transition in history],
                    "total_transitions": len(history)
                },
                timestamp=self._get_current_timestamp()
            )

        except Exception as e:
            logger.error(f"Error getting workflow history: {e}")
            return CommandResponse(
                success=False,
                data={},
                error_message=f"Failed to get workflow history: {str(e)}",
                timestamp=self._get_current_timestamp()
            )

    async def _handle_hardware_detect(self, parameters: Dict[str, Any]) -> CommandResponse:
        """Handle hardware detection command"""
        try:
            hardware_capabilities = self._hardware_factory.detect_hardware_capabilities()

            return CommandResponse(
                success=True,
                data={
                    "hardware_detection_complete": True,
                    "capabilities": {k.value: v.model_dump() for k, v in hardware_capabilities.items()},
                    "available_requirements": [req.value for req in self._hardware_factory.get_available_hardware_requirements()]
                },
                timestamp=self._get_current_timestamp()
            )

        except Exception as e:
            logger.error(f"Error detecting hardware: {e}")
            return CommandResponse(
                success=False,
                data={},
                error_message=f"Hardware detection failed: {str(e)}",
                timestamp=self._get_current_timestamp()
            )

    async def _handle_hardware_get_status(self, parameters: Dict[str, Any]) -> CommandResponse:
        """Handle get hardware status command"""
        try:
            platform_info = self._hardware_factory.platform_info
            hardware_capabilities = self._hardware_factory.detect_hardware_capabilities()

            status_response = HardwareStatusResponse(
                platform_type=platform_info.platform_type,
                development_mode=self._hardware_factory.development_mode,
                hardware_capabilities={k.value: v.model_dump() for k, v in hardware_capabilities.items()}
            )

            return CommandResponse(
                success=True,
                data=status_response.model_dump(),
                timestamp=self._get_current_timestamp()
            )

        except Exception as e:
            logger.error(f"Error getting hardware status: {e}")
            return CommandResponse(
                success=False,
                data={},
                error_message=f"Failed to get hardware status: {str(e)}",
                timestamp=self._get_current_timestamp()
            )

    async def _handle_system_health_check(self, parameters: Dict[str, Any]) -> CommandResponse:
        """Handle system health check command"""
        try:
            # Perform basic system health checks
            health_status = {
                "workflow_state_machine": "healthy",
                "hardware_factory": "healthy",
                "platform_detection": "healthy"
            }

            # Check if we can create interfaces
            try:
                self._hardware_factory.create_camera_interface()
                health_status["camera_interface"] = "healthy"
            except Exception:
                health_status["camera_interface"] = "degraded"

            try:
                self._hardware_factory.create_gpu_interface()
                health_status["gpu_interface"] = "healthy"
            except Exception:
                health_status["gpu_interface"] = "degraded"

            all_healthy = all(status == "healthy" for status in health_status.values())

            return CommandResponse(
                success=True,
                data={
                    "system_healthy": all_healthy,
                    "health_status": health_status,
                    "development_mode": self._hardware_factory.development_mode
                },
                timestamp=self._get_current_timestamp()
            )

        except Exception as e:
            logger.error(f"Error in system health check: {e}")
            return CommandResponse(
                success=False,
                data={},
                error_message=f"System health check failed: {str(e)}",
                timestamp=self._get_current_timestamp()
            )

    async def _handle_system_get_info(self, parameters: Dict[str, Any]) -> CommandResponse:
        """Handle get system information command"""
        try:
            platform_info = self._hardware_factory.platform_info

            return CommandResponse(
                success=True,
                data={
                    "platform_info": platform_info.model_dump(),
                    "workflow_state": self._workflow_state_machine.current_state.value,
                    "development_mode": self._hardware_factory.development_mode
                },
                timestamp=self._get_current_timestamp()
            )

        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return CommandResponse(
                success=False,
                data={},
                error_message=f"Failed to get system info: {str(e)}",
                timestamp=self._get_current_timestamp()
            )

    def _create_error_response(self, error_message: str, details: str) -> Dict[str, Any]:
        """Create error response dictionary"""
        error_response = CommandResponse(
            success=False,
            data={},
            error_message=f"{error_message}: {details}",
            timestamp=self._get_current_timestamp()
        )
        return error_response.model_dump()

    def _get_current_timestamp(self) -> float:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().timestamp()