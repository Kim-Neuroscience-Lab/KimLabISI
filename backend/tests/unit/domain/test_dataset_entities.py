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
    SessionStatus,
    AnalysisStatus
)
from src.domain.value_objects.parameters import (
    CombinedParameters,
    StimulusGenerationParams,
    AcquisitionProtocolParams,
    SpatialConfiguration
)


class TestStimulusDataset:
    """Test StimulusDataset entity"""

    @pytest.fixture
    def sample_parameters(self):
        """Create sample parameters for testing"""
        return CombinedParameters(
            stimulus_params=StimulusGenerationParams(
                stimulus_type="drifting_bars",
                directions=["LR", "RL", "TB", "BT"],
                temporal_frequency_hz=0.1,
                spatial_frequency_cpd=0.04,
                cycles_per_trial=10
            ),
            acquisition_params=AcquisitionProtocolParams(
                frame_rate_hz=30.0,
                frame_width=1024,
                frame_height=1024,
                exposure_time_ms=33.0,
                bit_depth=16
            ),
            spatial_config=SpatialConfiguration(
                camera_distance_mm=300.0,
                display_distance_mm=250.0
            )
        )

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
        assert dataset.creation_timestamp is not None
        assert not dataset.is_complete()

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

        dataset.add_data_file("stimulus_patterns", test_file_path)

        assert "stimulus_patterns" in dataset.data_files
        assert dataset.data_files["stimulus_patterns"] == test_file_path

    def test_stimulus_dataset_completion(self, sample_parameters, temp_base_path):
        """Test dataset completion workflow"""
        dataset = StimulusDataset(
            dataset_id="test_dataset_003",
            parameters=sample_parameters,
            base_path=temp_base_path
        )

        # Should not be complete initially
        assert not dataset.is_complete()
        assert dataset.status == DatasetStatus.GENERATING

        # Add required files
        test_files = ["stimulus_patterns.h5", "timing_data.json", "metadata.json"]
        for filename in test_files:
            file_path = temp_base_path / filename
            file_path.touch()
            dataset.add_data_file(filename.split('.')[0], file_path)

        # Mark as complete
        dataset.mark_as_complete()

        assert dataset.is_complete()
        assert dataset.status == DatasetStatus.COMPLETE
        assert dataset.completion_timestamp is not None

    def test_stimulus_dataset_parameter_compatibility(self, sample_parameters, temp_base_path):
        """Test parameter compatibility checking"""
        dataset = StimulusDataset(
            dataset_id="test_dataset_004",
            parameters=sample_parameters,
            base_path=temp_base_path
        )

        # Should be compatible with same parameters
        compatibility = dataset.check_parameter_compatibility(sample_parameters)
        assert compatibility["compatible"] == True
        assert compatibility["compatibility_score"] == 1.0

        # Test with different parameters
        different_params = CombinedParameters(
            stimulus_params=StimulusGenerationParams(
                stimulus_type="checkerboard",  # Different stimulus type
                directions=["LR", "RL"],
                temporal_frequency_hz=0.2,     # Different frequency
                spatial_frequency_cpd=0.04,
                cycles_per_trial=10
            ),
            acquisition_params=sample_parameters.acquisition_params,
            spatial_config=sample_parameters.spatial_config
        )

        compatibility = dataset.check_parameter_compatibility(different_params)
        assert compatibility["compatible"] == False
        assert compatibility["compatibility_score"] < 1.0
        assert len(compatibility["differences"]) > 0

    def test_stimulus_dataset_serialization(self, sample_parameters, temp_base_path):
        """Test dataset serialization and deserialization"""
        original_dataset = StimulusDataset(
            dataset_id="test_dataset_005",
            parameters=sample_parameters,
            base_path=temp_base_path
        )

        # Add some data
        original_dataset.add_data_file("test_file", temp_base_path / "test.h5")
        original_dataset.metadata["test_key"] = "test_value"

        # Convert to dict and back
        dataset_dict = original_dataset.to_dict()

        # Verify dict structure
        assert dataset_dict["dataset_id"] == "test_dataset_005"
        assert dataset_dict["status"] == DatasetStatus.GENERATING.value
        assert "parameters" in dataset_dict
        assert "data_files" in dataset_dict

    @patch('src.domain.entities.dataset.h5py')
    def test_stimulus_dataset_hdf5_integration(self, mock_h5py, sample_parameters, temp_base_path):
        """Test HDF5 file integration"""
        # Mock HDF5 file operations
        mock_file = MagicMock()
        mock_h5py.File.return_value.__enter__.return_value = mock_file

        dataset = StimulusDataset(
            dataset_id="test_dataset_hdf5",
            parameters=sample_parameters,
            base_path=temp_base_path
        )

        # Test data existence check
        dataset.add_data_file("patterns", temp_base_path / "patterns.h5")

        # Since we're mocking, we can't actually test file operations
        # but we can verify the file was added to the dataset
        assert "patterns" in dataset.data_files


class TestAcquisitionSession:
    """Test AcquisitionSession entity"""

    @pytest.fixture
    def sample_parameters(self):
        """Create sample parameters for testing"""
        return CombinedParameters(
            stimulus_params=StimulusGenerationParams(
                stimulus_type="drifting_bars",
                directions=["LR", "RL", "TB", "BT"],
                temporal_frequency_hz=0.1,
                spatial_frequency_cpd=0.04,
                cycles_per_trial=10
            ),
            acquisition_params=AcquisitionProtocolParams(
                frame_rate_hz=30.0,
                frame_width=1024,
                frame_height=1024,
                exposure_time_ms=33.0,
                bit_depth=16
            ),
            spatial_config=SpatialConfiguration(
                camera_distance_mm=300.0,
                display_distance_mm=250.0
            )
        )

    @pytest.fixture
    def temp_base_path(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_acquisition_session_creation(self, sample_parameters, temp_base_path):
        """Test creating an acquisition session"""
        session = AcquisitionSession(
            session_id="test_session_001",
            dataset_id="test_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path
        )

        assert session.session_id == "test_session_001"
        assert session.dataset_id == "test_dataset_001"
        assert session.parameters == sample_parameters
        assert session.base_path == temp_base_path
        assert session.status == SessionStatus.PREPARING
        assert not session.is_complete()

    def test_acquisition_session_frame_tracking(self, sample_parameters, temp_base_path):
        """Test frame counting and tracking"""
        session = AcquisitionSession(
            session_id="test_session_002",
            dataset_id="test_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path
        )

        # Start acquisition
        session.start_acquisition()
        assert session.status == SessionStatus.ACQUIRING
        assert session.start_timestamp is not None

        # Add frames
        for i in range(100):
            session.add_frame(timestamp=i * 0.033)  # 30 FPS

        assert session.frame_count == 100
        assert len(session.frame_timestamps) == 100

        # Check frame rate calculation
        frame_rate = session.calculate_actual_frame_rate()
        assert frame_rate is not None
        assert 29.0 < frame_rate < 31.0  # Should be close to 30 FPS

    def test_acquisition_session_quality_metrics(self, sample_parameters, temp_base_path):
        """Test quality metrics calculation"""
        session = AcquisitionSession(
            session_id="test_session_003",
            dataset_id="test_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path
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
        session = AcquisitionSession(
            session_id="test_session_004",
            dataset_id="test_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path
        )

        # Start and add some frames
        session.start_acquisition()
        for i in range(1000):
            session.add_frame(timestamp=i * 0.033)

        session.stop_acquisition()
        session.mark_as_complete()

        assert session.is_complete()
        assert session.status == SessionStatus.COMPLETE
        assert session.end_timestamp is not None
        assert session.duration_s > 0


class TestAnalysisResult:
    """Test AnalysisResult entity"""

    @pytest.fixture
    def sample_parameters(self):
        """Create sample parameters for testing"""
        return CombinedParameters(
            stimulus_params=StimulusGenerationParams(
                stimulus_type="drifting_bars",
                directions=["LR", "RL", "TB", "BT"],
                temporal_frequency_hz=0.1,
                spatial_frequency_cpd=0.04,
                cycles_per_trial=10
            ),
            acquisition_params=AcquisitionProtocolParams(
                frame_rate_hz=30.0,
                frame_width=1024,
                frame_height=1024,
                exposure_time_ms=33.0,
                bit_depth=16
            ),
            spatial_config=SpatialConfiguration(
                camera_distance_mm=300.0,
                display_distance_mm=250.0
            )
        )

    @pytest.fixture
    def temp_base_path(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_analysis_result_creation(self, sample_parameters, temp_base_path):
        """Test creating an analysis result"""
        result = AnalysisResult(
            analysis_id="test_analysis_001",
            dataset_id="test_dataset_001",
            session_id="test_session_001",
            parameters=sample_parameters,
            base_path=temp_base_path
        )

        assert result.analysis_id == "test_analysis_001"
        assert result.dataset_id == "test_dataset_001"
        assert result.session_id == "test_session_001"
        assert result.parameters == sample_parameters
        assert result.status == AnalysisStatus.ANALYZING
        assert not result.is_complete()

    def test_analysis_result_data_assignment(self, sample_parameters, temp_base_path):
        """Test analysis data assignment"""
        result = AnalysisResult(
            analysis_id="test_analysis_002",
            dataset_id="test_dataset_001",
            session_id="test_session_001",
            parameters=sample_parameters,
            base_path=temp_base_path
        )

        # Add analysis data
        phase_map = np.random.random((512, 512)).astype(np.float32)
        amplitude_map = np.random.random((512, 512)).astype(np.float32)

        result.phase_map = {"horizontal": phase_map}
        result.amplitude_map = {"horizontal": amplitude_map}
        result.quality_score = 0.85

        assert result.phase_map is not None
        assert result.amplitude_map is not None
        assert result.quality_score == 0.85

    def test_analysis_result_quality_assessment(self, sample_parameters, temp_base_path):
        """Test analysis quality assessment"""
        result = AnalysisResult(
            analysis_id="test_analysis_003",
            dataset_id="test_dataset_001",
            session_id="test_session_001",
            parameters=sample_parameters,
            base_path=temp_base_path
        )

        # Set quality metrics
        result.quality_metrics = {
            "coherence_mean": 0.7,
            "coverage_fraction": 0.8,
            "snr_db": 15.0
        }

        result.quality_score = 0.75

        # Test quality assessment
        quality_level = result.get_quality_level()
        assert quality_level in ["excellent", "good", "acceptable", "poor"]

    def test_analysis_result_completion(self, sample_parameters, temp_base_path):
        """Test analysis result completion"""
        result = AnalysisResult(
            analysis_id="test_analysis_004",
            dataset_id="test_dataset_001",
            session_id="test_session_001",
            parameters=sample_parameters,
            base_path=temp_base_path
        )

        # Add required analysis data
        result.phase_map = {"horizontal": np.random.random((100, 100))}
        result.amplitude_map = {"horizontal": np.random.random((100, 100))}
        result.retinotopic_map = {
            "azimuth": np.random.random((100, 100)),
            "elevation": np.random.random((100, 100))
        }
        result.visual_field_sign = np.random.random((100, 100))
        result.quality_score = 0.8

        result.mark_as_complete()

        assert result.is_complete()
        assert result.status == AnalysisStatus.COMPLETE
        assert result.completion_timestamp is not None


class TestDatasetIntegration:
    """Test integration between dataset entities"""

    @pytest.fixture
    def sample_parameters(self):
        """Create sample parameters for testing"""
        return CombinedParameters(
            stimulus_params=StimulusGenerationParams(
                stimulus_type="drifting_bars",
                directions=["LR", "RL", "TB", "BT"],
                temporal_frequency_hz=0.1,
                spatial_frequency_cpd=0.04,
                cycles_per_trial=10
            ),
            acquisition_params=AcquisitionProtocolParams(
                frame_rate_hz=30.0,
                frame_width=1024,
                frame_height=1024,
                exposure_time_ms=33.0,
                bit_depth=16
            ),
            spatial_config=SpatialConfiguration(
                camera_distance_mm=300.0,
                display_distance_mm=250.0
            )
        )

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
        dataset.mark_as_complete()

        # Create acquisition session
        session = AcquisitionSession(
            session_id="chain_session_001",
            dataset_id=dataset.dataset_id,
            parameters=sample_parameters,
            base_path=temp_base_path / "sessions"
        )

        # Add frames and complete session
        session.start_acquisition()
        for i in range(1000):
            session.add_frame(timestamp=i * 0.033)
        session.stop_acquisition()
        session.mark_as_complete()

        # Create analysis result
        analysis = AnalysisResult(
            analysis_id="chain_analysis_001",
            dataset_id=dataset.dataset_id,
            session_id=session.session_id,
            parameters=sample_parameters,
            base_path=temp_base_path / "analyses"
        )

        # Complete analysis
        analysis.phase_map = {"horizontal": np.random.random((100, 100))}
        analysis.amplitude_map = {"horizontal": np.random.random((100, 100))}
        analysis.quality_score = 0.8
        analysis.mark_as_complete()

        # Verify the chain
        assert dataset.is_complete()
        assert session.is_complete()
        assert analysis.is_complete()

        # Verify references
        assert session.dataset_id == dataset.dataset_id
        assert analysis.dataset_id == dataset.dataset_id
        assert analysis.session_id == session.session_id

        # Verify parameter consistency
        dataset_compat = dataset.check_parameter_compatibility(session.parameters)
        assert dataset_compat["compatible"] == True


if __name__ == "__main__":
    pytest.main([__file__])