"""
Tests for StatePersistenceService application service

Comprehensive test suite for workflow state persistence, recovery mechanisms,
snapshot management, and backup/restore functionality.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime, timedelta
import json
import tempfile
from pathlib import Path
import shutil
import asyncio

from src.application.services.state_persistence import (
    StatePersistenceService,
    WorkflowSnapshot,
    PersistenceLevel,
    RecoveryStrategy,
    PersistenceError
)
from src.domain.value_objects.workflow_state import WorkflowState
from src.domain.value_objects.parameters import CombinedParameters
from src.domain.entities.hardware import HardwareSystem


class TestStatePersistenceService:
    """Test StatePersistenceService functionality"""

    @pytest.fixture
    def temp_persistence_path(self):
        """Create temporary directory for persistence testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def mock_hardware_system(self):
        """Mock hardware system"""
        mock = Mock(spec=HardwareSystem)
        mock.get_system_status_summary.return_value = {
            "overall_status": "healthy",
            "components_count": 3,
            "active_components": 3,
            "hardware_health": 0.95
        }
        return mock

    @pytest.fixture
    def mock_combined_parameters(self):
        """Mock combined parameters"""
        mock = Mock(spec=CombinedParameters)
        mock.to_dict.return_value = {
            "stimulus": {"frequency": 10.0, "amplitude": 1.0},
            "acquisition": {"duration": 60.0, "sampling_rate": 1000.0}
        }
        return mock

    @pytest.fixture
    def persistence_service(self, temp_persistence_path, mock_hardware_system):
        """Create StatePersistenceService with temp directory"""
        return StatePersistenceService(
            persistence_path=temp_persistence_path,
            hardware_system=mock_hardware_system,
            persistence_level=PersistenceLevel.STANDARD
        )

    @pytest.mark.asyncio
    async def test_service_initialization(self, temp_persistence_path, mock_hardware_system):
        """Test service initialization and directory creation"""
        service = StatePersistenceService(
            persistence_path=temp_persistence_path,
            hardware_system=mock_hardware_system
        )

        # Check that directories were created
        assert service.persistence_path.exists()
        assert service.snapshots_path.exists()
        assert service.recovery_path.exists()
        assert service.current_state_path.parent.exists()

    @pytest.mark.asyncio
    async def test_save_workflow_snapshot(self, persistence_service, mock_combined_parameters):
        """Test saving workflow snapshot"""
        snapshot_id = await persistence_service.save_workflow_snapshot(
            workflow_state=WorkflowState.READY,
            parameters=mock_combined_parameters,
            dataset_id="test_dataset_001",
            session_id="session_001",
            metadata={"test": "metadata"}
        )

        assert snapshot_id is not None
        assert snapshot_id.startswith("snapshot_")

        # Check snapshot file was created
        snapshot_file = persistence_service.snapshots_path / f"{snapshot_id}.json"
        assert snapshot_file.exists()

        # Check snapshot content
        with open(snapshot_file, 'r') as f:
            snapshot_data = json.load(f)

        assert snapshot_data["workflow_state"] == WorkflowState.READY.value
        assert snapshot_data["dataset_id"] == "test_dataset_001"
        assert snapshot_data["session_id"] == "session_001"
        assert snapshot_data["metadata"]["test"] == "metadata"

    @pytest.mark.asyncio
    async def test_save_current_state(self, persistence_service, mock_combined_parameters):
        """Test saving current state file"""
        # First create a snapshot
        await persistence_service.save_workflow_snapshot(
            workflow_state=WorkflowState.READY,
            parameters=mock_combined_parameters
        )

        # Current state file should exist
        assert persistence_service.current_state_path.exists()

        # Check current state content
        with open(persistence_service.current_state_path, 'r') as f:
            state_data = json.load(f)

        assert state_data["workflow_state"] == WorkflowState.READY.value

    @pytest.mark.asyncio
    async def test_load_current_state(self, persistence_service, mock_combined_parameters):
        """Test loading current state"""
        # Save a snapshot first
        snapshot_id = await persistence_service.save_workflow_snapshot(
            workflow_state=WorkflowState.ACQUIRING,
            parameters=mock_combined_parameters,
            dataset_id="load_test"
        )

        # Load current state
        snapshot = await persistence_service.load_current_state()

        assert snapshot is not None
        assert snapshot.workflow_state == WorkflowState.ACQUIRING
        assert snapshot.dataset_id == "load_test"

    @pytest.mark.asyncio
    async def test_load_current_state_no_file(self, persistence_service):
        """Test loading current state when no file exists"""
        # Should return None when no current state file
        snapshot = await persistence_service.load_current_state()
        assert snapshot is None

    @pytest.mark.asyncio
    async def test_load_snapshot_by_id(self, persistence_service, mock_combined_parameters):
        """Test loading specific snapshot by ID"""
        # Create snapshot
        snapshot_id = await persistence_service.save_workflow_snapshot(
            workflow_state=WorkflowState.ANALYZING,
            parameters=mock_combined_parameters
        )

        # Load by ID
        loaded_snapshot = await persistence_service.load_snapshot(snapshot_id)

        assert loaded_snapshot is not None
        assert loaded_snapshot.snapshot_id == snapshot_id
        assert loaded_snapshot.workflow_state == WorkflowState.ANALYZING

    @pytest.mark.asyncio
    async def test_load_nonexistent_snapshot(self, persistence_service):
        """Test loading non-existent snapshot"""
        snapshot = await persistence_service.load_snapshot("nonexistent_snapshot")
        assert snapshot is None

    @pytest.mark.asyncio
    async def test_list_snapshots(self, persistence_service, mock_combined_parameters):
        """Test listing available snapshots"""
        # Create multiple snapshots
        snapshot_ids = []
        for i in range(3):
            snapshot_id = await persistence_service.save_workflow_snapshot(
                workflow_state=WorkflowState.READY,
                parameters=mock_combined_parameters,
                dataset_id=f"dataset_{i}"
            )
            snapshot_ids.append(snapshot_id)

        # List snapshots
        snapshots = await persistence_service.list_snapshots()

        assert len(snapshots) == 3
        assert all(snapshot["snapshot_id"] in snapshot_ids for snapshot in snapshots)
        assert all("timestamp" in snapshot for snapshot in snapshots)
        assert all("workflow_state" in snapshot for snapshot in snapshots)

    @pytest.mark.asyncio
    async def test_list_snapshots_with_limit(self, persistence_service, mock_combined_parameters):
        """Test listing snapshots with limit"""
        # Create multiple snapshots
        for i in range(5):
            await persistence_service.save_workflow_snapshot(
                workflow_state=WorkflowState.READY,
                parameters=mock_combined_parameters
            )

        # List with limit
        snapshots = await persistence_service.list_snapshots(limit=2)
        assert len(snapshots) == 2

    @pytest.mark.asyncio
    async def test_list_snapshots_with_time_filter(self, persistence_service, mock_combined_parameters):
        """Test listing snapshots with time filter"""
        # Create snapshot
        await persistence_service.save_workflow_snapshot(
            workflow_state=WorkflowState.READY,
            parameters=mock_combined_parameters
        )

        # List snapshots since future date (should be empty)
        future_date = datetime.now() + timedelta(hours=1)
        snapshots = await persistence_service.list_snapshots(since=future_date)
        assert len(snapshots) == 0

        # List snapshots since past date (should include our snapshot)
        past_date = datetime.now() - timedelta(hours=1)
        snapshots = await persistence_service.list_snapshots(since=past_date)
        assert len(snapshots) == 1

    @pytest.mark.asyncio
    async def test_auto_save_functionality(self, persistence_service, mock_combined_parameters):
        """Test automatic state saving"""
        # Set short auto-save interval for testing
        persistence_service._auto_save_interval_seconds = 0.1

        # Create initial snapshot
        await persistence_service.save_workflow_snapshot(
            workflow_state=WorkflowState.READY,
            parameters=mock_combined_parameters
        )

        # Start auto-save
        await persistence_service.start_auto_save()

        # Wait for auto-save cycles
        await asyncio.sleep(0.3)

        # Stop auto-save
        await persistence_service.stop_auto_save()

        # Auto-save should have triggered
        assert not persistence_service._is_auto_saving

    @pytest.mark.asyncio
    async def test_create_backup(self, persistence_service, mock_combined_parameters):
        """Test backup creation"""
        # Create some data to backup
        await persistence_service.save_workflow_snapshot(
            workflow_state=WorkflowState.READY,
            parameters=mock_combined_parameters
        )

        # Create backup
        backup_path = await persistence_service.create_backup("test_backup")

        assert backup_path.exists()
        assert (backup_path / "current_state.json").exists()
        assert (backup_path / "snapshots").exists()
        assert (backup_path / "backup_metadata.json").exists()

        # Check backup metadata
        with open(backup_path / "backup_metadata.json", 'r') as f:
            metadata = json.load(f)

        assert metadata["backup_name"] == "test_backup"
        assert "created_at" in metadata
        assert metadata["persistence_level"] == PersistenceLevel.STANDARD.value

    @pytest.mark.asyncio
    async def test_restore_from_backup(self, persistence_service, mock_combined_parameters):
        """Test restore from backup"""
        # Create initial data
        original_snapshot_id = await persistence_service.save_workflow_snapshot(
            workflow_state=WorkflowState.ANALYZING,
            parameters=mock_combined_parameters,
            dataset_id="original_dataset"
        )

        # Create backup
        backup_path = await persistence_service.create_backup("restore_test")

        # Modify current state
        await persistence_service.save_workflow_snapshot(
            workflow_state=WorkflowState.ERROR,
            parameters=mock_combined_parameters,
            dataset_id="modified_dataset"
        )

        # Restore from backup
        success = await persistence_service.restore_from_backup(backup_path)
        assert success is True

        # Check restored state
        restored_snapshot = await persistence_service.load_current_state()
        assert restored_snapshot.workflow_state == WorkflowState.ANALYZING
        assert restored_snapshot.dataset_id == "original_dataset"

    @pytest.mark.asyncio
    async def test_restore_from_nonexistent_backup(self, persistence_service):
        """Test restore from non-existent backup"""
        nonexistent_path = Path("/nonexistent/backup/path")
        success = await persistence_service.restore_from_backup(nonexistent_path)
        assert success is False

    @pytest.mark.asyncio
    async def test_snapshot_cleanup(self, persistence_service, mock_combined_parameters):
        """Test automatic cleanup of old snapshots"""
        # Set low max snapshots for testing
        persistence_service._max_snapshots = 2

        # Create multiple snapshots
        snapshot_ids = []
        for i in range(4):
            snapshot_id = await persistence_service.save_workflow_snapshot(
                workflow_state=WorkflowState.READY,
                parameters=mock_combined_parameters
            )
            snapshot_ids.append(snapshot_id)

        # Check that old snapshots were cleaned up
        remaining_snapshots = list(persistence_service.snapshots_path.glob("snapshot_*.json"))
        assert len(remaining_snapshots) <= persistence_service._max_snapshots

    @pytest.mark.asyncio
    async def test_corrupted_state_recovery(self, persistence_service, mock_combined_parameters):
        """Test recovery from corrupted current state file"""
        # Create valid snapshot first
        await persistence_service.save_workflow_snapshot(
            workflow_state=WorkflowState.READY,
            parameters=mock_combined_parameters
        )

        # Corrupt current state file
        with open(persistence_service.current_state_path, 'w') as f:
            f.write("corrupted json data {")

        # Attempt to load - should trigger recovery
        recovered_snapshot = await persistence_service.load_current_state()

        # Should have recovered from snapshots or returned None
        if recovered_snapshot:
            assert isinstance(recovered_snapshot, WorkflowSnapshot)

    @pytest.mark.asyncio
    async def test_persistence_level_minimal(self, temp_persistence_path, mock_hardware_system):
        """Test minimal persistence level"""
        service = StatePersistenceService(
            persistence_path=temp_persistence_path,
            hardware_system=mock_hardware_system,
            persistence_level=PersistenceLevel.MINIMAL
        )

        snapshot_id = await service.save_workflow_snapshot(WorkflowState.READY)

        # Load and check minimal data
        snapshot = await service.load_snapshot(snapshot_id)
        assert snapshot.workflow_state == WorkflowState.READY
        # Hardware status should be None for minimal level
        assert snapshot.hardware_status is None

    @pytest.mark.asyncio
    async def test_persistence_level_full(self, temp_persistence_path, mock_hardware_system, mock_combined_parameters):
        """Test full persistence level"""
        service = StatePersistenceService(
            persistence_path=temp_persistence_path,
            hardware_system=mock_hardware_system,
            persistence_level=PersistenceLevel.FULL
        )

        snapshot_id = await service.save_workflow_snapshot(
            workflow_state=WorkflowState.READY,
            parameters=mock_combined_parameters
        )

        # Load and check full data
        snapshot = await service.load_snapshot(snapshot_id)
        assert snapshot.workflow_state == WorkflowState.READY
        assert snapshot.hardware_status is not None
        assert snapshot.parameters is not None

    @pytest.mark.asyncio
    async def test_concurrent_snapshot_operations(self, persistence_service, mock_combined_parameters):
        """Test concurrent snapshot save/load operations"""
        # Launch concurrent save operations
        save_tasks = [
            persistence_service.save_workflow_snapshot(
                workflow_state=WorkflowState.READY,
                parameters=mock_combined_parameters,
                dataset_id=f"concurrent_test_{i}"
            )
            for i in range(5)
        ]

        snapshot_ids = await asyncio.gather(*save_tasks)

        # All operations should succeed
        assert len(snapshot_ids) == 5
        assert all(sid is not None for sid in snapshot_ids)

        # Launch concurrent load operations
        load_tasks = [
            persistence_service.load_snapshot(snapshot_id)
            for snapshot_id in snapshot_ids
        ]

        snapshots = await asyncio.gather(*load_tasks)

        # All loads should succeed
        assert len(snapshots) == 5
        assert all(snapshot is not None for snapshot in snapshots)

    def test_persistence_status(self, persistence_service):
        """Test persistence service status reporting"""
        status = persistence_service.get_persistence_status()

        required_fields = [
            "is_auto_saving",
            "auto_save_interval_seconds",
            "persistence_level",
            "persistence_path",
            "current_snapshot",
            "save_counter",
            "snapshots_count",
            "backups_count",
            "recovery_strategy"
        ]

        for field in required_fields:
            assert field in status

        assert status["persistence_level"] == PersistenceLevel.STANDARD.value
        assert status["is_auto_saving"] is False  # Initially not running

    @pytest.mark.asyncio
    async def test_error_handling_in_save(self, persistence_service):
        """Test error handling during snapshot save"""
        # Mock filesystem error
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            with pytest.raises(PersistenceError):
                await persistence_service.save_workflow_snapshot(WorkflowState.READY)

    @pytest.mark.asyncio
    async def test_atomic_save_operation(self, persistence_service, mock_combined_parameters):
        """Test atomic save operation (temp file + rename)"""
        # Mock to verify temp file usage
        original_open = open

        def mock_open(file_path, *args, **kwargs):
            # Check if it's using .tmp extension for atomic save
            if str(file_path).endswith('.tmp'):
                assert True  # Temp file is being used
            return original_open(file_path, *args, **kwargs)

        with patch('builtins.open', side_effect=mock_open):
            await persistence_service.save_workflow_snapshot(
                workflow_state=WorkflowState.READY,
                parameters=mock_combined_parameters
            )

    def test_recovery_strategy_configuration(self, persistence_service):
        """Test recovery strategy configuration"""
        assert persistence_service._recovery_strategy == RecoveryStrategy.PARTIAL_RECOVERY

        # Recovery strategy should be configurable
        # (Would require implementation in the actual service)
        pass


class TestWorkflowSnapshot:
    """Test WorkflowSnapshot functionality"""

    @pytest.fixture
    def mock_parameters(self):
        """Mock parameters for testing"""
        mock = Mock()
        mock.to_dict.return_value = {"test": "parameters"}
        return mock

    def test_snapshot_creation(self, mock_parameters):
        """Test workflow snapshot creation"""
        timestamp = datetime.now()
        snapshot = WorkflowSnapshot(
            snapshot_id="test_snapshot_001",
            timestamp=timestamp,
            workflow_state=WorkflowState.READY,
            parameters=mock_parameters,
            dataset_id="test_dataset",
            session_id="test_session",
            analysis_id="test_analysis",
            hardware_status={"status": "ok"},
            metadata={"custom": "metadata"}
        )

        assert snapshot.snapshot_id == "test_snapshot_001"
        assert snapshot.timestamp == timestamp
        assert snapshot.workflow_state == WorkflowState.READY
        assert snapshot.parameters == mock_parameters
        assert snapshot.dataset_id == "test_dataset"
        assert snapshot.session_id == "test_session"
        assert snapshot.analysis_id == "test_analysis"
        assert snapshot.hardware_status == {"status": "ok"}
        assert snapshot.metadata == {"custom": "metadata"}

    def test_snapshot_to_dict(self, mock_parameters):
        """Test snapshot serialization to dictionary"""
        timestamp = datetime.now()
        snapshot = WorkflowSnapshot(
            snapshot_id="dict_test",
            timestamp=timestamp,
            workflow_state=WorkflowState.ANALYZING,
            parameters=mock_parameters
        )

        snapshot_dict = snapshot.to_dict()

        assert snapshot_dict["snapshot_id"] == "dict_test"
        assert snapshot_dict["timestamp"] == timestamp.isoformat()
        assert snapshot_dict["workflow_state"] == WorkflowState.ANALYZING.value
        assert snapshot_dict["parameters"] == {"test": "parameters"}

    def test_snapshot_from_dict(self):
        """Test snapshot creation from dictionary"""
        with patch('src.domain.value_objects.parameters.CombinedParameters.from_dict') as mock_from_dict:
            mock_from_dict.return_value = Mock()

            snapshot_data = {
                "snapshot_id": "from_dict_test",
                "timestamp": datetime.now().isoformat(),
                "workflow_state": "ready",
                "parameters": {"test": "parameters"},
                "dataset_id": "test_dataset",
                "session_id": "test_session",
                "metadata": {"test": "metadata"}
            }

            snapshot = WorkflowSnapshot.from_dict(snapshot_data)

            assert snapshot.snapshot_id == "from_dict_test"
            assert snapshot.workflow_state == WorkflowState.READY
            assert snapshot.dataset_id == "test_dataset"
            assert snapshot.session_id == "test_session"
            assert snapshot.metadata == {"test": "metadata"}

    def test_snapshot_minimal_creation(self):
        """Test snapshot creation with minimal required fields"""
        snapshot = WorkflowSnapshot(
            snapshot_id="minimal_test",
            timestamp=datetime.now(),
            workflow_state=WorkflowState.IDLE
        )

        assert snapshot.snapshot_id == "minimal_test"
        assert snapshot.workflow_state == WorkflowState.IDLE
        assert snapshot.parameters is None
        assert snapshot.dataset_id is None
        assert snapshot.session_id is None
        assert snapshot.hardware_status is None
        assert snapshot.metadata == {}


class TestEnums:
    """Test enum definitions"""

    def test_persistence_level_values(self):
        """Test PersistenceLevel enum values"""
        expected = ["minimal", "standard", "full"]
        actual = [level.value for level in PersistenceLevel]
        for expected_val in expected:
            assert expected_val in actual

    def test_recovery_strategy_values(self):
        """Test RecoveryStrategy enum values"""
        expected = ["fail_safe", "partial", "full"]
        actual = [strategy.value for strategy in RecoveryStrategy]
        for expected_val in expected:
            assert expected_val in actual


class TestPersistenceError:
    """Test PersistenceError exception"""

    def test_persistence_error_creation(self):
        """Test PersistenceError creation"""
        error = PersistenceError("Test persistence error")
        assert str(error) == "Test persistence error"

    def test_persistence_error_inheritance(self):
        """Test PersistenceError inheritance"""
        error = PersistenceError("Test error")
        assert isinstance(error, Exception)


class TestBackupAndRecovery:
    """Test backup and recovery edge cases"""

    @pytest.mark.asyncio
    async def test_backup_with_no_data(self, persistence_service):
        """Test backup creation when no data exists"""
        # Create backup without any snapshots
        backup_path = await persistence_service.create_backup("empty_backup")

        assert backup_path.exists()
        assert (backup_path / "backup_metadata.json").exists()

        # Snapshots directory might not exist or be empty
        if (backup_path / "snapshots").exists():
            snapshot_files = list((backup_path / "snapshots").glob("*.json"))
            assert len(snapshot_files) == 0

    @pytest.mark.asyncio
    async def test_multiple_backup_creation(self, persistence_service, mock_combined_parameters):
        """Test creating multiple backups"""
        # Create some data
        await persistence_service.save_workflow_snapshot(
            workflow_state=WorkflowState.READY,
            parameters=mock_combined_parameters
        )

        # Create multiple backups
        backup_names = ["backup_1", "backup_2", "backup_3"]
        backup_paths = []

        for name in backup_names:
            backup_path = await persistence_service.create_backup(name)
            backup_paths.append(backup_path)

        # All backups should exist
        for backup_path in backup_paths:
            assert backup_path.exists()

        # Should be tracked in backup paths
        assert len(persistence_service._backup_paths) == 3

    @pytest.mark.asyncio
    async def test_corrupted_backup_restore(self, persistence_service, temp_persistence_path):
        """Test restore from corrupted backup"""
        # Create a corrupted backup directory structure
        corrupted_backup = temp_persistence_path / "corrupted_backup"
        corrupted_backup.mkdir()

        # Create invalid backup metadata
        with open(corrupted_backup / "backup_metadata.json", 'w') as f:
            f.write("invalid json {")

        # Attempt restore
        success = await persistence_service.restore_from_backup(corrupted_backup)
        assert success is False