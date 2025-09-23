"""
Hardware Factory - Platform Detection and Hardware Abstraction

This module implements the hardware factory for cross-platform development
as specified in ADR-0008 (Cross-Platform Development Strategy) and
ADR-0010 (Hardware Abstraction Layer).

Factory Responsibilities:
- Platform detection (macOS vs Windows)
- Hardware capability detection
- Abstract interface instantiation
- Mock vs production hardware selection
- Development mode configuration
"""

import platform
import logging
from typing import Protocol, Dict, Type, Set
from enum import Enum
from pydantic import BaseModel, Field

from ..abstract.camera_interface import CameraInterface
from ..abstract.gpu_interface import GPUInterface
from ..abstract.timing_interface import TimingInterface
from ..abstract.display_interface import DisplayInterface
from ...domain.entities.workflow_state import HardwareRequirement


logger = logging.getLogger(__name__)


class PlatformType(Enum):
    """Supported platform types"""
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"  # For future expansion
    UNKNOWN = "unknown"


class HardwareCapability(BaseModel):
    """Hardware capability detection result using Pydantic V2"""
    hardware_type: HardwareRequirement
    available: bool = Field(description="Whether hardware is available")
    mock: bool = Field(description="Whether this is mock hardware")
    details: Dict[str, str] = Field(default_factory=dict, description="Hardware-specific details")

    model_config = {"use_enum_values": True}


class PlatformInfo(BaseModel):
    """Platform detection information using Pydantic V2"""
    platform_type: PlatformType
    system: str = Field(description="Platform system name")
    machine: str = Field(description="Machine architecture")
    version: str = Field(description="Platform version")
    development_mode: bool = Field(default=False, description="Whether in development mode")

    model_config = {"use_enum_values": True}


class HardwareFactory:
    """
    Cross-Platform Hardware Factory

    Implements platform detection and hardware abstraction instantiation
    following the dependency inversion principle. Provides mock hardware
    for development and production hardware for Windows deployment.

    Design Principles:
    - Platform detection determines implementation strategy
    - Abstract interfaces ensure consistent API across platforms
    - Mock hardware enables development without production equipment
    - Graceful degradation when hardware unavailable
    """

    def __init__(self, force_development_mode: bool = False):
        """
        Initialize hardware factory

        Args:
            force_development_mode: Force development mode regardless of platform
        """
        self._platform_info = self._detect_platform()
        self._development_mode = force_development_mode or self._platform_info.platform_type == PlatformType.MACOS.value
        self._platform_info.development_mode = self._development_mode

        # Initialize platform-specific imports
        self._camera_implementations = self._initialize_camera_implementations()
        self._gpu_implementations = self._initialize_gpu_implementations()
        self._timing_implementations = self._initialize_timing_implementations()
        self._display_implementations = self._initialize_display_implementations()

        logger.info(f"Hardware factory initialized for {self._platform_info.platform_type} "
                   f"(development_mode={self._development_mode})")

    @property
    def platform_info(self) -> PlatformInfo:
        """Get platform detection information"""
        return self._platform_info

    @property
    def development_mode(self) -> bool:
        """Whether factory is in development mode"""
        return self._development_mode

    def detect_hardware_capabilities(self) -> Dict[HardwareRequirement, HardwareCapability]:
        """
        Detect available hardware capabilities

        Returns:
            Dictionary mapping hardware requirements to capabilities
        """
        capabilities = {}

        # Development mode provides mock hardware
        if self._development_mode:
            capabilities.update({
                HardwareRequirement.DISPLAY: HardwareCapability(
                    hardware_type=HardwareRequirement.DISPLAY,
                    available=True,
                    mock=True,
                    details={"type": "mock_display", "platform": self._platform_info.platform_type}
                ),
                HardwareRequirement.GPU: HardwareCapability(
                    hardware_type=HardwareRequirement.GPU,
                    available=True,
                    mock=True,
                    details={"type": "metal_gpu" if self._platform_info.platform_type == PlatformType.MACOS.value else "mock_gpu"}
                ),
                HardwareRequirement.CAMERA: HardwareCapability(
                    hardware_type=HardwareRequirement.CAMERA,
                    available=True,
                    mock=True,
                    details={"type": "mock_camera", "model": "PCO Panda 4.2 Simulation"}
                ),
                HardwareRequirement.STORAGE: HardwareCapability(
                    hardware_type=HardwareRequirement.STORAGE,
                    available=True,
                    mock=True,
                    details={"type": "local_storage", "location": "development"}
                ),
                HardwareRequirement.DEV_MODE_BYPASS: HardwareCapability(
                    hardware_type=HardwareRequirement.DEV_MODE_BYPASS,
                    available=True,
                    mock=False,
                    details={"enabled": "true"}
                )
            })
        else:
            # Production mode detects actual hardware
            capabilities.update(self._detect_production_hardware())

        return capabilities

    def create_camera_interface(self) -> CameraInterface:
        """
        Create camera interface based on platform and availability

        Returns:
            Camera interface implementation
        """
        if self._development_mode:
            return self._camera_implementations["mock"]()
        else:
            return self._camera_implementations["production"]()

    def create_gpu_interface(self) -> GPUInterface:
        """
        Create GPU interface based on platform and availability

        Returns:
            GPU interface implementation
        """
        if self._development_mode:
            gpu_type = "metal" if self._platform_info.platform_type == PlatformType.MACOS.value else "mock"
            return self._gpu_implementations[gpu_type]()
        else:
            return self._gpu_implementations["directx"]()

    def create_timing_interface(self) -> TimingInterface:
        """
        Create timing interface based on platform

        Returns:
            Timing interface implementation
        """
        if self._development_mode:
            return self._timing_implementations["mock"]()
        else:
            return self._timing_implementations["windows"]()

    def create_display_interface(self) -> DisplayInterface:
        """
        Create display interface based on platform

        Returns:
            Display interface implementation
        """
        if self._development_mode:
            return self._display_implementations["mock"]()
        else:
            return self._display_implementations["directx"]()

    def get_available_hardware_requirements(self) -> Set[HardwareRequirement]:
        """
        Get set of available hardware requirements

        Returns:
            Set of available hardware requirements
        """
        capabilities = self.detect_hardware_capabilities()
        return {req for req, cap in capabilities.items() if cap.available}

    def _detect_platform(self) -> PlatformInfo:
        """Detect current platform information"""
        system_name = platform.system().lower()

        platform_map = {
            "windows": PlatformType.WINDOWS,
            "darwin": PlatformType.MACOS,
            "linux": PlatformType.LINUX
        }

        detected_platform = platform_map.get(system_name, PlatformType.UNKNOWN)

        return PlatformInfo(
            platform_type=detected_platform,
            system=platform.system(),
            machine=platform.machine(),
            version=platform.version()
        )

    def _detect_production_hardware(self) -> Dict[HardwareRequirement, HardwareCapability]:
        """Detect actual production hardware capabilities"""
        capabilities = {}

        # TODO: Implement actual hardware detection
        # This would probe for:
        # - RTX 4070 GPU with DirectX 12 support
        # - PCO Panda 4.2 camera via PCO SDK
        # - High-speed storage capabilities
        # - Display hardware configuration

        # For now, return placeholder detection
        if self._platform_info.platform_type == PlatformType.WINDOWS.value:
            capabilities.update({
                HardwareRequirement.DISPLAY: HardwareCapability(
                    hardware_type=HardwareRequirement.DISPLAY,
                    available=True,  # Assume available on Windows
                    mock=False,
                    details={"type": "directx12", "gpu": "RTX 4070"}
                ),
                HardwareRequirement.GPU: HardwareCapability(
                    hardware_type=HardwareRequirement.GPU,
                    available=True,  # Assume available on Windows
                    mock=False,
                    details={"type": "cuda", "model": "RTX 4070"}
                ),
                HardwareRequirement.CAMERA: HardwareCapability(
                    hardware_type=HardwareRequirement.CAMERA,
                    available=False,  # Requires actual detection
                    mock=False,
                    details={"type": "pco_sdk", "model": "PCO Panda 4.2"}
                ),
                HardwareRequirement.STORAGE: HardwareCapability(
                    hardware_type=HardwareRequirement.STORAGE,
                    available=True,  # Assume available
                    mock=False,
                    details={"type": "nvme", "model": "Samsung 990 PRO"}
                )
            })

        return capabilities

    def _initialize_camera_implementations(self) -> Dict[str, Type]:
        """Initialize camera implementation classes based on platform"""
        implementations = {}

        if self._platform_info.platform_type == PlatformType.WINDOWS.value:
            try:
                from ..windows.pco_camera import PCOCamera
                implementations["production"] = PCOCamera
            except ImportError:
                logger.warning("PCO camera implementation not available")

        # Always provide mock implementation
        from ..macos.mock_camera import MockCamera
        implementations["mock"] = MockCamera

        return implementations

    def _initialize_gpu_implementations(self) -> Dict[str, Type]:
        """Initialize GPU implementation classes based on platform"""
        implementations = {}

        if self._platform_info.platform_type == PlatformType.WINDOWS.value:
            try:
                from ..windows.directx_gpu import DirectXGPU
                implementations["directx"] = DirectXGPU
            except ImportError:
                logger.warning("DirectX GPU implementation not available")

        if self._platform_info.platform_type == PlatformType.MACOS.value:
            try:
                from ..macos.metal_gpu import MetalGPU
                implementations["metal"] = MetalGPU
            except ImportError:
                logger.warning("Metal GPU implementation not available")

        # Mock implementation for fallback
        from ..macos.mock_processing import MockProcessing
        implementations["mock"] = MockProcessing

        return implementations

    def _initialize_timing_implementations(self) -> Dict[str, Type]:
        """Initialize timing implementation classes based on platform"""
        implementations = {}

        if self._platform_info.platform_type == PlatformType.WINDOWS.value:
            try:
                from ..windows.windows_timing import WindowsTiming
                implementations["windows"] = WindowsTiming
            except ImportError:
                logger.warning("Windows timing implementation not available")

        # Mock timing for development
        from ..macos.macos_timing import MacOSTiming
        implementations["mock"] = MacOSTiming

        return implementations

    def _initialize_display_implementations(self) -> Dict[str, Type]:
        """Initialize display implementation classes based on platform"""
        implementations = {}

        if self._platform_info.platform_type == PlatformType.WINDOWS.value:
            try:
                from ..windows.display_control import DisplayControl
                implementations["directx"] = DisplayControl
            except ImportError:
                logger.warning("DirectX display implementation not available")

        # Mock display for development
        from ..macos.mock_display import MockDisplay
        implementations["mock"] = MockDisplay

        return implementations