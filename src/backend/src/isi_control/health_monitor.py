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

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Standardized health status values."""
    ONLINE = "online"      # System is fully operational
    OFFLINE = "offline"    # System is not available but not in error state
    ERROR = "error"        # System encountered an error during health check
    UNKNOWN = "unknown"    # Health status has not been determined yet


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
                error_message=str(e)
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
            logger.info(f"Camera health check: {len(available_cameras)} camera(s) available")

            if len(available_cameras) > 0:
                camera_names = [cam.name for cam in available_cameras]
                logger.info(f"Camera health check: Available cameras: {', '.join(camera_names)}")
                logger.info("Camera health check: ✓ ONLINE")
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.ONLINE,
                    details=f"{len(available_cameras)} camera(s) available",
                    metrics={
                        "total_cameras": len(cameras),
                        "available_cameras": len(available_cameras),
                        "camera_names": camera_names
                    }
                )
            elif len(cameras) > 0:
                logger.warning("Camera health check: ○ OFFLINE - Cameras detected but none available")
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.OFFLINE,
                    details="Cameras detected but none available",
                    metrics={
                        "total_cameras": len(cameras),
                        "available_cameras": 0
                    }
                )
            else:
                logger.warning("Camera health check: ○ OFFLINE - No cameras detected")
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.OFFLINE,
                    details="No cameras detected"
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
                if hasattr(d, 'is_primary'):
                    # Object type (DisplayInfo)
                    if d.is_primary:
                        primary_displays.append(d)
                    display_info.append({
                        'name': getattr(d, 'name', 'Unknown'),
                        'width': getattr(d, 'width', 0),
                        'height': getattr(d, 'height', 0),
                        'is_primary': getattr(d, 'is_primary', False)
                    })
                elif isinstance(d, dict):
                    # Dict type
                    if d.get('is_primary', False):
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
                    "display_info": display_info
                }
            )
        else:
            return HealthCheckResult(
                system_name=self.system_name,
                status=HealthStatus.OFFLINE,
                details="No displays detected"
            )


class StimulusHealthChecker(BaseHealthChecker):
    """Health checker for stimulus system."""

    def __init__(self):
        super().__init__("stimulus")

    def _perform_health_check(self) -> HealthCheckResult:
        import signal
        import threading
        from .stimulus_manager import get_stimulus_generator

        # Set up a timeout mechanism
        result_container = [None]
        error_container = [None]

        def health_check_with_timeout():
            try:
                generator = get_stimulus_generator()

                # Verify stimulus generator is functional
                if generator and generator.stimulus_params and generator.spatial_config:
                    # Test basic functionality by getting dataset info
                    dataset_info = generator.get_dataset_info("LR", 1)
                    if "error" not in dataset_info:
                        result_container[0] = HealthCheckResult(
                            system_name=self.system_name,
                            status=HealthStatus.ONLINE,
                            details="Stimulus generator operational",
                            metrics={
                                "stimulus_params": generator.stimulus_params.__dict__,
                                "spatial_config": generator.spatial_config.__dict__,
                                "test_dataset_frames": dataset_info.get("total_frames", 0)
                            }
                        )
                    else:
                        result_container[0] = HealthCheckResult(
                            system_name=self.system_name,
                            status=HealthStatus.ERROR,
                            details="Stimulus generator test failed",
                            error_message=dataset_info.get("error", "Unknown error")
                        )
                else:
                    result_container[0] = HealthCheckResult(
                        system_name=self.system_name,
                        status=HealthStatus.OFFLINE,
                        details="Stimulus generator not properly initialized"
                    )
            except Exception as e:
                error_container[0] = str(e)

        # Run health check in a thread with timeout
        thread = threading.Thread(target=health_check_with_timeout)
        thread.daemon = True
        thread.start()
        thread.join(timeout=5.0)  # 5 second timeout

        if thread.is_alive():
            # Thread is still running - timeout occurred
            return HealthCheckResult(
                system_name=self.system_name,
                status=HealthStatus.ERROR,
                details="Stimulus health check timed out",
                error_message="Health check exceeded 5 second timeout"
            )
        elif error_container[0]:
            return HealthCheckResult(
                system_name=self.system_name,
                status=HealthStatus.ERROR,
                details="Stimulus generator test exception",
                error_message=error_container[0]
            )
        elif result_container[0]:
            return result_container[0]
        else:
            return HealthCheckResult(
                system_name=self.system_name,
                status=HealthStatus.ERROR,
                details="Unknown stimulus health check failure"
            )


class ParameterHealthChecker(BaseHealthChecker):
    """Health checker for parameter manager system."""

    def __init__(self):
        super().__init__("parameters")

    def _perform_health_check(self) -> HealthCheckResult:
        from .parameter_manager import get_parameter_manager

        param_manager = get_parameter_manager()

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
                        "parameter_groups": list(param_info.get("parameter_groups", {}).keys()),
                        "config_file_exists": param_manager.config_file.exists(),
                        "current_session_name": getattr(current_params.session, 'session_name', 'Unknown')
                    }
                )
            else:
                return HealthCheckResult(
                    system_name=self.system_name,
                    status=HealthStatus.ERROR,
                    details="Parameter manager functionality test failed"
                )
        except Exception as e:
            return HealthCheckResult(
                system_name=self.system_name,
                status=HealthStatus.ERROR,
                details="Parameter manager test exception",
                error_message=str(e)
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
        """Register health checkers for all standard systems."""
        self._send_console_log("Initializing system health checkers...")
        logger.info("Initializing system health checkers...")

        self._send_console_log("• Registering camera health checker...")
        logger.info("  • Registering camera health checker...")
        self.register_checker(CameraHealthChecker())

        self._send_console_log("• Registering display health checker...")
        logger.info("  • Registering display health checker...")
        self.register_checker(DisplayHealthChecker())

        self._send_console_log("• Registering stimulus health checker...")
        logger.info("  • Registering stimulus health checker...")
        self.register_checker(StimulusHealthChecker())

        self._send_console_log("• Registering parameter health checker...")
        logger.info("  • Registering parameter health checker...")
        self.register_checker(ParameterHealthChecker())

        self._send_console_log("✓ All health checkers registered successfully")
        logger.info("All health checkers registered successfully")

    def _send_console_log(self, message: str, level: str = "info"):
        """Send a log message to the frontend console if backend instance is available."""
        if self.backend_instance and hasattr(self.backend_instance, 'send_log_message'):
            self.backend_instance.send_log_message(message, level)

    def register_checker(self, checker: HealthChecker):
        """Register a health checker for a system."""
        with self._lock:
            self._health_checkers[checker.system_name] = checker
            logger.info(f"Registered health checker for {checker.system_name}")

    def check_system_health(self, system_name: str, use_cache: bool = True) -> HealthCheckResult:
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
                    error_message=f"No health checker registered for {system_name}"
                )

            checker = self._health_checkers[system_name]
            result = checker.check_health()

            # Cache the result
            self._health_cache[system_name] = result

            return result

    def check_all_systems_health(self, use_cache: bool = True) -> Dict[str, HealthCheckResult]:
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
            "detailed_results": {name: {
                "status": result.status.value,
                "details": result.details,
                "error_message": result.error_message,
                "metrics": result.metrics,
                "timestamp": result.timestamp,
                "age_seconds": result.age_seconds
            } for name, result in all_results.items()},
            "healthy_systems": [name for name, result in all_results.items() if result.is_healthy],
            "unhealthy_systems": [name for name, result in all_results.items() if not result.is_healthy],
            "last_check_time": time.time()
        }

    def clear_cache(self):
        """Clear all cached health check results."""
        with self._lock:
            self._health_cache.clear()
            logger.info("Health check cache cleared")


# Global health monitor instance
_health_monitor: Optional[SystemHealthMonitor] = None

def get_health_monitor() -> SystemHealthMonitor:
    """Get or create the global health monitor instance."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = SystemHealthMonitor()
    return _health_monitor

def reset_health_monitor():
    """Reset the global health monitor (mainly for testing)."""
    global _health_monitor
    _health_monitor = None