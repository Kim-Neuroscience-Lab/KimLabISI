"""
ISI Control System - Centralized Parameter Manager

This module provides centralized parameter management with persistence,
making the backend the Single Source of Truth for all system parameters.

Features:
- Type-safe parameter definitions using dataclasses
- JSON-based persistence with session management
- Parameter validation and defaults
- Thread-safe operations
- Export/import functionality
"""

import json
import logging
import threading
from dataclasses import dataclass, field, asdict, fields
from pathlib import Path
from typing import Dict, Any, List, Optional, Type, Union
from datetime import datetime

logger = logging.getLogger(__name__)

# Parameter Type Definitions
@dataclass
class SessionParameters:
    """Session metadata and identification parameters"""
    session_name: str = ""
    animal_id: str = ""
    animal_age: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_modified: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class MonitorParameters:
    """Monitor and display configuration parameters"""
    selected_display: str = ""
    available_displays: List[str] = field(default_factory=list)
    monitor_distance_cm: float = 10.0
    monitor_lateral_angle_deg: float = 0.0
    monitor_tilt_angle_deg: float = 0.0
    monitor_width_cm: float = 60.96
    monitor_height_cm: float = 36.195
    monitor_width_px: int = -1  # -1 indicates not detected/failed detection
    monitor_height_px: int = -1  # -1 indicates not detected/failed detection
    monitor_fps: int = -1  # -1 indicates not detected/failed detection

@dataclass
class StimulusParameters:
    """Stimulus generation and presentation parameters"""
    checker_size_deg: float = 25.0
    bar_width_deg: float = 20.0
    drift_speed_deg_per_sec: float = 9.0
    strobe_rate_hz: float = 6.0
    contrast: float = 0.8

@dataclass
class CameraParameters:
    """Camera acquisition and configuration parameters"""
    selected_camera: str = ""
    available_cameras: List[str] = field(default_factory=list)
    camera_fps: int = -1  # -1 indicates not detected/failed detection
    camera_width_px: int = -1  # -1 indicates not detected/failed detection
    camera_height_px: int = -1  # -1 indicates not detected/failed detection

@dataclass
class AcquisitionParameters:
    """Experimental acquisition timing and protocol parameters"""
    baseline_sec: float = 5.0
    between_sec: float = 5.0
    cycles: int = 3
    directions: List[str] = field(default_factory=lambda: ["LR", "RL"])

@dataclass
class AnalysisParameters:
    """Data analysis and processing parameters"""
    ring_size_mm: float = 1.0
    vfs_threshold_sd: float = 2.0
    smoothing_sigma: float = 1.0
    magnitude_threshold: float = 0.1
    phase_filter_sigma: float = 0.5
    gradient_window_size: int = 3
    area_min_size_mm2: float = 0.1
    response_threshold_percent: float = 5.0

@dataclass
class AllParameters:
    """Container for all parameter groups"""
    session: SessionParameters = field(default_factory=SessionParameters)
    monitor: MonitorParameters = field(default_factory=MonitorParameters)
    stimulus: StimulusParameters = field(default_factory=StimulusParameters)
    camera: CameraParameters = field(default_factory=CameraParameters)
    acquisition: AcquisitionParameters = field(default_factory=AcquisitionParameters)
    analysis: AnalysisParameters = field(default_factory=AnalysisParameters)


class ParameterValidationError(Exception):
    """Raised when parameter validation fails"""
    pass


class ParameterManager:
    """
    Centralized parameter management with persistence and validation.

    This class provides the Single Source of Truth for all system parameters,
    with automatic persistence to JSON files and session management.
    """

    # Parameter type mapping for dynamic access
    PARAMETER_TYPES = {
        'session': SessionParameters,
        'monitor': MonitorParameters,
        'stimulus': StimulusParameters,
        'camera': CameraParameters,
        'acquisition': AcquisitionParameters,
        'analysis': AnalysisParameters
    }

    # Parameter validation ranges
    VALIDATION_RULES = {
        'monitor': {
            'monitor_distance_cm': (0.1, 100.0),
            'monitor_lateral_angle_deg': (-90.0, 90.0),
            'monitor_tilt_angle_deg': (-90.0, 90.0),
            'monitor_width_cm': (1.0, 200.0),
            'monitor_height_cm': (1.0, 200.0),
            'monitor_width_px': (100, 10000),
            'monitor_height_px': (100, 10000),
            'monitor_fps': (1, 300)
        },
        'stimulus': {
            'checker_size_deg': (0.1, 180.0),
            'bar_width_deg': (0.1, 180.0),
            'drift_speed_deg_per_sec': (0.1, 1000.0),
            'strobe_rate_hz': (0.1, 100.0),
            'contrast': (0.0, 1.0)
        },
        'camera': {
            'camera_fps': (1, 300),
            'camera_width_px': (100, 10000),
            'camera_height_px': (100, 10000)
        },
        'acquisition': {
            'baseline_sec': (0.1, 3600.0),
            'between_sec': (0.1, 3600.0),
            'cycles': (1, 1000)
        },
        'analysis': {
            'ring_size_mm': (0.01, 100.0),
            'vfs_threshold_sd': (0.1, 10.0),
            'smoothing_sigma': (0.01, 10.0),
            'magnitude_threshold': (0.0, 1.0),
            'phase_filter_sigma': (0.01, 10.0),
            'gradient_window_size': (1, 100),
            'area_min_size_mm2': (0.001, 1000.0),
            'response_threshold_percent': (0.0, 100.0)
        }
    }

    def __init__(self, config_file: str = "isi_parameters.json", config_dir: Optional[str] = None):
        """
        Initialize the parameter manager.

        Args:
            config_file: Name of the JSON configuration file
            config_dir: Directory to store configuration (default: current working directory)
        """
        self.config_dir = Path(config_dir) if config_dir else Path.cwd()
        self.config_file = self.config_dir / config_file
        self._lock = threading.RLock()  # Reentrant lock for thread safety

        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Load existing parameters
        self._load_configuration()

        # Clear hardware-specific fields to ensure fresh detection
        self._clear_hardware_specific_fields()

        logger.info(f"ParameterManager initialized with config file: {self.config_file}")

    def _clear_hardware_specific_fields(self):
        """Clear hardware-specific fields that should be refreshed on each startup"""
        with self._lock:
            # Clear camera hardware info
            self._current_params.camera.available_cameras = []
            self._current_params.camera.selected_camera = ""
            self._current_params.camera.camera_fps = -1
            self._current_params.camera.camera_width_px = -1
            self._current_params.camera.camera_height_px = -1

            # Clear display hardware info
            self._current_params.monitor.available_displays = []
            self._current_params.monitor.selected_display = ""
            self._current_params.monitor.monitor_fps = -1
            self._current_params.monitor.monitor_width_px = -1
            self._current_params.monitor.monitor_height_px = -1

            # Save the updated parameters
            self._save_to_file()
            logger.info("Cleared hardware-specific fields for fresh detection")

    def _load_configuration(self):
        """Load parameter configuration from the config file"""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                data = json.load(f)

            # Load the current configuration
            self._current_params = self._dict_to_parameters(data['current'])

            # Load the default configuration for reset functionality
            self._default_params = self._dict_to_parameters(data['default'])

            logger.info("Loaded parameter configuration")
        else:
            # Create initial configuration
            self._current_params = AllParameters()
            self._default_params = AllParameters()
            self._save_to_file()
            logger.info("Created initial parameter configuration")

    def _save_to_file(self):
        """Save parameter configuration to the config file"""
        # Build the configuration structure
        data = {
            'current': self._parameters_to_dict(self._current_params),
            'default': self._parameters_to_dict(self._default_params)
        }

        # Write to file with backup
        backup_file = self.config_file.with_suffix('.json.backup')
        if self.config_file.exists():
            self.config_file.rename(backup_file)

        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=2, sort_keys=True)

        # Remove backup if save was successful
        if backup_file.exists():
            backup_file.unlink()

        logger.debug("Parameter configuration saved to file")

    def _parameters_to_dict(self, params: AllParameters) -> Dict[str, Any]:
        """Convert AllParameters to dictionary format"""
        return {
            'session': asdict(params.session),
            'monitor': asdict(params.monitor),
            'stimulus': asdict(params.stimulus),
            'camera': asdict(params.camera),
            'acquisition': asdict(params.acquisition),
            'analysis': asdict(params.analysis)
        }

    def _dict_to_parameters(self, data: Dict[str, Any]) -> AllParameters:
        """Convert dictionary to AllParameters object"""
        params = AllParameters()

        for group_name, param_class in self.PARAMETER_TYPES.items():
            if group_name in data:
                group_data = data[group_name]
                # Create parameter object from dict, filtering unknown fields
                valid_fields = {f.name for f in fields(param_class)}
                filtered_data = {k: v for k, v in group_data.items() if k in valid_fields}
                setattr(params, group_name, param_class(**filtered_data))

        return params

    def validate_parameter_group(self, group_name: str, params: Dict[str, Any]) -> List[str]:
        """
        Validate a parameter group against defined rules.

        Args:
            group_name: Name of the parameter group
            params: Dictionary of parameter values

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if group_name not in self.PARAMETER_TYPES:
            errors.append(f"Unknown parameter group: {group_name}")
            return errors

        param_class = self.PARAMETER_TYPES[group_name]
        valid_fields = {f.name: f.type for f in fields(param_class)}
        validation_rules = self.VALIDATION_RULES.get(group_name, {})

        for param_name, value in params.items():
            if param_name not in valid_fields:
                errors.append(f"Unknown parameter: {group_name}.{param_name}")
                continue

            # Type validation
            expected_type = valid_fields[param_name]
            if hasattr(expected_type, '__origin__'):  # Handle List[str] etc.
                if expected_type.__origin__ is list:
                    if not isinstance(value, list):
                        errors.append(f"Parameter {group_name}.{param_name} must be a list")
                        continue
                elif expected_type.__origin__ is Union:  # Handle Optional types
                    # Skip Union types (like Optional[str])
                    pass
            else:
                # Simple type checking
                if expected_type in (int, float):
                    if not isinstance(value, (int, float)):
                        errors.append(f"Parameter {group_name}.{param_name} must be a number")
                        continue
                elif expected_type is str:
                    if not isinstance(value, str):
                        errors.append(f"Parameter {group_name}.{param_name} must be a string")
                        continue

            # Range validation
            if param_name in validation_rules and isinstance(value, (int, float)):
                min_val, max_val = validation_rules[param_name]
                if not (min_val <= value <= max_val):
                    errors.append(f"Parameter {group_name}.{param_name} must be between {min_val} and {max_val}")

        return errors

    def load_parameters(self) -> AllParameters:
        """
        Load all current parameters.

        Returns:
            AllParameters object with current configuration
        """
        with self._lock:
            return self._current_params

    def save_parameters(self, params: AllParameters):
        """
        Save all parameters to current configuration.

        Args:
            params: AllParameters object to save
        """
        with self._lock:
            # Update timestamps
            params.session.last_modified = datetime.now().isoformat()
            if not params.session.created_at:
                params.session.created_at = params.session.last_modified

            # Update current parameters
            self._current_params = params

            # Save to file
            self._save_to_file()

            logger.info("Parameters saved to current configuration")

    def get_parameter_group(self, group_name: str) -> Dict[str, Any]:
        """
        Get a specific parameter group from current configuration.

        Args:
            group_name: Name of the parameter group

        Returns:
            Dictionary of parameter values
        """
        if group_name not in self.PARAMETER_TYPES:
            raise ParameterValidationError(f"Unknown parameter group: {group_name}")

        params = self.load_parameters()
        group_params = getattr(params, group_name)
        return asdict(group_params)

    def update_parameter_group(self, group_name: str, updates: Dict[str, Any]):
        """
        Update a specific parameter group in current configuration.

        Args:
            group_name: Name of the parameter group
            updates: Dictionary of parameter updates
        """
        if group_name not in self.PARAMETER_TYPES:
            raise ParameterValidationError(f"Unknown parameter group: {group_name}")

        # Validate updates
        errors = self.validate_parameter_group(group_name, updates)
        if errors:
            raise ParameterValidationError(f"Validation errors: {'; '.join(errors)}")

        with self._lock:
            group_params = getattr(self._current_params, group_name)

            # Update only provided fields
            for key, value in updates.items():
                if hasattr(group_params, key):
                    setattr(group_params, key, value)

            self.save_parameters(self._current_params)

            logger.info(f"Updated {group_name} parameters")

    def reset_to_defaults(self):
        """
        Reset current parameters to default values.
        """
        with self._lock:
            # Copy default parameters to current
            self._current_params = self._dict_to_parameters(self._parameters_to_dict(self._default_params))

            # Reset timestamps
            self._current_params.session.created_at = datetime.now().isoformat()
            self._current_params.session.last_modified = self._current_params.session.created_at

            # Save to file
            self._save_to_file()

            logger.info("Reset parameters to defaults")

    def export_parameters(self) -> str:
        """
        Export current parameters to JSON string.

        Returns:
            JSON string representation of the current parameters
        """
        data = self._parameters_to_dict(self._current_params)
        return json.dumps(data, indent=2, sort_keys=True)

    def import_parameters(self, json_data: str):
        """
        Import parameters from JSON string to current configuration.

        Args:
            json_data: JSON string containing parameter data
        """
        data = json.loads(json_data)
        self._current_params = self._dict_to_parameters(data)

        # Update timestamps
        self._current_params.session.last_modified = datetime.now().isoformat()

        self._save_to_file()
        logger.info("Imported parameters to current configuration")

    def update_camera_parameters(self, updates: Dict[str, Any]):
        """
        Update camera parameters in current configuration.

        Args:
            updates: Dictionary of camera parameter updates
        """
        self.update_parameter_group('camera', updates)

    def update_monitor_parameters(self, updates: Dict[str, Any]):
        """
        Update monitor parameters in current configuration.

        Args:
            updates: Dictionary of monitor parameter updates
        """
        self.update_parameter_group('monitor', updates)

    def get_all_parameters(self) -> Dict[str, Any]:
        """
        Get all parameters from current configuration as a dictionary.

        Returns:
            Dictionary containing all parameter groups
        """
        return self._parameters_to_dict(self._current_params)

    def get_parameter_info(self) -> Dict[str, Any]:
        """
        Get information about available parameter groups and validation rules.

        Returns:
            Dictionary containing parameter schema information
        """
        info = {
            'parameter_groups': {},
            'validation_rules': self.VALIDATION_RULES
        }

        for group_name, param_class in self.PARAMETER_TYPES.items():
            group_info = {
                'fields': {},
                'description': param_class.__doc__ or ""
            }

            for field_info in fields(param_class):
                field_type = str(field_info.type)
                default_value = field_info.default if field_info.default != field_info.default_factory else None

                group_info['fields'][field_info.name] = {
                    'type': field_type,
                    'default': default_value
                }

            info['parameter_groups'][group_name] = group_info

        return info


# Global parameter manager instance
_parameter_manager: Optional[ParameterManager] = None

def get_parameter_manager() -> ParameterManager:
    """Get or create the global parameter manager instance"""
    global _parameter_manager
    if _parameter_manager is None:
        _parameter_manager = ParameterManager()
    return _parameter_manager

def reset_parameter_manager():
    """Reset the global parameter manager (mainly for testing)"""
    global _parameter_manager
    _parameter_manager = None