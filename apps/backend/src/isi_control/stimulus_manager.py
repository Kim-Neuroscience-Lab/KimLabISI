"""
Unified Stimulus Generator
Handles both on-demand frame generation for frontend preview and full dataset generation for acquisition
Uses GPU acceleration (MPS on Mac, CUDA on Windows/Linux) when available
"""

import numpy as np
import time
from typing import Dict, Tuple, Optional, Any
from dataclasses import dataclass
from logging import Logger
from .logging_utils import get_logger
from .service_locator import get_services
from .ipc_utils import ipc_handler
from .shared_memory_stream import get_realtime_producer

# GPU acceleration
import torch

# Import existing spatial transformation components
from .spherical_transform import SphericalTransform

logger: Logger = get_logger(__name__)


def get_device() -> torch.device:
    """
    Detect and return the best available device for GPU acceleration.
    Priority: CUDA (NVIDIA) > MPS (Apple Silicon/Metal) > CPU
    """
    if torch.cuda.is_available():
        device = torch.device("cuda")
        logger.info(f"GPU acceleration enabled: CUDA ({torch.cuda.get_device_name(0)})")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
        logger.info("GPU acceleration enabled: MPS (Apple Metal)")
    else:
        device = torch.device("cpu")
        logger.info("GPU acceleration not available, using CPU")

    return device


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
            raise ValueError(
                "StimulusGenerator requires spatial_config and stimulus_params from parameter manager"
            )

        self.spatial_config: SpatialConfiguration = spatial_config
        self.stimulus_params: StimulusParameters = stimulus_params

        # Detect and set GPU device (CUDA/MPS/CPU)
        self.device = get_device()

        # Initialize spherical transform and coordinate grids
        self.spherical_transform = None
        self.X_pixels = None
        self.Y_pixels = None
        self.X_degrees = None
        self.Y_degrees = None
        self._setup_spherical_transform()
        self._setup_coordinate_grids()

        # Pre-compute invariants on GPU (computed once, used for all frames)
        self.pixel_azimuth = None
        self.pixel_altitude = None
        self.base_checkerboard = None
        self._precompute_invariants()

        logger.debug("StimulusGenerator initialized")
        logger.debug(
            "  Screen: %sx%s",
            self.spatial_config.screen_width_pixels,
            self.spatial_config.screen_height_pixels,
        )
        logger.debug(
            "  FoV: %.1f° x %.1f°",
            self.spatial_config.field_of_view_horizontal,
            self.spatial_config.field_of_view_vertical,
        )
        logger.debug("  Distance: %s cm", self.spatial_config.monitor_distance_cm)

    def _setup_spherical_transform(self):
        """Initialize spherical transform with spatial configuration"""
        self.spherical_transform = SphericalTransform(
            monitor_distance_cm=self.spatial_config.monitor_distance_cm,
            screen_width_cm=self.spatial_config.screen_width_cm,
            screen_height_cm=self.spatial_config.screen_height_cm,
        )

    def _setup_coordinate_grids(self):
        """Setup coordinate grids on GPU using PyTorch tensors"""
        width = self.spatial_config.screen_width_pixels
        height = self.spatial_config.screen_height_pixels

        # Pixel coordinates (on GPU)
        x_pixels = torch.arange(width, device=self.device, dtype=torch.float32)
        y_pixels = torch.arange(height, device=self.device, dtype=torch.float32)
        self.Y_pixels, self.X_pixels = torch.meshgrid(y_pixels, x_pixels, indexing="ij")

        # Convert to degrees from center
        center_x = width / 2
        center_y = height / 2

        pixels_per_degree_h = self.spatial_config.pixels_per_degree_horizontal
        pixels_per_degree_v = self.spatial_config.pixels_per_degree_vertical

        self.X_degrees = (self.X_pixels - center_x) / pixels_per_degree_h
        self.Y_degrees = (self.Y_pixels - center_y) / pixels_per_degree_v

    def _precompute_invariants(self):
        """Pre-compute spherical coordinates and base patterns on GPU (computed once, reused forever)"""
        logger.info(
            "Pre-computing spherical coordinates and checkerboard pattern on GPU..."
        )

        # Compute spherical coordinates ONCE on GPU (expensive operation)
        self.pixel_azimuth, self.pixel_altitude = (
            self.spherical_transform.screen_to_spherical_coordinates(
                self.X_degrees, self.Y_degrees, self.spatial_config
            )
        )

        # Pre-compute base checkerboard pattern on GPU (before phase flips)
        checker_size_degrees = self.stimulus_params.checkerboard_size_degrees
        azimuth_checks = (self.pixel_azimuth / checker_size_degrees).to(torch.int64)
        altitude_checks = (self.pixel_altitude / checker_size_degrees).to(torch.int64)
        self.base_checkerboard = (azimuth_checks + altitude_checks) % 2

        logger.info(
            f"Pre-computation complete on {self.device} - spherical coordinates and checkerboard cached"
        )

    def get_dataset_info(
        self, direction: str, total_frames: Optional[int] = None
    ) -> Dict[str, Any]:
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

            sweep_duration = (
                total_sweep_degrees / self.stimulus_params.drift_speed_degrees_per_sec
            )

            if total_frames is None:
                total_frames = int(sweep_duration * self.spatial_config.fps)

            # Calculate start and end angles
            start_angle, end_angle = self._calculate_angle_range(direction)

            return {
                "total_frames": total_frames,
                "duration_sec": sweep_duration,
                "start_angle": start_angle,
                "end_angle": end_angle,
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
        """Generate a single frame on GPU using PyTorch tensors, return as NumPy for output"""
        h, w = (
            self.spatial_config.screen_height_pixels,
            self.spatial_config.screen_width_pixels,
        )

        # Start with background (on GPU)
        frame = torch.full(
            (h, w),
            self.stimulus_params.background_luminance,
            dtype=torch.float32,
            device=self.device,
        )

        # Get checkerboard with phase (uses pre-computed base pattern on GPU)
        checkerboard = self._get_checkerboard_with_phase(frame_index)

        if not show_bar_mask:
            # Use checkerboard pattern across entire frame without bar mask
            frame = checkerboard
        else:
            # Create bar mask using PRE-COMPUTED spherical coordinates (already on GPU!)
            if direction in ["LR", "RL"]:
                coordinate_map = self.pixel_azimuth
            else:  # TB, BT
                coordinate_map = self.pixel_altitude

            # Vectorized bar mask calculation (GPU-accelerated)
            bar_half_width = self.stimulus_params.bar_width_degrees / 2
            bar_mask = torch.abs(coordinate_map - angle) <= bar_half_width

            # Apply checkerboard within bar using vectorized operation (GPU)
            frame[bar_mask] = checkerboard[bar_mask]

        # Convert to uint8 RGBA for direct canvas rendering (GPU-accelerated)
        frame_uint8 = torch.clamp(frame * 255, 0, 255).to(torch.uint8)

        # Expand grayscale to RGBA using broadcasting (GPU)
        frame_rgba = torch.empty((h, w, 4), dtype=torch.uint8, device=self.device)
        frame_rgba[:, :, :3] = frame_uint8.unsqueeze(-1)  # Broadcast to RGB
        frame_rgba[:, :, 3] = 255  # Alpha channel

        # Convert to NumPy only at the end for output
        return frame_rgba.cpu().numpy()

    def generate_frame_at_index(
        self,
        direction: str,
        frame_index: int,
        show_bar_mask: bool = True,
        total_frames: Optional[int] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Generate a single frame at the specified frame index"""
        try:
            # Get dataset info to calculate total frames
            dataset_info = self.get_dataset_info(direction, total_frames)
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

    def _get_checkerboard_with_phase(self, frame_index: int) -> torch.Tensor:
        """Get checkerboard pattern with counter-phase flip on GPU (uses pre-computed base pattern)"""
        # Use PRE-COMPUTED base checkerboard pattern on GPU (no expensive calculations!)
        checkerboard = self.base_checkerboard.clone()

        # Counter-phase flickering - simple inversion
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
                checkerboard = (
                    1 - checkerboard
                )  # Vectorized inversion on GPU (instant!)

        # Apply contrast using vectorized torch.where (GPU-accelerated)
        pattern = torch.where(
            checkerboard.bool(),
            self.stimulus_params.background_luminance + self.stimulus_params.contrast,
            self.stimulus_params.background_luminance - self.stimulus_params.contrast,
        )

        return torch.clamp(pattern, 0, 1)

    def generate_full_dataset(
        self, direction: str, num_cycles: int = 10
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate full frame sequence for acquisition"""
        try:
            logger.debug("Generating %s drifting bar stimulus dataset...", direction)

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

            logger.debug("  Total frames: %d", total_frames)
            logger.debug("  Duration: %.1fs", dataset_info["duration_sec"])
            logger.debug("  Angle range: %.1f° to %.1f°", start_angle, end_angle)

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
                    logger.debug("  Generated frame %d/%d", i, total_frames)

            logger.debug("Dataset generation complete: %d frames", total_frames)
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

        logger.debug("Spatial configuration updated")
        logger.debug(
            "  Monitor distance: %s cm", self.spatial_config.monitor_distance_cm
        )
        logger.debug(
            "  Field of view: %.1f° x %.1f°",
            self.spatial_config.field_of_view_horizontal,
            self.spatial_config.field_of_view_vertical,
        )

    def update_stimulus_params(self, params: Dict[str, Any]):
        """Update stimulus parameters"""
        for key, value in params.items():
            if hasattr(self.stimulus_params, key):
                setattr(self.stimulus_params, key, value)

        logger.debug("Stimulus parameters updated")


# Global stimulus generator instance for IPC handlers
_stimulus_generator = None


def invalidate_stimulus_generator():
    """Invalidate the global stimulus generator to force recreation with updated parameters"""
    global _stimulus_generator
    _stimulus_generator = None
    logger.info(
        "Stimulus generator invalidated - will be recreated with updated parameters"
    )


def get_stimulus_generator(param_manager=None) -> StimulusGenerator:
    """Get or create global stimulus generator instance using parameter manager

    Args:
        param_manager: Optional parameter manager. If None, pulls from service registry.
    """
    global _stimulus_generator
    if _stimulus_generator is None:
        if param_manager is None:
            param_manager = get_services().parameter_manager
        all_params = param_manager.load_parameters()

        # Validate monitor parameters before creating stimulus generator
        if (
            all_params.monitor.monitor_width_px <= 0
            or all_params.monitor.monitor_height_px <= 0
            or all_params.monitor.monitor_fps <= 0
        ):
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
            fps=all_params.monitor.monitor_fps,
        )

        # Create stimulus parameters from parameter manager
        stimulus_params = StimulusParameters(
            bar_width_degrees=all_params.stimulus.bar_width_deg,
            drift_speed_degrees_per_sec=all_params.stimulus.drift_speed_deg_per_sec,
            checkerboard_size_degrees=all_params.stimulus.checker_size_deg,
            flicker_frequency_hz=all_params.stimulus.strobe_rate_hz,
            contrast=all_params.stimulus.contrast,
            background_luminance=all_params.stimulus.background_luminance,
        )

        _stimulus_generator = StimulusGenerator(spatial_config, stimulus_params)
        logger.info("Stimulus generator created successfully with valid parameters")
    return _stimulus_generator


def provide_stimulus_generator(param_manager=None) -> StimulusGenerator:
    """Provide a generator instance for the service registry.

    Args:
        param_manager: Optional parameter manager. If None, pulls from service registry.
    """
    generator = get_stimulus_generator(param_manager=param_manager)
    if generator is None:
        raise RuntimeError(
            "Stimulus generator unavailable; monitor parameters not initialized"
        )
    return generator


# IPC Handler Functions - Primary stimulus business logic
@ipc_handler("get_stimulus_parameters")
def handle_get_stimulus_parameters(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_stimulus_parameters IPC command"""
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

    return {"parameters": params}


@ipc_handler("update_stimulus_parameters")
def handle_update_stimulus_parameters(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle update_stimulus_parameters IPC command"""
    param_manager = get_services().parameter_manager

    params = command.get("parameters", {})

    # Update parameter manager (single source of truth)
    param_manager.update_parameter_group("stimulus", params)

    # Invalidate stimulus generator so it recreates with new parameters
    invalidate_stimulus_generator()

    return {"message": "Stimulus parameters updated"}


@ipc_handler("get_spatial_configuration")
def handle_get_spatial_configuration(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_spatial_configuration IPC command"""
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

    return {"configuration": config}


@ipc_handler("update_spatial_configuration")
def handle_update_spatial_configuration(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle update_spatial_configuration IPC command"""
    param_manager = get_services().parameter_manager

    config = command.get("spatial_config", command.get("configuration", {}))

    # Map to monitor parameter names
    monitor_updates = {
        "monitor_distance_cm": config.get("monitor_distance_cm"),
        "monitor_lateral_angle_deg": config.get(
            "monitor_lateral_angle_deg", config.get("monitor_angle_degrees")
        ),
        "monitor_width_cm": config.get("monitor_width_cm"),
        "monitor_height_cm": config.get("monitor_height_cm"),
        "monitor_width_px": config.get(
            "monitor_width_px", config.get("screen_width_pixels")
        ),
        "monitor_height_px": config.get(
            "monitor_height_px", config.get("screen_height_pixels")
        ),
        "monitor_fps": config.get("monitor_fps", config.get("fps")),
    }

    # Remove None values
    monitor_updates = {k: v for k, v in monitor_updates.items() if v is not None}

    # Update parameter manager (single source of truth)
    param_manager.update_parameter_group("monitor", monitor_updates)

    # Invalidate stimulus generator so it recreates with new parameters
    invalidate_stimulus_generator()

    return {"message": "Spatial configuration updated"}


@ipc_handler("get_stimulus_info")
def handle_get_stimulus_info(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_stimulus_info IPC command - returns dataset information"""
    logger.debug("handle_get_stimulus_info called")
    generator = get_stimulus_generator()
    direction = command.get("direction", "LR")
    num_cycles = command.get("num_cycles", 3)

    logger.debug(
        "Calling get_dataset_info for direction=%s, num_cycles=%s",
        direction,
        num_cycles,
    )
    dataset_info = generator.get_dataset_info(direction, num_cycles)
    logger.debug("get_dataset_info returned: %s", dataset_info)

    if "error" in dataset_info:
        logger.error("Dataset info contains error: %s", dataset_info["error"])
        return {"success": False, "error": dataset_info["error"]}

    result = {**dataset_info}
    logger.debug("Returning result: %s", result)
    return result


@ipc_handler("get_stimulus_frame")
def handle_get_stimulus_frame(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_stimulus_frame IPC command - generates frame on-demand using vectorized operations"""
    generator = get_stimulus_generator()
    direction = command.get("direction", "LR")
    frame_index = command.get("frame_index", 0)
    show_bar_mask = command.get("show_bar_mask", True)
    total_frames = command.get("total_frames")

    # Get dataset info for this direction
    dataset_info = generator.get_dataset_info(direction, total_frames)
    total_frames = dataset_info.get("total_frames", 0)

    # Clamp frame index to valid range
    frame_index = max(0, min(frame_index, total_frames - 1))

    # Generate frame on-demand using vectorized operations (fast!)
    frame, metadata = generator.generate_frame_at_index(
        direction=direction,
        frame_index=frame_index,
        show_bar_mask=show_bar_mask,
        total_frames=total_frames,
    )

    # Build metadata
    angle = generator.calculate_frame_angle(direction, frame_index, total_frames)
    metadata = {
        "frame_index": frame_index,
        "direction": direction,
        "angle_degrees": angle,
        "width_px": generator.spatial_config.screen_width_pixels,
        "height_px": generator.spatial_config.screen_height_pixels,
        "total_frames": total_frames,
        "start_angle": dataset_info.get("start_angle", 0.0),
        "end_angle": dataset_info.get("end_angle", 0.0),
    }

    # Write frame to shared memory stream for frontend rendering
    stream = get_stimulus_shared_memory_stream()
    frame_id = stream.write_frame(frame, metadata)

    # Get the full frame metadata including shm_path
    frame_metadata = stream.get_frame_info(frame_id)
    if frame_metadata:
        # Convert to dict with shm_path included
        frame_info_with_path = frame_metadata.to_dict(f"/tmp/{stream.stream_name}_stimulus_shm")
    else:
        # Fallback to original metadata if frame info not found
        frame_info_with_path = metadata

    return {
        "frame_id": frame_id,
        "frame_info": frame_info_with_path,
    }


# Status tracking
_stimulus_status = {"is_presenting": False, "current_session": None}


# Shared memory streaming integration
def get_stimulus_shared_memory_stream():
    """Get shared memory stream for stimulus frames"""
    return get_services().shared_memory.stream


@ipc_handler("get_stimulus_status")
def handle_get_stimulus_status(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_stimulus_status IPC command"""
    return {"status": _stimulus_status.copy()}


def render_initial_stimulus_frame() -> None:
    """Render the initial stimulus frame into shared memory for startup preview."""
    try:
        generator = get_stimulus_generator()
        if generator is None:
            logger.info(
                "Initial stimulus frame skipped - stimulus generator not yet available"
            )
            return

        param_manager = get_services().parameter_manager
        parameters = param_manager.load_parameters()

        directions = parameters.acquisition.directions
        direction = directions[0] if directions else "LR"

        result = handle_get_stimulus_frame(
            {
                "direction": direction,
                "frame_index": 0,
                "show_bar_mask": True,
            }
        )

        if not result.get("success", False):
            raise RuntimeError(result.get("error", "Failed to render initial frame"))

        logger.info(
            "Initial stimulus frame rendered",
        )

    except Exception as exc:
        logger.warning(f"Unable to render initial stimulus frame: {exc}")


@ipc_handler("start_stimulus")
def handle_start_stimulus(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle start_stimulus IPC command - starts real-time shared memory streaming"""
    session_name = command.get("session_name", f"session_{int(time.time())}")
    direction = command.get("direction", "LR")
    show_bar_mask = command.get("show_bar_mask", False)
    fps = command.get("fps", 60.0)

    try:
        # Update status
        _stimulus_status["is_presenting"] = True
        _stimulus_status["current_session"] = session_name

        # Update state coordinator
        services = get_services()
        if hasattr(services, 'acquisition_state') and services.acquisition_state:
            services.acquisition_state.set_stimulus_active(True)

        # Get stimulus generator and start real-time streaming
        generator = get_stimulus_generator()

        if generator is None:
            raise Exception(
                "Stimulus generator not available - monitor parameters may not be initialized"
            )

        services = get_services()
        shared_memory = services.shared_memory

        # Start real-time streaming
        producer = shared_memory.start_realtime_streaming(generator, fps)

        # Set the direction for the realtime producer
        if producer:
            producer.set_stimulus_params(direction)
            logger.info(
                f"Real-time stimulus streaming started: {session_name}, direction: {direction}, fps: {fps}"
            )
        else:
            raise Exception(
                "Realtime producer not available after starting streaming"
            )

        return {"message": f"Real-time stimulus streaming started: {session_name}"}

    except Exception as e:
        logger.error(f"Error starting stimulus: {e}")
        _stimulus_status["is_presenting"] = False
        _stimulus_status["current_session"] = None
        raise  # Re-raise to let decorator handle error response


@ipc_handler("stop_stimulus")
def handle_stop_stimulus(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle stop_stimulus IPC command - stops real-time shared memory streaming"""
    # Stop real-time streaming via shared memory service
    services = get_services()
    services.shared_memory.stop_realtime_streaming()

    # Clear stimulus frames and timestamp
    services.shared_memory.clear_stimulus_frames()
    services.shared_memory.clear_stimulus_timestamp()

    # Update status
    session_name = _stimulus_status["current_session"]
    _stimulus_status["is_presenting"] = False
    _stimulus_status["current_session"] = None

    # Update state coordinator
    if hasattr(services, 'acquisition_state') and services.acquisition_state:
        services.acquisition_state.set_stimulus_active(False)

    logger.info(f"Real-time stimulus streaming stopped: {session_name}")

    return {"message": "Real-time stimulus streaming stopped"}


@ipc_handler("generate_stimulus_preview")
def handle_generate_stimulus_preview(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle generate_stimulus_preview IPC command"""
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
        "cycle_duration_sec": dataset_info["duration_sec"],
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

    return {"preview": preview_info}


@ipc_handler("display_timestamp")
def handle_display_timestamp(command: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle display_timestamp from frontend - exact vsync timestamp when frame was displayed.

    CRITICAL: This timestamp MUST come from hardware vsync (e.g., requestAnimationFrame timestamp).
    Software timestamps are NOT acceptable for scientific accuracy.

    Args:
        command: Must contain frame_id and display_timestamp_us

    Returns:
        Success/error response
    """
    frame_id = command.get("frame_id")
    display_timestamp_us = command.get("display_timestamp_us")

    if frame_id is None or display_timestamp_us is None:
        logger.error(
            "CRITICAL: Frontend did not provide display timestamp. "
            "display_timestamp_us is REQUIRED for scientific accuracy. "
            "Frontend must send hardware vsync timestamps for every rendered frame."
        )
        return {
            "success": False,
            "error": "Missing frame_id or display_timestamp_us - REQUIRED for scientific accuracy",
        }

    # Validate timestamp is reasonable (not zero, not in the past by too much, not in future)
    current_time_us = int(time.time() * 1_000_000)
    time_diff_us = abs(current_time_us - display_timestamp_us)

    # Timestamp should be within last 100ms (allowing for some processing delay)
    if time_diff_us > 100_000:  # 100ms
        logger.warning(
            f"Display timestamp seems incorrect: {time_diff_us / 1000:.1f}ms difference from current time. "
            f"Verify frontend is sending hardware vsync timestamps, not software timestamps."
        )

    # Store the display timestamp in shared memory service for correlation
    services = get_services()
    if services.shared_memory:
        services.shared_memory.set_stimulus_timestamp(
            display_timestamp_us, frame_id
        )
        logger.debug(
            f"Recorded display timestamp: frame_id={frame_id}, timestamp={display_timestamp_us}μs"
        )

    return {"success": True}
