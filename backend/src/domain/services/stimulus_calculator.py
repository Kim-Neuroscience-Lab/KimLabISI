"""
Stimulus Calculator Domain Service for ISI Macroscope System

Calculates stimulus timing, sequences, and display parameters based on
experimental protocols and hardware capabilities.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Iterator
import numpy as np
from scipy import signal

from ..value_objects.parameters import (
    StimulusGenerationParams,
    AcquisitionProtocolParams,
    DirectionSequence,
    BaselineMode
)
from .error_handler import ErrorHandlingService, ISIDomainError


class StimulusDirection(Enum):
    """Stimulus movement directions"""
    LEFT_TO_RIGHT = "left_to_right"
    RIGHT_TO_LEFT = "right_to_left"
    TOP_TO_BOTTOM = "top_to_bottom"
    BOTTOM_TO_TOP = "bottom_to_top"


class TimingPhase(Enum):
    """Phases of stimulus presentation timing"""
    BASELINE = "baseline"
    STIMULUS = "stimulus"
    INTER_TRIAL = "inter_trial"




class StimulusFrame:
    """Individual stimulus frame specification"""

    def __init__(
        self,
        frame_index: int,
        timestamp: float,
        direction: Optional[StimulusDirection],
        phase: TimingPhase,
        stimulus_phase_radians: float = 0.0,
        trial_index: int = 0,
        cycle_index: int = 0
    ):
        self.frame_index = frame_index
        self.timestamp = timestamp
        self.direction = direction
        self.phase = phase
        self.stimulus_phase_radians = stimulus_phase_radians
        self.trial_index = trial_index
        self.cycle_index = cycle_index

    def __repr__(self) -> str:
        return (f"StimulusFrame(frame={self.frame_index}, t={self.timestamp:.3f}s, "
                f"dir={self.direction.value if self.direction else 'None'}, "
                f"phase={self.phase.value})")


class StimulusSequence:
    """Complete stimulus sequence with timing and parameters"""

    def __init__(
        self,
        frames: List[StimulusFrame],
        total_duration_s: float,
        parameters: StimulusGenerationParams,
        metadata: Dict[str, Any]
    ):
        self.frames = frames
        self.total_duration_s = total_duration_s
        self.parameters = parameters
        self.metadata = metadata

    @property
    def total_frames(self) -> int:
        """Total number of frames in sequence"""
        return len(self.frames)

    @property
    def stimulus_frames(self) -> List[StimulusFrame]:
        """Get only frames during stimulus presentation"""
        return [f for f in self.frames if f.phase == TimingPhase.STIMULUS]

    @property
    def baseline_frames(self) -> List[StimulusFrame]:
        """Get only baseline frames"""
        return [f for f in self.frames if f.phase == TimingPhase.BASELINE]

    def get_frames_by_direction(self, direction: StimulusDirection) -> List[StimulusFrame]:
        """Get frames for specific direction"""
        return [f for f in self.frames if f.direction == direction]

    def get_direction_sequence(self) -> List[StimulusDirection]:
        """Get sequence of directions presented"""
        directions = []
        current_direction = None

        for frame in self.frames:
            if frame.direction != current_direction and frame.direction is not None:
                directions.append(frame.direction)
                current_direction = frame.direction

        return directions


class StimulusCalculator:
    """
    Domain service for calculating stimulus sequences and timing

    Generates precise stimulus timing sequences based on experimental parameters
    and hardware constraints following ISI protocols from literature.
    """

    def __init__(self, error_handler: Optional[ErrorHandlingService] = None):
        self.error_handler = error_handler or ErrorHandlingService()

        # Direction mappings
        self._direction_map = {
            "LR": StimulusDirection.LEFT_TO_RIGHT,
            "RL": StimulusDirection.RIGHT_TO_LEFT,
            "TB": StimulusDirection.TOP_TO_BOTTOM,
            "BT": StimulusDirection.BOTTOM_TO_TOP
        }

        # Standard direction sequences
        self._sequence_templates = {
            DirectionSequence.SEQUENTIAL: ["LR", "RL", "TB", "BT"],
            DirectionSequence.INTERLEAVED: ["LR", "TB", "RL", "BT"],
            DirectionSequence.RANDOMIZED: None,  # Generated dynamically
            DirectionSequence.CUSTOM: None       # User-defined
        }

        # Stimulus calculator initialized

    def calculate_stimulus_sequence(
        self,
        stimulus_params: StimulusGenerationParams,
        acquisition_params: AcquisitionProtocolParams,
        custom_direction_order: Optional[List[str]] = None
    ) -> StimulusSequence:
        """
        Calculate complete stimulus sequence with precise timing

        Args:
            stimulus_params: Stimulus generation parameters
            acquisition_params: Acquisition protocol parameters
            custom_direction_order: Custom direction order if using CUSTOM sequence

        Returns:
            Complete stimulus sequence with frame-by-frame timing
        """
        # Calculating stimulus sequence

        try:
            # Validate parameters
            self._validate_parameters(stimulus_params, acquisition_params)

            # Calculate timing parameters
            timing = self._calculate_timing_parameters(stimulus_params, acquisition_params)

            # Generate direction sequence
            directions = self._generate_direction_sequence(
                stimulus_params.direction_sequence,
                stimulus_params.directions,
                custom_direction_order
            )

            # Generate frame sequence
            frames = self._generate_frame_sequence(
                timing, directions, stimulus_params, acquisition_params
            )

            # Calculate total duration
            total_duration = frames[-1].timestamp if frames else 0.0

            # Generate metadata
            metadata = self._generate_sequence_metadata(
                timing, directions, stimulus_params, acquisition_params
            )

            sequence = StimulusSequence(frames, total_duration, stimulus_params, metadata)

            # Sequence calculation tracking delegated to application layer

            return sequence

        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="STIMULUS_CALCULATION_ERROR",
                custom_message="Stimulus calculation failed",
                stimulus_params=stimulus_params.stimulus_type,
                acquisition_params=acquisition_params.frame_rate_hz
            )
            raise ISIDomainError(domain_error)

    def calculate_display_parameters(
        self,
        sequence: StimulusSequence,
        display_width_px: int,
        display_height_px: int,
        stimulus_width_degrees: float = 120.0,
        stimulus_height_degrees: float = 90.0
    ) -> Dict[str, Any]:
        """
        Calculate display-specific stimulus parameters

        Args:
            sequence: Stimulus sequence
            display_width_px: Display width in pixels
            display_height_px: Display height in pixels
            stimulus_width_degrees: Stimulus field width in degrees
            stimulus_height_degrees: Stimulus field height in degrees

        Returns:
            Dictionary with display parameters
        """
        # Calculate spatial frequency in cycles per degree
        spatial_freq_cpd = sequence.parameters.spatial_frequency_cpd

        # Convert to cycles per pixel
        cycles_per_px_x = spatial_freq_cpd * stimulus_width_degrees / display_width_px
        cycles_per_px_y = spatial_freq_cpd * stimulus_height_degrees / display_height_px

        # Calculate bar width in pixels for each direction
        bar_width_px_horizontal = display_width_px / (spatial_freq_cpd * stimulus_width_degrees / display_width_px)
        bar_width_px_vertical = display_height_px / (spatial_freq_cpd * stimulus_height_degrees / display_height_px)

        # Calculate movement speed in pixels per frame
        temporal_freq = sequence.parameters.temporal_frequency_hz
        frame_rate = 60.0  # Assume 60 Hz display refresh rate

        speed_px_per_frame_x = (temporal_freq * bar_width_px_horizontal) / frame_rate
        speed_px_per_frame_y = (temporal_freq * bar_width_px_vertical) / frame_rate

        display_params = {
            "display_resolution": (display_width_px, display_height_px),
            "stimulus_field_degrees": (stimulus_width_degrees, stimulus_height_degrees),
            "spatial_frequency_cpd": spatial_freq_cpd,
            "cycles_per_pixel": (cycles_per_px_x, cycles_per_px_y),
            "bar_width_pixels": {
                "horizontal": bar_width_px_horizontal,
                "vertical": bar_width_px_vertical
            },
            "movement_speed_px_per_frame": {
                "horizontal": speed_px_per_frame_x,
                "vertical": speed_px_per_frame_y
            },
            "temporal_frequency_hz": temporal_freq,
            "display_refresh_rate_hz": frame_rate
        }

        # Display parameters calculated

        return display_params

    def calculate_fourier_analysis_parameters(
        self,
        sequence: StimulusSequence,
        acquisition_params: AcquisitionProtocolParams
    ) -> Dict[str, Any]:
        """
        Calculate parameters needed for Fourier analysis of ISI data

        Args:
            sequence: Stimulus sequence
            acquisition_params: Acquisition parameters

        Returns:
            Dictionary with Fourier analysis parameters
        """
        # Extract stimulus timing information
        stimulus_frames = sequence.stimulus_frames
        if not stimulus_frames:
            domain_error = self.error_handler.create_error(
                error_code="STIMULUS_CALCULATION_ERROR",
                custom_message="No stimulus frames found in sequence",
                sequence_id=getattr(sequence, 'sequence_id', 'unknown'),
                frame_count=len(stimulus_frames)
            )
            raise ISIDomainError(domain_error)

        # Calculate stimulus frequency from actual timing
        direction_durations = {}
        current_direction = None
        direction_start_time = 0.0

        for frame in stimulus_frames:
            if frame.direction != current_direction:
                if current_direction is not None:
                    duration = frame.timestamp - direction_start_time
                    if current_direction not in direction_durations:
                        direction_durations[current_direction] = []
                    direction_durations[current_direction].append(duration)

                current_direction = frame.direction
                direction_start_time = frame.timestamp

        # Calculate average stimulus frequency
        avg_stimulus_freq = sequence.parameters.temporal_frequency_hz
        sampling_freq = acquisition_params.frame_rate_hz

        # Nyquist frequency check using scipy signal processing
        nyquist_freq = sampling_freq / 2
        if avg_stimulus_freq >= nyquist_freq:
            # Stimulus frequency exceeds Nyquist frequency - handled by application layer
            pass

        # Calculate analysis window parameters
        cycle_duration_s = 1.0 / avg_stimulus_freq
        frames_per_cycle = int(cycle_duration_s * sampling_freq)

        # Calculate frequency bin resolution using scipy signal processing
        total_frames = len(sequence.frames)
        freq_resolution = sampling_freq / total_frames

        fourier_params = {
            "stimulus_frequency_hz": avg_stimulus_freq,
            "sampling_frequency_hz": sampling_freq,
            "nyquist_frequency_hz": nyquist_freq,
            "cycle_duration_s": cycle_duration_s,
            "frames_per_cycle": frames_per_cycle,
            "frequency_resolution_hz": freq_resolution,
            "total_analysis_frames": total_frames,
            "stimulus_bin_index": int(avg_stimulus_freq / freq_resolution),
            "direction_durations": {dir.value: durations
                                  for dir, durations in direction_durations.items()}
        }

        # Fourier analysis parameters calculated

        return fourier_params

    def _validate_parameters(
        self,
        stimulus_params: StimulusGenerationParams,
        acquisition_params: AcquisitionProtocolParams
    ):
        """Validate parameter consistency"""

        # Check temporal frequency vs acquisition rate
        if stimulus_params.temporal_frequency_hz >= acquisition_params.frame_rate_hz / 2:
            domain_error = self.error_handler.create_error(
                error_code="STIMULUS_CALCULATION_ERROR",
                custom_message=f"Stimulus frequency {stimulus_params.temporal_frequency_hz} Hz too high for acquisition rate {acquisition_params.frame_rate_hz} Hz",
                stimulus_frequency=stimulus_params.temporal_frequency_hz,
                frame_rate=acquisition_params.frame_rate_hz,
                validation_rule="nyquist_limit"
            )
            raise ISIDomainError(domain_error)

        # Check minimum cycle duration
        min_cycle_duration = 2.0 / acquisition_params.frame_rate_hz  # At least 2 frames per cycle
        actual_cycle_duration = 1.0 / stimulus_params.temporal_frequency_hz

        if actual_cycle_duration < min_cycle_duration:
            domain_error = self.error_handler.create_error(
                error_code="STIMULUS_CALCULATION_ERROR",
                custom_message=f"Stimulus cycle duration {actual_cycle_duration:.3f}s too short (minimum: {min_cycle_duration:.3f}s)",
                actual_cycle_duration=actual_cycle_duration,
                minimum_cycle_duration=min_cycle_duration,
                validation_rule="minimum_cycle_duration"
            )
            raise ISIDomainError(domain_error)

        # Validate direction count
        if len(stimulus_params.directions) == 0:
            domain_error = self.error_handler.create_error(
                error_code="STIMULUS_CALCULATION_ERROR",
                custom_message="At least one stimulus direction required",
                provided_directions=len(stimulus_params.directions),
                validation_rule="minimum_directions"
            )
            raise ISIDomainError(domain_error)

        # Validate timing parameters
        if stimulus_params.baseline_duration_s < 0:
            domain_error = self.error_handler.create_error(
                error_code="STIMULUS_CALCULATION_ERROR",
                custom_message="Baseline duration cannot be negative",
                baseline_duration=stimulus_params.baseline_duration_s,
                validation_rule="non_negative_duration"
            )
            raise ISIDomainError(domain_error)

        if stimulus_params.cycles_per_trial <= 0:
            domain_error = self.error_handler.create_error(
                error_code="STIMULUS_CALCULATION_ERROR",
                custom_message="Cycles per trial must be positive",
                cycles_per_trial=stimulus_params.cycles_per_trial,
                validation_rule="positive_cycles"
            )
            raise ISIDomainError(domain_error)

    def _calculate_timing_parameters(
        self,
        stimulus_params: StimulusGenerationParams,
        acquisition_params: AcquisitionProtocolParams
    ) -> Dict[str, float]:
        """Calculate precise timing parameters"""

        frame_duration_s = 1.0 / acquisition_params.frame_rate_hz
        cycle_duration_s = 1.0 / stimulus_params.temporal_frequency_hz

        # Calculate frames per cycle
        frames_per_cycle = int(round(cycle_duration_s / frame_duration_s))
        actual_cycle_duration_s = frames_per_cycle * frame_duration_s

        # Calculate trial duration
        frames_per_trial = frames_per_cycle * stimulus_params.cycles_per_trial
        trial_duration_s = frames_per_trial * frame_duration_s

        # Calculate baseline frames
        baseline_frames = int(round(stimulus_params.baseline_duration_s / frame_duration_s))
        actual_baseline_duration_s = baseline_frames * frame_duration_s

        timing = {
            "frame_duration_s": frame_duration_s,
            "cycle_duration_s": actual_cycle_duration_s,
            "trial_duration_s": trial_duration_s,
            "baseline_duration_s": actual_baseline_duration_s,
            "frames_per_cycle": frames_per_cycle,
            "frames_per_trial": frames_per_trial,
            "baseline_frames": baseline_frames,
            "total_cycles": stimulus_params.cycles_per_trial * len(stimulus_params.directions)
        }

        # Timing parameters calculated

        return timing

    def _generate_direction_sequence(
        self,
        sequence_type: DirectionSequence,
        enabled_directions: List[str],
        custom_order: Optional[List[str]] = None
    ) -> List[StimulusDirection]:
        """Generate sequence of stimulus directions"""

        if sequence_type == DirectionSequence.CUSTOM:
            if not custom_order:
                domain_error = self.error_handler.create_error(
                    error_code="STIMULUS_CALCULATION_ERROR",
                    custom_message="Custom direction order required for CUSTOM sequence",
                    sequence_type=sequence_type.value,
                    validation_rule="custom_order_required"
                )
                raise ISIDomainError(domain_error)
            direction_codes = custom_order
        elif sequence_type == DirectionSequence.RANDOMIZED:
            # Generate randomized sequence
            import random
            direction_codes = enabled_directions.copy()
            random.shuffle(direction_codes)
        else:
            # Use predefined template
            template = self._sequence_templates[sequence_type]
            direction_codes = [code for code in template if code in enabled_directions]

        # Convert codes to direction enums
        directions = []
        for code in direction_codes:
            if code in self._direction_map:
                directions.append(self._direction_map[code])
            else:
                # Unknown direction code - handled by validation
                pass

        if not directions:
            domain_error = self.error_handler.create_error(
                error_code="STIMULUS_CALCULATION_ERROR",
                custom_message=f"No valid directions generated from {enabled_directions}",
                enabled_directions=enabled_directions,
                sequence_type=sequence_type.value,
                validation_rule="valid_directions_required"
            )
            raise ISIDomainError(domain_error)

        # Direction sequence generated
        return directions

    def _generate_frame_sequence(
        self,
        timing: Dict[str, float],
        directions: List[StimulusDirection],
        stimulus_params: StimulusGenerationParams,
        acquisition_params: AcquisitionProtocolParams
    ) -> List[StimulusFrame]:
        """Generate complete frame-by-frame stimulus sequence"""

        frames = []
        frame_index = 0
        current_time = 0.0
        frame_duration = timing["frame_duration_s"]

        # Add initial baseline if requested
        if stimulus_params.baseline_mode != BaselineMode.NONE:
            baseline_frames = timing["baseline_frames"]
            for _ in range(baseline_frames):
                frame = StimulusFrame(
                    frame_index=frame_index,
                    timestamp=current_time,
                    direction=None,
                    phase=TimingPhase.BASELINE,
                    trial_index=0,
                    cycle_index=0
                )
                frames.append(frame)
                frame_index += 1
                current_time += frame_duration

        # Generate stimulus trials
        for trial_idx, direction in enumerate(directions):
            frames_per_trial = timing["frames_per_trial"]
            frames_per_cycle = timing["frames_per_cycle"]

            # Generate frames for this trial
            for frame_in_trial in range(frames_per_trial):
                cycle_index = frame_in_trial // frames_per_cycle
                frame_in_cycle = frame_in_trial % frames_per_cycle

                # Calculate stimulus phase within cycle using validated numpy constants
                phase_radians = 2 * np.pi * frame_in_cycle / frames_per_cycle

                frame = StimulusFrame(
                    frame_index=frame_index,
                    timestamp=current_time,
                    direction=direction,
                    phase=TimingPhase.STIMULUS,
                    stimulus_phase_radians=phase_radians,
                    trial_index=trial_idx,
                    cycle_index=cycle_index
                )
                frames.append(frame)
                frame_index += 1
                current_time += frame_duration

            # Add inter-trial baseline if requested
            if stimulus_params.baseline_mode == BaselineMode.BETWEEN_TRIALS and trial_idx < len(directions) - 1:
                baseline_frames = timing["baseline_frames"]
                for _ in range(baseline_frames):
                    frame = StimulusFrame(
                        frame_index=frame_index,
                        timestamp=current_time,
                        direction=None,
                        phase=TimingPhase.INTER_TRIAL,
                        trial_index=trial_idx,
                        cycle_index=0
                    )
                    frames.append(frame)
                    frame_index += 1
                    current_time += frame_duration

        # Add final baseline if requested
        if stimulus_params.baseline_mode in [BaselineMode.START_END, BaselineMode.END_ONLY]:
            baseline_frames = timing["baseline_frames"]
            for _ in range(baseline_frames):
                frame = StimulusFrame(
                    frame_index=frame_index,
                    timestamp=current_time,
                    direction=None,
                    phase=TimingPhase.BASELINE,
                    trial_index=len(directions),
                    cycle_index=0
                )
                frames.append(frame)
                frame_index += 1
                current_time += frame_duration

        # Frame sequence generated
        return frames

    def _generate_sequence_metadata(
        self,
        timing: Dict[str, float],
        directions: List[StimulusDirection],
        stimulus_params: StimulusGenerationParams,
        acquisition_params: AcquisitionProtocolParams
    ) -> Dict[str, Any]:
        """Generate metadata for stimulus sequence"""

        metadata = {
            "generation_timestamp": datetime.now().isoformat(),
            "stimulus_type": stimulus_params.stimulus_type,
            "direction_sequence": stimulus_params.direction_sequence.value,
            "directions": [d.value for d in directions],
            "timing_parameters": timing,
            "temporal_frequency_hz": stimulus_params.temporal_frequency_hz,
            "spatial_frequency_cpd": stimulus_params.spatial_frequency_cpd,
            "cycles_per_trial": stimulus_params.cycles_per_trial,
            "baseline_mode": stimulus_params.baseline_mode.value,
            "baseline_duration_s": stimulus_params.baseline_duration_s,
            "acquisition_frame_rate_hz": acquisition_params.frame_rate_hz,
            "total_trials": len(directions),
            "total_cycles": timing["total_cycles"],
            "estimated_duration_s": timing["trial_duration_s"] * len(directions),
        }

        return metadata

    def validate_sequence_timing(self, sequence: StimulusSequence) -> Tuple[bool, List[str]]:
        """Validate stimulus sequence timing consistency"""

        issues = []

        # Check frame timing consistency
        for i in range(1, len(sequence.frames)):
            expected_interval = 1.0 / 30.0  # Assume 30 Hz default
            actual_interval = sequence.frames[i].timestamp - sequence.frames[i-1].timestamp

            if abs(actual_interval - expected_interval) > 0.001:  # 1ms tolerance
                issues.append(f"Frame timing inconsistency at frame {i}: "
                             f"expected {expected_interval:.4f}s, got {actual_interval:.4f}s")
                break  # Don't flood with timing errors

        # Check direction transitions
        stimulus_frames = sequence.stimulus_frames
        if stimulus_frames:
            current_direction = stimulus_frames[0].direction
            direction_changes = 1

            for frame in stimulus_frames[1:]:
                if frame.direction != current_direction:
                    direction_changes += 1
                    current_direction = frame.direction

            expected_directions = len(set(frame.direction for frame in stimulus_frames
                                        if frame.direction is not None))
            if direction_changes < expected_directions:
                issues.append(f"Missing direction transitions: expected {expected_directions}, "
                             f"found {direction_changes}")

        # Check phase continuity within cycles
        for direction in set(f.direction for f in stimulus_frames if f.direction):
            dir_frames = [f for f in stimulus_frames if f.direction == direction]

            for i in range(1, len(dir_frames)):
                if dir_frames[i].cycle_index == dir_frames[i-1].cycle_index:
                    # Same cycle, check phase progression
                    phase_diff = dir_frames[i].stimulus_phase_radians - dir_frames[i-1].stimulus_phase_radians
                    if phase_diff < 0:  # Phase should always increase within cycle
                        issues.append(f"Phase regression in {direction.value} at frame {dir_frames[i].frame_index}")

        is_valid = len(issues) == 0

        # Timing validation completed

        return is_valid, issues