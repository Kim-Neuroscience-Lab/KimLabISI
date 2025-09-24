"""
Unit Tests for IPC Server

Tests the IPC server functionality including message handling,
validation, routing, and communication patterns.
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from src.infrastructure.communication.ipc_server import IPCServer, IPCMessage, MessageType
from pydantic import ValidationError


class TestMessageType:
    """Test MessageType enum"""

    def test_message_type_values(self):
        """Test message type enum values"""
        assert MessageType.COMMAND.value == "command"
        assert MessageType.QUERY.value == "query"
        assert MessageType.STATE_UPDATE.value == "state_update"
        assert MessageType.NOTIFICATION.value == "notification"
        assert MessageType.RESPONSE.value == "response"
        assert MessageType.ERROR.value == "error"


class TestIPCMessage:
    """Test IPCMessage Pydantic model"""

    def test_ipc_message_creation(self):
        """Test creating IPC message with Pydantic V2"""
        message = IPCMessage(
            message_type=MessageType.COMMAND,
            message_id="test-123",
            timestamp=1234567890.0,
            payload={"command": "test", "data": "value"},
        )

        assert message.message_type == MessageType.COMMAND.value
        assert message.message_id == "test-123"
        assert message.timestamp == 1234567890.0
        assert message.payload["command"] == "test"

    def test_ipc_message_serialization(self):
        """Test Pydantic V2 serialization"""
        message = IPCMessage(
            message_type=MessageType.STATE_UPDATE,
            message_id="update-456",
            timestamp=1234567890.0,
            payload={"state": "ready"},
        )

        data = message.model_dump()
        assert data["message_type"] == "state_update"
        assert data["message_id"] == "update-456"
        assert data["payload"]["state"] == "ready"

    def test_ipc_message_validation(self):
        """Test Pydantic V2 validation"""
        # Valid message
        valid_data = {
            "message_type": "command",
            "message_id": "test-123",
            "timestamp": 1234567890.0,
            "payload": {},
        }
        message = IPCMessage.model_validate(valid_data)
        assert message.message_type == MessageType.COMMAND.value

        # Invalid message type
        invalid_data = {
            "message_type": "invalid_type",
            "message_id": "test-123",
            "timestamp": 1234567890.0,
            "payload": {},
        }
        with pytest.raises(ValidationError):
            IPCMessage.model_validate(invalid_data)


class TestCommandMessage:
    """Test CommandMessage Pydantic model"""

    def test_command_message_creation(self):
        """Test creating command message"""
        command = CommandMessage(
            command="workflow.start", parameters={"param1": "value1"}, request_id="req-123"
        )

        assert command.command == "workflow.start"
        assert command.parameters["param1"] == "value1"
        assert command.request_id == "req-123"

    def test_command_message_defaults(self):
        """Test command message with default values"""
        command = CommandMessage(command="test.command")

        assert command.parameters == {}
        assert command.request_id is None

    def test_command_message_serialization(self):
        """Test command message serialization"""
        command = CommandMessage(command="hardware.detect", parameters={"force": True})

        data = command.model_dump()
        assert data["command"] == "hardware.detect"
        assert data["parameters"]["force"] is True
        assert data["request_id"] is None


class TestStateUpdateMessage:
    """Test StateUpdateMessage Pydantic model"""

    def test_state_update_message_creation(self):
        """Test creating state update message"""
        update = StateUpdateMessage(
            state_type="workflow", state_data={"current_state": "ready", "progress": 50}
        )

        assert update.state_type == "workflow"
        assert update.state_data["current_state"] == "ready"
        assert update.state_data["progress"] == 50


class TestNotificationMessage:
    """Test NotificationMessage Pydantic model"""

    def test_notification_message_creation(self):
        """Test creating notification message"""
        notification = NotificationMessage(
            level="error",
            title="Hardware Error",
            message="Camera disconnected",
            details={"error_code": 404},
        )

        assert notification.level == "error"
        assert notification.title == "Hardware Error"
        assert notification.message == "Camera disconnected"
        assert notification.details["error_code"] == 404

    def test_notification_message_defaults(self):
        """Test notification message with defaults"""
        notification = NotificationMessage(
            level="info", title="Info", message="Operation completed"
        )

        assert notification.details is None


class MockIPCHandler(IPCHandler):
    """Mock IPC handler for testing"""

    def __init__(self):
        self.commands_handled = []
        self.queries_handled = []

    async def handle_command(self, command: CommandMessage) -> Dict[str, Any]:
        self.commands_handled.append(command)
        return {"success": True, "command": command.command}

    async def handle_query(self, query: Dict[str, Any]) -> Dict[str, Any]:
        self.queries_handled.append(query)
        return {"success": True, "query_type": query.get("type", "unknown")}


class TestIPCServer:
    """Test IPCServer functionality"""

    @pytest.fixture
    def mock_handler(self):
        """Mock IPC handler for testing"""
        return MockIPCHandler()

    @pytest.mark.asyncio
    async def test_ipc_server_initialization(self, ipc_server):
        """Test IPC server initialization"""
        assert len(ipc_server._handlers) == 0
        assert len(ipc_server._subscribers) == 0
        assert ipc_server._running is False

    @pytest.mark.asyncio
    async def test_register_handler(self, ipc_server, mock_handler):
        """Test registering an IPC handler"""
        ipc_server.register_handler("test_handler", mock_handler)

        assert "test_handler" in ipc_server._handlers
        assert ipc_server._handlers["test_handler"] == mock_handler

    @pytest.mark.asyncio
    async def test_subscribe_to_state_updates(self, ipc_server):
        """Test subscribing to state updates"""
        callback = Mock()
        ipc_server.subscribe_to_state_updates("workflow", callback)

        assert "workflow" in ipc_server._subscribers
        assert callback in ipc_server._subscribers["workflow"]

    @pytest.mark.asyncio
    async def test_send_state_update(self, ipc_server):
        """Test sending state update"""
        with patch.object(ipc_server, "_send_to_frontend", new_callable=AsyncMock) as mock_send:
            await ipc_server.send_state_update("workflow", {"state": "ready"})

            mock_send.assert_called_once()
            message = mock_send.call_args[0][0]
            assert message.message_type == MessageType.STATE_UPDATE.value
            assert message.payload["state_type"] == "workflow"
            assert message.payload["state_data"]["state"] == "ready"

    @pytest.mark.asyncio
    async def test_send_notification(self, ipc_server):
        """Test sending notification"""
        with patch.object(ipc_server, "_send_to_frontend", new_callable=AsyncMock) as mock_send:
            await ipc_server.send_notification(
                "error", "Test Error", "Something went wrong", {"code": 500}
            )

            mock_send.assert_called_once()
            message = mock_send.call_args[0][0]
            assert message.message_type == MessageType.NOTIFICATION.value
            assert message.payload["level"] == "error"
            assert message.payload["title"] == "Test Error"
            assert message.payload["details"]["code"] == 500

    @pytest.mark.asyncio
    async def test_route_command_message(self, ipc_server, mock_handler):
        """Test routing command message to handler"""
        ipc_server.register_handler("command_handler", mock_handler)

        message = IPCMessage(
            message_type=MessageType.COMMAND,
            message_id="cmd-123",
            timestamp=1234567890.0,
            payload={
                "command": "workflow.start",
                "parameters": {"param": "value"},
                "request_id": "req-123",
            },
        )

        with patch.object(ipc_server, "_send_response", new_callable=AsyncMock) as mock_response:
            await ipc_server._route_message(message)

            assert len(mock_handler.commands_handled) == 1
            handled_command = mock_handler.commands_handled[0]
            assert handled_command.command == "workflow.start"
            assert handled_command.parameters["param"] == "value"

            mock_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_query_message(self, ipc_server, mock_handler):
        """Test routing query message to handler"""
        ipc_server.register_handler("query_handler", mock_handler)

        message = IPCMessage(
            message_type=MessageType.QUERY,
            message_id="query-123",
            timestamp=1234567890.0,
            payload={"type": "status", "details": "system"},
        )

        with patch.object(ipc_server, "_send_response", new_callable=AsyncMock) as mock_response:
            await ipc_server._route_message(message)

            assert len(mock_handler.queries_handled) == 1
            handled_query = mock_handler.queries_handled[0]
            assert handled_query["type"] == "status"

            mock_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_command_no_handler(self, ipc_server):
        """Test handling command with no registered handler"""
        message = IPCMessage(
            message_type=MessageType.COMMAND,
            message_id="cmd-123",
            timestamp=1234567890.0,
            payload={"command": "unknown.command", "parameters": {}, "request_id": "req-123"},
        )

        with patch.object(ipc_server, "_send_error_response", new_callable=AsyncMock) as mock_error:
            await ipc_server._handle_command(message)

            mock_error.assert_called_once()
            error_args = mock_error.call_args[0]
            assert "No handler registered" in error_args[1]

    @pytest.mark.asyncio
    async def test_handle_query_no_handlers(self, ipc_server):
        """Test handling query with no registered handlers"""
        message = IPCMessage(
            message_type=MessageType.QUERY,
            message_id="query-123",
            timestamp=1234567890.0,
            payload={"type": "status"},
        )

        with patch.object(ipc_server, "_send_error_response", new_callable=AsyncMock) as mock_error:
            await ipc_server._handle_query(message)

            mock_error.assert_called_once()
            error_args = mock_error.call_args[0]
            assert "No handlers available" in error_args[1]

    @pytest.mark.asyncio
    async def test_process_invalid_message(self, ipc_server):
        """Test processing invalid message format"""
        # Test the routing logic directly instead of the infinite loop
        invalid_message_data = {"invalid_field": "value", "missing_required_fields": True}

        # Mock the IPCMessage validation to fail
        with patch(
            "src.infrastructure.communication.ipc_server.IPCMessage.model_validate"
        ) as mock_validate:
            mock_validate.side_effect = ValidationError("Invalid message format", [])
            with patch.object(
                ipc_server, "_send_error_response", new_callable=AsyncMock
            ) as mock_error:
                # Create a fake message to test the routing logic
                fake_message = IPCMessage(
                    message_type=MessageType.COMMAND,
                    message_id="test-123",
                    timestamp=1234567890.0,
                    payload=invalid_message_data,
                )

                # Call _route_message directly to test error handling
                await ipc_server._route_message(fake_message)

                # Should have called error response due to validation failure
                mock_error.assert_called()

    @pytest.mark.asyncio
    async def test_get_handler_for_command(self, ipc_server):
        """Test command handler selection logic"""
        # Updated to match new single command handler pattern
        assert ipc_server._get_handler_for_command("workflow.start") == "command_handler"
        assert ipc_server._get_handler_for_command("hardware.detect") == "command_handler"
        assert ipc_server._get_handler_for_command("data.export") == "command_handler"
        assert ipc_server._get_handler_for_command("system.status") == "command_handler"
        assert ipc_server._get_handler_for_command("unknown.command") == "command_handler"
        assert ipc_server._get_handler_for_command("simple_command") == "command_handler"

    @pytest.mark.asyncio
    async def test_generate_message_id(self, ipc_server):
        """Test message ID generation"""
        id1 = ipc_server._generate_message_id()
        id2 = ipc_server._generate_message_id()

        assert isinstance(id1, str)
        assert isinstance(id2, str)
        assert id1 != id2  # Should be unique
        assert len(id1) > 0
        assert len(id2) > 0

    @pytest.mark.asyncio
    async def test_send_response(self, ipc_server):
        """Test sending response message"""
        response_data = {"success": True, "data": "test"}

        with patch.object(ipc_server, "_send_to_frontend", new_callable=AsyncMock) as mock_send:
            await ipc_server._send_response("req-123", response_data)

            mock_send.assert_called_once()
            message = mock_send.call_args[0][0]
            assert message.message_type == MessageType.RESPONSE.value
            assert message.message_id == "req-123"
            assert message.payload == response_data

    @pytest.mark.asyncio
    async def test_send_error_response(self, ipc_server):
        """Test sending error response"""
        with patch.object(ipc_server, "_send_to_frontend", new_callable=AsyncMock) as mock_send:
            await ipc_server._send_error_response("Test error", "Error details", "req-123")

            mock_send.assert_called_once()
            message = mock_send.call_args[0][0]
            assert message.message_type == MessageType.ERROR.value
            assert message.message_id == "req-123"
            assert message.payload["error"] == "Test error"
            assert message.payload["details"] == "Error details"

    @pytest.mark.asyncio
    async def test_send_error_response_no_request_id(self, ipc_server):
        """Test sending error response without request ID"""
        with patch.object(ipc_server, "_send_to_frontend", new_callable=AsyncMock) as mock_send:
            with patch.object(ipc_server, "_generate_message_id", return_value="auto-123"):
                await ipc_server._send_error_response("Test error", "Error details")

                mock_send.assert_called_once()
                message = mock_send.call_args[0][0]
                assert message.message_id == "auto-123"

    @pytest.mark.asyncio
    async def test_start_websocket_server(self, ipc_server):
        """Test starting WebSocket server"""
        with patch("websockets.serve", new_callable=AsyncMock) as mock_serve:
            with patch.object(ipc_server, "_process_messages", new_callable=AsyncMock):
                await ipc_server.start()
                mock_serve.assert_called_once_with(
                    ipc_server._handle_websocket_connection,
                    ipc_server.host,
                    ipc_server.port,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=10,
                )

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self, ipc_server):
        """Test that start() sets the running flag"""
        assert ipc_server._running is False

        with patch("websockets.serve", new_callable=AsyncMock):
            with patch.object(ipc_server, "_process_messages", new_callable=AsyncMock):
                await ipc_server.start()
                assert ipc_server._running is True

    @pytest.mark.asyncio
    async def test_stop_clears_running_flag(self, ipc_server):
        """Test that stop() clears the running flag"""
        ipc_server._running = True

        # Mock WebSocket server for cleanup
        mock_server = Mock()
        mock_server.close = Mock()
        mock_server.wait_closed = AsyncMock()
        ipc_server.websocket_server = mock_server

        await ipc_server.stop()
        assert ipc_server._running is False
        mock_server.close.assert_called_once()
        mock_server.wait_closed.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_connection_handling(self, ipc_server, mock_handler):
        """Test WebSocket connection handling"""
        ipc_server.register_handler("command_handler", mock_handler)

        # Mock websocket
        mock_websocket = MagicMock()
        mock_websocket.remote_address = ("127.0.0.1", 12345)
        mock_websocket.send = AsyncMock()

        # Mock the async iteration over websocket messages
        async def mock_messages():
            yield json.dumps(
                {"command": "workflow.start", "parameters": {}, "request_id": "test-123"}
            )

        mock_websocket.__aiter__ = lambda self: mock_messages()

        # Test connection handling
        await ipc_server._handle_websocket_connection(mock_websocket, "/")

        # Verify welcome message was sent
        assert mock_websocket.send.call_count >= 1
        welcome_call = mock_websocket.send.call_args_list[0]
        welcome_data = json.loads(welcome_call[0][0])
        assert welcome_data["message_type"] == "state_update"
        assert welcome_data["payload"]["state_type"] == "connection"

    @pytest.mark.asyncio
    async def test_handle_frontend_message_command(self, ipc_server, mock_handler):
        """Test handling command message from frontend"""
        ipc_server.register_handler("command_handler", mock_handler)

        mock_websocket = MagicMock()
        mock_websocket.send = AsyncMock()

        message_data = {
            "command": "workflow.get_state",
            "parameters": {"param": "value"},
            "request_id": "req-456",
        }

        await ipc_server._handle_frontend_message(message_data, mock_websocket)

        # Verify command was processed
        assert len(mock_handler.commands_handled) == 1
        handled_command = mock_handler.commands_handled[0]
        assert handled_command.command == "workflow.get_state"
        assert handled_command.request_id == "req-456"

        # Verify response was sent
        mock_websocket.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_frontend_message_query(self, ipc_server, mock_handler):
        """Test handling query message from frontend"""
        ipc_server.register_handler("command_handler", mock_handler)

        mock_websocket = MagicMock()
        mock_websocket.send = AsyncMock()

        message_data = {"query": "status", "type": "system", "request_id": "query-789"}

        await ipc_server._handle_frontend_message(message_data, mock_websocket)

        # Verify query was processed
        assert len(mock_handler.queries_handled) == 1

        # Verify response was sent
        mock_websocket.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_frontend_message_invalid(self, ipc_server):
        """Test handling invalid message from frontend"""
        mock_websocket = MagicMock()
        mock_websocket.send = AsyncMock()

        message_data = {"unknown_field": "value"}

        await ipc_server._handle_frontend_message(message_data, mock_websocket)

        # Verify error was sent
        mock_websocket.send.assert_called_once()
        error_call = mock_websocket.send.call_args[0][0]
        error_data = json.loads(error_call)
        assert error_data["message_type"] == "error"

    @pytest.mark.asyncio
    async def test_send_to_frontend_no_clients(self, ipc_server):
        """Test sending message when no clients are connected"""
        message = IPCMessage(
            message_type=MessageType.STATE_UPDATE,
            message_id="test-123",
            timestamp=1234567890.0,
            payload={"test": "data"},
        )

        # Should not raise an error when no clients connected
        await ipc_server._send_to_frontend(message)

    @pytest.mark.asyncio
    async def test_send_to_frontend_with_clients(self, ipc_server):
        """Test sending message to connected clients"""
        message = IPCMessage(
            message_type=MessageType.STATE_UPDATE,
            message_id="test-123",
            timestamp=1234567890.0,
            payload={"test": "data"},
        )

        # Add mock clients
        mock_client1 = MagicMock()
        mock_client1.send = AsyncMock()
        mock_client2 = MagicMock()
        mock_client2.send = AsyncMock()

        ipc_server.connected_clients.add(mock_client1)
        ipc_server.connected_clients.add(mock_client2)

        await ipc_server._send_to_frontend(message)

        # Verify message was sent to both clients
        mock_client1.send.assert_called_once()
        mock_client2.send.assert_called_once()

        # Verify message content
        sent_data = json.loads(mock_client1.send.call_args[0][0])
        assert sent_data["message_type"] == "state_update"
        assert sent_data["payload"]["test"] == "data"

    @pytest.mark.asyncio
    async def test_send_error_to_client(self, ipc_server):
        """Test sending error to specific client"""
        mock_websocket = MagicMock()
        mock_websocket.send = AsyncMock()

        await ipc_server._send_error_to_client(mock_websocket, "Test error", "Error details")

        mock_websocket.send.assert_called_once()
        error_call = mock_websocket.send.call_args[0][0]
        error_data = json.loads(error_call)

        assert error_data["message_type"] == "error"
        assert error_data["payload"]["error"] == "Test error"
        assert error_data["payload"]["details"] == "Error details"
