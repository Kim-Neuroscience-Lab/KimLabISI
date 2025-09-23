"""
Parameter Validation Service

Validates parameter combinations, checks scientific constraints,
and ensures parameter compatibility with existing datasets.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
from pathlib import Path

from ..value_objects.parameters import (
    SpatialConfiguration,
    StimulusGenerationParams,
    AcquisitionProtocolParams,
    CombinedParameters,
    ParameterValidationError,
    ParameterCompatibilityError
)

logger = logging.getLogger(__name__)


class ParameterValidator:
    """Validates parameter combinations and scientific constraints"""

    def __init__(self):
        self.validation_rules = self._load_validation_rules()

    def _load_validation_rules(self) -> Dict[str, Any]:
        """Load scientific validation rules and constraints"""
        return {
            "spatial_constraints": {
                "min_monitor_distance_cm": 5.0,
                "max_monitor_distance_cm": 20.0,
                "max_field_of_view_degrees": 180.0,
                "recommended_distance_cm": 10.0,  # Marshel et al.
                "recommended_angle_degrees": 20.0,  # Marshel et al.
            },
            "stimulus_constraints": {
                "min_bar_width_degrees": 1.0,
                "max_bar_width_degrees": 45.0,
                "recommended_bar_width_degrees": 20.0,  # Marshel et al.
                "min_drift_speed": 1.0,
                "max_drift_speed": 50.0,
                "recommended_drift_speed": 9.0,  # Marshel et al. 8.5-9.5°/s
                "min_checkerboard_size": 5.0,
                "max_checkerboard_size": 50.0,
                "recommended_checkerboard_size": 25.0,  # Marshel et al.
                "recommended_flicker_hz": 6.0,  # Marshel et al. 166ms period
            },
            "timing_constraints": {
                "max_cycle_duration_sec": 300.0,  # 5 minutes
                "min_frame_rate": 30.0,
                "max_frame_rate": 120.0,
                "recommended_frame_rate": 60.0,
            }
        }

    def validate_spatial_configuration(self, config: SpatialConfiguration) -> List[str]:
        """Validate spatial configuration parameters

        Returns:
            List of validation warnings (empty if valid)
        """
        warnings = []
        rules = self.validation_rules["spatial_constraints"]

        # Check monitor distance
        if config.monitor_distance_cm < rules["min_monitor_distance_cm"]:
            warnings.append(f"Monitor distance {config.monitor_distance_cm}cm is too close (min: {rules['min_monitor_distance_cm']}cm)")
        elif config.monitor_distance_cm > rules["max_monitor_distance_cm"]:
            warnings.append(f"Monitor distance {config.monitor_distance_cm}cm is too far (max: {rules['max_monitor_distance_cm']}cm)")

        # Check field of view coverage
        if config.field_of_view_horizontal_degrees > rules["max_field_of_view_degrees"]:
            warnings.append(f"Horizontal field of view {config.field_of_view_horizontal_degrees}° exceeds maximum")
        if config.field_of_view_vertical_degrees > rules["max_field_of_view_degrees"]:
            warnings.append(f"Vertical field of view {config.field_of_view_vertical_degrees}° exceeds maximum")

        # Check for reasonable pixel density
        pixels_per_degree = config.pixels_per_degree
        if pixels_per_degree < 5.0:
            warnings.append(f"Low pixel density ({pixels_per_degree:.1f} pixels/degree) may affect stimulus quality")
        elif pixels_per_degree > 100.0:
            warnings.append(f"Very high pixel density ({pixels_per_degree:.1f} pixels/degree) may be unnecessary")

        return warnings

    def validate_stimulus_parameters(self, params: StimulusGenerationParams) -> List[str]:
        """Validate stimulus generation parameters

        Returns:
            List of validation warnings (empty if valid)
        """
        warnings = []
        rules = self.validation_rules["stimulus_constraints"]

        # Check bar width
        if params.bar_width_degrees < rules["min_bar_width_degrees"]:
            warnings.append(f"Bar width {params.bar_width_degrees}° is very narrow (recommended: {rules['recommended_bar_width_degrees']}°)")
        elif params.bar_width_degrees > rules["max_bar_width_degrees"]:
            warnings.append(f"Bar width {params.bar_width_degrees}° is very wide (max: {rules['max_bar_width_degrees']}°)")

        # Check drift speed
        if params.drift_speed_degrees_per_sec < rules["min_drift_speed"]:
            warnings.append(f"Drift speed {params.drift_speed_degrees_per_sec}°/s is very slow")
        elif params.drift_speed_degrees_per_sec > rules["max_drift_speed"]:
            warnings.append(f"Drift speed {params.drift_speed_degrees_per_sec}°/s is very fast")

        # Check checkerboard size
        if params.checkerboard_size_degrees < rules["min_checkerboard_size"]:
            warnings.append(f"Checkerboard size {params.checkerboard_size_degrees}° is very small")
        elif params.checkerboard_size_degrees > rules["max_checkerboard_size"]:
            warnings.append(f"Checkerboard size {params.checkerboard_size_degrees}° is very large")

        # Check flicker frequency
        if params.flicker_frequency_hz < 1.0:
            warnings.append(f"Flicker frequency {params.flicker_frequency_hz}Hz is very low")
        elif params.flicker_frequency_hz > 30.0:
            warnings.append(f"Flicker frequency {params.flicker_frequency_hz}Hz is very high")

        return warnings

    def validate_acquisition_parameters(self, params: AcquisitionProtocolParams) -> List[str]:
        """Validate acquisition protocol parameters

        Returns:
            List of validation warnings (empty if valid)
        """
        warnings = []
        rules = self.validation_rules["timing_constraints"]

        # Check frame rate
        if params.frame_rate < rules["min_frame_rate"]:
            warnings.append(f"Frame rate {params.frame_rate}Hz is low (recommended: {rules['recommended_frame_rate']}Hz)")
        elif params.frame_rate > rules["max_frame_rate"]:
            warnings.append(f"Frame rate {params.frame_rate}Hz is very high")

        # Check for reasonable total experiment duration
        total_duration = (params.num_cycles * params.repetitions_per_direction *
                         (params.pre_stimulus_baseline_sec + params.post_stimulus_baseline_sec +
                          params.inter_trial_interval_sec))

        if total_duration > 3600:  # 1 hour
            warnings.append(f"Total experiment duration ({total_duration/60:.1f} minutes) is very long")

        return warnings

    def validate_combined_parameters(self, params: CombinedParameters) -> Tuple[bool, List[str]]:
        """Validate complete parameter set and check for interactions

        Returns:
            Tuple of (is_valid, warnings_list)
        """
        all_warnings = []

        # Validate individual parameter sets
        all_warnings.extend(self.validate_spatial_configuration(params.spatial_config))
        all_warnings.extend(self.validate_stimulus_parameters(params.stimulus_params))
        all_warnings.extend(self.validate_acquisition_parameters(params.protocol_params))

        # Check parameter interactions
        interaction_warnings = self._validate_parameter_interactions(params)
        all_warnings.extend(interaction_warnings)

        # Parameters are valid if no critical errors (only warnings allowed)
        is_valid = not any("error" in warning.lower() for warning in all_warnings)

        return is_valid, all_warnings

    def _validate_parameter_interactions(self, params: CombinedParameters) -> List[str]:
        """Check for problematic parameter interactions"""
        warnings = []

        # Check if bar width is appropriate for field of view
        horizontal_fov = params.spatial_config.field_of_view_horizontal_degrees
        vertical_fov = params.spatial_config.field_of_view_vertical_degrees
        bar_width = params.stimulus_params.bar_width_degrees

        if bar_width > horizontal_fov * 0.5:
            warnings.append(f"Bar width ({bar_width}°) is large relative to horizontal field of view ({horizontal_fov}°)")
        if bar_width > vertical_fov * 0.5:
            warnings.append(f"Bar width ({bar_width}°) is large relative to vertical field of view ({vertical_fov}°)")

        # Check if drift speed creates reasonable cycle duration
        drift_speed = params.stimulus_params.drift_speed_degrees_per_sec
        cycle_duration_h = horizontal_fov / drift_speed
        cycle_duration_v = vertical_fov / drift_speed

        if cycle_duration_h > 60:  # 1 minute
            warnings.append(f"Horizontal cycle duration ({cycle_duration_h:.1f}s) is very long due to slow drift speed")
        if cycle_duration_v > 60:
            warnings.append(f"Vertical cycle duration ({cycle_duration_v:.1f}s) is very long due to slow drift speed")

        # Check if checkerboard size is reasonable for monitor resolution
        pixels_per_degree = params.spatial_config.pixels_per_degree
        checkerboard_pixels = params.stimulus_params.checkerboard_size_degrees * pixels_per_degree

        if checkerboard_pixels < 10:
            warnings.append(f"Checkerboard squares will be very small ({checkerboard_pixels:.1f} pixels)")
        elif checkerboard_pixels > 200:
            warnings.append(f"Checkerboard squares will be very large ({checkerboard_pixels:.1f} pixels)")

        return warnings

    def check_literature_compliance(self, params: CombinedParameters) -> Dict[str, str]:
        """Check compliance with Marshel et al. 2011 reference values

        Returns:
            Dictionary of parameter compliance status
        """
        compliance = {}

        # Spatial configuration compliance
        if abs(params.spatial_config.monitor_distance_cm - 10.0) < 0.5:
            compliance["monitor_distance"] = "matches Marshel et al. (10cm)"
        else:
            compliance["monitor_distance"] = f"differs from Marshel et al. (10cm vs {params.spatial_config.monitor_distance_cm}cm)"

        if abs(params.spatial_config.monitor_angle_degrees - 20.0) < 1.0:
            compliance["monitor_angle"] = "matches Marshel et al. (20°)"
        else:
            compliance["monitor_angle"] = f"differs from Marshel et al. (20° vs {params.spatial_config.monitor_angle_degrees}°)"

        # Stimulus parameter compliance
        if abs(params.stimulus_params.bar_width_degrees - 20.0) < 1.0:
            compliance["bar_width"] = "matches Marshel et al. (20°)"
        else:
            compliance["bar_width"] = f"differs from Marshel et al. (20° vs {params.stimulus_params.bar_width_degrees}°)"

        if 8.5 <= params.stimulus_params.drift_speed_degrees_per_sec <= 9.5:
            compliance["drift_speed"] = "within Marshel et al. range (8.5-9.5°/s)"
        else:
            compliance["drift_speed"] = f"outside Marshel et al. range (8.5-9.5°/s vs {params.stimulus_params.drift_speed_degrees_per_sec}°/s)"

        if abs(params.stimulus_params.checkerboard_size_degrees - 25.0) < 1.0:
            compliance["checkerboard_size"] = "matches Marshel et al. (25°)"
        else:
            compliance["checkerboard_size"] = f"differs from Marshel et al. (25° vs {params.stimulus_params.checkerboard_size_degrees}°)"

        if abs(params.stimulus_params.flicker_frequency_hz - 6.0) < 0.5:
            compliance["flicker_frequency"] = "matches Marshel et al. (~6Hz)"
        else:
            compliance["flicker_frequency"] = f"differs from Marshel et al. (~6Hz vs {params.stimulus_params.flicker_frequency_hz}Hz)"

        return compliance


class ParameterCompatibilityChecker:
    """Checks parameter compatibility with existing datasets"""

    def __init__(self, dataset_directory: Optional[Path] = None):
        self.dataset_directory = dataset_directory

    def check_dataset_compatibility(self, params: CombinedParameters, dataset_path: Path) -> bool:
        """Check if parameters are compatible with existing dataset

        Args:
            params: Current parameter set
            dataset_path: Path to existing HDF5 dataset

        Returns:
            True if parameters are compatible for dataset reuse
        """
        try:
            # This would read HDF5 metadata and compare generation hashes
            # For now, return False to force regeneration
            logger.info(f"Checking compatibility with dataset: {dataset_path}")

            # TODO: Implement HDF5 metadata reading and hash comparison
            # existing_hash = read_dataset_generation_hash(dataset_path)
            # current_hash = params.generation_hash
            # return existing_hash == current_hash

            return False

        except Exception as e:
            logger.warning(f"Could not check dataset compatibility: {e}")
            return False

    def find_compatible_datasets(self, params: CombinedParameters) -> List[Path]:
        """Find existing datasets compatible with current parameters

        Returns:
            List of paths to compatible datasets
        """
        compatible_datasets = []

        if not self.dataset_directory or not self.dataset_directory.exists():
            return compatible_datasets

        # TODO: Implement dataset scanning and compatibility checking
        # This would scan all HDF5 files and check generation hashes

        return compatible_datasets