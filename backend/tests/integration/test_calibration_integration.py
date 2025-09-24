"""
Integration tests for calibration system

Tests the integration between calibration infrastructure components
and their usage in the broader system architecture.
"""

import pytest
import asyncio
import tempfile
import numpy as np
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime

from src.infrastructure.hardware.calibration.camera_calibrator import (
    CameraCalibrator,
    CalibrationPattern,
    CalibrationPatternType,
    CalibrationStatus
)
from src.infrastructure.hardware.calibration.display_calibrator import (
    DisplayCalibrator,
    DisplayCalibrationMode,
    ColorSpace
)
from src.domain.entities.hardware import Camera, Display, HardwareSystem


class TestCalibrationSystemIntegration:
    """Integration tests for calibration system"""

    @pytest.fixture
    def temp_calibration_path(self):
        """Create temporary directory for calibration data"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def mock_camera(self):
        """Mock camera entity"""
        camera = Mock(spec=Camera)
        camera.component_id = "test_camera_001"
        camera.status = "active"
        return camera

    @pytest.fixture
    def mock_display(self):
        """Mock display entity"""
        display = Mock(spec=Display)
        display.component_id = "test_display_001"
        display.status = "active"
        return display

    @pytest.fixture
    def camera_calibrator(self, temp_calibration_path):
        """Create camera calibrator"""
        return CameraCalibrator(
            calibration_data_path=temp_calibration_path / "camera",
            min_calibration_images=5,
            max_calibration_error=1.0
        )

    @pytest.fixture
    def display_calibrator(self, temp_calibration_path):
        """Create display calibrator"""
        return DisplayCalibrator(
            calibration_data_path=temp_calibration_path / "display",
            colorimeter_available=False,  # Use mock measurements
            photometer_available=False
        )

    @pytest.fixture
    def sample_calibration_images(self):
        """Generate sample calibration images"""
        images = []
        for i in range(10):
            # Create synthetic checkerboard-like images
            image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            # Add some structure to simulate checkerboard
            image[::50, :] = 255  # White stripes
            image[:, ::50] = 255  # White stripes
            images.append(image)
        return images

    @pytest.fixture
    def checkerboard_pattern(self):
        """Create checkerboard calibration pattern"""
        return CalibrationPattern(
            pattern_type=CalibrationPatternType.CHECKERBOARD,
            width=9,
            height=6,
            square_size=25.0  # 25mm squares
        )

    @pytest.mark.asyncio
    async def test_camera_calibration_end_to_end(self, camera_calibrator, mock_camera,
                                               sample_calibration_images, checkerboard_pattern):
        """Test complete camera calibration workflow"""

        # Perform calibration
        result = await camera_calibrator.calibrate_camera(
            camera=mock_camera,
            calibration_images=sample_calibration_images,
            pattern=checkerboard_pattern
        )

        # Verify calibration result
        assert result.status in [CalibrationStatus.CALIBRATED, CalibrationStatus.VALIDATION_FAILED]
        assert result.images_used == len(sample_calibration_images)
        assert result.pattern_detections >= 5  # At least min_calibration_images
        assert result.intrinsics is not None
        assert result.intrinsics.camera_matrix.shape == (3, 3)
        assert len(result.intrinsics.distortion_coefficients) == 5

        # Verify persistence
        loaded_result = await camera_calibrator.load_calibration(mock_camera.component_id)
        assert loaded_result is not None
        assert loaded_result.status == result.status
        assert np.array_equal(loaded_result.intrinsics.camera_matrix, result.intrinsics.camera_matrix)

    @pytest.mark.asyncio
    async def test_display_calibration_end_to_end(self, display_calibrator, mock_display):
        """Test complete display calibration workflow"""

        # Perform gamma calibration
        gamma_result = await display_calibrator.calibrate_gamma(
            display=mock_display,
            target_gamma=2.2
        )

        assert gamma_result.red_gamma > 0
        assert gamma_result.green_gamma > 0
        assert gamma_result.blue_gamma > 0
        assert len(gamma_result.luminance_curve) == 256

        # Perform color profile calibration
        color_result = await display_calibrator.calibrate_color_profile(
            display=mock_display,
            target_color_space=ColorSpace.SRGB
        )

        assert color_result.color_space == ColorSpace.SRGB
        assert color_result.white_point is not None
        assert color_result.primaries.shape == (3, 2)
        assert color_result.color_matrix.shape == (3, 3)

        # Perform spatial mapping calibration
        reference_points = np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.float32)
        measured_points = np.array([[2, 1], [98, 2], [99, 99], [1, 98]], dtype=np.float32)

        spatial_result = await display_calibrator.calibrate_spatial_mapping(
            display=mock_display,
            reference_points=reference_points,
            measured_points=measured_points
        )

        assert spatial_result.mapping_matrix.shape == (3, 3)
        assert spatial_result.display_corners.shape == (4, 2)
        assert spatial_result.pixel_pitch[0] > 0
        assert spatial_result.pixel_pitch[1] > 0

    @pytest.mark.asyncio
    async def test_full_display_calibration_integration(self, display_calibrator, mock_display):
        """Test full display calibration with multiple modes"""

        calibration_modes = [
            DisplayCalibrationMode.GAMMA_CORRECTION,
            DisplayCalibrationMode.COLOR_PROFILE,
            DisplayCalibrationMode.UNIFORMITY_CORRECTION
        ]

        # Provide spatial mapping data
        reference_points = np.array([[0, 0], [1920, 0], [1920, 1080], [0, 1080]], dtype=np.float32)
        measured_points = np.array([[10, 5], [1910, 8], [1915, 1075], [8, 1078]], dtype=np.float32)

        result = await display_calibrator.full_display_calibration(
            display=mock_display,
            calibration_modes=calibration_modes,
            target_gamma=2.2,
            target_color_space=ColorSpace.SRGB,
            reference_points=reference_points,
            measured_points=measured_points,
            grid_size=(5, 5)
        )

        # Verify all calibrations were performed
        assert result.display_id == mock_display.component_id
        assert result.gamma_correction is not None
        assert result.color_profile is not None
        assert result.uniformity_correction is not None

        # Verify persistence
        loaded_result = await display_calibrator.load_calibration(mock_display.component_id)
        assert loaded_result is not None
        assert loaded_result.display_id == result.display_id

    @pytest.mark.asyncio
    async def test_calibration_with_hardware_system(self, camera_calibrator, display_calibrator,
                                                   mock_camera, mock_display):
        """Test calibration integration with hardware system"""

        # Create hardware system with components
        hardware_system = Mock(spec=HardwareSystem)
        hardware_system.get_all_components.return_value = [mock_camera, mock_display]

        # Simulate calibration workflow with hardware system
        cameras = [comp for comp in hardware_system.get_all_components()
                  if isinstance(comp, Camera) or comp.component_id.startswith('camera')]
        displays = [comp for comp in hardware_system.get_all_components()
                   if isinstance(comp, Display) or comp.component_id.startswith('display')]

        calibration_results = {}

        # Calibrate all cameras
        for camera in cameras:
            if hasattr(camera, 'component_id') and 'camera' in camera.component_id:
                # Generate mock calibration images
                mock_images = [np.random.randint(0, 255, (480, 640), dtype=np.uint8) for _ in range(8)]

                pattern = CalibrationPattern(
                    pattern_type=CalibrationPatternType.CHECKERBOARD,
                    width=7, height=5, square_size=30.0
                )

                result = await camera_calibrator.calibrate_camera(camera, mock_images, pattern)
                calibration_results[camera.component_id] = result

        # Calibrate all displays
        for display in displays:
            if hasattr(display, 'component_id') and 'display' in display.component_id:
                result = await display_calibrator.calibrate_gamma(display, target_gamma=2.2)
                calibration_results[display.component_id] = result

        # Verify all components were calibrated
        assert len(calibration_results) == 2  # 1 camera + 1 display

    @pytest.mark.asyncio
    async def test_calibration_error_handling(self, camera_calibrator, mock_camera):
        """Test calibration error handling and recovery"""

        # Test with insufficient calibration images
        insufficient_images = [np.random.randint(0, 255, (480, 640), dtype=np.uint8) for _ in range(2)]
        pattern = CalibrationPattern(
            pattern_type=CalibrationPatternType.CHECKERBOARD,
            width=9, height=6, square_size=25.0
        )

        with pytest.raises(Exception):  # Should raise CameraCalibrationError
            await camera_calibrator.calibrate_camera(mock_camera, insufficient_images, pattern)

        # Test with corrupted calibration data
        calibration_file = camera_calibrator.calibration_data_path / f"{mock_camera.component_id}_calibration.json"
        calibration_file.parent.mkdir(parents=True, exist_ok=True)

        with open(calibration_file, 'w') as f:
            f.write("corrupted json data {")

        # Should handle corrupted data gracefully
        loaded_result = await camera_calibrator.load_calibration(mock_camera.component_id)
        assert loaded_result is None

    @pytest.mark.asyncio
    async def test_calibration_data_management(self, camera_calibrator, display_calibrator,
                                             mock_camera, mock_display):
        """Test calibration data management and cleanup"""

        # Create multiple calibrations
        for i in range(3):
            camera_id = f"test_camera_{i:03d}"
            mock_cam = Mock(spec=Camera)
            mock_cam.component_id = camera_id

            # Create minimal calibration
            images = [np.random.randint(0, 255, (480, 640), dtype=np.uint8) for _ in range(8)]
            pattern = CalibrationPattern(
                pattern_type=CalibrationPatternType.CHECKERBOARD,
                width=7, height=5, square_size=25.0
            )

            await camera_calibrator.calibrate_camera(mock_cam, images, pattern)

        # List calibrated cameras
        calibrated_cameras = camera_calibrator.list_calibrated_cameras()
        assert len(calibrated_cameras) >= 3

        # Delete specific calibration
        success = await camera_calibrator.delete_calibration("test_camera_001")
        assert success is True

        # Verify deletion
        deleted_result = await camera_calibrator.load_calibration("test_camera_001")
        assert deleted_result is None

        # Remaining calibrations should still exist
        remaining_cameras = camera_calibrator.list_calibrated_cameras()
        assert len(remaining_cameras) >= 2

    def test_calibration_pattern_creation(self, camera_calibrator):
        """Test calibration pattern creation and validation"""

        # Test checkerboard pattern
        checkerboard = camera_calibrator.create_calibration_pattern(
            CalibrationPatternType.CHECKERBOARD,
            width=9, height=6, square_size=25.0
        )

        assert checkerboard.pattern_type == CalibrationPatternType.CHECKERBOARD
        assert checkerboard.width == 9
        assert checkerboard.height == 6
        assert checkerboard.square_size == 25.0

        # Test circle grid pattern
        circle_grid = camera_calibrator.create_calibration_pattern(
            CalibrationPatternType.CIRCLE_GRID,
            width=7, height=4, square_size=30.0
        )

        assert circle_grid.pattern_type == CalibrationPatternType.CIRCLE_GRID

        # Test ChArUco pattern
        charuco = camera_calibrator.create_calibration_pattern(
            CalibrationPatternType.CHARUCO_BOARD,
            width=8, height=5, square_size=40.0, marker_size=30.0
        )

        assert charuco.pattern_type == CalibrationPatternType.CHARUCO_BOARD
        assert charuco.marker_size == 30.0

    def test_calibration_status_tracking(self, camera_calibrator, mock_camera):
        """Test calibration status tracking"""

        # Initial status should be NOT_CALIBRATED
        status = camera_calibrator.get_calibration_status(mock_camera.component_id)
        assert status == CalibrationStatus.NOT_CALIBRATED

        # After calibration, status should change
        # (Would need actual calibration for this test in real scenario)

    @pytest.mark.asyncio
    async def test_concurrent_calibrations(self, camera_calibrator, display_calibrator):
        """Test concurrent calibration operations"""

        # Create multiple mock devices
        cameras = []
        displays = []

        for i in range(3):
            camera = Mock(spec=Camera)
            camera.component_id = f"concurrent_camera_{i}"
            cameras.append(camera)

            display = Mock(spec=Display)
            display.component_id = f"concurrent_display_{i}"
            displays.append(display)

        # Run concurrent calibrations
        tasks = []

        # Camera calibrations
        for camera in cameras:
            images = [np.random.randint(0, 255, (480, 640), dtype=np.uint8) for _ in range(8)]
            pattern = CalibrationPattern(
                pattern_type=CalibrationPatternType.CHECKERBOARD,
                width=7, height=5, square_size=25.0
            )
            task = camera_calibrator.calibrate_camera(camera, images, pattern)
            tasks.append(task)

        # Display calibrations
        for display in displays:
            task = display_calibrator.calibrate_gamma(display, target_gamma=2.2)
            tasks.append(task)

        # Execute all calibrations concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All calibrations should succeed
        for result in results:
            assert not isinstance(result, Exception)

    @pytest.mark.asyncio
    async def test_calibration_performance_metrics(self, camera_calibrator, mock_camera,
                                                 sample_calibration_images, checkerboard_pattern):
        """Test calibration performance tracking"""

        start_time = asyncio.get_event_loop().time()

        # Perform calibration
        result = await camera_calibrator.calibrate_camera(
            camera=mock_camera,
            calibration_images=sample_calibration_images,
            pattern=checkerboard_pattern
        )

        end_time = asyncio.get_event_loop().time()
        calibration_duration = end_time - start_time

        # Calibration should complete in reasonable time
        assert calibration_duration < 10.0  # Should complete within 10 seconds

        # Verify calibration quality metrics
        assert result.validation_error is not None
        assert result.validation_error >= 0.0


@pytest.mark.integration
class TestCalibrationSystemPerformance:
    """Performance tests for calibration system"""

    @pytest.fixture
    def temp_calibration_path(self):
        """Create temporary directory for calibration data"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.mark.asyncio
    async def test_large_scale_calibration(self, temp_calibration_path):
        """Test calibration system with many devices"""

        camera_calibrator = CameraCalibrator(
            calibration_data_path=temp_calibration_path / "camera"
        )

        # Create many mock cameras
        cameras = []
        for i in range(20):
            camera = Mock(spec=Camera)
            camera.component_id = f"performance_camera_{i:03d}"
            cameras.append(camera)

        # Calibrate all cameras
        start_time = asyncio.get_event_loop().time()

        calibration_tasks = []
        for camera in cameras:
            images = [np.random.randint(0, 255, (480, 640), dtype=np.uint8) for _ in range(6)]
            pattern = CalibrationPattern(
                pattern_type=CalibrationPatternType.CHECKERBOARD,
                width=5, height=4, square_size=25.0
            )
            task = camera_calibrator.calibrate_camera(camera, images, pattern)
            calibration_tasks.append(task)

        # Execute calibrations in batches to avoid overwhelming system
        batch_size = 5
        for i in range(0, len(calibration_tasks), batch_size):
            batch = calibration_tasks[i:i+batch_size]
            await asyncio.gather(*batch, return_exceptions=True)

        end_time = asyncio.get_event_loop().time()
        total_duration = end_time - start_time

        # Should handle large scale calibrations efficiently
        calibrations_per_second = len(cameras) / total_duration
        assert calibrations_per_second > 1.0  # At least 1 calibration per second

        # Verify all calibrations were stored
        calibrated_cameras = camera_calibrator.list_calibrated_cameras()
        assert len(calibrated_cameras) >= len(cameras) * 0.8  # Allow some failures

    @pytest.mark.asyncio
    async def test_calibration_memory_usage(self, temp_calibration_path):
        """Test calibration system memory usage"""

        import gc

        camera_calibrator = CameraCalibrator(
            calibration_data_path=temp_calibration_path / "camera"
        )

        # Baseline memory
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Perform many calibrations
        for i in range(10):
            camera = Mock(spec=Camera)
            camera.component_id = f"memory_test_camera_{i}"

            images = [np.random.randint(0, 255, (480, 640), dtype=np.uint8) for _ in range(6)]
            pattern = CalibrationPattern(
                pattern_type=CalibrationPatternType.CHECKERBOARD,
                width=5, height=4, square_size=25.0
            )

            await camera_calibrator.calibrate_camera(camera, images, pattern)

            # Cleanup between calibrations
            del camera, images
            gc.collect()

        # Final memory check
        gc.collect()
        final_objects = len(gc.get_objects())
        object_growth = final_objects - initial_objects

        # Should not have excessive memory growth
        assert object_growth < 2000  # Reasonable threshold for object growth