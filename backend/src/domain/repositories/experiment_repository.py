"""
Domain Experiment Repository Interface

Abstract interface for experiment session management following clean architecture.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum

from ..value_objects.parameters import CombinedParameters


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


class ExperimentSessionInterface(ABC):
    """Abstract interface for experiment session entity"""

    @property
    @abstractmethod
    def session_id(self) -> str:
        """Session identifier"""
        pass

    @property
    @abstractmethod
    def status(self) -> SessionStatus:
        """Current session status"""
        pass

    @property
    @abstractmethod
    def parameters(self) -> CombinedParameters:
        """Session parameters"""
        pass

    @abstractmethod
    def update_activity(self) -> None:
        """Update last activity timestamp"""
        pass

    @abstractmethod
    def add_warning(self, warning: str) -> None:
        """Add a warning to the session"""
        pass

    @abstractmethod
    def record_error(self) -> None:
        """Record an error occurrence"""
        pass


class ExperimentRepositoryInterface(ABC):
    """Abstract interface for experiment session management"""

    @abstractmethod
    async def create_session(self,
                           session_type: SessionType,
                           parameters: CombinedParameters,
                           protocol_name: str = "Unknown Protocol",
                           subject_id: Optional[str] = None,
                           experimenter: Optional[str] = None,
                           notes: Optional[str] = None,
                           session_id: Optional[str] = None) -> ExperimentSessionInterface:
        """Create a new experimental session"""
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[ExperimentSessionInterface]:
        """Get session by ID"""
        pass

    @abstractmethod
    async def start_session(self, session_id: str) -> bool:
        """Start an experimental session"""
        pass

    @abstractmethod
    async def pause_session(self, session_id: str) -> bool:
        """Pause an active session"""
        pass

    @abstractmethod
    async def resume_session(self, session_id: str) -> bool:
        """Resume a paused session"""
        pass

    @abstractmethod
    async def complete_session(self, session_id: str, success: bool = True) -> bool:
        """Complete an experimental session"""
        pass

    @abstractmethod
    async def list_sessions(self,
                          session_type: Optional[SessionType] = None,
                          status: Optional[SessionStatus] = None,
                          limit: int = 100) -> List[ExperimentSessionInterface]:
        """List sessions with optional filtering"""
        pass