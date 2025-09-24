"""
State Persistence Service

Manages workflow state persistence and recovery to ensure system state
survives application restarts and unexpected shutdowns.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import logging
import json
import asyncio
import shutil

from ...domain.value_objects.workflow_state import WorkflowState
from ...domain.value_objects.parameters import CombinedParameters
from ...domain.entities.dataset import StimulusDataset, AcquisitionSession, AnalysisResult
from ...domain.entities.hardware import HardwareSystem


logger = logging.getLogger(__name__)


class PersistenceLevel(Enum):
    """Levels of state persistence"""
    MINIMAL = "minimal"      # Only critical workflow state
    STANDARD = "standard"    # Workflow state + current data references
    FULL = "full"           # Complete system snapshot


class RecoveryStrategy(Enum):
    """Recovery strategies for corrupted state"""
    FAIL_SAFE = "fail_safe"         # Return to safe initial state
    PARTIAL_RECOVERY = "partial"     # Recover what's possible
    FULL_RECOVERY = "full"          # Attempt complete restoration


class PersistenceError(Exception):
    """Raised when state persistence encounters errors"""
    pass


class WorkflowSnapshot:
    """Complete workflow state snapshot"""

    def __init__(
        self,
        snapshot_id: str,
        timestamp: datetime,
        workflow_state: WorkflowState,
        parameters: Optional[CombinedParameters] = None,
        dataset_id: Optional[str] = None,
        session_id: Optional[str] = None,
        analysis_id: Optional[str] = None,
        hardware_status: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.snapshot_id = snapshot_id
        self.timestamp = timestamp
        self.workflow_state = workflow_state
        self.parameters = parameters
        self.dataset_id = dataset_id
        self.session_id = session_id
        self.analysis_id = analysis_id
        self.hardware_status = hardware_status
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp.isoformat(),
            "workflow_state": self.workflow_state.value,
            "parameters": self.parameters.to_dict() if self.parameters else None,
            "dataset_id": self.dataset_id,
            "session_id": self.session_id,
            "analysis_id": self.analysis_id,
            "hardware_status": self.hardware_status,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WorkflowSnapshot:
        """Create from dictionary"""
        return cls(
            snapshot_id=data["snapshot_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            workflow_state=WorkflowState(data["workflow_state"]),
            parameters=CombinedParameters.from_dict(data["parameters"]) if data.get("parameters") else None,
            dataset_id=data.get("dataset_id"),
            session_id=data.get("session_id"),
            analysis_id=data.get("analysis_id"),
            hardware_status=data.get("hardware_status"),
            metadata=data.get("metadata", {})
        )


class StatePersistenceService:
    """
    Application service for workflow state persistence and recovery

    Ensures system state survives restarts and provides recovery
    mechanisms for unexpected shutdowns or corruption.
    """

    def __init__(
        self,
        persistence_path: Path,
        hardware_system: HardwareSystem,
        persistence_level: PersistenceLevel = PersistenceLevel.STANDARD
    ):
        self.persistence_path = Path(persistence_path)
        self.hardware_system = hardware_system
        self.persistence_level = persistence_level

        # Create persistence directories
        self.persistence_path.mkdir(parents=True, exist_ok=True)
        self.snapshots_path = self.persistence_path / "snapshots"
        self.snapshots_path.mkdir(exist_ok=True)
        self.current_state_path = self.persistence_path / "current_state.json"
        self.recovery_path = self.persistence_path / "recovery"
        self.recovery_path.mkdir(exist_ok=True)

        # Configuration
        self._auto_save_interval_seconds = 30.0
        self._max_snapshots = 50
        self._snapshot_retention_days = 7
        self._is_auto_saving = False

        # Current state tracking
        self._current_snapshot: Optional[WorkflowSnapshot] = None
        self._last_save_time: Optional[datetime] = None
        self._save_counter = 0

        # Recovery configuration
        self._recovery_strategy = RecoveryStrategy.PARTIAL_RECOVERY
        self._backup_paths: List[Path] = []

        logger.info(f"State persistence service initialized at {self.persistence_path}")

    async def start_auto_save(self):
        """Start automatic state saving"""

        if self._is_auto_saving:
            logger.warning("Auto-save already running")
            return

        self._is_auto_saving = True

        # Start auto-save loop
        asyncio.create_task(self._auto_save_loop())

        logger.info(f"Auto-save started with {self._auto_save_interval_seconds}s interval")

    async def stop_auto_save(self):
        """Stop automatic state saving"""

        self._is_auto_saving = False

        # Save final state
        if self._current_snapshot:
            await self.save_current_state()

        logger.info("Auto-save stopped")

    async def save_workflow_snapshot(
        self,
        workflow_state: WorkflowState,
        parameters: Optional[CombinedParameters] = None,
        dataset_id: Optional[str] = None,
        session_id: Optional[str] = None,
        analysis_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Save complete workflow snapshot"""

        try:
            # Create snapshot
            snapshot_id = f"snapshot_{int(datetime.now().timestamp())}"

            # Collect hardware status if needed
            hardware_status = None
            if self.persistence_level in [PersistenceLevel.STANDARD, PersistenceLevel.FULL]:
                hardware_status = self.hardware_system.get_system_status_summary()

            snapshot = WorkflowSnapshot(
                snapshot_id=snapshot_id,
                timestamp=datetime.now(),
                workflow_state=workflow_state,
                parameters=parameters,
                dataset_id=dataset_id,
                session_id=session_id,
                analysis_id=analysis_id,
                hardware_status=hardware_status,
                metadata=metadata
            )

            # Save snapshot to file
            snapshot_file = self.snapshots_path / f"{snapshot_id}.json"
            with open(snapshot_file, 'w') as f:
                json.dump(snapshot.to_dict(), f, indent=2)

            # Update current snapshot
            self._current_snapshot = snapshot
            self._last_save_time = datetime.now()
            self._save_counter += 1

            # Save as current state
            await self.save_current_state()

            # Cleanup old snapshots
            await self._cleanup_old_snapshots()

            logger.debug(f"Saved workflow snapshot: {snapshot_id}")
            return snapshot_id

        except Exception as e:
            logger.exception("Error saving workflow snapshot")
            raise PersistenceError(f"Failed to save snapshot: {str(e)}")

    async def save_current_state(self):
        """Save current state as the active state file"""

        if not self._current_snapshot:
            logger.warning("No current snapshot to save")
            return

        try:
            # Create atomic save (write to temp file, then rename)
            temp_file = self.current_state_path.with_suffix('.tmp')

            with open(temp_file, 'w') as f:
                json.dump(self._current_snapshot.to_dict(), f, indent=2)

            # Atomic move
            temp_file.replace(self.current_state_path)

            logger.debug("Current state saved")

        except Exception as e:
            logger.exception("Error saving current state")
            raise PersistenceError(f"Failed to save current state: {str(e)}")

    async def load_current_state(self) -> Optional[WorkflowSnapshot]:
        """Load the most recent workflow state"""

        try:
            if not self.current_state_path.exists():
                logger.info("No current state file found")
                return None

            with open(self.current_state_path, 'r') as f:
                data = json.load(f)

            snapshot = WorkflowSnapshot.from_dict(data)
            self._current_snapshot = snapshot

            logger.info(f"Loaded current state: {snapshot.workflow_state.value} from {snapshot.timestamp}")
            return snapshot

        except Exception as e:
            logger.exception("Error loading current state")

            # Try recovery from snapshots
            recovery_snapshot = await self._attempt_recovery_from_snapshots()
            if recovery_snapshot:
                return recovery_snapshot

            logger.error("Failed to load or recover current state")
            return None

    async def load_snapshot(self, snapshot_id: str) -> Optional[WorkflowSnapshot]:
        """Load specific snapshot by ID"""

        try:
            snapshot_file = self.snapshots_path / f"{snapshot_id}.json"

            if not snapshot_file.exists():
                logger.warning(f"Snapshot file not found: {snapshot_id}")
                return None

            with open(snapshot_file, 'r') as f:
                data = json.load(f)

            snapshot = WorkflowSnapshot.from_dict(data)

            logger.debug(f"Loaded snapshot: {snapshot_id}")
            return snapshot

        except Exception as e:
            logger.exception(f"Error loading snapshot {snapshot_id}")
            return None

    async def list_snapshots(
        self,
        limit: Optional[int] = None,
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """List available snapshots with metadata"""

        try:
            snapshots = []

            for snapshot_file in self.snapshots_path.glob("snapshot_*.json"):
                try:
                    with open(snapshot_file, 'r') as f:
                        data = json.load(f)

                    timestamp = datetime.fromisoformat(data["timestamp"])

                    # Filter by time if specified
                    if since and timestamp < since:
                        continue

                    snapshot_info = {
                        "snapshot_id": data["snapshot_id"],
                        "timestamp": data["timestamp"],
                        "workflow_state": data["workflow_state"],
                        "has_parameters": data.get("parameters") is not None,
                        "dataset_id": data.get("dataset_id"),
                        "session_id": data.get("session_id"),
                        "analysis_id": data.get("analysis_id"),
                        "file_size": snapshot_file.stat().st_size
                    }

                    snapshots.append(snapshot_info)

                except Exception as e:
                    logger.warning(f"Error reading snapshot file {snapshot_file}: {e}")
                    continue

            # Sort by timestamp (newest first)
            snapshots.sort(key=lambda s: s["timestamp"], reverse=True)

            # Apply limit
            if limit:
                snapshots = snapshots[:limit]

            logger.debug(f"Listed {len(snapshots)} snapshots")
            return snapshots

        except Exception as e:
            logger.exception("Error listing snapshots")
            return []

    async def create_backup(self, backup_name: str) -> Path:
        """Create full backup of persistence data"""

        try:
            backup_path = self.recovery_path / f"backup_{backup_name}_{int(datetime.now().timestamp())}"
            backup_path.mkdir()

            # Copy all persistence data
            if self.current_state_path.exists():
                shutil.copy2(self.current_state_path, backup_path / "current_state.json")

            snapshots_backup = backup_path / "snapshots"
            if self.snapshots_path.exists():
                shutil.copytree(self.snapshots_path, snapshots_backup)

            # Create backup metadata
            backup_metadata = {
                "backup_name": backup_name,
                "created_at": datetime.now().isoformat(),
                "files_count": len(list(backup_path.rglob("*.json"))),
                "persistence_level": self.persistence_level.value
            }

            with open(backup_path / "backup_metadata.json", 'w') as f:
                json.dump(backup_metadata, f, indent=2)

            self._backup_paths.append(backup_path)

            logger.info(f"Created backup: {backup_path}")
            return backup_path

        except Exception as e:
            logger.exception("Error creating backup")
            raise PersistenceError(f"Failed to create backup: {str(e)}")

    async def restore_from_backup(self, backup_path: Path) -> bool:
        """Restore state from backup"""

        try:
            if not backup_path.exists():
                logger.error(f"Backup path not found: {backup_path}")
                return False

            # Stop auto-save during restore
            was_auto_saving = self._is_auto_saving
            if was_auto_saving:
                await self.stop_auto_save()

            # Create safety backup of current state
            safety_backup = await self.create_backup("pre_restore_safety")

            try:
                # Restore current state
                backup_current_state = backup_path / "current_state.json"
                if backup_current_state.exists():
                    shutil.copy2(backup_current_state, self.current_state_path)

                # Restore snapshots
                backup_snapshots = backup_path / "snapshots"
                if backup_snapshots.exists():
                    # Clear existing snapshots
                    if self.snapshots_path.exists():
                        shutil.rmtree(self.snapshots_path)

                    # Copy backup snapshots
                    shutil.copytree(backup_snapshots, self.snapshots_path)

                # Reload current state
                await self.load_current_state()

                # Restart auto-save if it was running
                if was_auto_saving:
                    await self.start_auto_save()

                logger.info(f"Successfully restored from backup: {backup_path}")
                return True

            except Exception as restore_error:
                logger.exception("Error during restore, attempting rollback")

                # Attempt to restore from safety backup
                try:
                    await self.restore_from_backup(safety_backup)
                    logger.info("Rollback successful")
                except Exception:
                    logger.exception("Rollback failed - system may be in inconsistent state")

                raise restore_error

        except Exception as e:
            logger.exception("Error restoring from backup")
            return False

    async def _auto_save_loop(self):
        """Automatic state saving loop"""

        logger.debug("Starting auto-save loop")

        while self._is_auto_saving:
            try:
                # Save current state if we have one
                if self._current_snapshot:
                    await self.save_current_state()

                # Wait for next save
                await asyncio.sleep(self._auto_save_interval_seconds)

            except Exception as e:
                logger.exception(f"Error in auto-save loop: {e}")
                await asyncio.sleep(1.0)  # Brief pause on error

        logger.debug("Auto-save loop terminated")

    async def _cleanup_old_snapshots(self):
        """Clean up old snapshots based on retention policy"""

        try:
            # Get all snapshot files
            snapshot_files = list(self.snapshots_path.glob("snapshot_*.json"))

            # Sort by modification time (oldest first)
            snapshot_files.sort(key=lambda f: f.stat().st_mtime)

            # Remove excess snapshots
            if len(snapshot_files) > self._max_snapshots:
                excess_count = len(snapshot_files) - self._max_snapshots
                for f in snapshot_files[:excess_count]:
                    f.unlink()
                    logger.debug(f"Removed excess snapshot: {f.name}")

            # Remove snapshots older than retention period
            cutoff_time = datetime.now() - timedelta(days=self._snapshot_retention_days)
            cutoff_timestamp = cutoff_time.timestamp()

            for f in snapshot_files:
                if f.stat().st_mtime < cutoff_timestamp:
                    f.unlink()
                    logger.debug(f"Removed expired snapshot: {f.name}")

        except Exception as e:
            logger.warning(f"Error cleaning up old snapshots: {e}")

    async def _attempt_recovery_from_snapshots(self) -> Optional[WorkflowSnapshot]:
        """Attempt to recover from available snapshots"""

        try:
            logger.info("Attempting recovery from snapshots")

            snapshots = await self.list_snapshots(limit=10)  # Try last 10 snapshots

            for snapshot_info in snapshots:
                try:
                    snapshot = await self.load_snapshot(snapshot_info["snapshot_id"])
                    if snapshot:
                        logger.info(f"Recovery successful using snapshot: {snapshot.snapshot_id}")
                        self._current_snapshot = snapshot
                        return snapshot

                except Exception as e:
                    logger.warning(f"Failed to recover from snapshot {snapshot_info['snapshot_id']}: {e}")
                    continue

            logger.error("No valid snapshots found for recovery")
            return None

        except Exception as e:
            logger.exception("Error during snapshot recovery")
            return None

    def get_persistence_status(self) -> Dict[str, Any]:
        """Get persistence service status"""

        return {
            "is_auto_saving": self._is_auto_saving,
            "auto_save_interval_seconds": self._auto_save_interval_seconds,
            "persistence_level": self.persistence_level.value,
            "persistence_path": str(self.persistence_path),
            "current_snapshot": {
                "exists": self._current_snapshot is not None,
                "snapshot_id": self._current_snapshot.snapshot_id if self._current_snapshot else None,
                "timestamp": self._current_snapshot.timestamp.isoformat() if self._current_snapshot else None,
                "workflow_state": self._current_snapshot.workflow_state.value if self._current_snapshot else None
            },
            "last_save_time": self._last_save_time.isoformat() if self._last_save_time else None,
            "save_counter": self._save_counter,
            "snapshots_count": len(list(self.snapshots_path.glob("snapshot_*.json"))),
            "backups_count": len(self._backup_paths),
            "recovery_strategy": self._recovery_strategy.value
        }