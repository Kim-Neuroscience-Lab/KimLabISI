"""
IPC Server - Electron Inter-Process Communication

This module implements the IPC server for communication between the Electron
frontend and Python backend as specified in ADR-0005 (Electron IPC Communication)
and ADR-0003 (Thin Client Architecture).

IPC Server Responsibilities:
- Receive commands from Electron frontend via stdin
- Send state updates to frontend via stdout
- Route messages to appropriate handlers
- Maintain thin client pattern (frontend has zero business logic)
- Provide type-safe communication using Pydantic V2
"""

import asyncio
import logging
import sys
import json
import uuid
from typing import Dict, Callable, Any, Optional
from abc import ABC, abstractmethod
from enum import Enum
from pydantic import BaseModel, Field, ValidationError
from datetime import datetime

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """IPC message types for frontend-backend communication"""
    # Commands from frontend to backend
    COMMAND = "command"
    QUERY = "query"

    # Responses from backend to frontend
    STATE_UPDATE = "state_update"
    NOTIFICATION = "notification"
    RESPONSE = "response"
    ERROR = "error"


class IPCMessage(BaseModel):
    """Base IPC message structure using Pydantic V2"""
    message_type: MessageType
    message_id: str = Field(description="Unique message identifier")
    timestamp: float = Field(description="Message timestamp")
    payload: Dict[str, Any] = Field(description="Message payload data")

    model_config = {"use_enum_values": True}


class IPCHandler(ABC):
    """Abstract base class for IPC message handlers"""

    @abstractmethod
    async def handle_message(self, message: IPCMessage) -> Optional[IPCMessage]:
        """
        Handle incoming IPC message

        Args:
            message: Validated IPC message from frontend

        Returns:
            Optional response message to send back to frontend
        """
        pass


class IPCServer:
    """
    IPC Server for Electron Frontend Communication

    Implements native Electron IPC using stdin/stdout for message passing.
    Provides type-safe communication with automatic message validation,
    handler routing, and error handling with graceful degradation.
    """

    def __init__(self):
        """Initialize IPC server for native Electron communication"""
        self._handlers: Dict[str, IPCHandler] = {}
        self._subscribers: Dict[str, list[Callable]] = {}
        self._running = False
        self._message_queue = asyncio.Queue()

        # IPC streams
        self._stdin_reader = None
        self._stdout_writer = None

        logger.info("IPC server initialized for native Electron communication")

    def register_handler(self, handler_name: str, handler: IPCHandler) -> None:
        """
        Register message handler

        Args:
            handler_name: Name identifier for the handler
            handler: Handler instance implementing IPCHandler interface
        """
        self._handlers[handler_name] = handler
        logger.info(f"Registered IPC handler: {handler_name}")

    def subscribe_to_state_updates(self, state_type: str, callback: Callable) -> None:
        """
        Subscribe to state updates for broadcasting to frontend

        Args:
            state_type: Type of state to subscribe to
            callback: Callback function to handle state updates
        """
        if state_type not in self._subscribers:
            self._subscribers[state_type] = []
        self._subscribers[state_type].append(callback)
        logger.info(f"Subscribed to state updates: {state_type}")

    async def start(self) -> None:
        """Start the IPC server and begin processing messages"""
        self._running = True
        logger.info("Starting IPC server...")

        # Set up stdin/stdout for IPC communication
        self._stdin_reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self._stdin_reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        # Start message processing tasks
        asyncio.create_task(self._process_stdin_messages())
        asyncio.create_task(self._process_outgoing_messages())

        logger.info("IPC server started - listening for Electron messages")

    async def stop(self) -> None:
        """Stop the IPC server gracefully"""
        logger.info("Stopping IPC server...")
        self._running = False
        logger.info("IPC server stopped")

    def is_connected(self) -> bool:
        """Check if IPC server is connected and running"""
        return self._running

    @property
    def is_running(self) -> bool:
        """Check if IPC server is running"""
        return self._running

    async def send_state_update(self, state_type: str, state_data: Dict[str, Any]) -> None:
        """
        Send state update to frontend

        Args:
            state_type: Type of state being updated
            state_data: State data to send
        """
        message = IPCMessage(
            message_type=MessageType.STATE_UPDATE,
            message_id=self._generate_message_id(),
            timestamp=datetime.now().timestamp(),
            payload={
                "state_type": state_type,
                "state_data": state_data
            }
        )

        await self._send_to_frontend(message)

    async def send_notification(self, level: str, title: str, message: str,
                              details: Optional[Dict[str, Any]] = None) -> None:
        """
        Send notification to frontend

        Args:
            level: Notification level (info, warning, error)
            title: Notification title
            message: Notification message
            details: Additional notification details
        """
        notification = IPCMessage(
            message_type=MessageType.NOTIFICATION,
            message_id=self._generate_message_id(),
            timestamp=datetime.now().timestamp(),
            payload={
                "level": level,
                "title": title,
                "message": message,
                "details": details or {}
            }
        )

        await self._send_to_frontend(notification)

    async def send_message(self, message_json: str) -> None:
        """
        Send raw JSON message to frontend (used by StateBroadcaster)

        Args:
            message_json: JSON string message to send
        """
        try:
            sys.stdout.write(message_json + "\n")
            sys.stdout.flush()
            logger.debug("Sent raw message to frontend")
        except Exception as e:
            logger.error(f"Failed to send raw message to frontend: {e}")

    async def _process_stdin_messages(self) -> None:
        """Process incoming messages from Electron frontend via stdin"""
        while self._running:
            try:
                # Read line from stdin (Electron sends JSON messages line by line)
                line = await self._stdin_reader.readline()
                if not line:
                    await asyncio.sleep(0.1)
                    continue

                # Parse JSON message
                try:
                    message_data = json.loads(line.decode().strip())
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received from frontend: {e}")
                    await self._send_error_response("Invalid JSON format", str(e))
                    continue

                # Validate message structure
                try:
                    message = IPCMessage.model_validate(message_data)
                except ValidationError as e:
                    logger.error(f"Invalid message structure: {e}")
                    await self._send_error_response("Invalid message format", str(e))
                    continue

                # Queue message for processing
                await self._message_queue.put(message)

            except Exception as e:
                logger.error(f"Error processing stdin: {e}")
                await asyncio.sleep(1.0)

    async def _process_outgoing_messages(self) -> None:
        """Process queued messages and route to handlers"""
        while self._running:
            try:
                # Get message from queue with timeout
                message = await asyncio.wait_for(self._message_queue.get(), timeout=1.0)

                # Route message to appropriate handler
                await self._route_message(message)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing message: {e}")

    async def _route_message(self, message: IPCMessage) -> None:
        """
        Route message to appropriate handler

        Args:
            message: Validated IPC message to route
        """
        try:
            # Determine handler based on message payload
            handler_name = message.payload.get("handler", "command_handler")

            if handler_name not in self._handlers:
                await self._send_error_response(
                    f"Unknown handler: {handler_name}",
                    f"Available handlers: {list(self._handlers.keys())}"
                )
                return

            # Process message with handler
            handler = self._handlers[handler_name]
            response = await handler.handle_message(message)

            # Send response if handler returned one
            if response:
                await self._send_to_frontend(response)

        except Exception as e:
            logger.error(f"Error routing message: {e}")
            await self._send_error_response("Message routing failed", str(e))

    async def _send_to_frontend(self, message: IPCMessage) -> None:
        """
        Send message to frontend via stdout

        Args:
            message: Message to send to frontend
        """
        try:
            # Serialize message to JSON
            message_json = message.model_dump_json()

            # Send via stdout with newline (Electron expects line-delimited JSON)
            sys.stdout.write(message_json + "\n")
            sys.stdout.flush()

            logger.debug(f"Sent message to frontend: {message.message_type.value}")

        except Exception as e:
            logger.error(f"Failed to send message to frontend: {e}")

    async def _send_error_response(self, error_message: str, details: str) -> None:
        """
        Send error response to frontend

        Args:
            error_message: Error message
            details: Error details
        """
        error_response = IPCMessage(
            message_type=MessageType.ERROR,
            message_id=self._generate_message_id(),
            timestamp=datetime.now().timestamp(),
            payload={
                "error": error_message,
                "details": details
            }
        )

        await self._send_to_frontend(error_response)

    def _generate_message_id(self) -> str:
        """Generate unique message ID"""
        return str(uuid.uuid4())


class IPCClient:
    """
    IPC Client for testing and development

    Provides a simple interface for testing IPC communication
    without requiring a full Electron frontend.
    """

    def __init__(self):
        """Initialize IPC client"""
        self._message_handlers: Dict[MessageType, Callable] = {}

    def register_message_handler(self, message_type: MessageType, handler: Callable) -> None:
        """Register handler for specific message type"""
        self._message_handlers[message_type] = handler

    async def send_command(self, command: str, parameters: Dict[str, Any]) -> None:
        """
        Send command to backend via stdout (simulating Electron)

        Args:
            command: Command to send
            parameters: Command parameters
        """
        message = IPCMessage(
            message_type=MessageType.COMMAND,
            message_id=str(uuid.uuid4()),
            timestamp=datetime.now().timestamp(),
            payload={
                "command": command,
                "parameters": parameters
            }
        )

        # Send message via stdout
        message_json = message.model_dump_json()
        print(message_json, flush=True)

    async def listen_for_responses(self) -> None:
        """Listen for responses from backend via stdin"""
        while True:
            try:
                line = input()
                if not line:
                    continue

                message_data = json.loads(line)
                message = IPCMessage.model_validate(message_data)

                # Route to appropriate handler
                if message.message_type in self._message_handlers:
                    handler = self._message_handlers[message.message_type]
                    await handler(message)
                else:
                    logger.info(f"Received unhandled message: {message.message_type}")

            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                logger.error(f"Error processing response: {e}")