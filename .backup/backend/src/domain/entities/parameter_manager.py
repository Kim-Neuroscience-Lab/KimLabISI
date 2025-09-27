"""
Parameter Manager Entity - Pure Domain Logic

Manages parameter creation, validation, and business rules without any infrastructure dependencies.
Implements business logic for parameter management, defaults, and validation orchestration.
"""

from datetime import datetime
from typing import Dict, Any, Protocol

from domain.value_objects.parameters import (
    CombinedParameters,
    SpatialConfiguration,
    StimulusGenerationParams,
    AcquisitionProtocolParams,
    ParameterSource,
    DirectionSequence,
    BaselineMode,
)
from domain.services.parameter_validator import ParameterValidator
from domain.services.error_handler import ErrorHandlingService, ISIDomainError


class ParameterRepositoryInterface(Protocol):
    """Protocol for parameter repository dependency inversion"""

    def load_parameters(self, parameter_set_id: str) -> CombinedParameters:
        """Load parameters by ID"""

    def save_parameters(self, parameters: CombinedParameters, parameter_set_id: str) -> None:
        """Save parameters with ID"""

    def parameter_set_exists(self, parameter_set_id: str) -> bool:
        """Check if parameter set exists"""


class DefaultParameterFactory:
    """Factory for creating default parameter sets based on literature"""

    @staticmethod
    def create_marshel_2011_defaults() -> CombinedParameters:
        """Create parameter defaults based on Marshel et al. 2011"""

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

        # Minimal acquisition parameters for development
        protocol_params = AcquisitionProtocolParams(
            num_cycles=2,  # Only 2 cycles for development
            total_protocol_repetitions=1,
            direction_sequence=DirectionSequence.SEQUENTIAL,
            include_reverse_directions=False,  # Skip reverse for speed
            baseline_mode=BaselineMode.PRE_SESSION,
            baseline_duration_sec=2.0,  # Shorter baseline
            frame_rate=30.0,  # Lower frame rate
            inter_direction_interval_sec=1.0,
            inter_cycle_interval_sec=0.5,
            inter_protocol_interval_sec=5.0,
            # Legacy parameters
            inter_trial_interval_sec=0.5,
            pre_stimulus_baseline_sec=2.0,
            post_stimulus_baseline_sec=2.0,
            session_name_pattern="DEV_Session_{timestamp}",
            export_formats=["png"],  # Only PNG for development
            buffer_size_frames=60,
            error_recovery_mode="abort",
        )

        return CombinedParameters(
            spatial_config=spatial_config,
            stimulus_params=stimulus_params,
            protocol_params=protocol_params,
            parameter_source=ParameterSource.DEFAULT,
            created_timestamp=datetime.now().isoformat(),
            version="1.0-dev",
        )


class ParameterManager:
    """
    Domain entity for parameter management business logic

    Orchestrates parameter creation, validation, and business rules without
    any infrastructure dependencies. Uses dependency inversion for persistence.
    """

    def __init__(
        self,
        parameter_repository: ParameterRepositoryInterface,
        parameter_validator: ParameterValidator,
        error_handler: ErrorHandlingService,
    ):
        self.parameter_repository = parameter_repository
        self.parameter_validator = parameter_validator
        self.error_handler = error_handler

    def get_default_parameters(self, development_mode: bool = False) -> CombinedParameters:
        """Get appropriate default parameters based on mode"""
        try:
            if development_mode:
                return DefaultParameterFactory.create_development_defaults()
            else:
                return DefaultParameterFactory.create_marshel_2011_defaults()
        except Exception as e:
            self.error_handler.handle_error(
                "parameter_creation", f"Failed to create default parameters: {str(e)}"
            )
            raise ISIDomainError("Failed to create default parameters: %s", str(e))

    def load_parameters(self, parameter_set_id: str) -> CombinedParameters:
        """Load parameters by ID with business logic validation"""
        try:
            parameters = self.parameter_repository.load_parameters(parameter_set_id)

            # Business rule: Always validate loaded parameters
            validation_result = self.validate_parameters(parameters)
            if not validation_result["is_valid"]:
                self.error_handler.handle_error(
                    "parameter_validation",
                    f"Loaded parameters failed validation: {validation_result['errors']}",
                )

            return parameters

        except Exception as e:
            self.error_handler.handle_error(
                "parameter_loading", f"Failed to load parameters: {str(e)}"
            )
            raise ISIDomainError("Failed to load parameter set '%s': %s", parameter_set_id, str(e))

    def save_parameters(
        self,
        parameters: CombinedParameters,
        parameter_set_id: str,
        validate_before_save: bool = True,
    ) -> None:
        """Save parameters with optional validation"""
        try:
            # Business rule: Validate parameters before saving (if requested)
            if validate_before_save:
                validation_result = self.validate_parameters(parameters)
                if not validation_result["is_valid"]:
                    raise ISIDomainError(
                        f"Parameters failed validation: {validation_result['errors']}"
                    )

            # Business rule: Update metadata before saving
            updated_parameters = parameters.model_copy(
                update={
                    "parameter_source": ParameterSource.PARAMETER_STORE,
                    "created_timestamp": datetime.now().isoformat(),
                }
            )

            self.parameter_repository.save_parameters(updated_parameters, parameter_set_id)

        except Exception as e:
            self.error_handler.handle_error(
                "parameter_saving", f"Failed to save parameters: {str(e)}"
            )
            raise ISIDomainError("Failed to save parameter set '%s': %s", parameter_set_id, str(e))

    def validate_parameters(self, parameters: CombinedParameters) -> Dict[str, Any]:
        """Validate parameters using domain validation rules"""
        try:
            return self.parameter_validator.validate_combined_parameters(parameters)
        except Exception as e:
            self.error_handler.handle_error("parameter_validation", f"Validation failed: {str(e)}")
            return {
                "is_valid": False,
                "errors": [f"Validation system error: {str(e)}"],
                "warnings": [],
            }

    def parameter_set_exists(self, parameter_set_id: str) -> bool:
        """Check if parameter set exists"""
        try:
            return self.parameter_repository.parameter_set_exists(parameter_set_id)
        except Exception as e:
            self.error_handler.handle_error(
                "parameter_existence_check", f"Failed to check parameter existence: {str(e)}"
            )
            return False

    def merge_parameters(
        self,
        base_parameters: CombinedParameters,
        override_parameters: Dict[str, Any],
    ) -> CombinedParameters:
        """Merge parameter overrides with base parameters (business logic)"""
        try:
            # Business rule: Create updated parameters while preserving structure
            merged_data = base_parameters.model_dump()

            # Apply overrides at appropriate levels
            for key, value in override_parameters.items():
                if key in merged_data:
                    merged_data[key] = value
                elif "." in key:
                    # Support nested keys like "stimulus_params.velocity_degrees_per_sec"
                    parts = key.split(".")
                    current = merged_data
                    for part in parts[:-1]:
                        if part in current:
                            current = current[part]
                        else:
                            break
                    else:
                        current[parts[-1]] = value

            # Business rule: Update metadata for merged parameters
            merged_data["parameter_source"] = ParameterSource.USER_CONFIG
            merged_data["created_timestamp"] = datetime.now().isoformat()

            return CombinedParameters.model_validate(merged_data)

        except Exception as e:
            self.error_handler.handle_error(
                "parameter_merging", f"Failed to merge parameters: {str(e)}"
            )
            raise ISIDomainError("Failed to merge parameters: %s", str(e))
