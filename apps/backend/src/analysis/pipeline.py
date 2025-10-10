"""ISI Analysis Pipeline - Fourier-based retinotopic mapping.

Implements the complete analysis pipeline following:
- Kalatsky & Stryker 2003: Fourier-based retinotopic analysis
- Marshel et al. 2011: ISI experimental procedures
- Zhuang et al. 2017: Visual field sign analysis

All dependencies injected via constructor - NO service locator pattern.
"""

from __future__ import annotations

import logging
from typing import Dict, Tuple, Optional, Any
import numpy as np
from scipy import ndimage
from scipy.fft import fft, fftfreq

from config import AnalysisConfig

logger = logging.getLogger(__name__)

# GPU acceleration support
try:
    import torch
    GPU_AVAILABLE = torch.backends.mps.is_available() if hasattr(torch.backends, 'mps') else torch.cuda.is_available()
    if GPU_AVAILABLE:
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            DEVICE = torch.device('mps')
            DEVICE_NAME = 'MPS (Apple Metal)'
        elif torch.cuda.is_available():
            DEVICE = torch.device('cuda')
            DEVICE_NAME = f'CUDA (GPU {torch.cuda.get_device_name(0)})'
        else:
            GPU_AVAILABLE = False
            DEVICE = torch.device('cpu')
            DEVICE_NAME = 'CPU'
    else:
        DEVICE = torch.device('cpu')
        DEVICE_NAME = 'CPU'
except ImportError:
    GPU_AVAILABLE = False
    DEVICE = None
    DEVICE_NAME = 'CPU (PyTorch not available)'

logger.info(f"ISI Analysis GPU Status: {DEVICE_NAME}, GPU Available: {GPU_AVAILABLE}")


class AnalysisPipeline:
    """Fourier analysis pipeline for ISI data.

    Performs FFT-based phase and amplitude analysis on grayscale frames.
    All dependencies injected via constructor - NO service locator.
    """

    def __init__(self, config: AnalysisConfig):
        """Initialize analysis pipeline.

        Args:
            config: Analysis configuration (FFT params, filtering)
        """
        self.config = config
        self.use_gpu = GPU_AVAILABLE

        # Log GPU status on initialization
        if self.use_gpu:
            logger.info(f"GPU acceleration enabled: {DEVICE_NAME}")
        else:
            logger.warning(f"GPU acceleration not available, using CPU: {DEVICE_NAME}")

    # ========== FOURIER ANALYSIS (Kalatsky & Stryker Method) ==========

    def compute_fft_phase_maps(
        self,
        frames: np.ndarray,
        stimulus_frequency: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Compute phase at stimulus frequency for each pixel.

        Args:
            frames: [n_frames, height, width] grayscale data
            stimulus_frequency: Stimulus frequency in cycles per frame

        Returns:
            phase_map: [height, width] phase in radians
            magnitude_map: [height, width] response amplitude
        """
        logger.info("Computing FFT phase maps...")

        # Validate frame array shape
        if len(frames.shape) != 3:
            raise ValueError(
                f"Expected 3D frame array (n_frames, height, width), got shape {frames.shape}. "
                f"If frames are RGB/BGR, convert to grayscale first."
            )

        # Convert frames to float for processing
        frames_float = frames.astype(np.float32)
        n_frames, height, width = frames_float.shape

        logger.info(f"  Stimulus frequency: {stimulus_frequency:.4f} cycles/frame")
        logger.info(f"  Processing {height}x{width} pixels...")

        # Reshape frames from (n_frames, height, width) to (n_frames, n_pixels)
        n_pixels = height * width
        frames_reshaped = frames_float.reshape(n_frames, n_pixels)

        if self.use_gpu:
            # GPU-accelerated FFT computation using PyTorch
            logger.info(f"  Computing FFT for {n_pixels:,} pixels on {DEVICE_NAME}...")

            # Transfer to GPU
            frames_tensor = torch.from_numpy(frames_reshaped).to(DEVICE)

            # Remove DC component (mean) from all pixels at once
            frames_centered = frames_tensor - torch.mean(frames_tensor, dim=0, keepdim=True)

            # Compute FFT along time axis for all pixels simultaneously
            fft_result = torch.fft.fft(frames_centered, dim=0)

            # Get frequency bins (on CPU for argmin)
            freqs = fftfreq(n_frames)
            freq_idx = np.argmin(np.abs(freqs - stimulus_frequency))
            logger.info(f"  Extracting phase/magnitude at frequency index {freq_idx}")

            # Extract complex amplitude at stimulus frequency for all pixels
            complex_amplitude = fft_result[freq_idx, :]

            # Compute phase and magnitude for all pixels
            phase_flat = torch.angle(complex_amplitude)
            magnitude_flat = torch.abs(complex_amplitude)

            # Transfer back to CPU and convert to numpy
            phase_map = phase_flat.cpu().numpy().reshape(height, width).astype(np.float32)
            magnitude_map = magnitude_flat.cpu().numpy().reshape(height, width).astype(np.float32)

            logger.info(f"  Phase maps computed (GPU-accelerated on {DEVICE_NAME})")
        else:
            # CPU fallback: Vectorized FFT computation
            logger.info(f"  Computing FFT for {n_pixels:,} pixels on CPU...")

            # Remove DC component (mean) from all pixels at once
            frames_centered = frames_reshaped - np.mean(frames_reshaped, axis=0, keepdims=True)

            # Compute FFT along time axis for all pixels simultaneously
            fft_result = fft(frames_centered, axis=0)

            # Get frequency bins
            freqs = fftfreq(n_frames)

            # Find frequency index closest to stimulus frequency
            freq_idx = np.argmin(np.abs(freqs - stimulus_frequency))
            logger.info(f"  Extracting phase/magnitude at frequency index {freq_idx}")

            # Extract complex amplitude at stimulus frequency for all pixels
            complex_amplitude = fft_result[freq_idx, :]

            # Compute phase and magnitude for all pixels
            phase_flat = np.angle(complex_amplitude)
            magnitude_flat = np.abs(complex_amplitude)

            # Reshape back to (height, width)
            phase_map = phase_flat.reshape(height, width).astype(np.float32)
            magnitude_map = magnitude_flat.reshape(height, width).astype(np.float32)

            logger.info("  Phase maps computed (CPU vectorized)")

        return phase_map, magnitude_map

    def bidirectional_analysis(
        self,
        forward_phase: np.ndarray,
        reverse_phase: np.ndarray
    ) -> np.ndarray:
        """Combine opposing directions to find retinotopic center.

        The retinotopic center is where forward and reverse phases are equal.
        This removes the hemodynamic delay component.

        Args:
            forward_phase: Phase map from LR or TB
            reverse_phase: Phase map from RL or BT

        Returns:
            center_map: Estimated center position for each pixel
        """
        logger.info("Performing bidirectional analysis...")

        if self.use_gpu:
            # GPU-accelerated phase unwrapping and averaging
            logger.info(f"  Unwrapping phases on {DEVICE_NAME}...")

            # Transfer to GPU (convert to float32 for MPS compatibility)
            forward_tensor = torch.from_numpy(forward_phase.astype(np.float32)).to(DEVICE)
            reverse_tensor = torch.from_numpy(reverse_phase.astype(np.float32)).to(DEVICE)

            # Unwrap phases row-by-row on GPU
            def unwrap_tensor(phase_tensor):
                # Compute differences between adjacent elements along rows
                diff = torch.diff(phase_tensor, dim=1)
                # Find where phase jumps exceed π
                diff_adjusted = diff - 2 * torch.pi * torch.round(diff / (2 * torch.pi))
                # Cumulative sum to reconstruct unwrapped phase
                unwrapped = torch.zeros_like(phase_tensor)
                unwrapped[:, 0] = phase_tensor[:, 0]
                unwrapped[:, 1:] = phase_tensor[:, 0:1] + torch.cumsum(diff_adjusted, dim=1)
                return unwrapped

            forward_unwrapped = unwrap_tensor(forward_tensor)
            reverse_unwrapped = unwrap_tensor(reverse_tensor)

            # Average the two directions
            center_map_tensor = (forward_unwrapped + reverse_unwrapped) / 2

            # Wrap back to [-π, π] using atan2
            center_map = torch.atan2(torch.sin(center_map_tensor), torch.cos(center_map_tensor))

            # Transfer back to CPU
            center_map = center_map.cpu().numpy()
        else:
            # CPU fallback: Unwrap row-by-row using NumPy
            logger.info("  Unwrapping phases on CPU...")
            forward_unwrapped = np.apply_along_axis(np.unwrap, axis=1, arr=forward_phase)
            reverse_unwrapped = np.apply_along_axis(np.unwrap, axis=1, arr=reverse_phase)

            # Average the two directions
            center_map = (forward_unwrapped + reverse_unwrapped) / 2

            # Wrap back to [-π, π]
            center_map = np.arctan2(np.sin(center_map), np.cos(center_map))

        return center_map

    # ========== RETINOTOPIC MAPPING ==========

    def generate_azimuth_map(
        self,
        LR_phase: np.ndarray,
        RL_phase: np.ndarray
    ) -> np.ndarray:
        """Generate horizontal retinotopy (azimuth) map.

        Args:
            LR_phase: Phase map from left-to-right stimulus
            RL_phase: Phase map from right-to-left stimulus

        Returns:
            azimuth_map: Horizontal retinotopy in degrees (-60 to +60)
        """
        logger.info("Generating azimuth map...")

        # Combine LR and RL using bidirectional analysis
        center_phase = self.bidirectional_analysis(LR_phase, RL_phase)

        # Convert phase to degrees of visual angle
        # Phase range [-π, π] maps to visual field range [-60°, +60°]
        azimuth_map = center_phase * (60.0 / np.pi)

        return azimuth_map

    def generate_elevation_map(
        self,
        TB_phase: np.ndarray,
        BT_phase: np.ndarray
    ) -> np.ndarray:
        """Generate vertical retinotopy (elevation) map.

        Args:
            TB_phase: Phase map from top-to-bottom stimulus
            BT_phase: Phase map from bottom-to-top stimulus

        Returns:
            elevation_map: Vertical retinotopy in degrees (-30 to +30)
        """
        logger.info("Generating elevation map...")

        # Combine TB and BT using bidirectional analysis
        center_phase = self.bidirectional_analysis(TB_phase, BT_phase)

        # Convert phase to degrees of visual angle
        # Phase range [-π, π] maps to visual field range [-30°, +30°]
        elevation_map = center_phase * (30.0 / np.pi)

        return elevation_map

    # ========== VISUAL FIELD SIGN (Zhuang et al. Method) ==========

    def compute_spatial_gradients(
        self,
        azimuth_map: np.ndarray,
        elevation_map: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """Calculate spatial gradients of retinotopic maps.

        Args:
            azimuth_map: Horizontal retinotopy map
            elevation_map: Vertical retinotopy map

        Returns:
            Dictionary containing all gradient components
        """
        logger.info("Computing spatial gradients...")

        # Smooth maps before computing gradients (reduce noise)
        sigma = self.config.smoothing_sigma

        if self.use_gpu:
            # GPU-accelerated gradient computation
            logger.info(f"  Computing gradients on {DEVICE_NAME}...")

            # Note: Gaussian filtering still uses scipy (CPU) as it's efficient
            azimuth_smooth = ndimage.gaussian_filter(azimuth_map, sigma=sigma)
            elevation_smooth = ndimage.gaussian_filter(elevation_map, sigma=sigma)

            # Transfer smoothed maps to GPU for gradient computation (convert to float32 for MPS)
            azimuth_tensor = torch.from_numpy(azimuth_smooth.astype(np.float32)).to(DEVICE)
            elevation_tensor = torch.from_numpy(elevation_smooth.astype(np.float32)).to(DEVICE)

            # Compute gradients using PyTorch's gradient function
            d_azimuth_dy, d_azimuth_dx = torch.gradient(azimuth_tensor)
            d_elevation_dy, d_elevation_dx = torch.gradient(elevation_tensor)

            # Transfer back to CPU and convert to numpy
            gradients = {
                'd_azimuth_dx': d_azimuth_dx.cpu().numpy(),
                'd_azimuth_dy': d_azimuth_dy.cpu().numpy(),
                'd_elevation_dx': d_elevation_dx.cpu().numpy(),
                'd_elevation_dy': d_elevation_dy.cpu().numpy()
            }
        else:
            # CPU fallback
            logger.info("  Computing gradients on CPU...")
            azimuth_smooth = ndimage.gaussian_filter(azimuth_map, sigma=sigma)
            elevation_smooth = ndimage.gaussian_filter(elevation_map, sigma=sigma)

            # Compute gradients using numpy
            d_azimuth_dy, d_azimuth_dx = np.gradient(azimuth_smooth)
            d_elevation_dy, d_elevation_dx = np.gradient(elevation_smooth)

            gradients = {
                'd_azimuth_dx': d_azimuth_dx,
                'd_azimuth_dy': d_azimuth_dy,
                'd_elevation_dx': d_elevation_dx,
                'd_elevation_dy': d_elevation_dy
            }

        return gradients

    def calculate_visual_field_sign(
        self,
        gradients: Dict[str, np.ndarray]
    ) -> np.ndarray:
        """Calculate sign of visual field representation.

        VFS = sign(d_azimuth_dx * d_elevation_dy - d_azimuth_dy * d_elevation_dx)

        Args:
            gradients: Dictionary of gradient components

        Returns:
            sign_map: +1 (non-mirror) or -1 (mirror) for each pixel
        """
        logger.info("Calculating visual field sign...")

        d_azimuth_dx = gradients['d_azimuth_dx']
        d_azimuth_dy = gradients['d_azimuth_dy']
        d_elevation_dx = gradients['d_elevation_dx']
        d_elevation_dy = gradients['d_elevation_dy']

        # Calculate the determinant of the Jacobian matrix
        jacobian_det = d_azimuth_dx * d_elevation_dy - d_azimuth_dy * d_elevation_dx

        # Get the sign
        sign_map = np.sign(jacobian_det)

        return sign_map

    def detect_area_boundaries(self, sign_map: np.ndarray) -> np.ndarray:
        """Find boundaries where visual field sign reverses.

        Args:
            sign_map: Visual field sign map

        Returns:
            boundary_map: Binary map of area boundaries
        """
        logger.info("Detecting area boundaries...")

        # Apply median filter to reduce noise
        sign_filtered = ndimage.median_filter(sign_map, size=5)

        # Find boundaries using morphological operations
        boundary_map = np.zeros_like(sign_filtered)

        # Check for sign changes in horizontal and vertical directions
        h_boundaries = np.abs(np.diff(sign_filtered, axis=1)) > 0
        v_boundaries = np.abs(np.diff(sign_filtered, axis=0)) > 0

        # Combine boundaries
        boundary_map[:, :-1] += h_boundaries
        boundary_map[:-1, :] += v_boundaries

        # Convert to binary
        boundary_map = (boundary_map > 0).astype(np.uint8)

        return boundary_map

    def segment_visual_areas(
        self,
        sign_map: np.ndarray,
        boundary_map: np.ndarray
    ) -> np.ndarray:
        """Identify distinct visual areas.

        Args:
            sign_map: Visual field sign map
            boundary_map: Area boundary map

        Returns:
            area_map: Labeled map of visual areas
        """
        logger.info("Segmenting visual areas...")

        # Use area_min_size_mm2 parameter from config
        min_area_size = int(self.config.area_min_size_mm2)

        # Create mask of valid pixels (exclude boundaries)
        valid_mask = (boundary_map == 0) & (~np.isnan(sign_map))

        # Separate positive and negative sign regions
        pos_mask = valid_mask & (sign_map > 0)
        neg_mask = valid_mask & (sign_map < 0)

        # Label connected components for each sign
        pos_labels, pos_num = ndimage.label(pos_mask)
        neg_labels, neg_num = ndimage.label(neg_mask)

        # Combine labels (offset negative labels)
        area_map = np.zeros_like(sign_map, dtype=np.int32)
        area_map[pos_mask] = pos_labels[pos_mask]
        area_map[neg_mask] = neg_labels[neg_mask] + pos_num

        # Filter out small areas
        for label in range(1, pos_num + neg_num + 1):
            area_size = np.sum(area_map == label)
            if area_size < min_area_size:
                area_map[area_map == label] = 0

        logger.info(f"  Found {np.max(area_map)} visual areas")
        return area_map

    def apply_magnitude_threshold(
        self,
        phase_map: np.ndarray,
        magnitude_map: np.ndarray
    ) -> np.ndarray:
        """Mask out low-magnitude responses.

        Args:
            phase_map: Phase map to threshold
            magnitude_map: Magnitude map for thresholding

        Returns:
            Thresholded phase map with low-magnitude pixels set to NaN
        """
        threshold = self.config.magnitude_threshold
        logger.info(f"Applying magnitude threshold: {threshold}")

        # Create copy to avoid modifying input
        phase_thresholded = phase_map.copy()

        # Set low-magnitude pixels to NaN
        phase_thresholded[magnitude_map < threshold] = np.nan

        return phase_thresholded

    # ========== HIGH-LEVEL PIPELINE ORCHESTRATION ==========

    def run_from_phase_maps(
        self,
        phase_data: Dict[str, np.ndarray],
        magnitude_data: Dict[str, np.ndarray],
        anatomical: Optional[np.ndarray] = None
    ) -> Dict[str, np.ndarray]:
        """Run analysis pipeline starting from phase/magnitude maps.

        This allows processing data that has already undergone Fourier analysis
        (e.g., pre-computed sample data or externally processed data).

        Args:
            phase_data: Dict with keys 'LR', 'RL', 'TB', 'BT' containing phase maps
            magnitude_data: Dict with keys 'LR', 'RL', 'TB', 'BT' containing magnitude maps
            anatomical: Optional anatomical reference image

        Returns:
            Dictionary containing:
                - azimuth_map: Horizontal retinotopy
                - elevation_map: Vertical retinotopy
                - sign_map: Visual field sign
                - boundary_map: Area boundaries
                - anatomical: Anatomical reference (if provided)
        """
        logger.info("=" * 70)
        logger.info("Running analysis from phase/magnitude maps...")
        logger.info("=" * 70)

        results = {}

        # Step 1: Generate retinotopic maps
        logger.info("\n[1/3] Generating retinotopic maps...")
        azimuth_map = self.generate_azimuth_map(phase_data['LR'], phase_data['RL'])
        elevation_map = self.generate_elevation_map(phase_data['TB'], phase_data['BT'])

        results['azimuth_map'] = azimuth_map
        results['elevation_map'] = elevation_map

        logger.info(f"  Azimuth range: [{np.nanmin(azimuth_map):.1f}°, {np.nanmax(azimuth_map):.1f}°]")
        logger.info(f"  Elevation range: [{np.nanmin(elevation_map):.1f}°, {np.nanmax(elevation_map):.1f}°]")

        # Step 2: Compute visual field sign
        logger.info("\n[2/3] Computing visual field sign...")
        gradients = self.compute_spatial_gradients(azimuth_map, elevation_map)
        sign_map = self.calculate_visual_field_sign(gradients)

        # Apply magnitude threshold to sign map
        avg_magnitude = (magnitude_data['LR'] + magnitude_data['RL'] +
                        magnitude_data['TB'] + magnitude_data['BT']) / 4.0
        magnitude_threshold = np.percentile(avg_magnitude, 25)  # Bottom 25%
        sign_map[avg_magnitude < magnitude_threshold] = 0

        results['sign_map'] = sign_map.astype(np.int8)

        num_positive = np.sum(sign_map > 0)
        num_negative = np.sum(sign_map < 0)
        num_undefined = np.sum(sign_map == 0)
        total = sign_map.size
        logger.info(f"  Positive (non-mirror): {num_positive} ({100*num_positive/total:.1f}%)")
        logger.info(f"  Negative (mirror): {num_negative} ({100*num_negative/total:.1f}%)")
        logger.info(f"  Undefined: {num_undefined} ({100*num_undefined/total:.1f}%)")

        # Step 3: Detect boundaries
        logger.info("\n[3/3] Detecting area boundaries...")
        boundary_map = self.detect_area_boundaries(sign_map)

        num_boundary_pixels = np.sum(boundary_map > 0)
        boundary_percentage = 100 * num_boundary_pixels / boundary_map.size
        logger.info(f"  Boundary pixels: {num_boundary_pixels} ({boundary_percentage:.1f}%)")

        results['boundary_map'] = boundary_map

        # Add anatomical if provided
        if anatomical is not None:
            results['anatomical'] = anatomical

        logger.info("\n" + "=" * 70)
        logger.info("✅ Analysis pipeline complete!")
        logger.info("=" * 70)

        return results
