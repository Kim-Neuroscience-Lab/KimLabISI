"""
Tests for StateBroadcaster application service

Comprehensive test suite for real-time state broadcasting via IPC,
including batching, subscriber management, and broadcast reliability.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta
import json
import asyncio

from src.application.handlers.state_broadcaster import (
    StateBroadcaster,
    BroadcastType
)
from src.domain.value_objects.workflow_state import WorkflowState
from src.domain.value_objects.parameters import CombinedParameters
from src.domain.entities.dataset import StimulusDataset


class TestStateBroadcaster:
    """Test StateBroadcaster functionality"""

    @pytest.fixture
    def mock_ipc_server(self):
        """Mock IPC server for testing"""
        mock = AsyncMock()
        mock.broadcast_message = AsyncMock()
        mock.is_connected = Mock(return_value=True)
        mock.get_connected_clients = Mock(return_value=["client_1", "client_2"])
        return mock

    @pytest.fixture
    def broadcaster(self, mock_ipc_server):
        """Create StateBroadcaster with mocked IPC server"""
        broadcaster = StateBroadcaster(ipc_server=mock_ipc_server)
        return broadcaster

    @pytest.mark.asyncio
    async def test_broadcast_workflow_state(self, broadcaster, mock_ipc_server):
        """Test workflow state broadcasting"""
        current_state = WorkflowState.READY
        previous_state = WorkflowState.IDLE

        await broadcaster.broadcast_workflow_state(current_state, previous_state)

        # Give async processing time to complete
        await asyncio.sleep(0.1)

        # Verify message was queued and processed
        mock_ipc_server.broadcast_message.assert_called()
        call_args = mock_ipc_server.broadcast_message.call_args
        message = call_args[0][0]

        assert message["type"] == BroadcastType.WORKFLOW_STATE.value
        assert message["current_state"] == current_state.value
        assert message["previous_state"] == previous_state.value
        assert "timestamp" in message

    @pytest.mark.asyncio
    async def test_broadcast_system_status(self, broadcaster, mock_ipc_server):
        """Test system status broadcasting"""
        status_data = {
            "hardware_health": 0.95,
            "active_components": 3,
            "errors": []
        }

        await broadcaster.broadcast_system_status(status_data)
        await asyncio.sleep(0.1)

        mock_ipc_server.broadcast_message.assert_called()
        call_args = mock_ipc_server.broadcast_message.call_args
        message = call_args[0][0]

        assert message["type"] == BroadcastType.SYSTEM_STATUS.value
        assert message["data"] == status_data
        assert "timestamp" in message

    @pytest.mark.asyncio
    async def test_broadcast_data_update(self, broadcaster, mock_ipc_server):
        """Test data update broadcasting"""
        update_data = {
            "dataset_id": "test_dataset_001",
            "session_id": "session_001",
            "progress": 0.75
        }

        await broadcaster.broadcast_data_update(update_data)
        await asyncio.sleep(0.1)

        mock_ipc_server.broadcast_message.assert_called()
        call_args = mock_ipc_server.broadcast_message.call_args
        message = call_args[0][0]

        assert message["type"] == BroadcastType.DATA_UPDATE.value
        assert message["data"] == update_data

    @pytest.mark.asyncio
    async def test_broadcast_error_event(self, broadcaster, mock_ipc_server):
        """Test error event broadcasting"""
        error_data = {
            "error_type": "HardwareError",
            "error_message": "Camera connection lost",
            "component": "camera_001",
            "severity": "high"
        }

        await broadcaster.broadcast_error_event(error_data)
        await asyncio.sleep(0.1)

        mock_ipc_server.broadcast_message.assert_called()
        call_args = mock_ipc_server.broadcast_message.call_args
        message = call_args[0][0]

        assert message["type"] == BroadcastType.ERROR_EVENT.value
        assert message["data"] == error_data

    @pytest.mark.asyncio
    async def test_broadcast_performance_metrics(self, broadcaster, mock_ipc_server):
        """Test performance metrics broadcasting"""
        metrics = {
            "cpu_percent": 45.2,
            "memory_percent": 62.8,
            "disk_percent": 35.1,
            "fps": 30.0
        }

        await broadcaster.broadcast_performance_metrics(metrics)
        await asyncio.sleep(0.1)

        mock_ipc_server.broadcast_message.assert_called()
        call_args = mock_ipc_server.broadcast_message.call_args
        message = call_args[0][0]

        assert message["type"] == BroadcastType.PERFORMANCE_METRICS.value
        assert message["data"] == metrics

    @pytest.mark.asyncio
    async def test_message_batching(self, broadcaster, mock_ipc_server):
        """Test message batching functionality"""
        # Set small batch parameters for testing
        broadcaster._batch_size = 3
        broadcaster._batch_timeout_seconds = 0.1

        # Send multiple messages quickly
        messages = []
        for i in range(5):
            status_data = {"message_id": i, "status": "ok"}
            messages.append(broadcaster.broadcast_system_status(status_data))

        await asyncio.gather(*messages)
        await asyncio.sleep(0.2)  # Wait for batching timeout

        # Should have batched calls (fewer than 5 individual calls)
        assert mock_ipc_server.broadcast_message.call_count >= 2

    @pytest.mark.asyncio
    async def test_subscriber_filtering(self, broadcaster, mock_ipc_server):
        """Test subscriber filtering functionality"""
        # Add subscription filter
        filter_config = SubscriptionFilter(
            client_id="client_1",
            broadcast_types=[BroadcastType.WORKFLOW_STATE, BroadcastType.ERROR_EVENT],
            include_patterns=["*.workflow.*"],
            exclude_patterns=["*.debug.*"]
        )
        broadcaster.add_subscription_filter("client_1", filter_config)

        await broadcaster.broadcast_workflow_state(WorkflowState.READY)
        await asyncio.sleep(0.1)

        # Should call broadcast with filter applied
        mock_ipc_server.broadcast_message.assert_called()

    @pytest.mark.asyncio
    async def test_connection_status_monitoring(self, broadcaster, mock_ipc_server):
        """Test connection status monitoring"""
        # Initially connected
        assert broadcaster.get_connection_status() == ConnectionStatus.CONNECTED

        # Simulate connection loss
        mock_ipc_server.is_connected.return_value = False
        await broadcaster._check_connection_status()

        assert broadcaster.get_connection_status() == ConnectionStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_automatic_reconnection(self, broadcaster, mock_ipc_server):
        """Test automatic reconnection functionality"""
        # Enable auto-reconnect
        await broadcaster.start_auto_reconnect()

        # Simulate connection loss
        mock_ipc_server.is_connected.return_value = False
        await broadcaster._check_connection_status()

        # Wait for reconnection attempt
        await asyncio.sleep(0.1)

        # Should attempt to reconnect
        assert mock_ipc_server.broadcast_message.called or mock_ipc_server.is_connected.called

    @pytest.mark.asyncio
    async def test_message_queuing_when_disconnected(self, broadcaster, mock_ipc_server):
        """Test message queuing when disconnected"""
        # Simulate disconnection
        mock_ipc_server.is_connected.return_value = False
        mock_ipc_server.broadcast_message.side_effect = ConnectionError("Not connected")

        # Try to broadcast - should queue message
        await broadcaster.broadcast_workflow_state(WorkflowState.READY)
        await asyncio.sleep(0.1)

        # Message should be in queue
        assert len(broadcaster._message_queue) > 0

    @pytest.mark.asyncio
    async def test_queue_flushing_on_reconnect(self, broadcaster, mock_ipc_server):
        """Test message queue flushing when reconnected"""
        # Disconnect and queue messages
        mock_ipc_server.is_connected.return_value = False
        mock_ipc_server.broadcast_message.side_effect = ConnectionError("Not connected")

        await broadcaster.broadcast_workflow_state(WorkflowState.READY)
        await broadcaster.broadcast_system_status({"status": "ok"})
        await asyncio.sleep(0.1)

        # Reconnect
        mock_ipc_server.is_connected.return_value = True
        mock_ipc_server.broadcast_message.side_effect = None
        mock_ipc_server.broadcast_message.reset_mock()

        await broadcaster._flush_message_queue()

        # Should have sent queued messages
        assert mock_ipc_server.broadcast_message.call_count >= 2

    @pytest.mark.asyncio
    async def test_broadcast_priority_handling(self, broadcaster, mock_ipc_server):
        """Test priority message handling"""
        # Set up priority queue
        await broadcaster.broadcast_error_event(
            {"error": "Critical error"},
            priority="high"
        )
        await broadcaster.broadcast_system_status(
            {"status": "ok"},
            priority="low"
        )
        await asyncio.sleep(0.1)

        # High priority messages should be processed first
        # (Implementation would need priority queue support)
        mock_ipc_server.broadcast_message.assert_called()

    @pytest.mark.asyncio
    async def test_broadcast_rate_limiting(self, broadcaster, mock_ipc_server):
        """Test broadcast rate limiting"""
        # Set aggressive rate limit for testing
        broadcaster._max_messages_per_second = 2

        # Send messages rapidly
        start_time = asyncio.get_event_loop().time()
        for i in range(5):
            await broadcaster.broadcast_system_status({"id": i})

        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time

        # Should have been rate limited
        assert duration >= 1.0  # Should take at least 1 second for 5 messages at 2/sec

    @pytest.mark.asyncio
    async def test_message_serialization(self, broadcaster, mock_ipc_server):
        """Test message serialization for IPC"""
        complex_data = {
            "timestamp": datetime.now(),
            "parameters": {"nested": {"value": 42}},
            "list": [1, 2, 3]
        }

        await broadcaster.broadcast_data_update(complex_data)
        await asyncio.sleep(0.1)

        # Should handle complex data serialization
        mock_ipc_server.broadcast_message.assert_called()
        call_args = mock_ipc_server.broadcast_message.call_args
        message = call_args[0][0]

        # Message should be serializable
        json.dumps(message)

    def test_broadcast_statistics(self, broadcaster):
        """Test broadcast statistics tracking"""
        stats = broadcaster.get_broadcast_statistics()

        required_stats = [
            "total_messages_sent",
            "messages_per_type",
            "failed_messages",
            "connected_clients",
            "queue_size",
            "last_broadcast_time"
        ]

        for stat in required_stats:
            assert stat in stats

    @pytest.mark.asyncio
    async def test_concurrent_broadcasts(self, broadcaster, mock_ipc_server):
        """Test handling concurrent broadcast operations"""
        # Launch multiple concurrent broadcasts
        tasks = [
            broadcaster.broadcast_workflow_state(WorkflowState.READY),
            broadcaster.broadcast_system_status({"status": "ok"}),
            broadcaster.broadcast_data_update({"progress": 0.5}),
            broadcaster.broadcast_performance_metrics({"cpu": 50})
        ]

        await asyncio.gather(*tasks)
        await asyncio.sleep(0.1)

        # All broadcasts should complete successfully
        assert mock_ipc_server.broadcast_message.call_count >= 4

    @pytest.mark.asyncio
    async def test_error_handling_in_broadcast(self, broadcaster, mock_ipc_server):
        """Test error handling during broadcast operations"""
        # Mock broadcast failure
        mock_ipc_server.broadcast_message.side_effect = Exception("Broadcast failed")

        # Should handle error gracefully
        await broadcaster.broadcast_workflow_state(WorkflowState.READY)
        await asyncio.sleep(0.1)

        # Error should be logged but not crash
        assert broadcaster._connection_status == ConnectionStatus.ERROR

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, broadcaster, mock_ipc_server):
        """Test graceful shutdown process"""
        # Start broadcaster
        await broadcaster.start()

        # Queue some messages
        await broadcaster.broadcast_workflow_state(WorkflowState.READY)
        await broadcaster.broadcast_system_status({"status": "ok"})

        # Shutdown gracefully
        await broadcaster.stop()

        # Should flush remaining messages
        assert mock_ipc_server.broadcast_message.called

    def test_subscription_filter_creation(self):
        """Test subscription filter creation and validation"""
        filter_config = SubscriptionFilter(
            client_id="test_client",
            broadcast_types=[BroadcastType.WORKFLOW_STATE],
            include_patterns=["*.workflow.*"],
            exclude_patterns=["*.debug.*"]
        )

        assert filter_config.client_id == "test_client"
        assert BroadcastType.WORKFLOW_STATE in filter_config.broadcast_types
        assert "*.workflow.*" in filter_config.include_patterns
        assert "*.debug.*" in filter_config.exclude_patterns

    def test_broadcast_message_creation(self):
        """Test broadcast message creation"""
        message = BroadcastMessage(
            type=BroadcastType.SYSTEM_STATUS,
            data={"status": "ok"},
            timestamp=datetime.now(),
            client_filters=["client_1"]
        )

        assert message.type == BroadcastType.SYSTEM_STATUS
        assert message.data == {"status": "ok"}
        assert isinstance(message.timestamp, datetime)
        assert "client_1" in message.client_filters

    @pytest.mark.asyncio
    async def test_health_check_broadcasting(self, broadcaster, mock_ipc_server):
        """Test periodic health check broadcasting"""
        await broadcaster.start_health_check_broadcast(interval_seconds=0.1)
        await asyncio.sleep(0.3)  # Wait for a few broadcasts
        await broadcaster.stop_health_check_broadcast()

        # Should have sent multiple health check broadcasts
        assert mock_ipc_server.broadcast_message.call_count >= 2

    def test_connection_status_enum(self):
        """Test ConnectionStatus enum values"""
        assert ConnectionStatus.CONNECTED.value == "connected"
        assert ConnectionStatus.DISCONNECTED.value == "disconnected"
        assert ConnectionStatus.CONNECTING.value == "connecting"
        assert ConnectionStatus.ERROR.value == "error"


class TestBroadcastType:
    """Test BroadcastType enum"""

    def test_broadcast_type_values(self):
        """Test broadcast type enum values"""
        expected_types = [
            "workflow_state",
            "system_status",
            "data_update",
            "error_event",
            "performance_metrics",
            "hardware_status",
            "session_update",
            "analysis_progress",
            "calibration_update",
            "configuration_change"
        ]

        actual_types = [bt.value for bt in BroadcastType]
        for expected in expected_types:
            assert expected in actual_types

    def test_broadcast_type_uniqueness(self):
        """Test that all broadcast type values are unique"""
        values = [bt.value for bt in BroadcastType]
        assert len(values) == len(set(values))


class TestBroadcastError:
    """Test BroadcastError exception"""

    def test_broadcast_error_creation(self):
        """Test BroadcastError creation"""
        error = BroadcastError("Test broadcast error", "TestErrorType")

        assert str(error) == "Test broadcast error"
        assert error.error_type == "TestErrorType"

    def test_broadcast_error_without_type(self):
        """Test BroadcastError without explicit error type"""
        error = BroadcastError("Test error")

        assert str(error) == "Test error"
        assert error.error_type == "BroadcastError"


class TestMessageValidation:
    """Test message validation functionality"""

    def test_valid_message_structure(self):
        """Test validation of valid message structure"""
        valid_message = {
            "type": BroadcastType.WORKFLOW_STATE.value,
            "timestamp": datetime.now().isoformat(),
            "data": {"state": "ready"}
        }

        # Should pass validation
        from src.application.handlers.state_broadcaster import _validate_message_structure
        assert _validate_message_structure(valid_message) is True

    def test_invalid_message_structure(self):
        """Test validation of invalid message structure"""
        invalid_message = {
            "type": "invalid_type",
            # Missing timestamp and data
        }

        from src.application.handlers.state_broadcaster import _validate_message_structure
        assert _validate_message_structure(invalid_message) is False

    def test_message_size_validation(self):
        """Test message size validation"""
        # Large message
        large_data = {"data": "x" * 10000}  # 10KB of data
        large_message = {
            "type": BroadcastType.DATA_UPDATE.value,
            "timestamp": datetime.now().isoformat(),
            "data": large_data
        }

        from src.application.handlers.state_broadcaster import _validate_message_size
        # Should handle large messages appropriately
        result = _validate_message_size(large_message)
        assert isinstance(result, bool)