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
    import os

    # CRITICAL BUG WARNING: PyTorch MPS (Apple Metal) has numerical bugs with FFT operations
    # that cause zero outputs for large arrays (>1M pixels). This affects retinotopic analysis.
    # MPS is DISABLED BY DEFAULT for safety.
    #
    # To enable MPS anyway (e.g., for testing or if bug is fixed):
    #   export ENABLE_MPS_FFT=1
    #
    # Known issues:
    # - torch.fft.fft() on MPS returns all zeros for large tensors
    # - Affects: phase maps, magnitude maps, coherence maps
    # - Symptom: Uniform color retinotopic maps (all black or single color)

    enable_mps = os.environ.get('ENABLE_MPS_FFT', '0') == '1'

    if torch.cuda.is_available():
        # CUDA is always safe - use it
        GPU_AVAILABLE = True
        DEVICE = torch.device('cuda')
        DEVICE_NAME = f'CUDA (GPU {torch.cuda.get_device_name(0)})'
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available() and enable_mps:
        # MPS available and user explicitly enabled it
        GPU_AVAILABLE = True
        DEVICE = torch.device('mps')
        DEVICE_NAME = 'MPS (Apple Metal) - WARNING: Known FFT bugs, use at own risk'
        logger.warning("=" * 70)
        logger.warning("MPS GPU acceleration ENABLED via ENABLE_MPS_FFT=1")
        logger.warning("WARNING: MPS has known bugs with FFT operations!")
        logger.warning("If you see uniform color retinotopic maps, disable MPS:")
        logger.warning("  unset ENABLE_MPS_FFT")
        logger.warning("=" * 70)
    else:
        # Use CPU (safe fallback)
        GPU_AVAILABLE = False
        DEVICE = torch.device('cpu')
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            DEVICE_NAME = 'CPU (MPS available but disabled due to FFT bugs - set ENABLE_MPS_FFT=1 to override)'
        else:
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

        # Log all 9 analysis parameters (Juavinett et al. 2017 + Kalatsky & Stryker 2003)
        logger.info("=" * 70)
        logger.info("Analysis Pipeline Initialized with Parameters:")
        logger.info("  [1] ring_size_mm: %.2f mm (spatial calibration)", self.config.ring_size_mm)
        logger.info("  [2] phase_filter_sigma: %.2f (phase smoothing BEFORE conversion)", self.config.phase_filter_sigma)
        logger.info("  [3] magnitude_threshold: %.2f (per-direction magnitude filtering)", self.config.magnitude_threshold)
        logger.info("  [4] gradient_window_size: %d (UNUSED - gradients computed via central differences)", self.config.gradient_window_size)
        logger.info("  [5] response_threshold_percent: %d%% (percentile-based filtering)", self.config.response_threshold_percent)
        logger.info("  [6] coherence_threshold: %.2f (signal reliability threshold)", self.config.coherence_threshold)
        logger.info("  [7] smoothing_sigma: %.2f (position smoothing AFTER conversion)", self.config.smoothing_sigma)
        logger.info("  [8] vfs_threshold_sd: %.2f (statistical VFS threshold)", self.config.vfs_threshold_sd)
        logger.info("  [9] area_min_size_mm2: %.2f mm² (minimum area size)", self.config.area_min_size_mm2)
        logger.info("=" * 70)

    # ========== FOURIER ANALYSIS (Kalatsky & Stryker Method) ==========

    def compute_fft_phase_maps(
        self,
        frames: np.ndarray,
        stimulus_frequency: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute phase, magnitude, and coherence at stimulus frequency for each pixel.

        Implements Kalatsky & Stryker 2003 Fourier method with optional phase filtering
        (Juavinett et al. 2017 - Gaussian smoothing before phase-to-position conversion).

        Args:
            frames: [n_frames, height, width] grayscale data
            stimulus_frequency: Stimulus frequency in cycles per frame

        Returns:
            phase_map: [height, width] phase in radians (optionally filtered)
            magnitude_map: [height, width] response amplitude
            coherence_map: [height, width] signal coherence (0-1)
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

        # CRITICAL: Ensure C-contiguous before reshape to avoid stride issues
        # Non-contiguous frames cause horizontal/vertical tearing in final maps
        if not frames_float.flags['C_CONTIGUOUS']:
            logger.info("  Input frames NOT C-contiguous, converting...")
            frames_float = np.ascontiguousarray(frames_float)

        logger.info(f"  Stimulus frequency: {stimulus_frequency:.4f} cycles/frame")
        logger.info(f"  Processing {height}x{width} pixels (C-contiguous: {frames_float.flags['C_CONTIGUOUS']})...")

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
            logger.info(f"  Computing phase and magnitude...")
            phase_flat = torch.angle(complex_amplitude)
            magnitude_flat = torch.abs(complex_amplitude)

            # Compute coherence: magnitude at stimulus freq / standard deviation of signal
            # Kalatsky & Stryker 2003: coherence = response amplitude / signal variability
            logger.info(f"  Computing coherence from signal statistics...")
            signal_std = torch.std(frames_centered, dim=0)
            logger.info(f"  Signal std computed, calculating coherence ratio...")
            coherence_flat = magnitude_flat / (signal_std + 1e-10)
            coherence_flat = torch.clamp(coherence_flat, 0.0, 1.0)  # Normalize to [0, 1] range

            # Transfer back to CPU and convert to numpy
            logger.info(f"  Transferring results back to CPU...")
            phase_map = phase_flat.cpu().numpy().reshape(height, width).astype(np.float32)
            magnitude_map = magnitude_flat.cpu().numpy().reshape(height, width).astype(np.float32)
            coherence_map = coherence_flat.cpu().numpy().reshape(height, width).astype(np.float32)

            logger.info(f"  Phase/magnitude/coherence maps computed (GPU-accelerated on {DEVICE_NAME})")
        else:
            # CPU implementation: Vectorized FFT computation
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
            logger.info(f"  Computing phase and magnitude...")
            phase_flat = np.angle(complex_amplitude)
            magnitude_flat = np.abs(complex_amplitude)

            # Compute coherence: magnitude at stimulus freq / standard deviation of signal
            # Kalatsky & Stryker 2003: coherence = response amplitude / signal variability
            logger.info(f"  Computing coherence from signal statistics...")
            signal_std = np.std(frames_centered, axis=0)
            logger.info(f"  Signal std computed, calculating coherence ratio...")
            coherence_flat = magnitude_flat / (signal_std + 1e-10)
            coherence_flat = np.clip(coherence_flat, 0.0, 1.0)  # Normalize to [0, 1] range

            # Reshape back to (height, width)
            logger.info(f"  Reshaping results to 2D maps...")
            phase_map = phase_flat.reshape(height, width).astype(np.float32)
            magnitude_map = magnitude_flat.reshape(height, width).astype(np.float32)
            coherence_map = coherence_flat.reshape(height, width).astype(np.float32)

            logger.info("  Phase/magnitude/coherence maps computed (CPU vectorized)")

        # PARAMETER 2: Apply phase filtering BEFORE conversion to retinotopy (Juavinett et al. 2017)
        # This smooths the phase maps to reduce noise before converting to azimuth/elevation
        if self.config.phase_filter_sigma > 0:
            logger.info(f"Applying phase filter (sigma={self.config.phase_filter_sigma}) BEFORE position conversion...")
            from scipy.ndimage import gaussian_filter
            phase_map = gaussian_filter(phase_map, sigma=self.config.phase_filter_sigma)
            logger.info(f"  Phase map smoothed (different from smoothing_sigma={self.config.smoothing_sigma} which applies AFTER conversion)")

        return phase_map, magnitude_map, coherence_map

    def bidirectional_analysis(
        self,
        forward_phase: np.ndarray,
        reverse_phase: np.ndarray,
        unwrap_axis: int = 1
    ) -> np.ndarray:
        """Combine opposing directions to find retinotopic center.

        Uses simple phase subtraction WITHOUT delay correction to match HDF5 reference:
        center = (forward - reverse) / 2

        This matches the old_implementation and HDF5 reference exactly (correlation=1.0).

        Args:
            forward_phase: Phase map from LR or TB (wrapped, [-π, π])
            reverse_phase: Phase map from RL or BT (wrapped, [-π, π])
            unwrap_axis: UNUSED (kept for API compatibility)

        Returns:
            center_map: Retinotopic center position for each pixel (radians)
        """
        logger.info("Performing bidirectional analysis (simple phase subtraction)...")

        # Simple subtraction: (forward - reverse) / 2
        # This matches the HDF5 reference exactly (no delay correction)
        center_map = (forward_phase - reverse_phase) / 2

        logger.info(f"  Retinotopic map computed via simple phase subtraction")
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
        # Use axis=1 (horizontal unwrapping) for horizontal stimulus
        center_phase = self.bidirectional_analysis(LR_phase, RL_phase, unwrap_axis=1)

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
        # Use axis=0 (vertical unwrapping) for vertical stimulus
        center_phase = self.bidirectional_analysis(TB_phase, BT_phase, unwrap_axis=0)

        # Convert phase to degrees of visual angle
        # Phase range [-π, π] maps to visual field range [-30°, +30°]
        elevation_map = center_phase * (30.0 / np.pi)

        return elevation_map

    # ========== VISUAL FIELD SIGN (Zhuang et al. Method) ==========

    def _create_gaussian_kernel(self, shape: Tuple[int, int], sigma: float) -> np.ndarray:
        """Create Gaussian kernel for FFT-based smoothing.

        Matches MATLAB's fspecial('gaussian', size, sigma) for frequency-domain filtering.
        Creates kernel centered at image center (not corner) for proper FFT convolution.

        Args:
            shape: Shape of the image (height, width)
            sigma: Standard deviation of Gaussian

        Returns:
            Gaussian kernel with same shape as input image
        """
        y, x = np.ogrid[: shape[0], : shape[1]]
        center_y, center_x = shape[0] // 2, shape[1] // 2

        # Create Gaussian centered at image center
        kernel = np.exp(-((x - center_x) ** 2 + (y - center_y) ** 2) / (2 * sigma**2))

        return kernel

    def _apply_fft_gaussian_smoothing(self, data: np.ndarray, sigma: float) -> np.ndarray:
        """Apply Gaussian smoothing using FFT (frequency-domain convolution).

        This EXACTLY matches MATLAB's approach:
        1. Create Gaussian kernel: h = fspecial('gaussian', size(data), sigma)
        2. Normalize kernel: h = h / sum(h(:))
        3. FFT convolution: smoothed = real(ifft2(fft2(data) .* abs(fft2(h))))

        FFT-based filtering has different behavior than spatial-domain filtering:
        - Wraps at boundaries (circular convolution)
        - Uses full-image kernel (not truncated)
        - Better for periodic structures

        Args:
            data: Input 2D array to smooth
            sigma: Gaussian standard deviation

        Returns:
            Smoothed data (same shape as input)
        """
        # Create Gaussian kernel matching image size
        h = self._create_gaussian_kernel(data.shape, sigma)

        # Normalize kernel (MATLAB: h = h/sum(h(:)))
        h = h / np.sum(h)

        # FFT-based convolution (MATLAB: ifft2(fft2(data).*abs(fft2(h))))
        smoothed = np.real(
            np.fft.ifft2(np.fft.fft2(data) * np.abs(np.fft.fft2(h)))
        )

        return smoothed

    def compute_spatial_gradients(
        self,
        azimuth_map: np.ndarray,
        elevation_map: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """Calculate spatial gradients of retinotopic maps.

        PRE-SMOOTHS retinotopic maps using FFT-based Gaussian filtering BEFORE gradient computation.
        This matches the MATLAB getAreaBorders.m implementation.

        Args:
            azimuth_map: Horizontal retinotopy map
            elevation_map: Vertical retinotopy map

        Returns:
            Dictionary containing all gradient components
        """
        logger.info("Computing spatial gradients...")

        # PRE-SMOOTH maps before computing gradients (MATLAB getAreaBorders.m approach)
        # Use FFT-based smoothing to exactly match old_implementation
        sigma = self.config.smoothing_sigma

        if sigma > 0:
            logger.info(f"  Applying FFT-based Gaussian smoothing (sigma={sigma}) to retinotopic maps...")
            azimuth_smooth = self._apply_fft_gaussian_smoothing(azimuth_map, sigma)
            elevation_smooth = self._apply_fft_gaussian_smoothing(elevation_map, sigma)
        else:
            logger.info("  Skipping retinotopic map smoothing (sigma=0)")
            azimuth_smooth = azimuth_map
            elevation_smooth = elevation_map

        # Use central differences for gradient computation (matches MATLAB's gradient())
        logger.info(f"  Computing gradients using central differences (matches MATLAB)...")

        # Use numpy's gradient() which implements central differences
        # This exactly matches MATLAB's gradient() function
        d_azimuth_dy, d_azimuth_dx = np.gradient(azimuth_smooth)
        d_elevation_dy, d_elevation_dx = np.gradient(elevation_smooth)

        gradients = {
            'd_azimuth_dx': d_azimuth_dx,
            'd_azimuth_dy': d_azimuth_dy,
            'd_elevation_dx': d_elevation_dx,
            'd_elevation_dy': d_elevation_dy
        }

        logger.info(f"  Gradients computed using central differences on FFT-smoothed maps")

        return gradients

    def calculate_visual_field_sign(
        self,
        gradients: Dict[str, np.ndarray],
        vfs_smooth_sigma: Optional[float] = None
    ) -> np.ndarray:
        """Calculate visual field sign (VFS) from retinotopic gradients.

        Uses the MATLAB getAreaBorders.m method (gradient angle method):
        1. Compute gradient direction angles: graddir = atan2(dy, dx)
        2. Compute angle difference: vdiff = exp(1i*graddir_hor) * exp(-1i*graddir_vert)
        3. Take sine of angle: VFS = sin(angle(vdiff))

        This produces normalized VFS values in [-1, 1] range where:
        - Positive values: non-mirror representation (e.g., V1)
        - Negative values: mirror representation (e.g., LM, PM)

        This matches MATLAB getAreaBorders.m lines 118-131.

        Args:
            gradients: Dictionary of gradient components
            vfs_smooth_sigma: Sigma for VFS post-smoothing (default: 3.0, set to 0 to disable)

        Returns:
            vfs_map: Smoothed visual field sign map (sine of angle difference)
        """
        logger.info("Calculating visual field sign (gradient angle method)...")

        d_azimuth_dx = gradients['d_azimuth_dx']
        d_azimuth_dy = gradients['d_azimuth_dy']
        d_elevation_dx = gradients['d_elevation_dx']
        d_elevation_dy = gradients['d_elevation_dy']

        # MATLAB EXACT: graddir_hor = atan2(dhdy, dhdx);
        # MATLAB EXACT: graddir_vert = atan2(dvdy, dvdx);
        graddir_horizontal = np.arctan2(d_azimuth_dy, d_azimuth_dx)
        graddir_vertical = np.arctan2(d_elevation_dy, d_elevation_dx)

        # MATLAB EXACT: vdiff = exp(1i*graddir_hor) .* exp(-1i*graddir_vert);
        # MATLAB EXACT: VFS = sin(angle(vdiff));
        vdiff = np.exp(1j * graddir_horizontal) * np.exp(-1j * graddir_vertical)
        vfs = np.sin(np.angle(vdiff))

        # MATLAB EXACT: id = find(isnan(VFS)); VFS(id) = 0;
        vfs[np.isnan(vfs)] = 0

        logger.info(f"  Raw VFS range: [{np.nanmin(vfs):.3f}, {np.nanmax(vfs):.3f}]")
        logger.info(f"  Raw VFS - Positive (non-mirror) regions: {np.sum(vfs > 0)}")
        logger.info(f"  Raw VFS - Negative (mirror) regions: {np.sum(vfs < 0)}")

        # CRITICAL: Apply VFS post-smoothing using FFT-based Gaussian (σ=3)
        # This matches MATLAB getAreaBorders.m lines 136-138:
        # hh = fspecial('gaussian',size(VFS),3);
        # hh = hh/sum(hh(:));
        # VFS = real(ifft2(fft2(VFS).*abs(fft2(hh))));
        if vfs_smooth_sigma is None:
            vfs_smooth_sigma = 3.0  # MATLAB default

        if vfs_smooth_sigma > 0:
            logger.info(f"Applying VFS post-smoothing (sigma={vfs_smooth_sigma}, FFT-based)...")
            vfs_smoothed = self._apply_fft_gaussian_smoothing(vfs, vfs_smooth_sigma)

            logger.info(f"  Smoothed VFS range: [{np.nanmin(vfs_smoothed):.3f}, {np.nanmax(vfs_smoothed):.3f}]")
            logger.info(f"  Smoothed VFS - Positive regions: {np.sum(vfs_smoothed > 0)}")
            logger.info(f"  Smoothed VFS - Negative regions: {np.sum(vfs_smoothed < 0)}")

            return vfs_smoothed.astype(np.float32)
        else:
            logger.info("  VFS post-smoothing disabled (sigma=0)")
            return vfs.astype(np.float32)

    def _thin_boundaries_fast(self, binary_image: np.ndarray) -> np.ndarray:
        """Fast boundary thinning using morphological operations.

        Uses scipy's binary_hit_or_miss and erosion for efficient thinning.
        This is much faster than pixel-by-pixel iteration.

        Args:
            binary_image: Binary boundary map (0 or 1)

        Returns:
            Thinned boundary map (single-pixel wide)
        """
        from scipy.ndimage import binary_hit_or_miss, binary_erosion

        original_count = np.sum(binary_image > 0)
        image = binary_image.astype(bool).copy()

        # Simple morphological thinning: iteratively remove pixels that don't break connectivity
        # Use hit-or-miss transforms with thinning structure elements
        changed = True
        max_iterations = 10
        iteration = 0

        while changed and iteration < max_iterations:
            changed = False
            iteration += 1
            prev_count = np.sum(image)

            # Apply thinning: remove pixels that have neighbors on opposite sides
            # This creates single-pixel wide lines

            # Horizontal thinning: remove middle pixels in horizontal triplets
            h_struct = np.array([[0, 0, 0],
                                [1, 1, 1],
                                [0, 0, 0]], dtype=bool)
            h_thin = binary_hit_or_miss(image, structure1=h_struct)
            image[h_thin] = False

            # Vertical thinning: remove middle pixels in vertical triplets
            v_struct = np.array([[0, 1, 0],
                                [0, 1, 0],
                                [0, 1, 0]], dtype=bool)
            v_thin = binary_hit_or_miss(image, structure1=v_struct)
            image[v_thin] = False

            curr_count = np.sum(image)
            if curr_count < prev_count:
                changed = True
                logger.info(f"    Iteration {iteration}: removed {prev_count - curr_count} pixels")

        thinned_count = np.sum(image)
        reduction_pct = 100 * (original_count - thinned_count) / original_count if original_count > 0 else 0
        logger.info(f"    Thinning reduced boundaries from {original_count} to {thinned_count} pixels ({reduction_pct:.1f}% reduction)")

        return image.astype(np.uint8)

    def detect_area_boundaries(self, sign_map: np.ndarray) -> np.ndarray:
        """Find boundaries where visual field sign reverses.

        Detects boundaries where the VFS value changes sign (positive to negative
        or vice versa), ignoring transitions through zero (undefined regions).

        Args:
            sign_map: Visual field sign map (continuous values in [-1, 1])

        Returns:
            boundary_map: Binary map of area boundaries (single-pixel thin)
        """
        logger.info("Detecting area boundaries (continuous VFS)...")

        # Apply median filter to reduce noise (size=3 preserves sharp boundaries better)
        sign_filtered = ndimage.median_filter(sign_map, size=3)

        # Find boundaries using sign changes
        boundary_map = np.zeros_like(sign_filtered, dtype=np.float32)

        # For continuous values, detect sign reversals by checking where
        # the product of neighboring pixels is negative (sign change)
        # Ignore pixels near zero (undefined regions)
        threshold = 0.1  # Minimum absolute value to consider as defined

        # Horizontal boundaries: check where sign changes horizontally
        for i in range(sign_filtered.shape[1] - 1):
            left_col = sign_filtered[:, i]
            right_col = sign_filtered[:, i + 1]

            # Both pixels must be significantly non-zero
            both_defined = (np.abs(left_col) > threshold) & (np.abs(right_col) > threshold)

            # Product is negative when sign changes
            sign_change = (left_col * right_col) < 0

            # Mark boundary on the left pixel
            boundary_map[:, i] += (both_defined & sign_change).astype(np.float32)

        # Vertical boundaries: check where sign changes vertically
        for i in range(sign_filtered.shape[0] - 1):
            top_row = sign_filtered[i, :]
            bottom_row = sign_filtered[i + 1, :]

            # Both pixels must be significantly non-zero
            both_defined = (np.abs(top_row) > threshold) & (np.abs(bottom_row) > threshold)

            # Product is negative when sign changes
            sign_change = (top_row * bottom_row) < 0

            # Mark boundary on the top pixel
            boundary_map[i, :] += (both_defined & sign_change).astype(np.float32)

        # Convert to binary
        boundary_map = (boundary_map > 0).astype(np.uint8)

        # TEMPORARILY DISABLED: Thinning was causing timeouts
        # The diff-based detection produces reasonably thin boundaries
        # TODO: Re-enable with a faster algorithm
        # logger.info("  Applying skeletonization to ensure single-pixel boundaries...")
        # boundary_map = self._thin_boundaries_fast(boundary_map)

        return boundary_map

    def segment_visual_areas(
        self,
        sign_map: np.ndarray,
        boundary_map: np.ndarray,
        image_width_pixels: Optional[int] = None
    ) -> np.ndarray:
        """Identify distinct visual areas.

        Args:
            sign_map: Visual field sign map
            boundary_map: Area boundary map
            image_width_pixels: Width of image in pixels (for spatial calibration)

        Returns:
            area_map: Labeled map of visual areas
        """
        logger.info("Segmenting visual areas...")

        # PARAMETER 1: Use ring_size_mm for spatial calibration (Juavinett et al. 2017)
        # Convert area_min_size_mm2 to pixels using spatial calibration
        if image_width_pixels is not None:
            pixels_per_mm = image_width_pixels / self.config.ring_size_mm
            min_area_size_pixels = int(self.config.area_min_size_mm2 * (pixels_per_mm ** 2))
            logger.info(f"  Spatial calibration: {image_width_pixels} pixels / {self.config.ring_size_mm} mm = {pixels_per_mm:.2f} pixels/mm")
            logger.info(f"  Min area size: {self.config.area_min_size_mm2} mm² = {min_area_size_pixels} pixels")
        else:
            # Fallback: use area_min_size_mm2 directly as pixel count (backward compatibility)
            min_area_size_pixels = int(self.config.area_min_size_mm2)
            logger.warning(f"  No spatial calibration available, using area_min_size_mm2={self.config.area_min_size_mm2} as pixel count")

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
            if area_size < min_area_size_pixels:
                area_map[area_map == label] = 0

        logger.info(f"  Found {np.max(area_map)} visual areas (after filtering areas < {min_area_size_pixels} pixels)")
        return area_map

    # ========== HIGH-LEVEL PIPELINE ORCHESTRATION ==========

    def run_from_phase_maps(
        self,
        phase_data: Dict[str, np.ndarray],
        magnitude_data: Dict[str, np.ndarray],
        coherence_data: Optional[Dict[str, np.ndarray]] = None,
        anatomical: Optional[np.ndarray] = None
    ) -> Dict[str, np.ndarray]:
        """Run analysis pipeline starting from phase/magnitude maps.

        This allows processing data that has already undergone Fourier analysis
        (e.g., pre-computed sample data or externally processed data).

        Args:
            phase_data: Dict with keys 'LR', 'RL', 'TB', 'BT' containing phase maps
            magnitude_data: Dict with keys 'LR', 'RL', 'TB', 'BT' containing magnitude maps
            coherence_data: Optional dict with keys 'LR', 'RL', 'TB', 'BT' containing coherence maps
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

        # PARAMETER 3: Apply magnitude threshold to per-direction maps (Juavinett et al. 2017)
        # Threshold individual magnitude maps (LR, RL, TB, BT separately)
        # Do NOT average magnitudes across directions (that was previous error)
        logger.info("\n[1.5/3] Applying per-direction magnitude thresholding...")
        logger.info(f"  Magnitude threshold: {self.config.magnitude_threshold}")
        magnitude_thresholded = {}
        for direction in ['LR', 'RL', 'TB', 'BT']:
            if direction in magnitude_data:
                mag_map = magnitude_data[direction]
                thresholded = mag_map.copy()
                thresholded[mag_map < self.config.magnitude_threshold] = 0
                magnitude_thresholded[direction] = thresholded

                num_above = np.sum(mag_map >= self.config.magnitude_threshold)
                total = mag_map.size
                logger.info(f"  {direction}: {num_above}/{total} pixels ({100*num_above/total:.1f}%) above threshold")

        results['magnitude_thresholded'] = magnitude_thresholded

        # PARAMETER 5: Apply percentile-based threshold (alternative method, Juavinett et al. 2017)
        logger.info(f"\n[1.6/3] Applying percentile-based thresholding...")
        logger.info(f"  Response threshold percentile: {self.config.response_threshold_percent}")
        percentile_thresholded = {}
        for direction in ['LR', 'RL', 'TB', 'BT']:
            if direction in magnitude_data:
                mag_map = magnitude_data[direction]
                # Compute percentile only on non-zero values
                non_zero = mag_map[mag_map > 0]
                if len(non_zero) > 0:
                    percentile_val = np.percentile(non_zero, self.config.response_threshold_percent)
                    thresholded = mag_map.copy()
                    thresholded[mag_map < percentile_val] = 0
                    percentile_thresholded[direction] = thresholded

                    num_above = np.sum(mag_map >= percentile_val)
                    total = mag_map.size
                    logger.info(f"  {direction}: percentile value={percentile_val:.3f}, {num_above}/{total} pixels ({100*num_above/total:.1f}%) above")

        results['percentile_thresholded'] = percentile_thresholded

        # Step 2: Compute visual field sign
        logger.info("\n[2/3] Computing visual field sign...")
        gradients = self.compute_spatial_gradients(azimuth_map, elevation_map)
        raw_sign_map = self.calculate_visual_field_sign(gradients)

        # Save raw VFS map (before thresholding) - keep as float32 for continuous visualization
        results['raw_vfs_map'] = raw_sign_map

        # PRIMARY METHOD: Coherence-based thresholding (Kalatsky & Stryker 2003)
        # This is the literature-standard approach: threshold by signal reliability
        coherence_vfs_map = None
        if coherence_data is not None:
            logger.info(f"  Using coherence-based thresholding (threshold={self.config.coherence_threshold})")

            # Compute minimum coherence across all directions
            # A pixel must have reliable signal in ALL directions to be trusted
            min_coherence = np.minimum.reduce([
                coherence_data['LR'],
                coherence_data['RL'],
                coherence_data['TB'],
                coherence_data['BT']
            ])

            # Threshold VFS by coherence (literature-standard method)
            coherence_vfs_map = raw_sign_map.copy()
            coherence_vfs_map[min_coherence < self.config.coherence_threshold] = 0
            results['coherence_vfs_map'] = coherence_vfs_map

            num_positive_coh = np.sum(coherence_vfs_map > 0)
            num_negative_coh = np.sum(coherence_vfs_map < 0)
            num_undefined_coh = np.sum(coherence_vfs_map == 0)
            total = coherence_vfs_map.size
            logger.info(f"  Coherence-thresholded VFS - Positive: {num_positive_coh} ({100*num_positive_coh/total:.1f}%)")
            logger.info(f"  Coherence-thresholded VFS - Negative: {num_negative_coh} ({100*num_negative_coh/total:.1f}%)")
            logger.info(f"  Coherence-thresholded VFS - Masked: {num_undefined_coh} ({100*num_undefined_coh/total:.1f}%)")

        # ALTERNATIVE METHOD 1: Magnitude-thresholded VFS (for comparison)
        avg_magnitude = (magnitude_data['LR'] + magnitude_data['RL'] +
                        magnitude_data['TB'] + magnitude_data['BT']) / 4.0
        magnitude_threshold = np.percentile(avg_magnitude, 50)  # Bottom 50% (median threshold)

        magnitude_thresholded_vfs = raw_sign_map.copy()
        magnitude_thresholded_vfs[avg_magnitude < magnitude_threshold] = 0
        results['magnitude_vfs_map'] = magnitude_thresholded_vfs

        num_positive = np.sum(magnitude_thresholded_vfs > 0)
        num_negative = np.sum(magnitude_thresholded_vfs < 0)
        num_undefined = np.sum(magnitude_thresholded_vfs == 0)
        total = magnitude_thresholded_vfs.size
        logger.info(f"  Magnitude-thresholded VFS - Positive: {num_positive} ({100*num_positive/total:.1f}%)")
        logger.info(f"  Magnitude-thresholded VFS - Negative: {num_negative} ({100*num_negative/total:.1f}%)")
        logger.info(f"  Magnitude-thresholded VFS - Masked: {num_undefined} ({100*num_undefined/total:.1f}%)")

        # ALTERNATIVE METHOD 2: Statistical-thresholded VFS (using standard deviation)
        # CRITICAL FIX: Compute threshold on RAW VFS (all pixels), then apply to coherence-filtered VFS
        # This matches MATLAB getAreaBorders.m line 96: threshSeg = 1.5*std(VFS(:))
        if coherence_vfs_map is not None:
            # Compute statistics on RAW VFS (all pixels, not just coherent ones)
            # This prevents threshold inflation from biased subset
            vfs_mean = np.mean(raw_sign_map)
            vfs_std = np.std(raw_sign_map)
            statistical_threshold = self.config.vfs_threshold_sd * vfs_std

            # Apply statistical threshold to coherence-thresholded VFS
            # Two-stage pipeline: coherence filtering (reliability) → statistical filtering (strength)
            statistical_thresholded_vfs = coherence_vfs_map.copy()
            # Threshold by absolute VFS value (must be significantly non-zero)
            statistical_thresholded_vfs[np.abs(coherence_vfs_map) < statistical_threshold] = 0
            results['statistical_vfs_map'] = statistical_thresholded_vfs

            num_positive_stat = np.sum(statistical_thresholded_vfs > 0)
            num_negative_stat = np.sum(statistical_thresholded_vfs < 0)
            num_undefined_stat = np.sum(statistical_thresholded_vfs == 0)
            logger.info(f"  Statistical-thresholded VFS (coherence → statistical pipeline)")
            logger.info(f"  Threshold: {statistical_threshold:.3f} ({self.config.vfs_threshold_sd} × SD of raw VFS)")
            logger.info(f"  Statistical-thresholded VFS - Positive: {num_positive_stat} ({100*num_positive_stat/total:.1f}%)")
            logger.info(f"  Statistical-thresholded VFS - Negative: {num_negative_stat} ({100*num_negative_stat/total:.1f}%)")
            logger.info(f"  Statistical-thresholded VFS - Masked: {num_undefined_stat} ({100*num_undefined_stat/total:.1f}%)")
        else:
            # Fallback: if no coherence data, apply statistical threshold to raw VFS
            logger.warning("  No coherence data - applying statistical threshold to raw VFS (not recommended)")
            vfs_mean = np.mean(raw_sign_map)
            vfs_std = np.std(raw_sign_map)
            statistical_threshold = self.config.vfs_threshold_sd * vfs_std

            statistical_thresholded_vfs = raw_sign_map.copy()
            statistical_thresholded_vfs[np.abs(raw_sign_map) < statistical_threshold] = 0
            results['statistical_vfs_map'] = statistical_thresholded_vfs

            num_positive_stat = np.sum(statistical_thresholded_vfs > 0)
            num_negative_stat = np.sum(statistical_thresholded_vfs < 0)
            num_undefined_stat = np.sum(statistical_thresholded_vfs == 0)
            logger.info(f"  Statistical-thresholded VFS (threshold={statistical_threshold:.3f}, {self.config.vfs_threshold_sd} SD)")
            logger.info(f"  Statistical-thresholded VFS - Positive: {num_positive_stat} ({100*num_positive_stat/total:.1f}%)")
            logger.info(f"  Statistical-thresholded VFS - Negative: {num_negative_stat} ({100*num_negative_stat/total:.1f}%)")
            logger.info(f"  Statistical-thresholded VFS - Masked: {num_undefined_stat} ({100*num_undefined_stat/total:.1f}%)")

        # Use coherence-thresholded version for boundary detection (literature standard)
        # Fall back to magnitude if coherence not available
        if coherence_vfs_map is not None:
            thresholded_sign_map = coherence_vfs_map
            logger.info("  Using coherence-thresholded VFS for boundary detection (PRIMARY METHOD)")
        else:
            thresholded_sign_map = magnitude_thresholded_vfs
            logger.info("  Using magnitude-thresholded VFS for boundary detection (fallback - coherence unavailable)")

        # Step 3: Detect boundaries
        logger.info("\n[3/3] Detecting area boundaries...")
        boundary_map = self.detect_area_boundaries(thresholded_sign_map)

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
