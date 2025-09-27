"""
Message Dispatcher - IPC Message Routing

This module implements message routing and dispatching for the IPC server
as specified in the architecture. Routes incoming commands to appropriate
handlers and manages response handling.
"""

import logging
from typing import Dict, Optional, Any
from enum import Enum

from .ipc_server import IPCMessage, IPCHandler, MessageType

logger = logging.getLogger(__name__)


class CommandType(Enum):
    """Available command types from frontend"""
    # System commands
    SYSTEM_STATUS = "system_status"
    SYSTEM_SHUTDOWN = "system_shutdown"

    # Workflow commands
    WORKFLOW_START = "workflow_start"
    WORKFLOW_PAUSE = "workflow_pause"
    WORKFLOW_RESUME = "workflow_resume"
    WORKFLOW_STOP = "workflow_stop"
    WORKFLOW_RESET = "workflow_reset"

    # Configuration commands
    CONFIG_UPDATE = "config_update"
    CONFIG_VALIDATE = "config_validate"
    CONFIG_RESET = "config_reset"

    # Hardware commands
    HARDWARE_INITIALIZE = "hardware_initialize"
    HARDWARE_CALIBRATE = "hardware_calibrate"
    HARDWARE_TEST = "hardware_test"

    # Data commands
    DATA_START_ACQUISITION = "data_start_acquisition"
    DATA_STOP_ACQUISITION = "data_stop_acquisition"
    DATA_EXPORT = "data_export"


class MessageDispatcher(IPCHandler):
    """
    Message Dispatcher for IPC Commands

    Routes incoming IPC messages to appropriate command handlers
    based on message type and command content.
    """

    def __init__(self):
        """Initialize message dispatcher"""
        self._command_handlers: Dict[CommandType, IPCHandler] = {}
        self._query_handlers: Dict[str, IPCHandler] = {}

        logger.info("Message dispatcher initialized")

    def register_command_handler(self, command_type: CommandType, handler: IPCHandler) -> None:
        """
        Register handler for specific command type

        Args:
            command_type: Type of command to handle
            handler: Handler instance for the command
        """
        self._command_handlers[command_type] = handler
        logger.info(f"Registered command handler: {command_type.value}")

    def register_query_handler(self, query_type: str, handler: IPCHandler) -> None:
        """
        Register handler for specific query type

        Args:
            query_type: Type of query to handle
            handler: Handler instance for the query
        """
        self._query_handlers[query_type] = handler
        logger.info(f"Registered query handler: {query_type}")

    async def handle_message(self, message: IPCMessage) -> Optional[IPCMessage]:
        """
        Handle incoming IPC message and route to appropriate handler

        Args:
            message: Validated IPC message from frontend

        Returns:
            Optional response message to send back to frontend
        """
        try:
            if message.message_type == MessageType.COMMAND:
                return await self._handle_command(message)
            elif message.message_type == MessageType.QUERY:
                return await self._handle_query(message)
            else:
                logger.warning(f"Unhandled message type: {message.message_type}")
                return self._create_error_response(
                    message,
                    f"Unsupported message type: {message.message_type}"
                )

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return self._create_error_response(message, f"Message handling failed: {str(e)}")

    async def _handle_command(self, message: IPCMessage) -> Optional[IPCMessage]:
        """
        Handle command message

        Args:
            message: Command message to handle

        Returns:
            Optional response message
        """
        command_name = message.payload.get("command")
        if not command_name:
            return self._create_error_response(message, "Missing command in payload")

        try:
            command_type = CommandType(command_name)
        except ValueError:
            return self._create_error_response(
                message,
                f"Unknown command: {command_name}. Available: {[c.value for c in CommandType]}"
            )

        if command_type not in self._command_handlers:
            return self._create_error_response(
                message,
                f"No handler registered for command: {command_name}"
            )

        # Route to appropriate command handler
        handler = self._command_handlers[command_type]
        return await handler.handle_message(message)

    async def _handle_query(self, message: IPCMessage) -> Optional[IPCMessage]:
        """
        Handle query message

        Args:
            message: Query message to handle

        Returns:
            Optional response message
        """
        query_type = message.payload.get("query_type")
        if not query_type:
            return self._create_error_response(message, "Missing query_type in payload")

        if query_type not in self._query_handlers:
            return self._create_error_response(
                message,
                f"No handler registered for query: {query_type}"
            )

        # Route to appropriate query handler
        handler = self._query_handlers[query_type]
        return await handler.handle_message(message)

    def _create_error_response(self, original_message: IPCMessage, error_message: str) -> IPCMessage:
        """
        Create error response message

        Args:
            original_message: Original message that caused the error
            error_message: Error message

        Returns:
            Error response message
        """
        return IPCMessage(
            message_type=MessageType.ERROR,
            message_id=original_message.message_id,  # Use same ID for correlation
            timestamp=original_message.timestamp,
            payload={
                "error": error_message,
                "original_command": original_message.payload.get("command"),
                "original_query": original_message.payload.get("query_type")
            }
        )


class SystemCommandHandler(IPCHandler):
    """
    System Command Handler

    Handles system-level commands like status, shutdown, etc.
    """

    async def handle_message(self, message: IPCMessage) -> Optional[IPCMessage]:
        """Handle system command message"""
        command = message.payload.get("command")

        if command == CommandType.SYSTEM_STATUS.value:
            return await self._handle_system_status(message)
        elif command == CommandType.SYSTEM_SHUTDOWN.value:
            return await self._handle_system_shutdown(message)
        else:
            logger.warning(f"Unhandled system command: {command}")
            return None

    async def _handle_system_status(self, message: IPCMessage) -> IPCMessage:
        """Handle system status query"""
        # TODO: Implement actual system status collection
        status_data = {
            "status": "running",
            "uptime": "1h 23m",
            "memory_usage": "2.1GB",
            "cpu_usage": "15%",
            "hardware_status": {
                "camera": "connected",
                "display": "ready",
                "storage": "available"
            }
        }

        return IPCMessage(
            message_type=MessageType.RESPONSE,
            message_id=message.message_id,
            timestamp=message.timestamp,
            payload={
                "command": "system_status",
                "data": status_data
            }
        )

    async def _handle_system_shutdown(self, message: IPCMessage) -> IPCMessage:
        """Handle system shutdown command"""
        # TODO: Implement graceful shutdown
        logger.info("System shutdown requested")

        return IPCMessage(
            message_type=MessageType.RESPONSE,
            message_id=message.message_id,
            timestamp=message.timestamp,
            payload={
                "command": "system_shutdown",
                "status": "shutdown_initiated"
            }
        )