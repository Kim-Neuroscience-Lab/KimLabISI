"""Acquisition mode controllers for preview, record, and playback modes.

Refactored from isi_control/acquisition_mode_controllers.py with KISS approach:
- Constructor injection: all dependencies passed as parameters
- No service_locator imports
- No global singletons
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
import threading
import time

from .state import AcquisitionStateCoordinator

logger = logging.getLogger(__name__)


class AcquisitionModeController(ABC):
    """Base class for acquisition mode controllers."""

    def __init__(
        self,
        state_coordinator: Optional[AcquisitionStateCoordinator] = None,
    ):
        self.state_coordinator = state_coordinator

    @abstractmethod
    def activate(self, **kwargs) -> Dict[str, Any]:
        """
        Activate this mode.

        Returns:
            Dictionary with success status and mode information
        """
        pass

    @abstractmethod
    def deactivate(self) -> Dict[str, Any]:
        """
        Deactivate this mode.

        Returns:
            Dictionary with success status
        """
        pass


class PreviewModeController(AcquisitionModeController):
    """Handles preview mode logic."""

    def __init__(
        self,
        state_coordinator: Optional[AcquisitionStateCoordinator] = None,
        shared_memory_service=None,
        stimulus_generator=None,
        ipc=None,
    ):
        super().__init__(state_coordinator)
        self.shared_memory_service = shared_memory_service
        self.stimulus_generator = stimulus_generator
        self.ipc = ipc

    def activate(
        self,
        direction: str = "LR",
        frame_index: int = 0,
        show_bar_mask: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Activate preview mode and display a single stimulus frame.

        Args:
            direction: Stimulus direction (LR, RL, TB, BT)
            frame_index: Frame index to display
            show_bar_mask: Whether to show the bar mask
            **kwargs: Additional arguments (may include services)

        Returns:
            Dictionary with success status and preview information
        """
        # Update state coordinator
        if self.state_coordinator:
            self.state_coordinator.transition_to_preview()

        if not self.shared_memory_service:
            return {"success": False, "error": "Shared memory service unavailable"}

        if not self.stimulus_generator:
            return {"success": False, "error": "Stimulus generator unavailable"}

        # Generate preview frame
        frame, metadata = self.stimulus_generator.generate_frame_at_index(
            direction=direction,
            frame_index=frame_index,
            show_bar_mask=show_bar_mask,
        )

        preview_metadata = {
            **metadata,
            "mode": "preview",
            "direction": direction,
            "frame_index": frame_index,
            "show_bar_mask": show_bar_mask,
        }

        # Write preview frame to shared memory
        frame_id = self.shared_memory_service.write_preview_frame(
            frame, preview_metadata
        )
        frame_info = self.shared_memory_service.get_frame_info(frame_id)

        # Notify frontend
        if frame_info is not None and self.ipc:
            self.ipc.send_sync_message(
                {
                    "type": "stimulus_preview",
                    "frame_id": frame_info.frame_id,
                    "frame_index": frame_info.frame_index,
                    "direction": frame_info.direction,
                    "angle_degrees": frame_info.angle_degrees,
                    "timestamp_us": frame_info.timestamp_us,
                    "mode": "preview",
                }
            )

        logger.info(
            f"Preview mode activated: direction={direction}, frame={frame_index}"
        )

        return {
            "success": True,
            "mode": "preview",
            "direction": direction,
            "frame_index": frame_index,
            "show_bar_mask": show_bar_mask,
        }

    def deactivate(self) -> Dict[str, Any]:
        """
        Deactivate preview mode.

        Returns:
            Dictionary with success status
        """
        logger.info("Preview mode deactivated")
        return {"success": True}


class RecordModeController(AcquisitionModeController):
    """Handles record mode logic."""

    def __init__(
        self,
        state_coordinator: Optional[AcquisitionStateCoordinator] = None,
        acquisition_orchestrator=None,
    ):
        super().__init__(state_coordinator)
        self.acquisition_orchestrator = acquisition_orchestrator

    def activate(self, param_manager=None, **kwargs) -> Dict[str, Any]:
        """
        Activate record mode (prepare for recording, but don't auto-start).

        Record mode sets up the system for recording but waits for explicit
        start_acquisition command from the user via the Acquisition viewport.

        Args:
            param_manager: Parameter manager for acquisition parameters
            **kwargs: Additional arguments

        Returns:
            Dictionary with success status
        """
        # Check if already recording
        if self.acquisition_orchestrator and self.acquisition_orchestrator.is_running:
            return {"success": True, "mode": "record"}

        # Update state coordinator to indicate we're ready to record
        if self.state_coordinator:
            self.state_coordinator.transition_to_idle()  # Ready but not recording yet

        # Validate parameters are configured (but don't start acquisition)
        if param_manager:
            camera_params = param_manager.get_parameter_group("camera")
            camera_fps = camera_params.get("camera_fps")
            if camera_fps is None or camera_fps <= 0:
                return {
                    "success": False,
                    "error": (
                        "camera_fps is required but not configured in camera parameters. "
                        "Camera FPS must be set to the actual frame rate of your camera hardware "
                        "for scientifically valid acquisition timing."
                    ),
                }
        else:
            return {
                "success": False,
                "error": "Parameter manager is required for record mode",
            }

        # Record mode is now active - waiting for user to click Start in Acquisition viewport
        logger.info("Record mode activated (ready to start acquisition)")
        return {"success": True, "mode": "record"}

    def deactivate(self) -> Dict[str, Any]:
        """
        Deactivate record mode and stop acquisition.

        Returns:
            Dictionary with success status
        """
        if self.acquisition_orchestrator and self.acquisition_orchestrator.is_running:
            self.acquisition_orchestrator.stop_acquisition()

        logger.info("Record mode deactivated")
        return {"success": True}


class PlaybackModeController(AcquisitionModeController):
    """Handles playback mode logic - replays recorded acquisition sessions."""

    def __init__(
        self,
        state_coordinator: Optional[AcquisitionStateCoordinator] = None,
        shared_memory=None,
        ipc=None,
    ):
        super().__init__(state_coordinator)
        self.current_session_path: Optional[str] = None
        self.session_metadata: Optional[Dict[str, Any]] = None
        self._hdf5_file = None  # Keep HDF5 file open for on-demand frame access
        self._current_direction: Optional[str] = (
            None  # Track which direction file is open
        )

        # Playback sequence control
        self.shared_memory = shared_memory
        self.ipc = ipc
        self._playback_thread: Optional[threading.Thread] = None
        self._playback_running = False
        self._playback_stop_event = threading.Event()
        self._current_playback_position = {
            "direction_idx": 0,
            "cycle_idx": 0,
            "frame_idx": 0,
        }

    def activate(self, session_path: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Activate playback mode and load a recorded session.

        Args:
            session_path: Path to the recorded session directory
            **kwargs: Additional arguments

        Returns:
            Dictionary with success status and session information
        """
        import os
        import json

        # Update state coordinator
        if self.state_coordinator:
            self.state_coordinator.transition_to_playback()

        if not session_path:
            # List available sessions (use default base_dir)
            return self._list_available_sessions(base_dir=None)

        # Validate session path
        if not os.path.exists(session_path):
            return {
                "success": False,
                "error": f"Session path not found: {session_path}",
            }

        metadata_path = os.path.join(session_path, "metadata.json")
        if not os.path.exists(metadata_path):
            return {
                "success": False,
                "error": f"Invalid session: metadata.json not found in {session_path}",
            }

        # Load session metadata
        try:
            with open(metadata_path, "r") as f:
                self.session_metadata = json.load(f)

            self.current_session_path = session_path

            logger.info(f"Playback mode activated: loaded session {session_path}")

            return {
                "success": True,
                "mode": "playback",
                "session_path": session_path,
                "session_info": self.session_metadata,
            }

        except Exception as e:
            logger.error(f"Failed to load session: {e}", exc_info=True)
            return {"success": False, "error": f"Failed to load session: {str(e)}"}

    def deactivate(self) -> Dict[str, Any]:
        """
        Deactivate playback mode.

        Returns:
            Dictionary with success status
        """
        # Close HDF5 file if open
        if self._hdf5_file:
            try:
                self._hdf5_file.close()
                logger.info("Closed HDF5 file for playback")
            except Exception as e:
                logger.warning(f"Error closing HDF5 file: {e}")
            finally:
                self._hdf5_file = None

        self._current_direction = None
        self.current_session_path = None
        self.session_metadata = None
        logger.info("Playback mode deactivated")
        return {"success": True}

    def list_sessions(self, base_dir: Optional[str] = None) -> Dict[str, Any]:
        """List all available recorded sessions.

        Args:
            base_dir: Optional base directory to search for sessions.
                     If None, uses default data/sessions directory.

        Returns:
            Dictionary with success status and list of sessions
        """
        return self._list_available_sessions(base_dir)

    def _list_available_sessions(
        self, base_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all available recorded sessions."""
        import os

        # Use provided base_dir or default to data/sessions
        if base_dir:
            base_path = base_dir
        else:
            # Use absolute path to ensure we find sessions regardless of working directory
            base_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "data", "sessions"
            )
            base_path = os.path.abspath(base_path)

        logger.info(f"Looking for sessions in: {base_path}")

        if not os.path.exists(base_path):
            # Create directory if it doesn't exist
            try:
                os.makedirs(base_path, exist_ok=True)
                logger.info(f"Created sessions directory: {base_path}")
            except Exception as e:
                logger.error(f"Cannot create sessions directory: {e}")
                return {
                    "success": False,
                    "error": f"Cannot access sessions directory: {str(e)}",
                }

            return {
                "success": True,
                "mode": "playback",
                "sessions": [],
                "message": "No recorded sessions yet",
            }

        sessions = []
        for session_name in os.listdir(base_path):
            session_path = os.path.join(base_path, session_name)
            metadata_path = os.path.join(session_path, "metadata.json")

            if os.path.isdir(session_path) and os.path.exists(metadata_path):
                try:
                    import json

                    with open(metadata_path, "r") as f:
                        metadata = json.load(f)
                    sessions.append(
                        {
                            "session_name": session_name,
                            "session_path": session_path,
                            "metadata": metadata,
                        }
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to load session metadata: {session_path}: {e}"
                    )

        return {
            "success": True,
            "mode": "playback",
            "sessions": sessions,
            "count": len(sessions),
        }

    def get_session_data(self, direction: Optional[str] = None) -> Dict[str, Any]:
        """
        Get data from the loaded session for a specific direction.

        Args:
            direction: Direction to load (LR, RL, TB, BT). If None, returns all available.

        Returns:
            Dictionary with session data
        """
        import os
        import json
        import h5py
        import numpy as np

        if not self.current_session_path or not self.session_metadata:
            return {"success": False, "error": "No session loaded"}

        try:
            if direction is None:
                # Return available directions from acquisition metadata
                acquisition_params = self.session_metadata.get("acquisition", {})
                directions = acquisition_params.get("directions", [])
                return {
                    "success": True,
                    "directions": directions,
                    "metadata": self.session_metadata,
                }

            # Load data for specific direction
            session_path = self.current_session_path

            # Load stimulus events
            events_path = os.path.join(session_path, f"{direction}_events.json")
            if not os.path.exists(events_path):
                return {
                    "success": False,
                    "error": f"No data found for direction: {direction}",
                }

            with open(events_path, "r") as f:
                events = json.load(f)

            # Load stimulus angles
            stimulus_path = os.path.join(session_path, f"{direction}_stimulus.h5")
            angles = None
            if os.path.exists(stimulus_path):
                with h5py.File(stimulus_path, "r") as f:
                    angles = f["angles"][:]

            # Load camera data if available
            camera_path = os.path.join(session_path, f"{direction}_camera.h5")
            camera_data = None
            if os.path.exists(camera_path):
                try:
                    # Close previous file if switching directions
                    if self._hdf5_file and self._current_direction != direction:
                        self._hdf5_file.close()
                        self._hdf5_file = None

                    # Open HDF5 file in SWMR mode for concurrent read access
                    # This allows multiple readers without exclusive locks
                    self._hdf5_file = h5py.File(camera_path, "r", swmr=True)

                    # Check for required datasets
                    if (
                        "frames" not in self._hdf5_file
                        or "timestamps" not in self._hdf5_file
                    ):
                        logger.error(
                            f"Invalid camera file: missing datasets in {camera_path}"
                        )
                        self._hdf5_file.close()
                        self._hdf5_file = None
                        camera_data = {
                            "has_frames": False,
                            "error": "Invalid camera data file (missing datasets)",
                        }
                    else:
                        self._current_direction = direction

                        # Read ONLY metadata - do not load actual frame data into memory
                        frame_count = len(self._hdf5_file["frames"])
                        frame_shape = (
                            self._hdf5_file["frames"].shape[1:]
                            if frame_count > 0
                            else None
                        )

                        camera_data = {
                            "frame_count": frame_count,
                            "frame_shape": list(frame_shape) if frame_shape else None,
                            "has_frames": True,
                        }

                        logger.info(
                            f"Session has {frame_count} frames available for playback (on-demand loading)"
                        )
                        logger.info(f"Frame shape: {frame_shape}")

                except Exception as e:
                    logger.error(
                        f"Failed to open camera file {camera_path}: {e}", exc_info=True
                    )
                    if self._hdf5_file:
                        self._hdf5_file.close()
                        self._hdf5_file = None
                    camera_data = {
                        "has_frames": False,
                        "error": f"Cannot read camera data: {str(e)}",
                    }
            else:
                camera_data = {
                    "has_frames": False,
                    "frame_count": 0,
                    "message": "No camera data recorded for this direction",
                }

            return {
                "success": True,
                "direction": direction,
                "events": events,
                "stimulus_angles": angles.tolist() if angles is not None else None,
                "camera_data": camera_data,
                "metadata": self.session_metadata,
            }

        except Exception as e:
            logger.error(f"Failed to load session data: {e}", exc_info=True)
            return {"success": False, "error": f"Failed to load data: {str(e)}"}

    def get_playback_frame(self, direction: str, frame_index: int) -> Dict[str, Any]:
        """
        Load a specific frame from the session for playback.

        Args:
            direction: Direction (LR, RL, TB, BT)
            frame_index: Frame index to load

        Returns:
            Dictionary with frame data
        """
        import numpy as np

        if not self.current_session_path or not self.session_metadata:
            return {"success": False, "error": "No session loaded"}

        # Use already-open HDF5 file for fast frame access
        if not self._hdf5_file or self._current_direction != direction:
            return {"success": False, "error": "No session loaded for this direction"}

        try:
            # Validate frame index
            if frame_index < 0 or frame_index >= len(self._hdf5_file["frames"]):
                return {
                    "success": False,
                    "error": f"Frame index {frame_index} out of range",
                }

            # Access frame directly from already-open file - FAST (no file open overhead)
            frame_data = self._hdf5_file["frames"][frame_index]
            timestamp = self._hdf5_file["timestamps"][frame_index]

            # Validate and convert frame shape
            if len(frame_data.shape) not in [2, 3]:
                return {
                    "success": False,
                    "error": f"Invalid frame shape: {frame_data.shape}",
                }

            # Handle different color formats
            if len(frame_data.shape) == 3:
                channels = frame_data.shape[2]
                if channels == 3:
                    # RGB -> Grayscale using ITU-R BT.601 luminance formula
                    frame_gray = (
                        frame_data[:, :, 0] * 0.299
                        + frame_data[:, :, 1] * 0.587
                        + frame_data[:, :, 2] * 0.114
                    ).astype(np.uint8)
                    frame_data = frame_gray
                elif channels == 4:
                    # RGBA -> RGB -> Grayscale (drop alpha channel first)
                    rgb = frame_data[:, :, :3]
                    frame_gray = (
                        rgb[:, :, 0] * 0.299
                        + rgb[:, :, 1] * 0.587
                        + rgb[:, :, 2] * 0.114
                    ).astype(np.uint8)
                    frame_data = frame_gray
                else:
                    return {
                        "success": False,
                        "error": f"Unsupported channel count: {channels}",
                    }
            # else: Already grayscale (2D shape), use as-is

            return {
                "success": True,
                "frame_data": frame_data.tolist(),
                "timestamp": int(timestamp),
                "frame_index": frame_index,
                "direction": direction,
            }

        except Exception as e:
            logger.error(f"Failed to load playback frame: {e}", exc_info=True)
            return {"success": False, "error": f"Failed to load frame: {str(e)}"}

    def start_playback_sequence(self) -> Dict[str, Any]:
        """
        Start automatic playback sequence that replays all directions and cycles.

        Behavior matches acquisition-system.md lines 59-69:
        - Automatically replays full recorded sequence (all directions)
        - Respects baseline and between-trials timing from metadata
        - Publishes frames to shared memory at recorded FPS
        - No manual direction switching allowed

        Returns:
            Dictionary with success status
        """
        if not self.current_session_path or not self.session_metadata:
            return {"success": False, "error": "No session loaded"}

        if self._playback_running:
            return {"success": False, "error": "Playback already running"}

        # Reset position and events
        self._current_playback_position = {
            "direction_idx": 0,
            "cycle_idx": 0,
            "frame_idx": 0,
        }
        self._playback_stop_event.clear()
        self._playback_running = True

        # Start playback thread
        self._playback_thread = threading.Thread(
            target=self._playback_loop, name="PlaybackSequenceThread", daemon=True
        )
        self._playback_thread.start()

        logger.info("Playback sequence started")
        return {"success": True, "message": "Playback sequence started"}

    def stop_playback_sequence(self) -> Dict[str, Any]:
        """
        Stop playback sequence and reset to beginning.

        Returns:
            Dictionary with success status
        """
        if not self._playback_running:
            return {"success": True, "message": "Playback not running"}

        # Signal stop and wait for thread to finish
        self._playback_stop_event.set()
        self._playback_running = False

        if self._playback_thread and self._playback_thread.is_alive():
            self._playback_thread.join(timeout=2.0)

        self._playback_thread = None
        self._current_playback_position = {
            "direction_idx": 0,
            "cycle_idx": 0,
            "frame_idx": 0,
        }

        logger.info("Playback sequence stopped")
        return {"success": True, "message": "Playback stopped"}

    def _playback_loop(self):
        """
        Main playback loop that replays the acquisition sequence.

        Architecture:
        - Follows same sequence as acquisition (baseline → directions/cycles → final baseline)
        - Respects timing from metadata (camera_fps, baseline_sec, between_sec)
        - Publishes frames to shared memory for frontend display
        - Broadcasts progress events via IPC
        """
        import os
        import h5py
        import numpy as np

        try:
            # Load acquisition parameters from metadata
            acquisition_params = self.session_metadata.get("acquisition", {})
            camera_params = self.session_metadata.get("camera", {})

            directions = acquisition_params.get("directions", ["LR", "RL", "TB", "BT"])
            cycles = acquisition_params.get("cycles", 1)
            baseline_sec = acquisition_params.get("baseline_sec", 5.0)
            between_sec = acquisition_params.get("between_sec", 5.0)
            camera_fps = camera_params.get("camera_fps", 30.0)

            frame_interval = 1.0 / camera_fps if camera_fps > 0 else 1.0 / 30.0

            logger.info(
                f"Starting playback sequence: {len(directions)} directions, {cycles} cycles"
            )
            logger.info(
                f"Playback FPS: {camera_fps:.1f} (interval: {frame_interval*1000:.1f}ms)"
            )

            # Phase 1: Initial baseline
            if self.ipc:
                self.ipc.send_sync_message(
                    {
                        "type": "playback_progress",
                        "phase": "INITIAL_BASELINE",
                        "progress": 0.0,
                        "message": "Playing initial baseline",
                    }
                )

            logger.info(f"Phase: INITIAL_BASELINE ({baseline_sec}s)")
            time.sleep(baseline_sec)

            # Phase 2: Iterate through directions and cycles
            total_direction_cycles = len(directions) * cycles
            current_index = 0

            for direction_idx, direction in enumerate(directions):
                # Load camera data for this direction
                camera_path = os.path.join(
                    self.current_session_path, f"{direction}_camera.h5"
                )

                if not os.path.exists(camera_path):
                    logger.warning(
                        f"No camera data for direction {direction}, skipping"
                    )
                    continue

                # Open HDF5 file for this direction
                with h5py.File(camera_path, "r") as h5file:
                    if "frames" not in h5file or "timestamps" not in h5file:
                        logger.warning(f"Invalid camera file for {direction}, skipping")
                        continue

                    total_frames = len(h5file["frames"])
                    frames_per_cycle = (
                        total_frames // cycles if cycles > 0 else total_frames
                    )

                    for cycle_idx in range(cycles):
                        # Check for stop signal
                        if self._playback_stop_event.is_set():
                            logger.info("Playback stopped by user")
                            return

                        current_index += 1
                        progress = current_index / total_direction_cycles

                        # Broadcast progress
                        if self.ipc:
                            self.ipc.send_sync_message(
                                {
                                    "type": "playback_progress",
                                    "phase": "STIMULUS",
                                    "direction": direction,
                                    "cycle": cycle_idx + 1,
                                    "total_cycles": cycles,
                                    "progress": progress,
                                    "message": f"Playing {direction} cycle {cycle_idx + 1}/{cycles}",
                                }
                            )

                        logger.info(
                            f"Phase: STIMULUS - {direction} cycle {cycle_idx + 1}/{cycles}"
                        )

                        # Play frames for this cycle
                        start_frame = cycle_idx * frames_per_cycle
                        end_frame = min(start_frame + frames_per_cycle, total_frames)

                        for frame_idx in range(start_frame, end_frame):
                            # Check for stop signal
                            if self._playback_stop_event.is_set():
                                return

                            # Load and publish frame
                            try:
                                frame_data = h5file["frames"][frame_idx]
                                timestamp = h5file["timestamps"][frame_idx]

                                # Convert to grayscale if needed
                                if len(frame_data.shape) == 3:
                                    if frame_data.shape[2] == 3:
                                        # RGB to grayscale
                                        frame_gray = (
                                            frame_data[:, :, 0] * 0.299
                                            + frame_data[:, :, 1] * 0.587
                                            + frame_data[:, :, 2] * 0.114
                                        ).astype(np.uint8)
                                        frame_data = frame_gray
                                    elif frame_data.shape[2] == 4:
                                        # RGBA to grayscale
                                        rgb = frame_data[:, :, :3]
                                        frame_gray = (
                                            rgb[:, :, 0] * 0.299
                                            + rgb[:, :, 1] * 0.587
                                            + rgb[:, :, 2] * 0.114
                                        ).astype(np.uint8)
                                        frame_data = frame_gray

                                # Publish to shared memory (best-effort, non-blocking)
                                if self.shared_memory:
                                    try:
                                        self.shared_memory.write_camera_frame(
                                            frame_data=frame_data,
                                            camera_name="playback",
                                            capture_timestamp_us=int(timestamp),
                                        )
                                    except Exception as e:
                                        # Non-blocking: log but don't stop playback
                                        logger.debug(
                                            f"Failed to publish frame (non-critical): {e}"
                                        )

                                # Update position
                                self._current_playback_position = {
                                    "direction_idx": direction_idx,
                                    "cycle_idx": cycle_idx,
                                    "frame_idx": frame_idx,
                                }

                            except Exception as e:
                                logger.warning(f"Failed to load frame {frame_idx}: {e}")

                            # Sleep to maintain playback FPS
                            time.sleep(frame_interval)

                        # Between trials pause (except after last cycle)
                        if cycle_idx < cycles - 1:
                            logger.info(f"Phase: BETWEEN_TRIALS ({between_sec}s)")
                            time.sleep(between_sec)

            # Phase 3: Final baseline
            if self.ipc:
                self.ipc.send_sync_message(
                    {
                        "type": "playback_progress",
                        "phase": "FINAL_BASELINE",
                        "progress": 1.0,
                        "message": "Playing final baseline",
                    }
                )

            logger.info(f"Phase: FINAL_BASELINE ({baseline_sec}s)")
            time.sleep(baseline_sec)

            # Playback complete
            if self.ipc:
                self.ipc.send_sync_message(
                    {
                        "type": "playback_complete",
                        "message": "Playback sequence completed successfully",
                    }
                )

            logger.info("Playback sequence completed")

        except Exception as e:
            logger.error(f"Playback sequence error: {e}", exc_info=True)
            if self.ipc:
                self.ipc.send_sync_message({"type": "playback_error", "error": str(e)})
        finally:
            self._playback_running = False
