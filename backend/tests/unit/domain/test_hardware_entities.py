"""
Tests for Domain Hardware Entities

Tests for HardwareComponent, Camera, Display, and HardwareSystem entities
to ensure proper hardware abstraction and status management.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import json
from unittest.mock import Mock, patch, MagicMock

from src.domain.entities.hardware import (
    HardwareComponent,
    Camera,
    Display,
    HardwareSystem,
    HardwareStatus,
    HardwareType,
    CameraModel,
    DisplayType,
    HardwareCapabilities,
    HardwareConfiguration,
    HardwareMetrics
)


class TestHardwareCapabilities:
    """Test HardwareCapabilities value object"""

    def test_hardware_capabilities_creation(self):
        """Test creating hardware capabilities"""
        capabilities = HardwareCapabilities(
            max_resolution=(2048, 2048),
            bit_depth=16,
            max_frame_rate=60.0,
            wavelength_range=(400.0, 700.0)
        )

        assert capabilities.max_resolution == (2048, 2048)
        assert capabilities.bit_depth == 16
        assert capabilities.max_frame_rate == 60.0
        assert capabilities.wavelength_range == (400.0, 700.0)

    def test_resolution_support_check(self):
        """Test resolution support checking"""
        capabilities = HardwareCapabilities(
            max_resolution=(1024, 1024),
            bit_depth=16,
            max_frame_rate=30.0
        )

        # Should support smaller resolutions
        assert capabilities.supports_resolution(512, 512) == True
        assert capabilities.supports_resolution(1024, 1024) == True

        # Should not support larger resolutions
        assert capabilities.supports_resolution(2048, 2048) == False
        assert capabilities.supports_resolution(1024, 2048) == False

    def test_frame_rate_support_check(self):
        """Test frame rate support checking"""
        capabilities = HardwareCapabilities(
            max_resolution=(1024, 1024),
            max_frame_rate=60.0
        )

        # Should support lower frame rates
        assert capabilities.supports_frame_rate(30.0) == True
        assert capabilities.supports_frame_rate(60.0) == True

        # Should not support higher frame rates
        assert capabilities.supports_frame_rate(120.0) == False


class TestHardwareConfiguration:
    """Test HardwareConfiguration value object"""

    def test_hardware_configuration_creation(self):
        """Test creating hardware configuration"""
        config = HardwareConfiguration(
            exposure_time_ms=33.0,
            gain=1.5,
            binning=(2, 2),
            roi=(100, 100, 512, 512),
            temperature_setpoint=-10.0
        )

        assert config.exposure_time_ms == 33.0
        assert config.gain == 1.5
        assert config.binning == (2, 2)
        assert config.roi == (100, 100, 512, 512)
        assert config.temperature_setpoint == -10.0

    def test_configuration_serialization(self):
        """Test configuration serialization"""
        config = HardwareConfiguration(
            exposure_time_ms=33.0,
            gain=1.5,
            binning=(2, 2),
            custom_settings={"test_param": "test_value"}
        )

        config_dict = config.to_dict()

        assert config_dict["exposure_time_ms"] == 33.0
        assert config_dict["gain"] == 1.5
        assert config_dict["binning"] == (2, 2)
        assert config_dict["custom_settings"]["test_param"] == "test_value"

        # Test round-trip
        restored_config = HardwareConfiguration.from_dict(config_dict)
        assert restored_config.exposure_time_ms == config.exposure_time_ms
        assert restored_config.gain == config.gain
        assert restored_config.binning == config.binning


class TestHardwareMetrics:
    """Test HardwareMetrics value object"""

    def test_hardware_metrics_creation(self):
        """Test creating hardware metrics"""
        metrics = HardwareMetrics(
            temperature=25.0,
            cpu_usage=50.0,
            memory_usage=70.0,
            error_count=2,
            uptime_seconds=3600.0
        )

        assert metrics.temperature == 25.0
        assert metrics.cpu_usage == 50.0
        assert metrics.memory_usage == 70.0
        assert metrics.error_count == 2
        assert metrics.uptime_seconds == 3600.0

    def test_health_assessment(self):
        """Test health assessment logic"""
        # Healthy metrics
        healthy_metrics = HardwareMetrics(
            temperature=25.0,
            cpu_usage=50.0,
            memory_usage=70.0,
            error_count=2
        )
        assert healthy_metrics.is_healthy() == True

        # Unhealthy temperature
        hot_metrics = HardwareMetrics(
            temperature=85.0,
            cpu_usage=50.0,
            memory_usage=70.0,
            error_count=2
        )
        assert hot_metrics.is_healthy() == False

        # Unhealthy CPU usage
        high_cpu_metrics = HardwareMetrics(
            temperature=25.0,
            cpu_usage=98.0,
            memory_usage=70.0,
            error_count=2
        )
        assert high_cpu_metrics.is_healthy() == False

        # Too many errors
        error_metrics = HardwareMetrics(
            temperature=25.0,
            cpu_usage=50.0,
            memory_usage=70.0,
            error_count=15
        )
        assert error_metrics.is_healthy() == False


class TestHardwareComponent:
    """Test HardwareComponent base class"""

    def test_hardware_component_creation(self):
        """Test creating a hardware component"""
        component = HardwareComponent(
            hardware_id="test_component_001",
            name="Test Component",
            hardware_type=HardwareType.COMPUTE,
            model="Test Model v1.0",
            serial_number="SN123456"
        )

        assert component.hardware_id == "test_component_001"
        assert component.name == "Test Component"
        assert component.hardware_type == HardwareType.COMPUTE
        assert component.model == "Test Model v1.0"
        assert component.serial_number == "SN123456"
        assert component.status == HardwareStatus.UNKNOWN

    def test_status_change_tracking(self):
        """Test hardware status change tracking"""
        component = HardwareComponent(
            hardware_id="test_component_002",
            name="Test Component",
            hardware_type=HardwareType.COMPUTE
        )

        # Initial status
        assert component.status == HardwareStatus.UNKNOWN
        assert len(component._status_history) == 0

        # Change status
        component.status = HardwareStatus.AVAILABLE

        assert component.status == HardwareStatus.AVAILABLE
        assert len(component._status_history) == 1

        # Change again
        component.status = HardwareStatus.BUSY

        assert component.status == HardwareStatus.BUSY
        assert len(component._status_history) == 2

        # Check history contains previous statuses
        history = component.get_status_history(24)
        assert len(history) >= 1

    def test_error_message_tracking(self):
        """Test error message tracking"""
        component = HardwareComponent(
            hardware_id="test_component_003",
            name="Test Component",
            hardware_type=HardwareType.COMPUTE
        )

        # Add error messages
        component.add_error_message("First error occurred")
        component.add_error_message("Second error occurred")

        assert component.metrics.error_count == 2

        # Get recent errors
        recent_errors = component.get_recent_errors(24)
        assert len(recent_errors) == 2
        assert "First error occurred" in recent_errors[0]
        assert "Second error occurred" in recent_errors[1]

    def test_availability_checks(self):
        """Test hardware availability checking"""
        component = HardwareComponent(
            hardware_id="test_component_004",
            name="Test Component",
            hardware_type=HardwareType.COMPUTE
        )

        # Test different statuses
        component.status = HardwareStatus.AVAILABLE
        assert component.is_available() == True
        assert component.is_operational() == True

        component.status = HardwareStatus.BUSY
        assert component.is_available() == False
        assert component.is_operational() == True

        component.status = HardwareStatus.ERROR
        assert component.is_available() == False
        assert component.is_operational() == False

    def test_component_serialization(self):
        """Test hardware component serialization"""
        component = HardwareComponent(
            hardware_id="test_component_005",
            name="Test Component",
            hardware_type=HardwareType.CAMERA,
            model="Test Model",
            serial_number="SN789"
        )

        # Set some properties
        component.status = HardwareStatus.AVAILABLE
        component.capabilities = HardwareCapabilities(
            max_resolution=(1024, 1024),
            max_frame_rate=30.0
        )
        component.add_error_message("Test error")

        # Serialize
        component_dict = component.to_dict()

        assert component_dict["hardware_id"] == "test_component_005"
        assert component_dict["name"] == "Test Component"
        assert component_dict["hardware_type"] == "camera"
        assert component_dict["status"] == "available"
        assert len(component_dict["recent_errors"]) == 1

        # Test round-trip
        restored_component = HardwareComponent.from_dict(component_dict)
        assert restored_component.hardware_id == component.hardware_id
        assert restored_component.name == component.name
        assert restored_component.hardware_type == component.hardware_type


class TestCamera:
    """Test Camera hardware component"""

    def test_camera_creation(self):
        """Test creating a camera component"""
        camera = Camera(
            camera_id="camera_001",
            name="PCO Panda 4.2",
            model=CameraModel.PCO_PANDA,
            serial_number="PCO123456"
        )

        assert camera.hardware_id == "camera_001"
        assert camera.name == "PCO Panda 4.2"
        assert camera.hardware_type == HardwareType.CAMERA
        assert camera.camera_model == CameraModel.PCO_PANDA
        assert camera.serial_number == "PCO123456"
        assert camera.is_cooling_enabled == False

    def test_camera_cooling_control(self):
        """Test camera cooling control"""
        camera = Camera(
            camera_id="camera_002",
            name="Test Camera",
            model=CameraModel.GENERIC
        )

        # Initially no cooling
        assert camera.is_cooling_enabled == False

        # Enable cooling
        camera.enable_cooling(-15.0)
        assert camera.is_cooling_enabled == True
        assert camera._target_temperature == -15.0
        assert camera.configuration.temperature_setpoint == -15.0

        # Disable cooling
        camera.disable_cooling()
        assert camera.is_cooling_enabled == False
        assert camera.configuration.temperature_setpoint is None

    def test_camera_temperature_stability(self):
        """Test camera temperature stability checking"""
        camera = Camera(
            camera_id="camera_003",
            name="Test Camera",
            model=CameraModel.GENERIC
        )

        # Without cooling, should be stable
        assert camera.is_temperature_stable() == True

        # Enable cooling
        camera.enable_cooling(-10.0)

        # Set stable temperature
        camera.metrics.temperature = -10.5
        assert camera.is_temperature_stable(tolerance=2.0) == True

        # Set unstable temperature
        camera.metrics.temperature = -5.0
        assert camera.is_temperature_stable(tolerance=2.0) == False

    def test_camera_configuration(self):
        """Test camera configuration methods"""
        camera = Camera(
            camera_id="camera_004",
            name="Test Camera",
            model=CameraModel.GENERIC
        )

        # Set exposure
        camera.set_exposure(25.0)
        assert camera.configuration.exposure_time_ms == 25.0

        # Set binning
        camera.set_binning(2, 2)
        assert camera.configuration.binning == (2, 2)


class TestDisplay:
    """Test Display hardware component"""

    def test_display_creation(self):
        """Test creating a display component"""
        display = Display(
            display_id="display_001",
            name="LCD Monitor",
            display_type=DisplayType.LCD_MONITOR,
            serial_number="DISP123456"
        )

        assert display.hardware_id == "display_001"
        assert display.name == "LCD Monitor"
        assert display.hardware_type == HardwareType.DISPLAY
        assert display.display_type == DisplayType.LCD_MONITOR
        assert display.serial_number == "DISP123456"

    def test_display_settings(self):
        """Test display settings control"""
        display = Display(
            display_id="display_002",
            name="Test Display",
            display_type=DisplayType.LCD_MONITOR
        )

        # Test brightness control
        display.brightness = 75.0
        assert display.brightness == 75.0
        assert display.configuration.custom_settings["brightness"] == 75.0

        # Test brightness bounds
        display.brightness = 150.0  # Should be clamped to 100
        assert display.brightness == 100.0

        display.brightness = -10.0  # Should be clamped to 0
        assert display.brightness == 0.0

        # Test contrast control
        display.contrast = 60.0
        assert display.contrast == 60.0
        assert display.configuration.custom_settings["contrast"] == 60.0

        # Test gamma control
        display.gamma = 2.2
        assert display.gamma == 2.2
        assert display.configuration.custom_settings["gamma"] == 2.2

        # Test gamma bounds
        display.gamma = 10.0  # Should be clamped to 5.0
        assert display.gamma == 5.0

        display.gamma = 0.05  # Should be clamped to 0.1
        assert display.gamma == 0.1


class TestHardwareSystem:
    """Test HardwareSystem management"""

    def test_hardware_system_creation(self):
        """Test creating a hardware system"""
        system = HardwareSystem("test_system")

        assert system.system_id == "test_system"
        assert len(system._components) == 0

    def test_component_management(self):
        """Test adding and removing components"""
        system = HardwareSystem("test_system")

        # Add camera
        camera = Camera(
            camera_id="cam_001",
            name="Test Camera",
            model=CameraModel.GENERIC
        )
        system.add_component(camera)

        assert len(system._components) == 1
        assert system.get_component("cam_001") == camera

        # Add display
        display = Display(
            display_id="disp_001",
            name="Test Display",
            display_type=DisplayType.LCD_MONITOR
        )
        system.add_component(display)

        assert len(system._components) == 2

        # Remove component
        success = system.remove_component("cam_001")
        assert success == True
        assert len(system._components) == 1

        # Try to remove non-existent component
        success = system.remove_component("nonexistent")
        assert success == False

    def test_component_queries(self):
        """Test component query methods"""
        system = HardwareSystem("test_system")

        # Add components
        camera1 = Camera("cam_001", "Camera 1", CameraModel.GENERIC)
        camera2 = Camera("cam_002", "Camera 2", CameraModel.PCO_PANDA)
        display1 = Display("disp_001", "Display 1", DisplayType.LCD_MONITOR)

        camera1.status = HardwareStatus.AVAILABLE
        camera2.status = HardwareStatus.BUSY
        display1.status = HardwareStatus.AVAILABLE

        system.add_component(camera1)
        system.add_component(camera2)
        system.add_component(display1)

        # Test type queries
        cameras = system.get_cameras()
        assert len(cameras) == 2
        assert all(isinstance(cam, Camera) for cam in cameras)

        displays = system.get_displays()
        assert len(displays) == 1
        assert isinstance(displays[0], Display)

        components_by_type = system.get_components_by_type(HardwareType.CAMERA)
        assert len(components_by_type) == 2

        # Test status queries
        available_components = system.get_available_components()
        assert len(available_components) == 2  # camera1 and display1

        operational_components = system.get_operational_components()
        assert len(operational_components) == 3  # All components (busy is operational)

    def test_system_health_calculation(self):
        """Test system health score calculation"""
        system = HardwareSystem("test_system")

        # Empty system
        assert system.calculate_system_health() == 0.0

        # Add healthy components
        camera = Camera("cam_001", "Camera 1", CameraModel.GENERIC)
        display = Display("disp_001", "Display 1", DisplayType.LCD_MONITOR)

        camera.status = HardwareStatus.AVAILABLE
        camera.metrics = HardwareMetrics(temperature=25.0, cpu_usage=50.0, error_count=0)

        display.status = HardwareStatus.AVAILABLE
        display.metrics = HardwareMetrics(temperature=30.0, cpu_usage=40.0, error_count=0)

        system.add_component(camera)
        system.add_component(display)

        health_score = system.calculate_system_health()
        assert 0.8 <= health_score <= 1.0  # Should be high for healthy components

        # Add unhealthy component
        broken_camera = Camera("cam_broken", "Broken Camera", CameraModel.GENERIC)
        broken_camera.status = HardwareStatus.ERROR
        broken_camera.metrics = HardwareMetrics(temperature=90.0, error_count=20)

        system.add_component(broken_camera)

        health_score = system.calculate_system_health()
        assert health_score < 0.8  # Should be lower with broken component

    def test_acquisition_readiness(self):
        """Test system readiness for acquisition"""
        system = HardwareSystem("test_system")

        # No components - not ready
        ready, issues = system.is_system_ready_for_acquisition()
        assert ready == False
        assert len(issues) > 0

        # Add available camera and display
        camera = Camera("cam_001", "Camera 1", CameraModel.GENERIC)
        display = Display("disp_001", "Display 1", DisplayType.LCD_MONITOR)

        camera.status = HardwareStatus.AVAILABLE
        display.status = HardwareStatus.AVAILABLE

        system.add_component(camera)
        system.add_component(display)

        ready, issues = system.is_system_ready_for_acquisition()
        assert ready == True
        assert len(issues) == 0

        # Make camera unavailable
        camera.status = HardwareStatus.ERROR

        ready, issues = system.is_system_ready_for_acquisition()
        assert ready == False
        assert any("camera" in issue.lower() for issue in issues)

    def test_system_status_summary(self):
        """Test system status summary"""
        system = HardwareSystem("test_system")

        # Add components
        camera = Camera("cam_001", "Camera 1", CameraModel.GENERIC)
        display = Display("disp_001", "Display 1", DisplayType.LCD_MONITOR)

        camera.status = HardwareStatus.AVAILABLE
        display.status = HardwareStatus.BUSY

        system.add_component(camera)
        system.add_component(display)

        summary = system.get_system_status_summary()

        assert summary["system_id"] == "test_system"
        assert summary["component_count"] == 2
        assert summary["operational_components"] == 2
        assert summary["available_components"] == 1
        assert "components" in summary
        assert "cam_001" in summary["components"]
        assert "disp_001" in summary["components"]

    def test_system_serialization(self):
        """Test hardware system serialization"""
        system = HardwareSystem("test_system")

        # Add components
        camera = Camera("cam_001", "Camera 1", CameraModel.PCO_PANDA)
        camera.status = HardwareStatus.AVAILABLE

        system.add_component(camera)

        # Test saving to file
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "system.json"
            system.save_to_file(file_path)

            assert file_path.exists()

            # Test loading from file
            loaded_system = HardwareSystem.load_from_file(file_path)

            assert loaded_system.system_id == system.system_id
            assert len(loaded_system._components) == 1
            assert "cam_001" in loaded_system._components

            loaded_camera = loaded_system.get_component("cam_001")
            assert isinstance(loaded_camera, Camera)
            assert loaded_camera.status == HardwareStatus.AVAILABLE


if __name__ == "__main__":
    pytest.main([__file__])