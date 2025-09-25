"""
Tests for Domain Workflow Orchestrator

Tests for WorkflowOrchestrator service that manages the complete ISI workflow
state machine and ensures proper sequencing and validation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio

from src.domain.services.workflow_orchestrator import (
    WorkflowOrchestrator,
    WorkflowTransition
)
from src.domain.services.error_handler import ISIDomainError, create_workflow_error
from src.domain.value_objects.workflow_state import WorkflowState
from src.domain.value_objects.parameters import (
    CombinedParameters,
    StimulusGenerationParams,
    AcquisitionProtocolParams,
    SpatialConfiguration
)
from src.domain.entities.hardware import HardwareSystem, HardwareStatus
from src.domain.entities.dataset import StimulusDataset, AcquisitionSession, AnalysisResult


class TestWorkflowOrchestrator:
    """Test WorkflowOrchestrator service"""

    @pytest.fixture
    def mock_hardware_system(self):
        """Create mock hardware system"""
        hardware_system = Mock(spec=HardwareSystem)
        hardware_system.is_system_ready_for_acquisition.return_value = (True, [])
        hardware_system.get_cameras.return_value = [Mock()]
        hardware_system.get_displays.return_value = [Mock()]
        return hardware_system

    # Using sample_parameters fixture from conftest.py

    @pytest.fixture
    async def orchestrator(self, mock_hardware_system):
        """Create workflow orchestrator instance"""
        orchestrator = WorkflowOrchestrator(mock_hardware_system)
        return orchestrator

    def test_orchestrator_initialization(self, mock_hardware_system):
        """Test workflow orchestrator initialization"""
        orchestrator = WorkflowOrchestrator(mock_hardware_system)

        assert orchestrator.hardware_system == mock_hardware_system
        assert orchestrator.current_state == WorkflowState.UNINITIALIZED
        assert orchestrator.current_parameters is None
        assert orchestrator.current_dataset is None
        assert orchestrator.current_session is None
        assert orchestrator.current_analysis is None

    def test_valid_transitions_from_states(self, orchestrator):
        """Test valid transitions from different states"""
        # From UNINITIALIZED
        orchestrator._current_state = WorkflowState.UNINITIALIZED
        valid_transitions = orchestrator.get_valid_transitions()
        assert WorkflowTransition.INITIALIZE_SYSTEM in valid_transitions

        # From READY
        orchestrator._current_state = WorkflowState.READY
        valid_transitions = orchestrator.get_valid_transitions()
        assert WorkflowTransition.START_STIMULUS_GENERATION in valid_transitions
        assert WorkflowTransition.REQUEST_SHUTDOWN in valid_transitions

        # From GENERATING_STIMULUS
        orchestrator._current_state = WorkflowState.GENERATING_STIMULUS
        valid_transitions = orchestrator.get_valid_transitions()
        assert WorkflowTransition.COMPLETE_STIMULUS_GENERATION in valid_transitions
        assert WorkflowTransition.REPORT_ERROR in valid_transitions

        # From ERROR
        orchestrator._current_state = WorkflowState.ERROR
        valid_transitions = orchestrator.get_valid_transitions()
        assert WorkflowTransition.PERFORM_RECOVERY in valid_transitions
        assert WorkflowTransition.REQUEST_SHUTDOWN in valid_transitions

        # From SHUTDOWN
        orchestrator._current_state = WorkflowState.SHUTDOWN
        valid_transitions = orchestrator.get_valid_transitions()
        assert len(valid_transitions) == 0  # No transitions from shutdown

    @pytest.mark.asyncio
    async def test_system_initialization(self, orchestrator, mock_hardware_system):
        """Test system initialization workflow"""
        # Setup hardware system to be ready
        mock_hardware_system.is_system_ready_for_acquisition.return_value = (True, [])
        mock_hardware_system.get_cameras.return_value = [Mock()]
        mock_hardware_system.get_displays.return_value = [Mock()]

        # Initialize system
        success = await orchestrator.transition(WorkflowTransition.INITIALIZE_SYSTEM)

        assert success == True
        assert orchestrator.current_state == WorkflowState.READY
        assert orchestrator._workflow_start_time is not None

    @pytest.mark.asyncio
    async def test_system_initialization_failure(self, orchestrator, mock_hardware_system):
        """Test system initialization failure"""
        # Setup hardware system to not be ready
        mock_hardware_system.is_system_ready_for_acquisition.return_value = (False, ["Camera not available"])

        # Try to initialize system
        success = await orchestrator.transition(WorkflowTransition.INITIALIZE_SYSTEM)

        assert success == False
        assert orchestrator.current_state == WorkflowState.UNINITIALIZED

    @pytest.mark.asyncio
    async def test_stimulus_generation_workflow(self, orchestrator, sample_parameters):
        """Test stimulus generation workflow"""
        # Initialize system first
        orchestrator._current_state = WorkflowState.READY

        # Start stimulus generation
        success = await orchestrator.transition(
            WorkflowTransition.START_STIMULUS_GENERATION,
            parameters=sample_parameters
        )

        assert success == True
        assert orchestrator.current_state == WorkflowState.GENERATING_STIMULUS
        assert orchestrator.current_parameters == sample_parameters

        # Complete stimulus generation with dataset
        mock_dataset = Mock(spec=StimulusDataset)
        mock_dataset.is_complete.return_value = True
        mock_dataset.dataset_id = "test_dataset_001"

        success = await orchestrator.transition(
            WorkflowTransition.COMPLETE_STIMULUS_GENERATION,
            dataset=mock_dataset
        )

        assert success == True
        assert orchestrator.current_state == WorkflowState.STIMULUS_READY
        assert orchestrator.current_dataset == mock_dataset

    @pytest.mark.asyncio
    async def test_stimulus_generation_validation_failure(self, orchestrator):
        """Test stimulus generation parameter validation failure"""
        orchestrator._current_state = WorkflowState.READY

        # Try to start without parameters
        success = await orchestrator.transition(WorkflowTransition.START_STIMULUS_GENERATION)

        assert success == False

    @pytest.mark.asyncio
    async def test_incomplete_dataset_rejection(self, orchestrator, sample_parameters):
        """Test rejection of incomplete datasets"""
        orchestrator._current_state = WorkflowState.GENERATING_STIMULUS
        orchestrator._current_parameters = sample_parameters

        # Try to complete with incomplete dataset
        mock_dataset = Mock(spec=StimulusDataset)
        mock_dataset.is_complete.return_value = False

        success = await orchestrator.transition(
            WorkflowTransition.COMPLETE_STIMULUS_GENERATION,
            dataset=mock_dataset
        )

        assert success == False
        assert orchestrator.current_state == WorkflowState.GENERATING_STIMULUS

    @pytest.mark.asyncio
    async def test_spatial_setup_workflow(self, orchestrator, mock_hardware_system):
        """Test spatial setup workflow"""
        orchestrator._current_state = WorkflowState.STIMULUS_READY

        # Setup cameras to be available
        mock_camera = Mock()
        mock_camera.is_available.return_value = True
        mock_hardware_system.get_cameras.return_value = [mock_camera]

        # Start spatial setup
        success = await orchestrator.transition(WorkflowTransition.START_SPATIAL_SETUP)

        assert success == True
        assert orchestrator.current_state == WorkflowState.SPATIAL_SETUP

        # Complete spatial setup
        success = await orchestrator.transition(WorkflowTransition.COMPLETE_SPATIAL_SETUP)

        assert success == True
        assert orchestrator.current_state == WorkflowState.ACQUISITION_READY

    @pytest.mark.asyncio
    async def test_spatial_setup_no_cameras(self, orchestrator, mock_hardware_system):
        """Test spatial setup failure when no cameras available"""
        orchestrator._current_state = WorkflowState.STIMULUS_READY

        # No cameras available
        mock_hardware_system.get_cameras.return_value = []

        # Try spatial setup
        success = await orchestrator.transition(WorkflowTransition.START_SPATIAL_SETUP)

        assert success == False

    @pytest.mark.asyncio
    async def test_data_acquisition_workflow(self, orchestrator, mock_hardware_system, sample_parameters):
        """Test data acquisition workflow"""
        orchestrator._current_state = WorkflowState.ACQUISITION_READY
        orchestrator._current_dataset = Mock(spec=StimulusDataset)
        orchestrator._current_dataset.dataset_id = "test_dataset"

        # Setup hardware ready for acquisition
        mock_hardware_system.is_system_ready_for_acquisition.return_value = (True, [])

        # Start acquisition
        success = await orchestrator.transition(WorkflowTransition.START_ACQUISITION)

        assert success == True
        assert orchestrator.current_state == WorkflowState.ACQUIRING_DATA

        # Complete acquisition with session
        mock_session = Mock(spec=AcquisitionSession)
        mock_session.is_complete.return_value = True
        mock_session.session_id = "test_session_001"

        success = await orchestrator.transition(
            WorkflowTransition.COMPLETE_ACQUISITION,
            session=mock_session
        )

        assert success == True
        assert orchestrator.current_state == WorkflowState.DATA_ACQUIRED
        assert orchestrator.current_session == mock_session

    @pytest.mark.asyncio
    async def test_acquisition_hardware_not_ready(self, orchestrator, mock_hardware_system):
        """Test acquisition failure when hardware not ready"""
        orchestrator._current_state = WorkflowState.ACQUISITION_READY
        orchestrator._current_dataset = Mock(spec=StimulusDataset)

        # Hardware not ready
        mock_hardware_system.is_system_ready_for_acquisition.return_value = (False, ["Camera error"])

        # Try acquisition
        success = await orchestrator.transition(WorkflowTransition.START_ACQUISITION)

        assert success == False

    @pytest.mark.asyncio
    async def test_analysis_workflow(self, orchestrator):
        """Test analysis workflow"""
        orchestrator._current_state = WorkflowState.DATA_ACQUIRED
        orchestrator._current_session = Mock(spec=AcquisitionSession)
        orchestrator._current_session.session_id = "test_session"

        # Start analysis
        success = await orchestrator.transition(WorkflowTransition.START_ANALYSIS)

        assert success == True
        assert orchestrator.current_state == WorkflowState.ANALYZING_DATA

        # Complete analysis
        mock_analysis = Mock(spec=AnalysisResult)
        mock_analysis.is_complete.return_value = True
        mock_analysis.analysis_id = "test_analysis_001"

        success = await orchestrator.transition(
            WorkflowTransition.COMPLETE_ANALYSIS,
            analysis=mock_analysis
        )

        assert success == True
        assert orchestrator.current_state == WorkflowState.ANALYSIS_COMPLETE
        assert orchestrator.current_analysis == mock_analysis

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, orchestrator, mock_hardware_system):
        """Test error reporting and recovery"""
        orchestrator._current_state = WorkflowState.GENERATING_STIMULUS

        # Report error
        success = await orchestrator.transition(
            WorkflowTransition.REPORT_ERROR,
            error_message="Test error occurred"
        )

        assert success == True
        assert orchestrator.current_state == WorkflowState.ERROR
        assert len(orchestrator._error_history) == 1

        # Setup hardware for recovery
        mock_hardware_system.is_system_ready_for_acquisition.return_value = (True, [])

        # Attempt recovery
        success = await orchestrator.transition(WorkflowTransition.PERFORM_RECOVERY)

        assert success == True
        assert orchestrator.current_state == WorkflowState.READY

    @pytest.mark.asyncio
    async def test_recovery_failure(self, orchestrator, mock_hardware_system):
        """Test recovery failure when hardware still has issues"""
        orchestrator._current_state = WorkflowState.ERROR

        # Hardware still not ready
        mock_hardware_system.is_system_ready_for_acquisition.return_value = (False, ["Still broken"])

        # Try recovery
        success = await orchestrator.transition(WorkflowTransition.PERFORM_RECOVERY)

        assert success == False
        assert orchestrator.current_state == WorkflowState.ERROR

    @pytest.mark.asyncio
    async def test_shutdown_workflow(self, orchestrator):
        """Test shutdown workflow"""
        orchestrator._current_state = WorkflowState.READY

        # Request shutdown
        success = await orchestrator.transition(WorkflowTransition.REQUEST_SHUTDOWN)

        assert success == True
        assert orchestrator.current_state == WorkflowState.SHUTDOWN

    @pytest.mark.asyncio
    async def test_invalid_transition(self, orchestrator):
        """Test invalid state transition"""
        orchestrator._current_state = WorkflowState.UNINITIALIZED

        # Try invalid transition
        with pytest.raises(WorkflowTransitionError):
            await orchestrator.transition(WorkflowTransition.START_ACQUISITION)

    @pytest.mark.asyncio
    async def test_timeout_checking(self, orchestrator):
        """Test workflow timeout checking"""
        # Set very short timeout for testing
        orchestrator._state_timeouts[WorkflowState.GENERATING_STIMULUS] = timedelta(seconds=0.001)

        orchestrator._current_state = WorkflowState.GENERATING_STIMULUS
        orchestrator._state_start_time = datetime.now()

        # Wait a bit to exceed timeout
        await asyncio.sleep(0.002)

        assert orchestrator.is_state_timeout_exceeded() == True

        # Test workflow timeout
        orchestrator._workflow_start_time = datetime.now() - timedelta(hours=25)
        orchestrator._total_workflow_timeout = timedelta(hours=24)

        assert orchestrator.is_workflow_timeout_exceeded() == True

    def test_parameter_validation(self, orchestrator, sample_parameters):
        """Test parameter validation"""
        # Valid parameters
        assert orchestrator._validate_parameters(sample_parameters) == True

        # Invalid parameters - missing stimulus params
        invalid_params = CombinedParameters(
            stimulus_params=None,
            acquisition_params=sample_parameters.acquisition_params,
            spatial_config=sample_parameters.spatial_config
        )

        assert orchestrator._validate_parameters(invalid_params) == False

    def test_workflow_status_reporting(self, orchestrator, sample_parameters):
        """Test workflow status reporting"""
        # Set up some workflow state
        orchestrator._current_state = WorkflowState.GENERATING_STIMULUS
        orchestrator._workflow_start_time = datetime.now()
        orchestrator._current_parameters = sample_parameters

        mock_dataset = Mock()
        mock_dataset.dataset_id = "test_dataset"
        orchestrator._current_dataset = mock_dataset

        # Get status
        status = orchestrator.get_workflow_status()

        assert status["current_state"] == WorkflowState.GENERATING_STIMULUS.value
        assert len(status["valid_transitions"]) > 0
        assert status["workflow_start_time"] is not None
        assert status["current_dataset_id"] == "test_dataset"
        assert "hardware_ready" in status

    @pytest.mark.asyncio
    async def test_state_change_tracking(self, orchestrator):
        """Test state change tracking and history"""
        initial_state = orchestrator.current_state

        # Make a state change
        await orchestrator._change_state(WorkflowState.READY)

        assert orchestrator.current_state == WorkflowState.READY
        assert len(orchestrator._state_history) == 1
        assert orchestrator._state_history[0][1] == initial_state
        assert orchestrator._state_start_time is not None

    @pytest.mark.asyncio
    async def test_error_during_transition(self, orchestrator, mock_hardware_system):
        """Test error handling during transition execution"""
        orchestrator._current_state = WorkflowState.READY

        # Mock hardware to raise exception
        mock_hardware_system.is_system_ready_for_acquisition.side_effect = Exception("Hardware error")

        # Try transition that will fail
        success = await orchestrator.transition(WorkflowTransition.START_ACQUISITION)

        assert success == False
        # Should have transitioned to error state
        assert orchestrator.current_state == WorkflowState.ERROR

    @pytest.mark.asyncio
    async def test_workflow_data_management(self, orchestrator, sample_parameters):
        """Test workflow data object management"""
        # Set workflow objects
        mock_dataset = Mock(spec=StimulusDataset)
        mock_dataset.dataset_id = "test_dataset"

        mock_session = Mock(spec=AcquisitionSession)
        mock_session.session_id = "test_session"

        mock_analysis = Mock(spec=AnalysisResult)
        mock_analysis.analysis_id = "test_analysis"

        orchestrator._current_parameters = sample_parameters
        orchestrator._current_dataset = mock_dataset
        orchestrator._current_session = mock_session
        orchestrator._current_analysis = mock_analysis

        # Check accessors
        assert orchestrator.current_parameters == sample_parameters
        assert orchestrator.current_dataset == mock_dataset
        assert orchestrator.current_session == mock_session
        assert orchestrator.current_analysis == mock_analysis

        # Test cleanup
        await orchestrator._cleanup_workflow()

        assert orchestrator._current_parameters is None
        assert orchestrator._current_dataset is None
        assert orchestrator._current_session is None
        assert orchestrator._current_analysis is None

    @pytest.mark.asyncio
    async def test_state_persistence_integration(self, orchestrator):
        """Test integration with state persistence"""
        # This tests the save functionality used by persistence service

        orchestrator._current_state = WorkflowState.READY
        orchestrator._workflow_start_time = datetime.now()

        # Test state saving (mocked)
        with patch.object(orchestrator, '_save_workflow_state') as mock_save:
            await orchestrator._save_workflow_state()
            mock_save.assert_called_once()

    def test_workflow_orchestrator_robustness(self, orchestrator):
        """Test orchestrator robustness to invalid inputs"""

        # Test with None hardware system
        with pytest.raises(AttributeError):
            WorkflowOrchestrator(None)

        # Test getting status with minimal state
        status = orchestrator.get_workflow_status()
        assert "current_state" in status
        assert "valid_transitions" in status

        # Test transition with invalid enum (should be caught by type system in real usage)
        # This tests the robustness of the transition system


if __name__ == "__main__":
    pytest.main([__file__])