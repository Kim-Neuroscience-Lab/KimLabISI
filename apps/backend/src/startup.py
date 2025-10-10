"""Startup coordination and validation.

Checks hardware availability, validates configuration, and coordinates
service initialization order. Pure functions and simple coordinator.
NO service locator dependencies.
"""

from __future__ import annotations

import logging
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""

    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class SystemRequirements:
    """Minimum system requirements."""

    min_python_version: Tuple[int, int, int] = (3, 10, 0)
    min_memory_mb: int = 2048
    min_disk_space_gb: int = 1
    required_packages: list[str] = None

    def __post_init__(self):
        if self.required_packages is None:
            self.required_packages = [
                "numpy",
                "opencv-python",
                "torch",
                "psutil",
                "zmq",
            ]


class StartupCoordinator:
    """Coordinates system startup and validates requirements.

    Pure coordinator with no dependencies on other services.
    All validation is performed using static methods or simple state.
    """

    def __init__(self):
        """Initialize startup coordinator."""
        self.validation_results: Dict[str, ValidationResult] = {}
        logger.info("StartupCoordinator initialized")

    @staticmethod
    def validate_system_requirements(
        requirements: Optional[SystemRequirements] = None,
    ) -> ValidationResult:
        """Validate system meets minimum requirements.

        Args:
            requirements: System requirements to validate against

        Returns:
            ValidationResult with success status and any error messages
        """
        if requirements is None:
            requirements = SystemRequirements()

        errors = []

        # Check Python version
        current_version = sys.version_info[:3]
        if current_version < requirements.min_python_version:
            errors.append(
                f"Python {'.'.join(map(str, requirements.min_python_version))}+ required, "
                f"found {'.'.join(map(str, current_version))}"
            )
        else:
            logger.info(
                "Python version OK: %s", ".".join(map(str, current_version))
            )

        # Check memory
        try:
            import psutil

            memory_mb = psutil.virtual_memory().total / (1024 * 1024)
            if memory_mb < requirements.min_memory_mb:
                errors.append(
                    f"Minimum {requirements.min_memory_mb}MB RAM required, "
                    f"found {memory_mb:.0f}MB"
                )
            else:
                logger.info("Memory OK: %.0f MB", memory_mb)
        except ImportError:
            errors.append("psutil package not available for memory check")

        # Check disk space
        try:
            import psutil

            disk_gb = psutil.disk_usage("/").free / (1024 * 1024 * 1024)
            if disk_gb < requirements.min_disk_space_gb:
                errors.append(
                    f"Minimum {requirements.min_disk_space_gb}GB free disk space required, "
                    f"found {disk_gb:.1f}GB"
                )
            else:
                logger.info("Disk space OK: %.1f GB free", disk_gb)
        except ImportError:
            pass  # Already reported above

        # Check required packages
        missing_packages = []
        for package in requirements.required_packages:
            try:
                # Map common package names to import names
                import_name = package
                if package == "opencv-python":
                    import_name = "cv2"
                elif package == "pillow":
                    import_name = "PIL"

                __import__(import_name)
                logger.debug("Package OK: %s", package)
            except ImportError:
                missing_packages.append(package)

        if missing_packages:
            errors.append(
                f"Missing required packages: {', '.join(missing_packages)}"
            )
        else:
            logger.info("All required packages available")

        if errors:
            return ValidationResult(
                success=False,
                message="System requirements validation failed",
                details={"errors": errors},
            )

        return ValidationResult(
            success=True,
            message="System requirements validated successfully",
            details={
                "python_version": ".".join(map(str, current_version)),
                "platform": platform.system(),
                "platform_version": platform.version(),
            },
        )

    @staticmethod
    def check_hardware_availability() -> Dict[str, Any]:
        """Check which hardware devices are available.

        Returns:
            Dictionary with hardware availability information
        """
        hardware_info = {
            "cameras": 0,
            "camera_indices": [],
            "gpu": False,
            "gpu_type": None,
            "displays": 0,
            "display_info": [],
            "platform": platform.system(),
        }

        # Check cameras (simple OpenCV enumeration)
        try:
            import cv2

            camera_indices = []
            # Test up to 10 camera indices
            for idx in range(10):
                cap = cv2.VideoCapture(idx)
                if cap.isOpened():
                    camera_indices.append(idx)
                    cap.release()

            hardware_info["cameras"] = len(camera_indices)
            hardware_info["camera_indices"] = camera_indices
            logger.info("Cameras detected: %d", len(camera_indices))
        except ImportError:
            logger.warning("OpenCV not available for camera detection")
        except Exception as exc:
            logger.warning("Camera detection failed: %s", exc)

        # Check GPU
        try:
            import torch

            if torch.cuda.is_available():
                hardware_info["gpu"] = True
                hardware_info["gpu_type"] = "CUDA"
                hardware_info["gpu_count"] = torch.cuda.device_count()
                logger.info("GPU detected: CUDA (%d devices)", torch.cuda.device_count())
            elif torch.backends.mps.is_available():
                hardware_info["gpu"] = True
                hardware_info["gpu_type"] = "MPS (Apple Silicon)"
                logger.info("GPU detected: MPS (Apple Silicon)")
            else:
                logger.info("No GPU detected, using CPU")
        except ImportError:
            logger.warning("PyTorch not available for GPU detection")

        # Check displays (use simple platform detection)
        try:
            if platform.system() == "Darwin":  # macOS
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType", "-json"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    import json

                    data = json.loads(result.stdout)
                    displays = data.get("SPDisplaysDataType", [])
                    hardware_info["displays"] = len(displays)
                    logger.info("Displays detected: %d", len(displays))
            elif platform.system() == "Linux":
                result = subprocess.run(
                    ["xrandr", "--query"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    connected = result.stdout.count(" connected")
                    hardware_info["displays"] = connected
                    logger.info("Displays detected: %d", connected)
            elif platform.system() == "Windows":
                # Windows display detection requires win32api
                try:
                    import win32api

                    monitors = win32api.EnumDisplayMonitors()
                    hardware_info["displays"] = len(monitors)
                    logger.info("Displays detected: %d", len(monitors))
                except ImportError:
                    logger.warning("win32api not available for display detection")
        except subprocess.TimeoutExpired:
            logger.warning("Display detection timed out")
        except Exception as exc:
            logger.warning("Display detection failed: %s", exc)

        return hardware_info

    @staticmethod
    def validate_config_file(config_path: str | Path) -> ValidationResult:
        """Validate configuration file exists and is readable.

        Args:
            config_path: Path to configuration file

        Returns:
            ValidationResult indicating if config is valid
        """
        config_path = Path(config_path)

        if not config_path.exists():
            return ValidationResult(
                success=False,
                message=f"Configuration file not found: {config_path}",
            )

        if not config_path.is_file():
            return ValidationResult(
                success=False,
                message=f"Configuration path is not a file: {config_path}",
            )

        # Try to read and parse as JSON
        try:
            import json

            with open(config_path) as f:
                data = json.load(f)

            # Basic structure validation
            required_keys = ["current", "defaults", "parameter_config"]
            missing_keys = [key for key in required_keys if key not in data]

            if missing_keys:
                return ValidationResult(
                    success=False,
                    message=f"Configuration file missing required keys: {missing_keys}",
                    details={"path": str(config_path)},
                )

            return ValidationResult(
                success=True,
                message="Configuration file validated successfully",
                details={
                    "path": str(config_path),
                    "size_bytes": config_path.stat().st_size,
                },
            )

        except json.JSONDecodeError as exc:
            return ValidationResult(
                success=False,
                message=f"Configuration file is not valid JSON: {exc}",
                details={"path": str(config_path)},
            )
        except Exception as exc:
            return ValidationResult(
                success=False,
                message=f"Error reading configuration file: {exc}",
                details={"path": str(config_path)},
            )

    def run_all_validations(
        self, config_path: Optional[str | Path] = None
    ) -> ValidationResult:
        """Run all startup validations.

        Args:
            config_path: Optional path to configuration file to validate

        Returns:
            Aggregate validation result
        """
        logger.info("Running startup validations...")

        # Validate system requirements
        self.validation_results["system"] = self.validate_system_requirements()

        # Validate config if provided
        if config_path:
            self.validation_results["config"] = self.validate_config_file(config_path)

        # Check hardware availability
        hardware_info = self.check_hardware_availability()
        self.validation_results["hardware"] = ValidationResult(
            success=True,
            message="Hardware detection completed",
            details=hardware_info,
        )

        # Aggregate results
        all_successful = all(
            result.success for result in self.validation_results.values()
        )

        if all_successful:
            logger.info("All startup validations passed")
            return ValidationResult(
                success=True,
                message="All startup validations passed",
                details={"validation_count": len(self.validation_results)},
            )
        else:
            failed = [
                name
                for name, result in self.validation_results.items()
                if not result.success
            ]
            logger.error("Startup validation failed: %s", ", ".join(failed))
            return ValidationResult(
                success=False,
                message=f"Startup validation failed: {', '.join(failed)}",
                details={
                    "failed_validations": failed,
                    "results": {
                        name: result.message
                        for name, result in self.validation_results.items()
                    },
                },
            )


def validate_system_requirements() -> Tuple[bool, list[str]]:
    """Validate system meets minimum requirements (simple function API).

    Returns:
        Tuple of (success, list of error messages)
    """
    coordinator = StartupCoordinator()
    result = coordinator.validate_system_requirements()
    errors = result.details.get("errors", []) if result.details else []
    return (result.success, errors)


def check_hardware_availability() -> Dict[str, Any]:
    """Check which hardware devices are available (simple function API).

    Returns:
        Dictionary with hardware availability information
    """
    return StartupCoordinator.check_hardware_availability()
