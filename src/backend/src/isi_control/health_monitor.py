"""
Health Monitor - Standardized System Health Checking

This module provides a unified, standardized approach to checking the health
of all ISI Control System components. It implements a consistent interface
and reporting mechanism for all subsystems.

Design Principles:
1. Single Source of Truth - Backend is authoritative for all health status
2. Standardized Interface - All systems implement same health check pattern
3. Consistent Reporting - Same success/failure criteria across all systems
4. Detailed Diagnostics - Rich error information for troubleshooting
5. Performance Optimized - Cached results with configurable refresh intervals
"""

import logging
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Protocol
from enum import Enum

from .service_locator import get_services

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Standardized health status values."""

    ONLINE = "online"  # System is fully operational
    OFFLINE = "offline"  # System is not available but not in error state
    ERROR = "error"  # System encountered an error during health check
    UNKNOWN = "unknown"  # Health status has not been determined yet


@dataclass
class HealthCheckResult:
    """Standardized result structure for health checks."""

    system_name: str
    status: HealthStatus
    timestamp: float = field(default_factory=time.time)
    details: Optional[str] = None
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        """Check if system is in a healthy state."""
        return self.status == HealthStatus.ONLINE

    @property
    def age_seconds(self) -> float:
        """Get age of this health check result in seconds."""
        return time.time() - self.timestamp


class HealthChecker(Protocol):
    """Protocol that all system health checkers must implement."""

    @property
    def system_name(self) -> str:
        """Name of the system this checker monitors."""
        ...

    def check_health(self) -> HealthCheckResult:
        """Perform health check and return standardized result."""
        ...


class BaseHealthChecker(ABC):
    """Base class for standardized health checkers."""

    def __init__(self, system_name: str):
        self.system_name = system_name

    @abstractmethod
    def _perform_health_check(self) -> HealthCheckResult:
        """Implement system-specific health check logic."""
        pass

    def check_health(self) -> HealthCheckResult:
        """Perform health check with standardized error handling."""
        try:
            return self._perform_health_check()
        except Exception as e:
            logger.error(f"Health check failed for {self.system_name}: {e}")
            return HealthCheckResult(
                system_name=self.system_name,
                status=HealthStatus.ERROR,
                error_message=str(e),
            )


class CameraHealthChecker(BaseHealthChecker):
    """Health checker for camera system."""

    def __init__(self):
        super().__init__("camera")

    def _perform_health_check(self) -> HealthCheckResult:
        logger.info("Camera health check: Starting camera detection...")
        from .camera_manager import camera_manager

        try:
            cameras = camera_manager.detect_cameras()
            logger.info(f"Camera health check: Found {len(cameras)} total camera(s)")

            available_cameras = [cam for cam in cameras if cam.is_available]
            logger.info(
                f"Camera health check: {len(available_cameras)} camera(s) available"
            )

            if len(available_cameras) > 0:
                camera_names = [cam.name for cam in available_cameras]
                logger.info(
                    f"Camera health check: Available cameras: {', '.join(camera_names)}"
                )
                logger.info("Camera health check: ✓ ONLINE")
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.ONLINE,
                    details=f"{len(available_cameras)} camera(s) available",
                    metrics={
                        "total_cameras": len(cameras),
                        "available_cameras": len(available_cameras),
                        "camera_names": camera_names,
                    },
                )
            elif len(cameras) > 0:
                logger.warning(
                    "Camera health check: ○ OFFLINE - Cameras detected but none available"
                )
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.OFFLINE,
                    details="Cameras detected but none available",
                    metrics={"total_cameras": len(cameras), "available_cameras": 0},
                )
            else:
                logger.warning("Camera health check: ○ OFFLINE - No cameras detected")
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.OFFLINE,
                    details="No cameras detected",
                )
        except Exception as e:
            logger.error(f"Camera health check: ✗ ERROR - {e}")
            raise


class DisplayHealthChecker(BaseHealthChecker):
    """Health checker for display system."""

    def __init__(self):
        super().__init__("display")

    def _perform_health_check(self) -> HealthCheckResult:
        from .display_manager import display_manager

        displays = display_manager.detect_displays()

        if len(displays) > 0:
            # Handle both dict and object types for display info
            primary_displays = []
            display_info = []

            for d in displays:
                if hasattr(d, "is_primary"):
                    # Object type (DisplayInfo)
                    if d.is_primary:
                        primary_displays.append(d)
                    display_info.append(
                        {
                            "name": getattr(d, "name", "Unknown"),
                            "width": getattr(d, "width", 0),
                            "height": getattr(d, "height", 0),
                            "is_primary": getattr(d, "is_primary", False),
                        }
                    )
                elif isinstance(d, dict):
                    # Dict type
                    if d.get("is_primary", False):
                        primary_displays.append(d)
                    display_info.append(d)
                else:
                    # Fallback for other types
                    display_info.append(str(d))

            return HealthCheckResult(
                system_name=self.system_name,
                status=HealthStatus.ONLINE,
                details=f"{len(displays)} display(s) available",
                metrics={
                    "total_displays": len(displays),
                    "primary_displays": len(primary_displays),
                    "display_info": display_info,
                },
            )
        else:
            return HealthCheckResult(
                system_name=self.system_name,
                status=HealthStatus.OFFLINE,
                details="No displays detected",
            )


class ParameterHealthChecker(BaseHealthChecker):
    """Health checker for parameter manager system."""

    def __init__(self):
        super().__init__("parameters")

    def _perform_health_check(self) -> HealthCheckResult:
        from .service_locator import get_services

        param_manager = get_services().parameter_manager

        # Test parameter manager functionality
        try:
            # Try to load current parameters
            current_params = param_manager.load_parameters()

            # Try to get parameter info
            param_info = param_manager.get_parameter_info()

            if current_params and param_info:
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.ONLINE,
                    details="Parameter manager operational",
                    metrics={
                        "parameter_groups": list(
                            param_info.get("parameter_groups", {}).keys()
                        ),
                        "config_file_exists": param_manager.config_file.exists(),
                        "current_session_name": getattr(
                            current_params.session, "session_name", "Unknown"
                        ),
                    },
                )
            else:
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.ERROR,
                    details="Parameter manager functionality test failed",
                )
        except Exception as e:
            return HealthCheckResult(
                system_name=self.system_name,
                status=HealthStatus.ERROR,
                details="Parameter manager test exception",
                error_message=str(e),
            )


class SharedMemoryHealthChecker(BaseHealthChecker):
    """Health checker for shared memory streaming system."""

    def __init__(self):
        super().__init__("shared_memory")

    def _perform_health_check(self) -> HealthCheckResult:
        """Check shared memory streaming system health."""
        try:
            services = get_services()
            stream = services.shared_memory.stream if services.shared_memory else None

            if stream is None:
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.OFFLINE,
                    details="Shared memory stream not initialized",
                )

            # Check if ZeroMQ socket is connected
            if not hasattr(stream, "metadata_socket") or stream.metadata_socket is None:
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.OFFLINE,
                    details="ZeroMQ metadata socket not initialized",
                )

            # Check shared memory file accessibility
            import os

            shm_path = f"/tmp/{stream.stream_name}_shm"
            if os.path.exists(shm_path):
                # Check file permissions
                if not os.access(shm_path, os.R_OK | os.W_OK):
                    return HealthCheckResult(
                        system_name=self.system_name,
                        status=HealthStatus.ERROR,
                        details="Shared memory file access denied",
                        error_message=f"Cannot read/write: {shm_path}",
                    )
            else:
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.OFFLINE,
                    details="Shared memory file not created yet",
                    metrics={"expected_path": shm_path},
                )

            # System appears healthy
            metrics = {
                "zmq_socket_initialized": hasattr(stream, "metadata_socket")
                and stream.metadata_socket is not None,
                "shared_memory_path": shm_path,
                "frame_counter": getattr(stream, "frame_counter", 0),
                "stream_name": stream.stream_name,
                "buffer_size_bytes": getattr(stream, "buffer_size_bytes", 0),
            }

            return HealthCheckResult(
                system_name=self.system_name,
                status=HealthStatus.ONLINE,
                details="Shared memory streaming system operational",
                metrics=metrics,
            )

        except ImportError as e:
            return HealthCheckResult(
                system_name=self.system_name,
                status=HealthStatus.ERROR,
                details="Shared memory module import failed",
                error_message=str(e),
            )
        except Exception as e:
            return HealthCheckResult(
                system_name=self.system_name,
                status=HealthStatus.ERROR,
                details="Shared memory health check exception",
                error_message=str(e),
            )


class MultiChannelIPCHealthChecker(BaseHealthChecker):
    """Health checker for multi-channel IPC system."""

    def __init__(self):
        super().__init__("multi_channel_ipc")

    def _perform_health_check(self) -> HealthCheckResult:
        """Check multi-channel IPC system health."""
        try:
            from .service_locator import get_services

            ipc = get_services().ipc

            if ipc is None:
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.OFFLINE,
                    details="Multi-channel IPC not initialized",
                )

            # Check if channels are initialized
            if not hasattr(ipc, "channels") or not ipc.channels:
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.OFFLINE,
                    details="IPC channels not initialized",
                )

            # Check individual channel health
            channel_status = {}
            all_healthy = True
            error_messages = []

            for channel_type, channel_info in ipc.channels.items():
                try:
                    # Check if channel has a socket (channels are stored as dictionaries)
                    if isinstance(channel_info, dict) and channel_info.get("socket"):
                        socket = channel_info["socket"]
                        # Test basic socket operations
                        if socket and hasattr(socket, "closed") and not socket.closed:
                            channel_status[channel_type.value] = "online"
                        else:
                            channel_status[channel_type.value] = "offline"
                            all_healthy = False
                    else:
                        # Channel doesn't have a socket (e.g., stdio channels)
                        if (
                            isinstance(channel_info, dict)
                            and channel_info.get("type") == "stdio"
                        ):
                            channel_status[channel_type.value] = (
                                "online"  # stdio is always available
                            )
                        else:
                            channel_status[channel_type.value] = "offline"
                            all_healthy = False
                except Exception as e:
                    channel_status[channel_type.value] = "error"
                    error_messages.append(f"{channel_type.value}: {str(e)}")
                    all_healthy = False

            if all_healthy:
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.ONLINE,
                    details="All IPC channels operational",
                    metrics={
                        "channels": channel_status,
                        "total_channels": len(channel_status),
                        "healthy_channels": len(
                            [s for s in channel_status.values() if s == "online"]
                        ),
                    },
                )
            elif any(status == "online" for status in channel_status.values()):
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.ERROR,
                    details="Some IPC channels are unhealthy",
                    error_message="; ".join(error_messages) if error_messages else None,
                    metrics={
                        "channels": channel_status,
                        "total_channels": len(channel_status),
                        "healthy_channels": len(
                            [s for s in channel_status.values() if s == "online"]
                        ),
                    },
                )
            else:
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.OFFLINE,
                    details="All IPC channels are offline",
                    metrics={
                        "channels": channel_status,
                        "total_channels": len(channel_status),
                        "healthy_channels": 0,
                    },
                )

        except ImportError as e:
            return HealthCheckResult(
                system_name=self.system_name,
                status=HealthStatus.ERROR,
                details="Multi-channel IPC module import failed",
                error_message=str(e),
            )
        except Exception as e:
            return HealthCheckResult(
                system_name=self.system_name,
                status=HealthStatus.ERROR,
                details="Multi-channel IPC health check exception",
                error_message=str(e),
            )


class RealtimeStreamingHealthChecker(BaseHealthChecker):
    """Health checker for realtime streaming system."""

    def __init__(self):
        super().__init__("realtime_streaming")

    def _perform_health_check(self) -> HealthCheckResult:
        """Check realtime streaming system health."""
        try:
            services = get_services()
            shared_memory_service = services.shared_memory
            producer = (
                shared_memory_service._producer if shared_memory_service else None
            )
            stream = shared_memory_service.stream if shared_memory_service else None
            if stream is None:
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.OFFLINE,
                    details="Shared memory streaming not available",
                )

            # System is ONLINE if shared memory is available, whether or not actively streaming
            if producer is None:
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.ONLINE,
                    details="Realtime streaming ready (not active)",
                )

            # Check if producer thread is running (it's a Thread subclass)
            is_running = producer.is_alive() and not producer._stop_event.is_set()

            if is_running:
                metrics = {
                    "target_fps": getattr(producer, "target_fps", 0),
                    "thread_alive": producer.is_alive(),
                    "stop_event_set": producer._stop_event.is_set(),
                    "frame_interval_us": getattr(producer, "frame_interval_us", 0),
                }

                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.ONLINE,
                    details=f"Realtime streaming active at {metrics['target_fps']} FPS target",
                    metrics=metrics,
                )
            else:
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.OFFLINE,
                    details="Realtime producer not running",
                    metrics={
                        "thread_alive": producer.is_alive(),
                        "stop_event_set": producer._stop_event.is_set(),
                        "target_fps": getattr(producer, "target_fps", 0),
                    },
                )

        except ImportError as e:
            return HealthCheckResult(
                system_name=self.system_name,
                status=HealthStatus.ERROR,
                details="Realtime streaming module import failed",
                error_message=str(e),
            )
        except Exception as e:
            return HealthCheckResult(
                system_name=self.system_name,
                status=HealthStatus.ERROR,
                details="Realtime streaming health check exception",
                error_message=str(e),
            )


class SystemHealthMonitor:
    """Centralized health monitoring for all ISI Control System components."""

    def __init__(self, cache_duration: float = 5.0, backend_instance=None):
        """
        Initialize health monitor.

        Args:
            cache_duration: How long to cache health check results (seconds)
            backend_instance: Backend instance for sending log messages to frontend
        """
        self.cache_duration = cache_duration
        self.backend_instance = backend_instance
        self._health_checkers: Dict[str, HealthChecker] = {}
        self._health_cache: Dict[str, HealthCheckResult] = {}
        self._lock = threading.RLock()

        # Register all system health checkers
        self._register_default_checkers()

    def _register_default_checkers(self):
        """Register health checkers for multi-channel architecture systems."""
        self._send_console_log(
            "Initializing multi-channel architecture health checkers..."
        )
        logger.info("Initializing multi-channel architecture health checkers...")

        # Hardware detection systems
        self._send_console_log("• Registering camera health checker...")
        logger.info("  • Registering camera health checker...")
        self.register_checker(CameraHealthChecker())

        self._send_console_log("• Registering display health checker...")
        logger.info("  • Registering display health checker...")
        self.register_checker(DisplayHealthChecker())

        self._send_console_log("• Registering parameter health checker...")
        logger.info("  • Registering parameter health checker...")
        self.register_checker(ParameterHealthChecker())

        # Multi-channel architecture systems
        self._send_console_log("• Registering shared memory health checker...")
        logger.info("  • Registering shared memory health checker...")
        self.register_checker(SharedMemoryHealthChecker())

        self._send_console_log("• Registering multi-channel IPC health checker...")
        logger.info("  • Registering multi-channel IPC health checker...")
        self.register_checker(MultiChannelIPCHealthChecker())

        self._send_console_log("• Registering realtime streaming health checker...")
        logger.info("  • Registering realtime streaming health checker...")
        self.register_checker(RealtimeStreamingHealthChecker())

        self._send_console_log("✓ All health checkers registered successfully")
        logger.info("All health checkers registered successfully")

    def _send_console_log(self, message: str, level: str = "info"):
        """Send a log message to the frontend console if backend instance is available."""
        if self.backend_instance and hasattr(self.backend_instance, "send_log_message"):
            self.backend_instance.send_log_message(message, level)

    def register_checker(self, checker: HealthChecker):
        """Register a health checker for a system."""
        with self._lock:
            self._health_checkers[checker.system_name] = checker
            logger.info(f"Registered health checker for {checker.system_name}")

    def check_system_health(
        self, system_name: str, use_cache: bool = True
    ) -> HealthCheckResult:
        """
        Check health of a specific system.

        Args:
            system_name: Name of system to check
            use_cache: Whether to use cached results if available

        Returns:
            Health check result for the system
        """
        with self._lock:
            # Check cache first if requested
            if use_cache and system_name in self._health_cache:
                cached_result = self._health_cache[system_name]
                if cached_result.age_seconds < self.cache_duration:
                    return cached_result

            # Perform fresh health check
            if system_name not in self._health_checkers:
                return HealthCheckResult(
                    system_name=system_name,
                    status=HealthStatus.UNKNOWN,
                    error_message=f"No health checker registered for {system_name}",
                )

            checker = self._health_checkers[system_name]
            result = checker.check_health()

            # Cache the result
            self._health_cache[system_name] = result

            return result

    def check_all_systems_health(
        self, use_cache: bool = True
    ) -> Dict[str, HealthCheckResult]:
        """
        Check health of all registered systems.

        Args:
            use_cache: Whether to use cached results if available

        Returns:
            Dictionary mapping system names to health check results
        """
        results = {}
        for system_name in self._health_checkers.keys():
            result = self.check_system_health(system_name, use_cache)
            results[system_name] = result

        return results

    def get_overall_health_status(self, use_cache: bool = True) -> HealthStatus:
        """
        Get overall health status across all systems.

        Args:
            use_cache: Whether to use cached results if available

        Returns:
            Overall health status (worst status among all systems)
        """
        all_results = self.check_all_systems_health(use_cache)

        if not all_results:
            return HealthStatus.UNKNOWN

        # Determine overall status (worst case)
        statuses = [result.status for result in all_results.values()]

        if HealthStatus.ERROR in statuses:
            return HealthStatus.ERROR
        elif HealthStatus.OFFLINE in statuses:
            return HealthStatus.OFFLINE
        elif HealthStatus.UNKNOWN in statuses:
            return HealthStatus.UNKNOWN
        else:
            return HealthStatus.ONLINE

    def get_health_summary(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get comprehensive health summary for all systems.

        Args:
            use_cache: Whether to use cached results if available

        Returns:
            Dictionary containing overall status and individual system results
        """
        all_results = self.check_all_systems_health(use_cache)
        overall_status = self.get_overall_health_status(use_cache)

        # Convert results to simple status strings for API compatibility
        simple_status = {}
        for system_name, result in all_results.items():
            simple_status[system_name] = result.status.value

        return {
            "overall_status": overall_status.value,
            "systems": simple_status,
            "detailed_results": {
                name: {
                    "status": result.status.value,
                    "details": result.details,
                    "error_message": result.error_message,
                    "metrics": result.metrics,
                    "timestamp": result.timestamp,
                    "age_seconds": result.age_seconds,
                }
                for name, result in all_results.items()
            },
            "healthy_systems": [
                name for name, result in all_results.items() if result.is_healthy
            ],
            "unhealthy_systems": [
                name for name, result in all_results.items() if not result.is_healthy
            ],
            "last_check_time": time.time(),
        }

    def clear_cache(self):
        """Clear all cached health check results."""
        with self._lock:
            self._health_cache.clear()
            logger.info("Health check cache cleared")


# Global health monitor instance
_health_monitor: Optional[SystemHealthMonitor] = None


def get_health_monitor() -> SystemHealthMonitor:
    raise RuntimeError(
        "SystemHealthMonitor is provided via ServiceRegistry; do not call get_health_monitor() directly"
    )


def reset_health_monitor():
    raise RuntimeError(
        "reset_health_monitor is unsupported; use dependency injection in tests"
    )
