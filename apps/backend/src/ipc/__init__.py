"""Inter-process communication infrastructure."""

from .channels import MultiChannelIPC, ChannelType, ChannelConfig
from .shared_memory import SharedMemoryService

__all__ = [
    "MultiChannelIPC",
    "ChannelType",
    "ChannelConfig",
    "SharedMemoryService",
]
