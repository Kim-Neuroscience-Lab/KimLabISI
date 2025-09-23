"""
Stimulus Generation Use Case - Retinotopy Pattern Generation

This use case handles the generation of retinotopy mapping stimuli for
visual cortex mapping experiments. It orchestrates pattern generation,
timing, and stimulus presentation.

Key Responsibilities:
- Generate retinotopy stimulus patterns
- Manage stimulus timing and sequencing
- Coordinate with display hardware
- Provide stimulus preview and validation
"""

import asyncio
import logging
import numpy as np
from typing import List, Optional, Iterator
from pathlib import Path

from ...domain.value_objects.stimulus_params import (
    StimulusParams, VisualFieldParams, RetinotopyProtocol
)
from ...domain.entities.workflow_state import WorkflowState, HardwareRequirement
from ..algorithms.pattern_generators import PatternGenerator

logger = logging.getLogger(__name__)


class StimulusGenerationError(Exception):
    """Errors related to stimulus generation"""
    pass


class StimulusSequence:
    """Represents a complete stimulus sequence"""

    def __init__(self, protocol: RetinotopyProtocol, generator: PatternGenerator):
        """
        Initialize stimulus sequence

        Args:
            protocol: Retinotopy protocol parameters
            generator: Pattern generator instance
        """
        self.protocol = protocol
        self.generator = generator
        self.params = protocol.stimulus_params
        self._current_frame = 0

    @property
    def total_frames(self) -> int:
        """Total number of frames in the sequence"""
        return self.params.total_frames

    @property
    def current_frame_index(self) -> int:
        """Current frame index"""
        return self._current_frame

    @property
    def progress(self) -> float:
        """Current progress as fraction (0.0 to 1.0)"""
        return self._current_frame / max(1, self.total_frames)

    def get_frame(self, frame_index: Optional[int] = None) -> np.ndarray:
        """
        Get a specific frame from the sequence

        Args:
            frame_index: Frame index, or None for current frame

        Returns:
            Frame as numpy array
        """
        if frame_index is None:
            frame_index = self._current_frame

        if frame_index >= self.total_frames:
            raise ValueError(f"Frame index {frame_index} exceeds sequence length {self.total_frames}")

        return self.generator.generate_frame(self.params, frame_index)

    def advance_frame(self) -> bool:
        """
        Advance to next frame

        Returns:
            True if advanced, False if at end of sequence
        """
        if self._current_frame < self.total_frames - 1:
            self._current_frame += 1
            return True
        return False

    def reset(self):
        """Reset sequence to beginning"""
        self._current_frame = 0

    def __iter__(self) -> Iterator[np.ndarray]:
        """Iterate through all frames in sequence"""
        for frame_index in range(self.total_frames):
            yield self.get_frame(frame_index)


class StimulusGenerationUseCase:
    """
    Use case for generating retinotopy stimuli

    This use case handles the complete stimulus generation pipeline from
    protocol specification to frame-by-frame pattern generation.
    """

    def __init__(self):
        """Initialize stimulus generation use case"""
        self._current_sequence: Optional[StimulusSequence] = None
        self._generator: Optional[PatternGenerator] = None

    async def create_stimulus_sequence(self, protocol: RetinotopyProtocol) -> StimulusSequence:
        """
        Create a new stimulus sequence from protocol

        Args:
            protocol: Retinotopy protocol specification

        Returns:
            Configured stimulus sequence

        Raises:
            StimulusGenerationError: If sequence creation fails
        """
        try:
            logger.info(f"Creating stimulus sequence: {protocol.protocol_name}")

            # Create pattern generator
            generator = PatternGenerator(protocol.visual_field)

            # Create stimulus sequence
            sequence = StimulusSequence(protocol, generator)

            # Validate sequence
            await self._validate_sequence(sequence)

            self._current_sequence = sequence
            self._generator = generator

            logger.info(f"Stimulus sequence created: {sequence.total_frames} frames, "
                       f"{sequence.protocol.total_protocol_duration_sec:.1f}s duration")

            return sequence

        except Exception as e:
            logger.error(f"Failed to create stimulus sequence: {e}")
            raise StimulusGenerationError(f"Stimulus sequence creation failed: {e}")

    async def _validate_sequence(self, sequence: StimulusSequence):
        """
        Validate stimulus sequence

        Args:
            sequence: Sequence to validate

        Raises:
            StimulusGenerationError: If validation fails
        """
        # Test frame generation
        try:
            test_frame = sequence.get_frame(0)
            if test_frame is None or test_frame.size == 0:
                raise ValueError("Generated frame is empty")

            # Check frame properties
            if not np.isfinite(test_frame).all():
                raise ValueError("Generated frame contains invalid values")

            if test_frame.min() < 0 or test_frame.max() > 1:
                raise ValueError(f"Generated frame values out of range [0,1]: {test_frame.min():.3f} to {test_frame.max():.3f}")

        except Exception as e:
            raise StimulusGenerationError(f"Stimulus validation failed: {e}")

    async def generate_preview_frames(self,
                                    protocol: RetinotopyProtocol,
                                    num_frames: int = 10) -> List[np.ndarray]:
        """
        Generate preview frames for stimulus validation

        Args:
            protocol: Protocol to preview
            num_frames: Number of preview frames to generate

        Returns:
            List of preview frames

        Raises:
            StimulusGenerationError: If preview generation fails
        """
        try:
            logger.info(f"Generating {num_frames} preview frames")

            # Create temporary sequence
            generator = PatternGenerator(protocol.visual_field)
            sequence = StimulusSequence(protocol, generator)

            # Generate evenly spaced preview frames
            preview_frames = []
            frame_step = max(1, sequence.total_frames // num_frames)

            for i in range(num_frames):
                frame_index = min(i * frame_step, sequence.total_frames - 1)
                frame = sequence.get_frame(frame_index)
                preview_frames.append(frame)

            logger.info(f"Generated {len(preview_frames)} preview frames")
            return preview_frames

        except Exception as e:
            logger.error(f"Preview generation failed: {e}")
            raise StimulusGenerationError(f"Preview generation failed: {e}")

    async def export_stimulus_video(self,
                                  protocol: RetinotopyProtocol,
                                  output_path: Path,
                                  frame_skip: int = 1) -> Path:
        """
        Export stimulus sequence as video file for visual validation

        Args:
            protocol: Protocol to export
            output_path: Output video file path
            frame_skip: Skip every N frames to reduce file size

        Returns:
            Path to created video file

        Raises:
            StimulusGenerationError: If export fails
        """
        try:
            logger.info(f"Exporting stimulus video to {output_path}")

            # Ensure we have required dependencies
            try:
                import cv2
            except ImportError:
                raise StimulusGenerationError("OpenCV (cv2) required for video export. Install with: pip install opencv-python")

            # Create stimulus sequence
            generator = PatternGenerator(protocol.visual_field)
            sequence = StimulusSequence(protocol, generator)

            # Setup video writer
            height, width = (protocol.visual_field.screen_height_pixels,
                           protocol.visual_field.screen_width_pixels)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            fps = protocol.stimulus_params.frame_rate / frame_skip

            video_writer = cv2.VideoWriter(
                str(output_path),
                fourcc,
                fps,
                (width, height),
                isColor=False
            )

            if not video_writer.isOpened():
                raise StimulusGenerationError(f"Could not open video writer for {output_path}")

            # Generate and write frames
            frames_written = 0
            for frame_index in range(0, sequence.total_frames, frame_skip):
                # Generate frame
                frame = sequence.get_frame(frame_index)

                # Convert to 8-bit grayscale
                frame_8bit = (frame * 255).astype(np.uint8)

                # Write frame
                video_writer.write(frame_8bit)
                frames_written += 1

                # Progress logging
                if frames_written % 100 == 0:
                    progress = frame_index / sequence.total_frames
                    logger.info(f"Video export progress: {progress*100:.1f}%")

            video_writer.release()

            logger.info(f"Video export complete: {frames_written} frames written to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Video export failed: {e}")
            raise StimulusGenerationError(f"Video export failed: {e}")

    def get_current_sequence(self) -> Optional[StimulusSequence]:
        """Get currently loaded stimulus sequence"""
        return self._current_sequence

    async def start_stimulus_presentation(self) -> bool:
        """
        Start presenting current stimulus sequence

        Returns:
            True if presentation started successfully

        Raises:
            StimulusGenerationError: If no sequence is loaded or start fails
        """
        if self._current_sequence is None:
            raise StimulusGenerationError("No stimulus sequence loaded")

        try:
            logger.info("Starting stimulus presentation")
            self._current_sequence.reset()

            # In a real implementation, this would interface with display hardware
            # For now, we just log the start
            logger.info(f"Stimulus presentation started: {self._current_sequence.total_frames} frames")
            return True

        except Exception as e:
            logger.error(f"Failed to start stimulus presentation: {e}")
            raise StimulusGenerationError(f"Stimulus presentation failed: {e}")

    async def stop_stimulus_presentation(self) -> bool:
        """
        Stop current stimulus presentation

        Returns:
            True if stopped successfully
        """
        try:
            logger.info("Stopping stimulus presentation")

            # In a real implementation, this would stop the display hardware
            # For now, we just log the stop
            logger.info("Stimulus presentation stopped")
            return True

        except Exception as e:
            logger.error(f"Failed to stop stimulus presentation: {e}")
            return False


# Factory functions for creating common protocols

def create_horizontal_bar_protocol(visual_field: VisualFieldParams,
                                 cycle_duration: float = 30.0,
                                 num_cycles: int = 2) -> RetinotopyProtocol:
    """Create a horizontal bar retinotopy protocol"""
    from ..algorithms.pattern_generators import create_default_horizontal_bar_params

    stimulus_params = create_default_horizontal_bar_params(visual_field)
    stimulus_params = stimulus_params.model_copy(update={
        'cycle_duration_sec': cycle_duration,
        'num_cycles': num_cycles
    })

    return RetinotopyProtocol(
        protocol_name="Horizontal Bar Retinotopy",
        description="Phase-encoded horizontal bar for vertical retinotopy mapping",
        stimulus_params=stimulus_params,
        visual_field=visual_field,
        pre_stimulus_baseline_sec=10.0,
        post_stimulus_baseline_sec=10.0
    )


def create_vertical_bar_protocol(visual_field: VisualFieldParams,
                               cycle_duration: float = 30.0,
                               num_cycles: int = 2) -> RetinotopyProtocol:
    """Create a vertical bar retinotopy protocol"""
    from ..algorithms.pattern_generators import create_default_vertical_bar_params

    stimulus_params = create_default_vertical_bar_params(visual_field)
    stimulus_params = stimulus_params.model_copy(update={
        'cycle_duration_sec': cycle_duration,
        'num_cycles': num_cycles
    })

    return RetinotopyProtocol(
        protocol_name="Vertical Bar Retinotopy",
        description="Phase-encoded vertical bar for horizontal retinotopy mapping",
        stimulus_params=stimulus_params,
        visual_field=visual_field,
        pre_stimulus_baseline_sec=10.0,
        post_stimulus_baseline_sec=10.0
    )


def create_polar_wedge_protocol(visual_field: VisualFieldParams,
                              cycle_duration: float = 40.0,
                              num_cycles: int = 2) -> RetinotopyProtocol:
    """Create a polar wedge retinotopy protocol"""
    from ..algorithms.pattern_generators import create_default_polar_wedge_params

    stimulus_params = create_default_polar_wedge_params(visual_field)
    stimulus_params = stimulus_params.model_copy(update={
        'cycle_duration_sec': cycle_duration,
        'num_cycles': num_cycles
    })

    return RetinotopyProtocol(
        protocol_name="Polar Wedge Retinotopy",
        description="Phase-encoded polar wedge for polar angle mapping",
        stimulus_params=stimulus_params,
        visual_field=visual_field,
        pre_stimulus_baseline_sec=10.0,
        post_stimulus_baseline_sec=10.0
    )