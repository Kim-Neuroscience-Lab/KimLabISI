"""Acquisition sequence orchestrator for ISI experiments.

Refactored from isi_control/acquisition_manager.py with KISS approach:
- Constructor injection: all dependencies passed as parameters
- No service_locator imports
- No global singletons
- Explicit configuration
"""

import time
import threading
from typing import Optional, Dict, Any, List, Literal, TYPE_CHECKING
from enum import Enum
import logging

import numpy as np

from .sync_tracker import TimestampSynchronizationTracker
from .state import AcquisitionStateCoordinator
from .modes import (
    PreviewModeController,
    RecordModeController,
)

if TYPE_CHECKING:
    from .modes import PlaybackModeController

logger = logging.getLogger(__name__)


class AcquisitionPhase(Enum):
    """Phases of the acquisition sequence."""

    IDLE = "idle"
    INITIAL_BASELINE = "initial_baseline"
    STIMULUS = "stimulus"
    BETWEEN_TRIALS = "between_trials"
    FINAL_BASELINE = "final_baseline"
    COMPLETE = "complete"


class AcquisitionManager:
    """Orchestrates the acquisition sequence timing and phase transitions."""

    def __init__(
        self,
        ipc,  # MultiChannelIPC instance
        shared_memory,  # SharedMemoryService instance
        stimulus_generator,  # StimulusGenerator instance
        camera,  # CameraManager instance
        synchronization_tracker: Optional[TimestampSynchronizationTracker] = None,
        state_coordinator: Optional[AcquisitionStateCoordinator] = None,
        unified_stimulus=None,
        data_recorder=None,
        param_manager=None,
    ):
        """Initialize acquisition manager with injected dependencies.

        Args:
            ipc: IPC service for communication with frontend
            shared_memory: Shared memory service for frame data
            stimulus_generator: Stimulus generator for frame generation
            camera: Camera manager for frame acquisition
            synchronization_tracker: Optional timestamp synchronization tracker
            state_coordinator: Optional state coordinator
            unified_stimulus: Optional unified stimulus controller for both preview and record modes
            data_recorder: Optional data recorder
            param_manager: Optional parameter manager
        """
        # Injected dependencies
        self.ipc = ipc
        self.shared_memory = shared_memory
        self.stimulus_generator = stimulus_generator
        self.camera = camera
        self.param_manager = param_manager
        self.unified_stimulus = unified_stimulus

        self.is_running = False
        self.acquisition_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self._state_lock = threading.RLock()  # Thread-safe access to acquisition state

        # Acquisition state
        self.phase = AcquisitionPhase.IDLE
        self.current_direction_index = 0
        self.current_cycle = 0
        self.phase_start_time = 0.0
        self.acquisition_start_time = 0.0

        # Parameters (loaded from param_manager when acquisition starts)
        # CRITICAL: NO default values - Parameter Manager is Single Source of Truth
        # These MUST be loaded from param_manager before acquisition can start
        # See start_acquisition() method for parameter loading and validation
        self.baseline_sec: Optional[float] = None
        self.between_sec: Optional[float] = None
        self.cycles: Optional[int] = None
        self.directions: Optional[List[str]] = None
        self.camera_fps: Optional[float] = None
        self.target_mode: Literal["preview", "record", "playback"] = "preview"
        self.target_direction = "LR"
        self.target_frame_index = 0
        self.target_show_mask = False

        # Timestamp synchronization tracker (dependency injection)
        # IMPORTANT: Must be injected, not created here, to ensure single shared instance
        self.synchronization_tracker = synchronization_tracker

        # State coordinator (dependency injection)
        self.state_coordinator = state_coordinator

        # Data recorder (dependency injection)
        self.data_recorder = data_recorder

        # Mode controllers - inject dependencies
        self.preview_controller = PreviewModeController(
            state_coordinator=state_coordinator,
            shared_memory_service=shared_memory,
            stimulus_generator=stimulus_generator,
            ipc=ipc,
        )
        self.record_controller = RecordModeController(
            state_coordinator=state_coordinator,
            acquisition_orchestrator=self,
        )

        # Playback controller (injected from main.py to ensure single instance)
        self.playback_controller: Optional["PlaybackModeController"] = None

        # Subscribe to acquisition parameter changes
        if self.param_manager:
            self.param_manager.subscribe(
                "acquisition", self._handle_acquisition_params_changed
            )

    def _handle_acquisition_params_changed(
        self, group_name: str, updates: Dict[str, Any]
    ):
        """React to acquisition parameter changes.

        Args:
            group_name: Parameter group that changed ("acquisition")
            updates: Dictionary of updated parameters
        """
        logger.info(f"Acquisition parameters changed: {list(updates.keys())}")

        if self.is_running:
            logger.warning(
                "Acquisition parameters changed during active acquisition. "
                "Changes will apply to next acquisition start."
            )

    def set_mode(
        self,
        mode: Literal["preview", "record", "playback"],
        *,
        direction: Optional[str] = None,
        frame_index: Optional[int] = None,
        show_mask: Optional[bool] = None,
        param_manager=None,
    ) -> Dict[str, Any]:
        """Update acquisition mode via mode controllers."""

        if mode not in {"preview", "record", "playback"}:
            return {"success": False, "error": f"Unsupported mode: {mode}"}

        try:
            # Update target parameters
            if direction is not None:
                self.target_direction = direction
            if frame_index is not None:
                self.target_frame_index = frame_index
            if show_mask is not None:
                self.target_show_mask = show_mask

            # Stop acquisition if switching to preview/playback
            if mode in ("preview", "playback") and self.is_running:
                self.stop_acquisition()

            # CRITICAL: Deactivate previous mode to cleanup resources (close HDF5 files, etc.)
            if self.target_mode != mode:
                if self.target_mode == "playback" and self.playback_controller:
                    logger.info(
                        f"Deactivating playback mode before switching to {mode}"
                    )
                    self.playback_controller.deactivate()
                elif self.target_mode == "record" and self.record_controller:
                    logger.info(f"Deactivating record mode before switching to {mode}")
                    self.record_controller.deactivate()
                elif self.target_mode == "preview" and self.preview_controller:
                    logger.info(f"Deactivating preview mode before switching to {mode}")
                    self.preview_controller.deactivate()

            # Delegate to appropriate mode controller
            if mode == "preview":
                result = self.preview_controller.activate(
                    direction=self.target_direction,
                    frame_index=self.target_frame_index,
                    show_bar_mask=self.target_show_mask,
                )
            elif mode == "record":
                # Use injected param_manager or passed one
                pm = param_manager or self.param_manager
                result = self.record_controller.activate(
                    param_manager=pm,
                )
            else:  # playback
                if self.playback_controller is None:
                    return {
                        "success": False,
                        "error": "Playback controller not initialized",
                    }
                result = self.playback_controller.activate()

            if result.get("success"):
                self.target_mode = mode

            return result

        except Exception as exc:
            logger.error("Failed to set acquisition mode: %s", exc, exc_info=True)
            return {"success": False, "error": str(exc)}

    def start_acquisition(
        self, param_manager=None, record_data: bool = True
    ) -> Dict[str, Any]:
        """Start the acquisition sequence.

        Reads all parameters from param_manager (Single Source of Truth).

        Args:
            param_manager: Optional ParameterManager instance (uses self.param_manager if not provided)
            record_data: If True, initialize data recorder and save data to disk (record mode).
                        If False, run full sequence without saving (preview mode).

        Returns:
            Dict with success status and error message if failed
        """
        with self._state_lock:
            if self.is_running:
                return {"success": False, "error": "Acquisition already running"}

            # Defensive cleanup: ensure camera is streaming
            if not self.camera.is_streaming:
                logger.info(
                    "Starting camera acquisition for record mode (defensive startup)"
                )
                if not self.camera.start_acquisition():
                    return {"success": False, "error": "Failed to start camera"}

            # Validate required dependencies for record mode
            if not self.unified_stimulus:
                error_msg = (
                    "Unified stimulus controller is required for record mode. "
                    "This indicates a system initialization error - unified_stimulus "
                    "must be injected during backend setup."
                )
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Use injected param_manager or passed one
            pm = param_manager or self.param_manager
            if not pm:
                error_msg = (
                    "Parameter manager is required but not available. "
                    "This indicates a system initialization error - param_manager "
                    "must be injected during backend setup."
                )
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Load and validate REQUIRED acquisition parameters from param_manager
            # No defaults - experimental protocol must be explicit for scientific validity

            # Read acquisition parameters
            acquisition_params = pm.get_parameter_group("acquisition")
            if not acquisition_params:
                error_msg = (
                    "Acquisition parameters not found in param_manager. "
                    "Please configure acquisition parameters before starting acquisition."
                )
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            baseline_sec = acquisition_params.get("baseline_sec")
            if (
                baseline_sec is None
                or not isinstance(baseline_sec, (int, float))
                or baseline_sec < 0
            ):
                error_msg = (
                    "baseline_sec is required but not configured in param_manager. "
                    "Baseline duration must be explicitly specified for reproducible experiments. "
                    f"Please configure acquisition.baseline_sec in parameter manager. Received: {baseline_sec}"
                )
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
            self.baseline_sec = float(baseline_sec)

            between_sec = acquisition_params.get("between_sec")
            if (
                between_sec is None
                or not isinstance(between_sec, (int, float))
                or between_sec < 0
            ):
                error_msg = (
                    "between_sec is required but not configured in param_manager. "
                    "Inter-trial interval must be explicitly specified for reproducible experiments. "
                    f"Please configure acquisition.between_sec in parameter manager. Received: {between_sec}"
                )
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
            self.between_sec = float(between_sec)

            cycles = acquisition_params.get("cycles")
            if cycles is None or not isinstance(cycles, int) or cycles <= 0:
                error_msg = (
                    "cycles is required but not configured in param_manager. "
                    "Number of repetitions must be explicitly specified for reproducible experiments. "
                    f"Please configure acquisition.cycles in parameter manager. Received: {cycles}"
                )
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
            self.cycles = cycles

            directions = acquisition_params.get("directions")
            if (
                not directions
                or not isinstance(directions, list)
                or len(directions) == 0
            ):
                error_msg = (
                    "directions is required but not configured in param_manager. "
                    "Must specify list of sweep directions (e.g., ['LR', 'RL', 'TB', 'BT']). "
                    f"Please configure acquisition.directions in parameter manager. Received: {directions}"
                )
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Validate direction values
            valid_directions = {"LR", "RL", "TB", "BT"}
            invalid = [d for d in directions if d not in valid_directions]
            if invalid:
                error_msg = (
                    f"Invalid directions configured in param_manager: {invalid}. "
                    f"Must be one of {valid_directions}. "
                    f"Please configure acquisition.directions with valid values. Received: {directions}"
                )
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
            self.directions = directions

            # Read camera FPS from camera parameter group
            camera_params = pm.get_parameter_group("camera")
            if not camera_params:
                error_msg = (
                    "Camera parameters not found in param_manager. "
                    "Please configure camera parameters before starting acquisition."
                )
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            camera_fps_value = camera_params.get("camera_fps")
            if (
                camera_fps_value is None
                or not isinstance(camera_fps_value, (int, float))
                or camera_fps_value <= 0
            ):
                error_msg = (
                    "camera_fps is required but not configured in param_manager. "
                    "Camera FPS must be set to the actual frame rate of your camera hardware "
                    "for scientifically valid acquisition timing. "
                    f"Please configure camera.camera_fps in parameter manager. Received: {camera_fps_value}"
                )
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Type-safe assignment after validation
            self.camera_fps: float = float(camera_fps_value)

            # CRITICAL: Check if stimulus library is pre-generated
            # User MUST consciously generate and verify stimulus before acquisition
            # Auto-generation is NOT allowed - user must use Stimulus Generation viewport
            status = self.unified_stimulus.get_status()
            if not status.get("library_loaded"):
                error_msg = (
                    "Stimulus library must be pre-generated before acquisition. "
                    "Please go to Stimulus Generation viewport and generate the library."
                )
                logger.error(f"Acquisition start failed: {error_msg}")

                # Send error to frontend with redirect action
                if self.ipc:
                    self.ipc.send_sync_message(
                        {
                            "type": "acquisition_start_failed",
                            "reason": "stimulus_not_pre_generated",
                            "message": error_msg,
                            "action": "redirect_to_stimulus_generation",
                            "timestamp": time.time(),
                        }
                    )

                return {
                    "success": False,
                    "error": error_msg,
                    "reason": "stimulus_not_pre_generated",
                    "action": "redirect_to_stimulus_generation",
                }

            # Set mode based on record_data flag
            self.target_mode = "record" if record_data else "preview"
            mode_str = "record" if record_data else "preview"

            logger.info(
                f"Starting acquisition ({mode_str} mode): {self.cycles} cycles × {len(self.directions)} directions"
            )
            logger.info(f"Baseline: {self.baseline_sec}s, Between: {self.between_sec}s")
            logger.info(f"Unified stimulus mode: {self.camera_fps} camera fps")

            # Reset state
            self.is_running = True
            self.stop_event.clear()
            self.current_direction_index = 0
            self.current_cycle = 0
            self.acquisition_start_time = time.time()

        # Update state coordinator
        if self.state_coordinator:
            self.state_coordinator.set_acquisition_running(True)

        # Initialize data recorder with session metadata (ONLY if record_data=True)
        if record_data and self.data_recorder is None and pm:
            from .recorder import create_session_recorder

            # Build comprehensive session metadata from all parameter groups
            session_params = pm.get_parameter_group("session")
            session_metadata = {
                "session_name": session_params.get("session_name", "unnamed_session"),
                "animal_id": session_params.get("animal_id", ""),
                "animal_age": session_params.get("animal_age", ""),
                "timestamp": time.time(),
                "acquisition": acquisition_params,
                "camera": camera_params,
                "monitor": pm.get_parameter_group("monitor"),
                "stimulus": pm.get_parameter_group("stimulus"),
                "timestamp_info": {
                    "camera_timestamp_source": "to_be_determined",  # Set by camera manager
                    "stimulus_timestamp_source": "unified_stimulus_independent",
                    "synchronization_method": "independent_threads_no_triggering",
                    "display_vsync": "monitor_refresh_rate_vsync",
                    "display_latency_note": "Consistent ~8-16ms display lag (not compensated in data)",
                    "timing_architecture": {
                        "camera_fps": "actual_hardware_fps",  # Filled in from params
                        "monitor_fps": "monitor_refresh_rate",  # Filled in from params
                        "stimulus_frame_count_based_on": "camera_fps",
                        "display_vsync_rate": "monitor_fps",
                        "frame_index_is_ground_truth": True,
                        "vsync_explanation": (
                            "Display uses monitor VSync for smooth rendering. "
                            "Camera captures at independent rate. "
                            "Frame index provides 1:1 correspondence between camera and stimulus."
                        ),
                    },
                },
            }

            self.data_recorder = create_session_recorder(
                session_name=session_metadata["session_name"],
                metadata=session_metadata,
            )
            logger.info(f"Data recorder created: {self.data_recorder.session_path}")

            # Wire data recorder to camera manager so frames get saved
            self.camera.set_data_recorder(self.data_recorder)
            logger.info("Data recorder wired to camera manager")

        # Clear synchronization history and enable continuous tracking
        # Timestamp validation will filter non-stimulus synchronization data
        if self.synchronization_tracker:
            self.synchronization_tracker.clear()
            self.synchronization_tracker.enable()

        # Start acquisition thread
        self.acquisition_thread = threading.Thread(
            target=self._acquisition_loop, name="AcquisitionManager", daemon=True
        )
        self.acquisition_thread.start()

        # Broadcast presentation stimulus state change to enable presentation window
        # This tells the presentation window to start rendering frames from shared memory
        if self.ipc:
            self.ipc.send_sync_message(
                {
                    "type": "presentation_stimulus_state",
                    "enabled": True,
                    "timestamp": time.time(),
                }
            )
            logger.info("Sent presentation_stimulus_state: enabled=True")

        return {
            "success": True,
            "message": "Acquisition started",
            "total_directions": len(self.directions),
            "total_cycles": self.cycles,
        }

    def stop_acquisition(self) -> Dict[str, Any]:
        """Stop the acquisition sequence."""
        with self._state_lock:
            if not self.is_running:
                return {"success": False, "error": "Acquisition not running"}

            logger.info("Stopping acquisition")
            self.stop_event.set()
            self.is_running = False

        # Update state coordinator (release lock to avoid deadlock)
        if self.state_coordinator:
            self.state_coordinator.set_acquisition_running(False)
            self.state_coordinator.transition_to_idle()

        # Disable synchronization tracking
        if self.synchronization_tracker:
            self.synchronization_tracker.disable()

        # Wait for thread to finish
        if self.acquisition_thread:
            self.acquisition_thread.join(timeout=2.0)

        # Display black screen when stopping
        try:
            self._display_black_screen()
        except Exception as e:
            logger.warning(f"Failed to display black screen when stopping: {e}")

        # Broadcast presentation stimulus state change to disable presentation window
        if self.ipc:
            self.ipc.send_sync_message(
                {
                    "type": "presentation_stimulus_state",
                    "enabled": False,
                    "timestamp": time.time(),
                }
            )
            logger.info("Sent presentation_stimulus_state: enabled=False")

        with self._state_lock:
            self.phase = AcquisitionPhase.IDLE
            self.target_mode = "preview"

        return {"success": True, "message": "Acquisition stopped"}

    def display_black_screen(self) -> Dict[str, Any]:
        """Display a black screen (public API)."""
        try:
            self._display_black_screen()
            return {"success": True, "message": "Black screen displayed"}
        except Exception as e:
            logger.error(f"Failed to display black screen: {e}")
            return {"success": False, "error": str(e)}

    def get_status(self) -> Dict[str, Any]:
        """Get current acquisition status."""
        with self._state_lock:
            elapsed_time = (
                time.time() - self.acquisition_start_time if self.is_running else 0
            )

            # Defensive: handle case where parameters not yet loaded from param_manager
            # This should only happen if get_status() called before start_acquisition()
            current_direction = None
            if self.directions and self.current_direction_index < len(self.directions):
                current_direction = self.directions[self.current_direction_index]

            return {
                "is_running": self.is_running,
                "phase": self.phase.value,
                "current_direction": current_direction,
                "current_direction_index": self.current_direction_index,
                "total_directions": len(self.directions) if self.directions else 0,
                "current_cycle": self.current_cycle,
                "total_cycles": self.cycles if self.cycles else 0,
                "elapsed_time": elapsed_time,
                "phase_start_time": self.phase_start_time,
            }

    def get_presentation_state(self) -> Dict[str, Any]:
        """Get current presentation stimulus state.

        This allows frontend to query presentation state on mount/ready,
        preventing race conditions where the presentation window misses
        the presentation_stimulus_state broadcast message.

        Returns:
            Dict with enabled status (True during acquisition)
        """
        with self._state_lock:
            # Presentation should be enabled when acquisition is running
            enabled = self.is_running

            return {
                "success": True,
                "enabled": enabled,
                "is_running": self.is_running,
                "target_mode": self.target_mode,
            }

    def _acquisition_loop(self):
        """Main acquisition orchestration loop."""
        try:
            # Phase 1: Initial baseline
            self._enter_phase(AcquisitionPhase.INITIAL_BASELINE)
            initial_baseline_duration = self._publish_baseline_frame()
            if initial_baseline_duration > 0:
                self._wait_duration(initial_baseline_duration)

            # Phase 2: For each direction
            for direction_index, direction in enumerate(self.directions):
                if self.stop_event.is_set():
                    break

                with self._state_lock:
                    self.current_direction_index = direction_index
                    self.current_cycle = 0

                # Start data recording for this direction
                if self.data_recorder:
                    self.data_recorder.start_recording(direction)

                # For each cycle
                for cycle in range(self.cycles):
                    if self.stop_event.is_set():
                        break

                    with self._state_lock:
                        self.current_cycle = cycle + 1

                    # Play stimulus for this direction
                    self._enter_phase(AcquisitionPhase.STIMULUS)

                    # Get monitor FPS from parameters
                    monitor_params = self.param_manager.get_parameter_group("monitor")
                    monitor_fps = monitor_params.get("monitor_fps")

                    # Validate monitor_fps explicitly
                    if (
                        monitor_fps is None
                        or not isinstance(monitor_fps, (int, float))
                        or monitor_fps <= 0
                    ):
                        raise RuntimeError(
                            "monitor_fps is required but not configured in param_manager. "
                            "Monitor refresh rate must be explicitly specified for accurate stimulus timing. "
                            f"Please set monitor.monitor_fps parameter. Received: {monitor_fps}"
                        )

                    # Start unified stimulus playback for this direction
                    start_result = self.unified_stimulus.start_playback(
                        direction=direction, monitor_fps=monitor_fps
                    )
                    if not start_result.get("success"):
                        raise RuntimeError(
                            f"Failed to start unified stimulus: {start_result.get('error')}"
                        )
                    logger.info(
                        f"Unified stimulus playback started for {direction} cycle {cycle+1}: "
                        f"{start_result.get('total_frames')} frames at {start_result.get('fps')} fps"
                    )

                    # Calculate sweep duration based on stimulus dataset (one cycle)
                    # Unified stimulus plays at monitor FPS, camera captures independently
                    # Each cycle is one complete sweep - acquisition loops over cycles
                    dataset_info = self.stimulus_generator.get_dataset_info(direction)
                    sweep_duration_sec = dataset_info.get("duration_sec", 0.0)

                    logger.info(
                        f"Sweep duration: {sweep_duration_sec:.2f}s for {direction}"
                    )

                    # Sleep for sweep duration (unified stimulus plays in background thread)
                    self._wait_duration(sweep_duration_sec)

                    # Stop unified stimulus playback
                    stop_result = self.unified_stimulus.stop_playback()
                    if not stop_result.get("success"):
                        logger.warning(
                            f"Failed to stop unified stimulus: {stop_result.get('error')}"
                        )
                    logger.info(f"Unified stimulus playback stopped for {direction}")

                    # Always exit STIMULUS phase immediately after stopping stimulus
                    # This ensures we never remain in STIMULUS phase without active stimulus
                    # Timestamp is cleared both by stop_stimulus() and _enter_phase()
                    if cycle < self.cycles - 1:
                        # More cycles remain - enter between-trials phase
                        self._enter_phase(AcquisitionPhase.BETWEEN_TRIALS)
                        self._publish_baseline_frame()
                        self._wait_duration(self.between_sec)
                    else:
                        # Last cycle completed - stay in STIMULUS briefly for background screen
                        # Will transition to BETWEEN_TRIALS or FINAL_BASELINE next
                        self._publish_baseline_frame()

                # Stop data recording for this direction (after all cycles complete)
                if self.data_recorder:
                    self.data_recorder.stop_recording()

                if self.stop_event.is_set():
                    break

                # Between directions: add baseline wait only if not the last direction
                if direction_index < len(self.directions) - 1:
                    self._enter_phase(AcquisitionPhase.BETWEEN_TRIALS)
                    baseline_duration = self._publish_baseline_frame()
                    if baseline_duration > 0:
                        self._wait_duration(baseline_duration)

            # Phase 3: Final baseline
            self._enter_phase(AcquisitionPhase.FINAL_BASELINE)
            final_baseline_duration = self._publish_baseline_frame()
            if final_baseline_duration > 0:
                self._wait_duration(final_baseline_duration)

            # Complete
            self._enter_phase(AcquisitionPhase.COMPLETE)

        except Exception as e:
            logger.error(f"Acquisition loop error: {e}", exc_info=True)
        finally:
            with self._state_lock:
                self.is_running = False
                self.phase = AcquisitionPhase.IDLE

            if self.synchronization_tracker:
                self.synchronization_tracker.disable()

            # Save all recorded data to disk
            if self.data_recorder:
                try:
                    logger.info("Saving acquisition data...")
                    self.data_recorder.save_session()
                    logger.info(
                        f"Acquisition data saved to: {self.data_recorder.session_path}"
                    )

                    # Send IPC signal that data is saved and ready for analysis
                    # This eliminates race conditions by coordinating file access
                    if self.ipc:
                        self.ipc.send_sync_message(
                            {
                                "type": "acquisition_data_saved",
                                "session_path": str(self.data_recorder.session_path),
                                "timestamp": time.time(),
                            }
                        )
                        logger.info("Sent acquisition_data_saved IPC signal")

                except Exception as e:
                    logger.error(f"Failed to save acquisition data: {e}", exc_info=True)

            # Always display black screen when acquisition ends
            try:
                self._display_black_screen()
            except Exception as e:
                logger.warning(
                    f"Failed to display black screen at end of acquisition: {e}"
                )

    def _enter_phase(self, phase: AcquisitionPhase):
        """Enter a new acquisition phase."""
        with self._state_lock:
            self.phase = phase
            self.phase_start_time = time.time()

        # Clear stimulus timestamp when entering non-stimulus phases
        # This ensures no stale timestamps persist during baselines/between trials
        if phase != AcquisitionPhase.STIMULUS:
            if self.shared_memory:
                self.shared_memory.clear_stimulus_timestamp()
                logger.debug(f"Cleared stimulus timestamp for phase: {phase.value}")

        # Synchronization tracking remains enabled throughout acquisition
        # Timestamp validation filters non-stimulus synchronization data
        logger.info(f"Acquisition phase: {phase.value}")

        # Send progress update to frontend (get_status() acquires lock internally)
        status = self.get_status()
        if self.ipc:
            self.ipc.send_sync_message(
                {"type": "acquisition_progress", "timestamp": time.time(), **status}
            )

    def _wait_duration(self, duration_sec: float):
        """Wait for a duration, checking stop event periodically."""
        end_time = time.time() + duration_sec
        while time.time() < end_time:
            if self.stop_event.is_set():
                break
            time.sleep(0.1)  # Check every 100ms

    def _display_black_screen(self) -> None:
        """Display a background screen at configured background_luminance using unified stimulus."""
        if not self.unified_stimulus:
            logger.warning(
                "Cannot display baseline: no unified stimulus controller available"
            )
            return

        result = self.unified_stimulus.display_baseline()
        if not result.get("success"):
            logger.error(f"Failed to display baseline: {result.get('error')}")

    def _publish_baseline_frame(self) -> float:
        """Publish a background frame to display during baseline and return baseline duration."""
        self._display_black_screen()
        return float(self.baseline_sec)

    # ------------------------------------------------------------------
    # Timestamp synchronization tracking

    def record_synchronization(
        self,
        camera_timestamp_us: int,
        stimulus_timestamp_us: Optional[int],
        frame_id: Optional[int],
    ) -> None:
        """Record a camera-stimulus timestamp synchronization sample (delegates to tracker)."""
        if self.synchronization_tracker:
            self.synchronization_tracker.record_synchronization(
                camera_timestamp_us, stimulus_timestamp_us, frame_id
            )

    def get_synchronization_data(self) -> Dict[str, Any]:
        """Return synchronization dataset and summary statistics (delegates to tracker)."""
        if self.synchronization_tracker:
            return self.synchronization_tracker.get_synchronization_data()
        return {"synchronization": [], "statistics": {}, "window_info": {}}

    def get_recent_synchronization(
        self, window_seconds: float = 5.0
    ) -> List[Dict[str, Any]]:
        """Return synchronization within the most recent window (delegates to tracker)."""
        if self.synchronization_tracker:
            return self.synchronization_tracker.get_recent_synchronization(
                window_seconds
            )
        return []
