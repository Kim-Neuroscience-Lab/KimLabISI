"""
Preview Generator for Downsampled Monitoring Streams

Generates downsampled preview frames for the Electron frontend monitoring interface.
Scientific data (full resolution) never passes through this system - only monitoring previews.

Key Design Principles:
- Hardware acceleration when available (NVENC, CUDA, Metal)
- Configurable downsample factors from stream configuration
- Non-blocking operation - no impact on critical stimulus/capture paths
- Quality degradation acceptable for monitoring purposes
"""

import numpy as np
from typing import Optional, Protocol, Tuple
from abc import abstractmethod
import logging

from domain.value_objects.stream_config import DisplayStreamConfig

logger = logging.getLogger(__name__)


class PreviewGeneratorInterface(Protocol):
    """Protocol for preview generation implementations"""

    @abstractmethod
    def downsample_frame(
        self,
        frame: np.ndarray,
        target_size: Optional[Tuple[int, int]] = None
    ) -> np.ndarray:
        """Downsample a frame to preview size"""
        ...

    @abstractmethod
    def get_supported_formats(self) -> list[str]:
        """Get supported input frame formats"""
        ...


class PreviewGenerator:
    """
    Generates downsampled preview frames for frontend monitoring

    This class handles downsampling of both stimulus and camera frames
    for display in the Electron frontend monitoring interface.
    """

    def __init__(
        self,
        config: DisplayStreamConfig,
        hardware_accelerated: bool = True
    ):
        """
        Initialize preview generator

        Args:
            config: Display stream configuration with preview settings
            hardware_accelerated: Enable hardware acceleration if available
        """
        self._config = config
        self._hardware_accelerated = hardware_accelerated
        self._backend: Optional[PreviewGeneratorInterface] = None

        self._initialize_backend()

    def _initialize_backend(self) -> None:
        """Initialize the best available backend for preview generation"""

        if self._hardware_accelerated:
            # Try hardware-accelerated backends first
            backend = self._try_cuda_backend()
            if backend is None:
                backend = self._try_metal_backend()
            if backend is None:
                backend = self._try_opencv_backend()
        else:
            # Use CPU-only backend
            backend = self._try_opencv_backend()

        if backend is None:
            # Fallback to pure NumPy implementation
            backend = NumpyPreviewBackend()
            logger.warning("Using fallback NumPy preview backend - performance may be limited")

        self._backend = backend
        logger.info(f"Initialized preview generator with backend: {type(backend).__name__}")

    def _try_cuda_backend(self) -> Optional[PreviewGeneratorInterface]:
        """Try to initialize CUDA backend for RTX 4070"""
        try:
            return CudaPreviewBackend()
        except ImportError:
            logger.debug("CUDA not available for preview generation")
            return None
        except Exception as e:
            logger.debug(f"Failed to initialize CUDA backend: {e}")
            return None

    def _try_metal_backend(self) -> Optional[PreviewGeneratorInterface]:
        """Try to initialize Metal backend for macOS"""
        try:
            return MetalPreviewBackend()
        except ImportError:
            logger.debug("Metal not available for preview generation")
            return None
        except Exception as e:
            logger.debug(f"Failed to initialize Metal backend: {e}")
            return None

    def _try_opencv_backend(self) -> Optional[PreviewGeneratorInterface]:
        """Try to initialize OpenCV backend"""
        try:
            return OpenCVPreviewBackend()
        except ImportError:
            logger.debug("OpenCV not available for preview generation")
            return None

    def generate_stimulus_preview(self, stimulus_frame: np.ndarray) -> np.ndarray:
        """
        Generate downsampled preview of stimulus frame for monitoring

        Args:
            stimulus_frame: Full resolution stimulus frame (e.g., 2560x1440)

        Returns:
            Downsampled preview frame (e.g., 512x512)
        """
        target_size = (self._config.preview_width, self._config.preview_height)
        return self._backend.downsample_frame(stimulus_frame, target_size)

    def generate_camera_preview(self, camera_frame: np.ndarray) -> np.ndarray:
        """
        Generate downsampled preview of camera frame for monitoring

        Args:
            camera_frame: Full resolution camera frame

        Returns:
            Downsampled preview frame for monitoring display
        """
        target_size = (self._config.preview_width, self._config.preview_height)
        return self._backend.downsample_frame(camera_frame, target_size)

    def get_config(self) -> DisplayStreamConfig:
        """Get current preview configuration"""
        return self._config

    def update_config(self, config: DisplayStreamConfig) -> None:
        """Update preview configuration"""
        self._config = config


class NumpyPreviewBackend:
    """Pure NumPy fallback implementation for preview generation"""

    def downsample_frame(
        self,
        frame: np.ndarray,
        target_size: Optional[Tuple[int, int]] = None
    ) -> np.ndarray:
        """
        Downsample frame using simple decimation

        This is a basic implementation using NumPy array slicing.
        Performance is limited but provides reliable fallback.
        """
        if target_size is None:
            # Default to half resolution
            target_size = (frame.shape[1] // 2, frame.shape[0] // 2)

        target_width, target_height = target_size
        original_height, original_width = frame.shape[:2]

        # Calculate decimation factors
        width_factor = original_width // target_width
        height_factor = original_height // target_height

        if width_factor <= 1 and height_factor <= 1:
            # No downsampling needed
            return frame

        # Simple decimation - take every Nth pixel
        if len(frame.shape) == 3:
            # Color image
            downsampled = frame[::height_factor, ::width_factor, :]
        else:
            # Grayscale image
            downsampled = frame[::height_factor, ::width_factor]

        return downsampled

    def get_supported_formats(self) -> list[str]:
        """NumPy backend supports basic array formats"""
        return ["uint8", "uint16", "float32", "float64"]


class OpenCVPreviewBackend:
    """OpenCV implementation for preview generation"""

    def __init__(self):
        try:
            import cv2
            self._cv2 = cv2
        except ImportError:
            raise ImportError("OpenCV not available")

    def downsample_frame(
        self,
        frame: np.ndarray,
        target_size: Optional[Tuple[int, int]] = None
    ) -> np.ndarray:
        """Downsample using OpenCV resize with area interpolation"""
        if target_size is None:
            target_size = (frame.shape[1] // 2, frame.shape[0] // 2)

        # Use INTER_AREA for downsampling - provides good quality
        downsampled = self._cv2.resize(
            frame,
            target_size,
            interpolation=self._cv2.INTER_AREA
        )
        return downsampled

    def get_supported_formats(self) -> list[str]:
        """OpenCV supports many formats"""
        return ["uint8", "uint16", "float32"]


class CudaPreviewBackend:
    """CUDA implementation for hardware-accelerated preview generation (RTX 4070)"""

    def __init__(self):
        try:
            import cupy as cp
            import cv2
            self._cp = cp
            self._cv2 = cv2
            # Initialize CUDA context
            self._cp.cuda.Device(0).use()
        except ImportError:
            raise ImportError("CuPy not available for CUDA acceleration")

    def downsample_frame(
        self,
        frame: np.ndarray,
        target_size: Optional[Tuple[int, int]] = None
    ) -> np.ndarray:
        """Hardware-accelerated downsampling using CUDA"""
        if target_size is None:
            target_size = (frame.shape[1] // 2, frame.shape[0] // 2)

        # Transfer to GPU
        gpu_frame = self._cp.asarray(frame)

        # Use CuPy for GPU-accelerated resize (simpler approach)
        # For production, could use NVENC or NPP libraries
        target_width, target_height = target_size
        original_height, original_width = gpu_frame.shape[:2]

        # Calculate decimation factors
        width_factor = original_width // target_width
        height_factor = original_height // target_height

        # GPU decimation
        if len(gpu_frame.shape) == 3:
            downsampled_gpu = gpu_frame[::height_factor, ::width_factor, :]
        else:
            downsampled_gpu = gpu_frame[::height_factor, ::width_factor]

        # Transfer back to CPU
        downsampled = self._cp.asnumpy(downsampled_gpu)
        return downsampled

    def get_supported_formats(self) -> list[str]:
        """CUDA backend supports numerical types"""
        return ["uint8", "uint16", "float32"]


class MetalPreviewBackend:
    """Metal implementation for hardware-accelerated preview generation (macOS)"""

    def __init__(self):
        # This would require Metal-Python bindings or PyObjC
        # For now, fallback to OpenCV
        try:
            import cv2
            self._cv2 = cv2
        except ImportError:
            raise ImportError("Metal preview backend not fully implemented")

    def downsample_frame(
        self,
        frame: np.ndarray,
        target_size: Optional[Tuple[int, int]] = None
    ) -> np.ndarray:
        """Metal-accelerated downsampling (placeholder implementation)"""
        # TODO: Implement actual Metal acceleration
        # For now, use OpenCV as fallback
        if target_size is None:
            target_size = (frame.shape[1] // 2, frame.shape[0] // 2)

        downsampled = self._cv2.resize(
            frame,
            target_size,
            interpolation=self._cv2.INTER_AREA
        )
        return downsampled

    def get_supported_formats(self) -> list[str]:
        """Metal backend format support"""
        return ["uint8", "uint16", "float32"]


def create_preview_generator(
    config: DisplayStreamConfig,
    hardware_accelerated: bool = True
) -> PreviewGenerator:
    """
    Factory function to create preview generator with appropriate configuration

    Args:
        config: Display stream configuration with preview settings
        hardware_accelerated: Enable hardware acceleration if available

    Returns:
        Configured preview generator instance
    """
    return PreviewGenerator(config, hardware_accelerated)