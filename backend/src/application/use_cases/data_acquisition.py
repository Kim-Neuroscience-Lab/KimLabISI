"""
Data Acquisition Use Case - Core Workflow Functionality

This use case orchestrates the complete data acquisition workflow including
camera control, stimulus presentation, data storage, and real-time monitoring.

Key Responsibilities:
- Coordinate hardware components for synchronized acquisition
- Manage stimulus presentation timing
- Stream and store imaging data
- Monitor system performance and handle errors
- Integrate with session management and parameter system
"""

import asyncio
import logging
import numpy as np
from typing import Dict, Any, Optional, List, Callable, AsyncGenerator, Tuple
from datetime import datetime, timedelta
import time
from enum import Enum
from pydantic import BaseModel

from domain.value_objects.parameters import CombinedParameters
from domain.value_objects.workflow_state import WorkflowState, HardwareRequirement
from domain.repositories.data_repository import DataRepositoryInterface
from domain.repositories.experiment_repository import (
    ExperimentRepositoryInterface, ExperimentSessionInterface, SessionStatus, SessionType
)
from infrastructure.hardware.abstract.camera_interface import CameraInterface
from infrastructure.hardware.abstract.display_interface import DisplayInterface
from infrastructure.hardware.abstract.timing_interface import TimingInterface
from infrastructure.hardware.factory import HardwareFactory
from application.algorithms.pattern_generators import PatternGenerator
from .stimulus_generation import StimulusGenerationUseCase, StimulusSequence

logger = logging.getLogger(__name__)


class AcquisitionStatus(Enum):
    """Data acquisition status enumeration"""
    IDLE = "idle"
    PREPARING = "preparing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"
    COMPLETED = "completed"


class AcquisitionMode(Enum):
    """Data acquisition mode enumeration"""
    PREVIEW = "preview"          # Preview mode for setup
    STIMULUS_RESPONSE = "stimulus_response"  # Stimulus-evoked imaging
    SPONTANEOUS = "spontaneous"  # Spontaneous activity
    CALIBRATION = "calibration"  # System calibration


class AcquisitionMetrics(BaseModel):
    """Real-time acquisition metrics"""
    frames_acquired: int = 0
    frames_dropped: int = 0
    total_duration_sec: float = 0.0
    average_frame_rate: float = 0.0
    current_frame_rate: float = 0.0
    data_rate_mbps: float = 0.0
    buffer_usage_percent: float = 0.0
    errors: int = 0
    warnings: int = 0


class DataAcquisitionError(Exception):
    """Errors related to data acquisition"""
    pass


class DataAcquisitionUseCase:
    """
    Core data acquisition use case

    Orchestrates the complete workflow for acquiring imaging data including
    hardware coordination, stimulus presentation, and data storage.
    """

    def __init__(self,
                 hardware_factory: HardwareFactory,
                 data_repository: DataRepositoryInterface,
                 experiment_repository: ExperimentRepositoryInterface,
                 stimulus_use_case: StimulusGenerationUseCase):
        """
        Initialize data acquisition use case

        Args:
            hardware_factory: Factory for hardware interfaces
            data_repository: Data storage repository interface
            experiment_repository: Experiment session repository interface
            stimulus_use_case: Stimulus generation use case
        """
        self.hardware_factory = hardware_factory
        self.data_repository = data_repository
        self.experiment_repository = experiment_repository
        self.stimulus_use_case = stimulus_use_case

        # Hardware interfaces (initialized on setup)
        self.camera: Optional[CameraInterface] = None
        self.display: Optional[DisplayInterface] = None
        self.timing: Optional[TimingInterface] = None

        # Acquisition state
        self.status = AcquisitionStatus.IDLE
        self.current_session: Optional[ExperimentSessionInterface] = None
        self.current_parameters: Optional[CombinedParameters] = None
        self.current_stimulus_sequence: Optional[StimulusSequence] = None

        # Real-time metrics
        self.metrics = AcquisitionMetrics()
        self._start_time: Optional[float] = None
        self._last_frame_time: Optional[float] = None
        self._frame_times: List[float] = []

        # Event callbacks
        self._frame_callbacks: List[Callable[[np.ndarray, int], None]] = []
        self._status_callbacks: List[Callable[[AcquisitionStatus], None]] = []
        self._error_callbacks: List[Callable[[Exception], None]] = []

        logger.info("DataAcquisitionUseCase initialized")

    async def setup_hardware(self) -> bool:
        """
        Setup and initialize hardware interfaces

        Returns:
            True if hardware setup was successful
        """
        try:
            logger.info("Setting up hardware interfaces...")

            # Create hardware interfaces
            self.camera = self.hardware_factory.create_camera_interface()
            self.display = self.hardware_factory.create_display_interface()
            self.timing = self.hardware_factory.create_timing_interface()

            # Initialize hardware
            if not await self.camera.connect():
                raise DataAcquisitionError("Failed to connect to camera")

            if not await self.display.connect():
                raise DataAcquisitionError("Failed to connect to display")

            if not await self.timing.connect():
                raise DataAcquisitionError("Failed to connect to timing system")

            logger.info("Hardware setup completed successfully")
            return True

        except Exception as e:
            logger.error(f"Hardware setup failed: {e}")
            await self._handle_error(e)
            return False

    async def prepare_acquisition(self,
                                session_id: str,
                                mode: AcquisitionMode = AcquisitionMode.STIMULUS_RESPONSE,
                                preview_only: bool = False) -> bool:
        """
        Prepare for data acquisition

        Args:
            session_id: Session identifier
            mode: Acquisition mode
            preview_only: If True, only setup preview (no data storage)

        Returns:
            True if preparation was successful
        """
        try:
            self.status = AcquisitionStatus.PREPARING
            await self._notify_status_change()

            # Load session
            self.current_session = await self.experiment_repository.get_session(session_id)
            if not self.current_session:
                raise DataAcquisitionError(f"Session '{session_id}' not found")

            self.current_parameters = self.current_session.parameters

            # Validate session state
            if self.current_session.status not in (SessionStatus.CREATED, SessionStatus.PAUSED):
                raise DataAcquisitionError(f"Invalid session status: {self.current_session.status}")

            # Setup stimulus sequence if needed
            if mode in (AcquisitionMode.STIMULUS_RESPONSE, AcquisitionMode.CALIBRATION):
                await self._prepare_stimulus_sequence()

            # Configure camera
            await self._configure_camera()

            # Configure display
            if self.current_stimulus_sequence:
                await self._configure_display()

            # Setup data storage (unless preview only)
            if not preview_only:
                await self._prepare_data_storage()

            # Reset metrics
            self.metrics = AcquisitionMetrics()

            logger.info(f"Acquisition prepared for session {session_id} in {mode.value} mode")
            return True

        except Exception as e:
            logger.error(f"Failed to prepare acquisition: {e}")
            await self._handle_error(e)
            return False

    async def start_acquisition(self,
                              duration_sec: Optional[float] = None,
                              max_frames: Optional[int] = None) -> bool:
        """
        Start data acquisition

        Args:
            duration_sec: Maximum acquisition duration (None for unlimited)
            max_frames: Maximum number of frames (None for unlimited)

        Returns:
            True if acquisition started successfully
        """
        if self.status != AcquisitionStatus.PREPARING:
            raise DataAcquisitionError(f"Cannot start acquisition in status: {self.status}")

        try:
            # Start session if not already started
            if self.current_session.status == SessionStatus.CREATED:
                await self.experiment_repository.start_session(self.current_session.session_id)

            # Start hardware
            await self.camera.start_acquisition(self._get_camera_parameters())

            if self.current_stimulus_sequence and self.display:
                await self.display.start_presentation()

            # Initialize timing
            self._start_time = time.time()
            self._last_frame_time = self._start_time
            self._frame_times = []

            self.status = AcquisitionStatus.RUNNING
            await self._notify_status_change()

            logger.info(f"Started acquisition for session {self.current_session.session_id}")

            # Start acquisition loop
            await self._acquisition_loop(duration_sec, max_frames)

            return True

        except Exception as e:
            logger.error(f"Failed to start acquisition: {e}")
            await self._handle_error(e)
            return False

    async def pause_acquisition(self) -> bool:
        """
        Pause data acquisition

        Returns:
            True if acquisition was paused successfully
        """
        if self.status != AcquisitionStatus.RUNNING:
            logger.warning(f"Cannot pause acquisition in status: {self.status}")
            return False

        try:
            # Pause hardware
            await self.camera.stop_acquisition()
            if self.display:
                await self.display.stop_presentation()

            # Update session
            if self.current_session:
                await self.experiment_repository.pause_session(self.current_session.session_id)

            self.status = AcquisitionStatus.PAUSED
            await self._notify_status_change()

            logger.info("Acquisition paused")
            return True

        except Exception as e:
            logger.error(f"Failed to pause acquisition: {e}")
            await self._handle_error(e)
            return False

    async def resume_acquisition(self) -> bool:
        """
        Resume paused acquisition

        Returns:
            True if acquisition was resumed successfully
        """
        if self.status != AcquisitionStatus.PAUSED:
            logger.warning(f"Cannot resume acquisition in status: {self.status}")
            return False

        try:
            # Resume hardware
            await self.camera.start_acquisition(self._get_camera_parameters())
            if self.display:
                await self.display.start_presentation()

            # Update session
            if self.current_session:
                await self.experiment_repository.resume_session(self.current_session.session_id)

            self.status = AcquisitionStatus.RUNNING
            await self._notify_status_change()

            logger.info("Acquisition resumed")
            return True

        except Exception as e:
            logger.error(f"Failed to resume acquisition: {e}")
            await self._handle_error(e)
            return False

    async def stop_acquisition(self, success: bool = True) -> bool:
        """
        Stop data acquisition

        Args:
            success: Whether acquisition completed successfully

        Returns:
            True if acquisition was stopped successfully
        """
        if self.status in (AcquisitionStatus.IDLE, AcquisitionStatus.COMPLETED):
            return True

        try:
            self.status = AcquisitionStatus.STOPPING
            await self._notify_status_change()

            # Stop hardware
            if self.camera:
                await self.camera.stop_acquisition()
            if self.display:
                await self.display.stop_presentation()

            # Complete session
            if self.current_session:
                await self.experiment_repository.complete_session(
                    self.current_session.session_id, success
                )

            # Final metrics update
            if self._start_time:
                self.metrics.total_duration_sec = time.time() - self._start_time

            self.status = AcquisitionStatus.COMPLETED if success else AcquisitionStatus.ERROR
            await self._notify_status_change()

            logger.info(f"Acquisition stopped (success={success})")
            return True

        except Exception as e:
            logger.error(f"Failed to stop acquisition: {e}")
            await self._handle_error(e)
            return False

    async def get_live_preview(self) -> AsyncGenerator[np.ndarray, None]:
        """
        Get live preview frames (generator for streaming)

        Yields:
            Preview frames as numpy arrays
        """
        if not self.camera:
            raise DataAcquisitionError("Camera not initialized")

        # Start preview acquisition
        await self.camera.start_acquisition(self._get_preview_parameters())

        try:
            while True:
                frame_data = await self.camera.get_image()
                if frame_data is not None:
                    # Convert to numpy array (assuming raw bytes)
                    frame = np.frombuffer(frame_data, dtype=np.uint16)
                    # Reshape based on camera configuration
                    frame = frame.reshape(self._get_frame_shape())
                    yield frame
                else:
                    await asyncio.sleep(0.01)  # Brief pause if no frame available

        except asyncio.CancelledError:
            logger.info("Live preview cancelled")
        finally:
            await self.camera.stop_acquisition()

    def register_frame_callback(self, callback: Callable[[np.ndarray, int], None]) -> None:
        """Register callback for frame events"""
        self._frame_callbacks.append(callback)

    def register_status_callback(self, callback: Callable[[AcquisitionStatus], None]) -> None:
        """Register callback for status change events"""
        self._status_callbacks.append(callback)

    def register_error_callback(self, callback: Callable[[Exception], None]) -> None:
        """Register callback for error events"""
        self._error_callbacks.append(callback)

    def get_current_metrics(self) -> AcquisitionMetrics:
        """Get current acquisition metrics"""
        return self.metrics

    async def _acquisition_loop(self,
                               duration_sec: Optional[float] = None,
                               max_frames: Optional[int] = None) -> None:
        """Main acquisition loop"""
        frame_count = 0
        end_time = time.time() + duration_sec if duration_sec else None

        try:
            while self.status == AcquisitionStatus.RUNNING:
                # Check termination conditions
                if end_time and time.time() >= end_time:
                    logger.info("Acquisition duration reached")
                    break

                if max_frames and frame_count >= max_frames:
                    logger.info(f"Maximum frame count reached: {max_frames}")
                    break

                # Get frame from camera
                frame_data = await self.camera.get_image()
                if frame_data is None:
                    await asyncio.sleep(0.001)  # Brief pause if no frame
                    continue

                # Process frame
                current_time = time.time()
                frame = await self._process_frame(frame_data, frame_count, current_time)

                # Update stimulus if needed
                if self.current_stimulus_sequence and self.display:
                    await self._update_stimulus_display(frame_count)

                # Store frame
                await self._store_frame(frame, frame_count)

                # Update metrics
                self._update_metrics(frame, current_time)

                # Notify callbacks
                await self._notify_frame_callbacks(frame, frame_count)

                frame_count += 1

        except Exception as e:
            logger.error(f"Error in acquisition loop: {e}")
            await self._handle_error(e)
        finally:
            await self.stop_acquisition(success=(self.status != AcquisitionStatus.ERROR))

    async def _process_frame(self, frame_data: bytes, frame_index: int, timestamp: float) -> np.ndarray:
        """Process raw frame data"""
        # Convert bytes to numpy array
        frame = np.frombuffer(frame_data, dtype=np.uint16)
        frame = frame.reshape(self._get_frame_shape())

        # Apply any preprocessing here
        # (e.g., dark frame subtraction, flat field correction)

        return frame

    async def _store_frame(self, frame: np.ndarray, frame_index: int) -> None:
        """Store frame to HDF5 repository"""
        if self.current_session and self.data_repository:
            try:
                await self.data_repository.write_frames(
                    session_id=self.current_session.session_id,
                    dataset_name="imaging_data",
                    frames=frame,
                    frame_indices=frame_index
                )
            except Exception as e:
                logger.error(f"Failed to store frame {frame_index}: {e}")
                self.metrics.errors += 1

    async def _update_stimulus_display(self, frame_index: int) -> None:
        """Update stimulus display for current frame"""
        if self.current_stimulus_sequence and self.display:
            try:
                stimulus_frame = self.current_stimulus_sequence.get_frame(frame_index)
                await self.display.update_frame(stimulus_frame)
            except Exception as e:
                logger.error(f"Failed to update stimulus display: {e}")
                self.metrics.warnings += 1

    def _update_metrics(self, frame: np.ndarray, current_time: float) -> None:
        """Update real-time acquisition metrics"""
        self.metrics.frames_acquired += 1

        # Frame rate calculation
        if self._last_frame_time:
            frame_interval = current_time - self._last_frame_time
            if frame_interval > 0:
                self.metrics.current_frame_rate = 1.0 / frame_interval

        self._last_frame_time = current_time
        self._frame_times.append(current_time)

        # Keep only last 100 frame times for average calculation
        if len(self._frame_times) > 100:
            self._frame_times = self._frame_times[-100:]

        # Average frame rate
        if len(self._frame_times) > 1:
            total_time = self._frame_times[-1] - self._frame_times[0]
            if total_time > 0:
                self.metrics.average_frame_rate = (len(self._frame_times) - 1) / total_time

        # Data rate calculation
        frame_size_bytes = frame.nbytes
        self.metrics.data_rate_mbps = (frame_size_bytes * self.metrics.current_frame_rate) / (1024 * 1024)

        # Update session metrics
        if self.current_session:
            self.current_session.frames_acquired = self.metrics.frames_acquired
            self.current_session.update_activity()

    async def _prepare_stimulus_sequence(self) -> None:
        """Prepare stimulus sequence for acquisition"""
        # This would typically create a protocol based on session parameters
        # For now, we'll create a simple horizontal bar protocol
        from .stimulus_generation import create_horizontal_bar_protocol_from_parameters

        protocol = create_horizontal_bar_protocol_from_parameters()
        self.current_stimulus_sequence = await self.stimulus_use_case.create_stimulus_sequence(
            protocol,
            parameter_set_id="marshel_2011_defaults"
        )

    async def _configure_camera(self) -> None:
        """Configure camera based on acquisition parameters"""
        if not self.camera or not self.current_parameters:
            return

        # Configure camera settings based on parameters
        # This would set frame rate, exposure, gain, etc.
        pass

    async def _configure_display(self) -> None:
        """Configure display for stimulus presentation"""
        if not self.display or not self.current_parameters:
            return

        # Configure display settings
        pass

    async def _prepare_data_storage(self) -> None:
        """Prepare HDF5 storage for acquisition"""
        if not self.current_session or not self.data_repository:
            return

        # Calculate expected frame shape and count
        frame_shape = self._get_frame_shape()
        expected_frames = self._estimate_frame_count()

        # Create imaging dataset
        await self.data_repository.create_dataset(
            session_id=self.current_session.session_id,
            dataset_name="imaging_data",
            shape=(expected_frames,) + frame_shape,
            dtype=np.uint16,
            parameters=self.current_parameters,
            metadata={
                'acquisition_mode': 'stimulus_response',
                'frame_rate': self.current_parameters.protocol_params.frame_rate,
                'expected_frames': expected_frames
            }
        )

    def _get_camera_parameters(self) -> Dict[str, Any]:
        """Get camera configuration parameters"""
        if not self.current_parameters:
            return {}

        return {
            'frame_rate': self.current_parameters.protocol_params.frame_rate,
            'exposure_ms': 10.0,  # Default exposure
            'gain': 1.0,  # Default gain
        }

    def _get_preview_parameters(self) -> Dict[str, Any]:
        """Get camera parameters for preview mode"""
        return {
            'frame_rate': 30.0,  # Lower frame rate for preview
            'exposure_ms': 10.0,
            'gain': 1.0,
        }

    def _get_frame_shape(self) -> Tuple[int, int]:
        """Get expected frame shape"""
        if self.current_parameters:
            return (
                self.current_parameters.spatial_config.screen_height_pixels,
                self.current_parameters.spatial_config.screen_width_pixels
            )
        return (512, 512)  # Default shape

    def _estimate_frame_count(self) -> int:
        """Estimate total number of frames for acquisition"""
        if not self.current_parameters:
            return 10000  # Default estimate

        frame_rate = self.current_parameters.protocol_params.frame_rate
        duration_sec = (
            self.current_parameters.protocol_params.pre_stimulus_baseline_sec +
            self.current_parameters.protocol_params.post_stimulus_baseline_sec +
            (self.current_parameters.protocol_params.num_cycles * 60.0)  # Estimate cycle duration
        )

        return int(frame_rate * duration_sec * 1.1)  # 10% buffer

    async def _notify_frame_callbacks(self, frame: np.ndarray, frame_index: int) -> None:
        """Notify frame event callbacks"""
        for callback in self._frame_callbacks:
            try:
                callback(frame, frame_index)
            except Exception as e:
                logger.error(f"Error in frame callback: {e}")

    async def _notify_status_change(self) -> None:
        """Notify status change callbacks"""
        for callback in self._status_callbacks:
            try:
                callback(self.status)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")

    async def _handle_error(self, error: Exception) -> None:
        """Handle acquisition errors"""
        self.status = AcquisitionStatus.ERROR
        self.metrics.errors += 1

        # Notify error callbacks
        for callback in self._error_callbacks:
            try:
                callback(error)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")

        # Add warning to session
        if self.current_session:
            self.current_session.add_warning(f"Acquisition error: {error}")
            self.current_session.record_error()

        await self._notify_status_change()