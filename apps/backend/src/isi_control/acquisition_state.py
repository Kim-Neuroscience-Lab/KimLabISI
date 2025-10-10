"""Centralized acquisition state coordinator."""

from enum import Enum
from typing import Optional
import threading

from .logging_utils import get_logger

logger = get_logger(__name__)


class AcquisitionMode(Enum):
    """System-wide acquisition modes."""

    IDLE = "idle"
    PREVIEW = "preview"
    RECORDING = "recording"
    PLAYBACK = "playback"


class AcquisitionStateCoordinator:
    """
    Coordinates state across acquisition, camera, and stimulus managers.

    Provides a single source of truth for the current system mode and ensures
    consistent state transitions across all components.
    """

    def __init__(self):
        self._mode = AcquisitionMode.IDLE
        self._lock = threading.Lock()
        self._camera_active = False
        self._stimulus_active = False
        self._acquisition_running = False
        self._current_session: Optional[str] = None

    @property
    def mode(self) -> AcquisitionMode:
        """Get the current acquisition mode."""
        with self._lock:
            return self._mode

    @property
    def is_idle(self) -> bool:
        """Check if system is idle."""
        with self._lock:
            return self._mode == AcquisitionMode.IDLE

    @property
    def is_preview(self) -> bool:
        """Check if system is in preview mode."""
        with self._lock:
            return self._mode == AcquisitionMode.PREVIEW

    @property
    def is_recording(self) -> bool:
        """Check if system is recording."""
        with self._lock:
            return self._mode == AcquisitionMode.RECORDING

    @property
    def is_playback(self) -> bool:
        """Check if system is in playback mode."""
        with self._lock:
            return self._mode == AcquisitionMode.PLAYBACK

    @property
    def camera_active(self) -> bool:
        """Check if camera is currently active."""
        with self._lock:
            return self._camera_active

    @property
    def stimulus_active(self) -> bool:
        """Check if stimulus is currently active."""
        with self._lock:
            return self._stimulus_active

    @property
    def acquisition_running(self) -> bool:
        """Check if acquisition sequence is running."""
        with self._lock:
            return self._acquisition_running

    @property
    def current_session(self) -> Optional[str]:
        """Get the current session name."""
        with self._lock:
            return self._current_session

    def transition_to_preview(self) -> bool:
        """
        Transition to preview mode.

        Returns:
            True if transition was successful
        """
        with self._lock:
            if self._mode == AcquisitionMode.RECORDING:
                logger.warning("Cannot transition to preview while recording")
                return False

            logger.info(f"State transition: {self._mode.value} → preview")
            self._mode = AcquisitionMode.PREVIEW
            self._acquisition_running = False
            return True

    def transition_to_recording(self, session_name: Optional[str] = None) -> bool:
        """
        Transition to recording mode.

        Args:
            session_name: Optional name for the recording session

        Returns:
            True if transition was successful
        """
        with self._lock:
            logger.info(f"State transition: {self._mode.value} → recording")
            self._mode = AcquisitionMode.RECORDING
            self._acquisition_running = True
            self._current_session = session_name
            return True

    def transition_to_playback(self) -> bool:
        """
        Transition to playback mode.

        Returns:
            True if transition was successful
        """
        with self._lock:
            if self._mode == AcquisitionMode.RECORDING:
                logger.warning("Cannot transition to playback while recording")
                return False

            logger.info(f"State transition: {self._mode.value} → playback")
            self._mode = AcquisitionMode.PLAYBACK
            self._acquisition_running = False
            return True

    def transition_to_idle(self) -> bool:
        """
        Transition to idle mode.

        Returns:
            True if transition was successful
        """
        with self._lock:
            logger.info(f"State transition: {self._mode.value} → idle")
            self._mode = AcquisitionMode.IDLE
            self._acquisition_running = False
            self._camera_active = False
            self._stimulus_active = False
            self._current_session = None
            return True

    def set_camera_active(self, active: bool) -> None:
        """Update camera active state."""
        with self._lock:
            self._camera_active = active
            logger.debug(f"Camera active: {active}")

    def set_stimulus_active(self, active: bool) -> None:
        """Update stimulus active state."""
        with self._lock:
            self._stimulus_active = active
            logger.debug(f"Stimulus active: {active}")

    def set_acquisition_running(self, running: bool) -> None:
        """Update acquisition running state."""
        with self._lock:
            self._acquisition_running = running
            logger.debug(f"Acquisition running: {running}")

    def get_state_summary(self) -> dict:
        """
        Get a summary of all state flags.

        Returns:
            Dictionary with current state information
        """
        with self._lock:
            return {
                "mode": self._mode.value,
                "camera_active": self._camera_active,
                "stimulus_active": self._stimulus_active,
                "acquisition_running": self._acquisition_running,
                "current_session": self._current_session,
            }
