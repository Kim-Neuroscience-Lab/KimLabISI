"""
Data recorder for ISI acquisition sessions.
Saves camera frames, stimulus events, and metadata in format compatible with isi_analysis.py
"""

import os
import json
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import h5py

from .logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class StimulusEvent:
    """Single stimulus event record."""
    timestamp_us: int
    frame_id: int
    frame_index: int
    direction: str
    angle_degrees: float


@dataclass
class CameraFrame:
    """Single camera frame record."""
    timestamp_us: int
    frame_index: int
    frame_data: np.ndarray  # Will be saved to HDF5, not JSON


class AcquisitionRecorder:
    """Records acquisition data to disk for later analysis and playback."""

    def __init__(self, session_path: str, metadata: Dict[str, Any]):
        """
        Initialize recorder for a new acquisition session.

        Args:
            session_path: Directory where session data will be saved
            metadata: Session metadata (parameters, directions, etc.)
        """
        self.session_path = Path(session_path)
        self.session_path.mkdir(parents=True, exist_ok=True)

        self.metadata = metadata

        # Add timestamp source information for data provenance
        if "timestamp_info" not in self.metadata:
            self.metadata["timestamp_info"] = {
                "camera_timestamp_source": "unknown",
                "stimulus_timestamp_source": "vsync_from_frontend",
                "note": "Timestamp source determines data accuracy for scientific analysis"
            }

        self.is_recording = False

        # Data buffers per direction
        self.stimulus_events: Dict[str, List[StimulusEvent]] = {}
        self.camera_frames: Dict[str, List[CameraFrame]] = {}
        self.current_direction: Optional[str] = None

        # Anatomical reference image (captured before acquisition)
        self.anatomical_image: Optional[np.ndarray] = None

        logger.info(f"Acquisition recorder initialized: {self.session_path}")

    def start_recording(self, direction: str) -> None:
        """Start recording for a specific direction."""
        self.current_direction = direction
        self.is_recording = True

        # Initialize buffers for this direction if needed
        if direction not in self.stimulus_events:
            self.stimulus_events[direction] = []
        if direction not in self.camera_frames:
            self.camera_frames[direction] = []

        logger.info(f"Started recording for direction: {direction}")

    def stop_recording(self) -> None:
        """Stop recording current direction."""
        if self.current_direction:
            logger.info(
                f"Stopped recording for direction: {self.current_direction} "
                f"({len(self.stimulus_events.get(self.current_direction, []))} stimulus events, "
                f"{len(self.camera_frames.get(self.current_direction, []))} camera frames)"
            )
        self.is_recording = False
        self.current_direction = None

    def record_stimulus_event(
        self,
        timestamp_us: int,
        frame_id: int,
        frame_index: int,
        direction: str,
        angle_degrees: float,
    ) -> None:
        """Record a stimulus presentation event."""
        if not self.is_recording or direction != self.current_direction:
            return

        event = StimulusEvent(
            timestamp_us=timestamp_us,
            frame_id=frame_id,
            frame_index=frame_index,
            direction=direction,
            angle_degrees=angle_degrees,
        )

        self.stimulus_events[direction].append(event)

    def record_camera_frame(
        self,
        timestamp_us: int,
        frame_index: int,
        frame_data: np.ndarray,
        direction: Optional[str] = None,
    ) -> None:
        """Record a camera frame."""
        if not self.is_recording:
            return

        target_direction = direction or self.current_direction
        if not target_direction:
            return

        frame = CameraFrame(
            timestamp_us=timestamp_us,
            frame_index=frame_index,
            frame_data=frame_data.copy(),  # Copy to avoid reference issues
        )

        self.camera_frames[target_direction].append(frame)

    def set_anatomical_image(self, frame: np.ndarray) -> None:
        """
        Store anatomical reference frame.

        This should be called before starting acquisition to capture the baseline
        anatomical image that will be used for overlaying analysis results.

        Args:
            frame: Camera frame to use as anatomical reference
        """
        self.anatomical_image = frame.copy()  # Copy to avoid reference issues
        logger.info(f"Anatomical image captured: {frame.shape}, dtype={frame.dtype}")

    def save_session(self) -> None:
        """Save all recorded data to disk."""
        logger.info(f"Saving session data to {self.session_path}")

        try:
            # Save metadata
            metadata_path = self.session_path / "metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(self.metadata, f, indent=2)
            logger.info(f"  Saved metadata: {metadata_path}")

            # Save data for each direction
            for direction in self.stimulus_events.keys():
                self._save_direction_data(direction)

            # Save anatomical image if available
            if self.anatomical_image is not None:
                anatomical_path = self.session_path / "anatomical.npy"
                np.save(anatomical_path, self.anatomical_image)
                logger.info(f"  Saved anatomical image: {anatomical_path} ({self.anatomical_image.shape})")
            else:
                logger.warning("  No anatomical image captured for this session")

            logger.info("Session data saved successfully!")

        except Exception as e:
            logger.error(f"Failed to save session data: {e}", exc_info=True)
            raise

    def _save_direction_data(self, direction: str) -> None:
        """Save data for a specific direction."""
        logger.info(f"  Saving {direction} data...")

        # Save stimulus events as JSON
        events_path = self.session_path / f"{direction}_events.json"
        events_data = [
            {
                "timestamp": event.timestamp_us,
                "frame_id": event.frame_id,
                "frame_index": event.frame_index,
                "angle": event.angle_degrees,
            }
            for event in self.stimulus_events[direction]
        ]
        with open(events_path, 'w') as f:
            json.dump(events_data, f, indent=2)
        logger.info(f"    Saved {len(events_data)} stimulus events")

        # Save stimulus angles as HDF5
        stimulus_path = self.session_path / f"{direction}_stimulus.h5"
        angles = np.array([event.angle_degrees for event in self.stimulus_events[direction]])
        with h5py.File(stimulus_path, 'w') as f:
            f.create_dataset('angles', data=angles)
        logger.info(f"    Saved stimulus angles: {len(angles)} frames")

        # Save camera frames as HDF5 (if any were recorded)
        if direction in self.camera_frames and self.camera_frames[direction]:
            camera_path = self.session_path / f"{direction}_camera.h5"

            frames_list = self.camera_frames[direction]
            frames_array = np.stack([f.frame_data for f in frames_list])
            timestamps_array = np.array([f.timestamp_us for f in frames_list])

            with h5py.File(camera_path, 'w') as f:
                f.create_dataset(
                    'frames',
                    data=frames_array,
                    compression='gzip',
                    compression_opts=4
                )
                f.create_dataset('timestamps', data=timestamps_array)

            logger.info(
                f"    Saved camera data: {frames_array.shape} "
                f"({frames_array.nbytes / 1024 / 1024:.1f} MB)"
            )

    def get_session_info(self) -> Dict[str, Any]:
        """Get information about the current recording session."""
        return {
            "session_path": str(self.session_path),
            "is_recording": self.is_recording,
            "current_direction": self.current_direction,
            "directions_recorded": list(self.stimulus_events.keys()),
            "stimulus_events_count": {
                direction: len(events)
                for direction, events in self.stimulus_events.items()
            },
            "camera_frames_count": {
                direction: len(frames)
                for direction, frames in self.camera_frames.items()
            },
        }


def create_session_recorder(
    session_name: Optional[str] = None,
    base_path: str = "data/sessions",
    metadata: Optional[Dict[str, Any]] = None,
) -> AcquisitionRecorder:
    """
    Create a new acquisition recorder for a session.

    Args:
        session_name: Name of the session (auto-generated if None)
        base_path: Base directory for session data (relative to backend root)
        metadata: Session metadata

    Returns:
        Initialized AcquisitionRecorder
    """
    if session_name is None:
        session_name = f"session_{int(time.time())}"

    # Convert to absolute path relative to this file's location
    if not os.path.isabs(base_path):
        base_path = os.path.join(os.path.dirname(__file__), "..", "..", base_path)
        base_path = os.path.abspath(base_path)

    session_path = os.path.join(base_path, session_name)
    logger.info(f"💾 Creating session at: {session_path}")

    if metadata is None:
        metadata = {
            "session_name": session_name,
            "timestamp": time.time(),
        }

    return AcquisitionRecorder(session_path, metadata)
