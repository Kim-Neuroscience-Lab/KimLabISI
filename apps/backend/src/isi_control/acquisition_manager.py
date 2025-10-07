"""Acquisition sequence orchestrator for ISI experiments."""

import time
import threading
from typing import Optional, Dict, Any, List

import numpy as np
from enum import Enum

from .logging_utils import get_logger

logger = get_logger(__name__)


class AcquisitionPhase(Enum):
    """Phases of the acquisition sequence."""

    IDLE = "idle"
    INITIAL_BASELINE = "initial_baseline"
    STIMULUS = "stimulus"
    BETWEEN_TRIALS = "between_trials"
    FINAL_BASELINE = "final_baseline"
    COMPLETE = "complete"


class AcquisitionManager:
    """Manages the acquisition sequence timing and state."""

    def __init__(self):
        self.is_running = False
        self.acquisition_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

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

        # Timing correlation history (camera vs stimulus)
        self.correlation_history: List[Dict[str, Any]] = []

    def start_acquisition(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Start the acquisition sequence."""
        if self.is_running:
            return {"success": False, "error": "Acquisition already running"}

        # Load parameters
        self.baseline_sec = params.get("baseline_sec", 5)
        self.between_sec = params.get("between_sec", 5)
        self.cycles = params.get("cycles", 10)
        self.directions = params.get("directions", ["LR", "RL", "TB", "BT"])

        logger.info(
            f"Starting acquisition: {self.cycles} cycles × {len(self.directions)} directions"
        )
        logger.info(f"Baseline: {self.baseline_sec}s, Between: {self.between_sec}s")

        # Reset state
        self.is_running = True
        self.stop_event.clear()
        self.current_direction_index = 0
        self.current_cycle = 0
        self.acquisition_start_time = time.time()

        # Start acquisition thread
        self.acquisition_thread = threading.Thread(
            target=self._acquisition_loop, name="AcquisitionOrchestrator", daemon=True
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
        if not self.is_running:
            return {"success": False, "error": "Acquisition not running"}

        logger.info("Stopping acquisition")
        self.stop_event.set()
        self.is_running = False

        # Wait for thread to finish
        if self.acquisition_thread:
            self.acquisition_thread.join(timeout=2.0)

        self.phase = AcquisitionPhase.IDLE

        return {"success": True, "message": "Acquisition stopped"}

    def get_status(self) -> Dict[str, Any]:
        """Get current acquisition status."""
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
            # Get services
            from .service_locator import get_services

            services = get_services()
            ipc = services.ipc

            # Import stimulus manager handlers
            from .stimulus_manager import handle_start_stimulus, handle_stop_stimulus

            # Phase 1: Initial baseline
            self._enter_phase(AcquisitionPhase.INITIAL_BASELINE, ipc)
            self._wait_duration(self.baseline_sec)

            # Phase 2: For each direction
            for direction_index, direction in enumerate(self.directions):
                if self.stop_event.is_set():
                    break

                self.current_direction_index = direction_index

                # For each cycle
                for cycle in range(self.cycles):
                    if self.stop_event.is_set():
                        break

                    self.current_cycle = cycle + 1

                    # Play stimulus for this direction
                    self._enter_phase(AcquisitionPhase.STIMULUS, ipc)

                    # Start stimulus with mask enabled
                    result = handle_start_stimulus(
                        {"direction": direction, "show_bar_mask": True}
                    )

                    if not result.get("success"):
                        logger.error(f"Failed to start stimulus: {result.get('error')}")
                        # Break out of cycle loop - skip to next direction
                        break

                    # Wait for full stimulus duration (calculate based on stimulus params)
                    stimulus_duration = self._get_stimulus_duration()
                    self._wait_duration(stimulus_duration)

                    # Stop stimulus
                    result = handle_stop_stimulus({})
                    if not result.get("success"):
                        logger.error(f"Failed to stop stimulus: {result.get('error')}")

                    # Between trials baseline (only after successful stimulus)
                    if (
                        cycle < self.cycles - 1
                    ):  # Don't add between time after last cycle
                        self._enter_phase(AcquisitionPhase.BETWEEN_TRIALS, ipc)
                        self._wait_duration(self.between_sec)

                # After completing all cycles for this direction, play baseline
                # This happens for ALL directions, even the last one
                if not self.stop_event.is_set():
                    self._enter_phase(AcquisitionPhase.BETWEEN_TRIALS, ipc)
                    self._wait_duration(self.baseline_sec)

            # Phase 3: Final baseline
            self._enter_phase(AcquisitionPhase.FINAL_BASELINE, ipc)
            self._wait_duration(self.baseline_sec)

            # Complete
            self._enter_phase(AcquisitionPhase.COMPLETE, ipc)

        except Exception as e:
            logger.error(f"Acquisition loop error: {e}", exc_info=True)
        finally:
            self.is_running = False
            self.phase = AcquisitionPhase.IDLE
            self.correlation_history.clear()

    def _enter_phase(self, phase: AcquisitionPhase, ipc):
        """Enter a new acquisition phase."""
        self.phase = phase
        self.phase_start_time = time.time()

        logger.info(f"Acquisition phase: {phase.value}")

        # Send progress update to frontend
        status = self.get_status()
        ipc.send_sync_message(
            {"type": "acquisition_progress", "timestamp": time.time(), **status}
        )

    def _wait_duration(self, duration_sec: float):
        """Wait for a duration, checking stop event periodically."""
        end_time = time.time() + duration_sec
        while time.time() < end_time:
            if self.stop_event.is_set():
                break
            time.sleep(0.1)  # Check every 100ms

    def _get_stimulus_duration(self) -> float:
        """Calculate stimulus playback duration based on parameters."""
        from .service_locator import get_services

        services = get_services()
        param_manager = services.parameter_manager

        stimulus_params = param_manager.get_parameter_group("stimulus")
        monitor_params = param_manager.get_parameter_group("monitor")

        # Calculate duration: distance / speed
        # This is simplified - adjust based on your actual stimulus calculation
        drift_speed = stimulus_params.get("drift_speed_deg_per_sec", 9)

        # Approximate: one full sweep across monitor
        # You may need to adjust this calculation based on your stimulus geometry
        total_angle = 180  # degrees (full sweep)
        duration = total_angle / drift_speed

        return duration

    # ------------------------------------------------------------------
    # Correlation tracking

    def record_correlation(
        self,
        camera_timestamp_us: int,
        stimulus_timestamp_us: Optional[int],
        frame_id: Optional[int],
    ) -> None:
        """Record a camera-stimulus timing correlation sample."""

        if not self.is_running or stimulus_timestamp_us is None:
            return

        time_diff_us = camera_timestamp_us - stimulus_timestamp_us
        time_diff_ms = time_diff_us / 1000.0

        self.correlation_history.append(
            {
                "camera_timestamp": camera_timestamp_us,
                "stimulus_timestamp": stimulus_timestamp_us,
                "frame_id": frame_id,
                "time_difference_us": time_diff_us,
                "time_difference_ms": time_diff_ms,
            }
        )

        if len(self.correlation_history) > 1000:
            self.correlation_history.pop(0)

    def get_correlation_data(self) -> Dict[str, Any]:
        """Return correlation dataset and summary statistics."""

        recent_entries = self.get_recent_correlations()

        if not recent_entries:
            return {
                "correlations": [],
                "statistics": {
                    "count": 0,
                    "matched_count": 0,
                    "mean_diff_ms": 0.0,
                    "std_diff_ms": 0.0,
                    "min_diff_ms": 0.0,
                    "max_diff_ms": 0.0,
                    "histogram": [],
                    "bin_edges": [],
                },
            }

        diffs_ms = np.array(
            [
                c["time_difference_ms"]
                for c in recent_entries
                if c["time_difference_ms"] is not None
            ],
            dtype=float,
        )

        if diffs_ms.size == 0:
            stats = {
                "count": len(recent_entries),
                "matched_count": 0,
                "mean_diff_ms": 0.0,
                "std_diff_ms": 0.0,
                "min_diff_ms": 0.0,
                "max_diff_ms": 0.0,
                "histogram": [],
                "bin_edges": [],
            }
        else:
            hist, bin_edges = np.histogram(diffs_ms, bins=50)

            stats = {
                "count": len(recent_entries),
                "matched_count": int(diffs_ms.size),
                "mean_diff_ms": float(np.mean(diffs_ms)),
                "std_diff_ms": float(np.std(diffs_ms)),
                "min_diff_ms": float(np.min(diffs_ms)),
                "max_diff_ms": float(np.max(diffs_ms)),
                "histogram": hist.tolist(),
                "bin_edges": bin_edges.tolist(),
            }

        return {
            "correlations": recent_entries,
            "statistics": stats,
        }

    def get_recent_correlations(
        self, window_seconds: float = 5.0
    ) -> List[Dict[str, Any]]:
        """Return correlations within the most recent window in seconds."""

        if not self.correlation_history:
            return []

        latest_timestamp = self.correlation_history[-1]["camera_timestamp"]
        threshold = latest_timestamp - (window_seconds * 1_000_000)

        recent = [
            entry
            for entry in self.correlation_history
            if entry["camera_timestamp"] >= threshold
        ]

        return recent[-100:] if len(recent) > 100 else recent


# Global instance
_acquisition_manager = AcquisitionManager()


def get_acquisition_manager() -> AcquisitionManager:
    """Get the global acquisition manager instance."""
    return _acquisition_manager


# Handler functions for IPC
def handle_start_acquisition(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle start_acquisition IPC command."""
    from .service_locator import get_services

    services = get_services()
    param_manager = services.parameter_manager

    # Get acquisition parameters
    acq_params = param_manager.get_parameter_group("acquisition")

    manager = get_acquisition_manager()
    return manager.start_acquisition(acq_params)


def handle_stop_acquisition(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle stop_acquisition IPC command."""
    manager = get_acquisition_manager()
    return manager.stop_acquisition()


def handle_get_acquisition_status(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_acquisition_status IPC command."""
    manager = get_acquisition_manager()
    status = manager.get_status()

    return {"success": True, "status": status}
