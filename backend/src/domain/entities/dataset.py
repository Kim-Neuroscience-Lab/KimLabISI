"""
Dataset Entities - Scientific Data Management

This module defines the core dataset entities for the ISI Macroscope Control System,
representing stimulus datasets, acquisition sessions, and analysis results following
Clean Architecture domain modeling principles.
"""

from typing import Dict, List, Optional, Set, Any, Tuple
from datetime import datetime
from pathlib import Path
from enum import Enum
from joblib import hash as joblib_hash

from ..value_objects.parameters import CombinedParameters, SpatialConfiguration
from ..value_objects.stream_config import StreamingProfile
from ..services.error_handler import ErrorHandlingService, ISIDomainError


class DatasetType(Enum):
    """Types of scientific datasets"""
    STIMULUS_HDF5 = "stimulus_hdf5"         # Generated stimulus patterns
    CAMERA_FRAMES = "camera_frames"         # Raw camera capture data
    ANALYSIS_RESULTS = "analysis_results"   # Generated retinotopic maps
    SESSION_METADATA = "session_metadata"   # Experimental session information


class DatasetStatus(Enum):
    """Dataset processing status"""
    GENERATING = "generating"       # Currently being generated
    READY = "ready"                # Available for use
    PROCESSING = "processing"       # Being analyzed
    COMPLETED = "completed"         # Analysis complete
    ERROR = "error"                 # Processing error occurred
    ARCHIVED = "archived"           # Moved to long-term storage


class CompressionType(Enum):
    """Data compression types"""
    NONE = "none"
    GZIP = "gzip"
    LZF = "lzf"
    SZIP = "szip"


class StimulusDataset:
    """
    Entity representing a complete stimulus dataset (HDF5 files)

    Contains all stimulus patterns for one parameter configuration,
    organized by direction (LR, RL, TB, BT) with unified metadata.
    """

    def __init__(
        self,
        dataset_id: str,
        parameters: CombinedParameters,
        base_path: Path,
        created_by: str = "system"
    ):
        # Identity
        self.dataset_id = dataset_id
        self.parameters = parameters
        self.base_path = Path(base_path)
        self.created_by = created_by

        # Timestamps
        self.created_timestamp = datetime.now()
        self.modified_timestamp = self.created_timestamp

        # Status tracking
        self.status = DatasetStatus.GENERATING
        self.generation_progress = 0.0  # 0.0 to 1.0
        self.error_message: Optional[str] = None

        # File management
        self.direction_files: Dict[str, Path] = {}  # Direction -> HDF5 file path
        self.file_sizes: Dict[str, int] = {}        # Direction -> file size bytes
        self.frame_counts: Dict[str, int] = {}      # Direction -> number of frames

        # Quality metrics
        self.integrity_verified = False
        self.parameter_hash = self.parameters.generation_hash
        self.dataset_hash: Optional[str] = None

    def add_direction_file(
        self,
        direction: str,
        file_path: Path,
        frame_count: int,
        file_size: Optional[int] = None
    ):
        """Add a direction file to the dataset"""
        if direction not in ["LR", "RL", "TB", "BT"]:
            raise ValueError(f"Invalid direction: {direction}")

        self.direction_files[direction] = Path(file_path)
        self.frame_counts[direction] = frame_count

        if file_size is not None:
            self.file_sizes[direction] = file_size
        elif file_path.exists():
            self.file_sizes[direction] = file_path.stat().st_size

        self.modified_timestamp = datetime.now()
        logger.debug(f"Added {direction} file to dataset {self.dataset_id}: {frame_count} frames")

    def mark_completed(self):
        """Mark dataset generation as completed"""
        if len(self.direction_files) == 0:
            raise ValueError("Cannot complete dataset with no direction files")

        self.status = DatasetStatus.READY
        self.generation_progress = 1.0
        self.modified_timestamp = datetime.now()

        # Calculate dataset integrity hash
        self.dataset_hash = self._calculate_dataset_hash()
        self.integrity_verified = True

        logger.info(f"Dataset {self.dataset_id} marked as completed with {len(self.direction_files)} directions")

    def mark_error(self, error_message: str):
        """Mark dataset as having an error"""
        self.status = DatasetStatus.ERROR
        self.error_message = error_message
        self.modified_timestamp = datetime.now()
        logger.error(f"Dataset {self.dataset_id} marked as error: {error_message}")

    def get_available_directions(self) -> List[str]:
        """Get list of available stimulus directions"""
        return list(self.direction_files.keys())

    def get_total_frames(self) -> int:
        """Get total number of frames across all directions"""
        return sum(self.frame_counts.values())

    def get_total_size_bytes(self) -> int:
        """Get total dataset size in bytes"""
        return sum(self.file_sizes.values())

    def is_compatible_with_parameters(self, other_parameters: CombinedParameters) -> bool:
        """Check if dataset is compatible with given parameters"""
        return self.parameter_hash == other_parameters.generation_hash

    def verify_integrity(self) -> bool:
        """Verify dataset file integrity"""
        try:
            # Check all files exist and are readable
            for direction, file_path in self.direction_files.items():
                if not file_path.exists():
                    logger.error(f"Missing direction file: {direction} -> {file_path}")
                    return False

                if not file_path.is_file():
                    logger.error(f"Path is not a file: {file_path}")
                    return False

            # Verify hash if available
            if self.dataset_hash:
                current_hash = self._calculate_dataset_hash()
                if current_hash != self.dataset_hash:
                    logger.error(f"Dataset hash mismatch for {self.dataset_id}")
                    return False

            self.integrity_verified = True
            return True

        except Exception as e:
            logger.exception(f"Error verifying dataset integrity: {e}")
            return False

    def _calculate_dataset_hash(self) -> str:
        """Calculate deterministic hash for dataset integrity verification"""
        hash_data = {
            "dataset_id": self.dataset_id,
            "parameter_hash": self.parameter_hash,
            "direction_files": {
                direction: str(path) for direction, path in self.direction_files.items()
            },
            "frame_counts": self.frame_counts,
            "file_sizes": self.file_sizes
        }
        return joblib_hash(hash_data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "dataset_id": self.dataset_id,
            "parameters": self.parameters.model_dump(),
            "base_path": str(self.base_path),
            "created_by": self.created_by,
            "created_timestamp": self.created_timestamp.isoformat(),
            "modified_timestamp": self.modified_timestamp.isoformat(),
            "status": self.status.value,
            "generation_progress": self.generation_progress,
            "error_message": self.error_message,
            "direction_files": {k: str(v) for k, v in self.direction_files.items()},
            "file_sizes": self.file_sizes,
            "frame_counts": self.frame_counts,
            "integrity_verified": self.integrity_verified,
            "parameter_hash": self.parameter_hash,
            "dataset_hash": self.dataset_hash
        }


class AcquisitionSession:
    """
    Entity representing a complete experimental acquisition session

    Manages camera data, stimulus events, and session metadata for
    one complete retinotopic mapping experiment.
    """

    def __init__(
        self,
        session_id: str,
        stimulus_dataset: StimulusDataset,
        session_path: Path,
        streaming_profile: StreamingProfile,
        experimenter: str = "unknown"
    ):
        # Identity and relationships
        self.session_id = session_id
        self.stimulus_dataset = stimulus_dataset
        self.session_path = Path(session_path)
        self.streaming_profile = streaming_profile
        self.experimenter = experimenter

        # Timestamps
        self.created_timestamp = datetime.now()
        self.started_timestamp: Optional[datetime] = None
        self.completed_timestamp: Optional[datetime] = None

        # Status tracking
        self.status = DatasetStatus.READY
        self.acquisition_progress = 0.0  # 0.0 to 1.0
        self.current_direction: Optional[str] = None
        self.current_trial = 0
        self.total_trials = 0
        self.error_message: Optional[str] = None

        # Data organization
        self.camera_files: Dict[str, List[Path]] = {}      # Direction -> list of trial files
        self.event_files: Dict[str, Path] = {}             # Direction -> event CSV file
        self.frame_counts: Dict[str, int] = {}             # Direction -> total frames captured
        self.dropped_frames: Dict[str, int] = {}           # Direction -> dropped frame count

        # Quality metrics
        self.timing_quality: Dict[str, float] = {}         # Direction -> timing precision
        self.coverage_quality: Dict[str, float] = {}       # Direction -> coverage completeness
        self.hardware_issues: List[str] = []               # Hardware problems encountered

    def start_acquisition(self, total_trials: int):
        """Start acquisition session"""
        self.status = DatasetStatus.PROCESSING
        self.started_timestamp = datetime.now()
        self.total_trials = total_trials
        self.acquisition_progress = 0.0
        logger.info(f"Started acquisition session {self.session_id} with {total_trials} trials")

    def start_direction(self, direction: str):
        """Start acquiring a specific direction"""
        if direction not in ["LR", "RL", "TB", "BT"]:
            raise ValueError(f"Invalid direction: {direction}")

        self.current_direction = direction
        self.current_trial = 0

        # Initialize direction tracking
        if direction not in self.camera_files:
            self.camera_files[direction] = []
            self.frame_counts[direction] = 0
            self.dropped_frames[direction] = 0

        logger.info(f"Started direction {direction} in session {self.session_id}")

    def add_trial_data(
        self,
        direction: str,
        camera_file: Path,
        frame_count: int,
        dropped_count: int = 0
    ):
        """Add trial data for a direction"""
        if direction not in self.camera_files:
            self.camera_files[direction] = []
            self.frame_counts[direction] = 0
            self.dropped_frames[direction] = 0

        self.camera_files[direction].append(Path(camera_file))
        self.frame_counts[direction] += frame_count
        self.dropped_frames[direction] += dropped_count

        self.current_trial += 1
        self.acquisition_progress = self.current_trial / self.total_trials

        logger.debug(f"Added trial data for {direction}: {frame_count} frames, {dropped_count} dropped")

    def add_event_file(self, direction: str, event_file: Path):
        """Add stimulus event file for a direction"""
        self.event_files[direction] = Path(event_file)
        logger.debug(f"Added event file for {direction}: {event_file}")

    def complete_acquisition(self):
        """Mark acquisition as completed"""
        self.status = DatasetStatus.COMPLETED
        self.completed_timestamp = datetime.now()
        self.acquisition_progress = 1.0
        self.current_direction = None

        # Calculate quality metrics
        self._calculate_quality_metrics()

        logger.info(f"Completed acquisition session {self.session_id}")

    def mark_error(self, error_message: str):
        """Mark session as having an error"""
        self.status = DatasetStatus.ERROR
        self.error_message = error_message
        logger.error(f"Session {self.session_id} marked as error: {error_message}")

    def get_acquisition_duration(self) -> Optional[float]:
        """Get acquisition duration in seconds"""
        if self.started_timestamp and self.completed_timestamp:
            return (self.completed_timestamp - self.started_timestamp).total_seconds()
        return None

    def get_total_frames_captured(self) -> int:
        """Get total frames captured across all directions"""
        return sum(self.frame_counts.values())

    def get_total_dropped_frames(self) -> int:
        """Get total dropped frames across all directions"""
        return sum(self.dropped_frames.values())

    def get_frame_drop_rate(self) -> float:
        """Get overall frame drop rate"""
        total_frames = self.get_total_frames_captured()
        total_dropped = self.get_total_dropped_frames()
        total_expected = total_frames + total_dropped

        return total_dropped / total_expected if total_expected > 0 else 0.0

    def is_ready_for_analysis(self) -> bool:
        """Check if session is ready for analysis"""
        return (
            self.status == DatasetStatus.COMPLETED and
            len(self.camera_files) >= 2 and  # Need at least 2 directions
            len(self.event_files) >= 2 and
            self.get_frame_drop_rate() < 0.1  # Less than 10% frame drops
        )

    def _calculate_quality_metrics(self):
        """Calculate acquisition quality metrics"""
        for direction in self.camera_files.keys():
            # Calculate timing quality (placeholder - would use actual timing analysis)
            frame_count = self.frame_counts.get(direction, 0)
            dropped_count = self.dropped_frames.get(direction, 0)

            if frame_count + dropped_count > 0:
                timing_quality = 1.0 - (dropped_count / (frame_count + dropped_count))
                self.timing_quality[direction] = timing_quality

                # Coverage quality (placeholder - would use actual coverage analysis)
                self.coverage_quality[direction] = 1.0 if frame_count > 100 else frame_count / 100.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "session_id": self.session_id,
            "stimulus_dataset_id": self.stimulus_dataset.dataset_id,
            "session_path": str(self.session_path),
            "streaming_profile": self.streaming_profile.model_dump(),
            "experimenter": self.experimenter,
            "created_timestamp": self.created_timestamp.isoformat(),
            "started_timestamp": self.started_timestamp.isoformat() if self.started_timestamp else None,
            "completed_timestamp": self.completed_timestamp.isoformat() if self.completed_timestamp else None,
            "status": self.status.value,
            "acquisition_progress": self.acquisition_progress,
            "current_direction": self.current_direction,
            "current_trial": self.current_trial,
            "total_trials": self.total_trials,
            "error_message": self.error_message,
            "camera_files": {k: [str(p) for p in v] for k, v in self.camera_files.items()},
            "event_files": {k: str(v) for k, v in self.event_files.items()},
            "frame_counts": self.frame_counts,
            "dropped_frames": self.dropped_frames,
            "timing_quality": self.timing_quality,
            "coverage_quality": self.coverage_quality,
            "hardware_issues": self.hardware_issues
        }


class AnalysisResult:
    """
    Entity representing the results of ISI retinotopic analysis

    Contains generated retinotopic maps, visual field signs,
    area segmentations, and analysis quality metrics.
    """

    def __init__(
        self,
        result_id: str,
        session: AcquisitionSession,
        analysis_parameters: Dict[str, Any],
        analyzer: str = "system"
    ):
        # Identity and relationships
        self.result_id = result_id
        self.session = session
        self.analysis_parameters = analysis_parameters
        self.analyzer = analyzer

        # Timestamps
        self.created_timestamp = datetime.now()
        self.analysis_started: Optional[datetime] = None
        self.analysis_completed: Optional[datetime] = None

        # Status tracking
        self.status = DatasetStatus.READY
        self.analysis_progress = 0.0  # 0.0 to 1.0
        self.current_stage: Optional[str] = None
        self.error_message: Optional[str] = None

        # Analysis results
        self.retinotopic_maps: Dict[str, Any] = {}         # Direction -> phase/amplitude maps
        self.combined_maps: Dict[str, Any] = {}            # Azimuth/elevation combined maps
        self.visual_field_sign: Optional[Any] = None      # Visual field sign map
        self.visual_areas: List[Dict[str, Any]] = []       # Segmented visual areas

        # Quality metrics
        self.correlation_quality: Dict[str, float] = {}    # Direction -> correlation quality
        self.unwrapping_quality: Dict[str, float] = {}     # Direction -> unwrapping quality
        self.overall_quality_score: Optional[float] = None

        # File references
        self.result_files: Dict[str, Path] = {}            # Result type -> file path
        self.export_formats: List[str] = []                # Available export formats

    def start_analysis(self):
        """Start analysis process"""
        self.status = DatasetStatus.PROCESSING
        self.analysis_started = datetime.now()
        self.analysis_progress = 0.0
        logger.info(f"Started analysis {self.result_id} for session {self.session.session_id}")

    def update_progress(self, stage: str, progress: float):
        """Update analysis progress"""
        self.current_stage = stage
        self.analysis_progress = max(0.0, min(1.0, progress))  # Clamp to [0, 1]
        logger.debug(f"Analysis {self.result_id}: {stage} - {progress:.1%}")

    def add_retinotopic_map(self, direction: str, phase_map: Any, amplitude_map: Any, quality: float):
        """Add retinotopic map for a direction"""
        self.retinotopic_maps[direction] = {
            "phase_map": phase_map,
            "amplitude_map": amplitude_map,
            "direction": direction,
            "timestamp": datetime.now().isoformat()
        }
        self.correlation_quality[direction] = quality
        logger.debug(f"Added retinotopic map for {direction} (quality: {quality:.3f})")

    def set_combined_maps(self, azimuth_map: Any, elevation_map: Any):
        """Set combined azimuth and elevation maps"""
        self.combined_maps = {
            "azimuth_map": azimuth_map,
            "elevation_map": elevation_map,
            "timestamp": datetime.now().isoformat()
        }
        logger.debug("Set combined azimuth and elevation maps")

    def set_visual_field_sign(self, sign_map: Any, areas: List[Dict[str, Any]], quality: float):
        """Set visual field sign map and segmented areas"""
        self.visual_field_sign = sign_map
        self.visual_areas = areas
        self.unwrapping_quality["combined"] = quality
        logger.debug(f"Set visual field sign map with {len(areas)} areas (quality: {quality:.3f})")

    def add_result_file(self, result_type: str, file_path: Path):
        """Add result file reference"""
        self.result_files[result_type] = Path(file_path)
        logger.debug(f"Added result file: {result_type} -> {file_path}")

    def complete_analysis(self):
        """Mark analysis as completed"""
        self.status = DatasetStatus.COMPLETED
        self.analysis_completed = datetime.now()
        self.analysis_progress = 1.0
        self.current_stage = None

        # Calculate overall quality score
        self._calculate_overall_quality()

        logger.info(f"Completed analysis {self.result_id} (quality: {self.overall_quality_score:.3f})")

    def mark_error(self, error_message: str):
        """Mark analysis as having an error"""
        self.status = DatasetStatus.ERROR
        self.error_message = error_message
        logger.error(f"Analysis {self.result_id} marked as error: {error_message}")

    def get_analysis_duration(self) -> Optional[float]:
        """Get analysis duration in seconds"""
        if self.analysis_started and self.analysis_completed:
            return (self.analysis_completed - self.analysis_started).total_seconds()
        return None

    def get_available_directions(self) -> List[str]:
        """Get directions with retinotopic maps"""
        return list(self.retinotopic_maps.keys())

    def has_complete_retinotopy(self) -> bool:
        """Check if analysis has complete retinotopic maps"""
        return (
            len(self.combined_maps) > 0 and
            "azimuth_map" in self.combined_maps and
            "elevation_map" in self.combined_maps and
            self.visual_field_sign is not None
        )

    def _calculate_overall_quality(self):
        """Calculate overall analysis quality score"""
        if not self.correlation_quality and not self.unwrapping_quality:
            self.overall_quality_score = 0.0
            return

        # Weight different quality components
        correlation_scores = list(self.correlation_quality.values())
        unwrapping_scores = list(self.unwrapping_quality.values())

        avg_correlation = sum(correlation_scores) / len(correlation_scores) if correlation_scores else 0.0
        avg_unwrapping = sum(unwrapping_scores) / len(unwrapping_scores) if unwrapping_scores else 0.0

        # Combined score with weighting
        self.overall_quality_score = (avg_correlation * 0.6 + avg_unwrapping * 0.4)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "result_id": self.result_id,
            "session_id": self.session.session_id,
            "analysis_parameters": self.analysis_parameters,
            "analyzer": self.analyzer,
            "created_timestamp": self.created_timestamp.isoformat(),
            "analysis_started": self.analysis_started.isoformat() if self.analysis_started else None,
            "analysis_completed": self.analysis_completed.isoformat() if self.analysis_completed else None,
            "status": self.status.value,
            "analysis_progress": self.analysis_progress,
            "current_stage": self.current_stage,
            "error_message": self.error_message,
            "correlation_quality": self.correlation_quality,
            "unwrapping_quality": self.unwrapping_quality,
            "overall_quality_score": self.overall_quality_score,
            "result_files": {k: str(v) for k, v in self.result_files.items()},
            "export_formats": self.export_formats,
            "visual_areas_count": len(self.visual_areas),
            "has_complete_retinotopy": self.has_complete_retinotopy()
        }


