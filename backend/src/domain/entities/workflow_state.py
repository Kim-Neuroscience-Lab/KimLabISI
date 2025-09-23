"""
Workflow State Machine Entity - 12-State Scientific Workflow

This module implements the core domain entity for the ISI Macroscope Control System's
12-state workflow state machine as specified in WORKFLOW_STATES.md.

Domain Entity Rules:
- Pure business logic with zero external dependencies
- Immutable state transitions with validation
- Complete state transition matrix implementation
- Hardware requirement validation per state
"""

from enum import Enum
from typing import Set, Optional, Dict
from datetime import datetime
from pydantic import BaseModel, Field


class WorkflowState(Enum):
    """12-state workflow states for ISI Macroscope Control System"""

    # Primary Workflow States (9 states)
    STARTUP = "startup"
    SETUP_READY = "setup_ready"
    SETUP = "setup"
    GENERATION_READY = "generation_ready"
    GENERATION = "generation"
    ACQUISITION_READY = "acquisition_ready"
    ACQUISITION = "acquisition"
    ANALYSIS_READY = "analysis_ready"
    ANALYSIS = "analysis"

    # Error Handling States (3 states)
    ERROR = "error"
    RECOVERY = "recovery"
    DEGRADED = "degraded"


class HardwareRequirement(Enum):
    """Hardware requirements for workflow states"""
    MINIMAL = "minimal"  # Display only for error reporting
    DISPLAY = "display"  # Display hardware (RTX 4070 or dev-mode)
    GPU = "gpu"  # GPU with CUDA support
    CAMERA = "camera"  # PCO Panda 4.2 camera
    STORAGE = "storage"  # High-speed storage (Samsung 990 PRO)
    ALL_HARDWARE = "all_hardware"  # Complete production hardware
    DEV_MODE_BYPASS = "dev_mode_bypass"  # Development mode allows bypass


class WorkflowTransition(BaseModel):
    """Immutable workflow state transition record using Pydantic V2"""
    from_state: WorkflowState
    to_state: WorkflowState
    timestamp: datetime = Field(description="Timestamp when transition occurred")
    user_initiated: bool = Field(description="Whether transition was user-initiated")
    validation_passed: bool = Field(description="Whether transition validation passed")
    hardware_available: bool = Field(description="Whether required hardware was available")
    error_message: Optional[str] = Field(None, description="Error message if transition failed")

    model_config = {"frozen": True, "use_enum_values": True}


class WorkflowStateMachine:
    """
    12-State Workflow State Machine Entity

    Implements the complete state machine logic for ISI scientific workflow
    with hardware validation, error recovery, and non-linear navigation.

    Core Principles:
    - Non-linear navigation (users can return to previous phases)
    - State persistence across application restarts
    - Hardware requirement validation for each transition
    - Graceful degradation when hardware unavailable
    - Complete error recovery with transparency
    """

    def __init__(self, initial_state: WorkflowState = WorkflowState.STARTUP):
        self._current_state = initial_state
        self._transition_history: list[WorkflowTransition] = []
        self._hardware_requirements = self._initialize_hardware_requirements()
        self._valid_transitions = self._initialize_valid_transitions()

    @property
    def current_state(self) -> WorkflowState:
        """Get current workflow state"""
        return self._current_state

    @property
    def transition_history(self) -> list[WorkflowTransition]:
        """Get immutable copy of transition history"""
        return self._transition_history.copy()

    def get_hardware_requirements(self, state: WorkflowState) -> HardwareRequirement:
        """Get hardware requirements for a specific state"""
        return self._hardware_requirements[state]

    def get_valid_transitions(self, from_state: WorkflowState) -> Set[WorkflowState]:
        """Get valid transition targets from a given state"""
        return self._valid_transitions.get(from_state, set())

    def can_transition_to(self, target_state: WorkflowState,
                         hardware_available: Set[HardwareRequirement]) -> tuple[bool, Optional[str]]:
        """
        Validate if transition to target state is possible

        Args:
            target_state: Desired workflow state
            hardware_available: Set of available hardware capabilities

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if transition is valid in state machine
        valid_targets = self.get_valid_transitions(self._current_state)
        if target_state not in valid_targets:
            return False, f"Invalid transition from {self._current_state.value} to {target_state.value}"

        # Check hardware requirements
        required_hardware = self.get_hardware_requirements(target_state)

        # DEV_MODE_BYPASS allows any transition
        if HardwareRequirement.DEV_MODE_BYPASS in hardware_available:
            return True, None

        # Validate specific hardware requirements
        hardware_valid, hardware_error = self._validate_hardware(required_hardware, hardware_available)
        if not hardware_valid:
            return False, hardware_error

        return True, None

    def transition_to(self, target_state: WorkflowState,
                     hardware_available: Set[HardwareRequirement],
                     user_initiated: bool = True) -> WorkflowTransition:
        """
        Execute state transition with validation

        Args:
            target_state: Desired workflow state
            hardware_available: Set of available hardware capabilities
            user_initiated: Whether transition was user-initiated

        Returns:
            WorkflowTransition record

        Raises:
            ValueError: If transition is invalid
        """
        is_valid, error_message = self.can_transition_to(target_state, hardware_available)

        transition = WorkflowTransition(
            from_state=self._current_state,
            to_state=target_state,
            timestamp=datetime.now(),
            user_initiated=user_initiated,
            validation_passed=is_valid,
            hardware_available=len(hardware_available) > 0,
            error_message=error_message
        )

        if is_valid:
            self._current_state = target_state

        self._transition_history.append(transition)

        if not is_valid:
            raise ValueError(f"Transition failed: {error_message}")

        return transition

    def force_error_state(self, error_message: str) -> WorkflowTransition:
        """
        Force transition to ERROR state (system-initiated)

        Args:
            error_message: Description of the error condition

        Returns:
            WorkflowTransition record
        """
        transition = WorkflowTransition(
            from_state=self._current_state,
            to_state=WorkflowState.ERROR,
            timestamp=datetime.now(),
            user_initiated=False,
            validation_passed=True,  # Error transitions are always valid
            hardware_available=False,
            error_message=error_message
        )

        self._current_state = WorkflowState.ERROR
        self._transition_history.append(transition)

        return transition

    def _validate_hardware(self, required: HardwareRequirement,
                          available: Set[HardwareRequirement]) -> tuple[bool, Optional[str]]:
        """Validate hardware requirements against available hardware"""

        # Minimal requirements (always satisfied)
        if required == HardwareRequirement.MINIMAL:
            return True, None

        # Check specific requirements
        requirement_map = {
            HardwareRequirement.DISPLAY: [HardwareRequirement.DISPLAY],
            HardwareRequirement.GPU: [HardwareRequirement.GPU, HardwareRequirement.DISPLAY],
            HardwareRequirement.CAMERA: [HardwareRequirement.CAMERA],
            HardwareRequirement.STORAGE: [HardwareRequirement.STORAGE],
            HardwareRequirement.ALL_HARDWARE: [
                HardwareRequirement.DISPLAY,
                HardwareRequirement.GPU,
                HardwareRequirement.CAMERA,
                HardwareRequirement.STORAGE
            ]
        }

        required_items = requirement_map.get(required, [])
        missing_hardware = [req for req in required_items if req not in available]

        if missing_hardware:
            missing_names = [req.value for req in missing_hardware]
            return False, f"Missing required hardware: {', '.join(missing_names)}"

        return True, None

    def _initialize_hardware_requirements(self) -> Dict[WorkflowState, HardwareRequirement]:
        """Initialize hardware requirements for each workflow state"""
        return {
            # Primary workflow states
            WorkflowState.STARTUP: HardwareRequirement.ALL_HARDWARE,
            WorkflowState.SETUP_READY: HardwareRequirement.DISPLAY,
            WorkflowState.SETUP: HardwareRequirement.DISPLAY,
            WorkflowState.GENERATION_READY: HardwareRequirement.GPU,
            WorkflowState.GENERATION: HardwareRequirement.GPU,
            WorkflowState.ACQUISITION_READY: HardwareRequirement.ALL_HARDWARE,
            WorkflowState.ACQUISITION: HardwareRequirement.ALL_HARDWARE,
            WorkflowState.ANALYSIS_READY: HardwareRequirement.GPU,
            WorkflowState.ANALYSIS: HardwareRequirement.GPU,

            # Error handling states
            WorkflowState.ERROR: HardwareRequirement.MINIMAL,
            WorkflowState.RECOVERY: HardwareRequirement.MINIMAL,
            WorkflowState.DEGRADED: HardwareRequirement.MINIMAL,
        }

    def _initialize_valid_transitions(self) -> Dict[WorkflowState, Set[WorkflowState]]:
        """Initialize valid state transitions matrix"""
        return {
            # STARTUP transitions
            WorkflowState.STARTUP: {
                WorkflowState.SETUP_READY,  # Hardware validation complete
                WorkflowState.ERROR,  # Hardware failure
            },

            # SETUP_READY transitions
            WorkflowState.SETUP_READY: {
                WorkflowState.SETUP,  # User starts spatial configuration
                WorkflowState.GENERATION_READY,  # Navigate to generation (if data available)
                WorkflowState.ACQUISITION_READY,  # Navigate to acquisition (if data available)
                WorkflowState.ANALYSIS_READY,  # Navigate to analysis (if data available)
                WorkflowState.ERROR,  # Hardware failure
            },

            # SETUP transitions
            WorkflowState.SETUP: {
                WorkflowState.GENERATION_READY,  # Configuration confirmed
                WorkflowState.SETUP_READY,  # User navigates away
                WorkflowState.ERROR,  # Hardware failure
            },

            # GENERATION_READY transitions
            WorkflowState.GENERATION_READY: {
                WorkflowState.GENERATION,  # User starts stimulus generation
                WorkflowState.SETUP,  # User loads different parameters
                WorkflowState.ACQUISITION_READY,  # User selects compatible dataset
                WorkflowState.ERROR,  # Hardware failure
            },

            # GENERATION transitions
            WorkflowState.GENERATION: {
                WorkflowState.ACQUISITION_READY,  # Generation complete
                WorkflowState.GENERATION_READY,  # User cancels
                WorkflowState.ERROR,  # Hardware failure
            },

            # ACQUISITION_READY transitions
            WorkflowState.ACQUISITION_READY: {
                WorkflowState.ACQUISITION,  # User starts acquisition
                WorkflowState.GENERATION_READY,  # User modifies stimuli
                WorkflowState.SETUP,  # User modifies setup
                WorkflowState.ERROR,  # Hardware failure
            },

            # ACQUISITION transitions
            WorkflowState.ACQUISITION: {
                WorkflowState.ANALYSIS_READY,  # Acquisition complete
                WorkflowState.ACQUISITION_READY,  # User stops acquisition
                WorkflowState.ERROR,  # Hardware failure with data preservation
                WorkflowState.RECOVERY,  # Critical error with automatic recovery
            },

            # ANALYSIS_READY transitions
            WorkflowState.ANALYSIS_READY: {
                WorkflowState.ANALYSIS,  # User starts analysis
                WorkflowState.ACQUISITION_READY,  # User repeats acquisition
                WorkflowState.SETUP,  # User modifies setup (invalidates downstream)
                WorkflowState.ERROR,  # Hardware failure
            },

            # ANALYSIS transitions
            WorkflowState.ANALYSIS: {
                WorkflowState.ANALYSIS_READY,  # Analysis complete
                WorkflowState.ERROR,  # Hardware failure (preserve partial results)
            },

            # ERROR transitions
            WorkflowState.ERROR: {
                WorkflowState.RECOVERY,  # Automatic or manual recovery
                WorkflowState.STARTUP,  # User restarts application
                # Application exit handled at application layer
            },

            # RECOVERY transitions
            WorkflowState.RECOVERY: {
                WorkflowState.STARTUP,  # Recovery successful - restart
                WorkflowState.SETUP_READY,  # Recovery to ready state
                WorkflowState.GENERATION_READY,  # Recovery to generation
                WorkflowState.ACQUISITION_READY,  # Recovery to acquisition
                WorkflowState.ANALYSIS_READY,  # Recovery to analysis
                WorkflowState.ERROR,  # Recovery failed
                WorkflowState.DEGRADED,  # User chooses degraded mode
            },

            # DEGRADED transitions
            WorkflowState.DEGRADED: {
                WorkflowState.STARTUP,  # Hardware restored - full restart
                WorkflowState.SETUP_READY,  # Continue with limitations
                WorkflowState.GENERATION_READY,  # Continue with limitations
                WorkflowState.ACQUISITION_READY,  # Continue with limitations
                WorkflowState.ANALYSIS_READY,  # Continue with limitations
                WorkflowState.ERROR,  # Critical hardware fails
            },
        }