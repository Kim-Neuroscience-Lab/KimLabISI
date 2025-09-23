"""
Test Configuration and Fixtures

Provides shared test fixtures and configuration for the ISI Macroscope Control System test suite.
Uses pytest with Pydantic V2 models and proper isolation between tests.
"""

import pytest
import pytest_asyncio
import asyncio
from typing import Set, Dict, Any
from unittest.mock import Mock, AsyncMock

from src.domain.entities.workflow_state import (
    WorkflowStateMachine,
    WorkflowState,
    HardwareRequirement
)
from src.infrastructure.hardware.factory import HardwareFactory, HardwareCapability
from src.infrastructure.communication.ipc_server import IPCServer
from src.application.handlers.command_handler import CommandHandler


@pytest.fixture(scope="session")
def event_loop_policy():
    """Create an event loop policy for the test session."""
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def mock_hardware_capabilities():
    """Mock hardware capabilities for testing"""
    return {
        HardwareRequirement.DISPLAY: HardwareCapability(
            hardware_type=HardwareRequirement.DISPLAY,
            available=True,
            mock=True,
            details={"type": "mock_display", "platform": "test"}
        ),
        HardwareRequirement.GPU: HardwareCapability(
            hardware_type=HardwareRequirement.GPU,
            available=True,
            mock=True,
            details={"type": "mock_gpu", "model": "Test GPU"}
        ),
        HardwareRequirement.CAMERA: HardwareCapability(
            hardware_type=HardwareRequirement.CAMERA,
            available=True,
            mock=True,
            details={"type": "mock_camera", "model": "Test Camera"}
        ),
        HardwareRequirement.STORAGE: HardwareCapability(
            hardware_type=HardwareRequirement.STORAGE,
            available=True,
            mock=True,
            details={"type": "mock_storage", "location": "test"}
        ),
        HardwareRequirement.DEV_MODE_BYPASS: HardwareCapability(
            hardware_type=HardwareRequirement.DEV_MODE_BYPASS,
            available=True,
            mock=False,
            details={"enabled": "true"}
        )
    }


@pytest.fixture
def available_hardware_set(mock_hardware_capabilities):
    """Set of available hardware requirements for testing"""
    return set(mock_hardware_capabilities.keys())


@pytest.fixture
def workflow_state_machine():
    """Fresh workflow state machine for each test"""
    return WorkflowStateMachine(WorkflowState.STARTUP)


@pytest.fixture
def mock_hardware_factory(mock_hardware_capabilities):
    """Mock hardware factory for testing"""
    factory = Mock(spec=HardwareFactory)
    factory.detect_hardware_capabilities.return_value = mock_hardware_capabilities
    factory.get_available_hardware_requirements.return_value = set(mock_hardware_capabilities.keys())
    factory.development_mode = True
    factory.platform_info.platform_type.value = "test"
    return factory


@pytest_asyncio.fixture
async def ipc_server():
    """IPC server instance for testing"""
    server = IPCServer()
    yield server
    if hasattr(server, '_running') and server._running:
        await server.stop()


@pytest_asyncio.fixture
async def command_handler(mock_hardware_factory):
    """Command handler with mocked dependencies"""
    handler = CommandHandler()
    handler._hardware_factory = mock_hardware_factory
    return handler


@pytest.fixture
def sample_command_data():
    """Sample command data for testing"""
    return {
        "command": "workflow.start",
        "parameters": {},
        "request_id": "test-request-123"
    }


@pytest.fixture
def sample_ipc_message():
    """Sample IPC message for testing"""
    return {
        "message_type": "command",
        "message_id": "test-message-123",
        "timestamp": 1234567890.0,
        "payload": {
            "command": "workflow.start",
            "parameters": {},
            "request_id": "test-request-123"
        }
    }


# Hardware test fixtures

@pytest.fixture
def limited_hardware_capabilities():
    """Limited hardware capabilities for testing error conditions"""
    return {
        HardwareRequirement.DISPLAY: HardwareCapability(
            hardware_type=HardwareRequirement.DISPLAY,
            available=True,
            mock=True,
            details={"type": "mock_display"}
        )
    }


@pytest.fixture
def no_hardware_capabilities():
    """No hardware capabilities for testing error conditions"""
    return {}


@pytest.fixture
def production_hardware_capabilities():
    """Production hardware capabilities for testing"""
    return {
        HardwareRequirement.DISPLAY: HardwareCapability(
            hardware_type=HardwareRequirement.DISPLAY,
            available=True,
            mock=False,
            details={"type": "directx12", "gpu": "RTX 4070"}
        ),
        HardwareRequirement.GPU: HardwareCapability(
            hardware_type=HardwareRequirement.GPU,
            available=True,
            mock=False,
            details={"type": "cuda", "model": "RTX 4070"}
        ),
        HardwareRequirement.CAMERA: HardwareCapability(
            hardware_type=HardwareRequirement.CAMERA,
            available=True,
            mock=False,
            details={"type": "pco_sdk", "model": "PCO Panda 4.2"}
        ),
        HardwareRequirement.STORAGE: HardwareCapability(
            hardware_type=HardwareRequirement.STORAGE,
            available=True,
            mock=False,
            details={"type": "nvme", "model": "Samsung 990 PRO"}
        )
    }


# Async test helpers

@pytest.fixture
def async_mock():
    """Create an AsyncMock for testing async functions"""
    return AsyncMock()


@pytest.fixture
def mock_async_queue():
    """Mock async queue for testing"""
    queue = AsyncMock()
    queue.get = AsyncMock()
    queue.put = AsyncMock()
    return queue


# Test data fixtures

@pytest.fixture
def valid_workflow_states():
    """List of all valid workflow states"""
    return list(WorkflowState)


@pytest.fixture
def valid_hardware_requirements():
    """List of all valid hardware requirements"""
    return list(HardwareRequirement)


@pytest.fixture
def test_transition_scenarios():
    """Common transition scenarios for testing"""
    return [
        {
            "from_state": WorkflowState.STARTUP,
            "to_state": WorkflowState.SETUP_READY,
            "should_succeed": True
        },
        {
            "from_state": WorkflowState.SETUP_READY,
            "to_state": WorkflowState.SETUP,
            "should_succeed": True
        },
        {
            "from_state": WorkflowState.STARTUP,
            "to_state": WorkflowState.ANALYSIS,
            "should_succeed": False
        }
    ]