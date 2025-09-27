"""
Centralized Error Handling - Domain Service

Pure domain service for error handling business logic with zero external dependencies.
Consolidates all error handling patterns to eliminate massive DRY violations.
"""

from __future__ import annotations
from typing import Dict, Any, Optional, Type, Union, Protocol, runtime_checkable
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime


class ErrorSeverity(Enum):
    """Error severity levels for categorization and handling"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for proper handling and recovery"""
    VALIDATION = "validation"          # Input validation errors
    BUSINESS_LOGIC = "business_logic"  # Domain rule violations
    RESOURCE = "resource"              # Resource availability errors
    CONFIGURATION = "configuration"   # Configuration/setup errors
    INFRASTRUCTURE = "infrastructure" # External system errors
    WORKFLOW = "workflow"             # Workflow state errors
    SYSTEM = "system"                 # System-level errors


class ErrorRecoveryStrategy(Enum):
    """Recovery strategies for different error types"""
    NONE = "none"                     # No recovery possible
    RETRY = "retry"                   # Retry operation
    FALLBACK = "fallback"             # Use fallback method
    USER_INTERVENTION = "user"        # Requires user intervention
    SYSTEM_RESTART = "restart"        # Requires system restart
    GRACEFUL_DEGRADATION = "degrade"  # Continue with reduced functionality


class DomainError(BaseModel):
    """
    Immutable domain error representation

    Pure domain object with no external dependencies
    """
    code: str
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    recovery_strategy: ErrorRecoveryStrategy
    context: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    cause: Optional['DomainError'] = None

    model_config = {"frozen": True}

    def with_context(self, **context_data) -> DomainError:
        """Create new error with additional context"""
        return DomainError(
            code=self.code,
            message=self.message,
            category=self.category,
            severity=self.severity,
            recovery_strategy=self.recovery_strategy,
            context={**self.context, **context_data},
            timestamp=self.timestamp,
            cause=self.cause
        )

    def with_cause(self, cause: DomainError) -> DomainError:
        """Create new error with causal relationship"""
        return DomainError(
            code=self.code,
            message=self.message,
            category=self.category,
            severity=self.severity,
            recovery_strategy=self.recovery_strategy,
            context=self.context,
            timestamp=self.timestamp,
            cause=cause
        )


@runtime_checkable
class ErrorLogger(Protocol):
    """Protocol for error logging - allows injection without dependencies"""
    def log_error(self, error: DomainError, exception: Optional[Exception] = None) -> None:
        """Log error with appropriate level based on severity"""
        ...


class ErrorHandlingService:
    """
    Domain service for centralized error handling

    Pure business logic for error handling patterns with zero external dependencies.
    All 24+ custom exception classes should use this service.
    """

    def __init__(self, logger: Optional[ErrorLogger] = None):
        """
        Initialize error handler

        Args:
            logger: Optional error logger (injected dependency)
        """
        self._logger = logger
        self._error_definitions = self._initialize_error_definitions()

    def _initialize_error_definitions(self) -> Dict[str, DomainError]:
        """Initialize standard error definitions for the system"""
        return {
            # Parameter and Validation Errors
            "PARAMETER_VALIDATION_ERROR": DomainError(
                code="PARAM_VALIDATION",
                message="Parameter validation failed",
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.MEDIUM,
                recovery_strategy=ErrorRecoveryStrategy.USER_INTERVENTION
            ),
            "PARAMETER_COMPATIBILITY_ERROR": DomainError(
                code="PARAM_COMPATIBILITY",
                message="Parameter compatibility check failed",
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.MEDIUM,
                recovery_strategy=ErrorRecoveryStrategy.USER_INTERVENTION
            ),

            # Workflow Errors
            "WORKFLOW_TRANSITION_ERROR": DomainError(
                code="WORKFLOW_TRANSITION",
                message="Invalid workflow state transition",
                category=ErrorCategory.WORKFLOW,
                severity=ErrorSeverity.HIGH,
                recovery_strategy=ErrorRecoveryStrategy.USER_INTERVENTION
            ),
            "WORKFLOW_VALIDATION_ERROR": DomainError(
                code="WORKFLOW_VALIDATION",
                message="Workflow validation failed",
                category=ErrorCategory.WORKFLOW,
                severity=ErrorSeverity.HIGH,
                recovery_strategy=ErrorRecoveryStrategy.USER_INTERVENTION
            ),

            # Dataset and Repository Errors
            "DATASET_ERROR": DomainError(
                code="DATASET_ERROR",
                message="Dataset operation failed",
                category=ErrorCategory.RESOURCE,
                severity=ErrorSeverity.MEDIUM,
                recovery_strategy=ErrorRecoveryStrategy.RETRY
            ),
            "REPOSITORY_ERROR": DomainError(
                code="REPOSITORY_ERROR",
                message="Repository operation failed",
                category=ErrorCategory.RESOURCE,
                severity=ErrorSeverity.HIGH,
                recovery_strategy=ErrorRecoveryStrategy.RETRY
            ),

            # Analysis and Calculation Errors
            "ISI_ANALYSIS_ERROR": DomainError(
                code="ISI_ANALYSIS",
                message="ISI analysis failed",
                category=ErrorCategory.BUSINESS_LOGIC,
                severity=ErrorSeverity.HIGH,
                recovery_strategy=ErrorRecoveryStrategy.USER_INTERVENTION
            ),
            "STIMULUS_CALCULATION_ERROR": DomainError(
                code="STIMULUS_CALCULATION",
                message="Stimulus calculation failed",
                category=ErrorCategory.BUSINESS_LOGIC,
                severity=ErrorSeverity.HIGH,
                recovery_strategy=ErrorRecoveryStrategy.USER_INTERVENTION
            ),
            "PHASE_UNWRAPPING_ERROR": DomainError(
                code="PHASE_UNWRAPPING",
                message="Phase unwrapping failed",
                category=ErrorCategory.BUSINESS_LOGIC,
                severity=ErrorSeverity.HIGH,
                recovery_strategy=ErrorRecoveryStrategy.FALLBACK
            ),
            "SIGN_MAP_ERROR": DomainError(
                code="SIGN_MAP_ERROR",
                message="Sign map calculation failed",
                category=ErrorCategory.BUSINESS_LOGIC,
                severity=ErrorSeverity.HIGH,
                recovery_strategy=ErrorRecoveryStrategy.FALLBACK
            ),

            # Streaming and Configuration Errors
            "STREAMING_ERROR": DomainError(
                code="STREAMING_ERROR",
                message="Streaming configuration error",
                category=ErrorCategory.CONFIGURATION,
                severity=ErrorSeverity.HIGH,
                recovery_strategy=ErrorRecoveryStrategy.USER_INTERVENTION
            ),
            "STREAMING_VALIDATION_ERROR": DomainError(
                code="STREAMING_VALIDATION",
                message="Streaming validation failed",
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.MEDIUM,
                recovery_strategy=ErrorRecoveryStrategy.USER_INTERVENTION
            ),

            # Application Layer Errors
            "COMMUNICATION_ERROR": DomainError(
                code="COMMUNICATION_ERROR",
                message="Communication system error",
                category=ErrorCategory.INFRASTRUCTURE,
                severity=ErrorSeverity.HIGH,
                recovery_strategy=ErrorRecoveryStrategy.RETRY
            ),
            "QUERY_ERROR": DomainError(
                code="QUERY_ERROR",
                message="Query processing failed",
                category=ErrorCategory.BUSINESS_LOGIC,
                severity=ErrorSeverity.MEDIUM,
                recovery_strategy=ErrorRecoveryStrategy.RETRY
            ),
            "PERSISTENCE_ERROR": DomainError(
                code="PERSISTENCE_ERROR",
                message="State persistence failed",
                category=ErrorCategory.INFRASTRUCTURE,
                severity=ErrorSeverity.CRITICAL,
                recovery_strategy=ErrorRecoveryStrategy.RETRY
            ),
            "STIMULUS_GENERATION_ERROR": DomainError(
                code="STIMULUS_GENERATION",
                message="Stimulus generation failed",
                category=ErrorCategory.BUSINESS_LOGIC,
                severity=ErrorSeverity.HIGH,
                recovery_strategy=ErrorRecoveryStrategy.USER_INTERVENTION
            ),
            "DATA_ACQUISITION_ERROR": DomainError(
                code="DATA_ACQUISITION",
                message="Data acquisition failed",
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.CRITICAL,
                recovery_strategy=ErrorRecoveryStrategy.USER_INTERVENTION
            ),
            "SESSION_MANAGEMENT_ERROR": DomainError(
                code="SESSION_MANAGEMENT",
                message="Session management failed",
                category=ErrorCategory.BUSINESS_LOGIC,
                severity=ErrorSeverity.HIGH,
                recovery_strategy=ErrorRecoveryStrategy.RETRY
            ),
            "SESSION_VALIDATION_ERROR": DomainError(
                code="SESSION_VALIDATION",
                message="Session validation failed",
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.MEDIUM,
                recovery_strategy=ErrorRecoveryStrategy.USER_INTERVENTION
            ),
            "SYSTEM_STARTUP_ERROR": DomainError(
                code="SYSTEM_STARTUP",
                message="System startup failed",
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.CRITICAL,
                recovery_strategy=ErrorRecoveryStrategy.SYSTEM_RESTART
            ),

            # Infrastructure Layer Errors
            "HDF5_STORAGE_ERROR": DomainError(
                code="HDF5_STORAGE",
                message="HDF5 storage operation failed",
                category=ErrorCategory.INFRASTRUCTURE,
                severity=ErrorSeverity.HIGH,
                recovery_strategy=ErrorRecoveryStrategy.RETRY
            ),
            "SYSTEM_MONITOR_ERROR": DomainError(
                code="SYSTEM_MONITOR",
                message="System monitoring failed",
                category=ErrorCategory.INFRASTRUCTURE,
                severity=ErrorSeverity.MEDIUM,
                recovery_strategy=ErrorRecoveryStrategy.GRACEFUL_DEGRADATION
            ),
            "BUFFER_ERROR": DomainError(
                code="BUFFER_ERROR",
                message="Buffer operation failed",
                category=ErrorCategory.INFRASTRUCTURE,
                severity=ErrorSeverity.HIGH,
                recovery_strategy=ErrorRecoveryStrategy.RETRY
            ),
            "CAMERA_CALIBRATION_ERROR": DomainError(
                code="CAMERA_CALIBRATION",
                message="Camera calibration failed",
                category=ErrorCategory.CONFIGURATION,
                severity=ErrorSeverity.HIGH,
                recovery_strategy=ErrorRecoveryStrategy.USER_INTERVENTION
            ),
            "DISPLAY_CALIBRATION_ERROR": DomainError(
                code="DISPLAY_CALIBRATION",
                message="Display calibration failed",
                category=ErrorCategory.CONFIGURATION,
                severity=ErrorSeverity.HIGH,
                recovery_strategy=ErrorRecoveryStrategy.USER_INTERVENTION
            ),
        }

    def create_error(
        self,
        error_code: str,
        custom_message: Optional[str] = None,
        **context
    ) -> DomainError:
        """
        Create a domain error from predefined error code

        Args:
            error_code: Predefined error code
            custom_message: Optional custom message to override default
            **context: Additional context data

        Returns:
            DomainError instance
        """
        base_error = self._error_definitions.get(error_code)
        if not base_error:
            # Fallback for unknown error codes
            base_error = DomainError(
                code=error_code,
                message=custom_message or f"Unknown error: {error_code}",
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.HIGH,
                recovery_strategy=ErrorRecoveryStrategy.NONE
            )

        # Override message if provided
        message = custom_message if custom_message else base_error.message

        return DomainError(
            code=base_error.code,
            message=message,
            category=base_error.category,
            severity=base_error.severity,
            recovery_strategy=base_error.recovery_strategy,
            context=context
        )

    def handle_exception(
        self,
        exception: Exception,
        error_code: str,
        custom_message: Optional[str] = None,
        **context
    ) -> DomainError:
        """
        Handle a caught exception and convert to domain error

        This replaces all the duplicated try/catch/log/raise patterns

        Args:
            exception: The caught exception
            error_code: Domain error code to map to
            custom_message: Optional custom message
            **context: Additional context data

        Returns:
            DomainError with exception details
        """
        # Add exception details to context
        exception_context = {
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
            **context
        }

        domain_error = self.create_error(
            error_code=error_code,
            custom_message=custom_message,
            **exception_context
        )

        # Log error if logger is available
        if self._logger:
            self._logger.log_error(domain_error, exception)

        return domain_error

    def is_recoverable(self, error: DomainError) -> bool:
        """Check if error is recoverable"""
        return error.recovery_strategy != ErrorRecoveryStrategy.NONE

    def should_retry(self, error: DomainError) -> bool:
        """Check if error suggests retry"""
        return error.recovery_strategy == ErrorRecoveryStrategy.RETRY

    def requires_user_intervention(self, error: DomainError) -> bool:
        """Check if error requires user intervention"""
        return error.recovery_strategy == ErrorRecoveryStrategy.USER_INTERVENTION

    def get_error_context(self, error: DomainError) -> Dict[str, Any]:
        """Get full error context for debugging/reporting"""
        return {
            "code": error.code,
            "message": error.message,
            "category": error.category.value,
            "severity": error.severity.value,
            "recovery_strategy": error.recovery_strategy.value,
            "timestamp": error.timestamp.isoformat(),
            "context": error.context,
            "has_cause": error.cause is not None
        }


# Domain Exception Classes
# These replace all the scattered custom exceptions

class ISIDomainError(Exception):
    """
    Base domain exception that wraps DomainError

    This is the ONLY exception class needed for the entire system.
    All 24+ custom exceptions should be replaced with this.
    """

    def __init__(self, domain_error: DomainError):
        self.domain_error = domain_error
        super().__init__(domain_error.message)

    @property
    def code(self) -> str:
        return self.domain_error.code

    @property
    def category(self) -> ErrorCategory:
        return self.domain_error.category

    @property
    def severity(self) -> ErrorSeverity:
        return self.domain_error.severity

    @property
    def recovery_strategy(self) -> ErrorRecoveryStrategy:
        return self.domain_error.recovery_strategy

    @property
    def context(self) -> Dict[str, Any]:
        return self.domain_error.context


# Convenience functions for common error patterns
def create_parameter_error(message: str, **context) -> ISIDomainError:
    """Create parameter validation error"""
    error_handler = ErrorHandlingService()
    domain_error = error_handler.create_error("PARAMETER_VALIDATION_ERROR", message, **context)
    return ISIDomainError(domain_error)


def create_workflow_error(message: str, **context) -> ISIDomainError:
    """Create workflow error"""
    error_handler = ErrorHandlingService()
    domain_error = error_handler.create_error("WORKFLOW_TRANSITION_ERROR", message, **context)
    return ISIDomainError(domain_error)


def create_analysis_error(message: str, **context) -> ISIDomainError:
    """Create analysis error"""
    error_handler = ErrorHandlingService()
    domain_error = error_handler.create_error("ISI_ANALYSIS_ERROR", message, **context)
    return ISIDomainError(domain_error)