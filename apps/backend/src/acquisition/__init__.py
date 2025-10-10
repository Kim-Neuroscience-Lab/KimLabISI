"""Acquisition system for ISI Macroscope.

This package provides acquisition orchestration, state management, and data recording.
Uses constructor injection pattern - all dependencies passed explicitly.

Modules:
    - sync_tracker: Timestamp synchronization tracking
    - state: Acquisition state coordination
    - modes: Preview/Record/Playback mode controllers
    - camera_stimulus: Camera-triggered stimulus generation
    - recorder: Data recording and session management
    - manager: Main acquisition orchestration
"""

from .sync_tracker import TimestampSynchronizationTracker
from .state import AcquisitionStateCoordinator, AcquisitionMode
from .modes import (
    AcquisitionModeController,
    PreviewModeController,
    RecordModeController,
    PlaybackModeController,
)
from .camera_stimulus import CameraTriggeredStimulusController
from .recorder import (
    AcquisitionRecorder,
    StimulusEvent,
    CameraFrame,
    create_session_recorder,
)
from .manager import AcquisitionManager, AcquisitionPhase

__all__ = [
    # Synchronization
    "TimestampSynchronizationTracker",
    # State
    "AcquisitionStateCoordinator",
    "AcquisitionMode",
    # Mode controllers
    "AcquisitionModeController",
    "PreviewModeController",
    "RecordModeController",
    "PlaybackModeController",
    # Camera-triggered stimulus
    "CameraTriggeredStimulusController",
    # Recording
    "AcquisitionRecorder",
    "StimulusEvent",
    "CameraFrame",
    "create_session_recorder",
    # Manager
    "AcquisitionManager",
    "AcquisitionPhase",
]
