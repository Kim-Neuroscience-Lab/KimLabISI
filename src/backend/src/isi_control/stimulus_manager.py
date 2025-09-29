"""
Unified Stimulus Generator
Handles both on-demand frame generation for frontend preview and full dataset generation for acquisition
"""

import numpy as np
import base64
import io
import time
import threading
from PIL import Image
from typing import Dict, Tuple, Optional, Any
from dataclasses import dataclass
import logging

# Import existing spatial transformation components
from .spherical_transform import SphericalTransform

logger = logging.getLogger(__name__)


@dataclass
class SpatialConfiguration:
    """3D spatial configuration between mouse and monitor"""

    monitor_distance_cm: float = 10.0
    monitor_angle_degrees: float = 20.0
    screen_width_pixels: int = 512  # 2560 * 0.2 for testing
    screen_height_pixels: int = 288  # 1440 * 0.2 for testing
    screen_width_cm: float = 60.96
    screen_height_cm: float = 36.195
    fps: int = 60

    @property
    def field_of_view_horizontal(self) -> float:
        """Calculate horizontal field of view from screen width and distance"""
        return 2 * np.degrees(
            np.arctan(self.screen_width_cm / (2 * self.monitor_distance_cm))
        )

    @property
    def field_of_view_vertical(self) -> float:
        """Calculate vertical field of view from screen height and distance"""
        return 2 * np.degrees(
            np.arctan(self.screen_height_cm / (2 * self.monitor_distance_cm))
        )

    @property
    def pixels_per_degree_horizontal(self) -> float:
        return self.screen_width_pixels / self.field_of_view_horizontal

    @property
    def pixels_per_degree_vertical(self) -> float:
        return self.screen_height_pixels / self.field_of_view_vertical


@dataclass
class StimulusParameters:
    """Stimulus generation parameters"""

    bar_width_degrees: float = 20.0
    drift_speed_degrees_per_sec: float = 9.0
    num_cycles: int = 10
    checkerboard_size_degrees: float = 25.0
    flicker_frequency_hz: float = 6.0
    contrast: float = 0.8
    background_luminance: float = 0.0


class StimulusGenerator:
    """Unified stimulus generation for both on-demand frames and full datasets"""

    def __init__(self, spatial_config: SpatialConfiguration = None, stimulus_params: StimulusParameters = None):
        self.spatial_config = spatial_config or SpatialConfiguration()
        self.stimulus_params = stimulus_params or StimulusParameters()

        # Initialize spherical transform and coordinate grids
        self.spherical_transform = None
        self.X_pixels = None
        self.Y_pixels = None
        self.X_degrees = None
        self.Y_degrees = None
        self._setup_spherical_transform()
        self._setup_coordinate_grids()

        logger.info(f"StimulusGenerator initialized:")
        logger.info(f"  Screen: {self.spatial_config.screen_width_pixels}x{self.spatial_config.screen_height_pixels}")
        logger.info(f"  FoV: {self.spatial_config.field_of_view_horizontal:.1f}° x {self.spatial_config.field_of_view_vertical:.1f}°")
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

            cycle_duration = total_sweep_degrees / self.stimulus_params.drift_speed_degrees_per_sec
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
                "fps": self.spatial_config.fps
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
                (max_angle + bar_full_width) if direction == "LR"
                else -(max_angle + bar_full_width)
            )
            end_angle = (
                -(max_angle + bar_full_width) if direction == "LR"
                else (max_angle + bar_full_width)
            )
        else:  # TB, BT
            max_angle = self.spatial_config.field_of_view_vertical / 2
            start_angle = (
                -(max_angle + bar_full_width) if direction == "TB"
                else (max_angle + bar_full_width)
            )
            end_angle = (
                (max_angle + bar_full_width) if direction == "TB"
                else -(max_angle + bar_full_width)
            )

        return start_angle, end_angle

    def calculate_frame_angle(self, direction: str, frame_index: int, total_frames: int) -> float:
        """Convert frame index to spatial angle"""
        start_angle, end_angle = self._calculate_angle_range(direction)

        if total_frames <= 1:
            return start_angle

        # Linear interpolation between start and end angles
        progress = frame_index / (total_frames - 1)
        angle = start_angle + progress * (end_angle - start_angle)
        return angle

    def generate_frame_at_angle(self, direction: str, angle: float, show_bar_mask: bool = True, frame_index: int = 0) -> np.ndarray:
        """Generate a single frame at the specified angle"""
        h, w = self.spatial_config.screen_height_pixels, self.spatial_config.screen_width_pixels

        # Start with background
        frame = np.full((h, w), self.stimulus_params.background_luminance, dtype=np.float32)

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

    def generate_frame_at_index(self, direction: str, frame_index: int, show_bar_mask: bool = True, num_cycles: int = 3) -> Tuple[np.ndarray, Dict[str, Any]]:
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
            frame = self.generate_frame_at_angle(direction, angle, show_bar_mask, frame_index)

            # Return frame with metadata
            metadata = {
                "frame_index": frame_index,
                "total_frames": total_frames,
                "angle_degrees": angle,
                "direction": direction,
                "show_bar_mask": show_bar_mask
            }

            return frame, metadata

        except Exception as e:
            logger.error(f"Error generating frame at index {frame_index}: {e}")
            raise

    def frame_to_base64_png(self, frame: np.ndarray) -> str:
        """Convert frame numpy array to base64 PNG string"""
        try:
            # Convert to PIL Image
            if len(frame.shape) == 2:  # Grayscale
                image = Image.fromarray(frame, mode='L')
            else:  # RGB
                image = Image.fromarray(frame, mode='RGB')

            # Save to base64
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            buffer.seek(0)

            # Encode as base64
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return f"data:image/png;base64,{img_base64}"

        except Exception as e:
            logger.error(f"Error converting frame to base64: {e}")
            raise

    def _generate_checkerboard_pattern(self, w: int, h: int, frame_index: int) -> np.ndarray:
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
        flicker_period_frames = int(fps / flicker_frequency_hz) if flicker_frequency_hz > 0 else float('inf')

        if flicker_period_frames != float('inf'):
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

    def generate_full_dataset(self, direction: str, num_cycles: int = 10) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate full frame sequence for acquisition (legacy compatibility)"""
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
            timestamps = np.arange(total_frames) * (1_000_000 // self.spatial_config.fps)

            logger.info(f"  Total frames: {total_frames}")
            logger.info(f"  Duration: {dataset_info['duration_sec']:.1f}s")
            logger.info(f"  Angle range: {start_angle:.1f}° to {end_angle:.1f}°")

            # Generate all frames
            h, w = self.spatial_config.screen_height_pixels, self.spatial_config.screen_width_pixels
            frames = np.zeros((total_frames, h, w), dtype=np.uint8)

            # Get spherical coordinates once for efficiency
            pixel_azimuth, pixel_altitude = (
                self.spherical_transform.screen_to_spherical_coordinates(
                    self.X_degrees, self.Y_degrees, self.spatial_config
                )
            )

            for i, current_angle in enumerate(angles):
                # Generate frame at this angle
                frame = self.generate_frame_at_angle(direction, current_angle, show_bar_mask=True, frame_index=i)
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
        logger.info(f"  Field of view: {self.spatial_config.field_of_view_horizontal:.1f}° x {self.spatial_config.field_of_view_vertical:.1f}°")

    def update_stimulus_params(self, params: Dict[str, Any]):
        """Update stimulus parameters"""
        for key, value in params.items():
            if hasattr(self.stimulus_params, key):
                setattr(self.stimulus_params, key, value)

        logger.info(f"Stimulus parameters updated")


# Global stimulus generator instance for IPC handlers
_stimulus_generator = None

def get_stimulus_generator() -> StimulusGenerator:
    """Get or create global stimulus generator instance"""
    global _stimulus_generator
    if _stimulus_generator is None:
        _stimulus_generator = StimulusGenerator()
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
            "background_luminance": generator.stimulus_params.background_luminance
        }

        return {
            "success": True,
            "parameters": params
        }
    except Exception as e:
        logger.error(f"Error getting stimulus parameters: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def handle_update_stimulus_parameters(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle update_stimulus_parameters IPC command"""
    try:
        generator = get_stimulus_generator()
        params = command.get('parameters', {})

        # Map frontend parameter names to backend names
        param_mapping = {
            "bar_width_deg": "bar_width_degrees",
            "drift_speed_deg_per_sec": "drift_speed_degrees_per_sec",
            "checker_size_deg": "checkerboard_size_degrees",
            "strobe_rate_hz": "flicker_frequency_hz",
            "contrast": "contrast",
            "background_luminance": "background_luminance"
        }

        # Update parameters
        update_dict = {}
        for frontend_key, backend_key in param_mapping.items():
            if frontend_key in params:
                update_dict[backend_key] = params[frontend_key]

        generator.update_stimulus_params(update_dict)

        return {
            "success": True,
            "message": "Stimulus parameters updated"
        }
    except Exception as e:
        logger.error(f"Error updating stimulus parameters: {e}")
        return {
            "success": False,
            "error": str(e)
        }


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
            "field_of_view_vertical": generator.spatial_config.field_of_view_vertical
        }

        return {
            "success": True,
            "configuration": config
        }
    except Exception as e:
        logger.error(f"Error getting spatial configuration: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def handle_update_spatial_configuration(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle update_spatial_configuration IPC command"""
    try:
        generator = get_stimulus_generator()
        config = command.get('configuration', {})

        generator.update_spatial_config(config)

        return {
            "success": True,
            "message": "Spatial configuration updated"
        }
    except Exception as e:
        logger.error(f"Error updating spatial configuration: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def handle_get_stimulus_info(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_stimulus_info IPC command - returns dataset information"""
    try:
        generator = get_stimulus_generator()
        direction = command.get('direction', 'LR')
        num_cycles = command.get('num_cycles', 3)

        dataset_info = generator.get_dataset_info(direction, num_cycles)

        if "error" in dataset_info:
            return {
                "success": False,
                "error": dataset_info["error"]
            }

        return {
            "success": True,
            "type": "stimulus_info",
            **dataset_info
        }

    except Exception as e:
        logger.error(f"Error getting stimulus info: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def handle_get_stimulus_frame(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_stimulus_frame IPC command - returns a single frame as base64 PNG"""
    try:
        generator = get_stimulus_generator()
        direction = command.get('direction', 'LR')
        frame_index = command.get('frame_index', 0)
        show_bar_mask = command.get('show_bar_mask', True)
        num_cycles = command.get('num_cycles', 3)

        # Generate frame and get metadata
        frame, metadata = generator.generate_frame_at_index(
            direction=direction,
            frame_index=frame_index,
            show_bar_mask=show_bar_mask,
            num_cycles=num_cycles
        )

        # Convert frame to base64 PNG
        frame_data = generator.frame_to_base64_png(frame)

        return {
            "success": True,
            "type": "stimulus_frame",
            "frame_data": frame_data,
            "frame_info": metadata
        }

    except Exception as e:
        logger.error(f"Error generating stimulus frame: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# Status tracking
_stimulus_status = {
    "is_presenting": False,
    "current_session": None
}

# Animation thread tracking
_animation_thread = None
_animation_stop_event = threading.Event()


def _stimulus_animation_loop(direction: str, show_bar_mask: bool):
    """Animation loop that runs in a separate thread to stream frames to frontend"""
    global _animation_stop_event

    try:
        generator = get_stimulus_generator()
        frame_index = 0
        start_time = time.time()

        # Calculate frame interval from strobe rate
        strobe_rate_hz = generator.stimulus_params.flicker_frequency_hz
        frame_interval = 1.0 / strobe_rate_hz

        logger.info(f"Starting stimulus animation: direction={direction}, mask={show_bar_mask}, rate={strobe_rate_hz}Hz")

        while not _animation_stop_event.is_set():
            try:
                # Generate frame
                frame = generator.generate_frame_at_angle(
                    direction=direction,
                    angle=0.0,  # Start angle - could be parameterized
                    show_bar_mask=show_bar_mask,
                    frame_index=frame_index
                )

                # Convert to base64 for frontend
                frame_data = generator._frame_to_base64(frame)

                # Send frame to frontend via IPC
                from .main import send_message_to_frontend
                send_message_to_frontend({
                    "type": "stimulus_frame",
                    "frame_data": frame_data,
                    "frame_index": frame_index,
                    "direction": direction,
                    "show_bar_mask": show_bar_mask,
                    "timestamp": time.time()
                })

                frame_index += 1

                # Sleep for precise timing
                elapsed_time = time.time() - start_time
                next_frame_time = frame_index * frame_interval
                sleep_time = next_frame_time - elapsed_time

                if sleep_time > 0:
                    time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Error in animation loop: {e}")
                break

    except Exception as e:
        logger.error(f"Animation loop failed: {e}")
    finally:
        logger.info("Stimulus animation stopped")


def _start_stimulus_animation(direction: str, show_bar_mask: bool):
    """Start the stimulus animation in a background thread"""
    global _animation_thread, _animation_stop_event

    # Stop any existing animation
    _stop_stimulus_animation()

    # Reset stop event and start new thread
    _animation_stop_event.clear()
    _animation_thread = threading.Thread(
        target=_stimulus_animation_loop,
        args=(direction, show_bar_mask),
        daemon=True
    )
    _animation_thread.start()


def _stop_stimulus_animation():
    """Stop the stimulus animation thread"""
    global _animation_thread, _animation_stop_event

    if _animation_thread is not None:
        _animation_stop_event.set()
        _animation_thread.join(timeout=1.0)  # Wait up to 1 second
        _animation_thread = None


def handle_get_stimulus_status(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_stimulus_status IPC command"""
    return {
        "success": True,
        "status": _stimulus_status.copy()
    }


def handle_start_stimulus(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle start_stimulus IPC command"""
    try:
        session_name = command.get('session_name', f'session_{int(time.time())}')
        direction = command.get('direction', 'LR')
        show_bar_mask = command.get('show_bar_mask', False)

        # Update status
        _stimulus_status["is_presenting"] = True
        _stimulus_status["current_session"] = session_name

        # Start the animation loop in a separate thread
        _start_stimulus_animation(direction, show_bar_mask)

        logger.info(f"Stimulus presentation started: {session_name}, direction: {direction}, mask: {show_bar_mask}")

        return {
            "success": True,
            "message": f"Stimulus started: {session_name}"
        }
    except Exception as e:
        logger.error(f"Error starting stimulus: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def handle_stop_stimulus(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle stop_stimulus IPC command"""
    try:
        # Stop animation thread
        _stop_stimulus_animation()

        # Update status
        session_name = _stimulus_status["current_session"]
        _stimulus_status["is_presenting"] = False
        _stimulus_status["current_session"] = None

        logger.info(f"Stimulus presentation stopped: {session_name}")

        return {
            "success": True,
            "message": "Stimulus stopped"
        }
    except Exception as e:
        logger.error(f"Error stopping stimulus: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def handle_generate_stimulus_preview(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle generate_stimulus_preview IPC command - legacy compatibility"""
    try:
        generator = get_stimulus_generator()
        direction = command.get('direction', 'LR')

        # Get dataset info as preview information
        dataset_info = generator.get_dataset_info(direction, 3)

        if "error" in dataset_info:
            return {
                "success": False,
                "error": dataset_info["error"]
            }

        # Format as legacy preview response
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
                "vertical": generator.spatial_config.field_of_view_vertical
            },
            "resolution": {
                "width_px": generator.spatial_config.screen_width_pixels,
                "height_px": generator.spatial_config.screen_height_pixels
            },
            "timing": {
                "fps": generator.spatial_config.fps,
                "frame_duration_ms": 1000.0 / generator.spatial_config.fps,
                "strobe_period_ms": 1000.0 / generator.stimulus_params.flicker_frequency_hz if generator.stimulus_params.flicker_frequency_hz > 0 else None
            }
        }

        return {
            "success": True,
            "type": "stimulus_preview",
            "preview": preview_info
        }
    except Exception as e:
        logger.error(f"Error generating stimulus preview: {e}")
        return {
            "success": False,
            "error": str(e)
        }