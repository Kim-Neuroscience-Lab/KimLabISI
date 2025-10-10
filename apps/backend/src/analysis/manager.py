"""Analysis Manager - Orchestrates ISI analysis pipeline.

Manages the complete analysis workflow from data loading through result generation.
All dependencies injected via constructor - NO service locator pattern.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
import json
import numpy as np
import h5py

from config import AnalysisConfig, AcquisitionConfig
from ipc.channels import MultiChannelIPC
from ipc.shared_memory import SharedMemoryService
from .pipeline import AnalysisPipeline

logger = logging.getLogger(__name__)


class SessionData:
    """Container for loaded acquisition session data."""

    def __init__(self):
        self.metadata: Dict[str, Any] = {}
        self.anatomical: Optional[np.ndarray] = None
        self.directions: Dict[str, DirectionData] = {}


class DirectionData:
    """Container for single direction acquisition data."""

    def __init__(self):
        self.frames: Optional[np.ndarray] = None
        self.timestamps: Optional[np.ndarray] = None
        self.stimulus_angles: Optional[np.ndarray] = None
        self.events: Optional[List[Dict[str, Any]]] = None


class AnalysisResults:
    """Container for analysis results."""

    def __init__(self):
        self.phase_maps: Dict[str, np.ndarray] = {}
        self.magnitude_maps: Dict[str, np.ndarray] = {}
        self.azimuth_map: Optional[np.ndarray] = None
        self.elevation_map: Optional[np.ndarray] = None
        self.gradients: Optional[Dict[str, np.ndarray]] = None
        self.sign_map: Optional[np.ndarray] = None
        self.boundary_map: Optional[np.ndarray] = None
        self.area_map: Optional[np.ndarray] = None


class AnalysisManager:
    """Manages ISI analysis pipeline with IPC integration.

    Orchestrates the complete analysis workflow including data loading,
    Fourier analysis, retinotopic mapping, and result visualization.
    All dependencies injected via constructor.
    """

    def __init__(
        self,
        config: AnalysisConfig,
        acquisition_config: AcquisitionConfig,
        ipc: MultiChannelIPC,
        shared_memory: SharedMemoryService,
        pipeline: AnalysisPipeline
    ):
        """Initialize analysis manager.

        Args:
            config: Analysis configuration
            acquisition_config: Acquisition configuration (for directions, cycles)
            ipc: IPC communication channels
            shared_memory: Shared memory service for frame streaming
            pipeline: Analysis pipeline for Fourier computations
        """
        self.config = config
        self.acquisition_config = acquisition_config
        self.ipc = ipc
        self.shared_memory = shared_memory
        self.pipeline = pipeline

        # State tracking
        self.is_running = False
        self.current_session_path: Optional[str] = None
        self.analysis_thread: Optional[threading.Thread] = None
        self.progress = 0.0
        self.current_stage = "idle"
        self.error: Optional[str] = None
        self.results: Optional[AnalysisResults] = None

        # Import renderer for layer visualization
        from .renderer import AnalysisRenderer
        self.renderer = AnalysisRenderer(config, shared_memory)

        logger.info("AnalysisManager initialized")

    def _send_layer_ready(self, layer_name: str, layer_data: np.ndarray, session_path: str):
        """Send intermediate layer visualization to frontend.

        Renders the layer to PNG, encodes as base64, and sends via IPC.

        Args:
            layer_name: Name of the layer (e.g., 'azimuth_map', 'sign_map')
            layer_data: Layer data array
            session_path: Session path for context
        """
        import base64

        try:
            logger.info(f"Rendering intermediate layer: {layer_name} {layer_data.shape}")

            # Render based on layer type
            if layer_name == 'azimuth_map':
                rgb_image = self.renderer.render_retinotopic_map(layer_data, 'azimuth')
            elif layer_name == 'elevation_map':
                rgb_image = self.renderer.render_retinotopic_map(layer_data, 'elevation')
            elif layer_name == 'sign_map':
                rgb_image = self.renderer.render_sign_map(layer_data)
            elif layer_name == 'boundary_map':
                # Render boundary map (RGBA -> RGB on black background)
                boundary_rgba = self.renderer.render_boundary_map(layer_data)
                rgb_image = np.zeros((boundary_rgba.shape[0], boundary_rgba.shape[1], 3), dtype=np.uint8)
                alpha = boundary_rgba[:, :, 3:4].astype(np.float32) / 255.0
                rgb_image = (boundary_rgba[:, :, :3].astype(np.float32) * alpha).astype(np.uint8)
            else:
                # Default: render as amplitude map
                rgb_image = self.renderer.render_amplitude_map(layer_data)

            # Encode as PNG
            png_bytes = self.renderer.encode_as_png(rgb_image)
            if not png_bytes:
                logger.error(f"Failed to encode {layer_name} as PNG")
                return

            # Encode as base64 for JSON transmission
            png_base64 = base64.b64encode(png_bytes).decode('utf-8')

            logger.info(f"Rendered {layer_name} to PNG: {len(png_bytes)} bytes")

            # Send layer_ready message
            self._send_sync_message({
                "type": "analysis_layer_ready",
                "layer_name": layer_name,
                "image_base64": png_base64,
                "width": rgb_image.shape[1],
                "height": rgb_image.shape[0],
                "format": "png",
                "session_path": session_path,
                "timestamp": time.time(),
            })

            logger.info(f"Sent layer_ready message for {layer_name}")

        except Exception as e:
            logger.error(f"Failed to send layer_ready for {layer_name}: {e}", exc_info=True)

    def start_analysis(self, session_path: str) -> Dict[str, Any]:
        """Start analysis on a recorded session.

        Args:
            session_path: Path to session directory

        Returns:
            Success response with analysis info or error response
        """
        # Validate not already running
        if self.is_running:
            return self._format_error("Analysis already running")

        # Validate session exists
        session_path_obj = Path(session_path)
        if not session_path_obj.exists():
            return self._format_error(f"Session directory not found: {session_path}")

        # Validate session has required files
        metadata_file = session_path_obj / "metadata.json"
        if not metadata_file.exists():
            return self._format_error(f"Session missing metadata.json")

        # Check for data files
        has_data = False
        for direction in self.acquisition_config.directions:
            camera_file = session_path_obj / f"{direction}_camera.h5"
            if camera_file.exists():
                has_data = True
                break

        if not has_data:
            return self._format_error("Session contains no camera data files")

        # Initialize state
        self.current_session_path = session_path
        self.is_running = True
        self.progress = 0.0
        self.current_stage = "starting"
        self.error = None
        self.results = None

        logger.info(f"Starting analysis for session: {session_path}")

        # Start analysis in background thread
        self.analysis_thread = threading.Thread(
            target=self._run_analysis,
            args=(session_path,),
            daemon=True,
            name="AnalysisThread"
        )
        self.analysis_thread.start()

        return self._format_success("Analysis started", session_path=session_path)

    def stop_analysis(self) -> Dict[str, Any]:
        """Request to stop running analysis.

        Note: Analysis cannot be truly cancelled mid-execution due to numpy
        operations, but this will mark it as stopped.

        Returns:
            Success response or error if no analysis running
        """
        if not self.is_running:
            return self._format_error("No analysis currently running")

        logger.warning("Analysis stop requested")
        self.is_running = False
        self.current_stage = "stopping"

        return self._format_success("Analysis will complete current stage and stop")

    def get_status(self) -> Dict[str, Any]:
        """Get current analysis status.

        Returns:
            Status information including progress, stage, errors
        """
        return {
            "success": True,
            "is_running": self.is_running,
            "session_path": self.current_session_path,
            "progress": self.progress,
            "stage": self.current_stage,
            "error": self.error,
            "has_results": self.results is not None,
        }

    def _run_analysis(self, session_path: str):
        """Background thread for running analysis.

        Args:
            session_path: Path to session directory
        """
        try:
            # Send started message
            self.current_stage = "started"
            self._send_progress(0.0, "Analysis started")

            # Stage 1: Load session data (0% -> 10%)
            if not self.is_running:
                return

            self.progress = 0.0
            self.current_stage = "loading_data"
            self._send_progress(0.0, "Loading session data")

            session_data = self._load_acquisition_data(session_path)
            logger.info("Session data loaded successfully")

            # Stage 2: Process each direction (10% -> 70%)
            if not self.is_running:
                return

            directions = self.acquisition_config.directions
            logger.info(f"Processing {len(directions)} directions: {directions}")

            phase_maps = {}
            magnitude_maps = {}

            for i, direction in enumerate(directions):
                if not self.is_running:
                    return

                # Update progress proportionally
                progress = 0.1 + (i / len(directions)) * 0.6
                self.progress = progress
                self.current_stage = f"processing_{direction}"
                self._send_progress(progress, f"Processing {direction} direction")

                # Process this direction
                frames = session_data.directions[direction].frames
                angles = session_data.directions[direction].stimulus_angles

                if frames is None or angles is None:
                    logger.warning(f"Skipping {direction}: missing data")
                    continue

                # Compute FFT phase maps
                stimulus_freq = self.acquisition_config.cycles / len(frames)
                phase_map, magnitude_map = self.pipeline.compute_fft_phase_maps(
                    frames, stimulus_freq
                )

                phase_maps[direction] = phase_map
                magnitude_maps[direction] = magnitude_map

            # Stage 3: Generate retinotopic maps (70% -> 85%)
            if not self.is_running:
                return

            self.progress = 0.7
            self.current_stage = "retinotopic_mapping"
            self._send_progress(0.7, "Generating retinotopic maps")

            # Generate azimuth map (horizontal)
            azimuth_map = None
            if 'LR' in phase_maps and 'RL' in phase_maps:
                azimuth_map = self.pipeline.generate_azimuth_map(
                    phase_maps['LR'], phase_maps['RL']
                )
                # Send intermediate result to frontend
                self._send_layer_ready('azimuth_map', azimuth_map, session_path)

            # Generate elevation map (vertical)
            elevation_map = None
            if 'TB' in phase_maps and 'BT' in phase_maps:
                elevation_map = self.pipeline.generate_elevation_map(
                    phase_maps['TB'], phase_maps['BT']
                )
                # Send intermediate result to frontend
                self._send_layer_ready('elevation_map', elevation_map, session_path)

            # Stage 4: Visual field sign analysis (85% -> 90%)
            if not self.is_running:
                return

            self.progress = 0.85
            self.current_stage = "visual_field_sign"
            self._send_progress(0.85, "Computing visual field sign")

            gradients = None
            sign_map = None
            boundary_map = None
            area_map = None

            if azimuth_map is not None and elevation_map is not None:
                gradients = self.pipeline.compute_spatial_gradients(
                    azimuth_map, elevation_map
                )
                sign_map = self.pipeline.calculate_visual_field_sign(gradients)

                # Send intermediate result to frontend
                self._send_layer_ready('sign_map', sign_map, session_path)

                boundary_map = self.pipeline.detect_area_boundaries(sign_map)

                # Send intermediate result to frontend
                self._send_layer_ready('boundary_map', boundary_map, session_path)

                area_map = self.pipeline.segment_visual_areas(sign_map, boundary_map)

            # Stage 5: Save results (90% -> 100%)
            if not self.is_running:
                return

            self.progress = 0.9
            self.current_stage = "saving_results"
            self._send_progress(0.9, "Saving results")

            # Store results
            results = AnalysisResults()
            results.phase_maps = phase_maps
            results.magnitude_maps = magnitude_maps
            results.azimuth_map = azimuth_map
            results.elevation_map = elevation_map
            results.gradients = gradients
            results.sign_map = sign_map
            results.boundary_map = boundary_map
            results.area_map = area_map

            self.results = results

            # Save to disk
            output_path = Path(session_path) / "analysis_results"
            self._save_results(output_path, results, session_data)

            # Extract summary
            num_areas = int(np.max(area_map)) if area_map is not None else 0

            self.progress = 1.0
            self.current_stage = "complete"

            # Send completion message
            self._send_sync_message({
                "type": "analysis_complete",
                "session_path": session_path,
                "output_path": str(output_path),
                "num_areas": num_areas,
                "success": True,
                "timestamp": time.time(),
            })

            logger.info(f"Analysis complete: {num_areas} visual areas")

        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            self.error = str(e)
            self.current_stage = "error"

            self._send_sync_message({
                "type": "analysis_error",
                "error": str(e),
                "session_path": session_path,
                "timestamp": time.time(),
            })

        finally:
            self.is_running = False
            logger.info("Analysis thread finished")

    def _load_acquisition_data(self, session_path: str) -> SessionData:
        """Load all data from acquisition session.

        Args:
            session_path: Path to session directory

        Returns:
            SessionData container with all loaded data
        """
        logger.info(f"Loading session data from: {session_path}")
        session_path_obj = Path(session_path)

        session_data = SessionData()

        # Load metadata
        metadata_path = session_path_obj / "metadata.json"
        with open(metadata_path, 'r') as f:
            session_data.metadata = json.load(f)

        # Load anatomical image if exists
        anatomical_path = session_path_obj / "anatomical.npy"
        if anatomical_path.exists():
            anatomical = np.load(anatomical_path)

            # Crop anatomical to square centered on smallest dimension
            if len(anatomical.shape) >= 2:
                height, width = anatomical.shape[:2]
                min_dim = min(height, width)

                # Calculate centered crop coordinates
                y_start = (height - min_dim) // 2
                x_start = (width - min_dim) // 2
                y_end = y_start + min_dim
                x_end = x_start + min_dim

                # Crop anatomical image
                anatomical = anatomical[y_start:y_end, x_start:x_end]
                logger.info(f"  Cropped anatomical to square: {anatomical.shape[0]}x{anatomical.shape[1]} (from {height}x{width})")

            session_data.anatomical = anatomical
            logger.info(f"  Loaded anatomical image: {session_data.anatomical.shape}")

        # Load data for each direction
        for direction in self.acquisition_config.directions:
            logger.info(f"  Loading {direction} data...")

            direction_data = DirectionData()

            # Load camera data
            camera_path = session_path_obj / f"{direction}_camera.h5"
            if camera_path.exists():
                with h5py.File(camera_path, 'r') as f:
                    frames = f['frames'][:]
                    timestamps = f['timestamps'][:]

                    # Convert RGB/BGR frames to grayscale if needed
                    if len(frames.shape) == 4 and frames.shape[3] == 3:
                        logger.info(f"    Converting BGR frames to grayscale...")
                        # BGR to grayscale: 0.114*B + 0.587*G + 0.299*R
                        frames = np.dot(frames[..., :3], [0.114, 0.587, 0.299])
                        frames = frames.astype(np.uint8)

                    # Crop to square centered on smallest dimension
                    if len(frames.shape) >= 3:
                        num_frames, height, width = frames.shape[:3]
                        min_dim = min(height, width)

                        # Calculate centered crop coordinates
                        y_start = (height - min_dim) // 2
                        x_start = (width - min_dim) // 2
                        y_end = y_start + min_dim
                        x_end = x_start + min_dim

                        # Crop all frames
                        frames = frames[:, y_start:y_end, x_start:x_end]
                        logger.info(f"    Cropped to square: {frames.shape[1]}x{frames.shape[2]} (from {height}x{width})")

                    direction_data.frames = frames
                    direction_data.timestamps = timestamps
                    logger.info(f"    Camera: {frames.shape} dtype={frames.dtype}")

            # Load stimulus events
            events_path = session_path_obj / f"{direction}_events.json"
            if events_path.exists():
                with open(events_path, 'r') as f:
                    direction_data.events = json.load(f)

            # Load stimulus angles
            stimulus_path = session_path_obj / f"{direction}_stimulus.h5"
            if stimulus_path.exists():
                with h5py.File(stimulus_path, 'r') as f:
                    direction_data.stimulus_angles = f['angles'][:]

            session_data.directions[direction] = direction_data

        logger.info("Session data loaded successfully")
        return session_data

    def _save_results(
        self,
        output_path: Path,
        results: AnalysisResults,
        session_data: SessionData
    ):
        """Save all analysis results.

        Args:
            output_path: Directory to save results
            results: Analysis results to save
            session_data: Original session data
        """
        logger.info(f"Saving results to {output_path}")
        output_path.mkdir(parents=True, exist_ok=True)

        # Save main results as HDF5
        results_path = output_path / "analysis_results.h5"
        with h5py.File(results_path, 'w') as f:
            # Retinotopic maps
            if results.azimuth_map is not None:
                f.create_dataset('azimuth_map', data=results.azimuth_map)
            if results.elevation_map is not None:
                f.create_dataset('elevation_map', data=results.elevation_map)
            if results.sign_map is not None:
                f.create_dataset('sign_map', data=results.sign_map)
            if results.area_map is not None:
                f.create_dataset('area_map', data=results.area_map)
            if results.boundary_map is not None:
                f.create_dataset('boundary_map', data=results.boundary_map)

            # Phase maps for each direction
            if results.phase_maps:
                phase_group = f.create_group('phase_maps')
                for direction, phase_map in results.phase_maps.items():
                    phase_group.create_dataset(direction, data=phase_map)

            # Magnitude maps for each direction
            if results.magnitude_maps:
                magnitude_group = f.create_group('magnitude_maps')
                for direction, magnitude_map in results.magnitude_maps.items():
                    magnitude_group.create_dataset(direction, data=magnitude_map)

        logger.info(f"Results saved to {output_path}")

    def _send_progress(self, progress: float, stage: str):
        """Send progress update via IPC.

        Args:
            progress: Progress value 0.0-1.0
            stage: Current stage description
        """
        self._send_sync_message({
            "type": "analysis_progress",
            "progress": progress,
            "stage": stage,
            "timestamp": time.time(),
        })

    def _send_sync_message(self, message: Dict[str, Any]):
        """Send message via IPC sync channel.

        Args:
            message: Message to send
        """
        try:
            self.ipc.send_sync_message(message)
        except Exception as e:
            logger.error(f"Failed to send IPC message: {e}")

    def _format_success(self, message: str, **kwargs) -> Dict[str, Any]:
        """Format success response.

        Args:
            message: Success message
            **kwargs: Additional response fields

        Returns:
            Success response dictionary
        """
        return {
            "success": True,
            "message": message,
            **kwargs
        }

    def _format_error(self, message: str) -> Dict[str, Any]:
        """Format error response.

        Args:
            message: Error message

        Returns:
            Error response dictionary
        """
        return {
            "success": False,
            "error": message
        }
