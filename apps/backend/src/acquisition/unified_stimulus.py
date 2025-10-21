"""Unified stimulus controller for pre-generated stimulus playback.

Replaces legacy preview_stimulus system with single unified controller
used for both preview and record modes.

Architecture:
- Pre-generates LR + TB directions as grayscale (4x memory savings vs RGBA)
- Derives RL = reversed(LR), BT = reversed(TB) (50% compute savings)
- Stores frames as raw numpy arrays for zero-overhead playback
- Total memory: ~12 GB for all 4 directions (acceptable on modern systems)
- Playback at monitor FPS (VSync-locked, independent from camera)
- Frame correspondence via frame index (camera_frame_N → stimulus_frame_2N)

VSync Architecture:
- Backend: Publishes frames to shared memory at target FPS using time.sleep()
  (software timing with ~0.5-2ms jitter)
- Frontend: Displays frames using requestAnimationFrame() + Canvas API
  (hardware VSync synchronized to monitor refresh, ~50μs precision)
- Result: Frame publication rate is approximate, but actual display timing
  is hardware-synchronized via browser's VSync mechanism
- This decoupled approach is optimal for Electron apps - backend doesn't need
  platform-specific VSync APIs (CVDisplayLink/D3D11/X11), frontend handles it
"""

import threading
import time
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from collections import deque
from pathlib import Path
import json
import numpy as np
import h5py

logger = logging.getLogger(__name__)


@dataclass
class StimulusDisplayEvent:
    """Record of a stimulus frame display event."""
    timestamp_us: int
    frame_index: int
    angle_degrees: float
    direction: str


class UnifiedStimulusController:
    """Unified stimulus controller for pre-generated playback.

    Manages pre-generation, storage, and playback of stimulus frames
    for all four sweep directions with optimized performance.
    """

    def __init__(
        self,
        stimulus_generator,
        param_manager,
        shared_memory,
        ipc
    ):
        """Initialize unified stimulus controller.

        Args:
            stimulus_generator: StimulusGenerator instance for frame generation
            param_manager: ParameterManager instance
            shared_memory: SharedMemoryService for frame publishing
            ipc: MultiChannelIPC for event broadcasting
        """
        self.stimulus_generator = stimulus_generator
        self.param_manager = param_manager
        self.shared_memory = shared_memory
        self.ipc = ipc

        # Pre-generated frame library
        # Structure: {direction: {"frames": [numpy.ndarray (grayscale uint8, H×W)], "angles": [float]}}
        self._frame_library: Dict[str, Dict[str, List]] = {}
        self._library_lock = threading.RLock()
        self._generation_params: Optional[Dict[str, Any]] = None  # Parameters used for current library

        # Playback state
        self._playback_thread: Optional[threading.Thread] = None
        self._playback_stop_event = threading.Event()
        self._is_playing = False
        self._current_direction: Optional[str] = None
        self._current_fps: Optional[float] = None

        # Display event logging (use deque to prevent unbounded growth)
        self._display_log: Dict[str, deque] = {
            "LR": deque(maxlen=10000),
            "RL": deque(maxlen=10000),
            "TB": deque(maxlen=10000),
            "BT": deque(maxlen=10000)
        }
        self._log_lock = threading.RLock()

        # Subscribe to parameter changes for cache invalidation
        self.param_manager.subscribe("stimulus", self._handle_stimulus_params_changed)
        self.param_manager.subscribe("monitor", self._handle_monitor_params_changed)

        logger.info("UnifiedStimulusController initialized")

    def _handle_stimulus_params_changed(self, group_name: str, updates: Dict[str, Any]):
        """Invalidate pre-generated frames when stimulus parameters change.

        Only invalidates if parameters actually changed in value (not just updated with same value).

        Args:
            group_name: Parameter group name ("stimulus")
            updates: Dict of changed parameters
        """
        with self._library_lock:
            # Skip invalidation if library is empty
            if not self._frame_library:
                logger.debug(f"Stimulus parameters updated but library empty, skipping invalidation: {list(updates.keys())}")
                return

            # Skip invalidation if no generation parameters were captured
            if self._generation_params is None:
                logger.warning("Stimulus parameters changed but no generation_params captured, invalidating library")
                self._frame_library.clear()
                self._generation_params = None

                if self.ipc:
                    self.ipc.broadcast({
                        "event": "unified_stimulus_library_invalidated",
                        "reason": "stimulus_params_changed_no_baseline",
                        "changed_params": list(updates.keys())
                    })
                return

            # Compare old vs new parameter values
            old_stimulus_params = self._generation_params.get("stimulus", {})
            changed_values = {}

            for key, new_value in updates.items():
                old_value = old_stimulus_params.get(key)
                if old_value != new_value:
                    changed_values[key] = {"old": old_value, "new": new_value}

            # Only invalidate if values actually changed
            if changed_values:
                logger.info(f"Stimulus parameters changed (values differ), invalidating library: {changed_values}")
                self._frame_library.clear()
                self._generation_params = None

                if self.ipc:
                    self.ipc.broadcast({
                        "event": "unified_stimulus_library_invalidated",
                        "reason": "stimulus_params_changed",
                        "changed_params": list(changed_values.keys()),
                        "changes": changed_values
                    })
            else:
                logger.debug(f"Stimulus parameters updated but values unchanged, keeping library: {list(updates.keys())}")

    def _handle_monitor_params_changed(self, group_name: str, updates: Dict[str, Any]):
        """Invalidate pre-generated frames when monitor parameters change.

        Only invalidates if parameters that affect frame generation change in VALUE
        (not just updated with same value).

        Args:
            group_name: Parameter group name ("monitor")
            updates: Dict of changed parameters
        """
        # Parameters that require regeneration
        regeneration_keys = {
            "monitor_width_px", "monitor_height_px", "monitor_fps",
            "monitor_width_cm", "monitor_height_cm",
            "monitor_distance_cm", "monitor_lateral_angle_deg", "monitor_tilt_angle_deg"
        }

        # Filter to only regeneration-relevant keys
        relevant_updates = {k: v for k, v in updates.items() if k in regeneration_keys}

        if not relevant_updates:
            logger.debug(f"Monitor parameters updated but not regeneration-relevant, keeping library: {list(updates.keys())}")
            return

        with self._library_lock:
            # Skip invalidation if library is empty
            if not self._frame_library:
                logger.debug(f"Monitor parameters updated but library empty, skipping invalidation: {list(relevant_updates.keys())}")
                return

            # Skip invalidation if no generation parameters were captured
            if self._generation_params is None:
                logger.warning("Monitor parameters changed but no generation_params captured, invalidating library")
                self._frame_library.clear()
                self._generation_params = None

                if self.ipc:
                    self.ipc.broadcast({
                        "event": "unified_stimulus_library_invalidated",
                        "reason": "monitor_params_changed_no_baseline",
                        "changed_params": list(relevant_updates.keys())
                    })
                return

            # Compare old vs new parameter values
            old_monitor_params = self._generation_params.get("monitor", {})
            changed_values = {}

            for key, new_value in relevant_updates.items():
                old_value = old_monitor_params.get(key)
                if old_value != new_value:
                    changed_values[key] = {"old": old_value, "new": new_value}

            # Only invalidate if values actually changed
            if changed_values:
                logger.info(f"Monitor parameters changed (values differ), invalidating library: {changed_values}")
                self._frame_library.clear()
                self._generation_params = None

                if self.ipc:
                    self.ipc.broadcast({
                        "event": "unified_stimulus_library_invalidated",
                        "reason": "monitor_params_changed",
                        "changed_params": list(changed_values.keys()),
                        "changes": changed_values
                    })
            else:
                logger.debug(f"Monitor parameters updated but values unchanged, keeping library: {list(relevant_updates.keys())}")

    def pre_generate_all_directions(self) -> Dict[str, any]:
        """Pre-generate all stimulus directions.

        Generates LR + TB as grayscale, derives RL and BT via reversal.
        Stores frames as raw numpy arrays for maximum performance.

        Returns:
            Dict with success status and generation statistics
        """
        try:
            logger.info("Pre-generating stimulus library for all directions...")
            start_time = time.time()

            # Capture current parameters for invalidation checking
            monitor_params = self.param_manager.get_parameter_group("monitor")
            stimulus_params = self.param_manager.get_parameter_group("stimulus")
            generation_params = {
                "monitor": {
                    "monitor_width_px": monitor_params.get("monitor_width_px"),
                    "monitor_height_px": monitor_params.get("monitor_height_px"),
                    "monitor_fps": monitor_params.get("monitor_fps"),
                    "monitor_width_cm": monitor_params.get("monitor_width_cm"),
                    "monitor_height_cm": monitor_params.get("monitor_height_cm"),
                    "monitor_distance_cm": monitor_params.get("monitor_distance_cm"),
                    "monitor_lateral_angle_deg": monitor_params.get("monitor_lateral_angle_deg"),
                    "monitor_tilt_angle_deg": monitor_params.get("monitor_tilt_angle_deg"),
                },
                "stimulus": dict(stimulus_params)
            }

            # Statistics tracking
            stats = {
                "total_frames": 0,
                "total_memory_bytes": 0,
                "directions": {}
            }

            with self._library_lock:
                # Generate primary directions (LR, TB) as grayscale
                for direction_index, direction in enumerate(["LR", "TB"]):
                    logger.info(f"Generating {direction} direction...")
                    dir_start = time.time()

                    # Broadcast direction start
                    if self.ipc:
                        self.ipc.send_sync_message({
                            "type": "unified_stimulus_pregeneration_progress",
                            "phase": "generating",
                            "direction": direction,
                            "direction_index": direction_index,
                            "total_directions": 2,
                            "current_frame": 0,
                            "timestamp": time.time()
                        })

                    # Generate grayscale frames
                    frames, angles = self.stimulus_generator.generate_sweep(
                        direction=direction,
                        output_format="grayscale"
                    )

                    # Calculate memory size from numpy arrays
                    total_size = sum(frame.nbytes for frame in frames)

                    # Store frames directly (no compression)
                    self._frame_library[direction] = {
                        "frames": frames,  # List of numpy arrays
                        "angles": angles
                    }

                    dir_duration = time.time() - dir_start
                    avg_size = total_size / len(frames)

                    logger.info(
                        f"{direction} complete: {len(frames)} frames, "
                        f"{total_size / 1024 / 1024:.1f} MB, "
                        f"avg {avg_size / 1024:.1f} KB/frame, "
                        f"{dir_duration:.1f}s"
                    )

                    # Broadcast direction complete
                    if self.ipc:
                        self.ipc.send_sync_message({
                            "type": "unified_stimulus_pregeneration_progress",
                            "phase": "direction_complete",
                            "direction": direction,
                            "direction_index": direction_index,
                            "total_directions": 2,
                            "frames": len(frames),
                            "size_bytes": total_size,
                            "duration_sec": dir_duration,
                            "timestamp": time.time()
                        })

                    stats["total_frames"] += len(frames)
                    stats["total_memory_bytes"] += total_size
                    stats["directions"][direction] = {
                        "frames": len(frames),
                        "size_bytes": total_size,
                        "avg_frame_bytes": avg_size,
                        "duration_sec": dir_duration
                    }

                # Derive reversed directions (RL from LR, BT from TB)
                self._frame_library["RL"] = {
                    "frames": list(reversed(self._frame_library["LR"]["frames"])),
                    "angles": list(reversed(self._frame_library["LR"]["angles"]))
                }
                self._frame_library["BT"] = {
                    "frames": list(reversed(self._frame_library["TB"]["frames"])),
                    "angles": list(reversed(self._frame_library["TB"]["angles"]))
                }

                logger.info(f"Derived RL from reversed LR ({len(self._frame_library['RL']['frames'])} frames)")
                logger.info(f"Derived BT from reversed TB ({len(self._frame_library['BT']['frames'])} frames)")

                # Copy stats for derived directions
                stats["directions"]["RL"] = stats["directions"]["LR"].copy()
                stats["directions"]["BT"] = stats["directions"]["TB"].copy()
                stats["total_frames"] *= 2  # LR+RL and TB+BT

                total_duration = time.time() - start_time
                total_mb = stats["total_memory_bytes"] / 1024 / 1024

                logger.info(
                    f"Pre-generation complete: {stats['total_frames']} total frames, "
                    f"{total_mb:.1f} MB, {total_duration:.1f}s"
                )

                # Store generation parameters for smart invalidation
                self._generation_params = generation_params
                logger.debug(f"Captured generation parameters for invalidation checking")

                # Broadcast final completion
                if self.ipc:
                    self.ipc.send_sync_message({
                        "type": "unified_stimulus_pregeneration_complete",
                        "statistics": stats,
                        "total_duration_sec": total_duration,
                        "timestamp": time.time()
                    })

                return {
                    "success": True,
                    "statistics": stats,
                    "total_duration_sec": total_duration
                }

        except Exception as e:
            logger.error(f"Pre-generation failed: {e}", exc_info=True)

            # Broadcast failure
            if self.ipc:
                self.ipc.send_sync_message({
                    "type": "unified_stimulus_pregeneration_failed",
                    "error": str(e),
                    "timestamp": time.time()
                })

            return {
                "success": False,
                "error": str(e)
            }

    def start_playback(self, direction: str, monitor_fps: float) -> Dict[str, any]:
        """Start VSync-locked playback loop for given direction.

        Args:
            direction: Direction to play ("LR", "RL", "TB", "BT")
            monitor_fps: Monitor refresh rate for VSync timing

        Returns:
            Dict with success status
        """
        # CRITICAL SAFETY: Validate FPS parameter
        if not isinstance(monitor_fps, (int, float)) or monitor_fps <= 0:
            error_msg = f"Invalid monitor_fps: {monitor_fps}. Must be a positive number."
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

        # CRITICAL SAFETY: Check if already playing
        if self._is_playing:
            return {
                "success": False,
                "error": "Playback already running - stop current playback first"
            }

        # CRITICAL SAFETY: Validate direction
        valid_directions = {"LR", "RL", "TB", "BT"}
        if direction not in valid_directions:
            error_msg = f"Invalid direction: {direction}. Must be one of {valid_directions}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

        # Validate direction exists in library
        with self._library_lock:
            if direction not in self._frame_library:
                return {
                    "success": False,
                    "error": f"Direction {direction} not pre-generated. Call pre_generate_all_directions() first."
                }

            if len(self._frame_library[direction]["frames"]) == 0:
                return {
                    "success": False,
                    "error": f"Direction {direction} has no frames. Re-run pre_generate_all_directions()."
                }

        # Start playback thread
        self._playback_stop_event.clear()
        self._is_playing = True
        self._current_direction = direction
        self._current_fps = monitor_fps

        self._playback_thread = threading.Thread(
            target=self._playback_loop,
            args=(direction, monitor_fps),
            name=f"StimulusPlayback-{direction}",
            daemon=True
        )
        self._playback_thread.start()

        logger.info(f"Started playback: {direction} at {monitor_fps} fps")

        return {
            "success": True,
            "direction": direction,
            "fps": monitor_fps,
            "total_frames": len(self._frame_library[direction]["frames"])
        }

    def stop_playback(self) -> Dict[str, any]:
        """Stop current playback loop.

        Returns:
            Dict with success status
        """
        if not self._is_playing:
            return {
                "success": False,
                "error": "No playback running"
            }

        logger.info(f"Stopping playback: {self._current_direction}")

        # Signal thread to stop
        self._playback_stop_event.set()
        self._is_playing = False

        # Wait for thread to finish
        if self._playback_thread:
            self._playback_thread.join(timeout=2.0)
            if self._playback_thread.is_alive():
                logger.warning("Playback thread did not stop cleanly")

        direction = self._current_direction
        self._current_direction = None
        self._current_fps = None

        return {
            "success": True,
            "message": f"Playback stopped: {direction}"
        }

    def _playback_loop(self, direction: str, fps: float):
        """Playback loop running in background thread.

        Publishes pre-generated frames at monitor FPS with VSync timing.

        Args:
            direction: Direction to play
            fps: Target playback frame rate
        """
        try:
            frame_duration_sec = 1.0 / fps

            with self._library_lock:
                frames = self._frame_library[direction]["frames"]
                angles = self._frame_library[direction]["angles"]
                total_frames = len(frames)

            logger.info(
                f"Playback loop started: {direction}, {total_frames} frames at {fps} fps "
                f"(frame interval: {frame_duration_sec * 1000:.2f}ms)"
            )

            frame_index = 0
            frames_published = 0  # Counter for diagnostic logging

            while not self._playback_stop_event.is_set():
                frame_start = time.time()

                # Get grayscale frame (already in memory as numpy array)
                # NO COMPUTATION - just direct memory lookup!
                grayscale = frames[frame_index]

                # Publish to shared memory - NO RGBA conversion!
                timestamp_us = int(time.time() * 1_000_000)
                metadata = {
                    "frame_index": frame_index,
                    "total_frames": total_frames,
                    "angle_degrees": angles[frame_index],
                    "direction": direction,
                    "timestamp_us": timestamp_us,
                    "channels": 1  # Tell frontend this is grayscale (1 channel)
                }

                frame_id = self.shared_memory.write_frame(grayscale, metadata)
                frames_published += 1

                # DIAGNOSTIC: Log every 60 frames to confirm publishing
                if frames_published % 60 == 0:
                    logger.info(
                        f"Playback progress: {frames_published} frames published, "
                        f"current frame_index={frame_index}, "
                        f"angle={angles[frame_index]:.1f}°, "
                        f"frame_id={frame_id}"
                    )

                # Log display event
                with self._log_lock:
                    event = StimulusDisplayEvent(
                        timestamp_us=timestamp_us,
                        frame_index=frame_index,
                        angle_degrees=angles[frame_index],
                        direction=direction
                    )
                    self._display_log[direction].append(event)

                # Advance to next frame (loop)
                frame_index = (frame_index + 1) % total_frames

                # Sleep for remaining frame time to control publication rate
                # NOTE: This controls frame *publication* rate to shared memory.
                # The frontend uses requestAnimationFrame() for hardware VSync display.
                # Software timing here has ~0.5-2ms jitter, but frontend's hardware VSync
                # ensures actual display happens at exact monitor refresh intervals.
                elapsed = time.time() - frame_start
                sleep_time = max(0, frame_duration_sec - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    logger.warning(
                        f"Frame {frame_index} took {elapsed * 1000:.2f}ms "
                        f"(target: {frame_duration_sec * 1000:.2f}ms)"
                    )

            logger.info(f"Playback loop stopped: {direction}")

        except Exception as e:
            logger.error(f"Playback loop error: {e}", exc_info=True)
            self._is_playing = False

    def get_frame_for_viewport(
        self,
        direction: str,
        frame_index: int
    ) -> Optional[np.ndarray]:
        """Get grayscale frame for viewport display.

        Used by frontend viewports for scrubbing and preview.
        Returns grayscale frame directly - NO RUNTIME CONVERSION!

        Args:
            direction: Direction to retrieve from
            frame_index: Frame index to retrieve

        Returns:
            Grayscale frame array (H x W, uint8) or None if not available
        """
        with self._library_lock:
            if direction not in self._frame_library:
                logger.warning(f"Direction {direction} not in library")
                return None

            frames = self._frame_library[direction]["frames"]
            if frame_index < 0 or frame_index >= len(frames):
                logger.warning(f"Frame index {frame_index} out of range for {direction}")
                return None

            # Return grayscale frame directly - NO COMPUTATION!
            return frames[frame_index]

    def is_playing(self) -> bool:
        """Check if playback is currently active.

        Returns:
            True if playback running
        """
        return self._is_playing

    def get_display_log(self, direction: str) -> List[StimulusDisplayEvent]:
        """Get logged display events for given direction.

        Args:
            direction: Direction to get log for

        Returns:
            List of display events (copy)
        """
        with self._log_lock:
            return list(self._display_log.get(direction, []))

    def clear_display_log(self, direction: Optional[str] = None):
        """Clear display event log.

        Args:
            direction: Direction to clear, or None to clear all
        """
        with self._log_lock:
            if direction:
                self._display_log[direction] = deque(maxlen=10000)
            else:
                for d in self._display_log:
                    self._display_log[d] = deque(maxlen=10000)

    def get_stimulus_frame_index_for_camera_frame(
        self,
        camera_frame_index: int,
        camera_fps: float,
        monitor_fps: float
    ) -> int:
        """Calculate stimulus frame index corresponding to camera frame.

        Uses frame-index-based correspondence:
        camera_frame_N → stimulus_frame_M where M = N * (monitor_fps / camera_fps)

        This assumes both camera and stimulus started at the same time (synchronized).

        Args:
            camera_frame_index: Camera frame index (0-based)
            camera_fps: Camera frame rate
            monitor_fps: Monitor (stimulus) frame rate

        Returns:
            Stimulus frame index (0-based)
        """
        # Validate FPS values
        if camera_fps <= 0 or monitor_fps <= 0:
            logger.error(f"Invalid FPS values: camera={camera_fps}, monitor={monitor_fps}")
            return 0

        # Calculate frame rate ratio
        fps_ratio = monitor_fps / camera_fps

        # Calculate stimulus frame index
        stimulus_frame_index = int(camera_frame_index * fps_ratio)

        return stimulus_frame_index

    def get_stimulus_angle_for_camera_frame(
        self,
        camera_frame_index: int,
        camera_fps: float,
        monitor_fps: float,
        direction: str
    ) -> Optional[float]:
        """Get stimulus angle (in degrees) for given camera frame.

        Args:
            camera_frame_index: Camera frame index
            camera_fps: Camera frame rate
            monitor_fps: Monitor frame rate
            direction: Stimulus direction

        Returns:
            Stimulus angle in degrees, or None if not available
        """
        # Calculate corresponding stimulus frame index
        stimulus_frame_index = self.get_stimulus_frame_index_for_camera_frame(
            camera_frame_index, camera_fps, monitor_fps
        )

        # Get angle from library
        with self._library_lock:
            if direction not in self._frame_library:
                logger.warning(f"Direction {direction} not in library")
                return None

            angles = self._frame_library[direction].get("angles", [])
            if stimulus_frame_index < 0 or stimulus_frame_index >= len(angles):
                logger.warning(
                    f"Stimulus frame index {stimulus_frame_index} out of range "
                    f"for direction {direction} (0-{len(angles)-1})"
                )
                return None

            return angles[stimulus_frame_index]

    def display_baseline(self) -> Dict[str, Any]:
        """Display background luminance screen (for baseline/between phases).

        Reads monitor dimensions and background_luminance from parameters
        and publishes a solid grayscale frame to shared memory.

        Returns:
            Dict with success status
        """
        try:
            # Get monitor and stimulus parameters
            monitor_params = self.param_manager.get_parameter_group("monitor")
            stimulus_params = self.param_manager.get_parameter_group("stimulus")

            if not monitor_params or not stimulus_params:
                error_msg = "Cannot display baseline: monitor or stimulus parameters not available"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }

            # Validate monitor dimensions
            width = monitor_params.get("monitor_width_px")
            if not isinstance(width, int) or width <= 0:
                error_msg = f"Invalid monitor_width_px: {width}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }

            height = monitor_params.get("monitor_height_px")
            if not isinstance(height, int) or height <= 0:
                error_msg = f"Invalid monitor_height_px: {height}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }

            # Get background luminance from parameters
            luminance = stimulus_params.get("background_luminance")

            # Validate background_luminance explicitly
            if luminance is None or not isinstance(luminance, (int, float)) or not (0.0 <= luminance <= 1.0):
                raise RuntimeError(
                    "background_luminance is required but not configured in param_manager. "
                    "Background luminance must be between 0.0 (black) and 1.0 (white). "
                    f"Please set stimulus.background_luminance parameter. Received: {luminance}"
                )

            # Create grayscale baseline frame (1 channel, NOT RGBA!)
            luminance_uint8 = int(np.clip(luminance * 255, 0, 255))
            frame = np.full((height, width), luminance_uint8, dtype=np.uint8)

            # Publish to shared memory with channels metadata
            metadata = {
                "frame_index": 0,
                "direction": "baseline",
                "angle_degrees": 0.0,
                "total_frames": 1,
                "channels": 1  # Grayscale frame
            }
            self.shared_memory.write_frame(frame, metadata)
            logger.debug(f"Baseline displayed: {width}x{height} at luminance {luminance} (grayscale)")

            return {
                "success": True,
                "width": width,
                "height": height,
                "luminance": luminance
            }

        except Exception as e:
            error_msg = f"Failed to display baseline: {e}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg
            }

    def get_status(self) -> Dict[str, any]:
        """Get current controller status.

        Returns:
            Dict with status information
        """
        with self._library_lock:
            library_status = {
                direction: {
                    "frames": len(data["frames"]),
                    "memory_mb": sum(f.nbytes for f in data["frames"]) / 1024 / 1024
                }
                for direction, data in self._frame_library.items()
            }

        return {
            "is_playing": self._is_playing,
            "current_direction": self._current_direction,
            "current_fps": self._current_fps,
            "library_loaded": len(self._frame_library) > 0,
            "library_status": library_status
        }

    def save_library_to_disk(self, save_path: Optional[str] = None) -> Dict[str, Any]:
        """Save pre-generated stimulus library to disk with generation parameters.

        Saves frames as HDF5 files with embedded parameters for validation on load.

        Args:
            save_path: Directory to save library (defaults to data/stimulus_library)

        Returns:
            Dict with success status and file paths
        """
        try:
            with self._library_lock:
                # Validate library exists
                if not self._frame_library:
                    return {
                        "success": False,
                        "error": "No stimulus library loaded. Run pre-generation first."
                    }

                if not self._generation_params:
                    return {
                        "success": False,
                        "error": "No generation parameters captured. Cannot save without parameter metadata."
                    }

                # Determine save path
                if save_path is None:
                    backend_root = Path(__file__).resolve().parents[2]
                    save_path = backend_root / "data" / "stimulus_library"
                else:
                    save_path = Path(save_path)

                save_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Saving stimulus library to {save_path}")

                saved_files = []

                # Save each direction
                for direction in ["LR", "TB", "RL", "BT"]:
                    if direction not in self._frame_library:
                        continue

                    direction_data = self._frame_library[direction]
                    frames = direction_data["frames"]
                    angles = direction_data["angles"]

                    # Save as HDF5
                    h5_path = save_path / f"{direction}_frames.h5"

                    with h5py.File(h5_path, 'w') as f:
                        # Store frames as grayscale uint8
                        frames_array = np.array(frames, dtype=np.uint8)
                        f.create_dataset(
                            'frames',
                            data=frames_array,
                            compression='gzip',
                            compression_opts=4
                        )

                        # Store angles
                        f.create_dataset('angles', data=np.array(angles, dtype=np.float32))

                        # Store generation parameters as attributes
                        f.attrs['generation_params'] = json.dumps(self._generation_params)
                        f.attrs['direction'] = direction
                        f.attrs['num_frames'] = len(frames)
                        f.attrs['frame_shape'] = frames[0].shape if len(frames) > 0 else (0, 0)

                    saved_files.append(str(h5_path))
                    logger.info(f"  Saved {direction}: {len(frames)} frames to {h5_path.name}")

                # Save metadata JSON
                metadata_path = save_path / "library_metadata.json"
                metadata = {
                    "generation_params": self._generation_params,
                    "directions": list(self._frame_library.keys()),
                    "timestamp": time.time(),
                    "total_frames": sum(len(self._frame_library[d]["frames"]) for d in self._frame_library),
                }

                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)

                saved_files.append(str(metadata_path))

                logger.info(f"Stimulus library saved successfully: {len(saved_files)} files")

                return {
                    "success": True,
                    "save_path": str(save_path),
                    "files": saved_files,
                    "metadata": metadata
                }

        except Exception as e:
            logger.error(f"Failed to save stimulus library: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def load_library_from_disk(self, load_path: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
        """Load pre-generated stimulus library from disk with parameter validation.

        Validates that saved parameters match current parameters before loading.

        Args:
            load_path: Directory to load library from (defaults to data/stimulus_library)
            force: If True, load without parameter validation (dangerous!)

        Returns:
            Dict with success status and validation results
        """
        try:
            # Determine load path
            if load_path is None:
                backend_root = Path(__file__).resolve().parents[2]
                load_path = backend_root / "data" / "stimulus_library"
            else:
                load_path = Path(load_path)

            if not load_path.exists():
                return {
                    "success": False,
                    "error": f"Library path does not exist: {load_path}"
                }

            # Load metadata
            metadata_path = load_path / "library_metadata.json"
            if not metadata_path.exists():
                return {
                    "success": False,
                    "error": f"Library metadata not found: {metadata_path}"
                }

            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            saved_params = metadata.get("generation_params")
            if not saved_params:
                return {
                    "success": False,
                    "error": "No generation parameters found in saved library"
                }

            # Get current parameters
            current_monitor = self.param_manager.get_parameter_group("monitor")
            current_stimulus = self.param_manager.get_parameter_group("stimulus")
            current_params = {
                "monitor": {
                    "monitor_width_px": current_monitor.get("monitor_width_px"),
                    "monitor_height_px": current_monitor.get("monitor_height_px"),
                    "monitor_fps": current_monitor.get("monitor_fps"),
                    "monitor_width_cm": current_monitor.get("monitor_width_cm"),
                    "monitor_height_cm": current_monitor.get("monitor_height_cm"),
                    "monitor_distance_cm": current_monitor.get("monitor_distance_cm"),
                    "monitor_lateral_angle_deg": current_monitor.get("monitor_lateral_angle_deg"),
                    "monitor_tilt_angle_deg": current_monitor.get("monitor_tilt_angle_deg"),
                },
                "stimulus": dict(current_stimulus)
            }

            # Validate parameters match (unless force=True)
            if not force:
                mismatches = self._compare_parameters(saved_params, current_params)

                if mismatches:
                    return {
                        "success": False,
                        "error": "Parameter mismatch detected",
                        "validation_failed": True,
                        "mismatches": mismatches,
                        "saved_params": saved_params,
                        "current_params": current_params
                    }

            # Parameters match (or force=True), proceed with loading
            logger.info(f"Loading stimulus library from {load_path}")

            with self._library_lock:
                # Clear existing library
                self._frame_library.clear()

                loaded_stats = {}

                # Load each direction
                for direction in ["LR", "TB", "RL", "BT"]:
                    h5_path = load_path / f"{direction}_frames.h5"

                    if not h5_path.exists():
                        logger.warning(f"Missing direction file: {h5_path}")
                        continue

                    with h5py.File(h5_path, 'r') as f:
                        # Load frames
                        frames_array = f['frames'][:]
                        angles_array = f['angles'][:]

                        # Convert to list of numpy arrays (matching in-memory format)
                        frames = [frames_array[i] for i in range(len(frames_array))]
                        angles = angles_array.tolist()

                        self._frame_library[direction] = {
                            "frames": frames,
                            "angles": angles
                        }

                        loaded_stats[direction] = {
                            "frames": len(frames),
                            "memory_mb": sum(f.nbytes for f in frames) / 1024 / 1024
                        }

                        logger.info(f"  Loaded {direction}: {len(frames)} frames")

                # Store generation parameters
                self._generation_params = saved_params

                logger.info(f"Stimulus library loaded successfully: {len(self._frame_library)} directions")

                return {
                    "success": True,
                    "load_path": str(load_path),
                    "directions_loaded": list(self._frame_library.keys()),
                    "library_status": loaded_stats,
                    "generation_params": saved_params,
                    "validation_passed": True
                }

        except Exception as e:
            logger.error(f"Failed to load stimulus library: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def _compare_parameters(self, saved_params: Dict, current_params: Dict) -> Dict[str, Any]:
        """Compare saved and current parameters to detect mismatches.

        Args:
            saved_params: Parameters from saved library
            current_params: Current system parameters

        Returns:
            Dict of mismatches (empty if all match)
        """
        mismatches = {}

        # Compare monitor parameters
        for key in saved_params.get("monitor", {}).keys():
            saved_val = saved_params["monitor"].get(key)
            current_val = current_params["monitor"].get(key)

            if saved_val != current_val:
                mismatches[f"monitor.{key}"] = {
                    "saved": saved_val,
                    "current": current_val
                }

        # Compare stimulus parameters
        for key in saved_params.get("stimulus", {}).keys():
            saved_val = saved_params["stimulus"].get(key)
            current_val = current_params["stimulus"].get(key)

            if saved_val != current_val:
                mismatches[f"stimulus.{key}"] = {
                    "saved": saved_val,
                    "current": current_val
                }

        return mismatches

    def cleanup(self):
        """Stop playback and release resources."""
        if self._is_playing:
            self.stop_playback()

        # Unsubscribe from parameter changes
        try:
            self.param_manager.unsubscribe("stimulus", self._handle_stimulus_params_changed)
            self.param_manager.unsubscribe("monitor", self._handle_monitor_params_changed)
        except Exception as e:
            logger.warning(f"Error unsubscribing from parameters: {e}")

        with self._library_lock:
            self._frame_library.clear()
            self._generation_params = None

        logger.info("UnifiedStimulusController cleaned up")
