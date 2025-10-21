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
        self.has_camera_data: bool = False  # True if raw camera frames, False if pre-computed phase maps


class DirectionData:
    """Container for single direction acquisition data."""

    def __init__(self):
        # Raw acquisition data
        self.frames: Optional[np.ndarray] = None
        self.timestamps: Optional[np.ndarray] = None
        self.stimulus_angles: Optional[np.ndarray] = None
        self.events: Optional[List[Dict[str, Any]]] = None

        # Pre-computed phase/magnitude data (alternative to raw frames)
        self.phase_map: Optional[np.ndarray] = None
        self.magnitude_map: Optional[np.ndarray] = None


class AnalysisResults:
    """Container for analysis results."""

    def __init__(self):
        self.phase_maps: Dict[str, np.ndarray] = {}
        self.magnitude_maps: Dict[str, np.ndarray] = {}
        self.coherence_maps: Dict[str, np.ndarray] = {}
        self.azimuth_map: Optional[np.ndarray] = None
        self.elevation_map: Optional[np.ndarray] = None
        self.gradients: Optional[Dict[str, np.ndarray]] = None
        self.raw_vfs_map: Optional[np.ndarray] = None
        self.coherence_vfs_map: Optional[np.ndarray] = None  # PRIMARY: Coherence-thresholded (literature standard)
        self.magnitude_vfs_map: Optional[np.ndarray] = None  # ALTERNATIVE: Magnitude-thresholded
        self.statistical_vfs_map: Optional[np.ndarray] = None  # ALTERNATIVE: Statistical-thresholded
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
        param_manager,
        ipc: MultiChannelIPC,
        shared_memory: SharedMemoryService,
        pipeline: AnalysisPipeline
    ):
        """Initialize analysis manager.

        Args:
            param_manager: ParameterManager instance (Single Source of Truth)
            ipc: IPC communication channels
            shared_memory: Shared memory service for frame streaming
            pipeline: Analysis pipeline for Fourier computations
        """
        self.param_manager = param_manager
        self.ipc = ipc
        self.shared_memory = shared_memory
        self.pipeline = pipeline

        # Subscribe to analysis parameter changes
        self.param_manager.subscribe("analysis", self._handle_analysis_params_changed)

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
        # Get current analysis config from param_manager
        analysis_params = self.param_manager.get_parameter_group("analysis")

        # Validate ALL parameters explicitly - NO hardcoded defaults
        # Parameter Manager is the Single Source of Truth
        coherence_threshold = analysis_params.get("coherence_threshold")
        if coherence_threshold is None:
            raise RuntimeError(
                "coherence_threshold is required but not configured in param_manager. "
                "Please set analysis.coherence_threshold parameter."
            )

        magnitude_threshold = analysis_params.get("magnitude_threshold")
        if magnitude_threshold is None:
            raise RuntimeError(
                "magnitude_threshold is required but not configured in param_manager. "
                "Please set analysis.magnitude_threshold parameter."
            )

        smoothing_sigma = analysis_params.get("smoothing_sigma")
        if smoothing_sigma is None:
            raise RuntimeError(
                "smoothing_sigma is required but not configured in param_manager. "
                "Please set analysis.smoothing_sigma parameter."
            )

        vfs_threshold_sd = analysis_params.get("vfs_threshold_sd")
        if vfs_threshold_sd is None:
            raise RuntimeError(
                "vfs_threshold_sd is required but not configured in param_manager. "
                "Please set analysis.vfs_threshold_sd parameter."
            )

        ring_size_mm = analysis_params.get("ring_size_mm")
        if ring_size_mm is None:
            raise RuntimeError(
                "ring_size_mm is required but not configured in param_manager. "
                "Please set analysis.ring_size_mm parameter."
            )

        phase_filter_sigma = analysis_params.get("phase_filter_sigma")
        if phase_filter_sigma is None:
            raise RuntimeError(
                "phase_filter_sigma is required but not configured in param_manager. "
                "Please set analysis.phase_filter_sigma parameter."
            )

        gradient_window_size = analysis_params.get("gradient_window_size")
        if gradient_window_size is None:
            raise RuntimeError(
                "gradient_window_size is required but not configured in param_manager. "
                "Please set analysis.gradient_window_size parameter."
            )

        response_threshold_percent = analysis_params.get("response_threshold_percent")
        if response_threshold_percent is None:
            raise RuntimeError(
                "response_threshold_percent is required but not configured in param_manager. "
                "Please set analysis.response_threshold_percent parameter."
            )

        area_min_size_mm2 = analysis_params.get("area_min_size_mm2")
        if area_min_size_mm2 is None:
            raise RuntimeError(
                "area_min_size_mm2 is required but not configured in param_manager. "
                "Please set analysis.area_min_size_mm2 parameter."
            )

        # Create a compatibility config object with validated parameters (NO defaults)
        from config import AnalysisConfig
        config = AnalysisConfig(
            coherence_threshold=float(coherence_threshold),
            magnitude_threshold=float(magnitude_threshold),
            smoothing_sigma=float(smoothing_sigma),
            vfs_threshold_sd=float(vfs_threshold_sd),
            ring_size_mm=float(ring_size_mm),
            phase_filter_sigma=float(phase_filter_sigma),
            gradient_window_size=int(gradient_window_size),
            response_threshold_percent=float(response_threshold_percent),
            area_min_size_mm2=float(area_min_size_mm2)
        )
        self.renderer = AnalysisRenderer(config, shared_memory)

        logger.info("AnalysisManager initialized with ParameterManager")

    def _handle_analysis_params_changed(self, group_name: str, updates: Dict[str, Any]):
        """React to analysis parameter changes.

        Args:
            group_name: Parameter group that changed ("analysis")
            updates: Dictionary of updated parameters
        """
        logger.info(f"Analysis parameters changed: {list(updates.keys())}")
        # Analysis parameters are typically used at analysis time, not continuously

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

        # Check for data files - accept EITHER camera frames OR phase/magnitude maps
        has_camera_data = False
        has_phase_maps = False

        # Get acquisition directions from parameter manager
        acquisition_params = self.param_manager.get_parameter_group("acquisition")
        directions = acquisition_params.get("directions", ["LR", "RL", "TB", "BT"])

        # Check for raw camera frames
        for direction in directions:
            camera_file = session_path_obj / f"{direction}_camera.h5"
            if camera_file.exists():
                has_camera_data = True
                break

        # Check for pre-computed phase/magnitude maps (e.g., from MATLAB)
        for direction in directions:
            phase_file = session_path_obj / f"phase_{direction}.npy"
            magnitude_file = session_path_obj / f"magnitude_{direction}.npy"
            if phase_file.exists() and magnitude_file.exists():
                has_phase_maps = True
                break

        if not has_camera_data and not has_phase_maps:
            return self._format_error(
                "Session contains neither camera data files (.h5) nor phase/magnitude maps (.npy). "
                "Analysis requires either raw camera frames or pre-computed phase maps."
            )

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

            # Get acquisition directions from parameter manager
            acquisition_params = self.param_manager.get_parameter_group("acquisition")
            directions = acquisition_params.get("directions", ["LR", "RL", "TB", "BT"])
            logger.info(f"Processing {len(directions)} directions: {directions}")

            phase_maps = {}
            magnitude_maps = {}
            coherence_maps = {}

            for i, direction in enumerate(directions):
                if not self.is_running:
                    return

                # Update progress proportionally
                progress = 0.1 + (i / len(directions)) * 0.6
                self.progress = progress
                self.current_stage = f"processing_{direction}"
                self._send_progress(progress, f"Processing {direction} direction")

                # Check if we have pre-computed phase/magnitude maps or need to compute from frames
                if session_data.has_camera_data:
                    # Full pipeline: compute FFT from raw camera frames
                    frames = session_data.directions[direction].frames
                    angles = session_data.directions[direction].stimulus_angles

                    if frames is None or angles is None:
                        logger.warning(f"Skipping {direction}: missing data")
                        continue

                    # Compute FFT phase/magnitude/coherence maps
                    # Get cycles from parameter manager
                    cycles = acquisition_params.get("cycles", 10)
                    stimulus_freq = cycles / len(frames)
                    logger.info(f"  Computing FFT for {direction} ({len(frames)} frames, freq={stimulus_freq:.4f})...")
                    start_time = time.time()

                    phase_map, magnitude_map, coherence_map = self.pipeline.compute_fft_phase_maps(
                        frames, stimulus_freq
                    )

                    elapsed = time.time() - start_time
                    logger.info(f"  FFT computation completed in {elapsed:.2f}s")
                    logger.info(f"  Phase: [{np.min(phase_map):.3f}, {np.max(phase_map):.3f}], "
                               f"Mag: [{np.min(magnitude_map):.1f}, {np.max(magnitude_map):.1f}], "
                               f"Coh: [{np.min(coherence_map):.3f}, {np.max(coherence_map):.3f}]")

                    phase_maps[direction] = phase_map
                    magnitude_maps[direction] = magnitude_map
                    coherence_maps[direction] = coherence_map
                else:
                    # Partial pipeline: use pre-loaded phase/magnitude maps
                    phase_map = session_data.directions[direction].phase_map
                    magnitude_map = session_data.directions[direction].magnitude_map

                    if phase_map is None or magnitude_map is None:
                        logger.warning(f"Skipping {direction}: missing phase/magnitude data")
                        continue

                    logger.info(f"Using pre-computed phase/magnitude maps for {direction}")
                    phase_maps[direction] = phase_map
                    magnitude_maps[direction] = magnitude_map

                    # For pre-computed data without coherence, create placeholder
                    # (Ideally pre-computed data should include coherence, but for backwards compatibility)
                    coherence_maps[direction] = np.ones_like(magnitude_map)

            # Stage 3-5: Run complete retinotopic analysis pipeline (70% -> 90%)
            # This includes: retinotopic mapping, VFS computation, and boundary detection
            if not self.is_running:
                return

            self.progress = 0.7
            self.current_stage = "retinotopic_mapping"
            self._send_progress(0.7, "Running complete retinotopic analysis pipeline")

            # Run unified pipeline with coherence data (passes coherence_threshold parameter)
            logger.info("Passing coherence maps to pipeline for literature-compliant thresholding")
            pipeline_results = self.pipeline.run_from_phase_maps(
                phase_data=phase_maps,
                magnitude_data=magnitude_maps,
                coherence_data=coherence_maps if coherence_maps else None,
                anatomical=session_data.anatomical
            )

            # Extract results from pipeline
            azimuth_map = pipeline_results.get('azimuth_map')
            elevation_map = pipeline_results.get('elevation_map')
            raw_vfs_map = pipeline_results.get('raw_vfs_map')
            coherence_vfs_map = pipeline_results.get('coherence_vfs_map')  # PRIMARY method
            magnitude_vfs_map = pipeline_results.get('magnitude_vfs_map')  # Alternative method
            statistical_vfs_map = pipeline_results.get('statistical_vfs_map')  # Alternative method
            boundary_map = pipeline_results.get('boundary_map')

            # Send intermediate results to frontend
            if azimuth_map is not None:
                self._send_layer_ready('azimuth_map', azimuth_map, session_path)
            if elevation_map is not None:
                self._send_layer_ready('elevation_map', elevation_map, session_path)

            # Use coherence-thresholded VFS for display if available (literature standard)
            # Fall back to magnitude-thresholded if coherence unavailable
            display_vfs = coherence_vfs_map if coherence_vfs_map is not None else magnitude_vfs_map
            if display_vfs is not None:
                self._send_layer_ready('sign_map', display_vfs, session_path)
            if boundary_map is not None:
                self._send_layer_ready('boundary_map', boundary_map, session_path)

            # Segment visual areas with spatial calibration
            area_map = None
            if display_vfs is not None and boundary_map is not None:
                # Get image dimensions for spatial calibration (ring_size_mm parameter)
                image_width_pixels = azimuth_map.shape[1] if azimuth_map is not None else None
                area_map = self.pipeline.segment_visual_areas(display_vfs, boundary_map, image_width_pixels)

            # Compute gradients for results storage
            gradients = None
            if azimuth_map is not None and elevation_map is not None:
                gradients = self.pipeline.compute_spatial_gradients(azimuth_map, elevation_map)

            self.progress = 0.9
            self.current_stage = "analysis_complete"
            self._send_progress(0.9, "Retinotopic analysis complete")
            logger.info(f"Coherence maps available for {len(coherence_maps)} directions")

            # Stage 6: Save results (95% -> 100%)
            if not self.is_running:
                return

            self.progress = 0.95
            self.current_stage = "saving_results"
            self._send_progress(0.95, "Saving results")

            # Store results
            results = AnalysisResults()
            results.phase_maps = phase_maps
            results.magnitude_maps = magnitude_maps
            results.coherence_maps = coherence_maps
            results.azimuth_map = azimuth_map
            results.elevation_map = elevation_map
            results.gradients = gradients
            results.raw_vfs_map = raw_vfs_map
            results.coherence_vfs_map = coherence_vfs_map  # PRIMARY method (literature standard)
            results.magnitude_vfs_map = magnitude_vfs_map  # Alternative method
            results.statistical_vfs_map = statistical_vfs_map  # Alternative method
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

        Supports two modes:
        1. Full pipeline: Load raw camera frames (.h5) for complete analysis
        2. Partial pipeline: Load pre-computed phase/magnitude maps (.npy) from intermediate processing

        Args:
            session_path: Path to session directory

        Returns:
            SessionData container with all loaded data
        """
        logger.info(f"Loading session data from: {session_path}")
        session_path_obj = Path(session_path)

        # Get acquisition directions from parameter manager (needed to know which files to expect)
        acquisition_params = self.param_manager.get_parameter_group("acquisition")
        directions = acquisition_params.get("directions", ["LR", "RL", "TB", "BT"])

        # Poll for file availability instead of blind delay
        # This coordinates with acquisition's atomic file writes (.tmp -> rename)
        # Wait until all expected files exist and no .tmp files remain
        logger.info("Waiting for acquisition files to be ready...")

        max_wait_time = 30.0  # Maximum 30 seconds
        poll_interval = 0.5  # Check every 500ms
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            # Check if any .tmp files exist (atomic writes in progress)
            tmp_files = list(session_path_obj.glob("*.tmp"))
            if tmp_files:
                logger.debug(f"Temporary files still present: {[f.name for f in tmp_files]}")
                time.sleep(poll_interval)
                continue

            # Check if metadata and at least some data files exist
            metadata_path = session_path_obj / "metadata.json"
            if not metadata_path.exists():
                logger.debug("Waiting for metadata.json...")
                time.sleep(poll_interval)
                continue

            # Check if at least one direction has data files
            has_some_data = False
            for direction in directions:
                camera_path = session_path_obj / f"{direction}_camera.h5"
                stimulus_path = session_path_obj / f"{direction}_stimulus.h5"
                if camera_path.exists() or stimulus_path.exists():
                    has_some_data = True
                    break

            if has_some_data:
                logger.info(f"All acquisition files ready (waited {time.time() - start_time:.1f}s)")
                break

            time.sleep(poll_interval)
        else:
            logger.warning(
                f"Timed out waiting for acquisition files after {max_wait_time}s - proceeding anyway"
            )

        session_data = SessionData()

        # Load metadata
        with open(metadata_path, 'r') as f:
            session_data.metadata = json.load(f)

        # Detect which type of data we have
        has_camera_files = any(
            (session_path_obj / f"{dir}_camera.h5").exists()
            for dir in directions
        )
        has_phase_files = any(
            (session_path_obj / f"phase_{dir}.npy").exists()
            for dir in directions
        )

        if has_camera_files:
            logger.info("Loading raw camera data for full pipeline analysis")
            session_data.has_camera_data = True
        elif has_phase_files:
            logger.info("Loading pre-computed phase/magnitude maps for partial pipeline analysis")
            session_data.has_camera_data = False
        else:
            raise ValueError("No valid data files found (neither camera frames nor phase maps)")

        # Load anatomical image if exists
        anatomical_path = session_path_obj / "anatomical.npy"
        if anatomical_path.exists():
            anatomical = np.load(anatomical_path)

            # Check if anatomical needs cropping (legacy data)
            if len(anatomical.shape) >= 2:
                height, width = anatomical.shape[:2]

                if height != width:
                    # Legacy data: needs cropping to square
                    min_dim = min(height, width)
                    y_start = (height - min_dim) // 2
                    x_start = (width - min_dim) // 2
                    anatomical = anatomical[y_start:y_start + min_dim, x_start:x_start + min_dim]
                    logger.info(f"  Cropped legacy anatomical: {min_dim}x{min_dim} (from {height}x{width})")
                else:
                    # Modern data: already square
                    logger.info(f"  ✓ Square anatomical: {height}x{width}")

            session_data.anatomical = anatomical
            logger.info(f"  Loaded anatomical image: {session_data.anatomical.shape}")

        # Load data for each direction
        for direction in directions:
            logger.info(f"  Loading {direction} data...")

            direction_data = DirectionData()

            # Load camera data
            camera_path = session_path_obj / f"{direction}_camera.h5"
            if camera_path.exists():
                with h5py.File(camera_path, 'r') as f:
                    frames = f['frames'][:]
                    timestamps = f['timestamps'][:]

                    # Check if frames are already grayscale or need conversion (legacy data)
                    if len(frames.shape) == 4 and frames.shape[3] == 3:
                        # Legacy data: RGB/BGR frames need conversion and cropping
                        logger.warning(f"    ⚠️  LEGACY RGB/BGR DATA - converting to grayscale ({frames.shape})...")
                        start_time = time.time()

                        # BGR to grayscale: 0.114*B + 0.587*G + 0.299*R
                        # Use element-wise operations (avoids np.dot hang on large arrays)
                        frames = (frames[:, :, :, 0] * 0.114 +
                                 frames[:, :, :, 1] * 0.587 +
                                 frames[:, :, :, 2] * 0.299).astype(np.uint8)

                        # Legacy data also needs cropping
                        num_frames, height, width = frames.shape
                        min_dim = min(height, width)
                        y_start = (height - min_dim) // 2
                        x_start = (width - min_dim) // 2
                        frames = frames[:, y_start:y_start + min_dim, x_start:x_start + min_dim]

                        # Ensure C-contiguous after operations
                        if not frames.flags['C_CONTIGUOUS']:
                            frames = np.ascontiguousarray(frames)

                        elapsed = time.time() - start_time
                        logger.info(f"    Legacy conversion completed in {elapsed:.2f}s")
                        logger.info(f"    Result: {frames.shape} (cropped from {height}x{width})")
                    else:
                        # Modern data: already grayscale and square-cropped during recording
                        logger.info(f"    ✓ Optimized grayscale data: {frames.shape}")

                        # CRITICAL: Ensure C-contiguous (HDF5 may load as non-contiguous)
                        if not frames.flags['C_CONTIGUOUS']:
                            logger.info(f"    Making C-contiguous for GPU efficiency...")
                            frames = np.ascontiguousarray(frames)

                    direction_data.frames = frames
                    direction_data.timestamps = timestamps
                    logger.info(f"    Camera: {frames.shape} dtype={frames.dtype}")
            else:
                # If no camera data, load pre-computed phase/magnitude maps
                phase_file = session_path_obj / f"phase_{direction}.npy"
                magnitude_file = session_path_obj / f"magnitude_{direction}.npy"

                if phase_file.exists() and magnitude_file.exists():
                    phase_map = np.load(str(phase_file))
                    magnitude_map = np.load(str(magnitude_file))

                    direction_data.phase_map = phase_map
                    direction_data.magnitude_map = magnitude_map
                    logger.info(f"    Phase/Magnitude: {phase_map.shape} dtype={phase_map.dtype}")

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

        # Save main results as HDF5 using atomic writes
        # Write to temporary file first, then rename atomically
        results_path = output_path / "analysis_results.h5"
        results_tmp_path = output_path / "analysis_results.h5.tmp"

        # Remove any existing temp file from previous failed writes
        if results_tmp_path.exists():
            results_tmp_path.unlink()

        with h5py.File(results_tmp_path, 'w') as f:
            # Retinotopic maps (CRITICAL: ensure C-contiguous to avoid stride issues)
            if results.azimuth_map is not None:
                azimuth_data = np.ascontiguousarray(results.azimuth_map)
                f.create_dataset('azimuth_map', data=azimuth_data)
            if results.elevation_map is not None:
                elevation_data = np.ascontiguousarray(results.elevation_map)
                f.create_dataset('elevation_map', data=elevation_data)

            # Visual field sign maps - all 4 variants
            if results.raw_vfs_map is not None:
                raw_vfs_data = np.ascontiguousarray(results.raw_vfs_map)
                f.create_dataset('raw_vfs_map', data=raw_vfs_data)
            if results.coherence_vfs_map is not None:
                coherence_vfs_data = np.ascontiguousarray(results.coherence_vfs_map)
                f.create_dataset('coherence_vfs_map', data=coherence_vfs_data)  # PRIMARY (literature standard)
            if results.magnitude_vfs_map is not None:
                magnitude_vfs_data = np.ascontiguousarray(results.magnitude_vfs_map)
                f.create_dataset('magnitude_vfs_map', data=magnitude_vfs_data)  # Alternative
            if results.statistical_vfs_map is not None:
                statistical_vfs_data = np.ascontiguousarray(results.statistical_vfs_map)
                f.create_dataset('statistical_vfs_map', data=statistical_vfs_data)  # Alternative

            # Area segmentation
            if results.area_map is not None:
                area_data = np.ascontiguousarray(results.area_map)
                f.create_dataset('area_map', data=area_data)
            if results.boundary_map is not None:
                boundary_data = np.ascontiguousarray(results.boundary_map)
                f.create_dataset('boundary_map', data=boundary_data)

            # Phase maps for each direction
            if results.phase_maps:
                phase_group = f.create_group('phase_maps')
                for direction, phase_map in results.phase_maps.items():
                    phase_data = np.ascontiguousarray(phase_map)
                    phase_group.create_dataset(direction, data=phase_data)

            # Magnitude maps for each direction
            if results.magnitude_maps:
                magnitude_group = f.create_group('magnitude_maps')
                for direction, magnitude_map in results.magnitude_maps.items():
                    magnitude_data = np.ascontiguousarray(magnitude_map)
                    magnitude_group.create_dataset(direction, data=magnitude_data)

            # Coherence maps for each direction
            if results.coherence_maps:
                coherence_group = f.create_group('coherence_maps')
                for direction, coherence_map in results.coherence_maps.items():
                    coherence_data = np.ascontiguousarray(coherence_map)
                    coherence_group.create_dataset(direction, data=coherence_data)

        # Atomically rename temporary file to final path
        # This prevents file-already-open errors when re-analyzing
        import os
        if results_path.exists():
            results_path.unlink()  # Remove old file if it exists
        os.rename(results_tmp_path, results_path)

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
