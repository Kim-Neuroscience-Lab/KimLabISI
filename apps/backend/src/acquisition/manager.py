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
        synchronization_tracker: Optional[TimestampSynchronizationTracker] = None,
        state_coordinator: Optional[AcquisitionStateCoordinator] = None,
        camera_triggered_stimulus=None,
        data_recorder=None,
        param_manager=None,
    ):
        """Initialize acquisition manager with injected dependencies.

        Args:
            ipc: IPC service for communication with frontend
            shared_memory: Shared memory service for frame data
            stimulus_generator: Stimulus generator for frame generation
            synchronization_tracker: Optional timestamp synchronization tracker
            state_coordinator: Optional state coordinator
            camera_triggered_stimulus: Optional camera-triggered stimulus controller
            data_recorder: Optional data recorder
            param_manager: Optional parameter manager
        """
        # Injected dependencies
        self.ipc = ipc
        self.shared_memory = shared_memory
        self.stimulus_generator = stimulus_generator
        self.param_manager = param_manager

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

        # Parameters (set when acquisition starts)
        self.baseline_sec = 5
        self.between_sec = 5
        self.cycles = 10
        self.directions = ["LR", "RL", "TB", "BT"]
        self.camera_fps = 30.0  # Camera frame rate (used for camera-triggered timing)
        self.target_mode: Literal["preview", "record", "playback"] = "preview"
        self.target_direction = "LR"
        self.target_frame_index = 0
        self.target_show_mask = False

        # Timestamp synchronization tracker (dependency injection)
        # IMPORTANT: Must be injected, not created here, to ensure single shared instance
        self.synchronization_tracker = synchronization_tracker

        # State coordinator (dependency injection)
        self.state_coordinator = state_coordinator

        # Camera-triggered stimulus controller (dependency injection)
        self.camera_triggered_stimulus = camera_triggered_stimulus

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
                    return {"success": False, "error": "Playback controller not initialized"}
                result = self.playback_controller.activate()

            if result.get("success"):
                self.target_mode = mode

            return result

        except Exception as exc:
            logger.error("Failed to set acquisition mode: %s", exc, exc_info=True)
            return {"success": False, "error": str(exc)}

    def start_acquisition(self, params: Dict[str, Any], param_manager=None) -> Dict[str, Any]:
        """Start the acquisition sequence."""
        with self._state_lock:
            if self.is_running:
                return {"success": False, "error": "Acquisition already running"}

            # Validate required dependencies for record mode
            if not self.camera_triggered_stimulus:
                error_msg = (
                    "Camera-triggered stimulus controller is required for record mode. "
                    "This indicates a system initialization error - camera_triggered_stimulus "
                    "must be injected during backend setup."
                )
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Load and validate REQUIRED acquisition parameters
            # No defaults - experimental protocol must be explicit for scientific validity

            baseline_sec = params.get("baseline_sec")
            if baseline_sec is None or not isinstance(baseline_sec, (int, float)) or baseline_sec < 0:
                error_msg = (
                    "baseline_sec is required but not provided in acquisition parameters. "
                    "Baseline duration must be explicitly specified for reproducible experiments. "
                    f"Received: {baseline_sec}"
                )
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
            self.baseline_sec = float(baseline_sec)

            between_sec = params.get("between_sec")
            if between_sec is None or not isinstance(between_sec, (int, float)) or between_sec < 0:
                error_msg = (
                    "between_sec is required but not provided in acquisition parameters. "
                    "Inter-trial interval must be explicitly specified for reproducible experiments. "
                    f"Received: {between_sec}"
                )
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
            self.between_sec = float(between_sec)

            cycles = params.get("cycles")
            if cycles is None or not isinstance(cycles, int) or cycles <= 0:
                error_msg = (
                    "cycles is required but not provided in acquisition parameters. "
                    "Number of repetitions must be explicitly specified for reproducible experiments. "
                    f"Received: {cycles}"
                )
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
            self.cycles = cycles

            directions = params.get("directions")
            if not directions or not isinstance(directions, list) or len(directions) == 0:
                error_msg = (
                    "directions is required but not provided in acquisition parameters. "
                    "Must specify list of sweep directions (e.g., ['LR', 'RL', 'TB', 'BT']). "
                    f"Received: {directions}"
                )
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Validate direction values
            valid_directions = {"LR", "RL", "TB", "BT"}
            invalid = [d for d in directions if d not in valid_directions]
            if invalid:
                error_msg = (
                    f"Invalid directions: {invalid}. "
                    f"Must be one of {valid_directions}. "
                    f"Received: {directions}"
                )
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
            self.directions = directions

            # Camera FPS is REQUIRED - no default for scientific validity
            camera_fps_value = params.get("camera_fps")
            if camera_fps_value is None or not isinstance(camera_fps_value, (int, float)) or camera_fps_value <= 0:
                error_msg = (
                    "camera_fps is required but not provided in acquisition parameters. "
                    "Camera FPS must be set to the actual frame rate of your camera hardware "
                    "for scientifically valid acquisition timing. "
                    f"Received: {camera_fps_value}"
                )
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # Type-safe assignment after validation
            self.camera_fps: float = float(camera_fps_value)

            self.target_mode = "record"

            logger.info(
                f"Starting acquisition: {self.cycles} cycles × {len(self.directions)} directions"
            )
            logger.info(f"Baseline: {self.baseline_sec}s, Between: {self.between_sec}s")
            logger.info(f"Camera-triggered mode: {self.camera_fps} fps")

            # Reset state
            self.is_running = True
            self.stop_event.clear()
            self.current_direction_index = 0
            self.current_cycle = 0
            self.acquisition_start_time = time.time()

        # Update state coordinator
        if self.state_coordinator:
            self.state_coordinator.set_acquisition_running(True)

        # Initialize data recorder with session metadata
        # Use passed param_manager or injected one
        pm = param_manager or self.param_manager

        if self.data_recorder is None and pm:
            from .recorder import create_session_recorder

            # Build comprehensive session metadata from all parameter groups
            session_params = pm.get_parameter_group("session") if pm else {}
            session_metadata = {
                "session_name": session_params.get("session_name", "unnamed_session"),
                "animal_id": session_params.get("animal_id", ""),
                "animal_age": session_params.get("animal_age", ""),
                "timestamp": time.time(),
                "acquisition": params,
                "camera": pm.get_parameter_group("camera") if pm else {},
                "monitor": pm.get_parameter_group("monitor") if pm else {},
                "stimulus": pm.get_parameter_group("stimulus") if pm else {},
                "timestamp_info": {
                    "camera_timestamp_source": "to_be_determined",  # Set by camera manager
                    "stimulus_timestamp_source": "camera_triggered_synchronous",
                    "synchronization_method": "camera_capture_triggers_stimulus_generation",
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
                        )
                    }
                },
            }

            self.data_recorder = create_session_recorder(
                session_name=session_metadata["session_name"],
                metadata=session_metadata,
            )
            logger.info(f"Data recorder created: {self.data_recorder.session_path}")

            # NOTE: Passing data recorder to camera manager would normally happen here
            # but camera manager is not injected in this refactor (would need to be added)
            # For now, this would be handled by the system that creates the AcquisitionManager

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

            return {
                "is_running": self.is_running,
                "phase": self.phase.value,
                "current_direction": (
                    self.directions[self.current_direction_index]
                    if self.current_direction_index < len(self.directions)
                    else None
                ),
                "current_direction_index": self.current_direction_index,
                "total_directions": len(self.directions),
                "current_cycle": self.current_cycle,
                "total_cycles": self.cycles,
                "elapsed_time": elapsed_time,
                "phase_start_time": self.phase_start_time,
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

                # Start camera-triggered stimulus for this direction
                if self.camera_triggered_stimulus:
                    start_result = self.camera_triggered_stimulus.start_direction(
                        direction=direction,
                        camera_fps=self.camera_fps
                    )
                    if not start_result.get("success"):
                        raise RuntimeError(
                            f"Failed to start camera-triggered stimulus: {start_result.get('error')}"
                        )
                    logger.info(
                        f"Camera-triggered stimulus started for {direction}: "
                        f"{start_result.get('total_frames')} frames"
                    )

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

                    # Camera-triggered mode: REQUIRED for record mode
                    if not self.camera_triggered_stimulus:
                        raise RuntimeError(
                            "Camera-triggered stimulus controller is required for record mode. "
                            "This indicates a configuration error - ensure camera_triggered_stimulus "
                            "is properly injected during initialization."
                        )

                    # Calculate expected duration based on camera fps
                    stimulus_duration = self._get_stimulus_duration_camera_fps()
                    timeout = stimulus_duration * 2.0  # Safety timeout

                    logger.info(
                        f"Waiting for camera-triggered stimulus completion: "
                        f"direction={direction}, cycle={cycle+1}/{self.cycles}, "
                        f"expected_duration={stimulus_duration:.2f}s"
                    )

                    # Poll for completion
                    start_time = time.time()
                    while not self.camera_triggered_stimulus.is_direction_complete():
                        if self.stop_event.is_set():
                            break
                        if time.time() - start_time > timeout:
                            logger.warning(
                                f"Camera-triggered stimulus timeout after {timeout:.2f}s"
                            )
                            break
                        time.sleep(0.1)  # Poll every 100ms

                    status = self.camera_triggered_stimulus.get_status()
                    logger.info(
                        f"Camera-triggered stimulus complete: {status.get('frame_index')}/"
                        f"{status.get('total_frames')} frames"
                    )

                    # Always exit STIMULUS phase immediately after stopping stimulus
                    # This ensures we never remain in STIMULUS phase without active stimulus
                    # Timestamp is cleared both by stop_stimulus() and _enter_phase()
                    if cycle < self.cycles - 1:
                        # More cycles remain - enter between-trials phase
                        self._enter_phase(AcquisitionPhase.BETWEEN_TRIALS)
                        self._publish_baseline_frame()
                        self._wait_duration(self.between_sec)
                    else:
                        # Last cycle completed - stay in STIMULUS briefly for black screen
                        # Will transition to BETWEEN_TRIALS or FINAL_BASELINE next
                        self._publish_baseline_frame()

                # Stop camera-triggered stimulus and data recording for this direction
                if self.camera_triggered_stimulus:
                    stop_result = self.camera_triggered_stimulus.stop_direction()
                    logger.info(
                        f"Camera-triggered stimulus stopped: {stop_result.get('frames_generated')}/"
                        f"{stop_result.get('expected_frames')} frames generated"
                    )

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
                    logger.info(f"Acquisition data saved to: {self.data_recorder.session_path}")
                except Exception as e:
                    logger.error(f"Failed to save acquisition data: {e}", exc_info=True)

            # Always display black screen when acquisition ends
            try:
                self._display_black_screen()
            except Exception as e:
                logger.warning(f"Failed to display black screen at end of acquisition: {e}")

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

    def _get_stimulus_duration_camera_fps(self) -> float:
        """
        Calculate stimulus duration for camera-triggered mode.

        In camera-triggered mode, stimulus advancement is paced by camera FPS,
        not monitor FPS. Returns expected duration based on camera frame rate.

        The direction is tracked internally by the camera-triggered stimulus controller.

        Returns:
            Expected stimulus duration in seconds

        Raises:
            RuntimeError: If camera_triggered_stimulus is not available or if
                         stimulus parameters are invalid (system misconfiguration)
        """
        if not self.camera_triggered_stimulus:
            raise RuntimeError(
                "Camera-triggered stimulus controller is required for record mode. "
                "This indicates a system initialization error - camera_triggered_stimulus "
                "must be injected during backend setup. Cannot calculate stimulus duration."
            )

        # Get stimulus info from camera-triggered controller
        status = self.camera_triggered_stimulus.get_status()

        # Fail hard if total_frames missing or invalid - no defaults allowed
        total_frames = status.get("total_frames")
        if total_frames is None:
            raise RuntimeError(
                "Camera-triggered stimulus status does not contain 'total_frames'. "
                "This indicates the stimulus controller is in an invalid state. "
                "Cannot proceed with scientifically invalid acquisition parameters."
            )

        if not isinstance(total_frames, int) or total_frames <= 0:
            raise RuntimeError(
                f"Camera-triggered stimulus has invalid frame count: {total_frames}. "
                f"This indicates stimulus was not properly started or configured incorrectly. "
                f"Cannot proceed with scientifically invalid acquisition parameters."
            )

        if self.camera_fps <= 0:
            raise RuntimeError(
                f"Invalid camera FPS: {self.camera_fps}. "
                f"This indicates camera parameters are not properly configured. "
                f"Cannot proceed with scientifically invalid acquisition parameters."
            )

        duration = float(total_frames) / float(self.camera_fps)
        logger.debug(
            f"Camera-triggered stimulus duration: {duration:.2f}s "
            f"({total_frames} frames at {self.camera_fps} fps)"
        )
        return duration

    def _display_black_screen(self) -> None:
        """Display a black screen immediately."""
        # Get monitor parameters from injected param_manager
        if not self.param_manager:
            logger.warning("Cannot display black screen: no parameter manager available")
            return

        monitor_params = self.param_manager.get_parameter_group("monitor")

        # Validate monitor dimensions - REQUIRED for display operations
        width = monitor_params.get("monitor_width_px")
        if width is None:
            raise RuntimeError(
                "monitor_width_px is required but not configured in monitor parameters. "
                "Must specify monitor width for stimulus display."
            )
        if not isinstance(width, int) or width <= 0:
            raise RuntimeError(
                f"monitor_width_px must be a positive integer. Received: {width}"
            )

        height = monitor_params.get("monitor_height_px")
        if height is None:
            raise RuntimeError(
                "monitor_height_px is required but not configured in monitor parameters. "
                "Must specify monitor height for stimulus display."
            )
        if not isinstance(height, int) or height <= 0:
            raise RuntimeError(
                f"monitor_height_px must be a positive integer. Received: {height}"
            )

        if self.shared_memory:
            self.shared_memory.publish_black_frame(width, height)
            logger.debug("Black screen displayed")

    def _publish_baseline_frame(self) -> float:
        """Publish a black frame to display during baseline and return baseline duration."""
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
            return self.synchronization_tracker.get_recent_synchronization(window_seconds)
        return []
