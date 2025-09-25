"""
Configuration Repository Domain Interface

Abstract interface for configuration management following Clean Architecture principles.
This interface belongs in the domain layer and defines contracts for configuration
storage and retrieval that are implemented by infrastructure components.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from enum import Enum

from src.domain.entities.parameters import CombinedParameters

from domain.value_objects.parameters import CombinedParameters


class ConfigurationScope(Enum):
    """Scope of configuration settings"""

    SYSTEM = "system"  # System-wide configuration
    USER = "user"  # User-specific configuration
    SESSION = "session"  # Session-specific configuration
    HARDWARE = "hardware"  # Hardware-specific configuration
    CALIBRATION = "calibration"  # Calibration data and settings


class ConfigurationInterface(ABC):
    """Abstract interface for configuration management"""

    @abstractmethod
    async def get_configuration(
        self, scope: ConfigurationScope, key: str, default: Optional[Any] = None
    ) -> Any:
        """
        Retrieve a configuration value

        Args:
            scope: Configuration scope (system, user, session, etc.)
            key: Configuration key (supports dot notation for nested values)
            default: Default value if key not found

        Returns:
            Configuration value or default if not found
        """
        pass

    @abstractmethod
    async def set_configuration(self, scope: ConfigurationScope, key: str, value: Any) -> None:
        """
        Set a configuration value

        Args:
            scope: Configuration scope
            key: Configuration key (supports dot notation for nested values)
            value: Value to set (must be JSON serializable)
        """
        pass

    @abstractmethod
    async def get_all_configurations(self, scope: ConfigurationScope) -> Dict[str, Any]:
        """
        Get all configuration values for a scope

        Args:
            scope: Configuration scope

        Returns:
            Dictionary containing all configuration values for the scope
        """
        pass

    @abstractmethod
    async def delete_configuration(self, scope: ConfigurationScope, key: str) -> bool:
        """
        Delete a configuration value

        Args:
            scope: Configuration scope
            key: Configuration key to delete

        Returns:
            True if key existed and was deleted, False if key didn't exist
        """
        pass

    @abstractmethod
    async def configuration_exists(self, scope: ConfigurationScope, key: str) -> bool:
        """
        Check if a configuration key exists

        Args:
            scope: Configuration scope
            key: Configuration key to check

        Returns:
            True if configuration key exists
        """
        pass

    @abstractmethod
    async def backup_configuration(
        self, scope: ConfigurationScope, backup_name: Optional[str] = None
    ) -> str:
        """
        Create a backup of configuration for a scope

        Args:
            scope: Configuration scope to backup
            backup_name: Optional backup name (timestamp used if not provided)

        Returns:
            Backup identifier/name
        """
        pass

    @abstractmethod
    async def restore_configuration(self, scope: ConfigurationScope, backup_name: str) -> bool:
        """
        Restore configuration from a backup

        Args:
            scope: Configuration scope to restore
            backup_name: Backup name/identifier

        Returns:
            True if restore was successful
        """
        pass

    @abstractmethod
    async def list_backups(self, scope: ConfigurationScope) -> List[Dict[str, Any]]:
        """
        List available backups for a configuration scope

        Args:
            scope: Configuration scope

        Returns:
            List of backup metadata dictionaries
        """
        pass


class ParameterConfigurationInterface(ABC):
    """Specialized interface for experimental parameter configuration"""

    @abstractmethod
    async def save_parameters(
        self,
        parameters: CombinedParameters,
        name: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """
        Save experimental parameters as a named configuration

        Args:
            parameters: Combined experimental parameters
            name: Configuration name
            description: Optional description
            tags: Optional tags for categorization

        Returns:
            Configuration ID
        """
        pass

    @abstractmethod
    async def load_parameters(self, name: str) -> CombinedParameters:
        """
        Load experimental parameters by name

        Args:
            name: Configuration name

        Returns:
            Combined experimental parameters

        Raises:
            ConfigurationNotFoundError: If configuration doesn't exist
        """
        pass

    @abstractmethod
    async def list_parameter_configurations(
        self, tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        List available parameter configurations

        Args:
            tags: Optional tag filter

        Returns:
            List of parameter configuration metadata
        """
        pass

    @abstractmethod
    async def delete_parameters(self, name: str) -> bool:
        """
        Delete a parameter configuration

        Args:
            name: Configuration name

        Returns:
            True if configuration existed and was deleted
        """
        pass

    @abstractmethod
    async def validate_parameters(self, parameters: CombinedParameters) -> Dict[str, Any]:
        """
        Validate parameter configuration

        Args:
            parameters: Parameters to validate

        Returns:
            Validation results including any errors or warnings
        """
        pass


class CalibrationConfigurationInterface(ABC):
    """Specialized interface for calibration data management"""

    @abstractmethod
    async def save_calibration_data(
        self,
        component: str,
        calibration_data: Dict[str, Any],
        valid_until: Optional[datetime] = None,
    ) -> str:
        """
        Save calibration data for a hardware component

        Args:
            component: Hardware component identifier
            calibration_data: Calibration data dictionary
            valid_until: Optional expiration date

        Returns:
            Calibration record ID
        """
        pass

    @abstractmethod
    async def load_calibration_data(
        self, component: str, validate_expiration: bool = True
    ) -> Dict[str, Any]:
        """
        Load calibration data for a hardware component

        Args:
            component: Hardware component identifier
            validate_expiration: Whether to check calibration expiration

        Returns:
            Calibration data dictionary

        Raises:
            CalibrationNotFoundError: If no calibration exists
            CalibrationExpiredError: If calibration is expired (when validation enabled)
        """
        pass

    @abstractmethod
    async def is_calibration_valid(self, component: str) -> bool:
        """
        Check if calibration is valid and current

        Args:
            component: Hardware component identifier

        Returns:
            True if calibration exists and is not expired
        """
        pass

    @abstractmethod
    async def get_calibration_status(self, component: Optional[str] = None) -> Dict[str, Any]:
        """
        Get calibration status for components

        Args:
            component: Specific component, or None for all components

        Returns:
            Dictionary with calibration status information
        """
        pass


# Domain exceptions for configuration management
class ConfigurationError(Exception):
    """Base exception for configuration-related errors"""

    pass


class ConfigurationNotFoundError(ConfigurationError):
    """Raised when a requested configuration is not found"""

    pass


class CalibrationNotFoundError(ConfigurationError):
    """Raised when requested calibration data is not found"""

    pass


class CalibrationExpiredError(ConfigurationError):
    """Raised when calibration data has expired"""

    pass


class ConfigurationValidationError(ConfigurationError):
    """Raised when configuration validation fails"""

    pass
