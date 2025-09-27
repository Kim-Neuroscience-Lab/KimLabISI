"""Timing Interface - Abstract High-Precision Timing Interface"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum


class TimingStatus(Enum):
    """Timing system status enumeration"""
    INACTIVE = "inactive"
    ACTIVE = "active"
    SYNCHRONIZED = "synchronized"
    ERROR = "error"


class TimingInterface(ABC):
    """Abstract interface for high-precision timing"""

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize timing system"""
        pass

    @abstractmethod
    async def get_status(self) -> TimingStatus:
        """Get current timing status"""
        pass

    @abstractmethod
    async def start_timing(self, parameters: Dict[str, Any]) -> bool:
        """Start timing sequence"""
        pass

    @abstractmethod
    async def stop_timing(self) -> bool:
        """Stop timing sequence"""
        pass

    @abstractmethod
    async def get_precision(self) -> float:
        """Get timing precision in microseconds"""
        pass

    @abstractmethod
    async def synchronize(self) -> bool:
        """Synchronize with external timing source"""
        pass