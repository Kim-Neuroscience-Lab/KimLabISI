"""
ISI Analysis Pipeline - Complete Fourier Analysis and Retinotopic Mapping

Implements the complete analysis pipeline following:
- Kalatsky & Stryker 2003: Fourier-based retinotopic analysis
- Marshel et al. 2011: ISI experimental procedures
- Zhuang et al. 2017: Visual field sign analysis
"""

import numpy as np
import h5py
import json
import os
from typing import Dict, Tuple, Any, Optional
from scipy import ndimage
from scipy.fft import fft, fftfreq
import cv2

from .logging_utils import get_logger

logger = get_logger(__name__)

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

class ISIAnalysis:
    """Complete analysis pipeline for ISI data"""

    def __init__(self, params: Optional[Dict[str, Any]] = None, layer_callback=None):
        """
        Initialize ISI analysis pipeline.

        Args:
            params: Analysis parameters dictionary (from ParameterManager)
                   If None, uses default values for all parameters
            layer_callback: Optional callback function(layer_name, layer_data) called when
                           intermediate results are ready for visualization
        """
        self.params = params or {}
        self.session_data = {}
        self.results = {}
        self.use_gpu = GPU_AVAILABLE
        self.layer_callback = layer_callback

        # Log GPU status on initialization
        if self.use_gpu:
            logger.info(f"✓ GPU acceleration enabled: {DEVICE_NAME}")
        else:
            logger.warning(f"⚠ GPU acceleration not available, using CPU: {DEVICE_NAME}")

    # ========== PREPROCESSING ==========

    def load_acquisition_data(self, session_path: str) -> Dict[str, Any]:
        """
        Load all data from acquisition session

        Args:
            session_path: Path to session directory

        Returns:
            Dictionary containing all loaded data
        """
        print(f"\nLoading session data from: {session_path}")

        # Load metadata
        metadata_path = os.path.join(session_path, "metadata.json")
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

        session_data = {'metadata': metadata}

        # Load anatomical image
        anatomical_path = os.path.join(session_path, "anatomical.npy")
        if os.path.exists(anatomical_path):
            session_data['anatomical'] = np.load(anatomical_path)
            print(f"  Loaded anatomical image: {session_data['anatomical'].shape}")

        # Load direction data (from acquisition section)
        directions = metadata.get('acquisition', {}).get('directions', ['LR', 'RL', 'TB', 'BT'])

        for direction in directions:
            print(f"  Loading {direction} data...")

            # Load camera data
            camera_path = os.path.join(session_path, f"{direction}_camera.h5")
            if os.path.exists(camera_path):
                with h5py.File(camera_path, 'r') as f:
                    frames = f['frames'][:]
                    timestamps = f['timestamps'][:]

                    # Convert RGB/BGR frames to grayscale if needed
                    # Camera saves BGR frames (h, w, 3), but analysis expects grayscale (h, w)
                    if len(frames.shape) == 4:
                        original_shape = frames.shape
                        if frames.shape[3] == 3:
                            # RGB/BGR to grayscale using proper luminance weights
                            # Use BGR order since OpenCV captures in BGR
                            # Weights: 0.299*R + 0.587*G + 0.114*B
                            print(f"    Converting BGR frames {original_shape} to grayscale...")
                            frames = np.dot(frames[..., :3], [0.114, 0.587, 0.299])
                            frames = frames.astype(np.uint8)
                            print(f"    Converted to grayscale: {frames.shape}")
                        elif frames.shape[3] == 4:
                            # RGBA to grayscale (ignore alpha channel)
                            print(f"    Converting RGBA frames {original_shape} to grayscale...")
                            frames = np.dot(frames[..., :3], [0.114, 0.587, 0.299])
                            frames = frames.astype(np.uint8)
                            print(f"    Converted to grayscale: {frames.shape}")
                        else:
                            raise ValueError(
                                f"Unexpected frame shape: {original_shape}. "
                                f"Expected (n, h, w) for grayscale or (n, h, w, 3) for RGB/BGR"
                            )
                    elif len(frames.shape) != 3:
                        raise ValueError(
                            f"Invalid frame array shape: {frames.shape}. "
                            f"Expected 3D (n, h, w) or 4D (n, h, w, c)"
                        )

                    camera_data = {
                        'frames': frames,
                        'timestamps': timestamps
                    }
                session_data[f'{direction}_camera'] = camera_data
                print(f"    Camera: {camera_data['frames'].shape} dtype={camera_data['frames'].dtype}")

            # Load stimulus events
            events_path = os.path.join(session_path, f"{direction}_events.json")
            if os.path.exists(events_path):
                with open(events_path, 'r') as f:
                    session_data[f'{direction}_events'] = json.load(f)

            # Load stimulus data
            stimulus_path = os.path.join(session_path, f"{direction}_stimulus.h5")
            if os.path.exists(stimulus_path):
                with h5py.File(stimulus_path, 'r') as f:
                    stimulus_data = {
                        'angles': f['angles'][:]
                    }
                session_data[f'{direction}_stimulus'] = stimulus_data

        self.session_data = session_data
        print("Session data loaded successfully!")
        return session_data

    def correlate_temporal_data(self, direction: str) -> np.ndarray:
        """
        Match camera frames to stimulus angles using timestamps

        Args:
            direction: Direction being processed

        Returns:
            Array of camera frames correlated with stimulus angles
        """
        print(f"  Correlating temporal data for {direction}...")

        camera_data = self.session_data[f'{direction}_camera']
        stimulus_data = self.session_data[f'{direction}_stimulus']
        events = self.session_data[f'{direction}_events']

        camera_frames = camera_data['frames']
        camera_timestamps = camera_data['timestamps']
        stimulus_angles = stimulus_data['angles']

        # Extract stimulus event timestamps and angles
        event_timestamps = []
        event_angles = []
        for event in events:
            event_timestamps.append(event['timestamp'])
            event_angles.append(event['angle'])

        event_timestamps = np.array(event_timestamps)
        event_angles = np.array(event_angles)

        # Interpolate camera frames to stimulus timing
        # This accounts for the 30 FPS camera vs 60 FPS stimulus timing
        correlated_frames = []
        correlated_angles = []

        for i, cam_timestamp in enumerate(camera_timestamps):
            # Find closest stimulus event
            time_diffs = np.abs(event_timestamps - cam_timestamp)
            closest_idx = np.argmin(time_diffs)

            # Only include if within reasonable time window (< 50ms)
            if time_diffs[closest_idx] < 50000:  # 50ms in microseconds
                correlated_frames.append(camera_frames[i])
                correlated_angles.append(event_angles[closest_idx])

        print(f"    Correlated {len(correlated_frames)} frames with stimulus")
        return np.array(correlated_frames), np.array(correlated_angles)

    def compensate_hemodynamic_delay(self, frames: np.ndarray, delay_sec: float = 1.5) -> np.ndarray:
        """
        Compensate for blood flow response delay

        Args:
            frames: Camera frames
            delay_sec: Hemodynamic delay in seconds

        Returns:
            Delay-compensated frames
        """
        # For simplified implementation, we'll apply a basic temporal shift
        # In practice, would use more sophisticated hemodynamic response modeling

        fps = 30  # Camera frame rate
        delay_frames = int(delay_sec * fps)

        if delay_frames >= len(frames):
            return frames

        # Shift frames to compensate for delay
        compensated = np.roll(frames, -delay_frames, axis=0)

        return compensated

    # ========== FOURIER ANALYSIS (Kalatsky & Stryker Method) ==========

    def compute_fft_phase_maps(self, frames: np.ndarray, angles: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute phase at stimulus frequency for each pixel

        Args:
            frames: [n_frames, height, width] 16-bit data
            angles: [n_frames] stimulus angles in degrees

        Returns:
            phase_map: [height, width] phase in radians
            magnitude_map: [height, width] response amplitude
        """
        print("    Computing FFT phase maps...")

        # Validate frame array shape
        if len(frames.shape) != 3:
            raise ValueError(
                f"Expected 3D frame array (n_frames, height, width), got shape {frames.shape}. "
                f"If frames are RGB/BGR, convert to grayscale first in load_acquisition_data()."
            )

        # Convert frames to float for processing
        frames_float = frames.astype(np.float32)
        n_frames, height, width = frames_float.shape

        # Create time vector
        t = np.arange(n_frames)

        # Determine stimulus frequency from angle progression
        # For drifting bar, frequency is cycles per acquisition
        angle_range = np.max(angles) - np.min(angles)
        num_cycles = self.session_data['metadata'].get('acquisition', {}).get('cycles', 1)
        stimulus_freq = num_cycles / n_frames  # Cycles per frame

        print(f"      Stimulus frequency: {stimulus_freq:.4f} cycles/frame")
        print(f"      Processing {height}x{width} pixels...")

        # Reshape frames from (n_frames, height, width) to (n_frames, n_pixels)
        n_pixels = height * width
        frames_reshaped = frames_float.reshape(n_frames, n_pixels)

        if self.use_gpu:
            # GPU-accelerated FFT computation using PyTorch
            logger.info(f"      Computing FFT for {n_pixels:,} pixels on {DEVICE_NAME}...")

            # Transfer to GPU
            frames_tensor = torch.from_numpy(frames_reshaped).to(DEVICE)

            # Remove DC component (mean) from all pixels at once
            frames_centered = frames_tensor - torch.mean(frames_tensor, dim=0, keepdim=True)

            # Compute FFT along time axis for all pixels simultaneously
            # PyTorch FFT returns complex tensor
            fft_result = torch.fft.fft(frames_centered, dim=0)

            # Get frequency bins (on CPU for argmin)
            freqs = fftfreq(n_frames)
            freq_idx = np.argmin(np.abs(freqs - stimulus_freq))
            logger.info(f"      Extracting phase/magnitude at frequency index {freq_idx}")

            # Extract complex amplitude at stimulus frequency for all pixels
            complex_amplitude = fft_result[freq_idx, :]

            # Compute phase and magnitude for all pixels
            phase_flat = torch.angle(complex_amplitude)
            magnitude_flat = torch.abs(complex_amplitude)

            # Transfer back to CPU and convert to numpy
            phase_map = phase_flat.cpu().numpy().reshape(height, width).astype(np.float32)
            magnitude_map = magnitude_flat.cpu().numpy().reshape(height, width).astype(np.float32)

            logger.info(f"    Phase maps computed (GPU-accelerated on {DEVICE_NAME})")

        else:
            # CPU fallback: Vectorized FFT computation
            logger.info(f"      Computing FFT for {n_pixels:,} pixels on CPU...")

            # Remove DC component (mean) from all pixels at once
            frames_centered = frames_reshaped - np.mean(frames_reshaped, axis=0, keepdims=True)

            # Compute FFT along time axis for all pixels simultaneously
            fft_result = fft(frames_centered, axis=0)

            # Get frequency bins
            freqs = fftfreq(n_frames)

            # Find frequency index closest to stimulus frequency
            freq_idx = np.argmin(np.abs(freqs - stimulus_freq))
            print(f"      Extracting phase/magnitude at frequency index {freq_idx}")

            # Extract complex amplitude at stimulus frequency for all pixels
            complex_amplitude = fft_result[freq_idx, :]

            # Compute phase and magnitude for all pixels
            phase_flat = np.angle(complex_amplitude)
            magnitude_flat = np.abs(complex_amplitude)

            # Reshape back to (height, width)
            phase_map = phase_flat.reshape(height, width).astype(np.float32)
            magnitude_map = magnitude_flat.reshape(height, width).astype(np.float32)

            print("    Phase maps computed (CPU vectorized)")

        return phase_map, magnitude_map

    def bidirectional_analysis(self, forward_phase: np.ndarray, reverse_phase: np.ndarray) -> np.ndarray:
        """
        Combine opposing directions to find retinotopic center

        Args:
            forward_phase: Phase map from LR or TB
            reverse_phase: Phase map from RL or BT

        Returns:
            center_map: Estimated center position for each pixel
        """
        print("    Performing bidirectional analysis...")

        # The retinotopic center is where forward and reverse phases are equal
        # This removes the hemodynamic delay component

        if self.use_gpu:
            # GPU-accelerated phase unwrapping and averaging
            logger.info(f"      Unwrapping phases on {DEVICE_NAME}...")

            # Transfer to GPU
            forward_tensor = torch.from_numpy(forward_phase).to(DEVICE)
            reverse_tensor = torch.from_numpy(reverse_phase).to(DEVICE)

            # Unwrap phases row-by-row on GPU
            # PyTorch doesn't have unwrap, so we implement it using diff and cumsum
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
            logger.info("      Unwrapping phases on CPU...")
            forward_unwrapped = np.apply_along_axis(np.unwrap, axis=1, arr=forward_phase)
            reverse_unwrapped = np.apply_along_axis(np.unwrap, axis=1, arr=reverse_phase)

            # Average the two directions
            center_map = (forward_unwrapped + reverse_unwrapped) / 2

            # Wrap back to [-π, π]
            center_map = np.arctan2(np.sin(center_map), np.cos(center_map))

        return center_map

    # ========== RETINOTOPIC MAPPING ==========

    def generate_azimuth_map(self, LR_phase: np.ndarray, RL_phase: np.ndarray) -> np.ndarray:
        """
        Generate horizontal retinotopy (azimuth) map

        Args:
            LR_phase: Phase map from left-to-right stimulus
            RL_phase: Phase map from right-to-left stimulus

        Returns:
            azimuth_map: Horizontal retinotopy in degrees (-60 to +60)
        """
        print("  Generating azimuth map...")

        # Combine LR and RL using bidirectional analysis
        center_phase = self.bidirectional_analysis(LR_phase, RL_phase)

        # Convert phase to degrees of visual angle
        # Phase range [-π, π] maps to visual field range [-60°, +60°]
        azimuth_map = center_phase * (60.0 / np.pi)

        return azimuth_map

    def generate_elevation_map(self, TB_phase: np.ndarray, BT_phase: np.ndarray) -> np.ndarray:
        """
        Generate vertical retinotopy (elevation) map

        Args:
            TB_phase: Phase map from top-to-bottom stimulus
            BT_phase: Phase map from bottom-to-top stimulus

        Returns:
            elevation_map: Vertical retinotopy in degrees (-30 to +30)
        """
        print("  Generating elevation map...")

        # Combine TB and BT using bidirectional analysis
        center_phase = self.bidirectional_analysis(TB_phase, BT_phase)

        # Convert phase to degrees of visual angle
        # Phase range [-π, π] maps to visual field range [-30°, +30°]
        elevation_map = center_phase * (30.0 / np.pi)

        return elevation_map

    # ========== VISUAL FIELD SIGN (Zhuang et al. Method) ==========

    def compute_spatial_gradients(self, azimuth_map: np.ndarray, elevation_map: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Calculate spatial gradients of retinotopic maps

        Args:
            azimuth_map: Horizontal retinotopy map
            elevation_map: Vertical retinotopy map

        Returns:
            Dictionary containing all gradient components
        """
        print("  Computing spatial gradients...")

        # Smooth maps before computing gradients (reduce noise)
        # Use smoothing_sigma parameter or default to 2.0
        sigma = self.params.get('smoothing_sigma', 2.0)

        if self.use_gpu:
            # GPU-accelerated gradient computation
            logger.info(f"    Computing gradients on {DEVICE_NAME}...")

            # Note: Gaussian filtering still uses scipy (CPU) as it's efficient and
            # GPU transfer overhead may not be worth it for this operation
            azimuth_smooth = ndimage.gaussian_filter(azimuth_map, sigma=sigma)
            elevation_smooth = ndimage.gaussian_filter(elevation_map, sigma=sigma)

            # Transfer smoothed maps to GPU for gradient computation
            azimuth_tensor = torch.from_numpy(azimuth_smooth).to(DEVICE)
            elevation_tensor = torch.from_numpy(elevation_smooth).to(DEVICE)

            # Compute gradients using PyTorch's gradient function
            # torch.gradient returns tuple of (dy, dx) for 2D arrays
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
            logger.info("    Computing gradients on CPU...")
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

    def calculate_visual_field_sign(self, gradients: Dict[str, np.ndarray]) -> np.ndarray:
        """
        Calculate sign of visual field representation

        VFS = sign(d_azimuth_dx * d_elevation_dy - d_azimuth_dy * d_elevation_dx)

        Args:
            gradients: Dictionary of gradient components

        Returns:
            sign_map: +1 (non-mirror) or -1 (mirror) for each pixel
        """
        print("  Calculating visual field sign...")

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
        """
        Find boundaries where visual field sign reverses

        Args:
            sign_map: Visual field sign map

        Returns:
            boundary_map: Binary map of area boundaries
        """
        print("  Detecting area boundaries...")

        # Apply median filter to reduce noise
        sign_filtered = ndimage.median_filter(sign_map, size=5)

        # Find boundaries using morphological operations
        # Boundaries occur where sign changes
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

    def segment_visual_areas(self, sign_map: np.ndarray, boundary_map: np.ndarray,
                           min_area_size: Optional[int] = None) -> np.ndarray:
        """
        Identify distinct visual areas

        Args:
            sign_map: Visual field sign map
            boundary_map: Area boundary map
            min_area_size: Minimum area size in pixels (uses parameter if None)

        Returns:
            area_map: Labeled map of visual areas
        """
        print("  Segmenting visual areas...")

        # Use area_min_size_mm2 parameter or default to 1000
        if min_area_size is None:
            min_area_size = int(self.params.get('area_min_size_mm2', 1000))

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

        print(f"    Found {np.max(area_map)} visual areas")
        return area_map

    # ========== COMPLETE ANALYSIS PIPELINE ==========

    def analyze_session(self, session_path: str) -> Dict[str, Any]:
        """
        Run complete analysis pipeline on a session

        Args:
            session_path: Path to session directory

        Returns:
            Complete analysis results
        """
        print("\n" + "="*60)
        print("STARTING ISI ANALYSIS PIPELINE")
        print("="*60)

        # Step 1: Load data
        self.load_acquisition_data(session_path)

        # Step 2: Process each direction
        phase_maps = {}
        magnitude_maps = {}

        # Get directions from metadata (nested under 'acquisition')
        directions = self.session_data['metadata'].get('acquisition', {}).get('directions', ['LR', 'RL', 'TB', 'BT'])
        for direction in directions:
            print(f"\nProcessing {direction} direction...")

            # Correlate temporal data
            frames, angles = self.correlate_temporal_data(direction)

            # Compensate hemodynamic delay
            frames = self.compensate_hemodynamic_delay(frames)

            # Compute phase maps
            phase_map, magnitude_map = self.compute_fft_phase_maps(frames, angles)

            phase_maps[direction] = phase_map
            magnitude_maps[direction] = magnitude_map

        # Step 3: Generate retinotopic maps
        print("\nGenerating retinotopic maps...")
        azimuth_map = self.generate_azimuth_map(phase_maps['LR'], phase_maps['RL'])

        # Publish azimuth map for real-time visualization
        if self.layer_callback:
            self.layer_callback('azimuth_map', azimuth_map)

        elevation_map = self.generate_elevation_map(phase_maps['TB'], phase_maps['BT'])

        # Publish elevation map for real-time visualization
        if self.layer_callback:
            self.layer_callback('elevation_map', elevation_map)

        # Step 4: Visual field sign analysis
        print("\nPerforming visual field sign analysis...")
        gradients = self.compute_spatial_gradients(azimuth_map, elevation_map)
        sign_map = self.calculate_visual_field_sign(gradients)

        # Publish sign map for real-time visualization
        if self.layer_callback:
            self.layer_callback('sign_map', sign_map)

        boundary_map = self.detect_area_boundaries(sign_map)

        # Publish boundary map for real-time visualization
        if self.layer_callback:
            self.layer_callback('boundary_map', boundary_map)

        area_map = self.segment_visual_areas(sign_map, boundary_map)

        # Compile results
        results = {
            'phase_maps': phase_maps,
            'magnitude_maps': magnitude_maps,
            'azimuth_map': azimuth_map,
            'elevation_map': elevation_map,
            'gradients': gradients,
            'sign_map': sign_map,
            'boundary_map': boundary_map,
            'area_map': area_map,
            'anatomical': self.session_data.get('anatomical'),
            'metadata': self.session_data['metadata']
        }

        self.results = results

        print("\n" + "="*60)
        print("ANALYSIS PIPELINE COMPLETE")
        print(f"Found {np.max(area_map)} distinct visual areas")
        print("="*60)

        return results

    # ========== EXPORT & VISUALIZATION ==========

    def save_results(self, output_path: str):
        """Save all analysis results"""
        print(f"\nSaving results to {output_path}")

        os.makedirs(output_path, exist_ok=True)

        # Save main results as HDF5
        results_path = os.path.join(output_path, "analysis_results.h5")
        with h5py.File(results_path, 'w') as f:
            # Retinotopic maps
            f.create_dataset('azimuth_map', data=self.results['azimuth_map'])
            f.create_dataset('elevation_map', data=self.results['elevation_map'])
            f.create_dataset('sign_map', data=self.results['sign_map'])
            f.create_dataset('area_map', data=self.results['area_map'])
            f.create_dataset('boundary_map', data=self.results['boundary_map'])

            # Phase maps for each direction
            phase_group = f.create_group('phase_maps')
            for direction, phase_map in self.results['phase_maps'].items():
                phase_group.create_dataset(direction, data=phase_map)

            # Magnitude maps for each direction
            magnitude_group = f.create_group('magnitude_maps')
            for direction, magnitude_map in self.results['magnitude_maps'].items():
                magnitude_group.create_dataset(direction, data=magnitude_map)

        # Save individual maps as images
        for name, data in [
            ('azimuth_map', self.results['azimuth_map']),
            ('elevation_map', self.results['elevation_map']),
            ('sign_map', self.results['sign_map']),
            ('area_map', self.results['area_map'])
        ]:
            # Normalize to 0-255 for image saving
            if name in ['azimuth_map', 'elevation_map']:
                # Map degrees to 0-255
                data_norm = ((data + 60) / 120 * 255).astype(np.uint8)
            else:
                data_norm = ((data - data.min()) / (data.max() - data.min()) * 255).astype(np.uint8)

            img_path = os.path.join(output_path, f"{name}.png")
            cv2.imwrite(img_path, data_norm)

        print(f"Results saved to {output_path}")


def main():
    """Test analysis pipeline"""
    # This would typically be called after data acquisition
    print("ISI Analysis Pipeline Test")
    print("Note: Run after acquiring data with isi_system.py")

if __name__ == "__main__":
    main()