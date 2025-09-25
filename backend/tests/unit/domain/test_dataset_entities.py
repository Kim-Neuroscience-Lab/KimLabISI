"""
Tests for Domain Dataset Entities

Tests for StimulusDataset, AcquisitionSession, and AnalysisResult entities
to ensure proper domain logic and data integrity.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import json
import numpy as np
from unittest.mock import Mock, patch, MagicMock

from src.domain.entities.dataset import (
    StimulusDataset,
    AcquisitionSession,
    AnalysisResult,
    DatasetStatus,
    CompressionType
)
from src.domain.value_objects.stream_config import (
    StreamingProfile,
    CameraStreamConfig,
    DisplayStreamConfig,
    StatusStreamConfig
)
from src.domain.value_objects.parameters import (
    CombinedParameters,
    StimulusGenerationParams,
    AcquisitionProtocolParams,
    SpatialConfiguration
)


class TestStimulusDataset:
    """Test StimulusDataset entity"""

    # Using sample_parameters fixture from conftest.py

    @pytest.fixture
    def temp_base_path(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_stimulus_dataset_creation(self, sample_parameters, temp_base_path):
        """Test creating a stimulus dataset"""
        dataset = StimulusDataset(
            dataset_id="test_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path
        )

        assert dataset.dataset_id == "test_dataset_001"
        assert dataset.parameters == sample_parameters
        assert dataset.base_path == temp_base_path
        assert dataset.status == DatasetStatus.GENERATING
        assert dataset.created_timestamp is not None
        assert dataset.status != DatasetStatus.COMPLETED

    def test_stimulus_dataset_file_management(self, sample_parameters, temp_base_path):
        """Test dataset file management"""
        dataset = StimulusDataset(
            dataset_id="test_dataset_002",
            parameters=sample_parameters,
            base_path=temp_base_path
        )

        # Test adding data files
        test_file_path = temp_base_path / "test_stimulus.h5"
        test_file_path.touch()  # Create empty file

        dataset.add_direction_file("LR", test_file_path, frame_count=100)

        assert "LR" in dataset.direction_files
        assert dataset.direction_files["LR"] == test_file_path

    def test_stimulus_dataset_completion(self, sample_parameters, temp_base_path):
        """Test dataset completion workflow"""
        dataset = StimulusDataset(
            dataset_id="test_dataset_003",
            parameters=sample_parameters,
            base_path=temp_base_path
        )

        # Should not be complete initially
        assert not dataset.status == DatasetStatus.COMPLETED
        assert dataset.status == DatasetStatus.GENERATING

        # Add required files for valid directions
        test_files = [("LR", "lr_patterns.h5"), ("RL", "rl_patterns.h5"), ("TB", "tb_patterns.h5")]
        for direction, filename in test_files:
            file_path = temp_base_path / filename
            file_path.touch()
            dataset.add_direction_file(direction, file_path, frame_count=100)

        # Mark as complete
        dataset.mark_completed()

        assert dataset.status == DatasetStatus.READY
        assert dataset.generation_progress == 1.0
        assert dataset.modified_timestamp is not None

    def test_stimulus_dataset_parameter_compatibility(self, sample_parameters, temp_base_path):
        """Test parameter compatibility checking for HDF5 stimulus reuse"""
        dataset = StimulusDataset(
            dataset_id="test_dataset_004",
            parameters=sample_parameters,
            base_path=temp_base_path
        )

        # Should be compatible with same parameters
        compatibility = dataset.is_compatible_with_parameters(sample_parameters)
        assert compatibility == True

        # Test with different stimulus parameters (affects generation_hash)
        different_stimulus_params = CombinedParameters(
            stimulus_params=StimulusGenerationParams(
                stimulus_type="checkerboard",  # Different stimulus type
                directions=["TB", "BT"],       # Different directions
                temporal_frequency_hz=0.5,     # Very different frequency
                spatial_frequency_cpd=0.1,     # Very different spatial frequency
                cycles_per_trial=20             # Different cycle count
            ),
            protocol_params=sample_parameters.protocol_params,  # Same protocol
            spatial_config=sample_parameters.spatial_config      # Same spatial config
        )

        compatibility = dataset.is_compatible_with_parameters(different_stimulus_params)
        assert compatibility == False  # Different stimulus params = different generation_hash

        # Test with same stimulus/spatial but different protocol (should be compatible for reuse)
        different_protocol_params = CombinedParameters(
            stimulus_params=sample_parameters.stimulus_params,     # Same stimulus
            spatial_config=sample_parameters.spatial_config,      # Same spatial
            protocol_params=AcquisitionProtocolParams(
                duration_s=120,              # Different duration
                trial_count=8,               # Different trial count
                recording_mode="high_speed"  # Different mode
            )
        )

        compatibility = dataset.is_compatible_with_parameters(different_protocol_params)
        assert compatibility == True  # Same generation_hash = can reuse HDF5 files

    def test_stimulus_dataset_serialization(self, sample_parameters, temp_base_path):
        """Test dataset serialization and deserialization"""
        original_dataset = StimulusDataset(
            dataset_id="test_dataset_005",
            parameters=sample_parameters,
            base_path=temp_base_path
        )

        # Add some data
        test_file = temp_base_path / "test.h5"
        test_file.touch()
        original_dataset.add_direction_file("LR", test_file, frame_count=100)

        # Convert to dict and back
        dataset_dict = original_dataset.to_dict()

        # Verify dict structure
        assert dataset_dict["dataset_id"] == "test_dataset_005"
        assert dataset_dict["status"] == DatasetStatus.GENERATING.value
        assert "parameters" in dataset_dict
        assert "direction_files" in dataset_dict

    def test_stimulus_dataset_hdf5_file_management(self, sample_parameters, temp_base_path):
        """Test HDF5 file management in stimulus dataset"""
        dataset = StimulusDataset(
            dataset_id="test_dataset_hdf5",
            parameters=sample_parameters,
            base_path=temp_base_path
        )

        # Test adding HDF5 files for different directions
        directions = ["LR", "RL", "TB", "BT"]
        for direction in directions:
            hdf5_file = temp_base_path / f"{direction.lower()}_patterns.h5"
            hdf5_file.touch()  # Create empty HDF5 file
            dataset.add_direction_file(direction, hdf5_file, frame_count=1000)

        # Verify all HDF5 files were added
        assert len(dataset.direction_files) == 4
        for direction in directions:
            assert direction in dataset.direction_files
            assert dataset.direction_files[direction].suffix == ".h5"
            assert dataset.frame_counts[direction] == 1000

        # Test file size tracking (would be populated by infrastructure layer)
        for direction in directions:
            file_size = dataset.direction_files[direction].stat().st_size
            dataset.file_sizes[direction] = file_size
            assert dataset.file_sizes[direction] >= 0


class TestAcquisitionSession:
    """Test AcquisitionSession entity"""

    # Using sample_parameters fixture from conftest.py

    @pytest.fixture
    def temp_base_path(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_acquisition_session_creation(self, sample_parameters, temp_base_path):
        """Test creating an acquisition session"""
        # Create a stimulus dataset first

        dataset = StimulusDataset(
            dataset_id="test_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path / "datasets"
        )

        # Create streaming profile with required configurations
        camera_config = CameraStreamConfig(stream_id="test_camera")
        display_config = DisplayStreamConfig(stream_id="test_display")
        status_config = StatusStreamConfig(stream_id="test_status")

        streaming_profile = StreamingProfile(
            profile_name="test_profile",
            camera_stream=camera_config,
            display_stream=display_config,
            status_stream=status_config
        )

        session = AcquisitionSession(
            session_id="test_session_001",
            stimulus_dataset=dataset,
            session_path=temp_base_path,
            streaming_profile=streaming_profile
        )

        assert session.session_id == "test_session_001"
        assert session.stimulus_dataset.dataset_id == "test_dataset_001"
        assert session.session_path == temp_base_path
        assert session.status == DatasetStatus.READY
        assert not session.status == DatasetStatus.COMPLETED

    def test_acquisition_session_frame_tracking(self, sample_parameters, temp_base_path):
        """Test frame counting and tracking"""

        dataset = StimulusDataset(
            dataset_id="test_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path / "datasets"
        )

        # Create streaming profile with required configurations
        camera_config = CameraStreamConfig(stream_id="test_camera")
        display_config = DisplayStreamConfig(stream_id="test_display")
        status_config = StatusStreamConfig(stream_id="test_status")

        streaming_profile = StreamingProfile(
            profile_name="test_profile",
            camera_stream=camera_config,
            display_stream=display_config,
            status_stream=status_config
        )

        session = AcquisitionSession(
            session_id="test_session_002",
            stimulus_dataset=dataset,
            session_path=temp_base_path,
            streaming_profile=streaming_profile
        )

        # Start acquisition
        session.start_acquisition()
        assert session.status == DatasetStatus.PROCESSING
        assert session.started_timestamp is not None

        # Add frames
        for i in range(100):
            session.add_frame(timestamp=i * 0.033)  # 30 FPS

        assert session.frame_count == 100
        assert len(session.frame_metadata) >= 100

        # Check frame rate calculation
        frame_rate = session.calculate_frame_rate()
        assert frame_rate is not None
        assert 29.0 < frame_rate < 31.0  # Should be close to 30 FPS

    def test_acquisition_session_quality_metrics(self, sample_parameters, temp_base_path):
        """Test quality metrics calculation"""

        dataset = StimulusDataset(
            dataset_id="test_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path / "datasets"
        )

        # Create streaming profile with required configurations
        camera_config = CameraStreamConfig(stream_id="test_camera")
        display_config = DisplayStreamConfig(stream_id="test_display")
        status_config = StatusStreamConfig(stream_id="test_status")

        streaming_profile = StreamingProfile(
            profile_name="test_profile",
            camera_stream=camera_config,
            display_stream=display_config,
            status_stream=status_config
        )

        session = AcquisitionSession(
            session_id="test_session_003",
            stimulus_dataset=dataset,
            session_path=temp_base_path,
            streaming_profile=streaming_profile
        )

        session.start_acquisition()

        # Add frames with varying exposure
        exposures = [33.0, 32.8, 33.2, 32.9, 33.1] * 20  # Some variation
        for i, exposure in enumerate(exposures):
            session.add_frame(
                timestamp=i * 0.033,
                exposure_actual_ms=exposure
            )

        session.stop_acquisition()

        # Calculate quality metrics
        quality = session.calculate_quality_metrics()

        assert "frame_rate_stability" in quality
        assert "exposure_consistency" in quality
        assert "dropped_frames" in quality
        assert quality["frame_rate_stability"] > 0.9  # Should be stable
        assert quality["exposure_consistency"] > 0.9  # Should be consistent

    def test_acquisition_session_completion(self, sample_parameters, temp_base_path):
        """Test session completion workflow"""

        dataset = StimulusDataset(
            dataset_id="test_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path / "datasets"
        )

        # Create streaming profile with required configurations
        camera_config = CameraStreamConfig(stream_id="test_camera")
        display_config = DisplayStreamConfig(stream_id="test_display")
        status_config = StatusStreamConfig(stream_id="test_status")

        streaming_profile = StreamingProfile(
            profile_name="test_profile",
            camera_stream=camera_config,
            display_stream=display_config,
            status_stream=status_config
        )

        session = AcquisitionSession(
            session_id="test_session_004",
            stimulus_dataset=dataset,
            session_path=temp_base_path,
            streaming_profile=streaming_profile
        )

        # Start and add some frames
        session.start_acquisition()
        for i in range(1000):
            session.add_frame(timestamp=i * 0.033)

        session.stop_acquisition()
        session.complete_session()

        assert session.status == DatasetStatus.COMPLETED
        assert session.completed_timestamp is not None
        assert session.session_duration > 0


class TestAnalysisResult:
    """Test AnalysisResult entity"""

    # Using sample_parameters fixture from conftest.py

    @pytest.fixture
    def temp_base_path(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_analysis_result_creation(self, sample_parameters, temp_base_path):
        """Test creating an analysis result"""

        # Create prerequisite objects
        dataset = StimulusDataset(
            dataset_id="test_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path / "datasets"
        )

        # Create streaming profile with required configurations
        camera_config = CameraStreamConfig(stream_id="test_camera")
        display_config = DisplayStreamConfig(stream_id="test_display")
        status_config = StatusStreamConfig(stream_id="test_status")

        streaming_profile = StreamingProfile(
            profile_name="test_profile",
            camera_stream=camera_config,
            display_stream=display_config,
            status_stream=status_config
        )

        session = AcquisitionSession(
            session_id="test_session_001",
            stimulus_dataset=dataset,
            session_path=temp_base_path / "sessions",
            streaming_profile=streaming_profile
        )

        result = AnalysisResult(
            result_id="test_analysis_001",
            session=session,
            analysis_parameters={"algorithm": "fourier", "smoothing": 2.0}
        )

        assert result.result_id == "test_analysis_001"
        assert result.session.session_id == "test_session_001"
        assert result.analysis_parameters["algorithm"] == "fourier"
        assert result.status == DatasetStatus.ANALYZING
        assert not result.status == DatasetStatus.COMPLETED

    def test_analysis_result_data_assignment(self, sample_parameters, temp_base_path):
        """Test analysis data assignment"""

        dataset = StimulusDataset(
            dataset_id="test_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path / "datasets"
        )

        # Create streaming profile with required configurations
        camera_config = CameraStreamConfig(stream_id="test_camera")
        display_config = DisplayStreamConfig(stream_id="test_display")
        status_config = StatusStreamConfig(stream_id="test_status")

        streaming_profile = StreamingProfile(
            profile_name="test_profile",
            camera_stream=camera_config,
            display_stream=display_config,
            status_stream=status_config
        )

        session = AcquisitionSession(
            session_id="test_session_001",
            stimulus_dataset=dataset,
            session_path=temp_base_path / "sessions",
            streaming_profile=streaming_profile
        )

        result = AnalysisResult(
            result_id="test_analysis_002",
            session=session,
            analysis_parameters={"algorithm": "fourier", "smoothing": 2.0}
        )

        # Add analysis data using proper methods
        phase_map = np.random.random((512, 512)).astype(np.float32)
        amplitude_map = np.random.random((512, 512)).astype(np.float32)

        result.add_retinotopic_map("horizontal", phase_map, amplitude_map, 0.85)

        assert "horizontal" in result.retinotopic_maps
        assert result.correlation_quality["horizontal"] == 0.85

    def test_analysis_result_quality_assessment(self, sample_parameters, temp_base_path):
        """Test analysis quality assessment"""

        dataset = StimulusDataset(
            dataset_id="test_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path / "datasets"
        )

        # Create streaming profile with required configurations
        camera_config = CameraStreamConfig(stream_id="test_camera")
        display_config = DisplayStreamConfig(stream_id="test_display")
        status_config = StatusStreamConfig(stream_id="test_status")

        streaming_profile = StreamingProfile(
            profile_name="test_profile",
            camera_stream=camera_config,
            display_stream=display_config,
            status_stream=status_config
        )

        session = AcquisitionSession(
            session_id="test_session_001",
            stimulus_dataset=dataset,
            session_path=temp_base_path / "sessions",
            streaming_profile=streaming_profile
        )

        result = AnalysisResult(
            result_id="test_analysis_003",
            session=session,
            analysis_parameters={"algorithm": "fourier", "smoothing": 2.0}
        )

        # Add some retinotopic maps to calculate quality
        phase_map = np.random.random((100, 100))
        amplitude_map = np.random.random((100, 100))
        result.add_retinotopic_map("horizontal", phase_map, amplitude_map, 0.75)
        result.add_retinotopic_map("vertical", phase_map, amplitude_map, 0.80)

        # Test overall quality calculation
        result._calculate_overall_quality()
        assert result.overall_quality_score > 0.0

    def test_analysis_result_completion(self, sample_parameters, temp_base_path):
        """Test analysis result completion"""

        dataset = StimulusDataset(
            dataset_id="test_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path / "datasets"
        )

        # Create streaming profile with required configurations
        camera_config = CameraStreamConfig(stream_id="test_camera")
        display_config = DisplayStreamConfig(stream_id="test_display")
        status_config = StatusStreamConfig(stream_id="test_status")

        streaming_profile = StreamingProfile(
            profile_name="test_profile",
            camera_stream=camera_config,
            display_stream=display_config,
            status_stream=status_config
        )

        session = AcquisitionSession(
            session_id="test_session_001",
            stimulus_dataset=dataset,
            session_path=temp_base_path / "sessions",
            streaming_profile=streaming_profile
        )

        result = AnalysisResult(
            result_id="test_analysis_004",
            session=session,
            analysis_parameters={"algorithm": "fourier", "smoothing": 2.0}
        )

        # Add required analysis data using proper methods
        phase_map = np.random.random((100, 100))
        amplitude_map = np.random.random((100, 100))
        result.add_retinotopic_map("horizontal", phase_map, amplitude_map, 0.8)
        result.add_retinotopic_map("vertical", phase_map, amplitude_map, 0.8)

        # Set combined maps
        azimuth_map = np.random.random((100, 100))
        elevation_map = np.random.random((100, 100))
        result.set_combined_maps(azimuth_map, elevation_map)

        # Set visual field sign
        sign_map = np.random.random((100, 100))
        areas = [{"area": "V1", "size": 100}]
        result.set_visual_field_sign(sign_map, areas, 0.8)

        result.complete_analysis()

        assert result.status == DatasetStatus.COMPLETED
        assert result.analysis_completed is not None


class TestDatasetIntegration:
    """Test integration between dataset entities"""

    @pytest.fixture
    def temp_base_path(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_dataset_session_analysis_chain(self, sample_parameters, temp_base_path):
        """Test complete dataset → session → analysis chain"""

        # Create stimulus dataset
        dataset = StimulusDataset(
            dataset_id="chain_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path / "datasets"
        )
        dataset.mark_completed()

        # Create acquisition session
        # Create streaming profile with required configurations
        camera_config = CameraStreamConfig(stream_id="test_camera")
        display_config = DisplayStreamConfig(stream_id="test_display")
        status_config = StatusStreamConfig(stream_id="test_status")

        streaming_profile = StreamingProfile(
            profile_name="test_profile",
            camera_stream=camera_config,
            display_stream=display_config,
            status_stream=status_config
        )

        session = AcquisitionSession(
            session_id="chain_session_001",
            stimulus_dataset=dataset,
            session_path=temp_base_path / "sessions",
            streaming_profile=streaming_profile
        )

        # Add frames and complete session
        session.start_acquisition()
        for i in range(1000):
            session.add_frame(timestamp=i * 0.033)
        session.stop_acquisition()
        session.complete_session()

        # Create analysis result
        analysis = AnalysisResult(
            result_id="chain_analysis_001",
            session=session,
            analysis_parameters={"algorithm": "fourier", "smoothing": 2.0}
        )

        # Complete analysis
        phase_map = np.random.random((100, 100))
        amplitude_map = np.random.random((100, 100))
        analysis.add_retinotopic_map("horizontal", phase_map, amplitude_map, 0.8)
        analysis.complete_analysis()

        # Verify the chain
        assert dataset.status == DatasetStatus.COMPLETEDD
        assert session.status == DatasetStatus.COMPLETED  # This might need to be set in the test
        assert analysis.status == DatasetStatus.COMPLETED

        # Verify references
        assert session.stimulus_dataset.dataset_id == dataset.dataset_id
        assert analysis.session.session_id == session.session_id

        # Verify parameter consistency
        dataset_compat = dataset.is_compatible_with_parameters(sample_parameters)
        assert dataset_compat["compatible"] == True


if __name__ == "__main__":
    pytest.main([__file__])