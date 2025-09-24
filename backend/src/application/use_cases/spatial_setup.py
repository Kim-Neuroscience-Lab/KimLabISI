"""
Spatial Setup Use Case - 3D Spatial Configuration Workflow

This use case handles the interactive 3D spatial configuration process
where users define the relationship between mouse and monitor for
accurate retinotopic mapping stimulus presentation.
"""

import asyncio
import logging
import math
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from ...domain.entities.workflow_state_machine import WorkflowStateMachine
from ...domain.value_objects.workflow_state import (
    WorkflowState, WorkflowTransition, HardwareRequirement
)
from ...domain.entities.parameters import ParameterManager
from ...domain.value_objects.parameters import (
    SpatialConfiguration, CombinedParameters, ParameterSource
)
from ...infrastructure.hardware.factory import HardwareFactory

logger = logging.getLogger(__name__)


class SpatialSetupUseCase:
    """Orchestrates the 3D spatial configuration workflow"""

    def __init__(
        self,
        workflow: WorkflowStateMachine,
        parameter_manager: ParameterManager,
        hardware_factory: HardwareFactory
    ):
        self.workflow = workflow
        self.parameter_manager = parameter_manager
        self.hardware_factory = hardware_factory

        # Setup state
        self.current_config: Optional[SpatialConfiguration] = None
        self.validation_errors: List[str] = []
        self.setup_complete = False

    async def start_spatial_setup(self, base_parameters: Optional[str] = None) -> 'SpatialSetupResult':
        """
        Begin spatial setup workflow

        Args:
            base_parameters: Optional parameter set ID to use as starting point

        Returns:
            SpatialSetupResult with initial configuration
        """
        logger.info("Starting spatial setup workflow")

        try:
            # Verify we can transition to SETUP state
            transition = self.workflow.transition_to(
                WorkflowState.SETUP,
                {HardwareRequirement.DISPLAY_SYSTEM}
            )

            if not transition.success:
                return SpatialSetupResult(
                    success=False,
                    error_message=f"Cannot start setup: {transition.error_message}",
                    workflow_state=self.workflow.get_current_state()
                )

            # Load base parameters or use defaults
            if base_parameters:
                try:
                    params = self.parameter_manager.get_parameters(base_parameters)
                    self.current_config = params.spatial_config
                    logger.info(f"Loaded base parameters: {base_parameters}")
                except Exception as e:
                    logger.warning(f"Could not load base parameters {base_parameters}: {e}")
                    params = self.parameter_manager.get_development_defaults()
                    self.current_config = params.spatial_config
            else:
                params = self.parameter_manager.get_development_defaults()
                self.current_config = params.spatial_config

            # Initialize display system for preview
            display_manager = await self.hardware_factory.create_display_manager()
            preview_available = await display_manager.is_available()

            return SpatialSetupResult(
                success=True,
                spatial_config=self.current_config,
                workflow_state=WorkflowState.SETUP,
                preview_available=preview_available,
                field_of_view=self._calculate_field_of_view(self.current_config)
            )

        except Exception as e:
            logger.exception("Error starting spatial setup")
            return SpatialSetupResult(
                success=False,
                error_message=f"Spatial setup initialization failed: {str(e)}",
                workflow_state=self.workflow.get_current_state()
            )

    async def update_spatial_configuration(
        self,
        config_updates: Dict[str, float]
    ) -> 'SpatialSetupResult':
        """
        Update spatial configuration parameters with real-time validation

        Args:
            config_updates: Dictionary of parameter updates

        Returns:
            Updated SpatialSetupResult
        """
        logger.debug(f"Updating spatial configuration: {config_updates}")

        try:
            if not self.current_config:
                return SpatialSetupResult(
                    success=False,
                    error_message="No current configuration to update"
                )

            # Create updated configuration
            current_dict = self.current_config.model_dump()
            current_dict.update(config_updates)

            # Validate new configuration
            try:
                new_config = SpatialConfiguration(**current_dict)
                validation_result = self._validate_configuration(new_config)

                if validation_result.is_valid:
                    self.current_config = new_config
                    self.validation_errors = []
                    logger.debug("Configuration updated successfully")
                else:
                    self.validation_errors = validation_result.errors
                    logger.warning(f"Configuration validation warnings: {validation_result.errors}")

                return SpatialSetupResult(
                    success=True,
                    spatial_config=self.current_config,
                    workflow_state=WorkflowState.SETUP,
                    validation_errors=self.validation_errors,
                    field_of_view=self._calculate_field_of_view(self.current_config),
                    pixels_per_degree=self.current_config.pixels_per_degree
                )

            except Exception as e:
                return SpatialSetupResult(
                    success=False,
                    error_message=f"Invalid configuration: {str(e)}",
                    spatial_config=self.current_config
                )

        except Exception as e:
            logger.exception("Error updating spatial configuration")
            return SpatialSetupResult(
                success=False,
                error_message=f"Configuration update failed: {str(e)}"
            )

    def _validate_configuration(self, config: SpatialConfiguration) -> 'ConfigurationValidation':
        """Validate spatial configuration for scientific accuracy"""
        errors = []

        # Check visual field coverage is reasonable
        if config.field_of_view_horizontal_degrees > 180:
            errors.append("Horizontal field of view exceeds 180 degrees")
        if config.field_of_view_vertical_degrees > 180:
            errors.append("Vertical field of view exceeds 180 degrees")

        # Check monitor distance is in reasonable range for mouse
        if config.monitor_distance_cm < 5:
            errors.append("Monitor distance too close (< 5cm)")
        elif config.monitor_distance_cm > 50:
            errors.append("Monitor distance too far (> 50cm)")

        # Check pixel density is reasonable
        if config.pixels_per_degree < 1:
            errors.append("Pixel density too low (< 1 pixel/degree)")
        elif config.pixels_per_degree > 100:
            errors.append("Pixel density extremely high (> 100 pixels/degree)")

        return ConfigurationValidation(
            is_valid=len(errors) == 0,
            errors=errors
        )

    def _calculate_field_of_view(self, config: SpatialConfiguration) -> Dict[str, float]:
        """Calculate actual field of view based on configuration"""
        # Calculate field of view from screen geometry
        horizontal_fov = 2 * math.degrees(
            math.atan(config.screen_width_cm / (2 * config.monitor_distance_cm))
        )
        vertical_fov = 2 * math.degrees(
            math.atan(config.screen_height_cm / (2 * config.monitor_distance_cm))
        )

        return {
            "horizontal_degrees": horizontal_fov,
            "vertical_degrees": vertical_fov,
            "diagonal_degrees": math.sqrt(horizontal_fov**2 + vertical_fov**2)
        }


class SpatialSetupResult:
    """Result of spatial setup operations"""

    def __init__(
        self,
        success: bool,
        spatial_config: Optional[SpatialConfiguration] = None,
        workflow_state: Optional[WorkflowState] = None,
        error_message: Optional[str] = None,
        validation_errors: Optional[List[str]] = None,
        preview_available: bool = False,
        field_of_view: Optional[Dict[str, float]] = None,
        pixels_per_degree: Optional[float] = None,
        setup_complete: bool = False,
        saved_as: Optional[str] = None
    ):
        self.success = success
        self.spatial_config = spatial_config
        self.workflow_state = workflow_state
        self.error_message = error_message
        self.validation_errors = validation_errors or []
        self.preview_available = preview_available
        self.field_of_view = field_of_view
        self.pixels_per_degree = pixels_per_degree
        self.setup_complete = setup_complete
        self.saved_as = saved_as
        self.timestamp = datetime.now()


class ConfigurationValidation:
    """Configuration validation result"""

    def __init__(self, is_valid: bool, errors: List[str]):
        self.is_valid = is_valid
        self.errors = errors