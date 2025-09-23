"""
Parameter Entity - Parameter Store and Management

This module provides parameter storage, retrieval, and management
functionality for both development (defaults) and production use.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
import json
import logging
from abc import ABC, abstractmethod

from ..value_objects.parameters import (
    SpatialConfiguration,
    StimulusGenerationParams,
    AcquisitionProtocolParams,
    CombinedParameters,
    ParameterSource,
    ParameterValidationError
)
from ..services.parameter_validator import ParameterValidator

logger = logging.getLogger(__name__)


class ParameterStore(ABC):
    """Abstract base class for parameter storage implementations"""

    @abstractmethod
    def load_parameters(self, parameter_set_id: str) -> CombinedParameters:
        """Load parameters by ID"""
        pass

    @abstractmethod
    def save_parameters(self, parameters: CombinedParameters, parameter_set_id: str) -> None:
        """Save parameters with ID"""
        pass

    @abstractmethod
    def list_parameter_sets(self) -> List[str]:
        """List available parameter set IDs"""
        pass

    @abstractmethod
    def delete_parameter_set(self, parameter_set_id: str) -> None:
        """Delete a parameter set"""
        pass


class FileBasedParameterStore(ParameterStore):
    """File-based parameter storage for development and configuration management"""

    def __init__(self, storage_directory: Path):
        self.storage_directory = Path(storage_directory)
        self.storage_directory.mkdir(parents=True, exist_ok=True)
        self.validator = ParameterValidator()

    def load_parameters(self, parameter_set_id: str) -> CombinedParameters:
        """Load parameters from JSON file"""
        file_path = self.storage_directory / f"{parameter_set_id}.json"

        if not file_path.exists():
            raise ParameterValidationError(f"Parameter set '{parameter_set_id}' not found")

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Reconstruct CombinedParameters from JSON
            spatial_config = SpatialConfiguration(**data["spatial_config"])
            stimulus_params = StimulusGenerationParams(**data["stimulus_params"])
            protocol_params = AcquisitionProtocolParams(**data["protocol_params"])

            return CombinedParameters(
                spatial_config=spatial_config,
                stimulus_params=stimulus_params,
                protocol_params=protocol_params,
                parameter_source=ParameterSource(data.get("parameter_source", "user_config")),
                created_timestamp=data.get("created_timestamp"),
                modified_timestamp=data.get("modified_timestamp"),
                version=data.get("version", "1.0")
            )

        except Exception as e:
            raise ParameterValidationError(f"Failed to load parameter set '{parameter_set_id}': {e}")

    def save_parameters(self, parameters: CombinedParameters, parameter_set_id: str) -> None:
        """Save parameters to JSON file"""
        file_path = self.storage_directory / f"{parameter_set_id}.json"

        # Validate parameters before saving
        is_valid, warnings = self.validator.validate_combined_parameters(parameters)
        if not is_valid:
            raise ParameterValidationError(f"Cannot save invalid parameters: {warnings}")

        try:
            # Convert to dictionary with timestamps
            data = {
                "spatial_config": parameters.spatial_config.model_dump(),
                "stimulus_params": parameters.stimulus_params.model_dump(),
                "protocol_params": parameters.protocol_params.model_dump(),
                "parameter_source": parameters.parameter_source.value,
                "created_timestamp": parameters.created_timestamp or datetime.now().isoformat(),
                "modified_timestamp": datetime.now().isoformat(),
                "version": parameters.version,
                "metadata": {
                    "generation_hash": parameters.generation_hash,
                    "combined_hash": parameters.combined_hash,
                }
            }

            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2, sort_keys=True)

            logger.info(f"Saved parameter set '{parameter_set_id}' to {file_path}")

        except Exception as e:
            raise ParameterValidationError(f"Failed to save parameter set '{parameter_set_id}': {e}")

    def list_parameter_sets(self) -> List[str]:
        """List available parameter set IDs"""
        json_files = list(self.storage_directory.glob("*.json"))
        return [f.stem for f in json_files]

    def delete_parameter_set(self, parameter_set_id: str) -> None:
        """Delete a parameter set file"""
        file_path = self.storage_directory / f"{parameter_set_id}.json"
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted parameter set '{parameter_set_id}'")
        else:
            raise ParameterValidationError(f"Parameter set '{parameter_set_id}' not found")


class DefaultParameterFactory:
    """Factory for creating default parameter sets based on literature"""

    @staticmethod
    def create_marshel_2011_defaults() -> CombinedParameters:
        """Create default parameters based on Marshel et al. 2011

        Based on Marshel et al. Supplemental Experimental Procedures:
        - Monitor distance: 10 cm from eye (page 13)
        - Monitor angle: 20° inward toward nose (page 13)
        - Visual field: 153° vertical, 147° horizontal (page 12)
        - Bar width: 20° wide (page 13-14)
        - Bar drift speed: 8.5-9.5°/s for intrinsic imaging (page 14)
        - Counter-phase checkerboard: 25° squares with 166ms period (page 14)
        - Flicker frequency: 166ms period H 6 Hz (page 14)
        """

        # Spatial configuration from Marshel et al.
        spatial_config = SpatialConfiguration(
            monitor_distance_cm=10.0,  # 10 cm from eye
            monitor_angle_degrees=20.0,  # 20° inward toward nose
            monitor_height_degrees=0.0,  # Eye level
            monitor_roll_degrees=0.0,  # No roll
            screen_width_cm=52.0,  # Reasonable monitor size
            screen_height_cm=52.0,  # Square aspect ratio
            screen_width_pixels=2048,  # High resolution
            screen_height_pixels=2048,  # Square pixels
            field_of_view_horizontal_degrees=147.0,  # 147° horizontal
            field_of_view_vertical_degrees=153.0,  # 153° vertical
        )

        # Stimulus parameters from Marshel et al.
        stimulus_params = StimulusGenerationParams(
            bar_width_degrees=20.0,  # 20° wide
            drift_speed_degrees_per_sec=9.0,  # 8.5-9.5°/s range
            pattern_type="counter_phase_checkerboard",
            checkerboard_size_degrees=25.0,  # 25° squares
            flicker_frequency_hz=6.0,  # 166ms period H 6 Hz
            contrast=0.5,  # Full contrast (black to white)
            background_luminance=0.5,  # Mid gray
            spherical_correction=True,  # Apply spherical correction
            coordinate_system="spherical",
            bit_depth=8,
            compression_level=6,
        )

        # Standard acquisition parameters
        protocol_params = AcquisitionProtocolParams(
            num_cycles=10,  # 10 drifts in each direction
            repetitions_per_direction=1,
            frame_rate=60.0,  # Standard display rate
            inter_trial_interval_sec=2.0,
            pre_stimulus_baseline_sec=10.0,
            post_stimulus_baseline_sec=10.0,
            session_name_pattern="ISI_Mapping_Marshel_{timestamp}",
            export_formats=["hdf5", "png"],
            buffer_size_frames=120,
            error_recovery_mode="continue",
        )

        return CombinedParameters(
            spatial_config=spatial_config,
            stimulus_params=stimulus_params,
            protocol_params=protocol_params,
            parameter_source=ParameterSource.DEFAULT,
            created_timestamp=datetime.now().isoformat(),
            version="1.0"
        )

    @staticmethod
    def create_development_defaults() -> CombinedParameters:
        """Create fast defaults for development and testing"""

        # Reduced resolution and faster parameters for development
        spatial_config = SpatialConfiguration(
            monitor_distance_cm=10.0,
            monitor_angle_degrees=20.0,
            monitor_height_degrees=0.0,
            monitor_roll_degrees=0.0,
            screen_width_cm=30.0,  # Smaller for development
            screen_height_cm=30.0,
            screen_width_pixels=800,  # Lower resolution
            screen_height_pixels=600,
            field_of_view_horizontal_degrees=30.0,  # Smaller field
            field_of_view_vertical_degrees=30.0,
        )

        # Faster stimulus parameters for development
        stimulus_params = StimulusGenerationParams(
            bar_width_degrees=5.0,  # Narrower bar
            drift_speed_degrees_per_sec=15.0,  # Faster drift
            pattern_type="counter_phase_checkerboard",
            checkerboard_size_degrees=5.0,  # Smaller checkerboard
            flicker_frequency_hz=8.0,  # Faster flicker
            contrast=0.8,
            background_luminance=0.2,
            spherical_correction=True,
            coordinate_system="spherical",
            bit_depth=8,
            compression_level=3,  # Less compression
        )

        # Shorter acquisition for development
        protocol_params = AcquisitionProtocolParams(
            num_cycles=2,  # Fewer cycles
            repetitions_per_direction=1,
            frame_rate=30.0,  # Lower frame rate
            inter_trial_interval_sec=1.0,  # Shorter intervals
            pre_stimulus_baseline_sec=2.0,
            post_stimulus_baseline_sec=2.0,
            session_name_pattern="Dev_Test_{timestamp}",
            export_formats=["png"],  # PNG only for dev
            buffer_size_frames=60,
            error_recovery_mode="pause",
        )

        return CombinedParameters(
            spatial_config=spatial_config,
            stimulus_params=stimulus_params,
            protocol_params=protocol_params,
            parameter_source=ParameterSource.DEFAULT,
            created_timestamp=datetime.now().isoformat(),
            version="1.0"
        )


class ParameterManager:
    """High-level parameter management with validation and defaults"""

    def __init__(self, storage_directory: Optional[Path] = None):
        if storage_directory is None:
            # Default storage location
            storage_directory = Path.home() / ".isi_macroscope" / "parameters"

        self.parameter_store = FileBasedParameterStore(storage_directory)
        self.validator = ParameterValidator()
        self._ensure_defaults_exist()

    def _ensure_defaults_exist(self):
        """Ensure default parameter sets exist"""
        try:
            # Check if Marshel defaults exist
            if "marshel_2011_defaults" not in self.parameter_store.list_parameter_sets():
                defaults = DefaultParameterFactory.create_marshel_2011_defaults()
                self.parameter_store.save_parameters(defaults, "marshel_2011_defaults")
                logger.info("Created Marshel 2011 default parameters")

            # Check if development defaults exist
            if "development_defaults" not in self.parameter_store.list_parameter_sets():
                dev_defaults = DefaultParameterFactory.create_development_defaults()
                self.parameter_store.save_parameters(dev_defaults, "development_defaults")
                logger.info("Created development default parameters")

        except Exception as e:
            logger.warning(f"Could not create default parameters: {e}")

    def get_parameters(self, parameter_set_id: str) -> CombinedParameters:
        """Get parameters by ID with validation"""
        parameters = self.parameter_store.load_parameters(parameter_set_id)

        # Validate parameters
        is_valid, warnings = self.validator.validate_combined_parameters(parameters)
        if warnings:
            logger.warning(f"Parameter warnings for '{parameter_set_id}': {warnings}")

        return parameters

    def get_marshel_defaults(self) -> CombinedParameters:
        """Get Marshel et al. 2011 default parameters"""
        return self.get_parameters("marshel_2011_defaults")

    def get_development_defaults(self) -> CombinedParameters:
        """Get development default parameters"""
        return self.get_parameters("development_defaults")

    def save_parameters(self, parameters: CombinedParameters, parameter_set_id: str) -> None:
        """Save parameters with validation"""
        self.parameter_store.save_parameters(parameters, parameter_set_id)

    def list_available_parameters(self) -> List[str]:
        """List all available parameter sets"""
        return self.parameter_store.list_parameter_sets()

    def validate_parameters(self, parameters: CombinedParameters) -> Dict[str, Any]:
        """Comprehensive parameter validation and compliance check"""
        is_valid, warnings = self.validator.validate_combined_parameters(parameters)
        compliance = self.validator.check_literature_compliance(parameters)

        return {
            "is_valid": is_valid,
            "warnings": warnings,
            "literature_compliance": compliance,
            "generation_hash": parameters.generation_hash,
            "combined_hash": parameters.combined_hash,
        }