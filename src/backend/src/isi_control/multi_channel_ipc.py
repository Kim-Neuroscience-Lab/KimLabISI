"""
Multi-Channel IPC Architecture
Provides separate optimized channels for different types of communication:
- Control Channel: Parameters, configuration (existing stdin/stdout)
- Streaming Channel: Binary frame data (shared memory)
- Sync Channel: Hardware timestamp coordination (ZeroMQ)
- Health Channel: System status monitoring (ZeroMQ)
"""

import zmq
import json
import time
import threading
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ChannelType(Enum):
    CONTROL = "control"       # stdin/stdout for parameters
    STREAMING = "streaming"   # shared memory for frame data
    SYNC = "sync"            # hardware timestamp coordination
    HEALTH = "health"        # system status monitoring

@dataclass
class ChannelConfig:
    """Configuration for an IPC channel"""
    channel_type: ChannelType
    transport: str  # 'tcp', 'inproc', 'ipc', 'stdin'
    port: Optional[int] = None
    socket_type: Optional[int] = None  # ZeroMQ socket type
    bind: bool = True  # True to bind, False to connect

@dataclass
class HealthStatus:
    """System health status"""
    timestamp_us: int
    backend_fps: float
    frame_buffer_usage_percent: float
    memory_usage_mb: float
    cpu_usage_percent: float
    active_threads: int
    stimulus_active: bool
    camera_active: bool

@dataclass
class SyncMessage:
    """Hardware synchronization message"""
    timestamp_us: int
    frame_id: int
    camera_timestamp_us: Optional[int] = None
    stimulus_timestamp_us: Optional[int] = None
    sequence_number: int = 0

class MultiChannelIPC:
    """Multi-channel IPC communication system"""

    def __init__(self):
        self.zmq_context = zmq.Context()
        self.channels = {}
        self.running = False

        # Health monitoring
        self.health_socket = None
        self.health_thread = None
        self.health_callback = None

        # Sync coordination
        self.sync_socket = None
        self.sync_thread = None
        self.sync_callback = None

        # Threading
        self._lock = threading.RLock()

    def initialize_channels(self, configs: Dict[ChannelType, ChannelConfig]):
        """Initialize all IPC channels"""
        try:
            with self._lock:
                for channel_type, config in configs.items():
                    self._initialize_channel(channel_type, config)

                self.running = True
                logger.info(f"MultiChannelIPC initialized with {len(configs)} channels")

        except Exception as e:
            logger.error(f"Failed to initialize MultiChannelIPC: {e}")
            self.cleanup()
            raise

    def _initialize_channel(self, channel_type: ChannelType, config: ChannelConfig):
        """Initialize a single IPC channel"""
        if config.transport == 'stdin':
            # Control channel uses existing stdin/stdout
            self.channels[channel_type] = {
                'type': 'stdio',
                'config': config,
                'socket': None
            }
            logger.info(f"Initialized {channel_type.value} channel: stdio")
            return

        # ZeroMQ channels
        socket = self.zmq_context.socket(config.socket_type)

        if config.transport == 'tcp':
            address = f"tcp://*:{config.port}" if config.bind else f"tcp://localhost:{config.port}"
        elif config.transport == 'ipc':
            address = f"ipc:///tmp/isi_{channel_type.value}.ipc"
        else:
            raise ValueError(f"Unsupported transport: {config.transport}")

        if config.bind:
            socket.bind(address)
        else:
            socket.connect(address)

        self.channels[channel_type] = {
            'type': 'zmq',
            'config': config,
            'socket': socket,
            'address': address
        }

        logger.info(f"Initialized {channel_type.value} channel: {address}")

    def start_health_monitoring(self, callback: Callable[[HealthStatus], None],
                               interval_sec: float = 0.1):
        """Start health monitoring thread"""
        self.health_callback = callback
        self.health_thread = threading.Thread(
            target=self._health_monitoring_loop,
            args=(interval_sec,),
            daemon=True
        )
        self.health_thread.start()

    def _health_monitoring_loop(self, interval_sec: float):
        """Health monitoring loop"""
        try:
            health_socket = self.channels.get(ChannelType.HEALTH, {}).get('socket')
            if not health_socket:
                logger.warning("Health channel not available")
                return

            logger.info(f"Health monitoring started: {interval_sec}s interval")

            while self.running:
                try:
                    # Collect system health data
                    health_status = self._collect_health_status()

                    # Send via callback for local processing
                    if self.health_callback:
                        self.health_callback(health_status)

                    # Send via ZeroMQ for remote monitoring
                    try:
                        health_socket.send_json(asdict(health_status), zmq.NOBLOCK)
                    except zmq.Again:
                        logger.warning("Health monitoring queue full")

                    time.sleep(interval_sec)

                except Exception as e:
                    logger.error(f"Health monitoring error: {e}")
                    time.sleep(interval_sec)

        except Exception as e:
            logger.error(f"Health monitoring loop failed: {e}")

    def _collect_health_status(self) -> HealthStatus:
        """Collect current system health status"""
        import psutil
        import os

        # Get process info
        process = psutil.Process(os.getpid())

        # Basic system metrics
        memory_info = process.memory_info()
        cpu_percent = process.cpu_percent()

        # Thread count
        active_threads = threading.active_count()

        # Stimulus and camera status (would be connected to actual systems)
        stimulus_active = self._is_stimulus_active()
        camera_active = self._is_camera_active()

        return HealthStatus(
            timestamp_us=int(time.time() * 1_000_000),
            backend_fps=self._get_backend_fps(),
            frame_buffer_usage_percent=50.0,  # Placeholder
            memory_usage_mb=memory_info.rss / (1024 * 1024),
            cpu_usage_percent=cpu_percent,
            active_threads=active_threads,
            stimulus_active=stimulus_active,
            camera_active=camera_active
        )

    def start_sync_coordination(self, callback: Callable[[SyncMessage], None]):
        """Start hardware synchronization coordination"""
        self.sync_callback = callback
        self.sync_thread = threading.Thread(
            target=self._sync_coordination_loop,
            daemon=True
        )
        self.sync_thread.start()

    def _sync_coordination_loop(self):
        """Hardware synchronization loop"""
        try:
            sync_socket = self.channels.get(ChannelType.SYNC, {}).get('socket')
            if not sync_socket:
                logger.warning("Sync channel not available")
                return

            logger.info("Hardware sync coordination started")
            sequence_number = 0

            while self.running:
                try:
                    # Wait for sync messages (blocking with timeout)
                    if sync_socket.poll(timeout=1000):  # 1 second timeout
                        message_data = sync_socket.recv_json(zmq.NOBLOCK)

                        sync_msg = SyncMessage(
                            timestamp_us=message_data.get('timestamp_us', 0),
                            frame_id=message_data.get('frame_id', 0),
                            camera_timestamp_us=message_data.get('camera_timestamp_us'),
                            stimulus_timestamp_us=message_data.get('stimulus_timestamp_us'),
                            sequence_number=sequence_number
                        )

                        # Process sync message
                        if self.sync_callback:
                            self.sync_callback(sync_msg)

                        sequence_number += 1

                except zmq.Again:
                    continue
                except Exception as e:
                    logger.error(f"Sync coordination error: {e}")
                    time.sleep(0.1)

        except Exception as e:
            logger.error(f"Sync coordination loop failed: {e}")

    def send_control_message(self, message: Dict[str, Any]) -> bool:
        """Send message via control channel (existing stdout)"""
        try:
            import sys
            json_str = json.dumps(message)
            logger.debug(f"Sending CONTROL message to stdout: {message.get('type', 'unknown')}")
            print(json_str, file=sys.stdout, flush=True)
            logger.debug(f"CONTROL message sent successfully")
            return True
        except Exception as e:
            logger.error(f"Error sending control message: {e}")
            return False

    def send_sync_message(self, sync_msg: SyncMessage) -> bool:
        """Send hardware sync message"""
        try:
            sync_socket = self.channels.get(ChannelType.SYNC, {}).get('socket')
            if sync_socket:
                sync_socket.send_json(asdict(sync_msg), zmq.NOBLOCK)
                return True
            return False
        except Exception as e:
            logger.error(f"Error sending sync message: {e}")
            return False

    def send_startup_message(self, message: Dict[str, Any]) -> bool:
        """Send startup progress message via SYNC channel"""
        try:
            sync_socket = self.channels.get(ChannelType.SYNC, {}).get('socket')
            if sync_socket:
                sync_socket.send_json(message, zmq.NOBLOCK)
                return True
            return False
        except Exception as e:
            logger.error(f"Error sending startup message: {e}")
            return False

    def _is_stimulus_active(self) -> bool:
        """Check if stimulus system is active"""
        try:
            from .stimulus_manager import _stimulus_status
            return _stimulus_status.get("is_presenting", False)
        except:
            return False

    def _is_camera_active(self) -> bool:
        """Check if camera system is active"""
        # Placeholder - would integrate with actual camera system
        return False

    def _get_backend_fps(self) -> float:
        """Get current backend processing FPS"""
        # Placeholder - would track actual frame processing rate
        return 60.0

    def cleanup(self):
        """Clean up all channels and resources"""
        try:
            with self._lock:
                self.running = False

                # Stop monitoring threads
                if self.health_thread:
                    self.health_thread.join(timeout=1.0)

                if self.sync_thread:
                    self.sync_thread.join(timeout=1.0)

                # Close all ZeroMQ sockets
                for channel_info in self.channels.values():
                    if channel_info['type'] == 'zmq' and channel_info['socket']:
                        channel_info['socket'].close()

                self.channels.clear()
                self.zmq_context.term()

                logger.info("MultiChannelIPC cleaned up")

        except Exception as e:
            logger.error(f"Error during MultiChannelIPC cleanup: {e}")

# Global IPC instance
_global_ipc = None

def get_multi_channel_ipc() -> MultiChannelIPC:
    """Get or create global multi-channel IPC instance"""
    global _global_ipc
    if _global_ipc is None:
        _global_ipc = MultiChannelIPC()

        # Initialize with default channel configuration
        default_configs = {
            ChannelType.CONTROL: ChannelConfig(
                channel_type=ChannelType.CONTROL,
                transport='stdin'
            ),
            ChannelType.HEALTH: ChannelConfig(
                channel_type=ChannelType.HEALTH,
                transport='tcp',
                port=5555,
                socket_type=zmq.PUB
            ),
            ChannelType.SYNC: ChannelConfig(
                channel_type=ChannelType.SYNC,
                transport='tcp',
                port=5558,
                socket_type=zmq.PUB
            )
        }

        _global_ipc.initialize_channels(default_configs)

    return _global_ipc

def cleanup_multi_channel_ipc():
    """Clean up global IPC instance"""
    global _global_ipc
    if _global_ipc:
        _global_ipc.cleanup()
        _global_ipc = None