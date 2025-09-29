"""
Centralized Startup Coordinator - Single Source of System Initialization

This module provides a centralized, coordinated approach to system startup that ensures:
1. Sequential health checks for all systems
2. Coordinated hardware detection after health verification
3. Single point of truth for system readiness
4. No conflicting concurrent initialization processes
5. Proper error handling and rollback capabilities
"""

import asyncio
import logging
import time
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class StartupPhase(Enum):
    """Phases of the startup sequence."""
    INITIALIZING = "initializing"
    HEALTH_CHECKS = "health_checks"
    HARDWARE_DETECTION = "hardware_detection"
    SYSTEM_READY = "system_ready"
    FAILED = "failed"


@dataclass
class StartupResult:
    """Result of startup coordination."""
    phase: StartupPhase
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class StartupCoordinator:
    """Centralized coordinator for all system initialization."""

    def __init__(self):
        self.current_phase = StartupPhase.INITIALIZING
        self.startup_results: Dict[str, Any] = {}
        self.hardware_info: Dict[str, List[str]] = {
            'cameras': [],
            'displays': []
        }
        self.health_results: Dict[str, Any] = {}
        self._startup_lock = asyncio.Lock()

    async def coordinate_startup(self, send_message_callback=None) -> StartupResult:
        """
        Coordinate the complete system startup sequence.

        Args:
            send_message_callback: Function to send status updates to frontend

        Returns:
            StartupResult indicating final startup status
        """
        async with self._startup_lock:
            try:
                logger.info("Starting coordinated system initialization...")
                self.current_phase = StartupPhase.INITIALIZING

                if send_message_callback:
                    send_message_callback({
                        "type": "startup_status",
                        "phase": self.current_phase.value,
                        "message": "Initializing system startup..."
                    })

                # Phase 1: Health Checks
                result = await self._phase_1_health_checks(send_message_callback)
                if not result.success:
                    return result

                # Phase 2: Hardware Detection
                result = await self._phase_2_hardware_detection(send_message_callback)
                if not result.success:
                    return result

                # Phase 3: System Ready
                result = await self._phase_3_system_ready(send_message_callback)
                return result

            except Exception as e:
                logger.error(f"Startup coordination failed: {e}")
                self.current_phase = StartupPhase.FAILED
                return StartupResult(
                    phase=StartupPhase.FAILED,
                    success=False,
                    message="System startup failed",
                    error=str(e)
                )

    async def _phase_1_health_checks(self, send_message_callback=None) -> StartupResult:
        """Phase 1: Coordinated health checks for all systems."""
        logger.info("Phase 1: Starting coordinated health checks...")
        self.current_phase = StartupPhase.HEALTH_CHECKS

        if send_message_callback:
            send_message_callback({
                "type": "startup_status",
                "phase": self.current_phase.value,
                "message": "Checking system health..."
            })

        try:
            # Import here to avoid circular imports
            from .health_monitor import get_health_monitor

            # Get health monitor instance
            health_monitor = get_health_monitor()

            # Perform coordinated health checks (no concurrent access)
            logger.info("Performing health checks for all systems...")
            health_results = health_monitor.check_all_systems_health(use_cache=False)

            self.health_results = health_results

            # Check if all systems are healthy
            failed_systems = []
            for system_name, result in health_results.items():
                if not result.is_healthy:
                    failed_systems.append(f"{system_name}: {result.status.value}")
                    if result.error_message:
                        failed_systems[-1] += f" ({result.error_message})"

            if failed_systems:
                error_msg = f"Health check failed for: {', '.join(failed_systems)}"
                logger.error(error_msg)

                if send_message_callback:
                    send_message_callback({
                        "type": "startup_status",
                        "phase": self.current_phase.value,
                        "message": error_msg,
                        "error": True
                    })

                self.current_phase = StartupPhase.FAILED
                return StartupResult(
                    phase=StartupPhase.FAILED,
                    success=False,
                    message="System health checks failed",
                    error=error_msg,
                    details={"failed_systems": failed_systems}
                )

            # All systems healthy
            healthy_systems = list(health_results.keys())
            success_msg = f"✓ All systems healthy: {', '.join(healthy_systems)}"
            logger.info(success_msg)

            if send_message_callback:
                send_message_callback({
                    "type": "startup_status",
                    "phase": self.current_phase.value,
                    "message": success_msg
                })

                # Immediately update system health status for header icons
                hardware_status = {}
                for system_name, result in health_results.items():
                    hardware_status[system_name] = result.status.value

                send_message_callback({
                    "type": "system_health",
                    "hardware_status": hardware_status
                })

            return StartupResult(
                phase=StartupPhase.HEALTH_CHECKS,
                success=True,
                message="Health checks completed successfully",
                details={"healthy_systems": healthy_systems}
            )

        except Exception as e:
            error_msg = f"Health check phase failed: {e}"
            logger.error(error_msg)
            self.current_phase = StartupPhase.FAILED
            return StartupResult(
                phase=StartupPhase.FAILED,
                success=False,
                message="Health check phase failed",
                error=error_msg
            )

    async def _phase_2_hardware_detection(self, send_message_callback=None) -> StartupResult:
        """Phase 2: Coordinated hardware detection after health checks pass."""
        logger.info("Phase 2: Starting coordinated hardware detection...")
        self.current_phase = StartupPhase.HARDWARE_DETECTION

        if send_message_callback:
            send_message_callback({
                "type": "startup_status",
                "phase": self.current_phase.value,
                "message": "Detecting hardware..."
            })

        try:
            # Import here to avoid circular imports
            from .camera_manager import handle_detect_cameras
            from .display_manager import handle_detect_displays

            detected_hardware = {}

            # Camera detection
            logger.info("Detecting cameras...")
            camera_result = handle_detect_cameras({})
            if camera_result.get("success"):
                cameras = camera_result.get("cameras", [])
                detected_hardware['cameras'] = cameras
                self.hardware_info['cameras'] = cameras
                logger.info(f"✓ Found {len(cameras)} camera(s): {', '.join(cameras)}")
            else:
                logger.warning("✗ Camera detection failed")
                detected_hardware['cameras'] = []

            # Display detection
            logger.info("Detecting displays...")
            display_result = handle_detect_displays({})
            if display_result.get("success"):
                displays = display_result.get("displays", [])
                display_names = [d.get("name", "Unknown") for d in displays]
                detected_hardware['displays'] = display_names
                self.hardware_info['displays'] = display_names
                logger.info(f"✓ Found {len(displays)} display(s): {', '.join(display_names)}")
            else:
                logger.warning("✗ Display detection failed")
                detected_hardware['displays'] = []

            # Update parameter manager with detected hardware
            from .parameter_manager import get_parameter_manager
            param_manager = get_parameter_manager()

            # Update camera hardware list and auto-select first camera
            if detected_hardware.get('cameras'):
                current_params = param_manager.load_parameters()
                camera_updates = {'available_cameras': detected_hardware['cameras']}

                # Auto-select first camera if none selected
                auto_selected = False
                target_camera_name = current_params.camera.selected_camera
                if not current_params.camera.selected_camera:
                    target_camera_name = detected_hardware['cameras'][0]
                    camera_updates['selected_camera'] = target_camera_name
                    auto_selected = True
                    logger.info(f"Auto-selected first camera: {target_camera_name}")

                # Get camera capabilities for selected camera (whether auto-selected or already selected)
                if target_camera_name in detected_hardware['cameras']:
                    try:
                        from .camera_manager import camera_manager
                        # Find camera info from already detected cameras
                        cameras = camera_manager.detected_cameras
                        target_camera = None
                        for cam in cameras:
                            if cam.name == target_camera_name and cam.is_available:
                                target_camera = cam
                                break

                        if target_camera and target_camera.properties:
                            # Use capabilities from the detection phase (already captured)
                            props = target_camera.properties
                            capabilities_updates = {
                                'camera_fps': int(props.get('fps', -1)) if props.get('fps', 0) > 0 else -1,
                                'camera_width_px': props.get('width', -1),
                                'camera_height_px': props.get('height', -1)
                            }
                            camera_updates.update(capabilities_updates)
                            action = "Auto-detected" if auto_selected else "Updated"
                            logger.info(f"{action} camera capabilities from detection: {props}")
                        else:
                            logger.warning(f"Failed to get capabilities for camera {target_camera_name} from detection")
                    except Exception as e:
                        logger.error(f"Error getting camera capabilities: {e}")

                param_manager.update_camera_parameters(camera_updates)

            # Update display hardware list and auto-select first display
            if detected_hardware.get('displays'):
                current_params = param_manager.load_parameters()
                display_updates = {'available_displays': detected_hardware['displays']}

                # Auto-select display if none selected (prefer secondary/external displays for stimulus)
                auto_selected_display = False
                target_display_name = current_params.monitor.selected_display
                if not current_params.monitor.selected_display:
                    # Get full display objects to check primary/secondary status
                    from .display_manager import display_manager
                    available_displays = display_manager.displays

                    # Try to find a secondary (non-primary) display first
                    secondary_display = next((d for d in available_displays if not d.is_primary and d.is_available), None)
                    if secondary_display:
                        target_display_name = secondary_display.name
                        logger.info(f"Auto-selected secondary display for stimulus: {target_display_name}")
                    else:
                        # Fall back to primary display if no secondary available
                        primary_display = next((d for d in available_displays if d.is_primary and d.is_available), None)
                        if primary_display:
                            target_display_name = primary_display.name
                            logger.info(f"Auto-selected primary display (no secondary available): {target_display_name}")
                        else:
                            # Ultimate fallback to first in list
                            target_display_name = detected_hardware['displays'][0]
                            logger.info(f"Auto-selected first available display: {target_display_name}")

                    display_updates['selected_display'] = target_display_name
                    auto_selected_display = True

                # Get display capabilities for selected display (whether auto-selected or already selected)
                if target_display_name in detected_hardware['displays']:
                    try:
                        from .display_manager import display_manager
                        # Find display info from already detected displays
                        displays = display_manager.displays
                        target_display = None
                        for display in displays:
                            if display.name == target_display_name and display.is_available:
                                target_display = display
                                break

                        if target_display:
                            # Use capabilities from the detection phase (already captured)
                            capabilities_updates = {
                                'monitor_fps': int(target_display.refresh_rate) if target_display.refresh_rate > 0 else -1,
                                'monitor_width_px': target_display.width,
                                'monitor_height_px': target_display.height
                            }
                            display_updates.update(capabilities_updates)
                            action = "Auto-detected" if auto_selected_display else "Updated"
                            logger.info(f"{action} display capabilities from detection: {target_display.width}x{target_display.height} @ {target_display.refresh_rate}Hz")
                        else:
                            logger.warning(f"Failed to get capabilities for display {target_display_name} from detection")
                    except Exception as e:
                        logger.error(f"Error getting display capabilities: {e}")

                param_manager.update_monitor_parameters(display_updates)

            # Send parameter update notification to frontend
            if send_message_callback:
                try:
                    all_params = param_manager.get_all_parameters()
                    send_message_callback({
                        "type": "parameters_updated",
                        "parameters": all_params
                    })
                except Exception as e:
                    logger.warning(f"Failed to send parameter update: {e}")

            # Send startup status update
            if send_message_callback:
                hardware_summary = []
                if detected_hardware.get('cameras'):
                    hardware_summary.append(f"{len(detected_hardware['cameras'])} camera(s)")
                if detected_hardware.get('displays'):
                    hardware_summary.append(f"{len(detected_hardware['displays'])} display(s)")

                send_message_callback({
                    "type": "startup_status",
                    "phase": self.current_phase.value,
                    "message": f"✓ Hardware detected: {', '.join(hardware_summary)}"
                })

            return StartupResult(
                phase=StartupPhase.HARDWARE_DETECTION,
                success=True,
                message="Hardware detection completed successfully",
                details=detected_hardware
            )

        except Exception as e:
            error_msg = f"Hardware detection phase failed: {e}"
            logger.error(error_msg)
            self.current_phase = StartupPhase.FAILED
            return StartupResult(
                phase=StartupPhase.FAILED,
                success=False,
                message="Hardware detection phase failed",
                error=error_msg
            )

    async def _phase_3_system_ready(self, send_message_callback=None) -> StartupResult:
        """Phase 3: Declare system ready after all checks pass."""
        logger.info("Phase 3: System initialization complete")
        self.current_phase = StartupPhase.SYSTEM_READY

        ready_message = "Backend system: Online - All systems operational!"
        logger.info(ready_message)

        if send_message_callback:
            send_message_callback({
                "type": "log_message",
                "message": ready_message,
                "level": "info"
            })

            send_message_callback({
                "type": "startup_status",
                "phase": self.current_phase.value,
                "message": "System ready for experiments"
            })

        return StartupResult(
            phase=StartupPhase.SYSTEM_READY,
            success=True,
            message="System startup completed successfully",
            details={
                "hardware": self.hardware_info,
                "health": {name: result.status.value for name, result in self.health_results.items()}
            }
        )

    def is_ready(self) -> bool:
        """Check if system is fully ready for operations."""
        return self.current_phase == StartupPhase.SYSTEM_READY

    def get_startup_status(self) -> Dict[str, Any]:
        """Get current startup status information."""
        return {
            "phase": self.current_phase.value,
            "is_ready": self.is_ready(),
            "hardware": self.hardware_info,
            "health": {name: result.status.value for name, result in self.health_results.items()} if self.health_results else {}
        }


# Global startup coordinator instance
_startup_coordinator: Optional[StartupCoordinator] = None


def get_startup_coordinator() -> StartupCoordinator:
    """Get the global startup coordinator instance."""
    global _startup_coordinator
    if _startup_coordinator is None:
        _startup_coordinator = StartupCoordinator()
    return _startup_coordinator