"""
Error Recovery Use Case

Orchestrates system error recovery procedures and graceful degradation strategies
following the error handling patterns defined in ADR-0014.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from domain.services.error_handler import ErrorHandlingService, ISIDomainError, ErrorRecoveryStrategy
from domain.services.workflow_orchestrator import WorkflowOrchestrator
from application.services.monitoring_service import MonitoringService
from application.services.state_persistence import StatePersistenceService


class RecoveryAction(Enum):
    """Types of recovery actions that can be performed"""
    RESTART_COMPONENT = "restart_component"
    RESET_TO_SAFE_STATE = "reset_to_safe_state"
    GRACEFUL_DEGRADATION = "graceful_degradation"
    EMERGENCY_SHUTDOWN = "emergency_shutdown"
    RESTORE_FROM_BACKUP = "restore_from_backup"


class ErrorRecoveryUseCase:
    """
    Use case for coordinating system error recovery

    Implements sophisticated error recovery strategies based on error type,
    system state, and available recovery options.
    """

    def __init__(
        self,
        workflow_orchestrator: WorkflowOrchestrator,
        monitoring_service: MonitoringService,
        state_persistence: StatePersistenceService,
        error_handler: Optional[ErrorHandlingService] = None
    ):
        self.workflow_orchestrator = workflow_orchestrator
        self.monitoring_service = monitoring_service
        self.state_persistence = state_persistence
        self.error_handler = error_handler or ErrorHandlingService()

        # Recovery strategy mappings
        self._recovery_strategies = {
            ErrorRecoveryStrategy.RETRY: self._retry_operation,
            ErrorRecoveryStrategy.FALLBACK: self._execute_fallback,
            ErrorRecoveryStrategy.USER_INTERVENTION: self._request_user_intervention,
            ErrorRecoveryStrategy.SYSTEM_RESTART: self._restart_system,
            ErrorRecoveryStrategy.GRACEFUL_DEGRADATION: self._graceful_degradation
        }

    async def handle_system_error(
        self,
        error: ISIDomainError,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute appropriate recovery strategy for system error

        Args:
            error: The domain error that occurred
            context: Additional context about the error situation

        Returns:
            Recovery execution results
        """
        try:
            recovery_context = context or {}
            recovery_context["error_timestamp"] = datetime.now().isoformat()
            recovery_context["error_code"] = error.domain_error.error_code

            # Determine appropriate recovery strategy
            strategy = error.domain_error.recovery_strategy

            # Log error for monitoring
            self.monitoring_service.log_error(error, recovery_context)

            # Execute recovery strategy
            recovery_result = await self._execute_recovery_strategy(
                strategy, error, recovery_context
            )

            # Update system state based on recovery outcome
            await self._update_system_state_after_recovery(recovery_result)

            return recovery_result

        except Exception as e:
            # Recovery itself failed - escalate to emergency procedures
            return await self._emergency_recovery(e, error)

    async def _execute_recovery_strategy(
        self,
        strategy: ErrorRecoveryStrategy,
        error: ISIDomainError,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the specified recovery strategy"""

        if strategy not in self._recovery_strategies:
            # Unknown strategy - default to user intervention
            strategy = ErrorRecoveryStrategy.USER_INTERVENTION

        recovery_handler = self._recovery_strategies[strategy]
        return await recovery_handler(error, context)

    async def _retry_operation(
        self,
        error: ISIDomainError,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Implement retry recovery strategy"""

        max_retries = context.get("max_retries", 3)
        retry_count = context.get("retry_count", 0)

        if retry_count >= max_retries:
            # Max retries exceeded - escalate to fallback
            return await self._execute_fallback(error, context)

        # Wait before retry (exponential backoff)
        import asyncio
        await asyncio.sleep(2 ** retry_count)

        context["retry_count"] = retry_count + 1

        return {
            "action": RecoveryAction.RESTART_COMPONENT.value,
            "success": True,
            "message": f"Retrying operation (attempt {retry_count + 1}/{max_retries})",
            "context": context,
            "next_action": "retry_original_operation"
        }

    async def _execute_fallback(
        self,
        error: ISIDomainError,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Implement fallback recovery strategy"""

        # Attempt to restore from last known good state
        try:
            last_snapshot = await self.state_persistence.get_latest_snapshot()
            if last_snapshot:
                await self.workflow_orchestrator.restore_state(last_snapshot)

                return {
                    "action": RecoveryAction.RESTORE_FROM_BACKUP.value,
                    "success": True,
                    "message": "Restored from last known good state",
                    "restored_state": last_snapshot.state_id,
                    "context": context
                }
        except Exception:
            pass

        # If restore fails, fall back to safe state
        return await self._reset_to_safe_state(context)

    async def _request_user_intervention(
        self,
        error: ISIDomainError,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Request user intervention for error resolution"""

        return {
            "action": RecoveryAction.RESET_TO_SAFE_STATE.value,
            "success": False,
            "message": "User intervention required",
            "error_details": {
                "error_code": error.domain_error.error_code,
                "error_message": error.domain_error.message,
                "suggested_actions": self._get_suggested_user_actions(error)
            },
            "context": context,
            "requires_user_action": True
        }

    async def _restart_system(
        self,
        error: ISIDomainError,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Implement system restart recovery strategy"""

        try:
            # Save current state before restart
            await self.state_persistence.create_emergency_snapshot()

            # Reset workflow to initial state
            await self.workflow_orchestrator.reset_to_initial_state()

            return {
                "action": RecoveryAction.RESTART_COMPONENT.value,
                "success": True,
                "message": "System restarted successfully",
                "context": context,
                "emergency_snapshot_saved": True
            }

        except Exception as restart_error:
            return await self._emergency_recovery(restart_error, error)

    async def _graceful_degradation(
        self,
        error: ISIDomainError,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Implement graceful degradation strategy"""

        # Identify which components can be safely disabled
        degraded_components = self._identify_degradable_components(error)

        try:
            # Disable non-essential components
            for component in degraded_components:
                await self._disable_component(component)

            return {
                "action": RecoveryAction.GRACEFUL_DEGRADATION.value,
                "success": True,
                "message": "System operating in degraded mode",
                "disabled_components": degraded_components,
                "context": context
            }

        except Exception as degradation_error:
            return await self._emergency_recovery(degradation_error, error)

    async def _reset_to_safe_state(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Reset system to known safe state"""

        try:
            await self.workflow_orchestrator.transition_to_safe_state()

            return {
                "action": RecoveryAction.RESET_TO_SAFE_STATE.value,
                "success": True,
                "message": "System reset to safe state",
                "context": context
            }

        except Exception as e:
            return {
                "action": RecoveryAction.EMERGENCY_SHUTDOWN.value,
                "success": False,
                "message": f"Failed to reset to safe state: {str(e)}",
                "context": context,
                "requires_manual_intervention": True
            }

    async def _emergency_recovery(
        self,
        recovery_error: Exception,
        original_error: ISIDomainError
    ) -> Dict[str, Any]:
        """Last resort emergency recovery procedures"""

        return {
            "action": RecoveryAction.EMERGENCY_SHUTDOWN.value,
            "success": False,
            "message": "Emergency recovery procedures activated",
            "original_error": original_error.domain_error.message,
            "recovery_error": str(recovery_error),
            "requires_manual_intervention": True,
            "emergency_timestamp": datetime.now().isoformat()
        }

    async def _update_system_state_after_recovery(
        self,
        recovery_result: Dict[str, Any]
    ) -> None:
        """Update system monitoring and state after recovery"""

        # Log recovery outcome
        self.monitoring_service.log_recovery_attempt(recovery_result)

        # Update health status based on recovery success
        if recovery_result.get("success", False):
            await self.monitoring_service.mark_component_healthy("error_recovery")
        else:
            await self.monitoring_service.mark_component_unhealthy(
                "error_recovery", recovery_result.get("message", "Recovery failed")
            )

    def _get_suggested_user_actions(self, error: ISIDomainError) -> List[str]:
        """Get suggested actions for user intervention"""

        # Map error codes to suggested actions
        suggestions_map = {
            "HARDWARE_ERROR": [
                "Check hardware connections",
                "Verify hardware is powered on",
                "Restart hardware components"
            ],
            "CONFIGURATION_ERROR": [
                "Check configuration file syntax",
                "Verify configuration parameters",
                "Reset to default configuration"
            ],
            "PERMISSION_ERROR": [
                "Check file permissions",
                "Run with appropriate privileges",
                "Verify disk space availability"
            ]
        }

        error_code = error.domain_error.error_code
        return suggestions_map.get(error_code, [
            "Review system logs",
            "Contact system administrator",
            "Restart the application"
        ])

    def _identify_degradable_components(self, error: ISIDomainError) -> List[str]:
        """Identify components that can be safely disabled for degraded operation"""

        # Components that can be disabled without stopping core functionality
        degradable_components = [
            "preview_generation",
            "performance_monitoring",
            "advanced_analysis_features"
        ]

        # Filter based on error type and current system state
        error_code = error.domain_error.error_code
        if "HARDWARE" in error_code:
            degradable_components.extend(["hardware_monitoring", "calibration_checks"])

        return degradable_components

    async def _disable_component(self, component: str) -> None:
        """Safely disable a system component"""
        # This would integrate with the monitoring service
        # to disable specific components
        await self.monitoring_service.disable_component(component)