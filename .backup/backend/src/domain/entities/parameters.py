"""
Parameter Store Interface - Domain Layer

Abstract parameter storage interface for dependency inversion.
Defines the contract that infrastructure implementations must follow.
"""

from typing import List
from abc import ABC, abstractmethod


class ParameterStore(ABC):
    """Abstract base class for parameter storage implementations"""

    @abstractmethod
    def load_parameters(self, parameter_set_id: str) -> "CombinedParameters":
        """Load parameters by ID"""

    @abstractmethod
    def save_parameters(self, parameters: "CombinedParameters", parameter_set_id: str) -> None:
        """Save parameters with ID"""

    @abstractmethod
    def list_parameter_sets(self) -> List[str]:
        """List available parameter set IDs"""

    @abstractmethod
    def delete_parameter_set(self, parameter_set_id: str) -> None:
        """Delete a parameter set"""


