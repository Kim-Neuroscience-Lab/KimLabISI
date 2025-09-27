"""
Analysis Pipeline Use Case - ISI Retinotopic Map Generation

This use case handles the complete post-acquisition analysis pipeline
that correlates stimulus presentation with camera capture data to
generate retinotopic maps using modernized ISI methods.
"""

import asyncio
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from pathlib import Path

from domain.entities.workflow_state_machine import WorkflowStateMachine
from domain.value_objects.workflow_state import (
    WorkflowState, WorkflowTransition, HardwareRequirement
)
from domain.entities.parameter_manager import ParameterManager
from domain.value_objects.parameters import CombinedParameters
from infrastructure.storage.hdf5_repository import HDF5Repository
from infrastructure.storage.session_repository import SessionRepository
from infrastructure.hardware.factory import HardwareFactory
from application.algorithms.fourier_analysis import FourierAnalyzer
from application.algorithms.phase_unwrapping import PhaseUnwrapper
from application.algorithms.sign_map import SignMapCalculator

logger = logging.getLogger(__name__)


class AnalysisPipelineUseCase:
    """Orchestrates the complete ISI analysis pipeline"""

    def __init__(
        self,
        workflow: WorkflowStateMachine,
        parameter_manager: ParameterManager,
        hdf5_repository: HDF5Repository,
        session_repository: SessionRepository,
        hardware_factory: HardwareFactory
    ):
        self.workflow = workflow
        self.parameter_manager = parameter_manager
        self.hdf5_repository = hdf5_repository
        self.session_repository = session_repository
        self.hardware_factory = hardware_factory

        # Analysis state
        self.current_session: Optional[str] = None
        self.analysis_parameters: Optional[CombinedParameters] = None
        self.correlation_data: Optional[Dict] = None
        self.retinotopic_maps: Optional[Dict] = None
        self.analysis_complete = False

    async def start_analysis(self, session_id: str) -> 'AnalysisResult':
        """
        Begin analysis pipeline for a completed acquisition session

        Args:
            session_id: Session identifier to analyze

        Returns:
            AnalysisResult with initial status
        """
        logger.info(f"Starting analysis pipeline for session: {session_id}")

        try:
            # Verify we can transition to ANALYSIS state
            transition = self.workflow.transition_to(
                WorkflowState.ANALYSIS,
                {HardwareRequirement.GPU_SYSTEM}
            )

            if not transition.success:
                return AnalysisResult(
                    success=False,
                    error_message=f"Cannot start analysis: {transition.error_message}",
                    workflow_state=self.workflow.get_current_state()
                )

            # Load session data
            session_data = await self.session_repository.load_session_metadata(session_id)
            if not session_data:
                return AnalysisResult(
                    success=False,
                    error_message=f"Session {session_id} not found"
                )

            self.current_session = session_id

            # Load analysis parameters from session
            parameter_set_id = session_data.get("parameter_set_id", "development_defaults")
            self.analysis_parameters = self.parameter_manager.get_parameters(parameter_set_id)

            # Validate session has required data
            validation_result = await self._validate_session_data(session_id)
            if not validation_result.is_valid:
                return AnalysisResult(
                    success=False,
                    error_message="Session validation failed",
                    validation_errors=validation_result.errors
                )

            return AnalysisResult(
                success=True,
                session_id=session_id,
                workflow_state=WorkflowState.ANALYSIS,
                analysis_parameters=self.analysis_parameters,
                available_directions=validation_result.available_directions
            )

        except Exception as e:
            logger.exception("Error starting analysis pipeline")
            return AnalysisResult(
                success=False,
                error_message=f"Analysis initialization failed: {str(e)}"
            )

    async def correlate_stimulus_camera_data(self) -> 'CorrelationResult':
        """
        Correlate stimulus presentation with camera capture data

        Returns:
            CorrelationResult with correlation status and data
        """
        logger.info("Correlating stimulus and camera data")

        try:
            if not self.current_session or not self.analysis_parameters:
                return CorrelationResult(
                    success=False,
                    error_message="No active analysis session"
                )

            # Load stimulus events and camera frames
            stimulus_events = await self._load_stimulus_events()
            camera_frames = await self._load_camera_frames()

            if not stimulus_events or not camera_frames:
                return CorrelationResult(
                    success=False,
                    error_message="Missing stimulus or camera data"
                )

            # Perform temporal correlation
            correlation_data = await self._perform_correlation(stimulus_events, camera_frames)

            # Validate correlation quality
            quality_metrics = self._assess_correlation_quality(correlation_data)

            self.correlation_data = {
                "correlation_data": correlation_data,
                "quality_metrics": quality_metrics,
                "timestamp": datetime.now().isoformat()
            }

            logger.info(f"Correlation completed: {quality_metrics['frames_correlated']} frames processed")

            return CorrelationResult(
                success=True,
                frames_correlated=quality_metrics["frames_correlated"],
                correlation_quality=quality_metrics["correlation_quality"],
                timing_precision_us=quality_metrics["timing_precision_us"],
                available_directions=quality_metrics["available_directions"]
            )

        except Exception as e:
            logger.exception("Error during stimulus-camera correlation")
            return CorrelationResult(
                success=False,
                error_message=f"Correlation failed: {str(e)}"
            )

    async def generate_retinotopic_maps(self, analysis_options: Optional[Dict] = None) -> 'RetinotopicResult':
        """
        Generate retinotopic maps using ISI analysis methods

        Args:
            analysis_options: Optional analysis parameter overrides

        Returns:
            RetinotopicResult with generated maps
        """
        logger.info("Generating retinotopic maps")

        try:
            if not self.correlation_data:
                return RetinotopicResult(
                    success=False,
                    error_message="No correlation data available for analysis"
                )

            # Initialize analysis algorithms
            fourier_analyzer = FourierAnalyzer()
            phase_unwrapper = PhaseUnwrapper()
            sign_map_calculator = SignMapCalculator()

            # Get GPU manager for acceleration
            gpu_manager = await self.hardware_factory.create_gpu_manager()
            gpu_available = await gpu_manager.is_available()

            analysis_results = {}

            # Process each direction (LR, RL, TB, BT)
            for direction in ["LR", "RL", "TB", "BT"]:
                direction_data = self.correlation_data["correlation_data"].get(direction)
                if not direction_data:
                    logger.warning(f"No correlation data for direction {direction}")
                    continue

                logger.info(f"Processing direction: {direction}")

                # Phase 1: Fourier analysis for ISI signals
                fourier_result = await fourier_analyzer.analyze_isi_signal(
                    direction_data["frames"],
                    direction_data["angles"],
                    use_gpu=gpu_available
                )

                # Phase 2: Phase unwrapping and map generation
                phase_maps = await phase_unwrapper.unwrap_phase_maps(
                    fourier_result["phase_map"],
                    fourier_result["amplitude_map"]
                )

                analysis_results[direction] = {
                    "phase_map": phase_maps["unwrapped_phase"],
                    "amplitude_map": fourier_result["amplitude_map"],
                    "coherence_map": fourier_result["coherence_map"],
                    "quality_metrics": phase_maps["quality_metrics"]
                }

            # Phase 3: Generate combined retinotopic coordinates
            if "LR" in analysis_results and "RL" in analysis_results:
                horizontal_map = self._combine_opposing_directions(
                    analysis_results["LR"]["phase_map"],
                    analysis_results["RL"]["phase_map"]
                )
            else:
                horizontal_map = None

            if "TB" in analysis_results and "BT" in analysis_results:
                vertical_map = self._combine_opposing_directions(
                    analysis_results["TB"]["phase_map"],
                    analysis_results["BT"]["phase_map"]
                )
            else:
                vertical_map = None

            # Phase 4: Visual field sign calculation
            visual_field_sign = None
            if horizontal_map is not None and vertical_map is not None:
                visual_field_sign = await sign_map_calculator.calculate_visual_field_sign(
                    horizontal_map["azimuth_map"],
                    vertical_map["elevation_map"]
                )

            # Compile final results
            self.retinotopic_maps = {
                "horizontal_retinotopy": horizontal_map,
                "vertical_retinotopy": vertical_map,
                "visual_field_sign": visual_field_sign,
                "direction_maps": analysis_results,
                "analysis_timestamp": datetime.now().isoformat(),
                "analysis_parameters": self.analysis_parameters.model_dump() if self.analysis_parameters else None
            }

            # Save analysis results
            await self._save_analysis_results()

            return RetinotopicResult(
                success=True,
                horizontal_map_available=horizontal_map is not None,
                vertical_map_available=vertical_map is not None,
                visual_field_sign_available=visual_field_sign is not None,
                directions_processed=list(analysis_results.keys()),
                analysis_quality=self._calculate_overall_quality(analysis_results)
            )

        except Exception as e:
            logger.exception("Error generating retinotopic maps")
            return RetinotopicResult(
                success=False,
                error_message=f"Retinotopic analysis failed: {str(e)}"
            )

    async def finalize_analysis(self, export_formats: Optional[List[str]] = None) -> 'AnalysisResult':
        """
        Complete analysis and export results

        Args:
            export_formats: List of export formats (png, hdf5, matlab, etc.)

        Returns:
            Final AnalysisResult
        """
        logger.info("Finalizing analysis pipeline")

        try:
            if not self.retinotopic_maps:
                return AnalysisResult(
                    success=False,
                    error_message="No analysis results to finalize"
                )

            # Export in requested formats
            export_paths = []
            if export_formats:
                for format_type in export_formats:
                    try:
                        export_path = await self._export_results(format_type)
                        export_paths.append(export_path)
                        logger.info(f"Exported results to {export_path}")
                    except Exception as e:
                        logger.warning(f"Could not export to {format_type}: {e}")

            # Mark analysis as complete
            self.analysis_complete = True

            # Attempt to transition workflow
            transition = self.workflow.transition_to(
                WorkflowState.SETUP_READY,
                set()  # Analysis complete, ready for next experiment
            )

            logger.info("Analysis pipeline completed successfully")

            return AnalysisResult(
                success=True,
                session_id=self.current_session,
                workflow_state=transition.new_state if transition.success else self.workflow.get_current_state(),
                analysis_complete=True,
                export_paths=export_paths,
                retinotopic_maps_available=True
            )

        except Exception as e:
            logger.exception("Error finalizing analysis")
            return AnalysisResult(
                success=False,
                error_message=f"Analysis finalization failed: {str(e)}"
            )

    async def _validate_session_data(self, session_id: str) -> 'SessionValidation':
        """Validate that session has required data for analysis"""
        errors = []
        available_directions = []

        try:
            # Check for stimulus event files
            session_path = await self.session_repository.get_session_path(session_id)

            for direction in ["LR", "RL", "TB", "BT"]:
                events_file = session_path / "acquisition" / "stimulus_events" / f"{direction}_events.csv"
                frames_file = session_path / "acquisition" / "camera_frames" / f"{direction}_trial_001.h5"

                if events_file.exists() and frames_file.exists():
                    available_directions.append(direction)
                else:
                    errors.append(f"Missing data for direction {direction}")

            if len(available_directions) < 2:
                errors.append("Need at least 2 directions for analysis")

        except Exception as e:
            errors.append(f"Session validation error: {str(e)}")

        return SessionValidation(
            is_valid=len(errors) == 0,
            errors=errors,
            available_directions=available_directions
        )

    async def _load_stimulus_events(self) -> Optional[Dict]:
        """Load stimulus presentation events"""
        # Implementation would load CSV files with timing data
        # This is a placeholder for the actual data loading logic
        logger.debug("Loading stimulus events (placeholder)")
        return {"LR": [], "RL": [], "TB": [], "BT": []}

    async def _load_camera_frames(self) -> Optional[Dict]:
        """Load camera frame data"""
        # Implementation would load HDF5 camera frame data
        # This is a placeholder for the actual data loading logic
        logger.debug("Loading camera frames (placeholder)")
        return {"LR": [], "RL": [], "TB": [], "BT": []}

    async def _perform_correlation(self, stimulus_events: Dict, camera_frames: Dict) -> Dict:
        """Perform temporal correlation between stimulus and camera data"""
        # Implementation would do actual timestamp-based correlation
        # This is a placeholder for the correlation algorithm
        logger.debug("Performing correlation (placeholder)")
        return {
            "LR": {"frames": [], "angles": []},
            "RL": {"frames": [], "angles": []},
            "TB": {"frames": [], "angles": []},
            "BT": {"frames": [], "angles": []}
        }

    def _assess_correlation_quality(self, correlation_data: Dict) -> Dict:
        """Assess quality of correlation results"""
        return {
            "frames_correlated": sum(len(data.get("frames", [])) for data in correlation_data.values()),
            "correlation_quality": 0.95,  # Placeholder
            "timing_precision_us": 100,   # Placeholder
            "available_directions": list(correlation_data.keys())
        }

    def _combine_opposing_directions(self, forward_map: np.ndarray, reverse_map: np.ndarray) -> Dict:
        """Combine opposing direction phase maps to get retinotopic coordinates"""
        # Placeholder for actual phase map combination
        return {
            "azimuth_map": np.zeros((100, 100)),  # Placeholder
            "elevation_map": np.zeros((100, 100))  # Placeholder
        }

    def _calculate_overall_quality(self, analysis_results: Dict) -> float:
        """Calculate overall analysis quality score"""
        # Placeholder for quality calculation
        return 0.85

    async def _save_analysis_results(self):
        """Save analysis results to session directory"""
        # Implementation would save results to HDF5/filesystem
        logger.debug("Saving analysis results (placeholder)")

    async def _export_results(self, format_type: str) -> str:
        """Export results in specified format"""
        # Implementation would export to various formats
        return f"/path/to/exported/results.{format_type}"


class AnalysisResult:
    """Result of analysis pipeline operations"""

    def __init__(
        self,
        success: bool,
        session_id: Optional[str] = None,
        workflow_state: Optional[WorkflowState] = None,
        error_message: Optional[str] = None,
        validation_errors: Optional[List[str]] = None,
        analysis_parameters: Optional[CombinedParameters] = None,
        available_directions: Optional[List[str]] = None,
        analysis_complete: bool = False,
        export_paths: Optional[List[str]] = None,
        retinotopic_maps_available: bool = False
    ):
        self.success = success
        self.session_id = session_id
        self.workflow_state = workflow_state
        self.error_message = error_message
        self.validation_errors = validation_errors or []
        self.analysis_parameters = analysis_parameters
        self.available_directions = available_directions or []
        self.analysis_complete = analysis_complete
        self.export_paths = export_paths or []
        self.retinotopic_maps_available = retinotopic_maps_available
        self.timestamp = datetime.now()


class CorrelationResult:
    """Result of stimulus-camera correlation"""

    def __init__(
        self,
        success: bool,
        frames_correlated: int = 0,
        correlation_quality: float = 0.0,
        timing_precision_us: float = 0.0,
        available_directions: Optional[List[str]] = None,
        error_message: Optional[str] = None
    ):
        self.success = success
        self.frames_correlated = frames_correlated
        self.correlation_quality = correlation_quality
        self.timing_precision_us = timing_precision_us
        self.available_directions = available_directions or []
        self.error_message = error_message


class RetinotopicResult:
    """Result of retinotopic map generation"""

    def __init__(
        self,
        success: bool,
        horizontal_map_available: bool = False,
        vertical_map_available: bool = False,
        visual_field_sign_available: bool = False,
        directions_processed: Optional[List[str]] = None,
        analysis_quality: float = 0.0,
        error_message: Optional[str] = None
    ):
        self.success = success
        self.horizontal_map_available = horizontal_map_available
        self.vertical_map_available = vertical_map_available
        self.visual_field_sign_available = visual_field_sign_available
        self.directions_processed = directions_processed or []
        self.analysis_quality = analysis_quality
        self.error_message = error_message


class SessionValidation:
    """Session data validation result"""

    def __init__(self, is_valid: bool, errors: List[str], available_directions: List[str]):
        self.is_valid = is_valid
        self.errors = errors
        self.available_directions = available_directions