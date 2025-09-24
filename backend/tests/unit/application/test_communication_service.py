"""
Tests for CommunicationService application service

Comprehensive test suite for central IPC communication coordination,
connection management, and message routing between frontend and backend.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime, timedelta
import json
import asyncio

from src.application.services.communication_service import (
    CommunicationService,
    ConnectionState,
    MessageType,
    CommunicationError,
    MessageHandler,
    ConnectionMetrics
)
from src.domain.value_objects.workflow_state import WorkflowState


class TestCommunicationService:
    """Test CommunicationService functionality"""

    @pytest.fixture
    def mock_ipc_server(self):
        """Mock IPC server"""
        mock = AsyncMock()
        mock.start = AsyncMock()
        mock.stop = AsyncMock()
        mock.restart = AsyncMock()
        mock.send_message = AsyncMock()
        mock.broadcast_message = AsyncMock()
        mock.is_running = Mock(return_value=True)
        mock.get_connected_clients = Mock(return_value=["client_1", "client_2"])
        return mock

    @pytest.fixture
    def mock_state_broadcaster(self):
        """Mock state broadcaster"""
        mock = AsyncMock()
        mock.broadcast_workflow_state = AsyncMock()
        mock.broadcast_system_status = AsyncMock()
        mock.get_connection_status = Mock(return_value="connected")
        return mock

    @pytest.fixture
    def mock_query_handler(self):
        """Mock query handler"""
        mock = AsyncMock()
        mock.handle_query = AsyncMock(return_value={
            "success": True,
            "data": {"test": "response"}
        })
        return mock

    @pytest.fixture
    def communication_service(self, mock_ipc_server, mock_state_broadcaster, mock_query_handler):
        """Create CommunicationService with mocked dependencies"""
        service = CommunicationService(
            ipc_server=mock_ipc_server,
            state_broadcaster=mock_state_broadcaster,
            query_handler=mock_query_handler
        )
        return service

    @pytest.mark.asyncio
    async def test_service_startup(self, communication_service, mock_ipc_server):
        """Test communication service startup"""
        await communication_service.start()

        assert communication_service._connection_state == ConnectionState.CONNECTED
        mock_ipc_server.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_service_shutdown(self, communication_service, mock_ipc_server):
        """Test communication service shutdown"""
        await communication_service.start()
        await communication_service.stop()

        assert communication_service._connection_state == ConnectionState.DISCONNECTED
        mock_ipc_server.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_frontend_message(self, communication_service, mock_query_handler):
        """Test handling messages from frontend"""
        message = {
            "type": MessageType.QUERY.value,
            "id": "msg_001",
            "data": {
                "query_type": "system_status",
                "parameters": {}
            }
        }

        response = await communication_service.handle_frontend_message("client_1", message)

        assert response["success"] is True
        assert response["message_id"] == "msg_001"
        mock_query_handler.handle_query.assert_called_once_with("system_status", {})

    @pytest.mark.asyncio
    async def test_handle_command_message(self, communication_service):
        """Test handling command messages"""
        message = {
            "type": MessageType.COMMAND.value,
            "id": "cmd_001",
            "data": {
                "command": "start_acquisition",
                "parameters": {"duration": 60}
            }
        }

        with patch.object(communication_service, '_execute_command', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"success": True, "result": "started"}

            response = await communication_service.handle_frontend_message("client_1", message)

            assert response["success"] is True
            mock_execute.assert_called_once_with("start_acquisition", {"duration": 60})

    @pytest.mark.asyncio
    async def test_handle_subscription_message(self, communication_service):
        """Test handling subscription messages"""
        message = {
            "type": MessageType.SUBSCRIPTION.value,
            "id": "sub_001",
            "data": {
                "action": "subscribe",
                "topics": ["workflow_state", "system_status"]
            }
        }

        response = await communication_service.handle_frontend_message("client_1", message)

        assert response["success"] is True
        assert "client_1" in communication_service._client_subscriptions
        assert "workflow_state" in communication_service._client_subscriptions["client_1"]

    @pytest.mark.asyncio
    async def test_handle_unsubscription(self, communication_service):
        """Test handling unsubscription messages"""
        # First subscribe
        subscribe_message = {
            "type": MessageType.SUBSCRIPTION.value,
            "id": "sub_001",
            "data": {
                "action": "subscribe",
                "topics": ["workflow_state"]
            }
        }
        await communication_service.handle_frontend_message("client_1", subscribe_message)

        # Then unsubscribe
        unsubscribe_message = {
            "type": MessageType.SUBSCRIPTION.value,
            "id": "unsub_001",
            "data": {
                "action": "unsubscribe",
                "topics": ["workflow_state"]
            }
        }
        response = await communication_service.handle_frontend_message("client_1", unsubscribe_message)

        assert response["success"] is True
        assert "workflow_state" not in communication_service._client_subscriptions.get("client_1", [])

    @pytest.mark.asyncio
    async def test_connection_monitoring(self, communication_service, mock_ipc_server):
        """Test connection health monitoring"""
        await communication_service.start()
        await communication_service.start_connection_monitoring()

        # Wait for monitoring cycle
        await asyncio.sleep(0.1)

        # Connection should be monitored
        mock_ipc_server.is_running.assert_called()

    @pytest.mark.asyncio
    async def test_connection_recovery(self, communication_service, mock_ipc_server):
        """Test automatic connection recovery"""
        await communication_service.start()

        # Simulate connection loss
        mock_ipc_server.is_running.return_value = False
        communication_service._connection_state = ConnectionState.DISCONNECTED

        # Trigger recovery
        await communication_service.handle_connection_lost()

        # Should attempt reconnection
        mock_ipc_server.restart.assert_called()

    @pytest.mark.asyncio
    async def test_message_validation(self, communication_service):
        """Test message validation"""
        # Valid message
        valid_message = {
            "type": MessageType.QUERY.value,
            "id": "msg_001",
            "data": {"query_type": "system_status"}
        }

        is_valid = communication_service._validate_message(valid_message)
        assert is_valid is True

        # Invalid message (missing required fields)
        invalid_message = {
            "type": MessageType.QUERY.value,
            # Missing id and data
        }

        is_valid = communication_service._validate_message(invalid_message)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_message_routing(self, communication_service, mock_ipc_server):
        """Test message routing to appropriate handlers"""
        # Query message should go to query handler
        query_message = {
            "type": MessageType.QUERY.value,
            "id": "query_001",
            "data": {"query_type": "system_status"}
        }

        await communication_service.handle_frontend_message("client_1", query_message)

        # Command message should go to command handler
        command_message = {
            "type": MessageType.COMMAND.value,
            "id": "cmd_001",
            "data": {"command": "initialize_system"}
        }

        with patch.object(communication_service, '_execute_command', new_callable=AsyncMock):
            await communication_service.handle_frontend_message("client_1", command_message)

    @pytest.mark.asyncio
    async def test_broadcast_to_subscribers(self, communication_service, mock_ipc_server):
        """Test broadcasting messages to subscribed clients"""
        # Subscribe client to workflow_state
        communication_service._client_subscriptions["client_1"] = ["workflow_state"]
        communication_service._client_subscriptions["client_2"] = ["system_status"]

        # Broadcast workflow state update
        message = {
            "type": "workflow_state",
            "data": {"state": "ready"},
            "timestamp": datetime.now().isoformat()
        }

        await communication_service.broadcast_to_subscribers("workflow_state", message)

        # Should send to client_1 only
        mock_ipc_server.send_message.assert_called_with("client_1", message)

    @pytest.mark.asyncio
    async def test_client_disconnection_handling(self, communication_service):
        """Test handling client disconnections"""
        # Add client subscription
        communication_service._client_subscriptions["client_1"] = ["workflow_state"]

        # Handle client disconnection
        await communication_service.handle_client_disconnected("client_1")

        # Client should be removed from subscriptions
        assert "client_1" not in communication_service._client_subscriptions

    @pytest.mark.asyncio
    async def test_concurrent_message_handling(self, communication_service):
        """Test handling concurrent messages"""
        messages = []
        for i in range(5):
            message = {
                "type": MessageType.QUERY.value,
                "id": f"msg_{i}",
                "data": {"query_type": "system_status"}
            }
            messages.append(
                communication_service.handle_frontend_message(f"client_{i}", message)
            )

        responses = await asyncio.gather(*messages)

        # All messages should be processed successfully
        for response in responses:
            assert response["success"] is True

    @pytest.mark.asyncio
    async def test_message_queuing_when_disconnected(self, communication_service, mock_ipc_server):
        """Test message queuing when connection is lost"""
        # Start with connected state
        await communication_service.start()

        # Simulate disconnection
        communication_service._connection_state = ConnectionState.DISCONNECTED
        mock_ipc_server.is_running.return_value = False

        # Try to send message
        message = {"type": "test", "data": {"test": "value"}}
        await communication_service.broadcast_to_subscribers("test_topic", message)

        # Message should be queued
        assert len(communication_service._message_queue) > 0

    @pytest.mark.asyncio
    async def test_message_queue_flushing(self, communication_service, mock_ipc_server):
        """Test message queue flushing on reconnection"""
        # Queue some messages while disconnected
        communication_service._connection_state = ConnectionState.DISCONNECTED
        messages = [
            {"type": "test1", "data": {"value": 1}},
            {"type": "test2", "data": {"value": 2}}
        ]

        for msg in messages:
            communication_service._message_queue.append(msg)

        # Reconnect and flush
        communication_service._connection_state = ConnectionState.CONNECTED
        await communication_service._flush_message_queue()

        # Queue should be empty
        assert len(communication_service._message_queue) == 0

    @pytest.mark.asyncio
    async def test_error_handling_in_message_processing(self, communication_service, mock_query_handler):
        """Test error handling during message processing"""
        # Mock query handler to raise exception
        mock_query_handler.handle_query.side_effect = Exception("Query failed")

        message = {
            "type": MessageType.QUERY.value,
            "id": "error_msg",
            "data": {"query_type": "system_status"}
        }

        response = await communication_service.handle_frontend_message("client_1", message)

        # Should return error response
        assert response["success"] is False
        assert "error" in response
        assert response["message_id"] == "error_msg"

    @pytest.mark.asyncio
    async def test_heartbeat_mechanism(self, communication_service, mock_ipc_server):
        """Test heartbeat mechanism for connection health"""
        await communication_service.start()
        await communication_service.start_heartbeat(interval_seconds=0.1)

        # Wait for heartbeat cycles
        await asyncio.sleep(0.3)
        await communication_service.stop_heartbeat()

        # Should have sent heartbeat messages
        assert mock_ipc_server.broadcast_message.call_count >= 2

    def test_connection_metrics_tracking(self, communication_service):
        """Test connection metrics collection"""
        metrics = communication_service.get_connection_metrics()

        required_fields = [
            "connected_clients_count",
            "total_messages_processed",
            "failed_messages_count",
            "uptime_seconds",
            "connection_state",
            "reconnection_attempts"
        ]

        for field in required_fields:
            assert field in metrics

    def test_message_handler_registration(self, communication_service):
        """Test custom message handler registration"""
        def custom_handler(client_id: str, message: dict) -> dict:
            return {"success": True, "custom": True}

        communication_service.register_message_handler("custom_type", custom_handler)

        # Handler should be registered
        assert "custom_type" in communication_service._message_handlers
        assert communication_service._message_handlers["custom_type"] == custom_handler

    @pytest.mark.asyncio
    async def test_batch_message_processing(self, communication_service):
        """Test batch message processing"""
        messages = []
        for i in range(3):
            messages.append({
                "type": MessageType.QUERY.value,
                "id": f"batch_msg_{i}",
                "data": {"query_type": "system_status"}
            })

        responses = await communication_service.process_message_batch("client_1", messages)

        assert len(responses) == 3
        for response in responses:
            assert response["success"] is True

    @pytest.mark.asyncio
    async def test_connection_rate_limiting(self, communication_service):
        """Test connection rate limiting"""
        communication_service._enable_rate_limiting = True
        communication_service._max_messages_per_client_per_second = 2

        # Send messages rapidly
        messages = []
        for i in range(5):
            message = {
                "type": MessageType.QUERY.value,
                "id": f"rate_msg_{i}",
                "data": {"query_type": "system_status"}
            }
            messages.append(
                communication_service.handle_frontend_message("client_1", message)
            )

        start_time = asyncio.get_event_loop().time()
        responses = await asyncio.gather(*messages)
        end_time = asyncio.get_event_loop().time()

        # Should have been rate limited
        duration = end_time - start_time
        assert duration >= 1.0  # Should take time due to rate limiting

    def test_subscription_topic_validation(self, communication_service):
        """Test subscription topic validation"""
        valid_topics = ["workflow_state", "system_status", "data_update"]
        invalid_topics = ["invalid_topic", "", None]

        for topic in valid_topics:
            assert communication_service._is_valid_subscription_topic(topic) is True

        for topic in invalid_topics:
            assert communication_service._is_valid_subscription_topic(topic) is False

    @pytest.mark.asyncio
    async def test_graceful_shutdown_with_pending_messages(self, communication_service, mock_ipc_server):
        """Test graceful shutdown with pending messages"""
        # Start service and queue messages
        await communication_service.start()

        # Queue messages
        for i in range(3):
            message = {"type": "test", "data": {"id": i}}
            communication_service._message_queue.append(message)

        # Shutdown gracefully
        await communication_service.stop()

        # Should process remaining messages before shutdown
        assert len(communication_service._message_queue) == 0

    def test_connection_state_transitions(self, communication_service):
        """Test connection state transitions"""
        # Initial state
        assert communication_service._connection_state == ConnectionState.DISCONNECTED

        # Valid transitions
        communication_service._set_connection_state(ConnectionState.CONNECTING)
        assert communication_service._connection_state == ConnectionState.CONNECTING

        communication_service._set_connection_state(ConnectionState.CONNECTED)
        assert communication_service._connection_state == ConnectionState.CONNECTED

        communication_service._set_connection_state(ConnectionState.DISCONNECTED)
        assert communication_service._connection_state == ConnectionState.DISCONNECTED


class TestMessageType:
    """Test MessageType enum"""

    def test_message_type_values(self):
        """Test message type enum values"""
        expected_types = [
            "query",
            "command",
            "subscription",
            "response",
            "broadcast",
            "heartbeat",
            "error",
            "status"
        ]

        actual_types = [mt.value for mt in MessageType]
        for expected in expected_types:
            assert expected in actual_types

    def test_message_type_uniqueness(self):
        """Test that all message type values are unique"""
        values = [mt.value for mt in MessageType]
        assert len(values) == len(set(values))


class TestConnectionState:
    """Test ConnectionState enum"""

    def test_connection_state_values(self):
        """Test connection state enum values"""
        expected_states = [
            "disconnected",
            "connecting",
            "connected",
            "reconnecting",
            "error"
        ]

        actual_states = [cs.value for cs in ConnectionState]
        for expected in expected_states:
            assert expected in actual_states


class TestCommunicationError:
    """Test CommunicationError exception"""

    def test_communication_error_creation(self):
        """Test CommunicationError creation"""
        error = CommunicationError("Test communication error", "TestErrorType")

        assert str(error) == "Test communication error"
        assert error.error_type == "TestErrorType"

    def test_communication_error_without_type(self):
        """Test CommunicationError without explicit error type"""
        error = CommunicationError("Test error")

        assert str(error) == "Test error"
        assert error.error_type == "CommunicationError"


class TestConnectionMetrics:
    """Test ConnectionMetrics functionality"""

    def test_connection_metrics_creation(self):
        """Test connection metrics creation"""
        metrics = ConnectionMetrics(
            connected_clients_count=5,
            total_messages_processed=100,
            failed_messages_count=2,
            uptime_seconds=3600.0,
            connection_state="connected",
            reconnection_attempts=0
        )

        assert metrics.connected_clients_count == 5
        assert metrics.total_messages_processed == 100
        assert metrics.failed_messages_count == 2
        assert metrics.uptime_seconds == 3600.0
        assert metrics.connection_state == "connected"
        assert metrics.reconnection_attempts == 0

    def test_connection_metrics_serialization(self):
        """Test connection metrics serialization"""
        metrics = ConnectionMetrics(
            connected_clients_count=3,
            total_messages_processed=50,
            failed_messages_count=1,
            uptime_seconds=1800.0,
            connection_state="connected",
            reconnection_attempts=0
        )

        serialized = metrics.to_dict()

        assert serialized["connected_clients_count"] == 3
        assert serialized["total_messages_processed"] == 50
        assert serialized["failed_messages_count"] == 1
        assert serialized["uptime_seconds"] == 1800.0
        assert serialized["connection_state"] == "connected"
        assert serialized["reconnection_attempts"] == 0


class TestMessageHandler:
    """Test MessageHandler functionality"""

    def test_message_handler_interface(self):
        """Test MessageHandler interface"""
        def test_handler(client_id: str, message: dict) -> dict:
            return {
                "success": True,
                "client_id": client_id,
                "message_type": message.get("type")
            }

        handler = MessageHandler(
            name="test_handler",
            handler_func=test_handler,
            message_types=[MessageType.QUERY]
        )

        assert handler.name == "test_handler"
        assert handler.handler_func == test_handler
        assert MessageType.QUERY in handler.message_types

    def test_message_handler_execution(self):
        """Test message handler execution"""
        def echo_handler(client_id: str, message: dict) -> dict:
            return {
                "success": True,
                "echo": message.get("data"),
                "client": client_id
            }

        handler = MessageHandler(
            name="echo_handler",
            handler_func=echo_handler,
            message_types=[MessageType.QUERY]
        )

        result = handler.handler_func("client_1", {
            "type": MessageType.QUERY.value,
            "data": {"test": "value"}
        })

        assert result["success"] is True
        assert result["echo"] == {"test": "value"}
        assert result["client"] == "client_1"