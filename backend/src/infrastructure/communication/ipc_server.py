"""
IPC Server - Electron Inter-Process Communication

This module implements the IPC server for communication between the Electron
frontend and Python backend as specified in ADR-0005 (IPC/WebSocket Communication)
and ADR-0003 (Thin Client Architecture).

IPC Server Responsibilities:
- Receive commands from Electron frontend
- Send state updates to frontend for display
- Route messages to appropriate handlers
- Maintain thin client pattern (frontend has zero business logic)
- Provide type-safe communication using Pydantic V2
"""

import asyncio
import logging
import sys
import json
import websockets
from typing import Dict, Callable, Any, Optional, Set
from abc import ABC, abstractmethod
from enum import Enum
from pydantic import BaseModel, Field, ValidationError

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


class CommandMessage(BaseModel):
    """Command message from frontend to backend"""
    command: str = Field(description="Command name")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Command parameters")
    request_id: Optional[str] = Field(None, description="Request ID for response correlation")


class StateUpdateMessage(BaseModel):
    """State update message from backend to frontend"""
    state_type: str = Field(description="Type of state being updated")
    state_data: Dict[str, Any] = Field(description="State data for frontend display")


class NotificationMessage(BaseModel):
    """Notification message from backend to frontend"""
    level: str = Field(description="Notification level (info, warning, error)")
    title: str = Field(description="Notification title")
    message: str = Field(description="Notification message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional notification details")


class IPCHandler(ABC):
    """Abstract base class for IPC message handlers"""

    @abstractmethod
    async def handle_command(self, command: CommandMessage) -> Dict[str, Any]:
        """Handle command from frontend"""
        pass

    @abstractmethod
    async def handle_query(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Handle query from frontend"""
        pass


class IPCServer:
    """
    IPC Server for Electron Frontend Communication

    Implements the communication layer between Electron frontend and Python backend
    following the thin client architecture pattern. All business logic remains
    in the backend; frontend only sends commands and receives state updates.

    Design Principles:
    - Frontend sends commands, backend processes and responds
    - Backend broadcasts state updates for frontend display
    - Type-safe message validation using Pydantic V2
    - No business logic in communication layer
    - Error handling with graceful degradation
    """

    def __init__(self, host: str = "localhost", port: int = 8765):
        """Initialize IPC server with WebSocket support"""
        self._handlers: Dict[str, IPCHandler] = {}
        self._subscribers: Dict[str, list[Callable]] = {}
        self._running = False
        self._message_queue = asyncio.Queue()

        # WebSocket configuration
        self.host = host
        self.port = port
        self.websocket_server = None
        self.connected_clients: Set[websockets.WebSocketServerProtocol] = set()

        logger.info(f"IPC server initialized for WebSocket on {host}:{port}")

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
        """Start the WebSocket IPC server"""
        self._running = True
        logger.info("Starting WebSocket IPC server...")

        # Start message processing loop
        asyncio.create_task(self._process_messages())

        # Start WebSocket server
        try:
            self.websocket_server = await websockets.serve(
                self._handle_websocket_connection,
                self.host,
                self.port,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10
            )
            logger.info(f"WebSocket IPC server started on {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
            raise

    async def stop(self) -> None:
        """Stop the WebSocket IPC server"""
        self._running = False
        logger.info("Stopping WebSocket IPC server...")

        # Close all client connections
        if self.connected_clients:
            await asyncio.gather(
                *[client.close() for client in self.connected_clients],
                return_exceptions=True
            )
            self.connected_clients.clear()

        # Stop WebSocket server
        if self.websocket_server:
            close_result = self.websocket_server.close()
            # Handle case where close() returns a coroutine (e.g., in tests with AsyncMock)
            if hasattr(close_result, '__await__'):
                await close_result
            await self.websocket_server.wait_closed()

        logger.info("WebSocket IPC server stopped")

    async def send_state_update(self, state_type: str, state_data: Dict[str, Any]) -> None:
        """
        Send state update to frontend

        Args:
            state_type: Type of state being updated
            state_data: State data for frontend display
        """
        message = IPCMessage(
            message_type=MessageType.STATE_UPDATE,
            message_id=self._generate_message_id(),
            timestamp=asyncio.get_event_loop().time(),
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
            timestamp=asyncio.get_event_loop().time(),
            payload={
                "level": level,
                "title": title,
                "message": message,
                "details": details or {}
            }
        )

        await self._send_to_frontend(notification)

    async def _process_messages(self) -> None:
        """Process incoming messages from frontend"""
        while self._running:
            try:
                # Get message from queue (this would be populated by platform-specific IPC)
                message_data = await asyncio.wait_for(self._message_queue.get(), timeout=1.0)

                # Parse and validate message
                try:
                    message = IPCMessage.model_validate(message_data)
                except ValidationError as e:
                    logger.error(f"Invalid message received: {e}")
                    await self._send_error_response("Invalid message format", str(e))
                    continue

                # Route message to appropriate handler
                await self._route_message(message)

            except asyncio.TimeoutError:
                # No message received, continue loop
                continue
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await self._send_error_response("Message processing failed", str(e))

    async def _route_message(self, message: IPCMessage) -> None:
        """Route message to appropriate handler"""
        try:
            if message.message_type == MessageType.COMMAND.value:
                await self._handle_command(message)
            elif message.message_type == MessageType.QUERY.value:
                await self._handle_query(message)
            else:
                logger.warning(f"Unhandled message type: {message.message_type}")

        except Exception as e:
            logger.error(f"Error routing message: {e}")
            await self._send_error_response("Message routing failed", str(e))

    async def _handle_command(self, message: IPCMessage) -> None:
        """Handle command message from frontend"""
        try:
            command_data = CommandMessage.model_validate(message.payload)

            # Route to appropriate handler based on command
            handler_name = self._get_handler_for_command(command_data.command)
            if handler_name not in self._handlers:
                raise ValueError(f"No handler registered for command: {command_data.command}")

            handler = self._handlers[handler_name]
            result = await handler.handle_command(command_data)

            # Send response back to frontend
            await self._send_response(message.message_id, result)

        except Exception as e:
            logger.error(f"Error handling command: {e}")
            await self._send_error_response("Command handling failed", str(e), message.message_id)

    async def _handle_query(self, message: IPCMessage) -> None:
        """Handle query message from frontend"""
        try:
            # Route to appropriate handler
            # For now, route all queries to the first available handler
            if not self._handlers:
                raise ValueError("No handlers available for query")

            handler = next(iter(self._handlers.values()))
            result = await handler.handle_query(message.payload)

            # Send response back to frontend
            await self._send_response(message.message_id, result)

        except Exception as e:
            logger.error(f"Error handling query: {e}")
            await self._send_error_response("Query handling failed", str(e), message.message_id)

    async def _send_response(self, request_id: str, data: Dict[str, Any]) -> None:
        """Send response to frontend"""
        response = IPCMessage(
            message_type=MessageType.RESPONSE,
            message_id=request_id,
            timestamp=asyncio.get_event_loop().time(),
            payload=data
        )

        await self._send_to_frontend(response)

    async def _send_error_response(self, error_message: str, details: str,
                                 request_id: Optional[str] = None) -> None:
        """Send error response to frontend"""
        error_response = IPCMessage(
            message_type=MessageType.ERROR,
            message_id=request_id or self._generate_message_id(),
            timestamp=asyncio.get_event_loop().time(),
            payload={
                "error": error_message,
                "details": details
            }
        )

        await self._send_to_frontend(error_response)

    async def _send_to_frontend(self, message: IPCMessage) -> None:
        """Send message to frontend via WebSocket"""
        if not self.connected_clients:
            logger.debug("No connected clients to send message to")
            return

        # Serialize message using Pydantic
        message_json = message.model_dump_json()

        # Send to all connected clients
        disconnected_clients = set()
        for client in self.connected_clients:
            try:
                await client.send(message_json)
                logger.debug(f"Sent message {message.message_id} to client")
            except websockets.exceptions.ConnectionClosed:
                logger.info("Client connection closed during send")
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"Error sending message to client: {e}")
                disconnected_clients.add(client)

        # Clean up disconnected clients
        self.connected_clients -= disconnected_clients

    async def _handle_websocket_connection(self, websocket: websockets.WebSocketServerProtocol, path: str) -> None:
        """Handle new WebSocket connection from frontend"""
        logger.info(f"New WebSocket connection from {websocket.remote_address}")
        self.connected_clients.add(websocket)

        try:
            # Send welcome message
            welcome_message = IPCMessage(
                message_type=MessageType.STATE_UPDATE,
                message_id=self._generate_message_id(),
                timestamp=asyncio.get_event_loop().time(),
                payload={
                    "state_type": "connection",
                    "state_data": {"status": "connected", "server": "ISI Macroscope Backend"}
                }
            )
            await websocket.send(welcome_message.model_dump_json())

            # Listen for messages from client
            async for message in websocket:
                try:
                    # Parse incoming message
                    message_data = json.loads(message)
                    await self._handle_frontend_message(message_data, websocket)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from client: {e}")
                    await self._send_error_to_client(websocket, "Invalid JSON format", str(e))
                except Exception as e:
                    logger.error(f"Error processing client message: {e}")
                    await self._send_error_to_client(websocket, "Message processing failed", str(e))

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"WebSocket connection closed: {websocket.remote_address}")
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
        finally:
            # Clean up connection
            self.connected_clients.discard(websocket)
            logger.info(f"WebSocket connection cleanup complete")

    async def _handle_frontend_message(self, message_data: Dict[str, Any], websocket: websockets.WebSocketServerProtocol) -> None:
        """Handle message received from frontend"""
        try:
            # Determine message type and route appropriately
            if "command" in message_data:
                # Command message
                command_message = CommandMessage(
                    command=message_data["command"],
                    parameters=message_data.get("parameters", {}),
                    request_id=message_data.get("request_id")
                )
                await self._process_command_message(command_message, websocket)
            elif "query" in message_data:
                # Query message
                await self._process_query_message(message_data, websocket)
            else:
                logger.warning(f"Unknown message format: {message_data}")
                await self._send_error_to_client(websocket, "Unknown message format", "Expected 'command' or 'query'")

        except Exception as e:
            logger.error(f"Error handling frontend message: {e}")
            await self._send_error_to_client(websocket, "Message handling failed", str(e))

    async def _process_command_message(self, command_message: CommandMessage, websocket: websockets.WebSocketServerProtocol) -> None:
        """Process command message and send response back to specific client"""
        handler_name = self._get_handler_for_command(command_message.command)

        if handler_name in self._handlers:
            try:
                # Get response from handler
                response_data = await self._handlers[handler_name].handle_command(command_message)

                # Send response back to specific client
                response_message = IPCMessage(
                    message_type=MessageType.RESPONSE,
                    message_id=command_message.request_id or self._generate_message_id(),
                    timestamp=asyncio.get_event_loop().time(),
                    payload=response_data
                )
                await websocket.send(response_message.model_dump_json())

            except Exception as e:
                logger.error(f"Handler error for command {command_message.command}: {e}")
                await self._send_error_to_client(websocket, f"Command failed: {command_message.command}", str(e))
        else:
            await self._send_error_to_client(websocket, "No handler found", f"No handler for command: {command_message.command}")

    async def _process_query_message(self, query_data: Dict[str, Any], websocket: websockets.WebSocketServerProtocol) -> None:
        """Process query message and send response back to specific client"""
        # For now, route queries to the first available handler
        if self._handlers:
            handler = next(iter(self._handlers.values()))
            try:
                response_data = await handler.handle_query(query_data)

                response_message = IPCMessage(
                    message_type=MessageType.RESPONSE,
                    message_id=query_data.get("request_id", self._generate_message_id()),
                    timestamp=asyncio.get_event_loop().time(),
                    payload=response_data
                )
                await websocket.send(response_message.model_dump_json())

            except Exception as e:
                logger.error(f"Query handler error: {e}")
                await self._send_error_to_client(websocket, "Query failed", str(e))
        else:
            await self._send_error_to_client(websocket, "No handlers available", "No query handlers registered")

    async def _send_error_to_client(self, websocket: websockets.WebSocketServerProtocol, error_message: str, details: str) -> None:
        """Send error message to specific client"""
        error_response = IPCMessage(
            message_type=MessageType.ERROR,
            message_id=self._generate_message_id(),
            timestamp=asyncio.get_event_loop().time(),
            payload={
                "error": error_message,
                "details": details
            }
        )
        try:
            await websocket.send(error_response.model_dump_json())
        except Exception as e:
            logger.error(f"Failed to send error to client: {e}")

    def _get_handler_for_command(self, command: str) -> str:
        """Get appropriate handler name for command"""
        # All commands are handled by the single command_handler
        # This follows the single command handler pattern we implemented
        return "command_handler"

    def _generate_message_id(self) -> str:
        """Generate unique message ID"""
        import uuid
        return str(uuid.uuid4())

    # Platform-specific IPC methods removed - now using WebSocket for all platforms