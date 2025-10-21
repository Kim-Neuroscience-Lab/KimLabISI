"""Stimulus generation with GPU acceleration.

Handles on-demand frame generation for frontend preview and full dataset generation
for acquisition. Uses GPU acceleration (MPS on Mac, CUDA on Windows/Linux) when available.

Refactored to use ParameterManager as Single Source of Truth:
- Constructor injection: ParameterManager injected
- Subscribes to parameter changes
- No frozen configs
- Real-time parameter updates
"""

import numpy as np
import logging
from typing import Dict, Tuple, Optional, Any, List
from dataclasses import dataclass

# GPU acceleration
import torch

# Import spherical transformation
from .transform import SphericalTransform

logger = logging.getLogger(__name__)


def get_device() -> torch.device:
    """Detect and return the best available device for GPU acceleration.

    Priority: CUDA (NVIDIA) > MPS (Apple Silicon/Metal) > CPU

    Returns:
        torch.device: Best available device
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
    """3D spatial configuration between mouse and monitor.

    Computed from MonitorConfig for convenience.
    """

    monitor_distance_cm: float
    monitor_angle_degrees: float
    screen_width_pixels: int
    screen_height_pixels: int
    screen_width_cm: float
    screen_height_cm: float
    fps: int

    @property
    def field_of_view_horizontal(self) -> float:
        """Calculate horizontal field of view from screen width and distance."""
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
        """Calculate vertical field of view from screen height and distance."""
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
        """Calculate horizontal pixels per degree."""
        return (
            self.screen_width_pixels / self.field_of_view_horizontal
            if self.screen_width_pixels and self.field_of_view_horizontal
            else 0.0
        )

    @property
    def pixels_per_degree_vertical(self) -> float:
        """Calculate vertical pixels per degree."""
        return (
            self.screen_height_pixels / self.field_of_view_vertical
            if self.screen_height_pixels and self.field_of_view_vertical
            else 0.0
        )


class StimulusGenerator:
    """Unified stimulus generation for both on-demand frames and full datasets.

    Uses ParameterManager as Single Source of Truth:
    - Injects ParameterManager instead of frozen configs
    - Subscribes to parameter changes
    - Rebuilds GPU state when parameters change
    """

    def __init__(
        self,
        param_manager,  # ParameterManager instance
        logger=None
    ):
        """Initialize stimulus generator with ParameterManager.

        Args:
            param_manager: ParameterManager instance (Single Source of Truth)
            logger: Optional logger instance

        Raises:
            ValueError: If monitor configuration is invalid
        """
        # Store injected dependencies
        self.param_manager = param_manager
        self.logger = logger or logging.getLogger(__name__)

        # Subscribe to parameter changes
        self.param_manager.subscribe("stimulus", self._handle_stimulus_params_changed)
        self.param_manager.subscribe("monitor", self._handle_monitor_params_changed)

        # Detect and set GPU device (CUDA/MPS/CPU)
        self.device = get_device()

        # Initialize state from current parameters
        # These will be instance variables updated from ParameterManager
        self.bar_width_deg = None
        self.checker_size_deg = None
        self.drift_speed_deg_per_sec = None
        self.contrast = None
        self.strobe_rate_hz = None
        self.background_luminance = None

        self.monitor_distance_cm = None
        self.monitor_width_px = None
        self.monitor_height_px = None
        self.monitor_width_cm = None
        self.monitor_height_cm = None
        self.monitor_lateral_angle_deg = None
        self.monitor_tilt_angle_deg = None
        self.monitor_fps = None

        # Spatial configuration (will be rebuilt from parameters)
        self.spatial_config = None

        # GPU state (will be built from parameters)
        self.spherical_transform = None
        self.X_pixels = None
        self.Y_pixels = None
        self.X_degrees = None
        self.Y_degrees = None
        self.pixel_azimuth = None
        self.pixel_altitude = None
        self.base_checkerboard = None

        # Check if monitor parameters are valid before initializing
        monitor_params = self.param_manager.get_parameter_group("monitor")
        monitor_width_px = monitor_params.get("monitor_width_px", -1)
        monitor_height_px = monitor_params.get("monitor_height_px", -1)
        monitor_fps = monitor_params.get("monitor_fps", -1)

        if monitor_width_px > 0 and monitor_height_px > 0 and monitor_fps > 0:
            # Valid monitor config - initialize now
            self._setup_from_parameters()
            self.logger.info("StimulusGenerator initialized with ParameterManager")
            self.logger.info(
                "  Screen: %sx%s",
                self.spatial_config.screen_width_pixels,
                self.spatial_config.screen_height_pixels,
            )
            self.logger.info(
                "  FoV: %.1f° x %.1f°",
                self.spatial_config.field_of_view_horizontal,
                self.spatial_config.field_of_view_vertical,
            )
            self.logger.info("  Distance: %s cm", self.spatial_config.monitor_distance_cm)
        else:
            # Invalid monitor config - defer initialization until hardware detection
            # This is EXPECTED during normal startup (services created before hardware detection)
            self.logger.debug(
                "StimulusGenerator created with placeholder monitor parameters "
                f"(width={monitor_width_px}, height={monitor_height_px}, fps={monitor_fps}). "
                "Will initialize after hardware detection."
            )

    def _setup_from_parameters(self):
        """Initialize/reinitialize all state from current parameter values.

        Called on startup and whenever parameters change.
        Reads fresh values from ParameterManager and rebuilds all GPU state.
        """
        # Get current parameters
        stimulus_params = self.param_manager.get_parameter_group("stimulus")
        monitor_params = self.param_manager.get_parameter_group("monitor")

        # Extract ALL stimulus parameters
        self.bar_width_deg = stimulus_params.get("bar_width_deg", 15.0)
        self.checker_size_deg = stimulus_params.get("checker_size_deg", 5.0)
        self.drift_speed_deg_per_sec = stimulus_params.get("drift_speed_deg_per_sec", 10.0)
        self.contrast = stimulus_params.get("contrast", 0.5)
        self.strobe_rate_hz = stimulus_params.get("strobe_rate_hz", 2.0)
        self.background_luminance = stimulus_params.get("background_luminance", 0.5)

        # CRITICAL VALIDATION: Ensure pattern will be visible
        if self.background_luminance < self.contrast:
            self.logger.error(
                f"INVALID STIMULUS PARAMETERS: background_luminance ({self.background_luminance}) < contrast ({self.contrast}). "
                f"This will cause half the checkerboard to be clamped to black and invisible! "
                f"Clamping contrast to background_luminance to prevent invisible pattern."
            )
            self.contrast = self.background_luminance  # Emergency fix: reduce contrast to prevent negative values

        # Extract ALL monitor parameters
        self.monitor_distance_cm = monitor_params.get("monitor_distance_cm", 15.0)
        self.monitor_width_px = monitor_params.get("monitor_width_px", 1920)
        self.monitor_height_px = monitor_params.get("monitor_height_px", 1080)
        self.monitor_width_cm = monitor_params.get("monitor_width_cm", 50.0)
        self.monitor_height_cm = monitor_params.get("monitor_height_cm", 28.0)
        self.monitor_lateral_angle_deg = monitor_params.get("monitor_lateral_angle_deg", 0.0)
        self.monitor_tilt_angle_deg = monitor_params.get("monitor_tilt_angle_deg", 0.0)
        self.monitor_fps = monitor_params.get("monitor_fps", 60)

        # Validate monitor configuration
        if (
            self.monitor_width_px <= 0
            or self.monitor_height_px <= 0
            or self.monitor_fps <= 0
        ):
            raise ValueError(
                f"Invalid monitor configuration: "
                f"width_px={self.monitor_width_px}, "
                f"height_px={self.monitor_height_px}, "
                f"fps={self.monitor_fps}"
            )

        # Rebuild spatial configuration
        self.spatial_config = SpatialConfiguration(
            monitor_distance_cm=self.monitor_distance_cm,
            monitor_angle_degrees=self.monitor_lateral_angle_deg,
            screen_width_pixels=self.monitor_width_px,
            screen_height_pixels=self.monitor_height_px,
            screen_width_cm=self.monitor_width_cm,
            screen_height_cm=self.monitor_height_cm,
            fps=self.monitor_fps,
        )

        # Rebuild spherical transform and coordinate grids
        self._setup_spherical_transform()
        self._setup_coordinate_grids()

        # Rebuild GPU invariants
        self._precompute_invariants()

        if hasattr(self, 'logger'):
            self.logger.info("Stimulus generator reconfigured from current parameters")

    # Compatibility properties for external code (handlers in main.py)
    @property
    def stimulus_config(self):
        """Compatibility property - returns dict-like object with stimulus parameters."""
        class StimConfigCompat:
            def __init__(self, generator):
                self.generator = generator
            def __getattr__(self, name):
                return getattr(self.generator, name)
        return StimConfigCompat(self)

    def _handle_stimulus_params_changed(self, group_name: str, updates: Dict[str, Any]):
        """React to stimulus parameter changes - rebuild state.

        Args:
            group_name: Parameter group that changed ("stimulus")
            updates: Dictionary of updated parameters
        """
        self.logger.info(f"Stimulus parameters changed: {list(updates.keys())}")

        # Any stimulus parameter change requires rebuild
        self._setup_from_parameters()

    def _handle_monitor_params_changed(self, group_name: str, updates: Dict[str, Any]):
        """React to monitor parameter changes - rebuild spatial state.

        Args:
            group_name: Parameter group that changed ("monitor")
            updates: Dictionary of updated parameters
        """
        self.logger.info(f"Monitor parameters changed: {list(updates.keys())}")

        # Check if spatial parameters changed (affects FOV calculations)
        spatial_keys = [
            "monitor_distance_cm", "monitor_width_cm", "monitor_height_cm",
            "monitor_width_px", "monitor_height_px",
            "monitor_lateral_angle_deg", "monitor_tilt_angle_deg", "monitor_fps"
        ]

        if any(key in updates for key in spatial_keys):
            # Check if the updated parameters are valid
            monitor_params = self.param_manager.get_parameter_group("monitor")
            width_px = monitor_params.get("monitor_width_px", -1)
            height_px = monitor_params.get("monitor_height_px", -1)
            fps = monitor_params.get("monitor_fps", -1)

            if width_px > 0 and height_px > 0 and fps > 0:
                # Valid parameters - initialize/rebuild
                self._setup_from_parameters()  # Full rebuild
                self.logger.info(
                    f"StimulusGenerator initialized after hardware detection: "
                    f"{width_px}x{height_px}@{fps}Hz"
                )
            else:
                # Still invalid after hardware detection - this is a problem!
                self.logger.warning(
                    f"Monitor parameters still invalid after hardware detection: "
                    f"width_px={width_px}, height_px={height_px}, fps={fps}. "
                    f"StimulusGenerator cannot initialize until valid display is detected."
                )

    def _setup_spherical_transform(self):
        """Initialize spherical transform with spatial configuration."""
        self.spherical_transform = SphericalTransform(
            monitor_distance_cm=self.spatial_config.monitor_distance_cm,
            screen_width_cm=self.spatial_config.screen_width_cm,
            screen_height_cm=self.spatial_config.screen_height_cm,
        )

    def _setup_coordinate_grids(self):
        """Setup coordinate grids on GPU using PyTorch tensors."""
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
        """Pre-compute spherical coordinates and base patterns on GPU.

        Computed once, reused forever for performance.
        """
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
        checker_size_degrees = self.checker_size_deg
        azimuth_checks = (self.pixel_azimuth / checker_size_degrees).to(torch.int64)
        altitude_checks = (self.pixel_altitude / checker_size_degrees).to(torch.int64)
        self.base_checkerboard = (azimuth_checks + altitude_checks) % 2

        logger.info(
            f"Pre-computation complete on {self.device} - spherical coordinates and checkerboard cached"
        )

    def get_dataset_info(
        self, direction: str, total_frames: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get dataset information without generating frames.

        Args:
            direction: Sweep direction ("LR", "RL", "TB", "BT")
            total_frames: Optional total frame count (computed if None)

        Returns:
            Dictionary with dataset metadata
        """
        try:
            # Calculate the actual total sweep distance including off-screen portions
            bar_full_width = self.bar_width_deg

            if direction in ["LR", "RL"]:
                # Vertical bars - sweep through azimuth plus off-screen extensions
                fov_half = self.spatial_config.field_of_view_horizontal / 2
                total_sweep_degrees = 2 * (fov_half + bar_full_width)
            else:  # TB, BT
                # Horizontal bars - sweep through altitude plus off-screen extensions
                fov_half = self.spatial_config.field_of_view_vertical / 2
                total_sweep_degrees = 2 * (fov_half + bar_full_width)

            sweep_duration = (
                total_sweep_degrees / self.drift_speed_deg_per_sec
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
        """Calculate start and end angles for the given direction.

        Args:
            direction: Sweep direction ("LR", "RL", "TB", "BT")

        Returns:
            Tuple of (start_angle, end_angle) in degrees
        """
        bar_full_width = self.bar_width_deg

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
        """Convert frame index to spatial angle.

        Args:
            direction: Sweep direction
            frame_index: Current frame index
            total_frames: Total number of frames

        Returns:
            Angle in degrees
        """
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
        output_format: str = "rgba",
    ) -> np.ndarray:
        """Generate a single frame on GPU using PyTorch tensors.

        Args:
            direction: Sweep direction
            angle: Current bar angle in degrees
            show_bar_mask: Whether to show bar mask
            frame_index: Current frame index (for flicker phase)
            output_format: Output format - "grayscale" (H, W) or "rgba" (H, W, 4)

        Returns:
            NumPy array with grayscale (H, W) or RGBA (H, W, 4) data
        """
        h, w = (
            self.spatial_config.screen_height_pixels,
            self.spatial_config.screen_width_pixels,
        )

        # Start with background (on GPU)
        frame = torch.full(
            (h, w),
            self.background_luminance,
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
            bar_half_width = self.bar_width_deg / 2
            bar_mask = torch.abs(coordinate_map - angle) <= bar_half_width

            # Apply checkerboard within bar using vectorized operation (GPU)
            frame[bar_mask] = checkerboard[bar_mask]

        # Convert to uint8
        frame_uint8 = torch.clamp(frame * 255, 0, 255).to(torch.uint8)

        if output_format == "grayscale":
            # Return grayscale (for efficient storage - 4x smaller than RGBA)
            return frame_uint8.cpu().numpy()
        else:  # rgba
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
        """Generate a single frame at the specified frame index.

        Args:
            direction: Sweep direction
            frame_index: Current frame index
            show_bar_mask: Whether to show bar mask
            total_frames: Total frames (computed if None)

        Returns:
            Tuple of (frame_array, metadata_dict)
        """
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
        """Get checkerboard pattern with counter-phase flip on GPU.

        Uses pre-computed base pattern for performance.

        Args:
            frame_index: Current frame index for flicker phase

        Returns:
            Checkerboard pattern tensor on GPU
        """
        # Use PRE-COMPUTED base checkerboard pattern on GPU (no expensive calculations!)
        checkerboard = self.base_checkerboard.clone()

        # Counter-phase flickering - simple inversion
        fps = self.spatial_config.fps
        flicker_frequency_hz = self.strobe_rate_hz
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
            self.background_luminance + self.contrast,
            self.background_luminance - self.contrast,
        )

        return torch.clamp(pattern, 0, 1)

    def generate_sweep(
        self,
        direction: str,
        output_format: str = "grayscale"
    ) -> Tuple[List[np.ndarray], List[float]]:
        """Generate a complete sweep sequence (one cycle) for pre-generation.

        Args:
            direction: Sweep direction ("LR", "RL", "TB", "BT")
            output_format: "grayscale" or "rgba"

        Returns:
            Tuple of (frames_list, angles_list)
        """
        # Get dataset info for one cycle
        dataset_info = self.get_dataset_info(direction)
        if "error" in dataset_info:
            raise Exception(dataset_info["error"])

        total_frames = dataset_info["total_frames"]
        start_angle = dataset_info["start_angle"]
        end_angle = dataset_info["end_angle"]

        logger.info(f"Generating {direction} sweep: {total_frames} frames at {self.spatial_config.fps} fps")
        logger.info(f"  Duration: {dataset_info['duration_sec']:.2f}s, Angle range: {start_angle:.1f}° to {end_angle:.1f}°")

        frames = []
        angles = []

        for frame_index in range(total_frames):
            angle = self.calculate_frame_angle(direction, frame_index, total_frames)
            frame = self.generate_frame_at_angle(
                direction=direction,
                angle=angle,
                show_bar_mask=True,
                frame_index=frame_index,
                output_format=output_format
            )
            frames.append(frame)
            angles.append(angle)

            if frame_index % 100 == 0:
                logger.debug(f"  Generated frame {frame_index}/{total_frames}")

        logger.info(f"Sweep generation complete: {len(frames)} frames")
        return frames, angles

    def generate_full_dataset(
        self, direction: str, num_cycles: int = 10
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate full frame sequence for acquisition.

        Args:
            direction: Sweep direction
            num_cycles: Number of sweep cycles

        Returns:
            Tuple of (frames, angles, timestamps)
        """
        try:
            logger.debug("Generating %s drifting bar stimulus dataset...", direction)

            # Get dataset parameters for ONE cycle
            # num_cycles is used to multiply total_frames below
            dataset_info = self.get_dataset_info(direction)
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
            frames = np.zeros((total_frames, h, w, 4), dtype=np.uint8)

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
