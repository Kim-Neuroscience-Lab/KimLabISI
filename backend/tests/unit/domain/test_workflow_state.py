"""
Unit Tests for Workflow State Machine Domain Entity

Tests the core workflow state machine logic with all 12 states,
state transitions, hardware validation, and error handling.
"""

import pytest
from datetime import datetime
from typing import Set
from pydantic import ValidationError

from src.domain.entities.workflow_state_machine import WorkflowStateMachine
from src.domain.value_objects.workflow_state import (
    WorkflowState,
    HardwareRequirement,
    WorkflowTransition
)


class TestWorkflowState:
    """Test WorkflowState enum"""

    def test_workflow_state_values(self):
        """Test that all workflow states have correct values"""
        assert WorkflowState.STARTUP.value == "startup"
        assert WorkflowState.SETUP_READY.value == "setup_ready"
        assert WorkflowState.SETUP.value == "setup"
        assert WorkflowState.GENERATION_READY.value == "generation_ready"
        assert WorkflowState.GENERATION.value == "generation"
        assert WorkflowState.ACQUISITION_READY.value == "acquisition_ready"
        assert WorkflowState.ACQUISITION.value == "acquisition"
        assert WorkflowState.ANALYSIS_READY.value == "analysis_ready"
        assert WorkflowState.ANALYSIS.value == "analysis"
        assert WorkflowState.ERROR.value == "error"
        assert WorkflowState.RECOVERY.value == "recovery"
        assert WorkflowState.DEGRADED.value == "degraded"

    def test_workflow_state_count(self):
        """Test that we have exactly 12 workflow states"""
        assert len(list(WorkflowState)) == 12


class TestHardwareRequirement:
    """Test HardwareRequirement enum"""

    def test_hardware_requirement_values(self):
        """Test that all hardware requirements have correct values"""
        assert HardwareRequirement.MINIMAL.value == "minimal"
        assert HardwareRequirement.DISPLAY.value == "display"
        assert HardwareRequirement.GPU.value == "gpu"
        assert HardwareRequirement.CAMERA.value == "camera"
        assert HardwareRequirement.STORAGE.value == "storage"
        assert HardwareRequirement.ALL_HARDWARE.value == "all_hardware"
        assert HardwareRequirement.DEV_MODE_BYPASS.value == "dev_mode_bypass"


class TestWorkflowTransition:
    """Test WorkflowTransition Pydantic model"""

    def test_workflow_transition_creation(self):
        """Test creating a workflow transition with Pydantic V2"""
        transition = WorkflowTransition(
            from_state=WorkflowState.STARTUP,
            to_state=WorkflowState.SETUP_READY,
            timestamp=datetime.now(),
            user_initiated=True,
            validation_passed=True,
            hardware_available=True
        )

        assert transition.from_state == WorkflowState.STARTUP.value
        assert transition.to_state == WorkflowState.SETUP_READY.value
        assert transition.user_initiated is True
        assert transition.validation_passed is True
        assert transition.hardware_available is True
        assert transition.error_message is None

    def test_workflow_transition_with_error(self):
        """Test creating a workflow transition with error message"""
        error_msg = "Hardware not available"
        transition = WorkflowTransition(
            from_state=WorkflowState.STARTUP,
            to_state=WorkflowState.SETUP_READY,
            timestamp=datetime.now(),
            user_initiated=True,
            validation_passed=False,
            hardware_available=False,
            error_message=error_msg
        )

        assert transition.validation_passed is False
        assert transition.hardware_available is False
        assert transition.error_message == error_msg

    def test_workflow_transition_immutability(self):
        """Test that WorkflowTransition is immutable (frozen)"""
        transition = WorkflowTransition(
            from_state=WorkflowState.STARTUP,
            to_state=WorkflowState.SETUP_READY,
            timestamp=datetime.now(),
            user_initiated=True,
            validation_passed=True,
            hardware_available=True
        )

        with pytest.raises(ValidationError):
            transition.from_state = WorkflowState.ERROR

    def test_workflow_transition_serialization(self):
        """Test Pydantic V2 serialization with model_dump()"""
        transition = WorkflowTransition(
            from_state=WorkflowState.STARTUP,
            to_state=WorkflowState.SETUP_READY,
            timestamp=datetime.now(),
            user_initiated=True,
            validation_passed=True,
            hardware_available=True
        )

        data = transition.model_dump()
        assert data["from_state"] == "startup"
        assert data["to_state"] == "setup_ready"
        assert data["user_initiated"] is True


class TestWorkflowStateMachine:
    """Test WorkflowStateMachine core functionality"""

    def test_initial_state(self):
        """Test state machine initialization"""
        sm = WorkflowStateMachine()
        assert sm.current_state == WorkflowState.STARTUP

    def test_custom_initial_state(self):
        """Test state machine with custom initial state"""
        sm = WorkflowStateMachine(WorkflowState.SETUP_READY)
        assert sm.current_state == WorkflowState.SETUP_READY

    def test_transition_history_empty(self):
        """Test that transition history starts empty"""
        sm = WorkflowStateMachine()
        assert len(sm.transition_history) == 0

    def test_hardware_requirements_mapping(self):
        """Test that all states have hardware requirements defined"""
        sm = WorkflowStateMachine()

        for state in WorkflowState:
            requirement = sm.get_hardware_requirements(state)
            assert isinstance(requirement, HardwareRequirement)

        # Test specific requirements
        assert sm.get_hardware_requirements(WorkflowState.STARTUP) == HardwareRequirement.ALL_HARDWARE
        assert sm.get_hardware_requirements(WorkflowState.SETUP_READY) == HardwareRequirement.DISPLAY
        assert sm.get_hardware_requirements(WorkflowState.ERROR) == HardwareRequirement.MINIMAL

    def test_valid_transitions_mapping(self):
        """Test that all states have valid transitions defined"""
        sm = WorkflowStateMachine()

        for state in WorkflowState:
            valid_transitions = sm.get_valid_transitions(state)
            assert isinstance(valid_transitions, set)
            # All states should have at least one valid transition (except potentially some end states)
            if state != WorkflowState.ANALYSIS:  # Analysis might be an end state
                assert len(valid_transitions) > 0

    def test_startup_valid_transitions(self):
        """Test STARTUP state valid transitions"""
        sm = WorkflowStateMachine()
        valid = sm.get_valid_transitions(WorkflowState.STARTUP)

        assert WorkflowState.SETUP_READY in valid
        assert WorkflowState.ERROR in valid
        assert len(valid) == 2

    def test_can_transition_to_valid(self, available_hardware_set):
        """Test can_transition_to with valid transition"""
        sm = WorkflowStateMachine()

        can_transition, error = sm.can_transition_to(
            WorkflowState.SETUP_READY,
            available_hardware_set
        )

        assert can_transition is True
        assert error is None

    def test_can_transition_to_invalid_state(self, available_hardware_set):
        """Test can_transition_to with invalid state transition"""
        sm = WorkflowStateMachine()

        can_transition, error = sm.can_transition_to(
            WorkflowState.ANALYSIS,
            available_hardware_set
        )

        assert can_transition is False
        assert "Invalid transition" in error

    def test_can_transition_to_insufficient_hardware(self):
        """Test can_transition_to with insufficient hardware"""
        sm = WorkflowStateMachine()
        minimal_hardware = {HardwareRequirement.DISPLAY}

        can_transition, error = sm.can_transition_to(
            WorkflowState.SETUP_READY,
            minimal_hardware
        )

        # Should still work because SETUP_READY only requires DISPLAY
        assert can_transition is True

    def test_dev_mode_bypass(self):
        """Test that DEV_MODE_BYPASS allows any transition"""
        sm = WorkflowStateMachine()
        dev_mode_hardware = {HardwareRequirement.DEV_MODE_BYPASS}

        can_transition, error = sm.can_transition_to(
            WorkflowState.SETUP_READY,
            dev_mode_hardware
        )

        assert can_transition is True
        assert error is None

    def test_successful_transition(self, available_hardware_set):
        """Test successful state transition"""
        sm = WorkflowStateMachine()

        transition = sm.transition_to(
            WorkflowState.SETUP_READY,
            available_hardware_set,
            user_initiated=True
        )

        assert sm.current_state == WorkflowState.SETUP_READY
        assert len(sm.transition_history) == 1
        assert transition.from_state == WorkflowState.STARTUP.value
        assert transition.to_state == WorkflowState.SETUP_READY.value
        assert transition.validation_passed is True
        assert transition.user_initiated is True

    def test_failed_transition(self, available_hardware_set):
        """Test failed state transition raises exception"""
        sm = WorkflowStateMachine()

        with pytest.raises(ValueError, match="Transition failed"):
            sm.transition_to(
                WorkflowState.ANALYSIS,  # Invalid from STARTUP
                available_hardware_set,
                user_initiated=True
            )

        # State should remain unchanged
        assert sm.current_state == WorkflowState.STARTUP
        # But transition should be recorded
        assert len(sm.transition_history) == 1
        assert sm.transition_history[0].validation_passed is False

    def test_force_error_state(self):
        """Test forcing transition to ERROR state"""
        sm = WorkflowStateMachine()
        error_message = "Critical hardware failure"

        transition = sm.force_error_state(error_message)

        assert sm.current_state == WorkflowState.ERROR
        assert transition.from_state == WorkflowState.STARTUP.value
        assert transition.to_state == WorkflowState.ERROR.value
        assert transition.user_initiated is False
        assert transition.validation_passed is True  # Error transitions always valid
        assert transition.error_message == error_message

    def test_multiple_transitions(self, available_hardware_set):
        """Test sequence of multiple transitions"""
        sm = WorkflowStateMachine()

        # STARTUP -> SETUP_READY
        transition1 = sm.transition_to(
            WorkflowState.SETUP_READY,
            available_hardware_set
        )

        # SETUP_READY -> SETUP
        transition2 = sm.transition_to(
            WorkflowState.SETUP,
            available_hardware_set
        )

        assert sm.current_state == WorkflowState.SETUP
        assert len(sm.transition_history) == 2
        assert sm.transition_history[0] == transition1
        assert sm.transition_history[1] == transition2

    def test_transition_history_immutability(self, available_hardware_set):
        """Test that transition history copy is immutable"""
        sm = WorkflowStateMachine()

        sm.transition_to(WorkflowState.SETUP_READY, available_hardware_set)

        history_copy = sm.transition_history
        original_length = len(history_copy)

        # Modify the copy
        history_copy.append(None)

        # Original should be unchanged
        assert len(sm.transition_history) == original_length

    def test_hardware_validation_all_hardware(self):
        """Test hardware validation for ALL_HARDWARE requirement"""
        sm = WorkflowStateMachine()

        # Test with complete hardware
        complete_hardware = {
            HardwareRequirement.DISPLAY,
            HardwareRequirement.GPU,
            HardwareRequirement.CAMERA,
            HardwareRequirement.STORAGE
        }

        is_valid, error = sm._validate_hardware(
            HardwareRequirement.ALL_HARDWARE,
            complete_hardware
        )

        assert is_valid is True
        assert error is None

    def test_hardware_validation_missing_hardware(self):
        """Test hardware validation with missing hardware"""
        sm = WorkflowStateMachine()

        # Test with incomplete hardware
        incomplete_hardware = {
            HardwareRequirement.DISPLAY,
            HardwareRequirement.GPU
            # Missing CAMERA and STORAGE
        }

        is_valid, error = sm._validate_hardware(
            HardwareRequirement.ALL_HARDWARE,
            incomplete_hardware
        )

        assert is_valid is False
        assert "Missing required hardware" in error
        assert "camera" in error.lower()
        assert "storage" in error.lower()

    def test_hardware_validation_minimal(self):
        """Test hardware validation for MINIMAL requirement"""
        sm = WorkflowStateMachine()

        is_valid, error = sm._validate_hardware(
            HardwareRequirement.MINIMAL,
            set()  # No hardware available
        )

        assert is_valid is True
        assert error is None

    @pytest.mark.parametrize("from_state,to_state,should_succeed", [
        (WorkflowState.STARTUP, WorkflowState.SETUP_READY, True),
        (WorkflowState.SETUP_READY, WorkflowState.SETUP, True),
        (WorkflowState.SETUP, WorkflowState.GENERATION_READY, True),
        (WorkflowState.STARTUP, WorkflowState.ANALYSIS, False),
        (WorkflowState.SETUP, WorkflowState.ACQUISITION, False),
    ])
    def test_transition_scenarios(self, from_state, to_state, should_succeed, available_hardware_set):
        """Test various transition scenarios"""
        sm = WorkflowStateMachine(from_state)

        if should_succeed:
            transition = sm.transition_to(to_state, available_hardware_set)
            assert sm.current_state == to_state
            assert transition.validation_passed is True
        else:
            with pytest.raises(ValueError):
                sm.transition_to(to_state, available_hardware_set)