"""
Workflow Orchestrator Domain Service for ISI Macroscope System

Orchestrates the complete ISI workflow following the 12-state workflow state machine
defined in the architecture. Ensures proper sequencing, validation, and error handling.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Set
import asyncio
from pathlib import Path

from ..value_objects.workflow_state import WorkflowState
from ..value_objects.parameters import CombinedParameters, StimulusGenerationParams, AcquisitionProtocolParams
from ..entities.dataset import StimulusDataset, AcquisitionSession, AnalysisResult
from ..entities.hardware import HardwareSystem, HardwareStatus
from .error_handler import ErrorHandlingService, ISIDomainError


class WorkflowTransition(Enum):
    """Valid workflow state transitions"""
    INITIALIZE_SYSTEM = "initialize_system"
    START_STIMULUS_GENERATION = "start_stimulus_generation"
    COMPLETE_STIMULUS_GENERATION = "complete_stimulus_generation"
    START_SPATIAL_SETUP = "start_spatial_setup"
    COMPLETE_SPATIAL_SETUP = "complete_spatial_setup"
    START_ACQUISITION = "start_acquisition"
    COMPLETE_ACQUISITION = "complete_acquisition"
    START_ANALYSIS = "start_analysis"
    COMPLETE_ANALYSIS = "complete_analysis"
    REPORT_ERROR = "report_error"
    PERFORM_RECOVERY = "perform_recovery"
    REQUEST_SHUTDOWN = "request_shutdown"




class WorkflowOrchestrator:
    """
    Domain service for orchestrating ISI macroscope workflows

    Manages the complete lifecycle from initialization through analysis,
    ensuring proper state transitions and validation at each step.
    """

    def __init__(self, hardware_system: HardwareSystem, error_handler: Optional[ErrorHandlingService] = None):
        self.hardware_system = hardware_system
        self.error_handler = error_handler or ErrorHandlingService()
        self._current_state = WorkflowState.UNINITIALIZED
        self._state_history: List[tuple[datetime, WorkflowState]] = []
        self._error_history: List[tuple[datetime, str]] = []

        # Current workflow data
        self._current_parameters: Optional[CombinedParameters] = None
        self._current_dataset: Optional[StimulusDataset] = None
        self._current_session: Optional[AcquisitionSession] = None
        self._current_analysis: Optional[AnalysisResult] = None

        # State validation callbacks
        self._state_validators: Dict[WorkflowState, Callable[[], bool]] = {}
        self._state_entry_handlers: Dict[WorkflowState, Callable[[], None]] = {}
        self._state_exit_handlers: Dict[WorkflowState, Callable[[], None]] = {}

        # Workflow timing
        self._workflow_start_time: Optional[datetime] = None
        self._state_start_time: Optional[datetime] = None
        self._total_workflow_timeout = timedelta(hours=24)
        self._state_timeouts: Dict[WorkflowState, timedelta] = {
            WorkflowState.INITIALIZING: timedelta(minutes=5),
            WorkflowState.GENERATING_STIMULUS: timedelta(minutes=30),
            WorkflowState.SPATIAL_SETUP: timedelta(minutes=10),
            WorkflowState.ACQUIRING_DATA: timedelta(hours=2),
            WorkflowState.ANALYZING_DATA: timedelta(hours=1)
        }

        self._setup_default_handlers()

    @property
    def current_state(self) -> WorkflowState:
        """Get current workflow state"""
        return self._current_state

    @property
    def current_parameters(self) -> Optional[CombinedParameters]:
        """Get current workflow parameters"""
        return self._current_parameters

    @property
    def current_dataset(self) -> Optional[StimulusDataset]:
        """Get current stimulus dataset"""
        return self._current_dataset

    @property
    def current_session(self) -> Optional[AcquisitionSession]:
        """Get current acquisition session"""
        return self._current_session

    @property
    def current_analysis(self) -> Optional[AnalysisResult]:
        """Get current analysis result"""
        return self._current_analysis

    def get_valid_transitions(self) -> Set[WorkflowTransition]:
        """Get valid transitions from current state"""
        transitions_map = {
            WorkflowState.UNINITIALIZED: {WorkflowTransition.INITIALIZE_SYSTEM},
            WorkflowState.INITIALIZING: {WorkflowTransition.REPORT_ERROR, WorkflowTransition.REQUEST_SHUTDOWN},
            WorkflowState.READY: {
                WorkflowTransition.START_STIMULUS_GENERATION,
                WorkflowTransition.REQUEST_SHUTDOWN
            },
            WorkflowState.GENERATING_STIMULUS: {
                WorkflowTransition.COMPLETE_STIMULUS_GENERATION,
                WorkflowTransition.REPORT_ERROR,
                WorkflowTransition.REQUEST_SHUTDOWN
            },
            WorkflowState.STIMULUS_READY: {
                WorkflowTransition.START_SPATIAL_SETUP,
                WorkflowTransition.START_STIMULUS_GENERATION,  # Regenerate
                WorkflowTransition.REQUEST_SHUTDOWN
            },
            WorkflowState.SPATIAL_SETUP: {
                WorkflowTransition.COMPLETE_SPATIAL_SETUP,
                WorkflowTransition.REPORT_ERROR,
                WorkflowTransition.REQUEST_SHUTDOWN
            },
            WorkflowState.ACQUISITION_READY: {
                WorkflowTransition.START_ACQUISITION,
                WorkflowTransition.START_SPATIAL_SETUP,  # Redo spatial setup
                WorkflowTransition.REQUEST_SHUTDOWN
            },
            WorkflowState.ACQUIRING_DATA: {
                WorkflowTransition.COMPLETE_ACQUISITION,
                WorkflowTransition.REPORT_ERROR,
                WorkflowTransition.REQUEST_SHUTDOWN
            },
            WorkflowState.DATA_ACQUIRED: {
                WorkflowTransition.START_ANALYSIS,
                WorkflowTransition.START_ACQUISITION,  # Redo acquisition
                WorkflowTransition.REQUEST_SHUTDOWN
            },
            WorkflowState.ANALYZING_DATA: {
                WorkflowTransition.COMPLETE_ANALYSIS,
                WorkflowTransition.REPORT_ERROR,
                WorkflowTransition.REQUEST_SHUTDOWN
            },
            WorkflowState.ANALYSIS_COMPLETE: {
                WorkflowTransition.START_STIMULUS_GENERATION,  # New experiment
                WorkflowTransition.REQUEST_SHUTDOWN
            },
            WorkflowState.ERROR: {
                WorkflowTransition.PERFORM_RECOVERY,
                WorkflowTransition.REQUEST_SHUTDOWN
            },
            WorkflowState.SHUTDOWN: set()  # No transitions from shutdown
        }

        return transitions_map.get(self._current_state, set())

    async def transition(self, transition: WorkflowTransition, **kwargs) -> bool:
        """
        Execute workflow state transition

        Args:
            transition: The transition to execute
            **kwargs: Additional parameters for specific transitions

        Returns:
            True if transition successful, False otherwise
        """
        valid_transitions = self.get_valid_transitions()
        if transition not in valid_transitions:
            domain_error = self.error_handler.create_error(
                error_code="WORKFLOW_TRANSITION_ERROR",
                custom_message=f"Invalid transition {transition.value} from state {self._current_state.value}",
                transition=transition.value,
                current_state=self._current_state.value,
                valid_transitions=[t.value for t in valid_transitions]
            )
            raise ISIDomainError(domain_error)

        try:
            # Execute transition-specific logic
            success = await self._execute_transition(transition, **kwargs)

            if success:
                return True
            else:
                domain_error = self.error_handler.create_error(
                    error_code="WORKFLOW_TRANSITION_ERROR",
                    custom_message=f"Transition {transition.value} failed",
                    transition=transition.value,
                    current_state=self._current_state.value
                )
                raise ISIDomainError(domain_error)

        except ISIDomainError:
            # Re-raise domain errors
            raise
        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="WORKFLOW_TRANSITION_ERROR",
                custom_message=f"Error during transition {transition.value}",
                transition=transition.value,
                current_state=self._current_state.value
            )
            await self._handle_transition_error(str(e))
            raise ISIDomainError(domain_error)

    async def _execute_transition(self, transition: WorkflowTransition, **kwargs) -> bool:
        """Execute specific transition logic"""

        if transition == WorkflowTransition.INITIALIZE_SYSTEM:
            return await self._initialize_system()

        elif transition == WorkflowTransition.START_STIMULUS_GENERATION:
            parameters = kwargs.get('parameters')
            if not parameters:
                domain_error = self.error_handler.create_error(
                    error_code="WORKFLOW_VALIDATION_ERROR",
                    custom_message="Parameters required for stimulus generation",
                    transition=transition.value,
                    missing_parameter="parameters"
                )
                raise ISIDomainError(domain_error)
            return await self._start_stimulus_generation(parameters)

        elif transition == WorkflowTransition.COMPLETE_STIMULUS_GENERATION:
            dataset = kwargs.get('dataset')
            if not dataset:
                domain_error = self.error_handler.create_error(
                    error_code="WORKFLOW_VALIDATION_ERROR",
                    custom_message="Dataset required to complete stimulus generation",
                    transition=transition.value,
                    missing_parameter="dataset"
                )
                raise ISIDomainError(domain_error)
            return await self._complete_stimulus_generation(dataset)

        elif transition == WorkflowTransition.START_SPATIAL_SETUP:
            return await self._start_spatial_setup()

        elif transition == WorkflowTransition.COMPLETE_SPATIAL_SETUP:
            return await self._complete_spatial_setup()

        elif transition == WorkflowTransition.START_ACQUISITION:
            return await self._start_acquisition()

        elif transition == WorkflowTransition.COMPLETE_ACQUISITION:
            session = kwargs.get('session')
            if not session:
                domain_error = self.error_handler.create_error(
                    error_code="WORKFLOW_VALIDATION_ERROR",
                    custom_message="Session required to complete acquisition",
                    transition=transition.value,
                    missing_parameter="session"
                )
                raise ISIDomainError(domain_error)
            return await self._complete_acquisition(session)

        elif transition == WorkflowTransition.START_ANALYSIS:
            return await self._start_analysis()

        elif transition == WorkflowTransition.COMPLETE_ANALYSIS:
            analysis = kwargs.get('analysis')
            if not analysis:
                domain_error = self.error_handler.create_error(
                    error_code="WORKFLOW_VALIDATION_ERROR",
                    custom_message="Analysis result required to complete analysis",
                    transition=transition.value,
                    missing_parameter="analysis"
                )
                raise ISIDomainError(domain_error)
            return await self._complete_analysis(analysis)

        elif transition == WorkflowTransition.REPORT_ERROR:
            error_message = kwargs.get('error_message', 'Unknown error')
            return await self._report_error(error_message)

        elif transition == WorkflowTransition.PERFORM_RECOVERY:
            return await self._perform_recovery()

        elif transition == WorkflowTransition.REQUEST_SHUTDOWN:
            return await self._request_shutdown()

        else:
            domain_error = self.error_handler.create_error(
                error_code="WORKFLOW_TRANSITION_ERROR",
                custom_message=f"Unknown transition: {transition.value}",
                transition=transition.value,
                current_state=self._current_state.value
            )
            raise ISIDomainError(domain_error)

    async def _change_state(self, new_state: WorkflowState):
        """Change workflow state with validation and history tracking"""
        old_state = self._current_state

        # Execute exit handler for current state
        if old_state in self._state_exit_handlers:
            try:
                await self._state_exit_handlers[old_state]()
            except Exception as e:
                # Log exit handler errors but don't fail the state transition
                domain_error = self.error_handler.handle_exception(
                    exception=e,
                    error_code="WORKFLOW_TRANSITION_ERROR",
                    custom_message=f"Error in exit handler for state {old_state.value}",
                    old_state=old_state.value,
                    new_state=new_state.value,
                    handler_type="exit"
                )
                # Continue with state transition

        # Update state history
        if self._state_start_time:
            duration = datetime.now() - self._state_start_time
            self._state_history.append((self._state_start_time, old_state))

        # Change state
        self._current_state = new_state
        self._state_start_time = datetime.now()

        # Execute entry handler for new state
        if new_state in self._state_entry_handlers:
            try:
                await self._state_entry_handlers[new_state]()
            except Exception as e:
                # Entry handler errors are more serious - create domain error
                domain_error = self.error_handler.handle_exception(
                    exception=e,
                    error_code="WORKFLOW_TRANSITION_ERROR",
                    custom_message=f"Error in entry handler for state {new_state.value}",
                    old_state=old_state.value,
                    new_state=new_state.value,
                    handler_type="entry"
                )

    async def _initialize_system(self) -> bool:
        """Initialize system and transition to READY state"""
        await self._change_state(WorkflowState.INITIALIZING)

        # Check hardware system readiness
        ready, issues = self.hardware_system.is_system_ready_for_acquisition()
        if not ready:
            domain_error = self.error_handler.create_error(
                error_code="SYSTEM_STARTUP_ERROR",
                custom_message=f"Hardware system not ready: {issues}",
                hardware_issues=issues,
                current_state=self._current_state.value
            )
            return False

        # Initialize workflow timing
        self._workflow_start_time = datetime.now()

        # Validate system components
        cameras = self.hardware_system.get_cameras()
        displays = self.hardware_system.get_displays()

        if not cameras or not displays:
            domain_error = self.error_handler.create_error(
                error_code="SYSTEM_STARTUP_ERROR",
                custom_message="Required hardware components not available",
                available_cameras=len(cameras) if cameras else 0,
                available_displays=len(displays) if displays else 0,
                current_state=self._current_state.value
            )
            return False

        await self._change_state(WorkflowState.READY)
        return True

    async def _start_stimulus_generation(self, parameters: CombinedParameters) -> bool:
        """Start stimulus generation process"""
        await self._change_state(WorkflowState.GENERATING_STIMULUS)

        # Validate parameters
        if not self._validate_parameters(parameters):
            return False

        self._current_parameters = parameters
        return True

    async def _complete_stimulus_generation(self, dataset: StimulusDataset) -> bool:
        """Complete stimulus generation and transition to STIMULUS_READY"""
        # Validate dataset
        if not dataset.is_complete():
            domain_error = self.error_handler.create_error(
                error_code="DATASET_ERROR",
                custom_message="Dataset is not complete",
                dataset_id=dataset.dataset_id,
                current_state=self._current_state.value
            )
            return False

        self._current_dataset = dataset
        await self._change_state(WorkflowState.STIMULUS_READY)
        return True

    async def _start_spatial_setup(self) -> bool:
        """Start spatial calibration setup"""
        await self._change_state(WorkflowState.SPATIAL_SETUP)

        # Ensure hardware is ready for spatial setup
        cameras = self.hardware_system.get_cameras()
        available_cameras = [cam for cam in cameras if cam.is_available()]

        if not available_cameras:
            domain_error = self.error_handler.create_error(
                error_code="SYSTEM_STARTUP_ERROR",
                custom_message="No cameras available for spatial setup",
                total_cameras=len(cameras),
                available_cameras=0,
                current_state=self._current_state.value
            )
            return False

        return True

    async def _complete_spatial_setup(self) -> bool:
        """Complete spatial setup and transition to ACQUISITION_READY"""
        await self._change_state(WorkflowState.ACQUISITION_READY)
        return True

    async def _start_acquisition(self) -> bool:
        """Start data acquisition process"""
        await self._change_state(WorkflowState.ACQUIRING_DATA)

        # Validate acquisition readiness
        if not self._current_dataset:
            domain_error = self.error_handler.create_error(
                error_code="DATA_ACQUISITION_ERROR",
                custom_message="No stimulus dataset available for acquisition",
                current_state=self._current_state.value
            )
            return False

        # Ensure hardware is ready
        ready, issues = self.hardware_system.is_system_ready_for_acquisition()
        if not ready:
            domain_error = self.error_handler.create_error(
                error_code="DATA_ACQUISITION_ERROR",
                custom_message=f"Hardware not ready for acquisition: {issues}",
                hardware_issues=issues,
                current_state=self._current_state.value
            )
            return False

        return True

    async def _complete_acquisition(self, session: AcquisitionSession) -> bool:
        """Complete data acquisition and transition to DATA_ACQUIRED"""
        # Validate session
        if not session.is_complete():
            domain_error = self.error_handler.create_error(
                error_code="SESSION_VALIDATION_ERROR",
                custom_message="Acquisition session is not complete",
                session_id=session.session_id,
                current_state=self._current_state.value
            )
            return False

        self._current_session = session
        await self._change_state(WorkflowState.DATA_ACQUIRED)
        return True

    async def _start_analysis(self) -> bool:
        """Start data analysis process"""
        await self._change_state(WorkflowState.ANALYZING_DATA)

        if not self._current_session:
            domain_error = self.error_handler.create_error(
                error_code="ISI_ANALYSIS_ERROR",
                custom_message="No acquisition session available for analysis",
                current_state=self._current_state.value
            )
            return False

        return True

    async def _complete_analysis(self, analysis: AnalysisResult) -> bool:
        """Complete data analysis and transition to ANALYSIS_COMPLETE"""
        # Validate analysis result
        if not analysis.is_complete():
            domain_error = self.error_handler.create_error(
                error_code="ISI_ANALYSIS_ERROR",
                custom_message="Analysis result is not complete",
                analysis_id=analysis.analysis_id,
                current_state=self._current_state.value
            )
            return False

        self._current_analysis = analysis
        await self._change_state(WorkflowState.ANALYSIS_COMPLETE)
        return True

    async def _report_error(self, error_message: str) -> bool:
        """Report error and transition to ERROR state"""
        self._error_history.append((datetime.now(), error_message))
        await self._change_state(WorkflowState.ERROR)
        return True

    async def _perform_recovery(self) -> bool:
        """Attempt recovery from error state"""
        # Implement recovery logic based on error type and system state
        # For now, try to return to READY state if hardware is operational

        ready, issues = self.hardware_system.is_system_ready_for_acquisition()
        if ready:
            await self._change_state(WorkflowState.READY)
            return True
        else:
            domain_error = self.error_handler.create_error(
                error_code="WORKFLOW_TRANSITION_ERROR",
                custom_message=f"Recovery failed, hardware issues: {issues}",
                hardware_issues=issues,
                current_state=self._current_state.value,
                operation="recovery"
            )
            return False

    async def _request_shutdown(self) -> bool:
        """Request system shutdown"""
        await self._change_state(WorkflowState.SHUTDOWN)
        return True

    def _validate_parameters(self, parameters: CombinedParameters) -> bool:
        """Validate workflow parameters"""
        try:
            # Validate stimulus parameters
            if not parameters.stimulus_params:
                domain_error = self.error_handler.create_error(
                    error_code="PARAMETER_VALIDATION_ERROR",
                    custom_message="Stimulus parameters missing",
                    current_state=self._current_state.value,
                    missing_parameter="stimulus_params"
                )
                return False

            # Validate acquisition parameters
            if not parameters.acquisition_params:
                domain_error = self.error_handler.create_error(
                    error_code="PARAMETER_VALIDATION_ERROR",
                    custom_message="Acquisition parameters missing",
                    current_state=self._current_state.value,
                    missing_parameter="acquisition_params"
                )
                return False

            # Validate spatial configuration
            if not parameters.spatial_config:
                domain_error = self.error_handler.create_error(
                    error_code="PARAMETER_VALIDATION_ERROR",
                    custom_message="Spatial configuration missing",
                    current_state=self._current_state.value,
                    missing_parameter="spatial_config"
                )
                return False

            # Check hardware compatibility
            cameras = self.hardware_system.get_cameras()
            if cameras:
                camera = cameras[0]  # Use first available camera
                required_resolution = (
                    parameters.acquisition_params.frame_width,
                    parameters.acquisition_params.frame_height
                )
                if not camera.capabilities.supports_resolution(*required_resolution):
                    domain_error = self.error_handler.create_error(
                        error_code="PARAMETER_VALIDATION_ERROR",
                        custom_message=f"Camera does not support required resolution: {required_resolution}",
                        required_resolution=required_resolution,
                        camera_id=camera.camera_id,
                        current_state=self._current_state.value
                    )
                    return False

            return True

        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="PARAMETER_VALIDATION_ERROR",
                custom_message="Parameter validation error",
                current_state=self._current_state.value
            )
            return False

    async def _handle_transition_error(self, error_message: str):
        """Handle errors during state transitions"""
        if self._current_state != WorkflowState.ERROR:
            await self._report_error(f"Transition error: {error_message}")

    def _setup_default_handlers(self):
        """Setup default state entry/exit handlers"""

        async def on_enter_initializing():
            pass

        async def on_enter_error():
            # Attempt to save current state for recovery
            await self._save_workflow_state()

        async def on_enter_shutdown():
            # Cleanup resources
            await self._cleanup_workflow()

        self._state_entry_handlers[WorkflowState.INITIALIZING] = on_enter_initializing
        self._state_entry_handlers[WorkflowState.ERROR] = on_enter_error
        self._state_entry_handlers[WorkflowState.SHUTDOWN] = on_enter_shutdown

    async def _save_workflow_state(self):
        """Save current workflow state for recovery"""
        try:
            state_data = {
                "current_state": self._current_state.value,
                "workflow_start_time": self._workflow_start_time.isoformat() if self._workflow_start_time else None,
                "parameters": self._current_parameters.to_dict() if self._current_parameters else None,
                "dataset_id": self._current_dataset.dataset_id if self._current_dataset else None,
                "session_id": self._current_session.session_id if self._current_session else None,
                "analysis_id": self._current_analysis.analysis_id if self._current_analysis else None,
                "error_history": [(ts.isoformat(), msg) for ts, msg in self._error_history]
            }

            # In a real implementation, this would be saved to persistent storage
            pass

        except Exception as e:
            # Create domain error for save failures but don't propagate
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="PERSISTENCE_ERROR",
                custom_message="Failed to save workflow state",
                current_state=self._current_state.value,
                operation="save_workflow_state"
            )

    async def _cleanup_workflow(self):
        """Cleanup workflow resources"""
        try:
            # Reset workflow data
            self._current_parameters = None
            self._current_dataset = None
            self._current_session = None
            self._current_analysis = None

            pass

        except Exception as e:
            # Create domain error for cleanup failures but don't propagate
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="WORKFLOW_TRANSITION_ERROR",
                custom_message="Error during workflow cleanup",
                current_state=self._current_state.value,
                operation="cleanup_workflow"
            )

    def is_state_timeout_exceeded(self) -> bool:
        """Check if current state has exceeded its timeout"""
        if not self._state_start_time:
            return False

        current_duration = datetime.now() - self._state_start_time
        state_timeout = self._state_timeouts.get(self._current_state)

        if state_timeout and current_duration > state_timeout:
            # Create domain error for timeouts
            domain_error = self.error_handler.create_error(
                error_code="WORKFLOW_TRANSITION_ERROR",
                custom_message=f"State {self._current_state.value} timeout exceeded: {current_duration}",
                current_state=self._current_state.value,
                timeout_duration=str(current_duration),
                allowed_timeout=str(state_timeout)
            )
            return True

        return False

    def is_workflow_timeout_exceeded(self) -> bool:
        """Check if overall workflow has exceeded its timeout"""
        if not self._workflow_start_time:
            return False

        workflow_duration = datetime.now() - self._workflow_start_time
        return workflow_duration > self._total_workflow_timeout

    def get_workflow_status(self) -> Dict[str, Any]:
        """Get comprehensive workflow status"""
        status = {
            "current_state": self._current_state.value,
            "valid_transitions": [t.value for t in self.get_valid_transitions()],
            "workflow_start_time": self._workflow_start_time.isoformat() if self._workflow_start_time else None,
            "state_start_time": self._state_start_time.isoformat() if self._state_start_time else None,
            "state_timeout_exceeded": self.is_state_timeout_exceeded(),
            "workflow_timeout_exceeded": self.is_workflow_timeout_exceeded(),
            "hardware_ready": self.hardware_system.is_system_ready_for_acquisition()[0],
            "current_dataset_id": self._current_dataset.dataset_id if self._current_dataset else None,
            "current_session_id": self._current_session.session_id if self._current_session else None,
            "current_analysis_id": self._current_analysis.analysis_id if self._current_analysis else None,
            "error_count": len(self._error_history),
            "recent_errors": [msg for ts, msg in self._error_history[-5:]]  # Last 5 errors
        }

        return status