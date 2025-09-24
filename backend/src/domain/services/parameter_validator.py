"""
Parameter Validation Service

Validates parameter combinations, checks scientific constraints,
and ensures parameter compatibility with existing datasets.
"""

from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from cerberus import Validator
from schema import Schema, SchemaError, Optional as SchemaOptional
import marshmallow as ma
from marshmallow import fields, validate

from .error_handler import ErrorHandlingService, ISIDomainError


class ParameterValidator:
    """Validates parameter combinations and scientific constraints"""

    def __init__(self, error_handler: Optional[ErrorHandlingService] = None):
        self.error_handler = error_handler or ErrorHandlingService()
        self.validation_rules = self._load_validation_rules()

        # Setup Cerberus validator for structured parameter validation
        self.cerberus_validator = Validator()

        # Setup schema for spatial constraints
        self.spatial_schema = Schema({
            'monitor_distance_cm': fields.Float(validate=validate.Range(min=5.0, max=20.0)),
            'monitor_angle_degrees': fields.Float(validate=validate.Range(min=0.0, max=45.0)),
            'field_of_view_horizontal_degrees': fields.Float(validate=validate.Range(min=0.0, max=180.0)),
            'field_of_view_vertical_degrees': fields.Float(validate=validate.Range(min=0.0, max=180.0))
        })

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
                "recommended_drift_speed": 9.0,  # Marshel et al. 8.5-9.5 deg/s
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

    def validate_combined_parameters(self, parameters) -> Tuple[bool, List[str]]:
        """Validate complete parameter set using structured validation

        Returns:
            Tuple of (is_valid, warnings_list)
        """
        all_warnings = []
        is_valid = True

        try:
            # Validate spatial configuration using Marshmallow schema
            if hasattr(parameters, 'spatial_config'):
                spatial_data = {
                    'monitor_distance_cm': parameters.spatial_config.monitor_distance_cm,
                    'monitor_angle_degrees': parameters.spatial_config.monitor_angle_degrees,
                    'field_of_view_horizontal_degrees': parameters.spatial_config.field_of_view_horizontal_degrees,
                    'field_of_view_vertical_degrees': parameters.spatial_config.field_of_view_vertical_degrees
                }

                # Validate using the schema
                try:
                    self.spatial_schema.load(spatial_data)
                except ma.ValidationError as e:
                    is_valid = False
                    all_warnings.extend([f"Spatial validation error: {error}" for error in e.messages.values()])

        except Exception as e:
            is_valid = False
            all_warnings.append(f"Validation error: {str(e)}")

        return is_valid, all_warnings

    def check_literature_compliance(self, parameters) -> Dict[str, str]:
        """Check compliance with Marshel et al. 2011 reference values

        Returns:
            Dictionary of parameter compliance status
        """
        compliance = {}

        # Monitor distance compliance
        if hasattr(parameters, 'spatial_config'):
            distance = parameters.spatial_config.monitor_distance_cm
            if abs(distance - 10.0) < 0.5:
                compliance["monitor_distance"] = "matches Marshel et al. (10cm)"
            else:
                compliance["monitor_distance"] = f"differs from Marshel et al. (10cm vs {distance}cm)"

        # Bar width compliance
        if hasattr(parameters, 'stimulus_params'):
            bar_width = parameters.stimulus_params.bar_width_degrees
            if abs(bar_width - 20.0) < 1.0:
                compliance["bar_width"] = "matches Marshel et al. (20 degrees)"
            else:
                compliance["bar_width"] = f"differs from Marshel et al. (20 vs {bar_width} degrees)"

        return compliance


class ParameterCompatibilityChecker:
    """Checks parameter compatibility with existing datasets"""

    def __init__(self, dataset_directory: Optional[Path] = None, error_handler: Optional[ErrorHandlingService] = None):
        self.dataset_directory = dataset_directory
        self.error_handler = error_handler or ErrorHandlingService()

    def check_dataset_compatibility(self, params, dataset_path: Path) -> bool:
        """Check if parameters are compatible with existing dataset"""
        try:
            # For now, return False to force regeneration
            return False
        except Exception as e:
            # Create domain error instead of logging
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="PARAMETER_COMPATIBILITY_ERROR",
                custom_message=f"Could not check dataset compatibility with {dataset_path}",
                dataset_path=str(dataset_path),
                function="check_dataset_compatibility"
            )
            # For compatibility checking, we return False instead of raising
            return False

    def find_compatible_datasets(self, params) -> List[Path]:
        """Find existing datasets compatible with current parameters"""
        compatible_datasets = []
        return compatible_datasets