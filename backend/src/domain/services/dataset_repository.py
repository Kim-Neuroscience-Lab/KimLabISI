"""
Dataset Repository Domain Services for ISI Macroscope System

Simple repository services for managing persistence and retrieval of
stimulus datasets, acquisition sessions, and analysis results.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
import shutil


from src.domain.entities.dataset import StimulusDataset, AcquisitionSession, AnalysisResult
from .error_handler import DomainError, ErrorHandlingService, ISIDomainError


class SortOrder(Enum):
    """Sorting options for repository queries"""

    NEWEST_FIRST = "newest_first"
    OLDEST_FIRST = "oldest_first"
    NAME_ASC = "name_ascending"
    NAME_DESC = "name_descending"
    SIZE_ASC = "size_ascending"
    SIZE_DESC = "size_descending"


class DatasetMetadata:
    """Lightweight metadata for dataset discovery"""

    def __init__(
        self,
        dataset_id: str,
        file_path: Path,
        creation_timestamp: datetime,
        file_size_bytes: int,
        metadata: Dict[str, Any],
    ):
        self.dataset_id = dataset_id
        self.file_path = file_path
        self.creation_timestamp = creation_timestamp
        self.file_size_bytes = file_size_bytes
        self.metadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "dataset_id": self.dataset_id,
            "file_path": str(self.file_path),
            "creation_timestamp": self.creation_timestamp.isoformat(),
            "file_size_bytes": self.file_size_bytes,
            "metadata": self.metadata,
        }


class StimulusDatasetRepository:
    """Repository for managing stimulus dataset persistence"""

    def __init__(self, base_path: Path, error_handler: Optional[ErrorHandlingService] = None):
        self.base_path = Path(base_path)
        self.error_handler = error_handler or ErrorHandlingService()
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        self.datasets_path = self.base_path / "stimulus_datasets"
        self.datasets_path.mkdir(parents=True, exist_ok=True)

        # Repository initialization tracking delegated to application layer

    def save(self, dataset: StimulusDataset) -> Path:
        """
        Save stimulus dataset to repository

        Args:
            dataset: Stimulus dataset to save

        Returns:
            Path where dataset was saved
        """
        try:
            # Create dataset-specific directory
            dataset_dir = self.datasets_path / dataset.dataset_id
            dataset_dir.mkdir(parents=True, exist_ok=True)

            # Save dataset
            dataset_file = dataset_dir / "dataset.json"
            dataset.save_to_file(dataset_file)

            # Dataset save tracking delegated to application layer
            return dataset_file

        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="REPOSITORY_ERROR",
                custom_message="Failed to save stimulus dataset",
                dataset_id=dataset.dataset_id,
                operation="save",
            )
            raise ISIDomainError(domain_error)

    def load(self, dataset_id: str) -> StimulusDataset:
        """
        Load stimulus dataset from repository

        Args:
            dataset_id: ID of dataset to load

        Returns:
            Loaded stimulus dataset
        """
        try:
            dataset_file = self.datasets_path / dataset_id / "dataset.json"

            if not dataset_file.exists():
                domain_error = self.error_handler.create_error(
                    error_code="REPOSITORY_ERROR",
                    custom_message=f"Dataset {dataset_id} not found",
                    dataset_id=dataset_id,
                    operation="load",
                )
                raise ISIDomainError(domain_error)

            dataset = StimulusDataset.load_from_file(dataset_file)
            # Dataset loaded successfully
            return dataset

        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="REPOSITORY_ERROR",
                custom_message="Failed to load dataset",
                dataset_id=dataset_id,
                operation="load",
            )
            raise ISIDomainError(domain_error)

    def list_datasets(
        self, sort_order: SortOrder = SortOrder.NEWEST_FIRST, limit: Optional[int] = None
    ) -> List[DatasetMetadata]:
        """
        List available stimulus datasets

        Args:
            sort_order: How to sort the results
            limit: Maximum number of results to return

        Returns:
            List of dataset metadata objects
        """
        try:
            datasets = []

            for dataset_dir in self.datasets_path.iterdir():
                if not dataset_dir.is_dir():
                    continue

                dataset_file = dataset_dir / "dataset.json"
                if not dataset_file.exists():
                    continue

                try:
                    # Load basic metadata without full dataset
                    with open(dataset_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    metadata = DatasetMetadata(
                        dataset_id=data["dataset_id"],
                        file_path=dataset_file,
                        creation_timestamp=datetime.fromisoformat(data["creation_timestamp"]),
                        file_size_bytes=dataset_file.stat().st_size,
                        metadata={
                            "stimulus_type": data["parameters"]["stimulus_params"]["stimulus_type"],
                            "directions": data["parameters"]["stimulus_params"]["directions"],
                            "status": data["status"],
                            "file_count": len(data.get("data_files", {})),
                        },
                    )
                    datasets.append(metadata)

                except Exception as e:
                    # Error reading dataset metadata - skip this file
                    continue

            # Sort datasets
            datasets = self._sort_datasets(datasets, sort_order)

            # Apply limit
            if limit is not None:
                datasets = datasets[:limit]

            # Dataset listing completed
            return datasets

        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="REPOSITORY_ERROR",
                custom_message="Failed to list datasets",
                operation="list",
            )
            raise ISIDomainError(domain_error)

    def delete(self, dataset_id: str) -> bool:
        """
        Delete stimulus dataset from repository

        Args:
            dataset_id: ID of dataset to delete

        Returns:
            True if deleted successfully
        """
        try:
            dataset_dir = self.datasets_path / dataset_id

            if not dataset_dir.exists():
                # Dataset not found for deletion
                return False

            # Remove dataset directory and all contents
            import shutil

            shutil.rmtree(dataset_dir)

            # Dataset deleted successfully
            return True

        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="REPOSITORY_ERROR",
                custom_message="Failed to delete dataset",
                dataset_id=dataset_id,
                operation="delete",
            )
            raise ISIDomainError(domain_error)

    def exists(self, dataset_id: str) -> bool:
        """Check if dataset exists in repository"""
        dataset_file = self.datasets_path / dataset_id / "dataset.json"
        return dataset_file.exists()

    def get_storage_info(self) -> Dict[str, Any]:
        """Get repository storage information"""
        total_size = 0
        dataset_count = 0

        for dataset_dir in self.datasets_path.iterdir():
            if dataset_dir.is_dir():
                dataset_count += 1
                for file_path in dataset_dir.rglob("*"):
                    if file_path.is_file():
                        total_size += file_path.stat().st_size

        return {
            "base_path": str(self.base_path),
            "dataset_count": dataset_count,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }

    def _sort_datasets(
        self, datasets: List[DatasetMetadata], sort_order: SortOrder
    ) -> List[DatasetMetadata]:
        """Sort dataset list by specified order"""
        if sort_order == SortOrder.NEWEST_FIRST:
            return sorted(datasets, key=lambda d: d.creation_timestamp, reverse=True)
        elif sort_order == SortOrder.OLDEST_FIRST:
            return sorted(datasets, key=lambda d: d.creation_timestamp, reverse=False)
        elif sort_order == SortOrder.NAME_ASC:
            return sorted(datasets, key=lambda d: d.dataset_id)
        elif sort_order == SortOrder.NAME_DESC:
            return sorted(datasets, key=lambda d: d.dataset_id, reverse=True)
        elif sort_order == SortOrder.SIZE_ASC:
            return sorted(datasets, key=lambda d: d.file_size_bytes)
        elif sort_order == SortOrder.SIZE_DESC:
            return sorted(datasets, key=lambda d: d.file_size_bytes, reverse=True)
        else:
            return datasets


class AcquisitionSessionRepository:
    """Repository for managing acquisition session persistence"""

    def __init__(self, base_path: Path, error_handler: Optional[ErrorHandlingService] = None):
        self.base_path = Path(base_path)
        self.error_handler = error_handler or ErrorHandlingService()
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        self.sessions_path = self.base_path / "acquisition_sessions"
        self.sessions_path.mkdir(parents=True, exist_ok=True)

        # Repository initialization tracking delegated to application layer

    def save(self, session: AcquisitionSession) -> Path:
        """Save acquisition session to repository"""
        try:
            # Create session-specific directory
            session_dir = self.sessions_path / session.session_id
            session_dir.mkdir(parents=True, exist_ok=True)

            # Save session
            session_file = session_dir / "session.json"
            session.save_to_file(session_file)

            # Session saved successfully
            return session_file

        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="REPOSITORY_ERROR",
                custom_message="Failed to save session",
                session_id=session.session_id,
                operation="save",
            )
            raise ISIDomainError(domain_error)

    def load(self, session_id: str) -> AcquisitionSession:
        """Load acquisition session from repository"""
        try:
            session_file = self.sessions_path / session_id / "session.json"

            if not session_file.exists():
                domain_error = self.error_handler.create_error(
                    error_code="REPOSITORY_ERROR",
                    custom_message=f"Session {session_id} not found",
                    session_id=session_id,
                    operation="load",
                )
                raise ISIDomainError(domain_error)

            session = AcquisitionSession.load_from_file(session_file)
            # Session loaded successfully
            return session

        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="REPOSITORY_ERROR",
                custom_message="Failed to load session",
                session_id=session_id,
                operation="load",
            )
            raise ISIDomainError(domain_error)

    def list_sessions(
        self, sort_order: SortOrder = SortOrder.NEWEST_FIRST, limit: Optional[int] = None
    ) -> List[DatasetMetadata]:
        """List available acquisition sessions"""
        try:
            sessions = []

            for session_dir in self.sessions_path.iterdir():
                if not session_dir.is_dir():
                    continue

                session_file = session_dir / "session.json"
                if not session_file.exists():
                    continue

                try:
                    # Load basic metadata
                    with open(session_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    metadata = DatasetMetadata(
                        dataset_id=data["session_id"],
                        file_path=session_file,
                        creation_timestamp=datetime.fromisoformat(data["start_timestamp"]),
                        file_size_bytes=session_file.stat().st_size,
                        metadata={
                            "frame_count": data.get("frame_count", 0),
                            "duration_s": data.get("duration_s", 0),
                            "status": data["status"],
                            "quality_score": data.get("quality_score", 0),
                            "dataset_id": data.get("dataset_id"),
                        },
                    )
                    sessions.append(metadata)

                except Exception as e:
                    logger.warning(f"Error reading session metadata from {session_file}: {e}")
                    continue

            # Sort sessions
            sessions = self._sort_datasets(sessions, sort_order)

            # Apply limit
            if limit is not None:
                sessions = sessions[:limit]

            # Sessions listed successfully
            return sessions

        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="REPOSITORY_ERROR",
                custom_message="Failed to list sessions",
                operation="list",
            )
            raise ISIDomainError(domain_error)

    def delete(self, session_id: str) -> bool:
        """Delete acquisition session from repository"""
        try:
            session_dir = self.sessions_path / session_id

            if not session_dir.exists():
                # Session not found for deletion
                return False

            # Remove session directory and all contents
            import shutil

            shutil.rmtree(session_dir)

            # Session deleted successfully
            return True

        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="REPOSITORY_ERROR",
                custom_message="Failed to delete session",
                session_id=session_id,
                operation="delete",
            )
            raise ISIDomainError(domain_error)

    def exists(self, session_id: str) -> bool:
        """Check if session exists in repository"""
        session_file = self.sessions_path / session_id / "session.json"
        return session_file.exists()

    def _sort_datasets(
        self, datasets: List[DatasetMetadata], sort_order: SortOrder
    ) -> List[DatasetMetadata]:
        """Sort dataset list by specified order"""
        if sort_order == SortOrder.NEWEST_FIRST:
            return sorted(datasets, key=lambda d: d.creation_timestamp, reverse=True)
        elif sort_order == SortOrder.OLDEST_FIRST:
            return sorted(datasets, key=lambda d: d.creation_timestamp, reverse=False)
        elif sort_order == SortOrder.NAME_ASC:
            return sorted(datasets, key=lambda d: d.dataset_id)
        elif sort_order == SortOrder.NAME_DESC:
            return sorted(datasets, key=lambda d: d.dataset_id, reverse=True)
        elif sort_order == SortOrder.SIZE_ASC:
            return sorted(datasets, key=lambda d: d.file_size_bytes)
        elif sort_order == SortOrder.SIZE_DESC:
            return sorted(datasets, key=lambda d: d.file_size_bytes, reverse=True)
        else:
            return datasets


class AnalysisResultRepository:
    """Repository for managing analysis result persistence"""

    def __init__(self, base_path: Path, error_handler: Optional[ErrorHandlingService] = None):
        self.base_path = Path(base_path)
        self.error_handler = error_handler or ErrorHandlingService()
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        self.analyses_path = self.base_path / "analysis_results"
        self.analyses_path.mkdir(parents=True, exist_ok=True)

        # Repository initialization tracking delegated to application layer

    def save(self, analysis: AnalysisResult) -> Path:
        """Save analysis result to repository"""
        try:
            # Create analysis-specific directory
            analysis_dir = self.analyses_path / analysis.analysis_id
            analysis_dir.mkdir(parents=True, exist_ok=True)

            # Save analysis
            analysis_file = analysis_dir / "analysis.json"
            analysis.save_to_file(analysis_file)

            # Analysis result saved successfully
            return analysis_file

        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="REPOSITORY_ERROR",
                custom_message="Failed to save analysis",
                analysis_id=analysis.analysis_id,
                operation="save",
            )
            raise ISIDomainError(domain_error)

    def load(self, analysis_id: str) -> AnalysisResult:
        """Load analysis result from repository"""
        try:
            analysis_file = self.analyses_path / analysis_id / "analysis.json"

            if not analysis_file.exists():
                domain_error = self.error_handler.create_error(
                    error_code="REPOSITORY_ERROR",
                    custom_message=f"Analysis {analysis_id} not found",
                    analysis_id=analysis_id,
                    operation="load",
                )
                raise ISIDomainError(domain_error)

            analysis = AnalysisResult.load_from_file(analysis_file)
            # Analysis result loaded successfully
            return analysis

        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="REPOSITORY_ERROR",
                custom_message="Failed to load analysis",
                analysis_id=analysis_id,
                operation="load",
            )
            raise ISIDomainError(domain_error)

    def list_analyses(
        self, sort_order: SortOrder = SortOrder.NEWEST_FIRST, limit: Optional[int] = None
    ) -> List[DatasetMetadata]:
        """List available analysis results"""
        try:
            analyses = []

            for analysis_dir in self.analyses_path.iterdir():
                if not analysis_dir.is_dir():
                    continue

                analysis_file = analysis_dir / "analysis.json"
                if not analysis_file.exists():
                    continue

                try:
                    # Load basic metadata
                    with open(analysis_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    metadata = DatasetMetadata(
                        dataset_id=data["analysis_id"],
                        file_path=analysis_file,
                        creation_timestamp=datetime.fromisoformat(data["creation_timestamp"]),
                        file_size_bytes=analysis_file.stat().st_size,
                        metadata={
                            "session_id": data.get("session_id"),
                            "dataset_id": data.get("dataset_id"),
                            "status": data["status"],
                            "quality_score": data.get("quality_score", 0),
                            "processing_duration_s": data.get("metadata", {}).get(
                                "processing_duration_s", 0
                            ),
                        },
                    )
                    analyses.append(metadata)

                except Exception as e:
                    # Error reading analysis metadata - skip this file
                    continue

            # Sort analyses
            analyses = self._sort_datasets(analyses, sort_order)

            # Apply limit
            if limit is not None:
                analyses = analyses[:limit]

            # Analysis results listed successfully
            return analyses

        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="REPOSITORY_ERROR",
                custom_message="Failed to list analyses",
                operation="list",
            )
            raise ISIDomainError(domain_error)

    def delete(self, analysis_id: str) -> bool:
        """Delete analysis result from repository"""
        try:
            analysis_dir = self.analyses_path / analysis_id

            if not analysis_dir.exists():
                # Analysis not found for deletion
                return False

            shutil.rmtree(analysis_dir)

            # Analysis result deleted successfully
            return True

        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="REPOSITORY_ERROR",
                custom_message="Failed to delete analysis",
                analysis_id=analysis_id,
                operation="delete",
            )
            raise ISIDomainError(domain_error)

    def exists(self, analysis_id: str) -> bool:
        """Check if analysis exists in repository"""
        analysis_file = self.analyses_path / analysis_id / "analysis.json"
        return analysis_file.exists()

    def find_by_session(self, session_id: str) -> List[DatasetMetadata]:
        """Find all analyses for a specific session"""
        all_analyses = self.list_analyses()
        return [
            analysis
            for analysis in all_analyses
            if analysis.metadata.get("session_id") == session_id
        ]

    def find_by_dataset(self, dataset_id: str) -> List[DatasetMetadata]:
        """Find all analyses for a specific dataset"""
        all_analyses = self.list_analyses()
        return [
            analysis
            for analysis in all_analyses
            if analysis.metadata.get("dataset_id") == dataset_id
        ]

    def _sort_datasets(
        self, datasets: List[DatasetMetadata], sort_order: SortOrder
    ) -> List[DatasetMetadata]:
        """Sort dataset list by specified order"""
        if sort_order == SortOrder.NEWEST_FIRST:
            return sorted(datasets, key=lambda d: d.creation_timestamp, reverse=True)
        elif sort_order == SortOrder.OLDEST_FIRST:
            return sorted(datasets, key=lambda d: d.creation_timestamp, reverse=False)
        elif sort_order == SortOrder.NAME_ASC:
            return sorted(datasets, key=lambda d: d.dataset_id)
        elif sort_order == SortOrder.NAME_DESC:
            return sorted(datasets, key=lambda d: d.dataset_id, reverse=True)
        elif sort_order == SortOrder.SIZE_ASC:
            return sorted(datasets, key=lambda d: d.file_size_bytes)
        elif sort_order == SortOrder.SIZE_DESC:
            return sorted(datasets, key=lambda d: d.file_size_bytes, reverse=True)
        else:
            return datasets


class DatasetRepositoryManager:
    """Central manager for all dataset repositories"""

    def __init__(self, base_path: Path, error_handler: Optional[ErrorHandlingService] = None):
        self.base_path = Path(base_path)
        self.error_handler = error_handler or ErrorHandlingService()

        # Initialize individual repositories with shared error handler
        self.stimulus_datasets = StimulusDatasetRepository(base_path, error_handler)
        self.acquisition_sessions = AcquisitionSessionRepository(base_path, error_handler)
        self.analysis_results = AnalysisResultRepository(base_path, error_handler)

        # Repository manager initialization tracking delegated to application layer

    def get_system_overview(self) -> Dict[str, Any]:
        """Get overview of all repositories"""
        try:
            stimulus_info = self.stimulus_datasets.get_storage_info()

            # Get session and analysis counts
            session_count = len(
                self.acquisition_sessions.list_sessions(limit=1000)
            )  # Reasonable limit
            analysis_count = len(self.analysis_results.list_analyses(limit=1000))

            return {
                "base_path": str(self.base_path),
                "stimulus_datasets": {
                    "count": stimulus_info["dataset_count"],
                    "total_size_mb": stimulus_info["total_size_mb"],
                },
                "acquisition_sessions": {"count": session_count},
                "analysis_results": {"count": analysis_count},
                "last_updated": datetime.now().isoformat(),
            }

        except Exception as e:
            domain_error = self.error_handler.handle_exception(
                exception=e,
                error_code="REPOSITORY_ERROR",
                custom_message="Failed to get system overview",
                operation="system_overview",
            )
            raise ISIDomainError(domain_error)

    def cleanup_orphaned_data(self) -> Dict[str, int]:
        """Clean up orphaned data (analyses without sessions, etc.)"""
        try:
            cleanup_stats = {"orphaned_analyses_removed": 0, "invalid_files_removed": 0}

            # Get all sessions for reference
            session_ids = {
                metadata.dataset_id for metadata in self.acquisition_sessions.list_sessions()
            }

            # Check analyses for orphaned references
            all_analyses = self.analysis_results.list_analyses()

            for analysis_metadata in all_analyses:
                session_id = analysis_metadata.metadata.get("session_id")
                if session_id and session_id not in session_ids:
                    # Removing orphaned analysis
                    if self.analysis_results.delete(analysis_metadata.dataset_id):
                        cleanup_stats["orphaned_analyses_removed"] += 1

            # Cleanup completed successfully
            return cleanup_stats

        except Exception as e:
            domain_error: DomainError = self.error_handler.handle_exception(
                exception=e,
                error_code="REPOSITORY_ERROR",
                custom_message="Cleanup failed",
                operation="cleanup",
            )
            raise ISIDomainError(domain_error)
