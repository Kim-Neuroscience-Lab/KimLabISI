"""
Analysis Manager - Orchestrates ISI analysis pipeline with IPC integration.

This module provides the bridge between the ISI analysis algorithms (isi_analysis.py)
and the IPC system, enabling analysis to be triggered from the frontend and
providing real-time progress updates.

Architecture:
- Analysis runs in background thread to avoid blocking IPC
- Progress updates sent via IPC sync channel
- Results saved to disk (not transmitted via IPC)
- Follows same pattern as PlaybackModeController
"""

import threading
import time
from typing import Dict, Any, Optional
from pathlib import Path

from .isi_analysis import ISIAnalysis
from .logging_utils import get_logger
from .ipc_utils import format_success_response, format_error_response

logger = get_logger(__name__)


class AnalysisManager:
    """
    Manages ISI analysis pipeline with IPC integration.

    Responsibilities:
    - Orchestrate analysis workflow
    - Run analysis in background thread
    - Send progress updates via IPC
    - Handle errors and cancellation
    - Track analysis state
    """

    def __init__(self):
        """Initialize analysis manager."""
        self.is_running = False
        self.current_session_path: Optional[str] = None
        self.analysis_thread: Optional[threading.Thread] = None
        self.progress = 0.0
        self.current_stage = "idle"
        self.results: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        logger.info("AnalysisManager initialized")

    def start_analysis(
        self, session_path: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Start analysis on a recorded session.

        Args:
            session_path: Path to session directory
            params: Analysis parameters from ParameterManager

        Returns:
            Success response with analysis info or error response
        """
        # Validate not already running
        if self.is_running:
            return format_error_response(
                "start_analysis",
                "Analysis already running. Stop current analysis first."
            )

        # Validate session exists
        session_path_obj = Path(session_path)
        if not session_path_obj.exists():
            return format_error_response(
                "start_analysis",
                f"Session directory not found: {session_path}"
            )

        # Validate session has required files
        metadata_file = session_path_obj / "metadata.json"
        if not metadata_file.exists():
            return format_error_response(
                "start_analysis",
                f"Session missing metadata.json: {session_path}"
            )

        # Check for data files (at least one direction should have data)
        has_data = False
        for direction in ['LR', 'RL', 'TB', 'BT']:
            camera_file = session_path_obj / f"{direction}_camera.h5"
            if camera_file.exists():
                has_data = True
                break

        if not has_data:
            return format_error_response(
                "start_analysis",
                f"Session contains no camera data files: {session_path}"
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
            args=(session_path, params),
            daemon=True,
            name="AnalysisThread"
        )
        self.analysis_thread.start()

        return format_success_response(
            "start_analysis",
            message="Analysis started successfully",
            session_path=session_path,
        )

    def stop_analysis(self) -> Dict[str, Any]:
        """
        Request to stop running analysis.

        Note: Analysis cannot be truly cancelled mid-execution due to numpy
        operations, but this will mark it as stopped and prevent result processing.

        Returns:
            Success response or error if no analysis running
        """
        if not self.is_running:
            return format_error_response(
                "stop_analysis",
                "No analysis currently running"
            )

        logger.warning("Analysis stop requested (cannot interrupt running analysis)")

        # Mark as not running (will be checked in analysis thread)
        self.is_running = False
        self.current_stage = "stopping"

        return format_success_response(
            "stop_analysis",
            message="Analysis will complete current stage and then stop",
        )

    def get_status(self) -> Dict[str, Any]:
        """
        Get current analysis status.

        Returns:
            Status information including progress, stage, errors, and results
        """
        return format_success_response(
            "get_analysis_status",
            is_running=self.is_running,
            session_path=self.current_session_path,
            progress=self.progress,
            stage=self.current_stage,
            error=self.error,
            has_results=self.results is not None,
            results=self.results,
        )

    def _run_analysis(self, session_path: str, params: Dict[str, Any]):
        """
        Background thread for running analysis.

        This method runs the complete analysis pipeline and sends progress
        updates via IPC. It handles all errors and ensures proper cleanup.

        Args:
            session_path: Path to session directory
            params: Analysis parameters
        """
        from .service_locator import get_services

        services = get_services()
        ipc = services.ipc

        try:
            # Send started message
            self.current_stage = "started"
            ipc.send_sync_message({
                "type": "analysis_started",
                "session_path": session_path,
                "timestamp": time.time(),
            })
            logger.info("Analysis started message sent")

            # Create layer callback for incremental visualization
            def layer_ready_callback(layer_name: str, layer_data):
                """Called when intermediate layer is ready for visualization"""
                import numpy as np
                import base64
                from .analysis_image_renderer import render_signal_map
                from PIL import Image
                import io

                logger.info(f"Layer ready for visualization: {layer_name} {layer_data.shape}")

                # Ensure layer is float32
                if layer_data.dtype != np.float32:
                    layer_data = layer_data.astype(np.float32)

                try:
                    # Get data range for normalization
                    data_min = float(np.nanmin(layer_data))
                    data_max = float(np.nanmax(layer_data))

                    # Render layer to RGB image based on type
                    if layer_name == 'azimuth_map':
                        rgb_image = render_signal_map(layer_data, 'azimuth', data_min, data_max)
                    elif layer_name == 'elevation_map':
                        rgb_image = render_signal_map(layer_data, 'elevation', data_min, data_max)
                    elif layer_name == 'sign_map':
                        rgb_image = render_signal_map(layer_data, 'sign', data_min, data_max)
                    elif layer_name == 'boundary_map':
                        # Render boundary map (currently uses shared memory approach)
                        # For now, send as raw data since it's small and binary
                        # TODO: Could render as white-on-transparent PNG in future
                        from .analysis_image_renderer import render_boundaries
                        rgba_image = render_boundaries(layer_data)
                        # Convert RGBA to RGB for consistent PNG encoding
                        # Composite on black background
                        rgb_image = np.zeros((rgba_image.shape[0], rgba_image.shape[1], 3), dtype=np.uint8)
                        alpha = rgba_image[:, :, 3:4].astype(np.float32) / 255.0
                        rgb_image = (rgba_image[:, :, :3].astype(np.float32) * alpha).astype(np.uint8)
                    else:
                        # Default: render as grayscale signal
                        rgb_image = render_signal_map(layer_data, 'magnitude', data_min, data_max)

                    # Encode as PNG
                    img = Image.fromarray(rgb_image, mode='RGB')
                    buf = io.BytesIO()
                    img.save(buf, format='PNG', compress_level=6)
                    png_bytes = buf.getvalue()

                    # Encode as base64 for JSON transmission
                    png_base64 = base64.b64encode(png_bytes).decode('utf-8')

                    logger.info(f"Rendered {layer_name} to PNG: {len(png_bytes)} bytes")

                    # Send layer_ready message with rendered image
                    ipc.send_sync_message({
                        "type": "analysis_layer_ready",
                        "layer_name": layer_name,
                        "image_base64": png_base64,
                        "width": rgb_image.shape[1],
                        "height": rgb_image.shape[0],
                        "format": "png",
                        "session_path": session_path,  # Include session path for frontend
                        "timestamp": time.time(),
                    })
                    logger.info(f"Sent layer_ready message for {layer_name} with rendered PNG")
                except Exception as e:
                    logger.error(f"Failed to render and publish layer {layer_name}: {e}", exc_info=True)

            # Create analyzer with parameters and callback
            analyzer = ISIAnalysis(params=params, layer_callback=layer_ready_callback)
            logger.info(f"ISIAnalysis instance created with parameters: {params}")

            # Stage 1: Load session data (0% -> 10%)
            if not self.is_running:
                logger.info("Analysis cancelled before loading data")
                return

            self.progress = 0.0
            self.current_stage = "loading_data"
            ipc.send_sync_message({
                "type": "analysis_progress",
                "progress": 0.0,
                "stage": "Loading session data",
                "timestamp": time.time(),
            })

            analyzer.load_acquisition_data(session_path)
            logger.info("Session data loaded successfully")

            # Stage 2: Process each direction (10% -> 70%)
            if not self.is_running:
                logger.info("Analysis cancelled after loading data")
                return

            directions = analyzer.session_data['metadata'].get('acquisition', {}).get(
                'directions', ['LR', 'RL', 'TB', 'BT']
            )
            logger.info(f"Processing {len(directions)} directions: {directions}")

            for i, direction in enumerate(directions):
                if not self.is_running:
                    logger.info(f"Analysis cancelled during {direction} processing")
                    return

                # Update progress proportionally (10% to 70% across all directions)
                progress = 0.1 + (i / len(directions)) * 0.6
                self.progress = progress
                self.current_stage = f"processing_{direction}"

                ipc.send_sync_message({
                    "type": "analysis_progress",
                    "progress": progress,
                    "stage": f"Processing {direction} direction",
                    "timestamp": time.time(),
                })

            # Stage 3: Generate retinotopic maps (70% -> 85%)
            if not self.is_running:
                logger.info("Analysis cancelled before retinotopic mapping")
                return

            self.progress = 0.7
            self.current_stage = "retinotopic_mapping"
            ipc.send_sync_message({
                "type": "analysis_progress",
                "progress": 0.7,
                "stage": "Generating retinotopic maps",
                "timestamp": time.time(),
            })

            # Stage 4: Visual field sign analysis (85% -> 90%)
            self.progress = 0.85
            self.current_stage = "visual_field_sign"
            ipc.send_sync_message({
                "type": "analysis_progress",
                "progress": 0.85,
                "stage": "Computing visual field sign",
                "timestamp": time.time(),
            })

            # Run full analysis pipeline
            logger.info("Running complete analysis pipeline")
            results = analyzer.analyze_session(session_path)
            logger.info("Analysis pipeline completed successfully")

            # Stage 5: Save results (90% -> 100%)
            if not self.is_running:
                logger.info("Analysis cancelled before saving results")
                return

            self.progress = 0.9
            self.current_stage = "saving_results"
            ipc.send_sync_message({
                "type": "analysis_progress",
                "progress": 0.9,
                "stage": "Saving results",
                "timestamp": time.time(),
            })

            output_path = Path(session_path) / "analysis_results"
            analyzer.save_results(str(output_path))
            logger.info(f"Results saved to {output_path}")

            # Extract summary information
            num_areas = int(results['area_map'].max()) if 'area_map' in results else 0

            self.results = {
                "output_path": str(output_path),
                "num_areas": num_areas,
                "directions_processed": len(directions),
            }
            self.progress = 1.0
            self.current_stage = "complete"

            # Send completion message
            ipc.send_sync_message({
                "type": "analysis_complete",
                "session_path": session_path,
                "output_path": str(output_path),
                "timestamp": time.time(),
                "num_areas": num_areas,
                "success": True,
            })

            logger.info(
                f"Analysis complete: {session_path} "
                f"(found {num_areas} visual areas)"
            )

        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            self.error = str(e)
            self.current_stage = "error"

            # Send error message
            ipc.send_sync_message({
                "type": "analysis_error",
                "error": str(e),
                "session_path": session_path,
                "timestamp": time.time(),
            })

        finally:
            self.is_running = False
            logger.info("Analysis thread finished")


# Global instance (singleton pattern)
_analysis_manager: Optional[AnalysisManager] = None


def get_analysis_manager() -> AnalysisManager:
    """
    Get or create global analysis manager instance.

    Returns:
        Global AnalysisManager instance
    """
    global _analysis_manager
    if _analysis_manager is None:
        _analysis_manager = AnalysisManager()
        logger.info("Created global AnalysisManager instance")
    return _analysis_manager
