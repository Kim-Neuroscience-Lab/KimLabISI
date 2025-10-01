"""Service registry for backend components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .config import AppConfig
    from .multi_channel_ipc import MultiChannelIPC
    from .shared_memory_stream import SharedMemoryService
    from .startup_coordinator import StartupCoordinator
    from .health_monitor import SystemHealthMonitor
    from .parameter_manager import ParameterManager
    from .stimulus_manager import StimulusGenerator
    from .main import ISIMacroscopeBackend


@dataclass
class ServiceRegistry:
    """Resolved backend services."""

    config: "AppConfig"
    ipc: "MultiChannelIPC"
    shared_memory: "SharedMemoryService"
    parameter_manager: "ParameterManager"
    startup_coordinator: "StartupCoordinator"
    health_monitor: "SystemHealthMonitor"
    stimulus_generator_provider: Callable[[], "StimulusGenerator"]

    backend: Optional["ISIMacroscopeBackend"] = None


_registry: Optional[ServiceRegistry] = None


def set_registry(registry: ServiceRegistry) -> None:
    global _registry
    _registry = registry


def get_services() -> ServiceRegistry:
    if _registry is None:
        raise RuntimeError("Service registry not initialised")
    return _registry


def clear_registry() -> None:
    global _registry
    _registry = None
