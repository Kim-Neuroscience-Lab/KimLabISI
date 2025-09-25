"""
Session Repository - Experiment Session Management

This module provides high-level session management for experimental workflows,
including session state tracking, metadata management, and integration with
the HDF5 data storage system.

Key Features:
- Session lifecycle management (create, start, pause, complete)
- Session state persistence and recovery
- Integration with parameter system and data storage
- Session validation and integrity checking
- Experiment protocol tracking
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from datetime import datetime, timedelta
from enum import Enum
import uuid

from domain.value_objects.parameters import CombinedParameters, ParameterSource
from domain.entities.parameters import ParameterManager
from .hdf5_repository import HDF5Repository, HDF5SessionManager

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """Session status enumeration"""
    CREATED = "created"
    PREPARING = "preparing"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class SessionType(Enum):
    """Session type enumeration"""
    RETINOTOPY = "retinotopy"
    FUNCTIONAL_IMAGING = "functional_imaging"
    STIMULUS_RESPONSE = "stimulus_response"
    CALIBRATION = "calibration"
    DEVELOPMENT = "development"


class ExperimentSession:
    """
    Represents an experimental session with all associated metadata and state
    """

    def __init__(self,
                 session_id: str,
                 session_type: SessionType,
                 parameters: CombinedParameters,
                 protocol_name: str = "Unknown Protocol",
                 subject_id: Optional[str] = None,
                 experimenter: Optional[str] = None,
                 notes: Optional[str] = None):
        """
        Initialize experiment session

        Args:
            session_id: Unique session identifier
            session_type: Type of experimental session
            parameters: Combined parameters for the session
            protocol_name: Name of the experimental protocol
            subject_id: Subject identifier (for animal experiments)
            experimenter: Name of the experimenter
            notes: Additional notes about the session
        """
        self.session_id = session_id
        self.session_type = session_type
        self.parameters = parameters
        self.protocol_name = protocol_name
        self.subject_id = subject_id
        self.experimenter = experimenter
        self.notes = notes

        # Session state
        self.status = SessionStatus.CREATED
        self.created_timestamp = datetime.now()
        self.started_timestamp: Optional[datetime] = None
        self.completed_timestamp: Optional[datetime] = None
        self.last_activity_timestamp = self.created_timestamp

        # Session metrics
        self.frames_acquired = 0
        self.total_duration_sec = 0.0
        self.error_count = 0
        self.warnings: List[str] = []

        # Data tracking
        self.datasets: List[str] = []
        self.analysis_results: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for serialization"""
        return {
            'session_id': self.session_id,
            'session_type': self.session_type.value,
            'protocol_name': self.protocol_name,
            'subject_id': self.subject_id,
            'experimenter': self.experimenter,
            'notes': self.notes,
            'status': self.status.value,
            'created_timestamp': self.created_timestamp.isoformat(),
            'started_timestamp': self.started_timestamp.isoformat() if self.started_timestamp else None,
            'completed_timestamp': self.completed_timestamp.isoformat() if self.completed_timestamp else None,
            'last_activity_timestamp': self.last_activity_timestamp.isoformat(),
            'frames_acquired': self.frames_acquired,
            'total_duration_sec': self.total_duration_sec,
            'error_count': self.error_count,
            'warnings': self.warnings,
            'datasets': self.datasets,
            'analysis_results': self.analysis_results,
            'parameters': self.parameters.model_dump(),
            'generation_hash': self.parameters.generation_hash,
            'combined_hash': self.parameters.combined_hash,
            'parameter_source': self.parameters.parameter_source if isinstance(self.parameters.parameter_source, str) else self.parameters.parameter_source.value
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExperimentSession':
        """Create session from dictionary"""
        # Reconstruct parameters
        param_dict = data['parameters']
        parameters = CombinedParameters(**param_dict)

        # Create session
        session = cls(
            session_id=data['session_id'],
            session_type=SessionType(data['session_type']),
            parameters=parameters,
            protocol_name=data['protocol_name'],
            subject_id=data['subject_id'],
            experimenter=data['experimenter'],
            notes=data['notes']
        )

        # Restore state
        session.status = SessionStatus(data['status'])
        session.created_timestamp = datetime.fromisoformat(data['created_timestamp'])
        session.started_timestamp = datetime.fromisoformat(data['started_timestamp']) if data['started_timestamp'] else None
        session.completed_timestamp = datetime.fromisoformat(data['completed_timestamp']) if data['completed_timestamp'] else None
        session.last_activity_timestamp = datetime.fromisoformat(data['last_activity_timestamp'])
        session.frames_acquired = data['frames_acquired']
        session.total_duration_sec = data['total_duration_sec']
        session.error_count = data['error_count']
        session.warnings = data['warnings']
        session.datasets = data['datasets']
        session.analysis_results = data['analysis_results']

        return session

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity_timestamp = datetime.now()

    def add_warning(self, warning: str):
        """Add a warning to the session"""
        self.warnings.append(f"{datetime.now().isoformat()}: {warning}")
        self.update_activity()

    def record_error(self):
        """Record an error occurrence"""
        self.error_count += 1
        self.update_activity()

    def add_dataset(self, dataset_name: str):
        """Add a dataset to the session"""
        if dataset_name not in self.datasets:
            self.datasets.append(dataset_name)
            self.update_activity()

    def add_analysis_result(self, analysis_name: str):
        """Add an analysis result to the session"""
        if analysis_name not in self.analysis_results:
            self.analysis_results.append(analysis_name)
            self.update_activity()


class SessionRepository:
    """
    Repository for managing experimental sessions

    Provides high-level interface for session management including creation,
    state tracking, persistence, and integration with data storage.
    """

    def __init__(self, storage_directory: Path, hdf5_repository: Optional[HDF5Repository] = None):
        """
        Initialize session repository

        Args:
            storage_directory: Directory for session metadata storage
            hdf5_repository: Optional HDF5 repository for data storage integration
        """
        self.storage_directory = Path(storage_directory)
        self.storage_directory.mkdir(parents=True, exist_ok=True)

        self.hdf5_repository = hdf5_repository
        self.hdf5_session_manager = HDF5SessionManager(hdf5_repository) if hdf5_repository else None

        # In-memory session cache
        self._active_sessions: Dict[str, ExperimentSession] = {}
        self._session_metadata_cache: Dict[str, Dict[str, Any]] = {}

        logger.info(f"SessionRepository initialized: {storage_directory}")

    async def create_session(self,
                           session_type: SessionType,
                           parameters: CombinedParameters,
                           protocol_name: str = "Unknown Protocol",
                           subject_id: Optional[str] = None,
                           experimenter: Optional[str] = None,
                           notes: Optional[str] = None,
                           session_id: Optional[str] = None) -> ExperimentSession:
        """
        Create a new experimental session

        Args:
            session_type: Type of experimental session
            parameters: Combined parameters for the session
            protocol_name: Name of the experimental protocol
            subject_id: Subject identifier
            experimenter: Name of the experimenter
            notes: Additional notes
            session_id: Optional custom session ID

        Returns:
            Created ExperimentSession object
        """
        # Generate session ID if not provided
        if session_id is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = f"{session_type.value}_{timestamp}_{uuid.uuid4().hex[:8]}"

        # Create session object
        session = ExperimentSession(
            session_id=session_id,
            session_type=session_type,
            parameters=parameters,
            protocol_name=protocol_name,
            subject_id=subject_id,
            experimenter=experimenter,
            notes=notes
        )

        # Store in cache
        self._active_sessions[session_id] = session

        # Persist session metadata
        await self._save_session_metadata(session)

        # Create HDF5 session if repository available
        if self.hdf5_session_manager:
            await self.hdf5_session_manager.create_session(
                session_id=session_id,
                parameters=parameters,
                metadata={
                    'session_type': session_type.value,
                    'protocol_name': protocol_name,
                    'subject_id': subject_id,
                    'experimenter': experimenter,
                    'notes': notes
                }
            )

        logger.info(f"Created session '{session_id}' of type {session_type.value}")
        return session

    async def get_session(self, session_id: str) -> Optional[ExperimentSession]:
        """
        Get session by ID

        Args:
            session_id: Session identifier

        Returns:
            ExperimentSession object or None if not found
        """
        # Check cache first
        if session_id in self._active_sessions:
            return self._active_sessions[session_id]

        # Try to load from storage
        session = await self._load_session_metadata(session_id)
        if session:
            self._active_sessions[session_id] = session

        return session

    async def start_session(self, session_id: str) -> bool:
        """
        Start an experimental session

        Args:
            session_id: Session identifier

        Returns:
            True if session was started successfully
        """
        session = await self.get_session(session_id)
        if not session:
            logger.error(f"Session '{session_id}' not found")
            return False

        if session.status != SessionStatus.CREATED:
            logger.warning(f"Session '{session_id}' cannot be started (status: {session.status})")
            return False

        session.status = SessionStatus.ACTIVE
        session.started_timestamp = datetime.now()
        session.update_activity()

        await self._save_session_metadata(session)

        logger.info(f"Started session '{session_id}'")
        return True

    async def pause_session(self, session_id: str) -> bool:
        """
        Pause an active session

        Args:
            session_id: Session identifier

        Returns:
            True if session was paused successfully
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        if session.status != SessionStatus.ACTIVE:
            logger.warning(f"Session '{session_id}' cannot be paused (status: {session.status})")
            return False

        session.status = SessionStatus.PAUSED
        session.update_activity()

        # Update duration
        if session.started_timestamp:
            session.total_duration_sec += (datetime.now() - session.started_timestamp).total_seconds()

        await self._save_session_metadata(session)

        logger.info(f"Paused session '{session_id}'")
        return True

    async def resume_session(self, session_id: str) -> bool:
        """
        Resume a paused session

        Args:
            session_id: Session identifier

        Returns:
            True if session was resumed successfully
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        if session.status != SessionStatus.PAUSED:
            logger.warning(f"Session '{session_id}' cannot be resumed (status: {session.status})")
            return False

        session.status = SessionStatus.ACTIVE
        session.update_activity()

        await self._save_session_metadata(session)

        logger.info(f"Resumed session '{session_id}'")
        return True

    async def complete_session(self, session_id: str, success: bool = True) -> bool:
        """
        Complete an experimental session

        Args:
            session_id: Session identifier
            success: Whether the session completed successfully

        Returns:
            True if session was completed successfully
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        if session.status in (SessionStatus.COMPLETED, SessionStatus.CANCELLED):
            logger.warning(f"Session '{session_id}' already completed/cancelled")
            return False

        session.status = SessionStatus.COMPLETED if success else SessionStatus.ERROR
        session.completed_timestamp = datetime.now()
        session.update_activity()

        # Final duration calculation
        if session.started_timestamp:
            session.total_duration_sec += (session.completed_timestamp - session.started_timestamp).total_seconds()

        await self._save_session_metadata(session)

        # Close HDF5 session
        if self.hdf5_session_manager:
            await self.hdf5_session_manager.close_session(session_id)

        logger.info(f"Completed session '{session_id}' with status {session.status}")
        return True

    async def list_sessions(self,
                          session_type: Optional[SessionType] = None,
                          status: Optional[SessionStatus] = None,
                          limit: int = 100) -> List[ExperimentSession]:
        """
        List sessions with optional filtering

        Args:
            session_type: Filter by session type
            status: Filter by session status
            limit: Maximum number of sessions to return

        Returns:
            List of ExperimentSession objects
        """
        sessions = []

        # Get all session files
        session_files = list(self.storage_directory.glob("*.json"))
        session_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        for session_file in session_files[:limit]:
            try:
                session = await self._load_session_metadata(session_file.stem)
                if session:
                    # Apply filters
                    if session_type and session.session_type != session_type:
                        continue
                    if status and session.status != status:
                        continue

                    sessions.append(session)
            except Exception as e:
                logger.warning(f"Failed to load session {session_file.stem}: {e}")

        return sessions

    async def get_session_statistics(self) -> Dict[str, Any]:
        """
        Get overall session statistics

        Returns:
            Dictionary with session statistics
        """
        all_sessions = await self.list_sessions()

        stats = {
            'total_sessions': len(all_sessions),
            'by_type': {},
            'by_status': {},
            'total_frames_acquired': 0,
            'total_duration_hours': 0.0,
            'recent_sessions': 0  # Last 24 hours
        }

        recent_cutoff = datetime.now() - timedelta(hours=24)

        for session in all_sessions:
            # Count by type
            session_type = session.session_type.value
            stats['by_type'][session_type] = stats['by_type'].get(session_type, 0) + 1

            # Count by status
            status = session.status.value
            stats['by_status'][status] = stats['by_status'].get(status, 0) + 1

            # Aggregate metrics
            stats['total_frames_acquired'] += session.frames_acquired
            stats['total_duration_hours'] += session.total_duration_sec / 3600.0

            # Recent sessions
            if session.created_timestamp > recent_cutoff:
                stats['recent_sessions'] += 1

        return stats

    async def validate_session_integrity(self, session_id: str) -> Dict[str, Any]:
        """
        Validate session integrity including parameter consistency

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with validation results
        """
        validation_result = {
            'session_id': session_id,
            'valid': True,
            'issues': [],
            'warnings': []
        }

        session = await self.get_session(session_id)
        if not session:
            validation_result['valid'] = False
            validation_result['issues'].append("Session not found")
            return validation_result

        # Check parameter consistency with HDF5 data
        if self.hdf5_session_manager:
            try:
                param_valid = await self.hdf5_session_manager.validate_session_parameters(
                    session_id, session.parameters
                )
                if not param_valid:
                    validation_result['issues'].append("Parameter hash mismatch with HDF5 data")
                    validation_result['valid'] = False
            except Exception as e:
                validation_result['warnings'].append(f"Could not validate HDF5 parameters: {e}")

        # Check session state consistency
        if session.status == SessionStatus.ACTIVE and session.started_timestamp is None:
            validation_result['issues'].append("Active session missing start timestamp")
            validation_result['valid'] = False

        if session.status == SessionStatus.COMPLETED and session.completed_timestamp is None:
            validation_result['issues'].append("Completed session missing completion timestamp")
            validation_result['valid'] = False

        # Check for excessive warnings or errors
        if session.error_count > 10:
            validation_result['warnings'].append(f"High error count: {session.error_count}")

        if len(session.warnings) > 20:
            validation_result['warnings'].append(f"High warning count: {len(session.warnings)}")

        return validation_result

    async def _save_session_metadata(self, session: ExperimentSession) -> None:
        """Save session metadata to disk"""
        session_file = self.storage_directory / f"{session.session_id}.json"

        session_data = session.to_dict()

        def _write_file():
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)

        await asyncio.get_event_loop().run_in_executor(None, _write_file)

    async def _load_session_metadata(self, session_id: str) -> Optional[ExperimentSession]:
        """Load session metadata from disk"""
        session_file = self.storage_directory / f"{session_id}.json"

        if not session_file.exists():
            return None

        def _read_file():
            with open(session_file, 'r') as f:
                return json.load(f)

        try:
            session_data = await asyncio.get_event_loop().run_in_executor(None, _read_file)
            return ExperimentSession.from_dict(session_data)
        except Exception as e:
            logger.error(f"Failed to load session metadata for {session_id}: {e}")
            return None