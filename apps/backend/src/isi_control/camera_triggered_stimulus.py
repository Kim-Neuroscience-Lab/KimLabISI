"""
Camera-Triggered Stimulus Controller

Generates stimulus frames synchronously in response to camera capture events.
This eliminates async timestamp matching by creating perfect 1:1 frame correspondence.

Architecture:
    Camera captures frame N → Triggers stimulus generation → Display shows stimulus N

Scientific rationale:
    - Frame index becomes ground truth (no timestamp matching needed)
    - Consistent display latency (can be calibrated)
    - Eliminates clock drift between camera and stimulus
    - Simplifies data analysis (frame alignment guaranteed)
"""

import threading
from typing import Dict, Any, Optional, Tuple
import numpy as np

from .logging_utils import get_logger

logger = get_logger(__name__)


class CameraTriggeredStimulusController:
    """
    Controls stimulus generation triggered by camera capture events.

    Thread-safe controller that generates stimulus frames on-demand when
    camera captures occur, ensuring perfect temporal alignment.
    """

    def __init__(self, stimulus_generator):
        """
        Initialize camera-triggered stimulus controller.

        Args:
            stimulus_generator: StimulusGenerator instance for frame rendering
        """
        self.stimulus_generator = stimulus_generator

        # State lock for thread safety
        self._state_lock = threading.RLock()

        # Acquisition state
        self._is_active = False
        self._current_direction: Optional[str] = None
        self._frame_index = 0
        self._total_frames = 0

        # Dataset information
        self._dataset_info: Dict[str, Any] = {}

        # Statistics
        self._frames_generated = 0
        self._total_frames_all_directions = 0

        logger.info("CameraTriggeredStimulusController initialized")

    def start_direction(self, direction: str, camera_fps: float) -> Dict[str, Any]:
        """
        Start stimulus generation for a new direction.

        Args:
            direction: Direction to sweep (LR, RL, TB, BT)
            camera_fps: Camera frame rate (determines stimulus advancement speed)

        Returns:
            Dictionary with success status and direction info
        """
        with self._state_lock:
            # Get dataset information for this direction
            # Calculate total frames based on CAMERA fps, not monitor fps
            drift_speed = self.stimulus_generator.stimulus_params.drift_speed_degrees_per_sec

            if direction in ["LR", "RL"]:
                fov_half = self.stimulus_generator.spatial_config.field_of_view_horizontal / 2
                bar_width = self.stimulus_generator.stimulus_params.bar_width_degrees
            else:  # TB, BT
                fov_half = self.stimulus_generator.spatial_config.field_of_view_vertical / 2
                bar_width = self.stimulus_generator.stimulus_params.bar_width_degrees

            total_sweep_degrees = 2 * (fov_half + bar_width)
            sweep_duration = total_sweep_degrees / drift_speed
            total_frames = int(sweep_duration * camera_fps)

            self._dataset_info = self.stimulus_generator.get_dataset_info(
                direction,
                total_frames=total_frames
            )

            if "error" in self._dataset_info:
                logger.error(f"Failed to get dataset info: {self._dataset_info['error']}")
                return {"success": False, "error": self._dataset_info["error"]}

            self._current_direction = direction
            self._frame_index = 0
            self._total_frames = total_frames
            self._is_active = True

            logger.info(
                f"Started camera-triggered stimulus for direction {direction}: "
                f"{total_frames} frames at {camera_fps} fps "
                f"({sweep_duration:.2f}s sweep duration)"
            )

            return {
                "success": True,
                "direction": direction,
                "total_frames": total_frames,
                "sweep_duration_sec": sweep_duration,
                "camera_fps": camera_fps,
                "degrees_per_frame": total_sweep_degrees / total_frames,
            }

    def stop_direction(self) -> Dict[str, Any]:
        """
        Stop stimulus generation for current direction.

        Returns:
            Dictionary with statistics
        """
        with self._state_lock:
            if not self._is_active:
                return {"success": False, "error": "Not active"}

            direction = self._current_direction
            frames_generated = self._frame_index
            expected_frames = self._total_frames

            self._is_active = False
            self._current_direction = None
            self._frame_index = 0
            self._total_frames = 0

            logger.info(
                f"Stopped camera-triggered stimulus for direction {direction}: "
                f"{frames_generated}/{expected_frames} frames generated"
            )

            if frames_generated < expected_frames:
                logger.warning(
                    f"Direction {direction} incomplete: generated {frames_generated} of "
                    f"{expected_frames} expected frames"
                )

            return {
                "success": True,
                "direction": direction,
                "frames_generated": frames_generated,
                "expected_frames": expected_frames,
                "complete": frames_generated >= expected_frames,
            }

    def generate_next_frame(self) -> Tuple[Optional[np.ndarray], Optional[Dict[str, Any]]]:
        """
        Generate next stimulus frame (called when camera captures).

        This is the core triggering method - called synchronously when camera
        captures a frame to generate the corresponding stimulus frame.

        Returns:
            Tuple of (stimulus_frame, metadata) or (None, None) if inactive/complete
        """
        with self._state_lock:
            if not self._is_active:
                logger.debug("Cannot generate frame: controller not active")
                return None, None

            if self._frame_index >= self._total_frames:
                logger.info(
                    f"Stimulus sweep complete for {self._current_direction}: "
                    f"{self._frame_index}/{self._total_frames} frames"
                )
                return None, None

            # Get current state
            direction = self._current_direction
            frame_index = self._frame_index
            total_frames = self._total_frames

            # Calculate angle for this frame
            angle = self.stimulus_generator.calculate_frame_angle(
                direction, frame_index, total_frames
            )

        # Generate frame outside lock (can be slow on some GPUs)
        # NOTE: We do NOT catch exceptions here - if stimulus generation fails,
        # the entire acquisition must stop to preserve scientific validity.
        # Continuing with None frames would create corrupted data.
        frame, metadata = self.stimulus_generator.generate_frame_at_index(
            direction=direction,
            frame_index=frame_index,
            show_bar_mask=True,
            total_frames=total_frames,
        )

        # Update metadata with camera-triggered info
        metadata.update({
            "sync_method": "camera_triggered",
            "camera_frame_index": frame_index,
            "angle_degrees": angle,
        })

        # Increment frame counter with lock
        with self._state_lock:
            self._frame_index += 1
            self._frames_generated += 1

        return frame, metadata

    def get_status(self) -> Dict[str, Any]:
        """
        Get current controller status.

        Returns:
            Dictionary with controller state
        """
        with self._state_lock:
            if not self._is_active:
                return {
                    "active": False,
                    "direction": None,
                    "frame_index": 0,
                    "total_frames": 0,
                    "progress": 0.0,
                }

            progress = (
                (self._frame_index / self._total_frames * 100.0)
                if self._total_frames > 0
                else 0.0
            )

            return {
                "active": self._is_active,
                "direction": self._current_direction,
                "frame_index": self._frame_index,
                "total_frames": self._total_frames,
                "progress": progress,
                "frames_generated_total": self._frames_generated,
            }

    def is_direction_complete(self) -> bool:
        """
        Check if current direction sweep is complete.

        Returns:
            True if all frames generated for current direction
        """
        with self._state_lock:
            if not self._is_active:
                return True
            return self._frame_index >= self._total_frames

    def reset(self) -> None:
        """Reset controller state (for testing or error recovery)."""
        with self._state_lock:
            self._is_active = False
            self._current_direction = None
            self._frame_index = 0
            self._total_frames = 0
            self._dataset_info = {}
            logger.info("CameraTriggeredStimulusController reset")
