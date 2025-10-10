"""Multi-channel IPC architecture.

Provides ZeroMQ-backed multi-channel IPC system for control, streaming, sync, and health monitoring.
Simplified from original implementation: accepts config in constructor, no service locator.
"""

from __future__ import annotations

import logging
import time
import threading
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Callable, Dict, Optional

import zmq

logger = logging.getLogger(__name__)


class ChannelType(Enum):
    """Logical IPC channel types."""

    CONTROL = "control"
    STREAMING = "streaming"
    SYNC = "sync"
    HEALTH = "health"


@dataclass(frozen=True)
class ChannelConfig:
    """Configuration for an IPC channel."""

    channel_type: ChannelType
    transport: str  # 'tcp', 'ipc', 'stdin'
    port: Optional[int] = None
    socket_type: Optional[int] = None
    bind: bool = True


@dataclass(frozen=True)
class HealthStatus:
    """System health status payload."""

    timestamp_us: int
    backend_fps: float
    frame_buffer_usage_percent: float
    memory_usage_mb: float
    cpu_usage_percent: float
    active_threads: int
    stimulus_active: bool
    camera_active: bool


@dataclass(frozen=True)
class SyncMessage:
    """Hardware synchronization message."""

    timestamp_us: int
    frame_id: int
    camera_timestamp_us: Optional[int] = None
    stimulus_timestamp_us: Optional[int] = None
    sequence_number: int = 0


class MultiChannelIPC:
    """ZeroMQ-backed multi-channel IPC system.

    Simplified implementation using constructor injection.
    All dependencies are passed as parameters - no service locator.
    """

    def __init__(self, transport: str = "tcp", health_port: int = 5555, sync_port: int = 5558):
        """Initialize IPC with explicit configuration.

        Args:
            transport: Transport type ('tcp', 'ipc')
            health_port: Port for health monitoring channel
            sync_port: Port for synchronization channel
        """
        self._transport = transport
        self._health_port = health_port
        self._sync_port = sync_port

        self._context = zmq.Context()
        self._channels: Dict[ChannelType, Dict[str, Any]] = {}
        self._running = False
        self._lock = threading.RLock()

        self._health_thread: Optional[threading.Thread] = None
        self._health_callback: Optional[Callable[[HealthStatus], None]] = None

        self._sync_thread: Optional[threading.Thread] = None
        self._sync_callback: Optional[Callable[[SyncMessage], None]] = None

    def initialize_channels(self, configs: Dict[ChannelType, ChannelConfig]) -> None:
        """Initialize all configured channels.

        Args:
            configs: Dictionary mapping channel types to their configurations
        """
        try:
            with self._lock:
                for channel_type, channel_config in configs.items():
                    self._initialize_channel(channel_type, channel_config)

                self._running = True

                # ZeroMQ socket binding delay: Prevents "slow joiner syndrome" where
                # PUB sockets send messages before SUB sockets have connected.
                # 50ms is sufficient for socket binding on modern systems.
                time.sleep(0.05)

                logger.info("Initialized %d IPC channels", len(configs))
                for channel_type, channel_info in self._channels.items():
                    logger.info(
                        "  • %s → %s",
                        channel_type.value,
                        channel_info.get("address", "stdio"),
                    )
        except Exception as exc:
            logger.error("Failed to initialize IPC channels: %s", exc)
            self.cleanup()
            raise

    def _initialize_channel(
        self, channel_type: ChannelType, config: ChannelConfig
    ) -> None:
        """Initialize a single channel."""
        if config.transport == "stdin":
            self._channels[channel_type] = {
                "type": "stdio",
                "config": config,
                "socket": None,
                "address": "stdio",
            }
            return

        socket = self._context.socket(config.socket_type)

        if config.transport == "tcp":
            address = (
                f"tcp://*:{config.port}"
                if config.bind
                else f"tcp://localhost:{config.port}"
            )
        elif config.transport == "ipc":
            address = f"ipc:///tmp/isi_{channel_type.value}.ipc"
        else:
            raise ValueError(f"Unsupported transport {config.transport}")

        if config.bind:
            socket.bind(address)
        else:
            socket.connect(address)

        self._channels[channel_type] = {
            "type": "zmq",
            "config": config,
            "socket": socket,
            "address": address,
        }

    def start_health_monitoring(
        self,
        callback: Optional[Callable[[HealthStatus], None]] = None,
        interval_sec: float = 0.1,
    ) -> None:
        """Start health publish loop with optional local callback.

        Args:
            callback: Optional callback to invoke with health status
            interval_sec: Interval between health status updates
        """
        self._health_callback = callback
        self._health_thread = threading.Thread(
            target=self._health_monitoring_loop,
            args=(interval_sec,),
            daemon=True,
        )
        self._health_thread.start()

    def _health_monitoring_loop(self, interval_sec: float) -> None:
        """Background health monitoring loop."""
        try:
            health_socket = self._channels.get(ChannelType.HEALTH, {}).get("socket")
            if not health_socket:
                logger.warning("Health channel not available")
                return

            logger.info("Health monitoring interval set to %.2fs", interval_sec)

            while self._running:
                health_status = self._collect_health_status()

                if self._health_callback:
                    self._health_callback(health_status)

                try:
                    # Send as JSON directly (no pydantic dependency)
                    payload = asdict(health_status)
                    health_socket.send_json(payload, zmq.NOBLOCK)
                except zmq.Again:
                    logger.warning("Health channel backpressure detected")

                time.sleep(interval_sec)
        except Exception as exc:
            logger.error("Health monitoring loop terminated unexpectedly: %s", exc)

    def _collect_health_status(self) -> HealthStatus:
        """Collect current system health metrics."""
        import os
        import psutil

        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()

        return HealthStatus(
            timestamp_us=int(time.time() * 1_000_000),
            backend_fps=60.0,  # Default placeholder
            frame_buffer_usage_percent=50.0,
            memory_usage_mb=memory_info.rss / (1024 * 1024),
            cpu_usage_percent=process.cpu_percent(),
            active_threads=threading.active_count(),
            stimulus_active=False,  # Default placeholder
            camera_active=False,  # Default placeholder
        )

    def start_sync_coordination(self, callback: Callable[[SyncMessage], None]) -> None:
        """Start background sync coordination loop.

        Args:
            callback: Callback to invoke with sync messages
        """
        self._sync_callback = callback
        self._sync_thread = threading.Thread(
            target=self._sync_coordination_loop,
            daemon=True,
        )
        self._sync_thread.start()

    def _sync_coordination_loop(self) -> None:
        """Background sync coordination loop."""
        try:
            sync_socket = self._channels.get(ChannelType.SYNC, {}).get("socket")
            if not sync_socket:
                logger.warning("Sync channel not available")
                return

            sequence_number = 0
            while self._running:
                if sync_socket.poll(timeout=1000):
                    message_data = sync_socket.recv_json(zmq.NOBLOCK)
                    sync_msg = SyncMessage(
                        timestamp_us=message_data.get("timestamp_us", 0),
                        frame_id=message_data.get("frame_id", 0),
                        camera_timestamp_us=message_data.get("camera_timestamp_us"),
                        stimulus_timestamp_us=message_data.get("stimulus_timestamp_us"),
                        sequence_number=sequence_number,
                    )

                    if self._sync_callback:
                        self._sync_callback(sync_msg)

                    sequence_number += 1
        except zmq.Again:
            return
        except Exception as exc:
            logger.error("Sync coordination loop terminated unexpectedly: %s", exc)

    def send_control_message(self, message: Dict[str, Any]) -> bool:
        """Send control message via stdout.

        Args:
            message: Message dictionary to send

        Returns:
            True if message sent successfully, False otherwise
        """
        try:
            import sys
            import json

            json_str = json.dumps(message)
            print(json_str, file=sys.stdout, flush=True)
            return True
        except Exception as exc:
            logger.error("Failed to send control message: %s", exc)
            return False

    def send_sync_message(self, message: Dict[str, Any]) -> bool:
        """Send sync message via ZeroMQ.

        Args:
            message: Message dictionary to send

        Returns:
            True if message sent successfully, False otherwise
        """
        try:
            sync_socket = self._channels.get(ChannelType.SYNC, {}).get("socket")
            if sync_socket is None:
                logger.warning("SYNC channel unavailable")
                return False
            sync_socket.send_json(message, zmq.NOBLOCK)
            return True
        except Exception as exc:
            logger.error("Failed to send sync message: %s", exc)
            return False

    def cleanup(self) -> None:
        """Clean up all resources."""
        with self._lock:
            self._running = False

            if self._health_thread:
                self._health_thread.join(timeout=1.0)
                self._health_thread = None

            if self._sync_thread:
                self._sync_thread.join(timeout=1.0)
                self._sync_thread = None

            for channel_info in self._channels.values():
                socket = channel_info.get("socket")
                if socket is not None:
                    socket.close()

            self._channels.clear()
            self._context.term()

    @property
    def channels(self) -> Dict[ChannelType, Dict[str, Any]]:
        """Get channel information."""
        return self._channels


def build_multi_channel_ipc(transport: str = "tcp", health_port: int = 5555, sync_port: int = 5558) -> MultiChannelIPC:
    """Factory for a fully configured IPC system.

    Args:
        transport: Transport type ('tcp', 'ipc')
        health_port: Port for health monitoring channel
        sync_port: Port for synchronization channel

    Returns:
        Configured MultiChannelIPC instance
    """
    ipc = MultiChannelIPC(transport=transport, health_port=health_port, sync_port=sync_port)
    ipc.initialize_channels(
        {
            ChannelType.CONTROL: ChannelConfig(
                channel_type=ChannelType.CONTROL,
                transport="stdin",
            ),
            ChannelType.HEALTH: ChannelConfig(
                channel_type=ChannelType.HEALTH,
                transport=transport,
                port=health_port,
                socket_type=zmq.PUB,
            ),
            ChannelType.SYNC: ChannelConfig(
                channel_type=ChannelType.SYNC,
                transport=transport,
                port=sync_port,
                socket_type=zmq.PUB,
            ),
        }
    )
    return ipc
