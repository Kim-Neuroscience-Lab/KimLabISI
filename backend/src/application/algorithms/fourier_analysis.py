"""
Fourier Analysis for Intrinsic Signal Imaging - Kalatsky & Stryker 2003 Method

This module implements the exact Fourier analysis method from:
Kalatsky & Stryker (2003) "New paradigm for optical imaging:
temporally encoded maps of intrinsic signal" Nature.

Uses validated scientific packages:
- scipy.fft for robust FFT implementation
- CuPy for optional GPU acceleration (RTX 4070 optimization)
- Maintains exact literature algorithm fidelity
"""

import logging
import numpy as np
from typing import Dict, Optional, Tuple, Union, Any
from datetime import datetime

# Standard scientific packages
import scipy.fft
from scipy.signal import windows

# Optional GPU acceleration
try:
    import cupy as cp
    import cupyx.scipy.fft as cupy_fft
    CUPY_AVAILABLE = True
except ImportError:
    cp = None
    cupy_fft = None
    CUPY_AVAILABLE = False

logger = logging.getLogger(__name__)


class FourierAnalyzer:
    """
    Fourier analysis for ISI retinotopic mapping following Kalatsky & Stryker 2003

    Implements the exact periodic stimulus analysis method from literature
    with modern computational backends (SciPy FFT + optional CuPy GPU acceleration).
    """

    def __init__(self, use_gpu: bool = True):
        """
        Initialize Fourier analyzer

        Args:
            use_gpu: Whether to use GPU acceleration if available
        """
        self.use_gpu = use_gpu and CUPY_AVAILABLE

        if self.use_gpu:
            try:
                # Test GPU availability
                cp.cuda.Device(0).use()
                logger.info("GPU acceleration enabled for Fourier analysis")
            except Exception as e:
                logger.warning(f"GPU not available, falling back to CPU: {e}")
                self.use_gpu = False
        else:
            if use_gpu and not CUPY_AVAILABLE:
                logger.warning("CuPy not available, using CPU-only Fourier analysis")

    async def analyze_isi_signal(
        self,
        frames: np.ndarray,
        stimulus_angles: np.ndarray,
        stimulus_frequency_hz: float = 0.1,
        sampling_frequency_hz: float = 30.0,
        apply_windowing: bool = True,
        window_type: str = "hann"
    ) -> Dict[str, Any]:
        """
        Analyze ISI signal using Kalatsky & Stryker 2003 Fourier method

        Args:
            frames: ISI camera frames (time, height, width) - 16-bit from PCO Panda
            stimulus_angles: Corresponding stimulus angles in degrees
            stimulus_frequency_hz: Stimulus temporal frequency (typically 0.1 Hz)
            sampling_frequency_hz: Camera sampling frequency (typically 30 Hz)
            apply_windowing: Whether to apply window function to reduce spectral leakage
            window_type: Window function type ('hann', 'blackman', 'hamming')

        Returns:
            Dictionary containing:
            - phase_map: Phase values representing preferred stimulus position
            - amplitude_map: Response amplitude (signal strength)
            - coherence_map: Coherence values (quality metric)
            - power_spectrum: Full power spectrum for quality assessment
            - analysis_metadata: Analysis parameters and quality metrics
        """
        logger.info("Starting ISI Fourier analysis using Kalatsky & Stryker method")

        try:
            # Validate inputs
            self._validate_inputs(frames, stimulus_angles, stimulus_frequency_hz, sampling_frequency_hz)

            # Convert to appropriate data type and backend
            if self.use_gpu:
                frames_proc = cp.asarray(frames, dtype=cp.float32)
                logger.debug("Processing on GPU with CuPy")
            else:
                frames_proc = np.asarray(frames, dtype=np.float32)
                logger.debug("Processing on CPU with NumPy/SciPy")

            # Apply preprocessing
            frames_proc = await self._preprocess_frames(
                frames_proc, apply_windowing, window_type
            )

            # Perform Fourier analysis following Kalatsky & Stryker method
            fourier_results = await self._kalatsky_fourier_analysis(
                frames_proc, stimulus_frequency_hz, sampling_frequency_hz
            )

            # Calculate coherence (quality metric from literature)
            coherence_map = self._calculate_coherence(
                fourier_results["complex_response"],
                fourier_results["total_power"]
            )

            # Extract phase and amplitude maps
            phase_map = self._extract_phase_map(fourier_results["complex_response"])
            amplitude_map = self._extract_amplitude_map(fourier_results["complex_response"])

            # Convert back to CPU if using GPU
            if self.use_gpu:
                phase_map = cp.asnumpy(phase_map)
                amplitude_map = cp.asnumpy(amplitude_map)
                coherence_map = cp.asnumpy(coherence_map)
                power_spectrum = cp.asnumpy(fourier_results["power_spectrum"])
            else:
                power_spectrum = fourier_results["power_spectrum"]

            # Calculate quality metrics
            analysis_metadata = self._calculate_analysis_metadata(
                phase_map, amplitude_map, coherence_map,
                stimulus_frequency_hz, sampling_frequency_hz
            )

            logger.info(f"Fourier analysis completed. Quality metrics: "
                       f"mean_coherence={analysis_metadata['mean_coherence']:.3f}, "
                       f"snr={analysis_metadata['signal_to_noise_ratio']:.2f}")

            return {
                "phase_map": phase_map,
                "amplitude_map": amplitude_map,
                "coherence_map": coherence_map,
                "power_spectrum": power_spectrum,
                "analysis_metadata": analysis_metadata
            }

        except Exception as e:
            logger.exception("Error in Fourier analysis")
            raise ISIAnalysisError(f"Fourier analysis failed: {str(e)}")

    def _validate_inputs(
        self,
        frames: np.ndarray,
        stimulus_angles: np.ndarray,
        stimulus_frequency_hz: float,
        sampling_frequency_hz: float
    ):
        """Validate input parameters for ISI analysis"""
        if frames.ndim != 3:
            raise ValueError("Frames must be 3D array (time, height, width)")

        if len(stimulus_angles) != frames.shape[0]:
            raise ValueError("Number of stimulus angles must match number of frames")

        if stimulus_frequency_hz <= 0 or stimulus_frequency_hz >= sampling_frequency_hz / 2:
            raise ValueError("Invalid stimulus frequency relative to sampling frequency")

        # Check for reasonable ISI parameters based on literature
        if sampling_frequency_hz < 10 or sampling_frequency_hz > 120:
            logger.warning(f"Unusual sampling frequency: {sampling_frequency_hz} Hz")

        if stimulus_frequency_hz > 1.0:
            logger.warning(f"High stimulus frequency for ISI: {stimulus_frequency_hz} Hz")

    async def _preprocess_frames(
        self,
        frames: Union[np.ndarray, 'cp.ndarray'],
        apply_windowing: bool,
        window_type: str
    ) -> Union[np.ndarray, 'cp.ndarray']:
        """Preprocess frames for Fourier analysis"""

        # Baseline correction (remove DC component)
        if self.use_gpu:
            frames_mean = cp.mean(frames, axis=0, keepdims=True)
            frames_corrected = frames - frames_mean
        else:
            frames_mean = np.mean(frames, axis=0, keepdims=True)
            frames_corrected = frames - frames_mean

        # Apply windowing to reduce spectral leakage
        if apply_windowing:
            n_frames = frames.shape[0]

            # Create window function
            if window_type == "hann":
                window = windows.hann(n_frames)
            elif window_type == "blackman":
                window = windows.blackman(n_frames)
            elif window_type == "hamming":
                window = windows.hamming(n_frames)
            else:
                raise ValueError(f"Unsupported window type: {window_type}")

            if self.use_gpu:
                window = cp.asarray(window)

            # Apply window along time dimension
            window_3d = window[:, np.newaxis, np.newaxis]
            frames_corrected = frames_corrected * window_3d

            logger.debug(f"Applied {window_type} windowing to reduce spectral leakage")

        return frames_corrected

    async def _kalatsky_fourier_analysis(
        self,
        frames: Union[np.ndarray, 'cp.ndarray'],
        stimulus_frequency_hz: float,
        sampling_frequency_hz: float
    ) -> Dict[str, Union[np.ndarray, 'cp.ndarray']]:
        """
        Implement exact Kalatsky & Stryker 2003 Fourier analysis method

        Key steps from literature:
        1. Compute FFT along time dimension
        2. Extract complex response at stimulus frequency
        3. Calculate power spectrum for quality assessment
        """

        # Compute FFT along time axis (axis=0)
        if self.use_gpu:
            fft_result = cupy_fft.rfft(frames, axis=0)
        else:
            fft_result = scipy.fft.rfft(frames, axis=0)

        # Calculate frequency bins
        n_frames = frames.shape[0]
        freq_bins = scipy.fft.rfftfreq(n_frames, 1.0 / sampling_frequency_hz)

        # Find frequency bin closest to stimulus frequency
        stimulus_bin = np.argmin(np.abs(freq_bins - stimulus_frequency_hz))
        logger.debug(f"Stimulus frequency {stimulus_frequency_hz} Hz maps to bin {stimulus_bin} "
                    f"(actual freq: {freq_bins[stimulus_bin]:.3f} Hz)")

        # Extract complex response at stimulus frequency (Kalatsky method)
        complex_response = fft_result[stimulus_bin, :, :]

        # Calculate total power for coherence analysis
        if self.use_gpu:
            power_spectrum = cp.abs(fft_result) ** 2
            total_power = cp.sum(power_spectrum, axis=0)
        else:
            power_spectrum = np.abs(fft_result) ** 2
            total_power = np.sum(power_spectrum, axis=0)

        return {
            "complex_response": complex_response,
            "power_spectrum": power_spectrum,
            "total_power": total_power,
            "frequency_bins": freq_bins,
            "stimulus_bin": stimulus_bin
        }

    def _calculate_coherence(
        self,
        complex_response: Union[np.ndarray, 'cp.ndarray'],
        total_power: Union[np.ndarray, 'cp.ndarray']
    ) -> Union[np.ndarray, 'cp.ndarray']:
        """
        Calculate coherence as quality metric (Kalatsky & Stryker method)

        Coherence = |response_at_stimulus_freq|² / total_power
        Values closer to 1 indicate stronger periodic response
        """
        if self.use_gpu:
            stimulus_power = cp.abs(complex_response) ** 2
            coherence = stimulus_power / (total_power + cp.finfo(cp.float32).eps)
            coherence = cp.clip(coherence, 0, 1)  # Ensure [0, 1] range
        else:
            stimulus_power = np.abs(complex_response) ** 2
            coherence = stimulus_power / (total_power + np.finfo(np.float32).eps)
            coherence = np.clip(coherence, 0, 1)  # Ensure [0, 1] range

        return coherence

    def _extract_phase_map(
        self,
        complex_response: Union[np.ndarray, 'cp.ndarray']
    ) -> Union[np.ndarray, 'cp.ndarray']:
        """
        Extract phase map from complex Fourier response

        Phase represents preferred stimulus position (core of Kalatsky method)
        Range: [-À, À] representing stimulus angles
        """
        if self.use_gpu:
            phase_map = cp.angle(complex_response)
        else:
            phase_map = np.angle(complex_response)

        return phase_map

    def _extract_amplitude_map(
        self,
        complex_response: Union[np.ndarray, 'cp.ndarray']
    ) -> Union[np.ndarray, 'cp.ndarray']:
        """
        Extract amplitude map from complex Fourier response

        Amplitude represents response strength at each pixel
        """
        if self.use_gpu:
            amplitude_map = cp.abs(complex_response)
        else:
            amplitude_map = np.abs(complex_response)

        return amplitude_map

    def _calculate_analysis_metadata(
        self,
        phase_map: np.ndarray,
        amplitude_map: np.ndarray,
        coherence_map: np.ndarray,
        stimulus_frequency_hz: float,
        sampling_frequency_hz: float
    ) -> Dict[str, Any]:
        """Calculate quality metrics and analysis metadata"""

        # Basic statistics
        mean_coherence = np.mean(coherence_map)
        std_coherence = np.std(coherence_map)
        mean_amplitude = np.mean(amplitude_map)

        # Signal-to-noise ratio estimate
        signal_power = np.mean(amplitude_map ** 2)
        noise_power = np.mean((amplitude_map - mean_amplitude) ** 2)
        snr = 10 * np.log10(signal_power / (noise_power + np.finfo(np.float32).eps))

        # Phase statistics
        phase_coherence = np.abs(np.mean(np.exp(1j * phase_map)))

        # Coverage statistics (pixels with significant response)
        coherence_threshold = 0.3  # Literature-based threshold
        significant_pixels = np.sum(coherence_map > coherence_threshold)
        coverage_fraction = significant_pixels / coherence_map.size

        return {
            "analysis_timestamp": datetime.now().isoformat(),
            "stimulus_frequency_hz": stimulus_frequency_hz,
            "sampling_frequency_hz": sampling_frequency_hz,
            "gpu_acceleration_used": self.use_gpu,

            # Quality metrics
            "mean_coherence": float(mean_coherence),
            "std_coherence": float(std_coherence),
            "mean_amplitude": float(mean_amplitude),
            "signal_to_noise_ratio": float(snr),
            "phase_coherence": float(phase_coherence),
            "coverage_fraction": float(coverage_fraction),
            "significant_pixels": int(significant_pixels),

            # Analysis parameters
            "coherence_threshold": coherence_threshold,
            "total_pixels": int(coherence_map.size)
        }


class ISIAnalysisError(Exception):
    """Raised when ISI Fourier analysis encounters errors"""
    pass