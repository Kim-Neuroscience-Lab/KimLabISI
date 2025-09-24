"""
Tests for Domain Dataset Repository Services

Tests for repository classes that manage persistence and retrieval
of stimulus datasets, acquisition sessions, and analysis results.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import json
import shutil
from unittest.mock import Mock, patch, MagicMock

from src.domain.services.dataset_repository import (
    StimulusDatasetRepository,
    AcquisitionSessionRepository,
    AnalysisResultRepository,
    DatasetRepositoryManager,
    DatasetMetadata,
    SortOrder,
    RepositoryError
)
from src.domain.entities.dataset import (
    StimulusDataset,
    AcquisitionSession,
    AnalysisResult
)
from src.domain.value_objects.parameters import (
    CombinedParameters,
    StimulusGenerationParams,
    AcquisitionProtocolParams,
    SpatialConfiguration
)


class TestDatasetMetadata:
    """Test DatasetMetadata value object"""

    def test_dataset_metadata_creation(self):
        """Test creating dataset metadata"""
        metadata = DatasetMetadata(
            dataset_id="test_dataset_001",
            file_path=Path("/test/path/dataset.json"),
            creation_timestamp=datetime.now(),
            file_size_bytes=1024,
            metadata={"stimulus_type": "drifting_bars", "status": "complete"}
        )

        assert metadata.dataset_id == "test_dataset_001"
        assert metadata.file_path == Path("/test/path/dataset.json")
        assert metadata.file_size_bytes == 1024
        assert metadata.metadata["stimulus_type"] == "drifting_bars"

    def test_metadata_serialization(self):
        """Test metadata serialization"""
        timestamp = datetime.now()
        metadata = DatasetMetadata(
            dataset_id="test_dataset_002",
            file_path=Path("/test/path/dataset.json"),
            creation_timestamp=timestamp,
            file_size_bytes=2048,
            metadata={"test_key": "test_value"}
        )

        metadata_dict = metadata.to_dict()

        assert metadata_dict["dataset_id"] == "test_dataset_002"
        assert metadata_dict["file_path"] == "/test/path/dataset.json"
        assert metadata_dict["creation_timestamp"] == timestamp.isoformat()
        assert metadata_dict["file_size_bytes"] == 2048
        assert metadata_dict["metadata"]["test_key"] == "test_value"


class TestStimulusDatasetRepository:
    """Test StimulusDatasetRepository"""

    @pytest.fixture
    def temp_base_path(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

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

    def test_repository_initialization(self, temp_base_path):
        """Test repository initialization"""
        repo = StimulusDatasetRepository(temp_base_path)

        assert repo.base_path == temp_base_path
        assert repo.datasets_path == temp_base_path / "stimulus_datasets"
        assert repo.datasets_path.exists()

    def test_save_and_load_dataset(self, temp_base_path, sample_parameters):
        """Test saving and loading datasets"""
        repo = StimulusDatasetRepository(temp_base_path)

        # Create test dataset
        dataset = StimulusDataset(
            dataset_id="test_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path / "data"
        )
        dataset.mark_as_complete()

        # Save dataset
        saved_path = repo.save(dataset)
        assert saved_path.exists()
        assert saved_path.name == "dataset.json"

        # Load dataset
        loaded_dataset = repo.load("test_dataset_001")
        assert loaded_dataset.dataset_id == dataset.dataset_id
        assert loaded_dataset.parameters.stimulus_params.stimulus_type == dataset.parameters.stimulus_params.stimulus_type

    def test_dataset_existence_check(self, temp_base_path, sample_parameters):
        """Test dataset existence checking"""
        repo = StimulusDatasetRepository(temp_base_path)

        # Should not exist initially
        assert repo.exists("nonexistent_dataset") == False

        # Create and save dataset
        dataset = StimulusDataset(
            dataset_id="test_dataset_002",
            parameters=sample_parameters,
            base_path=temp_base_path / "data"
        )
        repo.save(dataset)

        # Should exist now
        assert repo.exists("test_dataset_002") == True

    def test_list_datasets(self, temp_base_path, sample_parameters):
        """Test listing datasets"""
        repo = StimulusDatasetRepository(temp_base_path)

        # Empty repository
        datasets = repo.list_datasets()
        assert len(datasets) == 0

        # Add multiple datasets
        for i in range(3):
            dataset = StimulusDataset(
                dataset_id=f"test_dataset_{i:03d}",
                parameters=sample_parameters,
                base_path=temp_base_path / "data" / f"dataset_{i}"
            )
            dataset.mark_as_complete()
            repo.save(dataset)

        # List all datasets
        datasets = repo.list_datasets()
        assert len(datasets) == 3

        # Check sorting (newest first by default)
        assert datasets[0].dataset_id >= datasets[1].dataset_id  # Lexicographically

        # Test with limit
        limited_datasets = repo.list_datasets(limit=2)
        assert len(limited_datasets) == 2

    def test_sorting_options(self, temp_base_path, sample_parameters):
        """Test different sorting options"""
        repo = StimulusDatasetRepository(temp_base_path)

        # Create datasets with different timestamps
        datasets_info = [
            ("dataset_a", datetime.now() - timedelta(hours=2)),
            ("dataset_b", datetime.now() - timedelta(hours=1)),
            ("dataset_c", datetime.now())
        ]

        for dataset_id, timestamp in datasets_info:
            dataset = StimulusDataset(
                dataset_id=dataset_id,
                parameters=sample_parameters,
                base_path=temp_base_path / "data"
            )
            dataset.creation_timestamp = timestamp
            dataset.mark_as_complete()
            repo.save(dataset)

        # Test newest first (default)
        datasets = repo.list_datasets(sort_order=SortOrder.NEWEST_FIRST)
        assert datasets[0].dataset_id == "dataset_c"
        assert datasets[2].dataset_id == "dataset_a"

        # Test oldest first
        datasets = repo.list_datasets(sort_order=SortOrder.OLDEST_FIRST)
        assert datasets[0].dataset_id == "dataset_a"
        assert datasets[2].dataset_id == "dataset_c"

        # Test name ascending
        datasets = repo.list_datasets(sort_order=SortOrder.NAME_ASC)
        assert datasets[0].dataset_id == "dataset_a"
        assert datasets[2].dataset_id == "dataset_c"

    def test_delete_dataset(self, temp_base_path, sample_parameters):
        """Test deleting datasets"""
        repo = StimulusDatasetRepository(temp_base_path)

        # Create and save dataset
        dataset = StimulusDataset(
            dataset_id="test_dataset_delete",
            parameters=sample_parameters,
            base_path=temp_base_path / "data"
        )
        repo.save(dataset)

        # Verify it exists
        assert repo.exists("test_dataset_delete") == True

        # Delete it
        success = repo.delete("test_dataset_delete")
        assert success == True

        # Verify it's gone
        assert repo.exists("test_dataset_delete") == False

        # Try to delete non-existent dataset
        success = repo.delete("nonexistent")
        assert success == False

    def test_storage_info(self, temp_base_path, sample_parameters):
        """Test storage information"""
        repo = StimulusDatasetRepository(temp_base_path)

        # Empty repository
        storage_info = repo.get_storage_info()
        assert storage_info["dataset_count"] == 0
        assert storage_info["total_size_bytes"] == 0

        # Add datasets
        for i in range(2):
            dataset = StimulusDataset(
                dataset_id=f"test_dataset_{i}",
                parameters=sample_parameters,
                base_path=temp_base_path / "data"
            )
            repo.save(dataset)

        storage_info = repo.get_storage_info()
        assert storage_info["dataset_count"] == 2
        assert storage_info["total_size_bytes"] > 0
        assert storage_info["total_size_mb"] > 0

    def test_error_handling(self, temp_base_path):
        """Test error handling"""
        repo = StimulusDatasetRepository(temp_base_path)

        # Try to load non-existent dataset
        with pytest.raises(RepositoryError):
            repo.load("nonexistent_dataset")

        # Try to save dataset with invalid data (mock the save to fail)
        with patch.object(StimulusDataset, 'save_to_file', side_effect=Exception("Save failed")):
            dataset = Mock()
            dataset.dataset_id = "test_fail"

            with pytest.raises(RepositoryError):
                repo.save(dataset)


class TestAcquisitionSessionRepository:
    """Test AcquisitionSessionRepository"""

    @pytest.fixture
    def temp_base_path(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def sample_parameters(self):
        """Create sample parameters for testing"""
        return CombinedParameters(
            stimulus_params=StimulusGenerationParams(
                stimulus_type="drifting_bars",
                directions=["LR", "RL"],
                temporal_frequency_hz=0.1,
                spatial_frequency_cpd=0.04,
                cycles_per_trial=5
            ),
            acquisition_params=AcquisitionProtocolParams(
                frame_rate_hz=30.0,
                frame_width=512,
                frame_height=512,
                exposure_time_ms=33.0,
                bit_depth=16
            ),
            spatial_config=SpatialConfiguration(
                camera_distance_mm=300.0,
                display_distance_mm=250.0
            )
        )

    def test_session_repository_basic_operations(self, temp_base_path, sample_parameters):
        """Test basic session repository operations"""
        repo = AcquisitionSessionRepository(temp_base_path)

        # Create test session
        session = AcquisitionSession(
            session_id="test_session_001",
            dataset_id="test_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path / "sessions"
        )
        session.start_acquisition()
        session.stop_acquisition()
        session.mark_as_complete()

        # Save session
        saved_path = repo.save(session)
        assert saved_path.exists()

        # Load session
        loaded_session = repo.load("test_session_001")
        assert loaded_session.session_id == session.session_id
        assert loaded_session.dataset_id == session.dataset_id

        # Check existence
        assert repo.exists("test_session_001") == True
        assert repo.exists("nonexistent") == False

    def test_session_listing(self, temp_base_path, sample_parameters):
        """Test session listing with metadata"""
        repo = AcquisitionSessionRepository(temp_base_path)

        # Create multiple sessions
        for i in range(3):
            session = AcquisitionSession(
                session_id=f"session_{i:03d}",
                dataset_id=f"dataset_{i:03d}",
                parameters=sample_parameters,
                base_path=temp_base_path / "sessions"
            )
            session.frame_count = (i + 1) * 100  # Different frame counts
            session.duration_s = (i + 1) * 30.0  # Different durations
            session.mark_as_complete()
            repo.save(session)

        # List sessions
        sessions = repo.list_sessions()
        assert len(sessions) == 3

        # Check metadata includes session-specific info
        for session_meta in sessions:
            assert "frame_count" in session_meta.metadata
            assert "duration_s" in session_meta.metadata
            assert "dataset_id" in session_meta.metadata


class TestAnalysisResultRepository:
    """Test AnalysisResultRepository"""

    @pytest.fixture
    def temp_base_path(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def sample_parameters(self):
        """Create sample parameters for testing"""
        return CombinedParameters(
            stimulus_params=StimulusGenerationParams(
                stimulus_type="drifting_bars",
                directions=["LR", "RL"],
                temporal_frequency_hz=0.1,
                spatial_frequency_cpd=0.04,
                cycles_per_trial=5
            ),
            acquisition_params=AcquisitionProtocolParams(
                frame_rate_hz=30.0,
                frame_width=512,
                frame_height=512,
                exposure_time_ms=33.0,
                bit_depth=16
            ),
            spatial_config=SpatialConfiguration(
                camera_distance_mm=300.0,
                display_distance_mm=250.0
            )
        )

    def test_analysis_repository_basic_operations(self, temp_base_path, sample_parameters):
        """Test basic analysis repository operations"""
        repo = AnalysisResultRepository(temp_base_path)

        # Create test analysis
        analysis = AnalysisResult(
            analysis_id="test_analysis_001",
            dataset_id="test_dataset_001",
            session_id="test_session_001",
            parameters=sample_parameters,
            base_path=temp_base_path / "analyses"
        )
        analysis.quality_score = 0.85
        analysis.mark_as_complete()

        # Save analysis
        saved_path = repo.save(analysis)
        assert saved_path.exists()

        # Load analysis
        loaded_analysis = repo.load("test_analysis_001")
        assert loaded_analysis.analysis_id == analysis.analysis_id
        assert loaded_analysis.dataset_id == analysis.dataset_id
        assert loaded_analysis.session_id == analysis.session_id

        # Check existence
        assert repo.exists("test_analysis_001") == True

    def test_analysis_relationship_queries(self, temp_base_path, sample_parameters):
        """Test analysis relationship queries"""
        repo = AnalysisResultRepository(temp_base_path)

        # Create analyses for different sessions and datasets
        analyses_info = [
            ("analysis_001", "dataset_001", "session_001"),
            ("analysis_002", "dataset_001", "session_002"),
            ("analysis_003", "dataset_002", "session_003")
        ]

        for analysis_id, dataset_id, session_id in analyses_info:
            analysis = AnalysisResult(
                analysis_id=analysis_id,
                dataset_id=dataset_id,
                session_id=session_id,
                parameters=sample_parameters,
                base_path=temp_base_path / "analyses"
            )
            analysis.mark_as_complete()
            repo.save(analysis)

        # Find by session
        session_analyses = repo.find_by_session("session_001")
        assert len(session_analyses) == 1
        assert session_analyses[0].dataset_id == "analysis_001"

        # Find by dataset
        dataset_analyses = repo.find_by_dataset("dataset_001")
        assert len(dataset_analyses) == 2

        # Find by non-existent session
        empty_results = repo.find_by_session("nonexistent")
        assert len(empty_results) == 0


class TestDatasetRepositoryManager:
    """Test DatasetRepositoryManager"""

    @pytest.fixture
    def temp_base_path(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def sample_parameters(self):
        """Create sample parameters for testing"""
        return CombinedParameters(
            stimulus_params=StimulusGenerationParams(
                stimulus_type="drifting_bars",
                directions=["LR", "RL"],
                temporal_frequency_hz=0.1,
                spatial_frequency_cpd=0.04,
                cycles_per_trial=5
            ),
            acquisition_params=AcquisitionProtocolParams(
                frame_rate_hz=30.0,
                frame_width=512,
                frame_height=512,
                exposure_time_ms=33.0,
                bit_depth=16
            ),
            spatial_config=SpatialConfiguration(
                camera_distance_mm=300.0,
                display_distance_mm=250.0
            )
        )

    def test_manager_initialization(self, temp_base_path):
        """Test repository manager initialization"""
        manager = DatasetRepositoryManager(temp_base_path)

        assert manager.base_path == temp_base_path
        assert isinstance(manager.stimulus_datasets, StimulusDatasetRepository)
        assert isinstance(manager.acquisition_sessions, AcquisitionSessionRepository)
        assert isinstance(manager.analysis_results, AnalysisResultRepository)

    def test_system_overview(self, temp_base_path, sample_parameters):
        """Test system overview functionality"""
        manager = DatasetRepositoryManager(temp_base_path)

        # Empty system
        overview = manager.get_system_overview()
        assert overview["stimulus_datasets"]["count"] == 0
        assert overview["acquisition_sessions"]["count"] == 0
        assert overview["analysis_results"]["count"] == 0

        # Add some data
        # Stimulus dataset
        dataset = StimulusDataset(
            dataset_id="overview_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path / "datasets"
        )
        manager.stimulus_datasets.save(dataset)

        # Session
        session = AcquisitionSession(
            session_id="overview_session_001",
            dataset_id="overview_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path / "sessions"
        )
        manager.acquisition_sessions.save(session)

        # Analysis
        analysis = AnalysisResult(
            analysis_id="overview_analysis_001",
            dataset_id="overview_dataset_001",
            session_id="overview_session_001",
            parameters=sample_parameters,
            base_path=temp_base_path / "analyses"
        )
        manager.analysis_results.save(analysis)

        # Check updated overview
        overview = manager.get_system_overview()
        assert overview["stimulus_datasets"]["count"] == 1
        assert overview["acquisition_sessions"]["count"] == 1
        assert overview["analysis_results"]["count"] == 1
        assert "last_updated" in overview

    def test_cleanup_orphaned_data(self, temp_base_path, sample_parameters):
        """Test orphaned data cleanup"""
        manager = DatasetRepositoryManager(temp_base_path)

        # Create session
        session = AcquisitionSession(
            session_id="cleanup_session_001",
            dataset_id="cleanup_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path / "sessions"
        )
        manager.acquisition_sessions.save(session)

        # Create analyses - one valid, one orphaned
        valid_analysis = AnalysisResult(
            analysis_id="cleanup_analysis_valid",
            dataset_id="cleanup_dataset_001",
            session_id="cleanup_session_001",
            parameters=sample_parameters,
            base_path=temp_base_path / "analyses"
        )
        manager.analysis_results.save(valid_analysis)

        orphaned_analysis = AnalysisResult(
            analysis_id="cleanup_analysis_orphaned",
            dataset_id="cleanup_dataset_001",
            session_id="nonexistent_session",  # This session doesn't exist
            parameters=sample_parameters,
            base_path=temp_base_path / "analyses"
        )
        manager.analysis_results.save(orphaned_analysis)

        # Verify both analyses exist
        assert manager.analysis_results.exists("cleanup_analysis_valid") == True
        assert manager.analysis_results.exists("cleanup_analysis_orphaned") == True

        # Run cleanup
        cleanup_stats = manager.cleanup_orphaned_data()

        # Check cleanup results
        assert cleanup_stats["orphaned_analyses_removed"] == 1

        # Verify orphaned analysis was removed, valid one remains
        assert manager.analysis_results.exists("cleanup_analysis_valid") == True
        assert manager.analysis_results.exists("cleanup_analysis_orphaned") == False

    def test_error_handling(self, temp_base_path):
        """Test repository manager error handling"""
        manager = DatasetRepositoryManager(temp_base_path)

        # Mock a failure in the stimulus repository
        with patch.object(manager.stimulus_datasets, 'get_storage_info', side_effect=Exception("Storage error")):
            with pytest.raises(RepositoryError):
                manager.get_system_overview()

        # Mock failure in cleanup
        with patch.object(manager.acquisition_sessions, 'list_sessions', side_effect=Exception("List error")):
            with pytest.raises(RepositoryError):
                manager.cleanup_orphaned_data()


class TestRepositoryIntegration:
    """Test repository integration scenarios"""

    @pytest.fixture
    def temp_base_path(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def sample_parameters(self):
        """Create sample parameters for testing"""
        return CombinedParameters(
            stimulus_params=StimulusGenerationParams(
                stimulus_type="drifting_bars",
                directions=["LR", "RL"],
                temporal_frequency_hz=0.1,
                spatial_frequency_cpd=0.04,
                cycles_per_trial=5
            ),
            acquisition_params=AcquisitionProtocolParams(
                frame_rate_hz=30.0,
                frame_width=512,
                frame_height=512,
                exposure_time_ms=33.0,
                bit_depth=16
            ),
            spatial_config=SpatialConfiguration(
                camera_distance_mm=300.0,
                display_distance_mm=250.0
            )
        )

    def test_complete_workflow_persistence(self, temp_base_path, sample_parameters):
        """Test complete workflow data persistence"""
        manager = DatasetRepositoryManager(temp_base_path)

        # Step 1: Create and save stimulus dataset
        dataset = StimulusDataset(
            dataset_id="workflow_dataset_001",
            parameters=sample_parameters,
            base_path=temp_base_path / "datasets"
        )
        dataset.mark_as_complete()
        dataset_path = manager.stimulus_datasets.save(dataset)

        # Step 2: Create and save acquisition session
        session = AcquisitionSession(
            session_id="workflow_session_001",
            dataset_id=dataset.dataset_id,
            parameters=sample_parameters,
            base_path=temp_base_path / "sessions"
        )
        session.start_acquisition()
        for i in range(100):
            session.add_frame(timestamp=i * 0.033)
        session.stop_acquisition()
        session.mark_as_complete()
        session_path = manager.acquisition_sessions.save(session)

        # Step 3: Create and save analysis result
        analysis = AnalysisResult(
            analysis_id="workflow_analysis_001",
            dataset_id=dataset.dataset_id,
            session_id=session.session_id,
            parameters=sample_parameters,
            base_path=temp_base_path / "analyses"
        )
        analysis.quality_score = 0.8
        analysis.mark_as_complete()
        analysis_path = manager.analysis_results.save(analysis)

        # Verify all files exist
        assert dataset_path.exists()
        assert session_path.exists()
        assert analysis_path.exists()

        # Verify data integrity through loading
        loaded_dataset = manager.stimulus_datasets.load(dataset.dataset_id)
        loaded_session = manager.acquisition_sessions.load(session.session_id)
        loaded_analysis = manager.analysis_results.load(analysis.analysis_id)

        # Verify relationships
        assert loaded_session.dataset_id == loaded_dataset.dataset_id
        assert loaded_analysis.dataset_id == loaded_dataset.dataset_id
        assert loaded_analysis.session_id == loaded_session.session_id

        # Verify system overview
        overview = manager.get_system_overview()
        assert overview["stimulus_datasets"]["count"] == 1
        assert overview["acquisition_sessions"]["count"] == 1
        assert overview["analysis_results"]["count"] == 1

    def test_cross_repository_queries(self, temp_base_path, sample_parameters):
        """Test queries across different repositories"""
        manager = DatasetRepositoryManager(temp_base_path)

        # Create related data
        dataset_id = "cross_dataset_001"
        session_id = "cross_session_001"

        # Dataset
        dataset = StimulusDataset(
            dataset_id=dataset_id,
            parameters=sample_parameters,
            base_path=temp_base_path / "datasets"
        )
        manager.stimulus_datasets.save(dataset)

        # Session
        session = AcquisitionSession(
            session_id=session_id,
            dataset_id=dataset_id,
            parameters=sample_parameters,
            base_path=temp_base_path / "sessions"
        )
        manager.acquisition_sessions.save(session)

        # Multiple analyses for the same session
        for i in range(3):
            analysis = AnalysisResult(
                analysis_id=f"cross_analysis_{i:03d}",
                dataset_id=dataset_id,
                session_id=session_id,
                parameters=sample_parameters,
                base_path=temp_base_path / "analyses"
            )
            manager.analysis_results.save(analysis)

        # Query analyses by session
        session_analyses = manager.analysis_results.find_by_session(session_id)
        assert len(session_analyses) == 3

        # Query analyses by dataset
        dataset_analyses = manager.analysis_results.find_by_dataset(dataset_id)
        assert len(dataset_analyses) == 3

        # Verify all analyses reference the same session and dataset
        for analysis_meta in session_analyses:
            assert analysis_meta.metadata["dataset_id"] == dataset_id
            assert analysis_meta.metadata["session_id"] == session_id


if __name__ == "__main__":
    pytest.main([__file__])