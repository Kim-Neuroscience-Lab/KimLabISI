"""
Hardware Factory - Platform Detection and Hardware Abstraction

This module implements the hardware factory for cross-platform development
as specified in ADR-0008 (Cross-Platform Development Strategy) and
ADR-0010 (Hardware Abstraction Layer).

Factory Responsibilities:
- Platform detection (macOS vs Windows)
- Hardware capability detection
- Abstract interface instantiation
- Development stub vs production hardware selection
- Development mode configuration
"""

import platform
import logging
from typing import Protocol, Dict, Type, Set
from enum import Enum
from pydantic import BaseModel, Field

from .abstract.camera_interface import CameraInterface
from .abstract.gpu_interface import GPUInterface
from .abstract.timing_interface import TimingInterface
from .abstract.display_interface import DisplayInterface
from ...domain.value_objects.workflow_state import HardwareRequirement


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
    simulated: bool = Field(default=False, description="Whether this is simulated hardware for development")
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
    following the dependency inversion principle. Provides simulated hardware
    for development and production hardware for Windows deployment.

    Design Principles:
    - Platform detection determines implementation strategy
    - Abstract interfaces ensure consistent API across platforms
    - Development stubs enable development without production equipment
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

        # Development mode provides simulated hardware
        if self._development_mode:
            capabilities.update({
                HardwareRequirement.DISPLAY: HardwareCapability(
                    hardware_type=HardwareRequirement.DISPLAY,
                    available=True,
                    simulated=True,
                    details={"type": "simulated_display", "platform": self._platform_info.platform_type}
                ),
                HardwareRequirement.GPU: HardwareCapability(
                    hardware_type=HardwareRequirement.GPU,
                    available=True,
                    simulated=True,
                    details={"type": "metal_gpu" if self._platform_info.platform_type == PlatformType.MACOS.value else "simulated_gpu"}
                ),
                HardwareRequirement.CAMERA: HardwareCapability(
                    hardware_type=HardwareRequirement.CAMERA,
                    available=True,
                    simulated=True,
                    details={"type": "simulated_camera", "model": "PCO Panda 4.2 Simulation"}
                ),
                HardwareRequirement.STORAGE: HardwareCapability(
                    hardware_type=HardwareRequirement.STORAGE,
                    available=True,
                    simulated=True,
                    details={"type": "local_storage", "location": "development"}
                ),
                HardwareRequirement.DEV_MODE_BYPASS: HardwareCapability(
                    hardware_type=HardwareRequirement.DEV_MODE_BYPASS,
                    available=True,
                    simulated=False,
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
        if self._development_mode and "development" in self._camera_implementations:
            return self._camera_implementations["development"]()
        elif "production" in self._camera_implementations:
            return self._camera_implementations["production"]()
        else:
            raise RuntimeError("No camera implementation available for this platform")

    def create_gpu_interface(self) -> GPUInterface:
        """
        Create GPU interface based on platform and availability

        Returns:
            GPU interface implementation
        """
        if self._platform_info.platform_type == PlatformType.MACOS.value and "metal" in self._gpu_implementations:
            return self._gpu_implementations["metal"]()
        else:
            return self._gpu_implementations["directx"]()

    def create_timing_interface(self) -> TimingInterface:
        """
        Create timing interface based on platform

        Returns:
            Timing interface implementation
        """
        if self._platform_info.platform_type == PlatformType.MACOS.value and "macos" in self._timing_implementations:
            return self._timing_implementations["macos"]()
        else:
            return self._timing_implementations["windows"]()

    def create_display_interface(self) -> DisplayInterface:
        """
        Create display interface based on platform

        Returns:
            Display interface implementation
        """
        if self._platform_info.platform_type == PlatformType.MACOS.value and "displaycontrol" in self._display_implementations:
            return self._display_implementations["displaycontrol"]()
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
                    simulated=False,
                    details={"type": "directx12", "gpu": "RTX 4070"}
                ),
                HardwareRequirement.GPU: HardwareCapability(
                    hardware_type=HardwareRequirement.GPU,
                    available=True,  # Assume available on Windows
                    simulated=False,
                    details={"type": "cuda", "model": "RTX 4070"}
                ),
                HardwareRequirement.CAMERA: HardwareCapability(
                    hardware_type=HardwareRequirement.CAMERA,
                    available=False,  # Requires actual detection
                    simulated=False,
                    details={"type": "pco_sdk", "model": "PCO Panda 4.2"}
                ),
                HardwareRequirement.STORAGE: HardwareCapability(
                    hardware_type=HardwareRequirement.STORAGE,
                    available=True,  # Assume available
                    simulated=False,
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

        # Development mode uses stub implementation
        if self._development_mode:
            try:
                from ..development.stub_camera import StubCamera
                implementations["development"] = StubCamera
            except ImportError:
                logger.warning("Development camera stub not available")

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

        if self._platform_info.platform_type == PlatformType.MACOS.value:
            try:
                from ..macos.macos_timing import MacOSTiming
                implementations["macos"] = MacOSTiming
            except ImportError:
                logger.warning("macOS timing implementation not available")

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

        if self._platform_info.platform_type == PlatformType.MACOS.value:
            try:
                from ..macos.display_control import DisplayControl
                implementations["displaycontrol"] = DisplayControl
            except ImportError:
                logger.warning("macOS display implementation not available")

        return implementations