"""
Parameter Store - Infrastructure Implementation

File-based parameter storage implementation extracted from domain layer.
Handles all I/O operations while implementing the domain ParameterStore interface.
"""

import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from domain.value_objects.parameters import (
    CombinedParameters,
    SpatialConfiguration,
    StimulusGenerationParams,
    AcquisitionProtocolParams,
    ParameterSource,
)
from domain.services.error_handler import ErrorHandlingService, ISIDomainError
from domain.services.parameter_validator import ParameterValidator
from domain.entities.parameters import ParameterStore


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
            with open(file_path, "r", encoding="utf-8") as f:
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

            with open(file_path, "w", encoding="utf-8") as f:
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
        return [f.stem for f in json_files if f.is_file()]

    def delete_parameter_set(self, parameter_set_id: str) -> None:
        """Delete a parameter set"""
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
            file_path.unlink()
        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="PARAMETER_VALIDATION_ERROR",
                custom_message=f"Failed to delete parameter set '{parameter_set_id}'",
                parameter_set_id=parameter_set_id,
                operation="delete",
            )
            raise ISIDomainError(domain_error)