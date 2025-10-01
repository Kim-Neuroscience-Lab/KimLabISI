"""Backend configuration primitives.

All runtime configuration is expressed as immutable dataclasses so that
components receive explicit settings during initialization. This keeps the
startup sequence deterministic and avoids hidden globals or implicit defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IPCConfig:
    """ZeroMQ channel configuration."""

    transport: str
    health_port: int
    sync_port: int


@dataclass(frozen=True)
class SharedMemoryConfig:
    """Shared memory streaming configuration."""

    stream_name: str
    buffer_size_mb: int
    metadata_port: int


@dataclass(frozen=True)
class ParameterStoreConfig:
    """Parameter persistence configuration."""

    file_path: Path


@dataclass(frozen=True)
class LoggingConfig:
    """Logging configuration."""

    log_file: Path


@dataclass(frozen=True)
class AppConfig:
    """Composite application configuration."""

    ipc: IPCConfig
    shared_memory: SharedMemoryConfig
    parameters: ParameterStoreConfig
    logging: LoggingConfig

    @staticmethod
    def default() -> "AppConfig":
        """Build the default configuration for the application."""

        project_root = Path(__file__).resolve().parents[4]

        return AppConfig(
            ipc=IPCConfig(
                transport="tcp",
                health_port=5555,
                sync_port=5558,
            ),
            shared_memory=SharedMemoryConfig(
                stream_name="stimulus_stream",
                buffer_size_mb=100,
                metadata_port=5557,
            ),
            parameters=ParameterStoreConfig(
                file_path=project_root / "isi_parameters.json",
            ),
            logging=LoggingConfig(
                log_file=project_root / "isi_macroscope.log",
            ),
        )
