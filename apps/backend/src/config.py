"""Backend configuration primitives.

All runtime configuration is expressed as immutable dataclasses so that
components receive explicit settings during initialization. This keeps the
startup sequence deterministic and avoids hidden globals or implicit defaults.

Simplified from original implementation: Added to_dict() methods and from_file() static method.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List


@dataclass(frozen=True)
class IPCConfig:
    """ZeroMQ channel configuration."""

    transport: str
    health_port: int
    sync_port: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "transport": self.transport,
            "health_port": self.health_port,
            "sync_port": self.sync_port,
        }


@dataclass(frozen=True)
class SharedMemoryConfig:
    """Shared memory streaming configuration."""

    stream_name: str
    buffer_size_mb: int
    metadata_port: int  # Port for stimulus frame metadata
    camera_metadata_port: int  # Port for camera frame metadata
    analysis_metadata_port: int  # Port for analysis frame metadata

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "stream_name": self.stream_name,
            "buffer_size_mb": self.buffer_size_mb,
            "metadata_port": self.metadata_port,
            "camera_metadata_port": self.camera_metadata_port,
            "analysis_metadata_port": self.analysis_metadata_port,
        }


@dataclass(frozen=True)
class CameraConfig:
    """Camera configuration."""

    selected_camera: str
    camera_width_px: int
    camera_height_px: int
    camera_fps: int
    available_cameras: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "selected_camera": self.selected_camera,
            "camera_width_px": self.camera_width_px,
            "camera_height_px": self.camera_height_px,
            "camera_fps": self.camera_fps,
            "available_cameras": self.available_cameras,
        }


@dataclass(frozen=True)
class MonitorConfig:
    """Monitor configuration."""

    selected_display: str
    monitor_width_px: int
    monitor_height_px: int
    monitor_width_cm: float
    monitor_height_cm: float
    monitor_distance_cm: float
    monitor_fps: int
    monitor_lateral_angle_deg: float
    monitor_tilt_angle_deg: float
    available_displays: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "selected_display": self.selected_display,
            "monitor_width_px": self.monitor_width_px,
            "monitor_height_px": self.monitor_height_px,
            "monitor_width_cm": self.monitor_width_cm,
            "monitor_height_cm": self.monitor_height_cm,
            "monitor_distance_cm": self.monitor_distance_cm,
            "monitor_fps": self.monitor_fps,
            "monitor_lateral_angle_deg": self.monitor_lateral_angle_deg,
            "monitor_tilt_angle_deg": self.monitor_tilt_angle_deg,
            "available_displays": self.available_displays,
        }


@dataclass(frozen=True)
class StimulusConfig:
    """Stimulus configuration."""

    bar_width_deg: float
    checker_size_deg: float
    drift_speed_deg_per_sec: float
    contrast: float
    background_luminance: float
    strobe_rate_hz: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "bar_width_deg": self.bar_width_deg,
            "checker_size_deg": self.checker_size_deg,
            "drift_speed_deg_per_sec": self.drift_speed_deg_per_sec,
            "contrast": self.contrast,
            "background_luminance": self.background_luminance,
            "strobe_rate_hz": self.strobe_rate_hz,
        }


@dataclass(frozen=True)
class AcquisitionConfig:
    """Acquisition configuration."""

    directions: List[str]
    cycles: int
    baseline_sec: float
    between_sec: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "directions": self.directions,
            "cycles": self.cycles,
            "baseline_sec": self.baseline_sec,
            "between_sec": self.between_sec,
        }


@dataclass(frozen=True)
class AnalysisConfig:
    """Analysis configuration (all literature-based parameters)."""

    # Core thresholding (Kalatsky & Stryker 2003)
    coherence_threshold: float  # Signal reliability threshold

    # Spatial calibration (Juavinett et al. 2017)
    ring_size_mm: float  # Imaging field diameter for pixels-to-mm conversion

    # Filtering (Juavinett et al. 2017)
    phase_filter_sigma: float  # Gaussian smoothing of phase maps before conversion
    smoothing_sigma: float  # Gaussian smoothing after phase-to-position conversion

    # Gradient computation (Juavinett et al. 2017)
    gradient_window_size: int  # Sobel kernel size for retinotopic gradients

    # Response thresholding (Juavinett et al. 2017)
    magnitude_threshold: float  # Per-direction magnitude threshold
    response_threshold_percent: int  # Percentile-based response filtering

    # VFS and area filtering
    vfs_threshold_sd: float  # Statistical threshold for VFS (alternative method)
    area_min_size_mm2: float  # Minimum area size (noise filtering)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "coherence_threshold": self.coherence_threshold,
            "ring_size_mm": self.ring_size_mm,
            "phase_filter_sigma": self.phase_filter_sigma,
            "smoothing_sigma": self.smoothing_sigma,
            "gradient_window_size": self.gradient_window_size,
            "magnitude_threshold": self.magnitude_threshold,
            "response_threshold_percent": self.response_threshold_percent,
            "vfs_threshold_sd": self.vfs_threshold_sd,
            "area_min_size_mm2": self.area_min_size_mm2,
        }


@dataclass(frozen=True)
class SessionConfig:
    """Session configuration."""

    session_name: str
    animal_id: str
    animal_age: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_name": self.session_name,
            "animal_id": self.animal_id,
            "animal_age": self.animal_age,
        }


@dataclass(frozen=True)
class ParameterStoreConfig:
    """Parameter persistence configuration."""

    file_path: Path

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_path": str(self.file_path),
        }


@dataclass(frozen=True)
class LoggingConfig:
    """Logging configuration."""

    log_file: Path

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "log_file": str(self.log_file),
        }


@dataclass(frozen=True)
class AppConfig:
    """Composite application configuration."""

    ipc: IPCConfig
    shared_memory: SharedMemoryConfig
    camera: CameraConfig
    monitor: MonitorConfig
    stimulus: StimulusConfig
    acquisition: AcquisitionConfig
    analysis: AnalysisConfig
    session: SessionConfig
    parameters: ParameterStoreConfig
    logging: LoggingConfig

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ipc": self.ipc.to_dict(),
            "shared_memory": self.shared_memory.to_dict(),
            "camera": self.camera.to_dict(),
            "monitor": self.monitor.to_dict(),
            "stimulus": self.stimulus.to_dict(),
            "acquisition": self.acquisition.to_dict(),
            "analysis": self.analysis.to_dict(),
            "session": self.session.to_dict(),
            "parameters": self.parameters.to_dict(),
            "logging": self.logging.to_dict(),
        }

    @staticmethod
    def from_file(path: str) -> "AppConfig":
        """Load configuration from JSON file.

        Args:
            path: Path to JSON configuration file

        Returns:
            AppConfig instance populated from file
        """
        file_path = Path(path)
        with open(file_path) as f:
            data = json.load(f)

        # Extract current values from JSON structure
        current = data.get("current", {})

        # Determine backend root and paths
        backend_root = Path(__file__).resolve().parents[1]
        parameters_file = backend_root / "config" / "isi_parameters.json"
        logs_file = backend_root / "logs" / "isi_macroscope.log"

        parameters_file.parent.mkdir(parents=True, exist_ok=True)
        logs_file.parent.mkdir(parents=True, exist_ok=True)

        # Build configuration objects from JSON data
        return AppConfig(
            ipc=IPCConfig(
                transport="tcp",
                health_port=5555,
                sync_port=5558,
            ),
            shared_memory=SharedMemoryConfig(
                stream_name="stimulus_stream",
                buffer_size_mb=100,
                metadata_port=5557,  # Stimulus frames
                camera_metadata_port=5559,  # Camera frames
                analysis_metadata_port=5561,  # Analysis frames
            ),
            camera=CameraConfig(
                selected_camera=current.get("camera", {}).get("selected_camera", ""),
                camera_width_px=current.get("camera", {}).get("camera_width_px", -1),
                camera_height_px=current.get("camera", {}).get("camera_height_px", -1),
                camera_fps=current.get("camera", {}).get("camera_fps", -1),
                available_cameras=current.get("camera", {}).get("available_cameras", []),
            ),
            monitor=MonitorConfig(
                selected_display=current.get("monitor", {}).get("selected_display", ""),
                monitor_width_px=current.get("monitor", {}).get("monitor_width_px", -1),
                monitor_height_px=current.get("monitor", {}).get("monitor_height_px", -1),
                monitor_width_cm=current.get("monitor", {}).get("monitor_width_cm", 60.96),
                monitor_height_cm=current.get("monitor", {}).get("monitor_height_cm", 36.195),
                monitor_distance_cm=current.get("monitor", {}).get("monitor_distance_cm", 10.0),
                monitor_fps=current.get("monitor", {}).get("monitor_fps", -1),
                monitor_lateral_angle_deg=current.get("monitor", {}).get("monitor_lateral_angle_deg", 30.0),
                monitor_tilt_angle_deg=current.get("monitor", {}).get("monitor_tilt_angle_deg", 20.0),
                available_displays=current.get("monitor", {}).get("available_displays", []),
            ),
            stimulus=StimulusConfig(
                bar_width_deg=current.get("stimulus", {}).get("bar_width_deg", 20.0),
                checker_size_deg=current.get("stimulus", {}).get("checker_size_deg", 25.0),
                drift_speed_deg_per_sec=current.get("stimulus", {}).get("drift_speed_deg_per_sec", 9.0),
                contrast=current.get("stimulus", {}).get("contrast", 1.0),
                background_luminance=current.get("stimulus", {}).get("background_luminance", 0.0),
                strobe_rate_hz=current.get("stimulus", {}).get("strobe_rate_hz", 6.0),
            ),
            acquisition=AcquisitionConfig(
                directions=current.get("acquisition", {}).get("directions", ["LR", "RL", "TB", "BT"]),
                cycles=current.get("acquisition", {}).get("cycles", 10),
                baseline_sec=current.get("acquisition", {}).get("baseline_sec", 5.0),
                between_sec=current.get("acquisition", {}).get("between_sec", 5.0),
            ),
            analysis=AnalysisConfig(
                coherence_threshold=current.get("analysis", {}).get("coherence_threshold", 0.3),
                ring_size_mm=current.get("analysis", {}).get("ring_size_mm", 2.0),
                phase_filter_sigma=current.get("analysis", {}).get("phase_filter_sigma", 2.0),
                smoothing_sigma=current.get("analysis", {}).get("smoothing_sigma", 3.0),
                gradient_window_size=current.get("analysis", {}).get("gradient_window_size", 3),
                magnitude_threshold=current.get("analysis", {}).get("magnitude_threshold", 0.3),
                response_threshold_percent=current.get("analysis", {}).get("response_threshold_percent", 20),
                vfs_threshold_sd=current.get("analysis", {}).get("vfs_threshold_sd", 2.0),
                area_min_size_mm2=current.get("analysis", {}).get("area_min_size_mm2", 0.1),
            ),
            session=SessionConfig(
                session_name=current.get("session", {}).get("session_name", ""),
                animal_id=current.get("session", {}).get("animal_id", ""),
                animal_age=current.get("session", {}).get("animal_age", ""),
            ),
            parameters=ParameterStoreConfig(
                file_path=parameters_file,
            ),
            logging=LoggingConfig(
                log_file=logs_file,
            ),
        )

    @staticmethod
    def default() -> "AppConfig":
        """Build the default configuration from the parameter file.

        IMPORTANT: Loads defaults from the 'default' section of isi_parameters.json.
        NO hardcoded defaults - the config file is the single source of truth.
        """
        backend_root = Path(__file__).resolve().parents[1]
        parameters_file = backend_root / "config" / "isi_parameters.json"

        # Load from the 'default' section of the parameter file
        with open(parameters_file) as f:
            data = json.load(f)

        defaults = data.get("default", {})

        # Paths
        logs_file = backend_root / "logs" / "isi_macroscope.log"
        parameters_file.parent.mkdir(parents=True, exist_ok=True)
        logs_file.parent.mkdir(parents=True, exist_ok=True)

        return AppConfig(
            ipc=IPCConfig(
                transport="tcp",
                health_port=5555,
                sync_port=5558,
            ),
            shared_memory=SharedMemoryConfig(
                stream_name="stimulus_stream",
                buffer_size_mb=100,
                metadata_port=5557,
                camera_metadata_port=5559,
                analysis_metadata_port=5561,
            ),
            camera=CameraConfig(
                selected_camera=defaults.get("camera", {}).get("selected_camera", ""),
                camera_width_px=defaults.get("camera", {}).get("camera_width_px", -1),
                camera_height_px=defaults.get("camera", {}).get("camera_height_px", -1),
                camera_fps=defaults.get("camera", {}).get("camera_fps", -1),
                available_cameras=defaults.get("camera", {}).get("available_cameras", []),
            ),
            monitor=MonitorConfig(
                selected_display=defaults.get("monitor", {}).get("selected_display", ""),
                monitor_width_px=defaults.get("monitor", {}).get("monitor_width_px", -1),
                monitor_height_px=defaults.get("monitor", {}).get("monitor_height_px", -1),
                monitor_width_cm=defaults.get("monitor", {}).get("monitor_width_cm", 60.96),
                monitor_height_cm=defaults.get("monitor", {}).get("monitor_height_cm", 36.195),
                monitor_distance_cm=defaults.get("monitor", {}).get("monitor_distance_cm", 10.0),
                monitor_fps=defaults.get("monitor", {}).get("monitor_fps", -1),
                monitor_lateral_angle_deg=defaults.get("monitor", {}).get("monitor_lateral_angle_deg", 30.0),
                monitor_tilt_angle_deg=defaults.get("monitor", {}).get("monitor_tilt_angle_deg", 20.0),
                available_displays=defaults.get("monitor", {}).get("available_displays", []),
            ),
            stimulus=StimulusConfig(
                bar_width_deg=defaults.get("stimulus", {}).get("bar_width_deg", 20.0),
                checker_size_deg=defaults.get("stimulus", {}).get("checker_size_deg", 25.0),
                drift_speed_deg_per_sec=defaults.get("stimulus", {}).get("drift_speed_deg_per_sec", 9.0),
                contrast=defaults.get("stimulus", {}).get("contrast", 1.0),
                background_luminance=defaults.get("stimulus", {}).get("background_luminance", 0.0),
                strobe_rate_hz=defaults.get("stimulus", {}).get("strobe_rate_hz", 6.0),
            ),
            acquisition=AcquisitionConfig(
                directions=defaults.get("acquisition", {}).get("directions", ["LR", "RL", "TB", "BT"]),
                cycles=defaults.get("acquisition", {}).get("cycles", 10),
                baseline_sec=defaults.get("acquisition", {}).get("baseline_sec", 5.0),
                between_sec=defaults.get("acquisition", {}).get("between_sec", 5.0),
            ),
            analysis=AnalysisConfig(
                coherence_threshold=defaults.get("analysis", {}).get("coherence_threshold", 0.3),
                ring_size_mm=defaults.get("analysis", {}).get("ring_size_mm", 2.0),
                phase_filter_sigma=defaults.get("analysis", {}).get("phase_filter_sigma", 2.0),
                smoothing_sigma=defaults.get("analysis", {}).get("smoothing_sigma", 3.0),
                gradient_window_size=defaults.get("analysis", {}).get("gradient_window_size", 3),
                magnitude_threshold=defaults.get("analysis", {}).get("magnitude_threshold", 0.3),
                response_threshold_percent=defaults.get("analysis", {}).get("response_threshold_percent", 20),
                vfs_threshold_sd=defaults.get("analysis", {}).get("vfs_threshold_sd", 2.0),
                area_min_size_mm2=defaults.get("analysis", {}).get("area_min_size_mm2", 0.1),
            ),
            session=SessionConfig(
                session_name=defaults.get("session", {}).get("session_name", ""),
                animal_id=defaults.get("session", {}).get("animal_id", ""),
                animal_age=defaults.get("session", {}).get("animal_age", ""),
            ),
            parameters=ParameterStoreConfig(
                file_path=parameters_file,
            ),
            logging=LoggingConfig(
                log_file=logs_file,
            ),
        )
