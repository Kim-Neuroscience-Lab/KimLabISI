"""
Session Management Use Case

This module implements the session management use case for coordinating
experimental sessions following clean architecture principles. Handles
session lifecycle, state management, and integration with workflow state machine.

Key Responsibilities:
- Session creation and initialization
- Session state transitions and validation
- Parameter set management and validation
- Integration with workflow state machine
- Session persistence and recovery
- Error handling and session integrity
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from domain.entities.workflow_state_machine import WorkflowStateMachine
from domain.value_objects.workflow_state import WorkflowState
from domain.value_objects.parameters import CombinedParameters, ParameterSource
from domain.repositories.experiment_repository import (
    ExperimentRepositoryInterface,
    ExperimentSessionInterface,
    SessionStatus,
    SessionType
)
from domain.repositories.data_repository import DataRepositoryInterface

logger = logging.getLogger(__name__)


class SessionManagementError(Exception):
    """Exception raised for session management errors"""
    pass


class SessionValidationError(Exception):
    """Exception raised for session validation errors"""
    pass


class SessionManagementUseCase:
    """
    Session Management Use Case

    Orchestrates experimental session management according to clean architecture.
    Coordinates between domain entities, repositories, and workflow state machine.
    """

    def __init__(
        self,
        experiment_repository: ExperimentRepositoryInterface,
        data_repository: DataRepositoryInterface,
        workflow_state_machine: WorkflowStateMachine
    ):
        """
        Initialize session management use case

        Args:
            experiment_repository: Repository for experiment session management
            data_repository: Repository for data storage
            workflow_state_machine: Domain workflow state machine
        """
        self.experiment_repository = experiment_repository
        self.data_repository = data_repository
        self.workflow_state_machine = workflow_state_machine

        # Current active session
        self._current_session: Optional[ExperimentSessionInterface] = None

        logger.info("Session management use case initialized")

    async def create_session(
        self,
        session_type: SessionType,
        parameters: CombinedParameters,
        protocol_name: str = "Unknown Protocol",
        subject_id: Optional[str] = None,
        experimenter: Optional[str] = None,
        notes: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> ExperimentSessionInterface:
        """
        Create a new experimental session

        Args:
            session_type: Type of experimental session
            parameters: Combined parameters for the session
            protocol_name: Name of the experimental protocol
            subject_id: Subject identifier (optional)
            experimenter: Experimenter name (optional)
            notes: Session notes (optional)
            session_id: Custom session ID (optional, auto-generated if None)

        Returns:
            Created session interface

        Raises:
            SessionManagementError: If session creation fails
            SessionValidationError: If parameters are invalid
        """
        try:
            logger.info(f"Creating new session: type={session_type.value}, protocol={protocol_name}")

            # Validate parameters
            await self._validate_session_parameters(parameters)

            # Ensure we're in the correct workflow state for session creation
            if self.workflow_state_machine.current_state not in [
                WorkflowState.STARTUP,
                WorkflowState.SETUP_READY,
                WorkflowState.ANALYSIS_READY
            ]:
                raise SessionManagementError(
                    f"Cannot create session in current workflow state: {self.workflow_state_machine.current_state}"
                )

            # Create session through repository
            session = await self.experiment_repository.create_session(
                session_type=session_type,
                parameters=parameters,
                protocol_name=protocol_name,
                subject_id=subject_id,
                experimenter=experimenter,
                notes=notes,
                session_id=session_id
            )

            # Create corresponding data storage
            await self._initialize_session_storage(session)

            # Set as current session
            self._current_session = session

            logger.info(f"Session created successfully: {session.session_id}")
            return session

        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise SessionManagementError(f"Session creation failed: {str(e)}")

    async def start_session(self, session_id: str) -> bool:
        """
        Start an experimental session

        Args:
            session_id: Session identifier

        Returns:
            True if session started successfully

        Raises:
            SessionManagementError: If session start fails
        """
        try:
            logger.info(f"Starting session: {session_id}")

            # Validate session exists and is in correct state
            session = await self.experiment_repository.get_session(session_id)
            if not session:
                raise SessionManagementError(f"Session not found: {session_id}")

            if session.status != SessionStatus.CREATED:
                raise SessionManagementError(
                    f"Cannot start session in status: {session.status}"
                )

            # Start session through repository
            success = await self.experiment_repository.start_session(session_id)

            if success:
                # Update current session reference
                self._current_session = session

                # Update workflow state if appropriate
                if self.workflow_state_machine.current_state == WorkflowState.SETUP_READY:
                    self.workflow_state_machine.transition_to(WorkflowState.SETUP)

                logger.info(f"Session started successfully: {session_id}")
            else:
                raise SessionManagementError("Repository failed to start session")

            return success

        except Exception as e:
            logger.error(f"Failed to start session {session_id}: {e}")
            raise SessionManagementError(f"Session start failed: {str(e)}")

    async def pause_session(self, session_id: str) -> bool:
        """
        Pause an active session

        Args:
            session_id: Session identifier

        Returns:
            True if session paused successfully
        """
        try:
            logger.info(f"Pausing session: {session_id}")

            success = await self.experiment_repository.pause_session(session_id)

            if success:
                logger.info(f"Session paused successfully: {session_id}")
            else:
                raise SessionManagementError("Repository failed to pause session")

            return success

        except Exception as e:
            logger.error(f"Failed to pause session {session_id}: {e}")
            raise SessionManagementError(f"Session pause failed: {str(e)}")

    async def resume_session(self, session_id: str) -> bool:
        """
        Resume a paused session

        Args:
            session_id: Session identifier

        Returns:
            True if session resumed successfully
        """
        try:
            logger.info(f"Resuming session: {session_id}")

            success = await self.experiment_repository.resume_session(session_id)

            if success:
                logger.info(f"Session resumed successfully: {session_id}")
            else:
                raise SessionManagementError("Repository failed to resume session")

            return success

        except Exception as e:
            logger.error(f"Failed to resume session {session_id}: {e}")
            raise SessionManagementError(f"Session resume failed: {str(e)}")

    async def complete_session(self, session_id: str, success: bool = True) -> bool:
        """
        Complete an experimental session

        Args:
            session_id: Session identifier
            success: Whether session completed successfully

        Returns:
            True if session completed successfully
        """
        try:
            logger.info(f"Completing session: {session_id} (success={success})")

            completed = await self.experiment_repository.complete_session(session_id, success)

            if completed:
                # Clear current session if this was the active one
                if self._current_session and self._current_session.session_id == session_id:
                    self._current_session = None

                # Update workflow state
                if success:
                    self.workflow_state_machine.transition_to(WorkflowState.ANALYSIS_READY)
                else:
                    self.workflow_state_machine.transition_to(WorkflowState.ERROR)

                logger.info(f"Session completed successfully: {session_id}")
            else:
                raise SessionManagementError("Repository failed to complete session")

            return completed

        except Exception as e:
            logger.error(f"Failed to complete session {session_id}: {e}")
            raise SessionManagementError(f"Session completion failed: {str(e)}")

    async def get_current_session(self) -> Optional[ExperimentSessionInterface]:
        """
        Get the currently active session

        Returns:
            Current session interface or None if no active session
        """
        return self._current_session

    async def get_session(self, session_id: str) -> Optional[ExperimentSessionInterface]:
        """
        Get session by ID

        Args:
            session_id: Session identifier

        Returns:
            Session interface or None if not found
        """
        try:
            return await self.experiment_repository.get_session(session_id)
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None

    async def list_sessions(
        self,
        session_type: Optional[SessionType] = None,
        status: Optional[SessionStatus] = None,
        limit: int = 100
    ) -> List[ExperimentSessionInterface]:
        """
        List sessions with optional filtering

        Args:
            session_type: Filter by session type (optional)
            status: Filter by session status (optional)
            limit: Maximum number of sessions to return

        Returns:
            List of session interfaces
        """
        try:
            return await self.experiment_repository.list_sessions(
                session_type=session_type,
                status=status,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []

    async def validate_session_integrity(self, session_id: str) -> Dict[str, Any]:
        """
        Validate session integrity and consistency

        Args:
            session_id: Session identifier

        Returns:
            Validation results dictionary
        """
        try:
            logger.info(f"Validating session integrity: {session_id}")

            session = await self.experiment_repository.get_session(session_id)
            if not session:
                return {
                    "valid": False,
                    "errors": ["Session not found"],
                    "warnings": []
                }

            validation_results = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "session_info": {
                    "session_id": session.session_id,
                    "status": session.status.value,
                    "parameters_hash": session.parameters.generation_hash
                }
            }

            # Validate parameter consistency
            try:
                await self._validate_session_parameters(session.parameters)
            except SessionValidationError as e:
                validation_results["errors"].append(f"Parameter validation failed: {str(e)}")
                validation_results["valid"] = False

            # Check data storage consistency
            try:
                # Verify data repository has session data
                sessions = await self.data_repository.list_sessions()
                if session_id not in sessions:
                    validation_results["warnings"].append("No data storage found for session")
            except Exception as e:
                validation_results["warnings"].append(f"Could not verify data storage: {str(e)}")

            logger.info(f"Session validation completed: {session_id} (valid={validation_results['valid']})")
            return validation_results

        except Exception as e:
            logger.error(f"Session validation failed for {session_id}: {e}")
            return {
                "valid": False,
                "errors": [f"Validation process failed: {str(e)}"],
                "warnings": []
            }

    async def _validate_session_parameters(self, parameters: CombinedParameters) -> None:
        """
        Validate session parameters

        Args:
            parameters: Combined parameters to validate

        Raises:
            SessionValidationError: If parameters are invalid
        """
        try:
            # Validate parameter structure
            if not parameters.generation_hash:
                raise SessionValidationError("Missing generation hash")

            if not parameters.combined_hash:
                raise SessionValidationError("Missing combined hash")

            # Validate parameter source
            if parameters.parameter_source not in [source.value for source in ParameterSource]:
                raise SessionValidationError(f"Invalid parameter source: {parameters.parameter_source}")

            # Additional validation can be added here
            logger.debug(f"Parameters validated successfully: {parameters.generation_hash[:8]}")

        except Exception as e:
            raise SessionValidationError(f"Parameter validation failed: {str(e)}")

    async def _initialize_session_storage(self, session: ExperimentSessionInterface) -> None:
        """
        Initialize data storage for session

        Args:
            session: Session interface

        Raises:
            SessionManagementError: If storage initialization fails
        """
        try:
            logger.debug(f"Initializing storage for session: {session.session_id}")

            # This will be called when the first dataset is created
            # For now, we just log the intent
            logger.debug(f"Storage initialization completed for session: {session.session_id}")

        except Exception as e:
            raise SessionManagementError(f"Storage initialization failed: {str(e)}")

    def get_session_summary(self) -> Dict[str, Any]:
        """
        Get summary of current session management state

        Returns:
            Summary dictionary
        """
        return {
            "current_session": self._current_session.session_id if self._current_session else None,
            "workflow_state": self.workflow_state_machine.current_state.value,
            "session_management_ready": True
        }