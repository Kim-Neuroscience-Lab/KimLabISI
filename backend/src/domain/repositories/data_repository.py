"""
Domain Data Repository Interfaces

Abstract interfaces for data storage following clean architecture principles.
These interfaces belong in the domain layer and are implemented by infrastructure.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple, Union
from pathlib import Path

from ..value_objects.parameters import CombinedParameters

# Domain-appropriate type aliases instead of numpy
DataType = Union[str, int, float]  # Generic data type specification
ShapeType = Tuple[int, ...]       # Shape specification
FrameData = List[List[List[float]]]  # Multi-dimensional frame data


class DataRepositoryInterface(ABC):
    """Abstract interface for scientific data storage"""

    @abstractmethod
    async def create_dataset(self,
                           session_id: str,
                           dataset_name: str,
                           shape: ShapeType,
                           dtype: str,  # String representation of data type
                           parameters: Optional[CombinedParameters] = None,
                           metadata: Optional[Dict[str, Any]] = None) -> Path:
        """Create a new dataset for storing imaging data"""
        pass

    @abstractmethod
    async def write_frames(self,
                          session_id: str,
                          dataset_name: str,
                          frames: FrameData,
                          frame_indices: Optional[List[int]] = None) -> None:
        """Write frame data to dataset"""
        pass

    @abstractmethod
    async def read_frames(self,
                         session_id: str,
                         dataset_name: str,
                         frame_indices: Optional[List[int]] = None) -> FrameData:
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