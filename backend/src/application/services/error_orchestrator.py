"""
Error Orchestrator - Application Service

Application-level error handling orchestrator that implements infrastructure concerns
like logging, metrics, and error reporting while using the pure domain error handler.

This replaces all the duplicated try/catch/log/raise patterns across the codebase.
"""

from __future__ import annotations
from typing import Dict, Any, Optional, List, Callable
import logging
from datetime import datetime, timedelta

from ...domain.services.error_handler import (
    ErrorHandlingService,
    DomainError,
    ISIDomainError,
    ErrorLogger,
    ErrorSeverity,
    ErrorCategory,
    ErrorRecoveryStrategy
)


class ErrorOrchestrator(ErrorLogger):
    """
    Application service that orchestrates error handling with infrastructure concerns

    Implements the ErrorLogger protocol for the domain service while providing:
    - Structured logging with appropriate levels
    - Error metrics collection
    - Error notification/alerting
    - Recovery strategy execution
    """

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        enable_metrics: bool = True,
        enable_alerts: bool = True
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.enable_metrics = enable_metrics
        self.enable_alerts = enable_alerts

        # Initialize domain error handler with this orchestrator as logger
        self.domain_handler = ErrorHandlingService(logger=self)

        # Error tracking
        self._error_counts: Dict[str, int] = {}
        self._error_history: List[DomainError] = []
        self._max_history_size = 1000

        # Alert callbacks
        self._alert_callbacks: List[Callable[[DomainError], None]] = []

        # Recovery callbacks
        self._recovery_handlers: Dict[ErrorRecoveryStrategy, Callable[[DomainError], bool]] = {}

    def log_error(self, error: DomainError, exception: Optional[Exception] = None) -> None:
        """
        Log error with appropriate level based on severity

        Implements ErrorLogger protocol for domain service
        """
        # Map severity to log levels
        level_mapping = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }

        log_level = level_mapping.get(error.severity, logging.ERROR)

        # Create structured log entry
        log_data = {
            "error_code": error.code,
            "category": error.category.value,
            "severity": error.severity.value,
            "recovery_strategy": error.recovery_strategy.value,
            "context": error.context
        }

        # Log with exception details if available
        if exception:
            self.logger.log(
                log_level,
                f"[{error.code}] {error.message}",
                exc_info=exception,
                extra=log_data
            )
        else:
            self.logger.log(
                log_level,
                f"[{error.code}] {error.message}",
                extra=log_data
            )

        # Track error metrics
        if self.enable_metrics:
            self._track_error_metrics(error)

        # Add to history
        self._add_to_history(error)

        # Trigger alerts for high/critical errors
        if self.enable_alerts and error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            self._trigger_alerts(error)

    def handle_exception(
        self,
        exception: Exception,
        error_code: str,
        custom_message: Optional[str] = None,
        **context
    ) -> ISIDomainError:
        """
        Handle exception and return domain error

        This is the main method that replaces all the scattered error handling patterns
        """
        domain_error = self.domain_handler.handle_exception(
            exception=exception,
            error_code=error_code,
            custom_message=custom_message,
            **context
        )

        # Attempt recovery if strategy is defined
        if self._should_attempt_recovery(domain_error):
            recovery_attempted = self._attempt_recovery(domain_error)
            if recovery_attempted:
                # Add recovery attempt to context
                domain_error = domain_error.with_context(recovery_attempted=True)

        return ISIDomainError(domain_error)

    def create_domain_error(
        self,
        error_code: str,
        custom_message: Optional[str] = None,
        **context
    ) -> ISIDomainError:
        """Create domain error directly (without exception)"""
        domain_error = self.domain_handler.create_error(
            error_code=error_code,
            custom_message=custom_message,
            **context
        )

        # Still log it for tracking
        self.log_error(domain_error)

        return ISIDomainError(domain_error)

    def _track_error_metrics(self, error: DomainError) -> None:
        """Track error metrics for monitoring"""
        # Count by error code
        self._error_counts[error.code] = self._error_counts.get(error.code, 0) + 1

        # Could integrate with monitoring service here
        # For now, just track counts for reporting

    def _add_to_history(self, error: DomainError) -> None:
        """Add error to history with size limit"""
        self._error_history.append(error)

        # Maintain history size limit
        if len(self._error_history) > self._max_history_size:
            self._error_history = self._error_history[-self._max_history_size:]

    def _trigger_alerts(self, error: DomainError) -> None:
        """Trigger alerts for critical errors"""
        for callback in self._alert_callbacks:
            try:
                callback(error)
            except Exception as e:
                # Don't let alert failures break error handling
                self.logger.warning(f"Alert callback failed: {e}")

    def _should_attempt_recovery(self, error: DomainError) -> bool:
        """Check if recovery should be attempted"""
        return (
            error.recovery_strategy != ErrorRecoveryStrategy.NONE and
            error.recovery_strategy in self._recovery_handlers
        )

    def _attempt_recovery(self, error: DomainError) -> bool:
        """Attempt error recovery based on strategy"""
        recovery_handler = self._recovery_handlers.get(error.recovery_strategy)
        if recovery_handler:
            try:
                return recovery_handler(error)
            except Exception as e:
                self.logger.warning(f"Recovery attempt failed: {e}")
                return False
        return False

    def add_alert_callback(self, callback: Callable[[DomainError], None]) -> None:
        """Add callback for error alerts"""
        self._alert_callbacks.append(callback)

    def remove_alert_callback(self, callback: Callable[[DomainError], None]) -> None:
        """Remove alert callback"""
        if callback in self._alert_callbacks:
            self._alert_callbacks.remove(callback)

    def register_recovery_handler(
        self,
        strategy: ErrorRecoveryStrategy,
        handler: Callable[[DomainError], bool]
    ) -> None:
        """Register recovery handler for specific strategy"""
        self._recovery_handlers[strategy] = handler

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for monitoring/reporting"""
        total_errors = sum(self._error_counts.values())

        # Calculate recent error rate (last hour)
        recent_cutoff = datetime.now() - timedelta(hours=1)
        recent_errors = [
            e for e in self._error_history
            if e.timestamp >= recent_cutoff
        ]

        return {
            "total_errors": total_errors,
            "error_counts_by_code": dict(self._error_counts),
            "recent_error_count": len(recent_errors),
            "history_size": len(self._error_history),
            "most_common_errors": self._get_most_common_errors(5)
        }

    def _get_most_common_errors(self, limit: int) -> List[Dict[str, Any]]:
        """Get most common errors sorted by count"""
        sorted_errors = sorted(
            self._error_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [
            {"error_code": code, "count": count}
            for code, count in sorted_errors[:limit]
        ]

    def get_recent_errors(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent errors for debugging"""
        recent_errors = sorted(
            self._error_history,
            key=lambda e: e.timestamp,
            reverse=True
        )[:limit]

        return [
            self.domain_handler.get_error_context(error)
            for error in recent_errors
        ]

    def clear_error_history(self) -> None:
        """Clear error history and reset counts"""
        self._error_history.clear()
        self._error_counts.clear()


# Convenience decorator for error handling
def handle_errors(error_code: str, custom_message: Optional[str] = None):
    """
    Decorator to automatically handle exceptions in methods

    Usage:
    @handle_errors("REPOSITORY_ERROR", "Failed to save data")
    def save_data(self, data):
        # method implementation
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Assume first arg is self with error_orchestrator
            instance = args[0]
            error_orchestrator = getattr(instance, '_error_orchestrator', None)

            if not error_orchestrator:
                # Fallback to basic exception handling
                return func(*args, **kwargs)

            try:
                return func(*args, **kwargs)
            except Exception as e:
                domain_error = error_orchestrator.handle_exception(
                    exception=e,
                    error_code=error_code,
                    custom_message=custom_message,
                    function=func.__name__,
                    args=str(args[1:]) if len(args) > 1 else "none",
                    kwargs=str(kwargs) if kwargs else "none"
                )
                raise domain_error

        return wrapper
    return decorator


# Global error orchestrator instance for convenience
# This can be configured at application startup
_global_error_orchestrator: Optional[ErrorOrchestrator] = None


def get_error_orchestrator() -> ErrorOrchestrator:
    """Get global error orchestrator instance"""
    global _global_error_orchestrator
    if _global_error_orchestrator is None:
        _global_error_orchestrator = ErrorOrchestrator()
    return _global_error_orchestrator


def configure_global_error_orchestrator(
    logger: Optional[logging.Logger] = None,
    enable_metrics: bool = True,
    enable_alerts: bool = True
) -> ErrorOrchestrator:
    """Configure global error orchestrator"""
    global _global_error_orchestrator
    _global_error_orchestrator = ErrorOrchestrator(
        logger=logger,
        enable_metrics=enable_metrics,
        enable_alerts=enable_alerts
    )
    return _global_error_orchestrator


# Convenience functions that use global orchestrator
def handle_exception(
    exception: Exception,
    error_code: str,
    custom_message: Optional[str] = None,
    **context
) -> ISIDomainError:
    """Handle exception using global orchestrator"""
    return get_error_orchestrator().handle_exception(
        exception=exception,
        error_code=error_code,
        custom_message=custom_message,
        **context
    )


def create_error(
    error_code: str,
    custom_message: Optional[str] = None,
    **context
) -> ISIDomainError:
    """Create domain error using global orchestrator"""
    return get_error_orchestrator().create_domain_error(
        error_code=error_code,
        custom_message=custom_message,
        **context
    )