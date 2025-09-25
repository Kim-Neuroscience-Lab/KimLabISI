"""
Communication Service

Manages IPC communication between backend and frontend, coordinating
message handlers and state broadcasting.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Awaitable
import logging
import asyncio
import json

from infrastructure.communication.ipc_server import IPCServer
from infrastructure.communication.message_dispatcher import MessageDispatcher
from application.handlers.command_handler import CommandHandler
from application.handlers.query_handler import QueryHandler
from application.handlers.state_broadcaster import StateBroadcaster


logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """IPC connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class CommunicationError(Exception):
    """Raised when communication encounters errors"""
    pass


class CommunicationService:
    """
    Application service for managing IPC communication

    Coordinates all communication between backend and frontend,
    managing connection state, message routing, and error handling.
    """

    def __init__(
        self,
        ipc_server: IPCServer,
        message_dispatcher: MessageDispatcher,
        command_handler: CommandHandler,
        query_handler: QueryHandler,
        state_broadcaster: StateBroadcaster
    ):
        self.ipc_server = ipc_server
        self.message_dispatcher = message_dispatcher
        self.command_handler = command_handler
        self.query_handler = query_handler
        self.state_broadcaster = state_broadcaster

        # Connection management
        self._connection_state = ConnectionState.DISCONNECTED
        self._connection_attempts = 0
        self._max_connection_attempts = 5
        self._reconnect_delay_seconds = 2.0
        self._last_connection_time: Optional[datetime] = None
        self._connection_error: Optional[str] = None

        # Message statistics
        self._messages_sent = 0
        self._messages_received = 0
        self._commands_processed = 0
        self._queries_processed = 0
        self._connection_drops = 0

        # Connection event handlers
        self._connection_handlers: List[Callable[[ConnectionState], Awaitable[None]]] = []

        logger.info("Communication service initialized")

    async def start(self, port: int = 8765):
        """Start the communication service"""

        try:
            self._connection_state = ConnectionState.CONNECTING
            await self._notify_connection_handlers()

            # Setup message handlers
            await self._setup_message_handlers()

            # Start IPC server
            await self.ipc_server.start()

            # Start state broadcaster
            await self.state_broadcaster.start()

            self._connection_state = ConnectionState.CONNECTED
            self._last_connection_time = datetime.now()
            self._connection_error = None
            await self._notify_connection_handlers()

            logger.info(f"Communication service started on port {port}")

        except Exception as e:
            self._connection_state = ConnectionState.ERROR
            self._connection_error = str(e)
            await self._notify_connection_handlers()

            logger.exception("Failed to start communication service")
            raise CommunicationError(f"Failed to start communication service: {str(e)}")

    async def stop(self):
        """Stop the communication service"""

        try:
            # Stop state broadcaster
            await self.state_broadcaster.stop()

            # Stop IPC server
            await self.ipc_server.stop()

            self._connection_state = ConnectionState.DISCONNECTED
            await self._notify_connection_handlers()

            logger.info("Communication service stopped")

        except Exception as e:
            logger.exception("Error stopping communication service")
            raise CommunicationError(f"Failed to stop communication service: {str(e)}")

    async def send_command_response(
        self,
        command_id: str,
        success: bool,
        result: Optional[Any] = None,
        error: Optional[str] = None
    ):
        """Send command response to frontend"""

        response = {
            "type": "command_response",
            "command_id": command_id,
            "timestamp": datetime.now().isoformat(),
            "success": success,
            "result": result,
            "error": error
        }

        await self._send_message(response)
        logger.debug(f"Sent command response: {command_id} success={success}")

    async def send_query_response(
        self,
        query_id: str,
        result: Dict[str, Any]
    ):
        """Send query response to frontend"""

        response = {
            "type": "query_response",
            "query_id": query_id,
            "timestamp": datetime.now().isoformat(),
            **result
        }

        await self._send_message(response)
        self._queries_processed += 1
        logger.debug(f"Sent query response: {query_id}")

    async def send_notification(
        self,
        notification_type: str,
        title: str,
        message: str,
        severity: str = "info",
        data: Optional[Dict[str, Any]] = None
    ):
        """Send notification to frontend"""

        notification = {
            "type": "notification",
            "notification_type": notification_type,
            "title": title,
            "message": message,
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
            "data": data or {}
        }

        await self._send_message(notification)
        logger.debug(f"Sent notification: {notification_type} - {title}")

    async def broadcast_state_change(
        self,
        state_type: str,
        state_data: Dict[str, Any]
    ):
        """Broadcast state change via state broadcaster"""

        # Delegate to state broadcaster
        if state_type == "workflow_state":
            await self.state_broadcaster.broadcast_workflow_state(**state_data)
        elif state_type == "hardware_status":
            await self.state_broadcaster.broadcast_hardware_status(**state_data)
        elif state_type == "progress_update":
            await self.state_broadcaster.broadcast_progress_update(**state_data)
        elif state_type == "error_notification":
            await self.state_broadcaster.broadcast_error_notification(**state_data)
        else:
            logger.warning(f"Unknown state broadcast type: {state_type}")

    def add_connection_handler(
        self,
        handler: Callable[[ConnectionState], Awaitable[None]]
    ):
        """Add connection state change handler"""
        self._connection_handlers.append(handler)
        logger.debug("Added connection state handler")

    def remove_connection_handler(
        self,
        handler: Callable[[ConnectionState], Awaitable[None]]
    ):
        """Remove connection state change handler"""
        if handler in self._connection_handlers:
            self._connection_handlers.remove(handler)
            logger.debug("Removed connection state handler")

    async def handle_connection_lost(self):
        """Handle lost connection and attempt reconnection"""

        self._connection_drops += 1
        self._connection_state = ConnectionState.RECONNECTING
        await self._notify_connection_handlers()

        logger.warning("Connection lost, attempting reconnection")

        while (self._connection_attempts < self._max_connection_attempts and
               self._connection_state == ConnectionState.RECONNECTING):

            try:
                await asyncio.sleep(self._reconnect_delay_seconds)

                # Attempt to restart IPC server
                await self.ipc_server.restart()

                self._connection_state = ConnectionState.CONNECTED
                self._last_connection_time = datetime.now()
                self._connection_attempts = 0
                self._connection_error = None
                await self._notify_connection_handlers()

                logger.info("Reconnection successful")
                return

            except Exception as e:
                self._connection_attempts += 1
                self._connection_error = str(e)

                logger.warning(f"Reconnection attempt {self._connection_attempts} failed: {e}")

                # Exponential backoff
                self._reconnect_delay_seconds = min(self._reconnect_delay_seconds * 1.5, 30.0)

        # Max attempts reached
        self._connection_state = ConnectionState.ERROR
        await self._notify_connection_handlers()

        logger.error(f"Failed to reconnect after {self._max_connection_attempts} attempts")

    def get_connection_status(self) -> Dict[str, Any]:
        """Get current connection status"""

        return {
            "state": self._connection_state.value,
            "connected": self._connection_state == ConnectionState.CONNECTED,
            "last_connection_time": self._last_connection_time.isoformat() if self._last_connection_time else None,
            "connection_attempts": self._connection_attempts,
            "connection_drops": self._connection_drops,
            "error": self._connection_error,
            "statistics": {
                "messages_sent": self._messages_sent,
                "messages_received": self._messages_received,
                "commands_processed": self._commands_processed,
                "queries_processed": self._queries_processed
            },
            "server_info": {
                "is_running": self.ipc_server.is_running if hasattr(self.ipc_server, 'is_running') else False,
                "port": getattr(self.ipc_server, 'port', None),
                "client_count": getattr(self.ipc_server, 'client_count', 0)
            }
        }

    async def _setup_message_handlers(self):
        """Setup message routing handlers"""

        # Register CommandHandler with MessageDispatcher for all command types
        from infrastructure.communication.message_dispatcher import CommandType
        for command_type in CommandType:
            self.message_dispatcher.register_command_handler(command_type, self.command_handler)

        # Register QueryHandler with MessageDispatcher for common query types
        common_query_types = [
            "system_status", "workflow_state", "hardware_status",
            "configuration", "data_summary", "session_info"
        ]
        for query_type in common_query_types:
            self.message_dispatcher.register_query_handler(query_type, self.query_handler)

        # Register MessageDispatcher with IPC server as the main message handler
        self.ipc_server.register_handler("main", self.message_dispatcher)

        # Register connection handlers
        self.ipc_server.on_message_received = self._handle_received_message
        self.ipc_server.on_connection_lost = self.handle_connection_lost

        logger.debug("Message handlers setup complete")

    async def _handle_command_message(self, message_data: Dict[str, Any]):
        """Handle command message from frontend"""

        try:
            command_id = message_data.get("command_id", "unknown")
            command_type = message_data.get("command_type")
            parameters = message_data.get("parameters", {})

            logger.debug(f"Processing command: {command_type}")

            # Process command
            result = await self.command_handler.handle_command(command_type, parameters)

            # Send response
            await self.send_command_response(
                command_id=command_id,
                success=result.get("success", False),
                result=result.get("result"),
                error=result.get("error")
            )

            self._commands_processed += 1

        except Exception as e:
            logger.exception("Error handling command message")

            await self.send_command_response(
                command_id=message_data.get("command_id", "unknown"),
                success=False,
                error=f"Command processing error: {str(e)}"
            )

    async def _handle_query_message(self, message_data: Dict[str, Any]):
        """Handle query message from frontend"""

        try:
            query_id = message_data.get("query_id", "unknown")
            query_type = message_data.get("query_type")
            parameters = message_data.get("parameters", {})

            logger.debug(f"Processing query: {query_type}")

            # Process query
            result = await self.query_handler.handle_query(query_type, parameters)

            # Send response
            await self.send_query_response(query_id, result)

        except Exception as e:
            logger.exception("Error handling query message")

            error_result = {
                "success": False,
                "error": f"Query processing error: {str(e)}",
                "query_type": message_data.get("query_type", "unknown")
            }

            await self.send_query_response(
                message_data.get("query_id", "unknown"),
                error_result
            )

    async def _handle_received_message(self, message: str):
        """Handle received message from IPC server"""

        try:
            self._messages_received += 1

            # Parse message
            message_data = json.loads(message)

            # Dispatch to appropriate handler
            await self.message_dispatcher.dispatch_message(message_data)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse received message: {e}")
        except Exception as e:
            logger.exception("Error handling received message")

    async def _send_message(self, message_data: Dict[str, Any]):
        """Send message to frontend via IPC"""

        try:
            if self._connection_state != ConnectionState.CONNECTED:
                logger.warning("Cannot send message, not connected")
                return

            message_json = json.dumps(message_data)
            await self.ipc_server.send_message(message_json)

            self._messages_sent += 1

        except Exception as e:
            logger.error(f"Error sending message: {e}")

    async def _notify_connection_handlers(self):
        """Notify all connection state handlers"""

        for handler in self._connection_handlers:
            try:
                await handler(self._connection_state)
            except Exception as e:
                logger.error(f"Error in connection handler: {e}")

    def reset_statistics(self):
        """Reset communication statistics"""

        self._messages_sent = 0
        self._messages_received = 0
        self._commands_processed = 0
        self._queries_processed = 0
        self._connection_drops = 0

        logger.info("Communication statistics reset")