"""
Integration Tests for Workflow System

Tests the integration between workflow state machine, hardware factory,
IPC server, and command handler working together as a complete system.
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import patch, Mock

from src.domain.entities.workflow_state_machine import WorkflowStateMachine
from src.domain.value_objects.workflow_state import WorkflowState, HardwareRequirement
from src.infrastructure.hardware.factory import HardwareFactory, HardwareCapability
from src.infrastructure.communication.ipc_server import IPCServer, IPCMessage, MessageType
from src.application.handlers.command_handler import CommandHandler


class TestWorkflowIntegration:
    """Test complete workflow integration"""

    @pytest_asyncio.fixture
    async def integrated_system(self):
        """Set up integrated system with all components"""
        # Create components
        ipc_server = IPCServer()
        command_handler = CommandHandler()

        # Register command handler with IPC server
        ipc_server.register_handler("command_handler", command_handler)

        yield {
            "ipc_server": ipc_server,
            "command_handler": command_handler,
            "workflow_sm": command_handler._workflow_state_machine,
            "hardware_factory": command_handler._hardware_factory
        }

        # Cleanup
        if ipc_server._running:
            await ipc_server.stop()

    @pytest.mark.asyncio
    async def test_complete_workflow_start_sequence(self, integrated_system):
        """Test complete workflow start sequence through IPC"""
        ipc_server = integrated_system["ipc_server"]
        command_handler = integrated_system["command_handler"]

        # Simulate workflow start command from frontend
        command_message = IPCMessage(
            message_type=MessageType.COMMAND,
            message_id="start-workflow-123",
            timestamp=1234567890.0,
            payload={
                "command": "workflow.start",
                "parameters": {},
                "request_id": "req-123"
            }
        )

        # Process the command through the IPC server
        await ipc_server._route_message(command_message)

        # Verify workflow state changed
        workflow_sm = command_handler._workflow_state_machine
        assert workflow_sm.current_state == WorkflowState.SETUP_READY
        assert len(workflow_sm.transition_history) == 1

        # Verify transition was recorded correctly
        transition = workflow_sm.transition_history[0]
        assert transition.from_state == WorkflowState.STARTUP.value
        assert transition.to_state == WorkflowState.SETUP_READY.value
        assert transition.user_initiated is True
        assert transition.validation_passed is True

    @pytest.mark.asyncio
    async def test_workflow_state_query_integration(self, integrated_system):
        """Test querying workflow state through integrated system"""
        ipc_server = integrated_system["ipc_server"]
        command_handler = integrated_system["command_handler"]

        # First start the workflow
        await self._send_command(ipc_server, "workflow.start", {})

        # Query the current state
        query_message = IPCMessage(
            message_type=MessageType.COMMAND,
            message_id="query-state-123",
            timestamp=1234567890.0,
            payload={
                "command": "workflow.get_state",
                "parameters": {},
                "request_id": "query-123"
            }
        )

        # Mock the response sending to capture the result
        response_data = None

        async def capture_response(message):
            nonlocal response_data
            response_data = message.payload

        with patch.object(ipc_server, '_send_to_frontend', capture_response):
            await ipc_server._route_message(query_message)

        # Verify response contains correct state information
        assert response_data is not None
        assert response_data["success"] is True
        assert response_data["data"]["current_state"] == "setup_ready"
        assert "valid_transitions" in response_data["data"]
        assert "hardware_requirements" in response_data["data"]

    @pytest.mark.asyncio
    async def test_hardware_detection_integration(self, integrated_system):
        """Test hardware detection through integrated system"""
        ipc_server = integrated_system["ipc_server"]

        # Send hardware detection command
        detect_message = IPCMessage(
            message_type=MessageType.COMMAND,
            message_id="detect-hw-123",
            timestamp=1234567890.0,
            payload={
                "command": "hardware.detect",
                "parameters": {},
                "request_id": "detect-123"
            }
        )

        response_data = None

        async def capture_response(message):
            nonlocal response_data
            response_data = message.payload

        with patch.object(ipc_server, '_send_to_frontend', capture_response):
            await ipc_server._route_message(detect_message)

        # Verify hardware detection response
        assert response_data is not None
        assert response_data["success"] is True
        assert response_data["data"]["hardware_detection_complete"] is True
        assert "capabilities" in response_data["data"]
        assert "available_requirements" in response_data["data"]

    @pytest.mark.asyncio
    async def test_workflow_transition_sequence(self, integrated_system):
        """Test sequence of workflow transitions"""
        ipc_server = integrated_system["ipc_server"]
        command_handler = integrated_system["command_handler"]

        # Start workflow (STARTUP -> SETUP_READY)
        await self._send_command(ipc_server, "workflow.start", {})

        # Transition to SETUP
        await self._send_command(ipc_server, "workflow.transition", {"target_state": "setup"})

        # Verify final state
        workflow_sm = command_handler._workflow_state_machine
        assert workflow_sm.current_state == WorkflowState.SETUP
        assert len(workflow_sm.transition_history) == 2

        # Verify transition sequence
        assert workflow_sm.transition_history[0].to_state == WorkflowState.SETUP_READY.value
        assert workflow_sm.transition_history[1].to_state == WorkflowState.SETUP.value

    @pytest.mark.asyncio
    async def test_invalid_transition_handling(self, integrated_system):
        """Test handling of invalid workflow transitions"""
        ipc_server = integrated_system["ipc_server"]
        command_handler = integrated_system["command_handler"]

        # Try to transition directly from STARTUP to ANALYSIS (invalid)
        transition_message = IPCMessage(
            message_type=MessageType.COMMAND,
            message_id="invalid-transition-123",
            timestamp=1234567890.0,
            payload={
                "command": "workflow.transition",
                "parameters": {"target_state": "analysis"},
                "request_id": "invalid-123"
            }
        )

        response_data = None

        async def capture_response(message):
            nonlocal response_data
            response_data = message.payload

        with patch.object(ipc_server, '_send_to_frontend', capture_response):
            await ipc_server._route_message(transition_message)

        # Verify error response
        assert response_data is not None
        assert response_data["success"] is False
        assert "Invalid transition" in response_data["error_message"]

        # Verify state didn't change
        workflow_sm = command_handler._workflow_state_machine
        assert workflow_sm.current_state == WorkflowState.STARTUP

    @pytest.mark.asyncio
    async def test_system_health_check_integration(self, integrated_system):
        """Test system health check integration"""
        ipc_server = integrated_system["ipc_server"]

        health_message = IPCMessage(
            message_type=MessageType.COMMAND,
            message_id="health-check-123",
            timestamp=1234567890.0,
            payload={
                "command": "system.health_check",
                "parameters": {},
                "request_id": "health-123"
            }
        )

        response_data = None

        async def capture_response(message):
            nonlocal response_data
            response_data = message.payload

        with patch.object(ipc_server, '_send_to_frontend', capture_response):
            await ipc_server._route_message(health_message)

        # Verify health check response
        assert response_data is not None
        assert response_data["success"] is True
        assert "system_healthy" in response_data["data"]
        assert "health_status" in response_data["data"]
        assert response_data["data"]["development_mode"] is True

    @pytest.mark.asyncio
    async def test_hardware_requirements_validation(self, integrated_system):
        """Test hardware requirements validation in workflow"""
        command_handler = integrated_system["command_handler"]

        # Mock limited hardware availability without DEV_MODE_BYPASS to simulate production
        limited_capabilities = {
            HardwareRequirement.DISPLAY: HardwareCapability(
                hardware_type=HardwareRequirement.DISPLAY,
                available=True,
                mock=True,
                details={"type": "mock_display"}
            ),
            # Missing other hardware requirements (GPU, CAMERA, STORAGE)
            # No DEV_MODE_BYPASS to simulate production mode
        }

        with patch.object(command_handler._hardware_factory, 'detect_hardware_capabilities',
                         return_value=limited_capabilities):
            with patch.object(command_handler._hardware_factory, 'get_available_hardware_requirements',
                             return_value=set(limited_capabilities.keys())):

                # Try to start workflow with limited hardware
                workflow_sm = command_handler._workflow_state_machine

                # Move to a state where hardware requirements matter
                workflow_sm._current_state = WorkflowState.SETUP_READY

                # Available hardware only includes DISPLAY
                available_hardware = set(limited_capabilities.keys())

                # Try to transition to ACQUISITION_READY which requires ALL_HARDWARE
                can_transition, error = workflow_sm.can_transition_to(
                    WorkflowState.ACQUISITION_READY,
                    available_hardware
                )

                # This should fail due to missing hardware requirements without DEV_MODE_BYPASS
                assert can_transition is False
                assert "Missing required hardware" in error

    @pytest.mark.asyncio
    async def test_error_state_handling(self, integrated_system):
        """Test error state handling integration"""
        command_handler = integrated_system["command_handler"]
        workflow_sm = command_handler._workflow_state_machine

        # Force an error state
        error_message = "Critical hardware failure"
        transition = workflow_sm.force_error_state(error_message)

        # Verify error state
        assert workflow_sm.current_state == WorkflowState.ERROR
        assert transition.error_message == error_message
        assert transition.user_initiated is False

        # Verify error state allows recovery transitions
        valid_transitions = workflow_sm.get_valid_transitions(WorkflowState.ERROR)
        assert WorkflowState.RECOVERY in valid_transitions
        assert WorkflowState.STARTUP in valid_transitions

    @pytest.mark.asyncio
    async def test_concurrent_command_handling(self, integrated_system):
        """Test handling multiple concurrent commands"""
        ipc_server = integrated_system["ipc_server"]

        # Create multiple commands
        commands = [
            ("workflow.get_state", {}),
            ("hardware.get_status", {}),
            ("system.get_info", {}),
        ]

        # Send commands concurrently
        tasks = []
        for command, params in commands:
            task = asyncio.create_task(
                self._send_command(ipc_server, command, params)
            )
            tasks.append(task)

        # Wait for all commands to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify no exceptions occurred
        for result in results:
            assert not isinstance(result, Exception)

    @pytest.mark.asyncio
    async def test_state_persistence_across_commands(self, integrated_system):
        """Test that state persists correctly across multiple commands"""
        ipc_server = integrated_system["ipc_server"]
        command_handler = integrated_system["command_handler"]

        # Start workflow
        await self._send_command(ipc_server, "workflow.start", {})

        # Get state
        state_response = await self._send_command_with_response(
            ipc_server, "workflow.get_state", {}
        )

        # Verify state is consistent
        assert state_response["data"]["current_state"] == "setup_ready"

        # Get history
        history_response = await self._send_command_with_response(
            ipc_server, "workflow.get_history", {}
        )

        # Verify history contains the start transition
        assert history_response["data"]["total_transitions"] == 1

        # Make another transition
        await self._send_command(ipc_server, "workflow.transition", {"target_state": "setup"})

        # Verify updated history
        history_response = await self._send_command_with_response(
            ipc_server, "workflow.get_history", {}
        )

        assert history_response["data"]["total_transitions"] == 2

    # Helper methods

    async def _send_command(self, ipc_server, command, parameters):
        """Helper to send a command through IPC server"""
        message = IPCMessage(
            message_type=MessageType.COMMAND,
            message_id=f"test-{command}-{id(parameters)}",
            timestamp=1234567890.0,
            payload={
                "command": command,
                "parameters": parameters,
                "request_id": f"req-{command}-{id(parameters)}"
            }
        )

        await ipc_server._route_message(message)

    async def _send_command_with_response(self, ipc_server, command, parameters):
        """Helper to send a command and capture the response"""
        response_data = None

        async def capture_response(message):
            nonlocal response_data
            response_data = message.payload

        with patch.object(ipc_server, '_send_to_frontend', capture_response):
            await self._send_command(ipc_server, command, parameters)

        return response_data


class TestCrossPlatformIntegration:
    """Test cross-platform integration scenarios"""

    @patch('platform.system', return_value='Windows')
    @pytest.mark.asyncio
    async def test_windows_production_integration(self, mock_system):
        """Test integration on Windows production platform"""
        command_handler = CommandHandler()

        # Verify Windows platform setup
        # Note: Will be in development mode due to missing production dependencies
        assert command_handler._hardware_factory.platform_info.platform_type == "windows"

        # Test hardware capabilities detection
        capabilities = command_handler._hardware_factory.detect_hardware_capabilities()
        assert HardwareRequirement.DISPLAY in capabilities
        assert HardwareRequirement.GPU in capabilities

        # Test workflow start in production mode
        workflow_sm = command_handler._workflow_state_machine
        available_hardware = set(capabilities.keys())

        # Should work if all hardware is available
        if len(available_hardware) >= 4:  # Display, GPU, Camera, Storage
            transition = workflow_sm.transition_to(
                WorkflowState.SETUP_READY,
                available_hardware
            )
            assert transition.validation_passed is True

    @patch('platform.system', return_value='Darwin')
    @pytest.mark.asyncio
    async def test_macos_development_integration(self, mock_system):
        """Test integration on macOS development platform"""
        command_handler = CommandHandler()

        # Verify macOS development setup
        assert command_handler._hardware_factory.development_mode is True

        # Test hardware capabilities detection
        capabilities = command_handler._hardware_factory.detect_hardware_capabilities()
        assert HardwareRequirement.DEV_MODE_BYPASS in capabilities

        # Test workflow start in development mode
        workflow_sm = command_handler._workflow_state_machine
        available_hardware = set(capabilities.keys())

        # Should always work in development mode
        transition = workflow_sm.transition_to(
            WorkflowState.SETUP_READY,
            available_hardware
        )
        assert transition.validation_passed is True