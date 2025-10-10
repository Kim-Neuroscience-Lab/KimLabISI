"""System health monitoring service.

Monitors CPU, memory, GPU, disk usage and reports health metrics via IPC.
All dependencies injected via constructor - NO service locator.
"""

from __future__ import annotations

import logging
import os
import platform
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

import psutil

from ipc.channels import MultiChannelIPC

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Standardized health status values."""

    ONLINE = "online"  # System is fully operational
    DEGRADED = "degraded"  # System operational but with reduced performance
    OFFLINE = "offline"  # System is not available
    ERROR = "error"  # System encountered an error
    UNKNOWN = "unknown"  # Health status not yet determined


@dataclass
class SystemMetrics:
    """System resource usage metrics."""

    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_free_gb: float
    thread_count: int
    process_count: int
    uptime_seconds: float
    gpu_available: bool
    gpu_memory_used_mb: Optional[float] = None
    gpu_memory_total_mb: Optional[float] = None
    gpu_utilization_percent: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "memory_used_mb": self.memory_used_mb,
            "memory_available_mb": self.memory_available_mb,
            "disk_usage_percent": self.disk_usage_percent,
            "disk_free_gb": self.disk_free_gb,
            "thread_count": self.thread_count,
            "process_count": self.process_count,
            "uptime_seconds": self.uptime_seconds,
            "gpu_available": self.gpu_available,
            "gpu_memory_used_mb": self.gpu_memory_used_mb,
            "gpu_memory_total_mb": self.gpu_memory_total_mb,
            "gpu_utilization_percent": self.gpu_utilization_percent,
        }


@dataclass
class HealthReport:
    """Complete system health report."""

    status: HealthStatus
    timestamp: float
    metrics: SystemMetrics
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "status": self.status.value,
            "timestamp": self.timestamp,
            "metrics": self.metrics.to_dict(),
            "warnings": self.warnings,
            "errors": self.errors,
            "is_healthy": self.status == HealthStatus.ONLINE,
        }


class HealthMonitor:
    """System health monitoring service.

    Monitors CPU, memory, GPU, disk usage and reports via IPC.
    All dependencies injected via constructor.
    """

    def __init__(
        self,
        ipc: MultiChannelIPC,
        check_interval: float = 5.0,
        cpu_warning_threshold: float = 80.0,
        memory_warning_threshold: float = 85.0,
        disk_warning_threshold: float = 90.0,
    ):
        """Initialize health monitor.

        Args:
            ipc: IPC channel for reporting health metrics
            check_interval: Seconds between health checks
            cpu_warning_threshold: CPU usage % to trigger warning
            memory_warning_threshold: Memory usage % to trigger warning
            disk_warning_threshold: Disk usage % to trigger warning
        """
        self.ipc = ipc
        self.check_interval = check_interval
        self.cpu_warning_threshold = cpu_warning_threshold
        self.memory_warning_threshold = memory_warning_threshold
        self.disk_warning_threshold = disk_warning_threshold

        self._monitoring = False
        self._thread: Optional[threading.Thread] = None
        self._start_time = time.time()
        self._lock = threading.RLock()

        logger.info(
            "HealthMonitor initialized (check_interval=%.1fs, "
            "cpu_warn=%.0f%%, mem_warn=%.0f%%, disk_warn=%.0f%%)",
            check_interval,
            cpu_warning_threshold,
            memory_warning_threshold,
            disk_warning_threshold,
        )

    def start_monitoring(self) -> None:
        """Start health monitoring in background thread."""
        with self._lock:
            if self._monitoring:
                logger.warning("Health monitoring already running")
                return

            self._monitoring = True
            self._thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True,
                name="HealthMonitor",
            )
            self._thread.start()
            logger.info("Health monitoring started")

    def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        with self._lock:
            if not self._monitoring:
                logger.warning("Health monitoring not running")
                return

            self._monitoring = False
            if self._thread is not None:
                self._thread.join(timeout=2.0)
                self._thread = None
            logger.info("Health monitoring stopped")

    def get_health_report(self) -> HealthReport:
        """Get current health metrics and status.

        Returns:
            Complete health report with metrics and status
        """
        metrics = self._collect_metrics()
        warnings = []
        errors = []

        # Check thresholds
        if metrics.cpu_percent > self.cpu_warning_threshold:
            warnings.append(f"High CPU usage: {metrics.cpu_percent:.1f}%")

        if metrics.memory_percent > self.memory_warning_threshold:
            warnings.append(f"High memory usage: {metrics.memory_percent:.1f}%")

        if metrics.disk_usage_percent > self.disk_warning_threshold:
            warnings.append(f"High disk usage: {metrics.disk_usage_percent:.1f}%")

        # Determine status
        if errors:
            status = HealthStatus.ERROR
        elif metrics.cpu_percent > 95 or metrics.memory_percent > 95:
            status = HealthStatus.DEGRADED
        elif warnings:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.ONLINE

        return HealthReport(
            status=status,
            timestamp=time.time(),
            metrics=metrics,
            warnings=warnings,
            errors=errors,
        )

    def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        try:
            while self._monitoring:
                try:
                    report = self.get_health_report()

                    # Send via IPC sync channel
                    message = {
                        "type": "health_report",
                        **report.to_dict(),
                    }
                    self.ipc.send_sync_message(message)

                    # Log warnings/errors
                    if report.warnings:
                        for warning in report.warnings:
                            logger.warning("Health: %s", warning)

                    if report.errors:
                        for error in report.errors:
                            logger.error("Health: %s", error)

                except Exception as exc:
                    logger.error("Error in health monitoring loop: %s", exc)

                time.sleep(self.check_interval)

        except Exception as exc:
            logger.error("Health monitoring loop crashed: %s", exc)
        finally:
            logger.info("Health monitoring loop exited")

    def _collect_metrics(self) -> SystemMetrics:
        """Collect current system resource metrics.

        Returns:
            Current system metrics
        """
        # CPU and memory
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()

        # Disk usage for root filesystem
        disk = psutil.disk_usage("/")

        # Process info
        process = psutil.Process(os.getpid())
        thread_count = threading.active_count()
        process_count = len(psutil.pids())

        # Uptime
        uptime_seconds = time.time() - self._start_time

        # GPU detection
        gpu_available = False
        gpu_memory_used_mb = None
        gpu_memory_total_mb = None
        gpu_utilization_percent = None

        try:
            # Try to detect GPU (PyTorch)
            import torch

            if torch.cuda.is_available():
                gpu_available = True
                gpu_memory_used_mb = (
                    torch.cuda.memory_allocated(0) / (1024 * 1024)
                )
                gpu_memory_total_mb = (
                    torch.cuda.get_device_properties(0).total_memory / (1024 * 1024)
                )
            elif torch.backends.mps.is_available():
                gpu_available = True
                # MPS (Apple Silicon) doesn't provide detailed metrics
        except ImportError:
            pass
        except Exception as exc:
            logger.debug("GPU detection failed: %s", exc)

        return SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_mb=memory.used / (1024 * 1024),
            memory_available_mb=memory.available / (1024 * 1024),
            disk_usage_percent=disk.percent,
            disk_free_gb=disk.free / (1024 * 1024 * 1024),
            thread_count=thread_count,
            process_count=process_count,
            uptime_seconds=uptime_seconds,
            gpu_available=gpu_available,
            gpu_memory_used_mb=gpu_memory_used_mb,
            gpu_memory_total_mb=gpu_memory_total_mb,
            gpu_utilization_percent=gpu_utilization_percent,
        )

    @property
    def is_monitoring(self) -> bool:
        """Check if monitoring is currently active."""
        return self._monitoring
