"""
Unified Stimulus Generator
Handles both on-demand frame generation for frontend preview and full dataset generation for acquisition
"""

import numpy as np
import io
import time
import threading
from PIL import Image
from typing import Dict, Tuple, Optional, Any
from dataclasses import dataclass
import logging
from logging import Logger


# Import existing spatial transformation components
from .spherical_transform import SphericalTransform

logger: Logger = logging.getLogger(__name__)


@dataclass
class SpatialConfiguration:
    """3D spatial configuration between mouse and monitor"""

    monitor_distance_cm: float
    monitor_angle_degrees: float
    screen_width_pixels: int
    screen_height_pixels: int
    screen_width_cm: float
    screen_height_cm: float
    fps: int

    @property
    def field_of_view_horizontal(self) -> float:
        """Calculate horizontal field of view from screen width and distance"""
        return (
            2
            * np.degrees(
                np.arctan(self.screen_width_cm / (2 * self.monitor_distance_cm))
            )
            if self.screen_width_cm and self.monitor_distance_cm
            else 0.0
        )

    @property
    def field_of_view_vertical(self) -> float:
        """Calculate vertical field of view from screen height and distance"""
        return (
            2
            * np.degrees(
                np.arctan(self.screen_height_cm / (2 * self.monitor_distance_cm))
            )
            if self.screen_height_cm and self.monitor_distance_cm
            else 0.0
        )

    @property
    def pixels_per_degree_horizontal(self) -> float:
        return (
            self.screen_width_pixels / self.field_of_view_horizontal
            if self.screen_width_pixels and self.field_of_view_horizontal
            else 0.0
        )

    @property
    def pixels_per_degree_vertical(self) -> float:
        return (
            self.screen_height_pixels / self.field_of_view_vertical
            if self.screen_height_pixels and self.field_of_view_vertical
            else 0.0
        )


@dataclass
class StimulusParameters:
    """Stimulus generation parameters"""

    bar_width_degrees: float
    drift_speed_degrees_per_sec: float
    checkerboard_size_degrees: float
    flicker_frequency_hz: float
    contrast: float
    background_luminance: float


class StimulusGenerator:
    """Unified stimulus generation for both on-demand frames and full datasets"""

    def __init__(
        self,
        spatial_config: Optional[SpatialConfiguration] = None,
        stimulus_params: Optional[StimulusParameters] = None,
    ):
        # Must provide configurations - no defaults
        if not spatial_config or not stimulus_params:
            raise ValueError("StimulusGenerator requires spatial_config and stimulus_params from parameter manager")

        self.spatial_config: SpatialConfiguration = spatial_config
        self.stimulus_params: StimulusParameters = stimulus_params

        # Initialize spherical transform and coordinate grids
        self.spherical_transform = None
        self.X_pixels = None
        self.Y_pixels = None
        self.X_degrees = None
        self.Y_degrees = None
        self._setup_spherical_transform()
        self._setup_coordinate_grids()

        logger.info(f"StimulusGenerator initialized:")
        logger.info(
            f"  Screen: {self.spatial_config.screen_width_pixels}x{self.spatial_config.screen_height_pixels}"
        )
        logger.info(
            f"  FoV: {self.spatial_config.field_of_view_horizontal:.1f}° x {self.spatial_config.field_of_view_vertical:.1f}°"
        )
        logger.info(f"  Distance: {self.spatial_config.monitor_distance_cm} cm")

    def _setup_spherical_transform(self):
        """Initialize spherical transform with spatial configuration"""
        self.spherical_transform = SphericalTransform(
            monitor_distance_cm=self.spatial_config.monitor_distance_cm,
            screen_width_cm=self.spatial_config.screen_width_cm,
            screen_height_cm=self.spatial_config.screen_height_cm,
        )

    def _setup_coordinate_grids(self):
        """Setup coordinate grids exactly like old backend pattern generator"""
        width = self.spatial_config.screen_width_pixels
        height = self.spatial_config.screen_height_pixels

        # Pixel coordinates
        x_pixels = np.arange(width)
        y_pixels = np.arange(height)
        self.X_pixels, self.Y_pixels = np.meshgrid(x_pixels, y_pixels)

        # Convert to degrees from center - exact old backend approach
        center_x = width / 2
        center_y = height / 2

        pixels_per_degree_h = self.spatial_config.pixels_per_degree_horizontal
        pixels_per_degree_v = self.spatial_config.pixels_per_degree_vertical

        self.X_degrees = (self.X_pixels - center_x) / pixels_per_degree_h
        self.Y_degrees = (self.Y_pixels - center_y) / pixels_per_degree_v

    def get_dataset_info(self, direction: str, num_cycles: int = 3) -> Dict[str, Any]:
        """Get dataset information without generating frames"""
        try:
            # Calculate the actual total sweep distance including off-screen portions
            bar_full_width = self.stimulus_params.bar_width_degrees

            if direction in ["LR", "RL"]:
                # Vertical bars - sweep through azimuth plus off-screen extensions
                fov_half = self.spatial_config.field_of_view_horizontal / 2
                total_sweep_degrees = 2 * (fov_half + bar_full_width)
            else:  # TB, BT
                # Horizontal bars - sweep through altitude plus off-screen extensions
                fov_half = self.spatial_config.field_of_view_vertical / 2
                total_sweep_degrees = 2 * (fov_half + bar_full_width)

            cycle_duration = (
                total_sweep_degrees / self.stimulus_params.drift_speed_degrees_per_sec
            )
            total_duration = cycle_duration * num_cycles
            total_frames = int(total_duration * self.spatial_config.fps)

            # Calculate start and end angles
            start_angle, end_angle = self._calculate_angle_range(direction)

            return {
                "total_frames": total_frames,
                "duration_sec": total_duration,
                "start_angle": start_angle,
                "end_angle": end_angle,
                "cycle_duration": cycle_duration,
                "sweep_degrees": total_sweep_degrees,
                "fps": self.spatial_config.fps,
            }
        except Exception as e:
            logger.error(f"Error getting dataset info: {e}")
            return {"error": str(e)}

    def _calculate_angle_range(self, direction: str) -> Tuple[float, float]:
        """Calculate start and end angles for the given direction"""
        bar_full_width = self.stimulus_params.bar_width_degrees

        if direction in ["LR", "RL"]:
            max_angle = self.spatial_config.field_of_view_horizontal / 2
            start_angle = (
                (max_angle + bar_full_width)
                if direction == "LR"
                else -(max_angle + bar_full_width)
            )
            end_angle = (
                -(max_angle + bar_full_width)
                if direction == "LR"
                else (max_angle + bar_full_width)
            )
        else:  # TB, BT
            max_angle = self.spatial_config.field_of_view_vertical / 2
            start_angle = (
                -(max_angle + bar_full_width)
                if direction == "TB"
                else (max_angle + bar_full_width)
            )
            end_angle = (
                (max_angle + bar_full_width)
                if direction == "TB"
                else -(max_angle + bar_full_width)
            )

        return start_angle, end_angle

    def calculate_frame_angle(
        self, direction: str, frame_index: int, total_frames: int
    ) -> float:
        """Convert frame index to spatial angle"""
        start_angle, end_angle = self._calculate_angle_range(direction)

        if total_frames <= 1:
            return start_angle

        # Linear interpolation between start and end angles
        progress = frame_index / (total_frames - 1)
        angle = start_angle + progress * (end_angle - start_angle)
        return angle

    def generate_frame_at_angle(
        self,
        direction: str,
        angle: float,
        show_bar_mask: bool = True,
        frame_index: int = 0,
    ) -> np.ndarray:
        """Generate a single frame at the specified angle"""
        h, w = (
            self.spatial_config.screen_height_pixels,
            self.spatial_config.screen_width_pixels,
        )

        # Start with background
        frame = np.full(
            (h, w), self.stimulus_params.background_luminance, dtype=np.float32
        )

        if not show_bar_mask:
            # Generate checkerboard pattern across entire frame without bar mask
            checkerboard = self._generate_checkerboard_pattern(w, h, frame_index)
            frame = checkerboard
        else:
            # Get spherical coordinates for bar positioning
            pixel_azimuth, pixel_altitude = (
                self.spherical_transform.screen_to_spherical_coordinates(
                    self.X_degrees, self.Y_degrees, self.spatial_config
                )
            )

            # Create bar mask based on spherical coordinates
            if direction in ["LR", "RL"]:
                # Vertical bar moving horizontally - use azimuth coordinates
                coordinate_map = pixel_azimuth
            else:  # TB, BT
                # Horizontal bar moving vertically - use altitude coordinates
                coordinate_map = pixel_altitude

            # Create bar mask in spherical space
            bar_half_width = self.stimulus_params.bar_width_degrees / 2
            bar_mask = np.abs(coordinate_map - angle) <= bar_half_width

            # Generate checkerboard pattern within bar
            if np.any(bar_mask):
                checkerboard = self._generate_checkerboard_pattern(w, h, frame_index)
                frame[bar_mask] = checkerboard[bar_mask]

        # Convert to uint8
        frame_uint8 = np.clip(frame * 255, 0, 255).astype(np.uint8)
        return frame_uint8

    def generate_frame_at_index(
        self,
        direction: str,
        frame_index: int,
        show_bar_mask: bool = True,
        num_cycles: int = 3,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Generate a single frame at the specified frame index"""
        try:
            # Get dataset info to calculate total frames
            dataset_info = self.get_dataset_info(direction, num_cycles)
            if "error" in dataset_info:
                raise Exception(dataset_info["error"])

            total_frames = dataset_info["total_frames"]

            # Clamp frame index to valid range
            frame_index = max(0, min(frame_index, total_frames - 1))

            # Calculate angle for this frame
            angle = self.calculate_frame_angle(direction, frame_index, total_frames)

            # Generate the frame
            frame = self.generate_frame_at_angle(
                direction, angle, show_bar_mask, frame_index
            )

            # Return frame with metadata
            metadata = {
                "frame_index": frame_index,
                "total_frames": total_frames,
                "angle_degrees": angle,
                "direction": direction,
                "show_bar_mask": show_bar_mask,
            }

            return frame, metadata

        except Exception as e:
            logger.error(f"Error generating frame at index {frame_index}: {e}")
            raise


    def _generate_checkerboard_pattern(
        self, w: int, h: int, frame_index: int
    ) -> np.ndarray:
        """Generate counter-phase checkerboard pattern in spherical coordinates"""
        # Get spherical coordinates for checkerboard pattern
        pixel_azimuth, pixel_altitude = (
            self.spherical_transform.screen_to_spherical_coordinates(
                self.X_degrees, self.Y_degrees, self.spatial_config
            )
        )

        # Use checkerboard size in degrees directly in spherical space
        checker_size_degrees = self.stimulus_params.checkerboard_size_degrees

        # Create checkerboard pattern in spherical coordinates
        azimuth_checks = (pixel_azimuth / checker_size_degrees).astype(int)
        altitude_checks = (pixel_altitude / checker_size_degrees).astype(int)
        checkerboard = (azimuth_checks + altitude_checks) % 2

        # Counter-phase flickering using parameter system
        fps = self.spatial_config.fps
        flicker_frequency_hz = self.stimulus_params.flicker_frequency_hz
        flicker_period_frames = (
            int(fps / flicker_frequency_hz)
            if flicker_frequency_hz > 0
            else float("inf")
        )

        if flicker_period_frames != float("inf"):
            phase_flip = (frame_index // flicker_period_frames) % 2
            if phase_flip:
                checkerboard = 1 - checkerboard

        # Apply contrast - alternating between black and white
        pattern = np.where(
            checkerboard,
            self.stimulus_params.background_luminance + self.stimulus_params.contrast,
            self.stimulus_params.background_luminance - self.stimulus_params.contrast,
        )

        return np.clip(pattern, 0, 1)

    def generate_full_dataset(
        self, direction: str, num_cycles: int = 10
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate full frame sequence for acquisition"""
        try:
            logger.info(f"Generating {direction} drifting bar stimulus dataset...")

            # Get dataset parameters
            dataset_info = self.get_dataset_info(direction, num_cycles)
            if "error" in dataset_info:
                raise Exception(dataset_info["error"])

            total_frames = dataset_info["total_frames"]
            start_angle = dataset_info["start_angle"]
            end_angle = dataset_info["end_angle"]

            # Generate angle progression
            angles = np.linspace(start_angle, end_angle, total_frames)
            timestamps = np.arange(total_frames) * (
                1_000_000 // self.spatial_config.fps
            )

            logger.info(f"  Total frames: {total_frames}")
            logger.info(f"  Duration: {dataset_info['duration_sec']:.1f}s")
            logger.info(f"  Angle range: {start_angle:.1f}° to {end_angle:.1f}°")

            # Generate all frames
            h, w = (
                self.spatial_config.screen_height_pixels,
                self.spatial_config.screen_width_pixels,
            )
            frames = np.zeros((total_frames, h, w), dtype=np.uint8)

            # Get spherical coordinates once for efficiency
            pixel_azimuth, pixel_altitude = (
                self.spherical_transform.screen_to_spherical_coordinates(
                    self.X_degrees, self.Y_degrees, self.spatial_config
                )
            )

            for i, current_angle in enumerate(angles):
                # Generate frame at this angle
                frame = self.generate_frame_at_angle(
                    direction, current_angle, show_bar_mask=True, frame_index=i
                )
                frames[i] = frame

                if i % 100 == 0:  # Progress logging
                    logger.info(f"  Generated frame {i}/{total_frames}")

            logger.info(f"Dataset generation complete: {total_frames} frames")
            return frames, angles, timestamps

        except Exception as e:
            logger.error(f"Error generating full dataset: {e}")
            raise

    def update_spatial_config(self, config: Dict[str, Any]):
        """Update spatial configuration and reinitialize coordinate systems"""
        for key, value in config.items():
            if hasattr(self.spatial_config, key):
                setattr(self.spatial_config, key, value)

        # Reinitialize systems with new config
        self._setup_spherical_transform()
        self._setup_coordinate_grids()

        logger.info(f"Spatial configuration updated:")
        logger.info(f"  Monitor distance: {self.spatial_config.monitor_distance_cm} cm")
        logger.info(
            f"  Field of view: {self.spatial_config.field_of_view_horizontal:.1f}° x {self.spatial_config.field_of_view_vertical:.1f}°"
        )

    def update_stimulus_params(self, params: Dict[str, Any]):
        """Update stimulus parameters"""
        for key, value in params.items():
            if hasattr(self.stimulus_params, key):
                setattr(self.stimulus_params, key, value)

        logger.info(f"Stimulus parameters updated")


# Global stimulus generator instance for IPC handlers
_stimulus_generator = None


def invalidate_stimulus_generator():
    """Invalidate the global stimulus generator to force recreation with updated parameters"""
    global _stimulus_generator
    _stimulus_generator = None
    logger.info("Stimulus generator invalidated - will be recreated with updated parameters")


def get_stimulus_generator() -> StimulusGenerator:
    """Get or create global stimulus generator instance using parameter manager"""
    global _stimulus_generator
    if _stimulus_generator is None:
        from .parameter_manager import get_parameter_manager

        # Get current parameters from parameter manager
        param_manager = get_parameter_manager()
        all_params = param_manager.load_parameters()

        # Validate monitor parameters before creating stimulus generator
        if (all_params.monitor.monitor_width_px <= 0 or
            all_params.monitor.monitor_height_px <= 0 or
            all_params.monitor.monitor_fps <= 0):
            # During startup, parameters may not be ready yet - return None gracefully
            logger.debug(
                f"Stimulus generator not available - monitor parameters not yet initialized: "
                f"width_px={all_params.monitor.monitor_width_px}, "
                f"height_px={all_params.monitor.monitor_height_px}, fps={all_params.monitor.monitor_fps}"
            )
            return None

        # Create spatial configuration from monitor parameters
        spatial_config = SpatialConfiguration(
            monitor_distance_cm=all_params.monitor.monitor_distance_cm,
            monitor_angle_degrees=all_params.monitor.monitor_lateral_angle_deg,
            screen_width_pixels=all_params.monitor.monitor_width_px,
            screen_height_pixels=all_params.monitor.monitor_height_px,
            screen_width_cm=all_params.monitor.monitor_width_cm,
            screen_height_cm=all_params.monitor.monitor_height_cm,
            fps=all_params.monitor.monitor_fps
        )

        # Create stimulus parameters from parameter manager
        stimulus_params = StimulusParameters(
            bar_width_degrees=all_params.stimulus.bar_width_deg,
            drift_speed_degrees_per_sec=all_params.stimulus.drift_speed_deg_per_sec,
            checkerboard_size_degrees=all_params.stimulus.checker_size_deg,
            flicker_frequency_hz=all_params.stimulus.strobe_rate_hz,
            contrast=all_params.stimulus.contrast,
            background_luminance=all_params.stimulus.background_luminance
        )

        _stimulus_generator = StimulusGenerator(spatial_config, stimulus_params)
        logger.info("Stimulus generator created successfully with valid parameters")
    return _stimulus_generator


# IPC Handler Functions - Primary stimulus business logic
def handle_get_stimulus_parameters(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_stimulus_parameters IPC command"""
    try:
        generator = get_stimulus_generator()

        # Return current stimulus parameters
        params = {
            "bar_width_deg": generator.stimulus_params.bar_width_degrees,
            "drift_speed_deg_per_sec": generator.stimulus_params.drift_speed_degrees_per_sec,
            "checker_size_deg": generator.stimulus_params.checkerboard_size_degrees,
            "strobe_rate_hz": generator.stimulus_params.flicker_frequency_hz,
            "contrast": generator.stimulus_params.contrast,
            "background_luminance": generator.stimulus_params.background_luminance,
        }

        return {"success": True, "parameters": params}
    except Exception as e:
        logger.error(f"Error getting stimulus parameters: {e}")
        return {"success": False, "error": str(e)}


def handle_update_stimulus_parameters(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle update_stimulus_parameters IPC command"""
    try:
        from .parameter_manager import get_parameter_manager

        params = command.get("parameters", {})

        # Update parameter manager (single source of truth)
        param_manager = get_parameter_manager()
        param_manager.update_parameter_group('stimulus', params)

        # Invalidate stimulus generator so it recreates with new parameters
        invalidate_stimulus_generator()

        return {"success": True, "message": "Stimulus parameters updated"}
    except Exception as e:
        logger.error(f"Error updating stimulus parameters: {e}")
        return {"success": False, "error": str(e)}


def handle_get_spatial_configuration(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_spatial_configuration IPC command"""
    try:
        generator = get_stimulus_generator()

        config = {
            "monitor_distance_cm": generator.spatial_config.monitor_distance_cm,
            "monitor_angle_degrees": generator.spatial_config.monitor_angle_degrees,
            "screen_width_pixels": generator.spatial_config.screen_width_pixels,
            "screen_height_pixels": generator.spatial_config.screen_height_pixels,
            "screen_width_cm": generator.spatial_config.screen_width_cm,
            "screen_height_cm": generator.spatial_config.screen_height_cm,
            "fps": generator.spatial_config.fps,
            "field_of_view_horizontal": generator.spatial_config.field_of_view_horizontal,
            "field_of_view_vertical": generator.spatial_config.field_of_view_vertical,
        }

        return {"success": True, "configuration": config}
    except Exception as e:
        logger.error(f"Error getting spatial configuration: {e}")
        return {"success": False, "error": str(e)}


def handle_update_spatial_configuration(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle update_spatial_configuration IPC command"""
    try:
        from .parameter_manager import get_parameter_manager

        config = command.get("spatial_config", command.get("configuration", {}))

        # Map to monitor parameter names
        monitor_updates = {
            "monitor_distance_cm": config.get("monitor_distance_cm"),
            "monitor_lateral_angle_deg": config.get("monitor_lateral_angle_deg", config.get("monitor_angle_degrees")),
            "monitor_width_cm": config.get("monitor_width_cm"),
            "monitor_height_cm": config.get("monitor_height_cm"),
            "monitor_width_px": config.get("monitor_width_px", config.get("screen_width_pixels")),
            "monitor_height_px": config.get("monitor_height_px", config.get("screen_height_pixels")),
            "monitor_fps": config.get("monitor_fps", config.get("fps")),
        }

        # Remove None values
        monitor_updates = {k: v for k, v in monitor_updates.items() if v is not None}

        # Update parameter manager (single source of truth)
        param_manager = get_parameter_manager()
        param_manager.update_parameter_group('monitor', monitor_updates)

        # Invalidate stimulus generator so it recreates with new parameters
        invalidate_stimulus_generator()

        return {"success": True, "message": "Spatial configuration updated"}
    except Exception as e:
        logger.error(f"Error updating spatial configuration: {e}")
        return {"success": False, "error": str(e)}


def handle_get_stimulus_info(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_stimulus_info IPC command - returns dataset information"""
    try:
        logger.info("[STIMULUS-DEBUG] handle_get_stimulus_info called")
        generator = get_stimulus_generator()
        direction = command.get("direction", "LR")
        num_cycles = command.get("num_cycles", 3)

        logger.info(f"[STIMULUS-DEBUG] Calling get_dataset_info for direction={direction}, num_cycles={num_cycles}")
        dataset_info = generator.get_dataset_info(direction, num_cycles)
        logger.info(f"[STIMULUS-DEBUG] get_dataset_info returned: {dataset_info}")

        if "error" in dataset_info:
            logger.error(f"[STIMULUS-DEBUG] Dataset info contains error: {dataset_info['error']}")
            return {"success": False, "error": dataset_info["error"]}

        result = {"success": True, "type": "stimulus_info", **dataset_info}
        logger.info(f"[STIMULUS-DEBUG] Returning result: {result}")
        return result

    except Exception as e:
        logger.error(f"[STIMULUS-DEBUG] Exception in handle_get_stimulus_info: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def handle_get_stimulus_frame(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_stimulus_frame IPC command - renders to PsychoPy window and shared memory"""
    try:
        generator = get_stimulus_generator()
        direction = command.get("direction", "LR")
        frame_index = command.get("frame_index", 0)
        show_bar_mask = command.get("show_bar_mask", True)
        num_cycles = command.get("num_cycles", 3)

        # Get dataset info for this direction to include in metadata
        dataset_info = generator.get_dataset_info(direction, num_cycles)

        # Generate frame and get metadata
        frame, metadata = generator.generate_frame_at_index(
            direction=direction,
            frame_index=frame_index,
            show_bar_mask=show_bar_mask,
            num_cycles=num_cycles,
        )

        # Add dataset info to metadata for frontend slider
        metadata['total_frames'] = dataset_info.get('total_frames', 0)
        metadata['start_angle'] = dataset_info.get('start_angle', 0.0)
        metadata['end_angle'] = dataset_info.get('end_angle', 0.0)

        # Write frame to shared memory stream for frontend rendering
        # (Presentation window will be managed by Electron, not Python)
        stream = get_stimulus_shared_memory_stream()
        frame_id = stream.write_frame(frame, metadata)

        return {
            "success": True,
            "type": "stimulus_frame",
            "frame_id": frame_id,
            "frame_info": metadata
        }

    except Exception as e:
        logger.error(f"Error generating stimulus frame: {e}")
        return {"success": False, "error": str(e)}


def handle_get_stimulus_frame_binary(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_stimulus_frame_binary - removed, use shared memory streaming"""
    return {
        "success": False,
        "error": "This command has been removed. Use shared memory streaming instead."
    }


# Status tracking
_stimulus_status = {"is_presenting": False, "current_session": None}

# Shared memory streaming integration
def get_stimulus_shared_memory_stream():
    """Get shared memory stream for stimulus frames"""
    from .shared_memory_stream import get_shared_memory_stream
    return get_shared_memory_stream()


def handle_get_stimulus_status(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_stimulus_status IPC command"""
    return {"success": True, "status": _stimulus_status.copy()}


def handle_start_stimulus(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle start_stimulus IPC command - starts real-time shared memory streaming"""
    try:
        session_name = command.get("session_name", f"session_{int(time.time())}")
        direction = command.get("direction", "LR")
        show_bar_mask = command.get("show_bar_mask", False)
        fps = command.get("fps", 60.0)

        # Update status
        _stimulus_status["is_presenting"] = True
        _stimulus_status["current_session"] = session_name

        # Get stimulus generator and start real-time streaming
        generator = get_stimulus_generator()

        # Get backend instance and start real-time streaming
        from .main import _backend_instance
        if _backend_instance and _backend_instance.start_realtime_streaming(generator, fps):
            logger.info(
                f"Real-time stimulus streaming started: {session_name}, direction: {direction}, fps: {fps}"
            )
            return {"success": True, "message": f"Real-time stimulus streaming started: {session_name}"}
        else:
            raise Exception("Failed to start real-time streaming")

    except Exception as e:
        logger.error(f"Error starting stimulus: {e}")
        _stimulus_status["is_presenting"] = False
        _stimulus_status["current_session"] = None
        return {"success": False, "error": str(e)}


def handle_stop_stimulus(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle stop_stimulus IPC command - stops real-time shared memory streaming"""
    try:
        # Get backend instance and stop real-time streaming
        from .main import _backend_instance
        if _backend_instance:
            _backend_instance.stop_realtime_streaming()

        # Update status
        session_name = _stimulus_status["current_session"]
        _stimulus_status["is_presenting"] = False
        _stimulus_status["current_session"] = None

        logger.info(f"Real-time stimulus streaming stopped: {session_name}")

        return {"success": True, "message": "Real-time stimulus streaming stopped"}
    except Exception as e:
        logger.error(f"Error stopping stimulus: {e}")
        return {"success": False, "error": str(e)}


def handle_generate_stimulus_preview(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle generate_stimulus_preview IPC command"""
    try:
        generator = get_stimulus_generator()
        direction = command.get("direction", "LR")

        # Get dataset info as preview information
        dataset_info = generator.get_dataset_info(direction, 3)

        if "error" in dataset_info:
            return {"success": False, "error": dataset_info["error"]}

        # Format preview response
        preview_info = {
            "direction": direction,
            "bar_width_deg": generator.stimulus_params.bar_width_degrees,
            "sweep_range_deg": dataset_info["sweep_degrees"],
            "cycle_duration_sec": dataset_info["cycle_duration"],
            "frames_per_cycle": dataset_info["total_frames"] // 3,  # For 3 cycles
            "total_frames": dataset_info["total_frames"],
            "estimated_duration_sec": dataset_info["duration_sec"],
            "field_of_view_deg": {
                "horizontal": generator.spatial_config.field_of_view_horizontal,
                "vertical": generator.spatial_config.field_of_view_vertical,
            },
            "resolution": {
                "width_px": generator.spatial_config.screen_width_pixels,
                "height_px": generator.spatial_config.screen_height_pixels,
            },
            "timing": {
                "fps": generator.spatial_config.fps,
                "frame_duration_ms": 1000.0 / generator.spatial_config.fps,
                "strobe_period_ms": (
                    1000.0 / generator.stimulus_params.flicker_frequency_hz
                    if generator.stimulus_params.flicker_frequency_hz > 0
                    else None
                ),
            },
        }

        return {"success": True, "type": "stimulus_preview", "preview": preview_info}
    except Exception as e:
        logger.error(f"Error generating stimulus preview: {e}")
        return {"success": False, "error": str(e)}
