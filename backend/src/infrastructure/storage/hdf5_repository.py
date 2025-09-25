"""
HDF5 Data Repository - Scientific Data Storage Foundation

This module implements HDF5-based data storage for the ISI Macroscope Control System.
Handles storage of imaging data, metadata, and analysis results with proper
scientific data management practices.

Key Features:
- Efficient storage of large imaging datasets
- Metadata preservation and linking
- Parameter tracking and reproducibility
- Compression and chunking optimization
- Thread-safe operations
"""

import h5py
import numpy as np
import logging
import asyncio
from typing import Dict, Any, Optional, List, Union, Tuple
from pathlib import Path
from datetime import datetime
import json
import threading
from concurrent.futures import ThreadPoolExecutor

from domain.value_objects.parameters import CombinedParameters
from domain.entities.parameters import ParameterManager
from domain.repositories.data_repository import DataRepositoryInterface

logger = logging.getLogger(__name__)


class HDF5StorageError(Exception):
    """Errors related to HDF5 storage operations"""
    pass


class HDF5Repository(DataRepositoryInterface):
    """
    HDF5-based repository for scientific data storage

    Provides high-level interface for storing and retrieving imaging data,
    metadata, and analysis results with proper scientific data management.
    """

    def __init__(self, storage_directory: Path, max_workers: int = 4):
        """
        Initialize HDF5 repository

        Args:
            storage_directory: Directory for HDF5 files
            max_workers: Maximum number of worker threads for I/O operations
        """
        self.storage_directory = Path(storage_directory)
        self.storage_directory.mkdir(parents=True, exist_ok=True)

        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()

        logger.info(f"HDF5Repository initialized: {storage_directory}")

    def __del__(self):
        """Clean up thread pool on destruction"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)

    async def create_dataset(self,
                           session_id: str,
                           dataset_name: str,
                           shape: Tuple[int, ...],
                           dtype: np.dtype = np.float32,
                           parameters: Optional[CombinedParameters] = None,
                           metadata: Optional[Dict[str, Any]] = None,
                           compression: str = 'gzip',
                           chunks: Optional[Tuple[int, ...]] = None) -> Path:
        """
        Create a new HDF5 dataset for imaging data

        Args:
            session_id: Unique session identifier
            dataset_name: Name for the dataset
            shape: Shape of the dataset (frames, height, width)
            dtype: NumPy data type for the dataset
            parameters: Combined parameters used for acquisition
            metadata: Additional metadata to store
            compression: Compression algorithm ('gzip', 'lzf', 'szip', None)
            chunks: Chunk shape for the dataset (None for auto)

        Returns:
            Path to the created HDF5 file
        """
        file_path = self._get_session_file_path(session_id)

        def _create_dataset():
            nonlocal chunks  # Allow modification of chunks parameter
            with h5py.File(file_path, 'a') as f:
                # Create dataset group if it doesn't exist
                if dataset_name in f:
                    raise HDF5StorageError(f"Dataset '{dataset_name}' already exists in session {session_id}")

                # Determine optimal chunking if not provided
                if chunks is None:
                    chunks = self._calculate_optimal_chunks(shape, dtype)

                # Create dataset with compression
                dataset = f.create_dataset(
                    dataset_name,
                    shape=shape,
                    dtype=dtype,
                    compression=compression,
                    chunks=chunks,
                    shuffle=True,  # Improves compression
                    fletcher32=True  # Error detection
                )

                # Store metadata
                if metadata:
                    for key, value in metadata.items():
                        dataset.attrs[key] = self._serialize_attribute(value)

                # Store parameters if provided
                if parameters:
                    self._store_parameters(dataset, parameters)

                # Store creation timestamp
                dataset.attrs['created_timestamp'] = datetime.now().isoformat()
                dataset.attrs['dataset_version'] = '1.0'

                logger.info(f"Created dataset '{dataset_name}' in session {session_id}: {shape}, {dtype}")

        await asyncio.get_event_loop().run_in_executor(self.executor, _create_dataset)
        return file_path

    async def write_frames(self,
                          session_id: str,
                          dataset_name: str,
                          frames: np.ndarray,
                          frame_indices: Optional[Union[int, slice, np.ndarray]] = None) -> None:
        """
        Write image frames to an existing dataset

        Args:
            session_id: Session identifier
            dataset_name: Name of the dataset
            frames: Frame data to write (can be single frame or multiple frames)
            frame_indices: Frame indices to write to (None for append mode)
        """
        file_path = self._get_session_file_path(session_id)

        def _write_frames():
            with h5py.File(file_path, 'a') as f:
                if dataset_name not in f:
                    raise HDF5StorageError(f"Dataset '{dataset_name}' not found in session {session_id}")

                dataset = f[dataset_name]

                # Handle different indexing scenarios
                if frame_indices is None:
                    # Append mode - find next available index
                    current_size = dataset.shape[0]
                    if frames.ndim == 2:  # Single frame
                        dataset.resize((current_size + 1,) + dataset.shape[1:])
                        dataset[current_size] = frames
                    else:  # Multiple frames
                        new_size = current_size + frames.shape[0]
                        dataset.resize((new_size,) + dataset.shape[1:])
                        dataset[current_size:new_size] = frames
                else:
                    # Direct indexing
                    dataset[frame_indices] = frames

                # Update last modified timestamp
                dataset.attrs['last_modified'] = datetime.now().isoformat()

        await asyncio.get_event_loop().run_in_executor(self.executor, _write_frames)

    async def read_frames(self,
                         session_id: str,
                         dataset_name: str,
                         frame_indices: Optional[Union[int, slice, np.ndarray]] = None) -> np.ndarray:
        """
        Read image frames from a dataset

        Args:
            session_id: Session identifier
            dataset_name: Name of the dataset
            frame_indices: Frame indices to read (None for all frames)

        Returns:
            Frame data as numpy array
        """
        file_path = self._get_session_file_path(session_id)

        def _read_frames():
            with h5py.File(file_path, 'r') as f:
                if dataset_name not in f:
                    raise HDF5StorageError(f"Dataset '{dataset_name}' not found in session {session_id}")

                dataset = f[dataset_name]

                if frame_indices is None:
                    return dataset[:]
                else:
                    return dataset[frame_indices]

        return await asyncio.get_event_loop().run_in_executor(self.executor, _read_frames)

    async def get_dataset_info(self, session_id: str, dataset_name: str) -> Dict[str, Any]:
        """
        Get information about a dataset

        Args:
            session_id: Session identifier
            dataset_name: Name of the dataset

        Returns:
            Dictionary with dataset information
        """
        file_path = self._get_session_file_path(session_id)

        def _get_info():
            with h5py.File(file_path, 'r') as f:
                if dataset_name not in f:
                    raise HDF5StorageError(f"Dataset '{dataset_name}' not found in session {session_id}")

                dataset = f[dataset_name]

                info = {
                    'shape': dataset.shape,
                    'dtype': str(dataset.dtype),
                    'compression': dataset.compression,
                    'chunks': dataset.chunks,
                    'size_bytes': dataset.size * dataset.dtype.itemsize,
                    'compression_ratio': dataset.compression_opts if dataset.compression else None,
                }

                # Add attributes
                info['attributes'] = dict(dataset.attrs)

                return info

        return await asyncio.get_event_loop().run_in_executor(self.executor, _get_info)

    async def store_analysis_results(self,
                                   session_id: str,
                                   analysis_name: str,
                                   results: Dict[str, Any],
                                   parameters: Optional[CombinedParameters] = None) -> None:
        """
        Store analysis results in the HDF5 file

        Args:
            session_id: Session identifier
            analysis_name: Name for the analysis results
            results: Dictionary of analysis results
            parameters: Parameters used for analysis
        """
        file_path = self._get_session_file_path(session_id)

        def _store_analysis():
            with h5py.File(file_path, 'a') as f:
                # Create analysis group
                analysis_group_name = f"analysis/{analysis_name}"
                if analysis_group_name in f:
                    del f[analysis_group_name]  # Replace existing

                group = f.create_group(analysis_group_name)

                # Store results
                for key, value in results.items():
                    if isinstance(value, np.ndarray):
                        group.create_dataset(key, data=value, compression='gzip')
                    else:
                        group.attrs[key] = self._serialize_attribute(value)

                # Store parameters if provided
                if parameters:
                    self._store_parameters(group, parameters)

                # Store analysis timestamp
                group.attrs['analysis_timestamp'] = datetime.now().isoformat()

                logger.info(f"Stored analysis results '{analysis_name}' for session {session_id}")

        await asyncio.get_event_loop().run_in_executor(self.executor, _store_analysis)

    async def list_sessions(self) -> List[str]:
        """
        List all available sessions

        Returns:
            List of session IDs
        """
        def _list_sessions():
            sessions = []
            for file_path in self.storage_directory.glob("*.h5"):
                # Extract session ID from filename
                session_id = file_path.stem
                sessions.append(session_id)
            return sorted(sessions)

        return await asyncio.get_event_loop().run_in_executor(self.executor, _list_sessions)

    async def list_datasets(self, session_id: str) -> List[str]:
        """
        List all datasets in a session

        Args:
            session_id: Session identifier

        Returns:
            List of dataset names
        """
        file_path = self._get_session_file_path(session_id)

        def _list_datasets():
            datasets = []
            with h5py.File(file_path, 'r') as f:
                def visit_func(name, obj):
                    if isinstance(obj, h5py.Dataset) and not name.startswith('analysis/'):
                        datasets.append(name)

                f.visititems(visit_func)
            return sorted(datasets)

        return await asyncio.get_event_loop().run_in_executor(self.executor, _list_datasets)

    async def get_session_metadata(self, session_id: str) -> Dict[str, Any]:
        """
        Get metadata for a session

        Args:
            session_id: Session identifier

        Returns:
            Session metadata dictionary
        """
        file_path = self._get_session_file_path(session_id)

        def _get_metadata():
            with h5py.File(file_path, 'r') as f:
                # Get file-level attributes
                metadata = dict(f.attrs)

                # Add file statistics
                metadata['file_size_bytes'] = file_path.stat().st_size
                metadata['datasets'] = list(f.keys())

                return metadata

        return await asyncio.get_event_loop().run_in_executor(self.executor, _get_metadata)

    def _get_session_file_path(self, session_id: str) -> Path:
        """Get the file path for a session"""
        return self.storage_directory / f"{session_id}.h5"

    def _calculate_optimal_chunks(self, shape: Tuple[int, ...], dtype: np.dtype) -> Tuple[int, ...]:
        """
        Calculate optimal chunk size for HDF5 dataset

        Aims for chunks around 1MB for good I/O performance
        """
        target_chunk_bytes = 1024 * 1024  # 1MB
        # Handle dtype properly - convert to numpy dtype if needed
        if not isinstance(dtype, np.dtype):
            dtype = np.dtype(dtype)
        element_bytes = dtype.itemsize

        if len(shape) == 3:  # (frames, height, width)
            frame_bytes = shape[1] * shape[2] * element_bytes
            frames_per_chunk = max(1, target_chunk_bytes // frame_bytes)
            return (min(frames_per_chunk, shape[0]), shape[1], shape[2])
        elif len(shape) == 2:  # (height, width)
            return shape
        else:
            # Default chunking for other shapes
            return tuple(min(s, 64) for s in shape)

    def _serialize_attribute(self, value: Any) -> Any:
        """Serialize attribute value for HDF5 storage"""
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        elif isinstance(value, np.ndarray):
            return value.tolist()
        elif hasattr(value, 'model_dump'):  # Pydantic model
            return json.dumps(value.model_dump())
        else:
            return value

    def _store_parameters(self, obj: Union[h5py.Dataset, h5py.Group], parameters: CombinedParameters) -> None:
        """Store combined parameters as attributes"""
        param_dict = parameters.model_dump()

        # Store parameter hashes for validation
        obj.attrs['generation_hash'] = parameters.generation_hash
        obj.attrs['combined_hash'] = parameters.combined_hash
        obj.attrs['parameter_source'] = parameters.parameter_source if isinstance(parameters.parameter_source, str) else parameters.parameter_source.value
        obj.attrs['parameter_version'] = parameters.version

        # Store full parameters as JSON (with proper serialization)
        obj.attrs['parameters'] = self._serialize_attribute(param_dict)


class HDF5SessionManager:
    """
    High-level session management for HDF5 data storage

    Provides session-based workflow for managing experimental data
    """

    def __init__(self, repository: HDF5Repository):
        """Initialize session manager with HDF5 repository"""
        self.repository = repository
        self._active_sessions: Dict[str, Dict[str, Any]] = {}

    async def create_session(self,
                           session_id: str,
                           parameters: CombinedParameters,
                           metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Create a new experimental session

        Args:
            session_id: Unique session identifier
            parameters: Combined parameters for the session
            metadata: Additional session metadata
        """
        if session_id in self._active_sessions:
            raise HDF5StorageError(f"Session '{session_id}' is already active")

        # Create session metadata
        session_metadata = {
            'session_id': session_id,
            'created_timestamp': datetime.now().isoformat(),
            'parameter_set': parameters.model_dump(),
            'generation_hash': parameters.generation_hash,
            'combined_hash': parameters.combined_hash,
        }

        if metadata:
            session_metadata.update(metadata)

        # Store in repository
        file_path = self.repository._get_session_file_path(session_id)

        def _create_session_file():
            with h5py.File(file_path, 'w') as f:
                # Store session-level metadata
                for key, value in session_metadata.items():
                    # Handle special cases for HDF5 attribute storage
                    if key == 'parameter_set':
                        f.attrs[key] = json.dumps(value)
                    else:
                        f.attrs[key] = self.repository._serialize_attribute(value)

                # Create standard groups
                f.create_group('imaging')
                f.create_group('analysis')
                f.create_group('metadata')

        await asyncio.get_event_loop().run_in_executor(
            self.repository.executor, _create_session_file
        )

        # Track active session
        self._active_sessions[session_id] = session_metadata

        logger.info(f"Created session '{session_id}' with parameters hash {parameters.generation_hash[:8]}")

    async def close_session(self, session_id: str) -> None:
        """Close an active session"""
        if session_id in self._active_sessions:
            del self._active_sessions[session_id]
            logger.info(f"Closed session '{session_id}'")

    def get_active_sessions(self) -> List[str]:
        """Get list of currently active session IDs"""
        return list(self._active_sessions.keys())

    async def validate_session_parameters(self, session_id: str, parameters: CombinedParameters) -> bool:
        """
        Validate that parameters match the session

        Args:
            session_id: Session identifier
            parameters: Parameters to validate

        Returns:
            True if parameters match session parameters
        """
        try:
            session_metadata = await self.repository.get_session_metadata(session_id)
            stored_hash = session_metadata.get('generation_hash', '')
            return stored_hash == parameters.generation_hash
        except Exception as e:
            logger.warning(f"Failed to validate session parameters: {e}")
            return False