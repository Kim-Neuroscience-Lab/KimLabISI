"""
Backend Main Entry Point Integration Tests

Tests the complete backend initialization and integration
of all system components through the main entry point.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock

from src.isi_control.main import ISIMacroscopeBackend


class TestBackendMain:
    """Test the main backend entry point integration"""

    @pytest.mark.asyncio
    async def test_backend_initialization(self):
        """Test complete backend initialization"""
        backend = ISIMacroscopeBackend(development_mode=True)

        # Test initialization
        await backend.initialize()

        # Verify all components are initialized
        assert backend.workflow_state_machine is not None
        assert backend.hardware_factory is not None
        assert backend.ipc_server is not None
        assert backend.command_handler is not None

        # Verify system info
        info = backend.get_system_info()
        assert info["backend_version"] == "1.0.0"
        assert info["development_mode"] is True
        assert info["current_state"] == "startup"
        assert info["hardware_capabilities"] >= 4

    @pytest.mark.asyncio
    async def test_backend_development_mode(self):
        """Test backend in development mode"""
        backend = ISIMacroscopeBackend(development_mode=True)
        await backend.initialize()

        # Verify development mode is properly set
        assert backend.development_mode is True
        assert backend.hardware_factory.development_mode is True

        # Verify dev mode bypass is available
        capabilities = backend.hardware_factory.detect_hardware_capabilities()
        from src.domain.value_objects.workflow_state import HardwareRequirement
        assert HardwareRequirement.DEV_MODE_BYPASS in capabilities

    @pytest.mark.asyncio
    async def test_backend_production_mode(self):
        """Test backend in production mode"""
        backend = ISIMacroscopeBackend(development_mode=False)
        await backend.initialize()

        # Verify production mode settings
        assert backend.development_mode is False

        # Note: hardware_factory.development_mode might still be True on macOS
        # This is correct behavior per the platform detection logic

    @pytest.mark.asyncio
    async def test_backend_health_check(self):
        """Test backend health check functionality"""
        backend = ISIMacroscopeBackend(development_mode=True)
        await backend.initialize()

        # Health check is performed during initialization
        # If we reach here, health check passed
        assert backend.workflow_state_machine is not None
        assert backend.hardware_factory is not None
        assert backend.command_handler is not None
        assert backend.ipc_server is not None

    @pytest.mark.asyncio
    async def test_ipc_handler_registration(self):
        """Test IPC handler registration"""
        backend = ISIMacroscopeBackend(development_mode=True)
        await backend.initialize()

        # Verify command handler is registered
        assert "command_handler" in backend.ipc_server._handlers
        assert backend.ipc_server._handlers["command_handler"] == backend.command_handler

    @pytest.mark.asyncio
    async def test_system_info_structure(self):
        """Test system info structure through proper Clean Architecture CommandHandler"""
        backend = ISIMacroscopeBackend(development_mode=True, host="test", port=9999)
        await backend.initialize()

        # Test system info through CommandHandler (proper architecture)
        from src.application.handlers.command_handler import CommandRequest

        command_request = CommandRequest(
            command_type="system.get_info",
            parameters={},
            request_id="test-system-info"
        )

        response = await backend.command_handler.handle_command(command_request)

        assert response.success is True
        assert "platform_info" in response.data
        assert "workflow_state" in response.data
        assert "development_mode" in response.data
        assert response.data["development_mode"] is True

    @pytest.mark.asyncio
    async def test_backend_stop_gracefully(self):
        """Test backend graceful shutdown"""
        backend = ISIMacroscopeBackend(development_mode=True)
        await backend.initialize()

        # Mock the IPC server stop method
        backend.ipc_server.stop = MagicMock(return_value=asyncio.create_task(asyncio.sleep(0)))

        # Test stop
        await backend.stop()

        assert backend.running is False
        backend.ipc_server.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_component_integration(self):
        """Test integration between all components"""
        backend = ISIMacroscopeBackend(development_mode=True)
        await backend.initialize()

        # Test workflow state machine integration
        from src.domain.value_objects.workflow_state import WorkflowState
        assert backend.workflow_state_machine.current_state == WorkflowState.STARTUP

        # Test hardware factory integration
        capabilities = backend.hardware_factory.detect_hardware_capabilities()
        assert len(capabilities) >= 4

        # Test command handler can access components
        assert backend.command_handler._workflow_state_machine is not None
        assert backend.command_handler._hardware_factory is not None

        # Test IPC server has handlers registered
        assert len(backend.ipc_server._handlers) >= 1