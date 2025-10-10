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
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from .service_locator import get_services
from .logging_utils import get_logger

logger = get_logger(__name__)


class SystemState(Enum):
    """
    Single source of truth for system state.
    Backend controls ALL state transitions. Frontend displays state directly.
    """

    INITIALIZING = "initializing"
    WAITING_FRONTEND = "waiting_frontend"
    IPC_READY = "ipc_ready"
    PARAMETERS_LOADED = "parameters_loaded"
    HARDWARE_DETECTED = "hardware_detected"
    SYSTEMS_VALIDATED = "systems_validated"
    READY = "ready"
    ERROR = "error"

    def get_display_text(self) -> str:
        """Get UI-ready display text for this state."""
        display_texts = {
            SystemState.INITIALIZING: "Initializing backend systems...",
            SystemState.WAITING_FRONTEND: "Waiting for frontend connection...",
            SystemState.IPC_READY: "Communication channels established",
            SystemState.PARAMETERS_LOADED: "Parameters loaded successfully",
            SystemState.HARDWARE_DETECTED: "Hardware detected and configured",
            SystemState.SYSTEMS_VALIDATED: "All systems validated",
            SystemState.READY: "System ready for experiments",
            SystemState.ERROR: "System initialization failed",
        }
        return display_texts.get(self, self.value)


@dataclass
class StartupResult:
    """Result of startup coordination."""

    state: SystemState
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class StartupCoordinator:
    """
    Centralized coordinator for all system initialization.

    Architecture principles:
    1. Single source of truth - only this class tracks system state
    2. Backend controls all state transitions
    3. Frontend displays state directly without interpretation
    4. Proper channel handshake before any coordination messages
    5. All business logic in backend, frontend is pure view layer
    """

    def __init__(self):
        self.current_state = SystemState.INITIALIZING
        self.startup_results: Dict[str, Any] = {}
        self.hardware_info: Dict[str, List[str]] = {"cameras": [], "displays": []}
        self.health_results: Dict[str, Any] = {}
        self._startup_lock = asyncio.Lock()
        self.frontend_ready = False  # Track frontend connection state
        self.backend_instance = None  # Reference to backend for IPC
        self.hardware_detected = False  # Flag to prevent redundant hardware detection
        self.hardware_detection_timestamp: float = 0.0  # When hardware was last detected

    def broadcast_state(
        self,
        state: SystemState,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        """
        Broadcast state change to frontend via proper channel.

        This is the ONLY method that sends state updates.
        Frontend displays this state directly without interpretation.
        """
        self.current_state = state

        message = {
            "type": "system_state",
            "state": state.value,
            "display_text": state.get_display_text(),
            "is_ready": state == SystemState.READY,
            "is_error": state == SystemState.ERROR,
            "timestamp": time.time(),
        }

        if details:
            message["details"] = details

        if error:
            message["error"] = error

        # Use CONTROL channel during early startup, SYNC channel after frontend ready
        ipc = get_services().ipc

        if self.frontend_ready and ipc:
            # Use SYNC channel for state broadcasts after handshake complete
            success = ipc.send_sync_message(message)
            if success:
                logger.info(f"State broadcast via SYNC: {state.value}")
            else:
                logger.warning(f"Failed to broadcast state via SYNC: {state.value}")
        elif ipc:
            # Use CONTROL channel during early startup before frontend connects
            success = ipc.send_control_message(message)
            if success:
                logger.info(f"State broadcast via CONTROL: {state.value}")
            else:
                logger.warning(f"Failed to broadcast state via CONTROL: {state.value}")

    async def wait_for_frontend_ready(self, timeout: float = 10.0) -> bool:
        """
        Wait for frontend to establish ZeroMQ connections and send ready signal.

        This implements the proper handshake protocol:
        1. Backend initializes ZeroMQ sockets
        2. Backend sends explicit "zeromq_ready" message with connection details
        3. Frontend receives details and connects to ZeroMQ
        4. Frontend sends "frontend_ready" command via CONTROL channel (stdin)
        5. Backend receives confirmation and proceeds
        """
        logger.info("Waiting for frontend to establish connections...")

        # Send explicit ZeroMQ connection details to frontend
        ipc = get_services().ipc
        zeromq_ready_message = {
            "type": "zeromq_ready",
            "health_port": 5555,
            "sync_port": 5558,
            "timestamp": time.time(),
        }
        ipc.send_control_message(zeromq_ready_message)
        logger.info("Sent ZeroMQ connection details to frontend")

        # Then broadcast waiting state
        self.broadcast_state(SystemState.WAITING_FRONTEND)

        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.frontend_ready:
                logger.info("Frontend connection confirmed")
                return True
            await asyncio.sleep(0.1)

        logger.error("Frontend connection timeout")
        return False

    async def coordinate_startup(self, backend_instance=None) -> StartupResult:
        """
        Coordinate the complete system startup sequence with proper state machine.
        """
        async with self._startup_lock:
            services = get_services()
            try:
                logger.info("Starting coordinated system initialization...")
                self.backend_instance = backend_instance
                self.broadcast_state(SystemState.INITIALIZING)

                # Phase 1: Initialize IPC channels
                result = await self._initialize_ipc(backend_instance)
                if not result.success:
                    self.broadcast_state(SystemState.ERROR, error=result.error)
                    return result

                # Phase 2: Wait for frontend connection (handshake)
                frontend_ready = await self.wait_for_frontend_ready(timeout=15.0)
                if not frontend_ready:
                    error_msg = "Frontend failed to establish connection"
                    logger.error(error_msg)
                    self.broadcast_state(SystemState.ERROR, error=error_msg)
                    return StartupResult(
                        state=SystemState.ERROR,
                        success=False,
                        message="Frontend connection failed",
                        error=error_msg,
                    )

                self.broadcast_state(SystemState.IPC_READY)

                # Phase 3: Load parameters
                result = await self._load_parameters()
                if not result.success:
                    self.broadcast_state(SystemState.ERROR, error=result.error)
                    return result

                self.broadcast_state(SystemState.PARAMETERS_LOADED)

                # Phase 4: Detect and configure hardware
                result = await self._detect_hardware()
                if not result.success:
                    self.broadcast_state(SystemState.ERROR, error=result.error)
                    return result

                self.broadcast_state(
                    SystemState.HARDWARE_DETECTED, details=result.details
                )

                # Phase 5: Validate all systems
                result = await self._validate_systems()
                if not result.success:
                    self.broadcast_state(SystemState.ERROR, error=result.error)
                    return result

                self.broadcast_state(SystemState.SYSTEMS_VALIDATED)

                logger.info("System initialization complete - All systems operational")
                self.broadcast_state(SystemState.READY)

                return StartupResult(
                    state=SystemState.READY,
                    success=True,
                    message="System startup completed successfully",
                    details={
                        "hardware": self.hardware_info,
                        "health": {
                            name: result.status.value
                            for name, result in self.health_results.items()
                        },
                    },
                )

            except Exception as error:
                logger.error("Startup coordination failed: %s", error)
                self.broadcast_state(SystemState.ERROR, error=str(error))
                return StartupResult(
                    state=SystemState.ERROR,
                    success=False,
                    message="System startup failed",
                    error=str(error),
                )

    async def _initialize_ipc(self, backend_instance=None) -> StartupResult:
        """Initialize multi-channel IPC system (ZeroMQ sockets)."""
        logger.info("Initializing multi-channel IPC system...")

        try:
            # Initialize multi-channel IPC system
            ipc = get_services().ipc

            if ipc is None:
                error_msg = "Failed to initialize multi-channel IPC system"
                logger.error(error_msg)
                return StartupResult(
                    state=SystemState.ERROR,
                    success=False,
                    message="Multi-channel IPC initialization failed",
                    error=error_msg,
                )

            # Initialize shared memory system
            stream = get_services().shared_memory

            if stream is None:
                error_msg = "Failed to initialize shared memory streaming system"
                logger.error(error_msg)
                return StartupResult(
                    state=SystemState.ERROR,
                    success=False,
                    message="Shared memory system initialization failed",
                    error=error_msg,
                )

            # Store references in backend instance if provided
            if backend_instance:
                backend_instance.multi_channel_ipc = ipc
                backend_instance.shared_memory_stream = stream

                # Start health monitoring on the multi-channel system
                ipc.start_health_monitoring(
                    callback=None, interval_sec=0.1
                )

            logger.info("✓ Multi-channel IPC system initialized successfully")

            return StartupResult(
                state=SystemState.INITIALIZING,
                success=True,
                message="Multi-channel IPC system initialized successfully",
            )

        except Exception as e:
            error_msg = f"Multi-channel IPC initialization failed: {e}"
            logger.error(error_msg)
            return StartupResult(
                state=SystemState.ERROR,
                success=False,
                message="Multi-channel IPC initialization failed",
                error=error_msg,
            )

    async def _load_parameters(self) -> StartupResult:
        """Load and validate parameter system."""
        logger.info("Loading parameter system...")

        try:
            health_monitor = get_services().health_monitor

            # Check parameter system health
            result = health_monitor.check_system_health("parameters")
            logger.info(f"Parameter system health: {result.status.value}")

            if not result.is_healthy:
                error_msg = f"Parameter system check failed: {result.status.value}"
                if result.error_message:
                    error_msg += f" ({result.error_message})"
                logger.error(error_msg)
                return StartupResult(
                    state=SystemState.ERROR,
                    success=False,
                    message="Parameter system validation failed",
                    error=error_msg,
                )

            logger.info("✓ Parameter system loaded successfully")
            return StartupResult(
                state=SystemState.PARAMETERS_LOADED,
                success=True,
                message="Parameter system loaded successfully",
            )

        except Exception as e:
            error_msg = f"Parameter system initialization failed: {e}"
            logger.error(error_msg)
            return StartupResult(
                state=SystemState.ERROR,
                success=False,
                message="Parameter system initialization failed",
                error=error_msg,
            )

    async def _detect_hardware(self) -> StartupResult:
        """Detect and configure hardware (cameras and displays)."""
        logger.info("Detecting hardware...")

        try:
            from .camera_manager import handle_detect_cameras, camera_manager
            from .display_manager import handle_detect_displays

            detected_hardware = {}

            # Camera detection
            logger.info("Detecting cameras...")
            camera_result = handle_detect_cameras({"force": True})
            if camera_result.get("success"):
                cameras = camera_result.get("cameras", [])
                detected_hardware["cameras"] = cameras
                self.hardware_info["cameras"] = cameras
                logger.info(f"✓ Found {len(cameras)} camera(s)")
            else:
                logger.warning("✗ Camera detection failed")
                detected_hardware["cameras"] = []

            # Display detection (auto-saves display parameters)
            logger.info("Detecting displays...")
            display_result = handle_detect_displays({"force": True})
            if display_result.get("success"):
                displays = display_result.get("displays", [])
                display_names = [d.get("name", "Unknown") for d in displays]
                detected_hardware["displays"] = display_names
                self.hardware_info["displays"] = display_names
                logger.info(f"✓ Found {len(displays)} display(s)")
            else:
                logger.warning("✗ Display detection failed")
                detected_hardware["displays"] = []

            # Configure camera parameters
            # Note: This requires a second save because display_manager already saved display params
            # Future optimization: Make display_manager skip auto-save during startup
            param_manager = get_services().parameter_manager
            current_params = param_manager.load_parameters()

            if detected_hardware.get("cameras"):
                camera_updates = {"available_cameras": detected_hardware["cameras"]}

                if not current_params.camera.selected_camera:
                    camera_updates["selected_camera"] = detected_hardware["cameras"][0]

                    # Get capabilities for auto-selected camera
                    target_camera = next(
                        (
                            cam
                            for cam in camera_manager.detected_cameras
                            if cam.name == camera_updates["selected_camera"]
                            and cam.is_available
                        ),
                        None,
                    )
                    if target_camera and target_camera.properties:
                        props = target_camera.properties
                        camera_updates.update(
                            {
                                "camera_fps": (
                                    int(props.get("fps", -1))
                                    if props.get("fps", 0) > 0
                                    else -1
                                ),
                                "camera_width_px": props.get("width", -1),
                                "camera_height_px": props.get("height", -1),
                            }
                        )

                # Save camera parameters (second save after display auto-save)
                param_manager.update_parameter_group("camera", camera_updates)
                logger.info("Camera parameters saved")

            # Broadcast parameter update via SYNC channel
            ipc = get_services().ipc
            all_params = param_manager.get_all_parameters()
            ipc.send_sync_message(
                {
                    "type": "parameters_snapshot",
                    "timestamp": time.time(),
                    "parameters": all_params,
                    "parameter_config": get_services()
                    .parameter_manager.get_parameter_info()
                    .get("parameter_config", {}),
                }
            )

            # Mark hardware as detected to prevent redundant detection in health checks
            self.hardware_detected = True
            self.hardware_detection_timestamp = time.time()

            logger.info("✓ Hardware detection and configuration complete")
            return StartupResult(
                state=SystemState.HARDWARE_DETECTED,
                success=True,
                message="Hardware detection completed successfully",
                details=detected_hardware,
            )

        except Exception as e:
            error_msg = f"Hardware detection failed: {e}"
            logger.error(error_msg)
            return StartupResult(
                state=SystemState.ERROR,
                success=False,
                message="Hardware detection failed",
                error=error_msg,
            )

    async def _validate_systems(self) -> StartupResult:
        """Validate all systems are healthy and ready."""
        logger.info("Validating all systems...")

        try:
            health_monitor = get_services().health_monitor

            # Check all critical systems
            systems_to_check = [
                "parameters",
                "display",
                "camera",
                "shared_memory",
                "multi_channel_ipc",
                "realtime_streaming",
            ]
            failed_systems = []

            for system_name in systems_to_check:
                try:
                    result = health_monitor.check_system_health(system_name)
                    self.health_results[system_name] = result
                    logger.info(
                        f"System validation - {system_name}: {result.status.value}"
                    )

                    if not result.is_healthy:
                        failed_systems.append(f"{system_name}: {result.status.value}")
                        if result.error_message:
                            failed_systems[-1] += f" ({result.error_message})"
                except Exception as e:
                    logger.error(f"Validation failed for {system_name}: {e}")
                    failed_systems.append(f"{system_name}: {str(e)}")

            if failed_systems:
                error_msg = f"System validation failed: {', '.join(failed_systems)}"
                logger.error(error_msg)
                return StartupResult(
                    state=SystemState.ERROR,
                    success=False,
                    message="System validation failed",
                    error=error_msg,
                )

            # Validate stimulus generator can be created
            try:
                stimulus_generator = get_services().stimulus_generator_provider()
                logger.info(
                    f"✓ Stimulus generator validated: {type(stimulus_generator).__name__}"
                )
            except Exception as e:
                error_msg = f"Stimulus generator validation failed: {e}"
                logger.error(error_msg)
                return StartupResult(
                    state=SystemState.ERROR,
                    success=False,
                    message="Stimulus generator validation failed",
                    error=error_msg,
                )

            logger.info("✓ All systems validated successfully")
            return StartupResult(
                state=SystemState.SYSTEMS_VALIDATED,
                success=True,
                message="All systems validated successfully",
            )

        except Exception as e:
            error_msg = f"System validation failed: {e}"
            logger.error(error_msg)
            return StartupResult(
                state=SystemState.ERROR,
                success=False,
                message="System validation failed",
                error=error_msg,
            )

    def is_ready(self) -> bool:
        """Check if system is fully ready for operations."""
        return self.current_state == SystemState.READY

    def get_startup_status(self) -> Dict[str, Any]:
        """Get current startup status information."""
        return {
            "state": self.current_state.value,
            "is_ready": self.is_ready(),
            "hardware": self.hardware_info,
            "health": (
                {
                    name: result.status.value
                    for name, result in self.health_results.items()
                }
                if self.health_results
                else {}
            ),
        }
