"""
Parameter Entity - Parameter Store and Management

This module provides parameter storage, retrieval, and management
functionality for both development (defaults) and production use.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
import json
from abc import ABC, abstractmethod

from domain.value_objects.parameters import (
    SpatialConfiguration,
    StimulusGenerationParams,
    AcquisitionProtocolParams,
    CombinedParameters,
    ParameterSource,
    DirectionSequence,
    BaselineMode,
)
from domain.services.parameter_validator import ParameterValidator
from domain.services.error_handler import ErrorHandlingService, ISIDomainError


class ParameterStore(ABC):
    """Abstract base class for parameter storage implementations"""

    @abstractmethod
    def load_parameters(self, parameter_set_id: str):
        """Load parameters by ID"""

    @abstractmethod
    def save_parameters(self, parameters: "CombinedParameters", parameter_set_id: str):
        """Save parameters with ID"""

    @abstractmethod
    def list_parameter_sets(self) -> List[str]:
        """List available parameter set IDs"""

    @abstractmethod
    def delete_parameter_set(self, parameter_set_id: str) -> None:
        """Delete a parameter set"""


class FileBasedParameterStore(ParameterStore):
    """File-based parameter storage for development and configuration management"""

    def __init__(
        self, storage_directory: Path, error_handler: Optional[ErrorHandlingService] = None
    ):
        self.storage_directory = Path(storage_directory)
        self.storage_directory.mkdir(parents=True, exist_ok=True)
        self.error_handler = error_handler or ErrorHandlingService()
        self.validator = ParameterValidator(self.error_handler)

    def load_parameters(self, parameter_set_id: str) -> CombinedParameters:
        """Load parameters from JSON file"""
        file_path = self.storage_directory / f"{parameter_set_id}.json"

        if not file_path.exists():
            domain_error = self.error_handler.create_error(
                error_code="PARAMETER_VALIDATION_ERROR",
                custom_message=f"Parameter set '{parameter_set_id}' not found",
                parameter_set_id=parameter_set_id,
                file_path=str(file_path),
            )
            raise ISIDomainError(domain_error)

        try:
            with open(file_path, "r") as f:
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
                version=data.get("version", "1.0"),
            )

        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="PARAMETER_VALIDATION_ERROR",
                custom_message=f"Failed to load parameter set '{parameter_set_id}'",
                parameter_set_id=parameter_set_id,
                operation="load",
            )
            raise ISIDomainError(domain_error)

    def save_parameters(self, parameters: CombinedParameters, parameter_set_id: str) -> None:
        """Save parameters to JSON file"""
        file_path = self.storage_directory / f"{parameter_set_id}.json"

        # Validate parameters before saving
        is_valid, warnings = self.validator.validate_combined_parameters(parameters)
        if not is_valid:
            domain_error = self.error_handler.create_error(
                error_code="PARAMETER_VALIDATION_ERROR",
                custom_message="Cannot save invalid parameters",
                parameter_set_id=parameter_set_id,
                validation_warnings=warnings,
            )
            raise ISIDomainError(domain_error)

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
                },
            }

            with open(file_path, "w") as f:
                json.dump(data, f, indent=2, sort_keys=True)

        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="PARAMETER_VALIDATION_ERROR",
                custom_message=f"Failed to save parameter set '{parameter_set_id}'",
                parameter_set_id=parameter_set_id,
                operation="save",
            )
            raise ISIDomainError(domain_error)

    def list_parameter_sets(self) -> List[str]:
        """List available parameter set IDs"""
        json_files = list(self.storage_directory.glob("*.json"))
        return [f.stem for f in json_files]

    def delete_parameter_set(self, parameter_set_id: str) -> None:
        """Delete a parameter set file"""
        file_path = self.storage_directory / f"{parameter_set_id}.json"
        if file_path.exists():
            file_path.unlink()
        else:
            domain_error = self.error_handler.create_error(
                error_code="PARAMETER_VALIDATION_ERROR",
                custom_message=f"Parameter set '{parameter_set_id}' not found",
                parameter_set_id=parameter_set_id,
                operation="delete",
            )
            raise ISIDomainError(domain_error)


class DefaultParameterFactory:
    """Factory for creating default parameter sets based on literature"""

    @staticmethod
    def create_marshel_2011_defaults() -> CombinedParameters:
        """Create default parameters based on Marshel et al. 2011

        Based on Marshel et al. Supplemental Experimental Procedures:
        - Monitor distance: 10 cm from eye (page 13)
        - Monitor angle: 20 degrees inward toward nose (page 13)
        - Visual field: 153 degrees vertical, 147 degrees horizontal (page 12)
        - Bar width: 20 degrees wide (page 13-14)
        - Bar drift speed: 8.5-9.5 degrees/s for intrinsic imaging (page 14)
        - Counter-phase checkerboard: 25 degrees squares with 166ms period (page 14)
        - Flicker frequency: 166ms period approximately 6 Hz (page 14)
        """

        # Spatial configuration from Marshel et al.
        spatial_config = SpatialConfiguration(
            monitor_distance_cm=10.0,  # 10 cm from eye
            monitor_angle_degrees=20.0,  # 20 degrees inward toward nose
            monitor_height_degrees=0.0,  # Eye level
            monitor_roll_degrees=0.0,  # No roll
            screen_width_cm=52.0,  # Reasonable monitor size
            screen_height_cm=52.0,  # Square aspect ratio
            screen_width_pixels=2048,  # High resolution
            screen_height_pixels=2048,  # Square pixels
            field_of_view_horizontal_degrees=147.0,  # 147 degrees horizontal
            field_of_view_vertical_degrees=153.0,  # 153 degrees vertical
        )

        # Stimulus parameters from Marshel et al.
        stimulus_params = StimulusGenerationParams(
            bar_width_degrees=20.0,  # 20 degrees wide
            drift_speed_degrees_per_sec=9.0,  # 8.5-9.5 degrees/s range
            pattern_type="counter_phase_checkerboard",
            checkerboard_size_degrees=25.0,  # 25 degrees squares
            flicker_frequency_hz=6.0,  # 166ms period approximately 6 Hz
            contrast=0.5,  # Full contrast (black to white)
            background_luminance=0.5,  # Mid gray
            spherical_correction=True,  # Apply spherical correction
            coordinate_system="spherical",
            bit_depth=8,
            compression_level=6,
        )

        # Standard acquisition parameters based on Marshel et al.
        protocol_params = AcquisitionProtocolParams(
            num_cycles=10,  # 10 drifts in each direction per Marshel et al.
            total_protocol_repetitions=1,
            direction_sequence=DirectionSequence.SEQUENTIAL,
            include_reverse_directions=True,
            baseline_mode=BaselineMode.PRE_POST_SESSION,
            baseline_duration_sec=10.0,
            frame_rate=60.0,  # Standard display rate
            inter_direction_interval_sec=5.0,
            inter_cycle_interval_sec=2.0,
            inter_protocol_interval_sec=30.0,
            # Legacy parameters for compatibility
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
            version="1.0",
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
            num_cycles=2,  # Fewer cycles for faster testing
            total_protocol_repetitions=1,
            direction_sequence=DirectionSequence.SEQUENTIAL,
            include_reverse_directions=False,  # Only LR and TB for speed
            baseline_mode=BaselineMode.PRE_SESSION,
            baseline_duration_sec=2.0,  # Shorter baseline
            frame_rate=30.0,  # Lower frame rate
            inter_direction_interval_sec=1.0,
            inter_cycle_interval_sec=0.5,
            inter_protocol_interval_sec=5.0,
            # Legacy parameters for compatibility
            inter_trial_interval_sec=1.0,
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
            version="1.0",
        )


class ParameterManager:
    """High-level parameter management with validation and defaults"""

    def __init__(
        self,
        storage_directory: Optional[Path] = None,
        error_handler: Optional[ErrorHandlingService] = None,
    ):
        if storage_directory is None:
            # Default storage location
            storage_directory = Path.home() / ".isi_macroscope" / "parameters"

        self.error_handler = error_handler or ErrorHandlingService()
        self.parameter_store = FileBasedParameterStore(storage_directory, self.error_handler)
        self.validator = ParameterValidator(self.error_handler)
        self._ensure_defaults_exist()

    def _ensure_defaults_exist(self):
        """Ensure default parameter sets exist"""
        try:
            # Check if Marshel defaults exist
            if "marshel_2011_defaults" not in self.parameter_store.list_parameter_sets():
                defaults = DefaultParameterFactory.create_marshel_2011_defaults()
                self.parameter_store.save_parameters(defaults, "marshel_2011_defaults")

            # Check if development defaults exist
            if "development_defaults" not in self.parameter_store.list_parameter_sets():
                dev_defaults = DefaultParameterFactory.create_development_defaults()
                self.parameter_store.save_parameters(dev_defaults, "development_defaults")

        except Exception as e:
            # Create domain error but don't fail initialization
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="PARAMETER_VALIDATION_ERROR",
                custom_message="Could not create default parameters",
                operation="ensure_defaults_exist",
            )

    def get_parameters(self, parameter_set_id: str) -> CombinedParameters:
        """Get parameters by ID with validation"""
        parameters = self.parameter_store.load_parameters(parameter_set_id)

        # Validate parameters
        is_valid, warnings = self.validator.validate_combined_parameters(parameters)
        if warnings:
            # Create domain error for warnings but don't fail
            domain_error = self.error_handler.create_error(
                error_code="PARAMETER_VALIDATION_ERROR",
                custom_message=f"Parameter warnings for '{parameter_set_id}': {warnings}",
                parameter_set_id=parameter_set_id,
                warnings=warnings,
            )

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
