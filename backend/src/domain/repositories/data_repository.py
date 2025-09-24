"""
Domain Data Repository Interfaces

Abstract interfaces for data storage following clean architecture principles.
These interfaces belong in the domain layer and are implemented by infrastructure.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import numpy as np

from ..value_objects.parameters import CombinedParameters


class DataRepositoryInterface(ABC):
    """Abstract interface for scientific data storage"""

    @abstractmethod
    async def create_dataset(self,
                           session_id: str,
                           dataset_name: str,
                           shape: Tuple[int, ...],
                           dtype: np.dtype,
                           parameters: Optional[CombinedParameters] = None,
                           metadata: Optional[Dict[str, Any]] = None) -> Path:
        """Create a new dataset for storing imaging data"""
        pass

    @abstractmethod
    async def write_frames(self,
                          session_id: str,
                          dataset_name: str,
                          frames: np.ndarray,
                          frame_indices: Optional[np.ndarray] = None) -> None:
        """Write frame data to dataset"""
        pass

    @abstractmethod
    async def read_frames(self,
                         session_id: str,
                         dataset_name: str,
                         frame_indices: Optional[np.ndarray] = None) -> np.ndarray:
        """Read frame data from dataset"""
        pass

    @abstractmethod
    async def get_dataset_info(self, session_id: str, dataset_name: str) -> Dict[str, Any]:
        """Get dataset information and metadata"""
        pass

    @abstractmethod
    async def store_analysis_results(self,
                                   session_id: str,
                                   analysis_name: str,
                                   results: Dict[str, Any],
                                   parameters: Optional[CombinedParameters] = None) -> None:
        """Store analysis results"""
        pass