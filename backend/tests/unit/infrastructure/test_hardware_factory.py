"""
Unit Tests for Hardware Factory

Tests platform detection, hardware capability detection, and
cross-platform hardware abstraction functionality.
"""

import pytest
from unittest.mock import Mock, patch
from typing import Dict, Set

from src.infrastructure.hardware.factory import (
    HardwareFactory,
    PlatformType,
    HardwareCapability,
    PlatformInfo
)
from src.domain.entities.workflow_state import HardwareRequirement


class TestPlatformType:
    """Test PlatformType enum"""

    def test_platform_type_values(self):
        """Test platform type enum values"""
        assert PlatformType.WINDOWS.value == "windows"
        assert PlatformType.MACOS.value == "macos"
        assert PlatformType.LINUX.value == "linux"
        assert PlatformType.UNKNOWN.value == "unknown"


class TestHardwareCapability:
    """Test HardwareCapability Pydantic model"""

    def test_hardware_capability_creation(self):
        """Test creating hardware capability with Pydantic V2"""
        capability = HardwareCapability(
            hardware_type=HardwareRequirement.GPU,
            available=True,
            mock=False,
            details={"type": "cuda", "model": "RTX 4070"}
        )

        assert capability.hardware_type == HardwareRequirement.GPU.value
        assert capability.available is True
        assert capability.mock is False
        assert capability.details["type"] == "cuda"

    def test_hardware_capability_defaults(self):
        """Test hardware capability with default values"""
        capability = HardwareCapability(
            hardware_type=HardwareRequirement.DISPLAY,
            available=True,
            mock=True
        )

        assert capability.details == {}

    def test_hardware_capability_serialization(self):
        """Test Pydantic V2 serialization"""
        capability = HardwareCapability(
            hardware_type=HardwareRequirement.CAMERA,
            available=True,
            mock=True,
            details={"model": "PCO Panda 4.2"}
        )

        data = capability.model_dump()
        assert data["hardware_type"] == "camera"
        assert data["available"] is True
        assert data["mock"] is True
        assert data["details"]["model"] == "PCO Panda 4.2"


class TestPlatformInfo:
    """Test PlatformInfo Pydantic model"""

    def test_platform_info_creation(self):
        """Test creating platform info with Pydantic V2"""
        info = PlatformInfo(
            platform_type=PlatformType.MACOS,
            system="Darwin",
            machine="arm64",
            version="23.0.0"
        )

        assert info.platform_type == PlatformType.MACOS.value
        assert info.system == "Darwin"
        assert info.machine == "arm64"
        assert info.version == "23.0.0"
        assert info.development_mode is False

    def test_platform_info_with_development_mode(self):
        """Test platform info with development mode enabled"""
        info = PlatformInfo(
            platform_type=PlatformType.MACOS,
            system="Darwin",
            machine="arm64",
            version="23.0.0",
            development_mode=True
        )

        assert info.development_mode is True

    def test_platform_info_serialization(self):
        """Test Pydantic V2 serialization"""
        info = PlatformInfo(
            platform_type=PlatformType.WINDOWS,
            system="Windows",
            machine="AMD64",
            version="10.0.19041"
        )

        data = info.model_dump()
        assert data["platform_type"] == "windows"
        assert data["system"] == "Windows"


class TestHardwareFactory:
    """Test HardwareFactory functionality"""

    @patch('platform.system')
    @patch('platform.machine')
    @patch('platform.version')
    def test_detect_platform_macos(self, mock_version, mock_machine, mock_system):
        """Test platform detection for macOS"""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"
        mock_version.return_value = "23.0.0"

        factory = HardwareFactory()
        platform_info = factory.platform_info

        assert platform_info.platform_type == PlatformType.MACOS.value
        assert platform_info.system == "Darwin"
        assert platform_info.machine == "arm64"
        assert factory.development_mode is True  # macOS defaults to dev mode

    @patch('platform.system')
    @patch('platform.machine')
    @patch('platform.version')
    def test_detect_platform_windows(self, mock_version, mock_machine, mock_system):
        """Test platform detection for Windows"""
        mock_system.return_value = "Windows"
        mock_machine.return_value = "AMD64"
        mock_version.return_value = "10.0.19041"

        factory = HardwareFactory()
        platform_info = factory.platform_info

        assert platform_info.platform_type == PlatformType.WINDOWS.value
        assert platform_info.system == "Windows"
        assert platform_info.machine == "AMD64"
        assert factory.development_mode is False  # Windows defaults to production

    @patch('platform.system')
    def test_detect_platform_unknown(self, mock_system):
        """Test platform detection for unknown platform"""
        mock_system.return_value = "FreeBSD"

        factory = HardwareFactory()
        platform_info = factory.platform_info

        assert platform_info.platform_type == PlatformType.UNKNOWN.value

    def test_force_development_mode(self):
        """Test forcing development mode regardless of platform"""
        with patch('platform.system', return_value="Windows"):
            factory = HardwareFactory(force_development_mode=True)
            assert factory.development_mode is True

    @patch('platform.system', return_value="Darwin")
    def test_development_mode_hardware_capabilities(self, mock_system):
        """Test hardware capabilities in development mode"""
        factory = HardwareFactory()
        capabilities = factory.detect_hardware_capabilities()

        # Should have all mock hardware in development mode
        assert HardwareRequirement.DISPLAY in capabilities
        assert HardwareRequirement.GPU in capabilities
        assert HardwareRequirement.CAMERA in capabilities
        assert HardwareRequirement.STORAGE in capabilities
        assert HardwareRequirement.DEV_MODE_BYPASS in capabilities

        # All should be mock except DEV_MODE_BYPASS
        assert capabilities[HardwareRequirement.DISPLAY].mock is True
        assert capabilities[HardwareRequirement.GPU].mock is True
        assert capabilities[HardwareRequirement.CAMERA].mock is True
        assert capabilities[HardwareRequirement.STORAGE].mock is True
        assert capabilities[HardwareRequirement.DEV_MODE_BYPASS].mock is False

    @patch('platform.system', return_value="Windows")
    def test_production_mode_hardware_capabilities(self, mock_system):
        """Test hardware capabilities in production mode"""
        factory = HardwareFactory()
        capabilities = factory.detect_hardware_capabilities()

        # Should detect production hardware
        assert HardwareRequirement.DISPLAY in capabilities
        assert HardwareRequirement.GPU in capabilities
        assert HardwareRequirement.CAMERA in capabilities
        assert HardwareRequirement.STORAGE in capabilities

        # Should not be mock hardware
        assert capabilities[HardwareRequirement.DISPLAY].mock is False
        assert capabilities[HardwareRequirement.GPU].mock is False

    def test_get_available_hardware_requirements(self):
        """Test getting available hardware requirements"""
        with patch('platform.system', return_value="Darwin"):
            factory = HardwareFactory()
            available = factory.get_available_hardware_requirements()

            assert isinstance(available, set)
            assert HardwareRequirement.DEV_MODE_BYPASS in available
            assert len(available) > 0

    @patch('platform.system', return_value="Darwin")
    def test_create_camera_interface_development(self, mock_system):
        """Test creating camera interface in development mode"""
        factory = HardwareFactory()
        camera = factory.create_camera_interface()

        # Should return mock camera interface
        assert camera is not None

    @patch('platform.system', return_value="Windows")
    def test_create_camera_interface_production(self, mock_system):
        """Test creating camera interface in production mode (falls back to development)"""
        # Force development mode since production hardware isn't available
        factory = HardwareFactory(force_development_mode=True)

        camera = factory.create_camera_interface()
        assert camera is not None
        # Should use mock implementation when production hardware isn't available

    @patch('platform.system', return_value="Darwin")
    def test_create_gpu_interface_development_macos(self, mock_system):
        """Test creating GPU interface in development mode on macOS"""
        factory = HardwareFactory()
        gpu = factory.create_gpu_interface()

        # Should return Metal or mock GPU interface
        assert gpu is not None

    @patch('platform.system', return_value="Windows")
    def test_create_gpu_interface_production(self, mock_system):
        """Test creating GPU interface in production mode (falls back to development)"""
        # Force development mode since production hardware isn't available
        factory = HardwareFactory(force_development_mode=True)

        gpu = factory.create_gpu_interface()
        assert gpu is not None

    @patch('platform.system', return_value="Darwin")
    def test_create_timing_interface_development(self, mock_system):
        """Test creating timing interface in development mode"""
        factory = HardwareFactory()
        timing = factory.create_timing_interface()

        assert timing is not None

    @patch('platform.system', return_value="Windows")
    def test_create_timing_interface_production(self, mock_system):
        """Test creating timing interface in production mode (falls back to development)"""
        # Force development mode since production hardware isn't available
        factory = HardwareFactory(force_development_mode=True)

        timing = factory.create_timing_interface()
        assert timing is not None

    @patch('platform.system', return_value="Darwin")
    def test_create_display_interface_development(self, mock_system):
        """Test creating display interface in development mode"""
        factory = HardwareFactory()
        display = factory.create_display_interface()

        assert display is not None

    @patch('platform.system', return_value="Windows")
    def test_create_display_interface_production(self, mock_system):
        """Test creating display interface in production mode (falls back to development)"""
        # Force development mode since production hardware isn't available
        factory = HardwareFactory(force_development_mode=True)

        display = factory.create_display_interface()
        assert display is not None

    def test_platform_info_property(self):
        """Test platform_info property access"""
        with patch('platform.system', return_value="Darwin"):
            factory = HardwareFactory()
            info = factory.platform_info

            assert isinstance(info, PlatformInfo)
            assert info.platform_type == PlatformType.MACOS.value

    def test_development_mode_property(self):
        """Test development_mode property access"""
        with patch('platform.system', return_value="Darwin"):
            factory = HardwareFactory()
            assert factory.development_mode is True

        with patch('platform.system', return_value="Windows"):
            factory = HardwareFactory()
            assert factory.development_mode is False

    @patch('platform.system', return_value="Darwin")
    def test_hardware_capability_pydantic_validation(self, mock_system):
        """Test that hardware capabilities use proper Pydantic V2 validation"""
        factory = HardwareFactory()
        capabilities = factory.detect_hardware_capabilities()

        # Test that each capability is a proper Pydantic model
        for req, capability in capabilities.items():
            assert isinstance(capability, HardwareCapability)

            # Test serialization works
            data = capability.model_dump()
            assert "hardware_type" in data
            assert "available" in data
            assert "mock" in data
            assert "details" in data

            # Test that hardware_type serializes as enum value
            assert data["hardware_type"] == req.value