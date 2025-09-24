"""
Monitoring Service

System health monitoring, performance tracking, and alert generation.
Provides comprehensive system oversight for the ISI macroscope.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Union
import logging
import asyncio
import psutil
import time
from dataclasses import dataclass

from ...domain.entities.hardware import HardwareSystem
from ...domain.services.workflow_orchestrator import WorkflowOrchestrator
from ..handlers.state_broadcaster import StateBroadcaster


logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MonitoringMetric(Enum):
    """Types of metrics to monitor"""
    SYSTEM_RESOURCES = "system_resources"
    HARDWARE_HEALTH = "hardware_health"
    WORKFLOW_PERFORMANCE = "workflow_performance"
    STORAGE_USAGE = "storage_usage"
    NETWORK_STATUS = "network_status"
    APPLICATION_HEALTH = "application_health"


@dataclass
class Alert:
    """System alert"""
    id: str
    timestamp: datetime
    level: AlertLevel
    category: str
    message: str
    details: Dict[str, Any]
    acknowledged: bool = False
    resolved: bool = False


@dataclass
class PerformanceMetrics:
    """System performance metrics snapshot"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_available_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_free_gb: float
    network_bytes_sent: int
    network_bytes_recv: int
    process_count: int
    thread_count: int


class MonitoringService:
    """
    Application service for system monitoring and health tracking

    Monitors system resources, hardware health, and application performance.
    Generates alerts and tracks performance trends.
    """

    def __init__(
        self,
        hardware_system: HardwareSystem,
        workflow_orchestrator: WorkflowOrchestrator,
        state_broadcaster: StateBroadcaster
    ):
        self.hardware_system = hardware_system
        self.workflow_orchestrator = workflow_orchestrator
        self.state_broadcaster = state_broadcaster

        # Monitoring configuration
        self._monitoring_interval_seconds = 5.0
        self._metrics_retention_hours = 24
        self._alert_retention_hours = 48
        self._is_monitoring = False

        # Thresholds for alerts
        self._alert_thresholds = {
            "cpu_percent": {"warning": 80.0, "critical": 95.0},
            "memory_percent": {"warning": 85.0, "critical": 95.0},
            "disk_percent": {"warning": 90.0, "critical": 98.0},
            "hardware_health": {"warning": 0.7, "critical": 0.5},
            "workflow_timeout": {"warning": 3600, "critical": 7200}  # seconds
        }

        # Data storage
        self._performance_history: List[PerformanceMetrics] = []
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: List[Alert] = []
        self._last_network_stats = None

        # Alert callbacks
        self._alert_callbacks: List[Callable[[Alert], None]] = []

        # Performance tracking
        self._last_performance_check = datetime.now()
        self._performance_trends: Dict[str, List[float]] = {}

        logger.info("Monitoring service initialized")

    async def start(self):
        """Start the monitoring service"""

        if self._is_monitoring:
            logger.warning("Monitoring service already running")
            return

        self._is_monitoring = True

        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop())

        # Initialize network stats baseline
        try:
            net_io = psutil.net_io_counters()
            self._last_network_stats = {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "timestamp": datetime.now()
            }
        except Exception:
            self._last_network_stats = None

        logger.info("Monitoring service started")

    async def stop(self):
        """Stop the monitoring service"""

        self._is_monitoring = False
        logger.info("Monitoring service stopped")

    async def force_health_check(self) -> Dict[str, Any]:
        """Force immediate health check and return results"""

        logger.info("Performing forced health check")

        # Collect all metrics
        performance_metrics = await self._collect_performance_metrics()
        hardware_health = self.hardware_system.calculate_system_health()
        workflow_status = self.workflow_orchestrator.get_workflow_status()

        # Check for immediate issues
        alerts_triggered = await self._check_alert_conditions(performance_metrics, hardware_health)

        health_report = {
            "timestamp": datetime.now().isoformat(),
            "overall_health": self._calculate_overall_health_score(),
            "performance_metrics": {
                "cpu_percent": performance_metrics.cpu_percent,
                "memory_percent": performance_metrics.memory_percent,
                "disk_percent": performance_metrics.disk_percent
            },
            "hardware_health": hardware_health,
            "workflow_status": workflow_status["current_state"],
            "active_alerts": len(self._active_alerts),
            "new_alerts": len(alerts_triggered),
            "system_ready": self.hardware_system.is_system_ready_for_acquisition()[0]
        }

        logger.info(f"Health check completed: overall_health={health_report['overall_health']:.2f}")
        return health_report

    def get_performance_trends(self, hours: int = 1) -> Dict[str, Any]:
        """Get performance trends over specified time period"""

        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [
            m for m in self._performance_history
            if m.timestamp >= cutoff_time
        ]

        if not recent_metrics:
            return {"error": "No metrics available for specified period"}

        # Calculate trends
        trends = {
            "period_hours": hours,
            "samples": len(recent_metrics),
            "cpu_trend": self._calculate_trend([m.cpu_percent for m in recent_metrics]),
            "memory_trend": self._calculate_trend([m.memory_percent for m in recent_metrics]),
            "disk_trend": self._calculate_trend([m.disk_percent for m in recent_metrics]),
            "current_values": {
                "cpu_percent": recent_metrics[-1].cpu_percent,
                "memory_percent": recent_metrics[-1].memory_percent,
                "disk_percent": recent_metrics[-1].disk_percent
            },
            "peak_values": {
                "cpu_percent": max(m.cpu_percent for m in recent_metrics),
                "memory_percent": max(m.memory_percent for m in recent_metrics),
                "disk_percent": max(m.disk_percent for m in recent_metrics)
            }
        }

        return trends

    def get_active_alerts(self, level: Optional[AlertLevel] = None) -> List[Dict[str, Any]]:
        """Get currently active alerts"""

        alerts = list(self._active_alerts.values())

        if level:
            alerts = [alert for alert in alerts if alert.level == level]

        return [self._alert_to_dict(alert) for alert in alerts]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""

        if alert_id in self._active_alerts:
            self._active_alerts[alert_id].acknowledged = True
            logger.info(f"Alert acknowledged: {alert_id}")
            return True

        logger.warning(f"Alert not found for acknowledgment: {alert_id}")
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved"""

        if alert_id in self._active_alerts:
            alert = self._active_alerts[alert_id]
            alert.resolved = True

            # Move to history
            self._alert_history.append(alert)
            del self._active_alerts[alert_id]

            logger.info(f"Alert resolved: {alert_id}")
            return True

        logger.warning(f"Alert not found for resolution: {alert_id}")
        return False

    def add_alert_callback(self, callback: Callable[[Alert], None]):
        """Add callback for alert notifications"""
        self._alert_callbacks.append(callback)

    def remove_alert_callback(self, callback: Callable[[Alert], None]):
        """Remove alert notification callback"""
        if callback in self._alert_callbacks:
            self._alert_callbacks.remove(callback)

    async def _monitoring_loop(self):
        """Main monitoring loop"""

        logger.debug("Starting monitoring loop")

        while self._is_monitoring:
            try:
                loop_start = datetime.now()

                # Collect performance metrics
                performance_metrics = await self._collect_performance_metrics()
                self._performance_history.append(performance_metrics)

                # Check hardware health
                hardware_health = self.hardware_system.calculate_system_health()

                # Check for alert conditions
                await self._check_alert_conditions(performance_metrics, hardware_health)

                # Cleanup old data
                await self._cleanup_old_data()

                # Broadcast system health update
                await self._broadcast_health_update(performance_metrics, hardware_health)

                # Calculate time to next check
                elapsed = (datetime.now() - loop_start).total_seconds()
                sleep_time = max(0, self._monitoring_interval_seconds - elapsed)

                await asyncio.sleep(sleep_time)

            except Exception as e:
                logger.exception(f"Error in monitoring loop: {e}")
                await asyncio.sleep(1.0)  # Brief pause on error

        logger.debug("Monitoring loop terminated")

    async def _collect_performance_metrics(self) -> PerformanceMetrics:
        """Collect current system performance metrics"""

        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=None)

            # Memory usage
            memory = psutil.virtual_memory()

            # Disk usage
            disk = psutil.disk_usage('/')

            # Network I/O
            net_io = psutil.net_io_counters()
            net_bytes_sent = net_io.bytes_sent
            net_bytes_recv = net_io.bytes_recv

            # Process info
            process_count = len(psutil.pids())

            # Current process threads
            current_process = psutil.Process()
            thread_count = current_process.num_threads()

            metrics = PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_gb=memory.used / (1024**3),
                memory_available_gb=memory.available / (1024**3),
                disk_percent=(disk.used / disk.total) * 100,
                disk_used_gb=disk.used / (1024**3),
                disk_free_gb=disk.free / (1024**3),
                network_bytes_sent=net_bytes_sent,
                network_bytes_recv=net_bytes_recv,
                process_count=process_count,
                thread_count=thread_count
            )

            return metrics

        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")
            # Return default metrics on error
            return PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_gb=0.0,
                memory_available_gb=0.0,
                disk_percent=0.0,
                disk_used_gb=0.0,
                disk_free_gb=0.0,
                network_bytes_sent=0,
                network_bytes_recv=0,
                process_count=0,
                thread_count=0
            )

    async def _check_alert_conditions(
        self,
        performance_metrics: PerformanceMetrics,
        hardware_health: float
    ) -> List[Alert]:
        """Check for alert conditions and generate alerts"""

        new_alerts = []

        # Check CPU usage
        cpu_alert = self._check_threshold_alert(
            "cpu_high",
            "CPU Usage",
            performance_metrics.cpu_percent,
            self._alert_thresholds["cpu_percent"],
            f"CPU usage is {performance_metrics.cpu_percent:.1f}%"
        )
        if cpu_alert:
            new_alerts.append(cpu_alert)

        # Check memory usage
        memory_alert = self._check_threshold_alert(
            "memory_high",
            "Memory Usage",
            performance_metrics.memory_percent,
            self._alert_thresholds["memory_percent"],
            f"Memory usage is {performance_metrics.memory_percent:.1f}%"
        )
        if memory_alert:
            new_alerts.append(memory_alert)

        # Check disk usage
        disk_alert = self._check_threshold_alert(
            "disk_full",
            "Disk Usage",
            performance_metrics.disk_percent,
            self._alert_thresholds["disk_percent"],
            f"Disk usage is {performance_metrics.disk_percent:.1f}%"
        )
        if disk_alert:
            new_alerts.append(disk_alert)

        # Check hardware health
        health_alert = self._check_threshold_alert(
            "hardware_degraded",
            "Hardware Health",
            hardware_health,
            self._alert_thresholds["hardware_health"],
            f"Hardware health score is {hardware_health:.2f}",
            lower_is_worse=True
        )
        if health_alert:
            new_alerts.append(health_alert)

        # Process new alerts
        for alert in new_alerts:
            await self._process_new_alert(alert)

        return new_alerts

    def _check_threshold_alert(
        self,
        alert_id: str,
        category: str,
        current_value: float,
        thresholds: Dict[str, float],
        message: str,
        lower_is_worse: bool = False
    ) -> Optional[Alert]:
        """Check if value exceeds thresholds and create alert if needed"""

        # Determine alert level
        alert_level = None

        if lower_is_worse:
            if current_value <= thresholds["critical"]:
                alert_level = AlertLevel.CRITICAL
            elif current_value <= thresholds["warning"]:
                alert_level = AlertLevel.WARNING
        else:
            if current_value >= thresholds["critical"]:
                alert_level = AlertLevel.CRITICAL
            elif current_value >= thresholds["warning"]:
                alert_level = AlertLevel.WARNING

        # Check if alert already exists
        if alert_id in self._active_alerts:
            existing_alert = self._active_alerts[alert_id]

            # Update alert level if changed
            if alert_level and existing_alert.level != alert_level:
                existing_alert.level = alert_level
                existing_alert.message = message
                existing_alert.timestamp = datetime.now()

            # Clear alert if condition resolved
            elif not alert_level:
                self.resolve_alert(alert_id)

            return None

        # Create new alert if threshold exceeded
        if alert_level:
            return Alert(
                id=alert_id,
                timestamp=datetime.now(),
                level=alert_level,
                category=category,
                message=message,
                details={
                    "current_value": current_value,
                    "thresholds": thresholds,
                    "lower_is_worse": lower_is_worse
                }
            )

        return None

    async def _process_new_alert(self, alert: Alert):
        """Process a new alert"""

        # Add to active alerts
        self._active_alerts[alert.id] = alert

        # Notify callbacks
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

        # Broadcast alert
        await self.state_broadcaster.broadcast_error_notification(
            error_message=alert.message,
            error_type=alert.category,
            severity=alert.level.value,
            component="system_monitor"
        )

        logger.info(f"New {alert.level.value} alert: {alert.category} - {alert.message}")

    async def _cleanup_old_data(self):
        """Clean up old performance data and resolved alerts"""

        # Clean old performance data
        cutoff_time = datetime.now() - timedelta(hours=self._metrics_retention_hours)
        self._performance_history = [
            m for m in self._performance_history
            if m.timestamp >= cutoff_time
        ]

        # Clean old alert history
        alert_cutoff = datetime.now() - timedelta(hours=self._alert_retention_hours)
        self._alert_history = [
            alert for alert in self._alert_history
            if alert.timestamp >= alert_cutoff
        ]

    async def _broadcast_health_update(
        self,
        performance_metrics: PerformanceMetrics,
        hardware_health: float
    ):
        """Broadcast system health update"""

        health_data = {
            "health_score": self._calculate_overall_health_score(),
            "health_details": {
                "cpu_percent": performance_metrics.cpu_percent,
                "memory_percent": performance_metrics.memory_percent,
                "disk_percent": performance_metrics.disk_percent,
                "hardware_health": hardware_health,
                "active_alerts": len(self._active_alerts)
            },
            "alerts": [
                alert.message for alert in self._active_alerts.values()
                if alert.level in [AlertLevel.ERROR, AlertLevel.CRITICAL]
            ][:5]  # Top 5 critical alerts
        }

        await self.state_broadcaster.broadcast_system_health(**health_data)

    def _calculate_overall_health_score(self) -> float:
        """Calculate overall system health score (0-1)"""

        if not self._performance_history:
            return 0.5  # Unknown health

        latest_metrics = self._performance_history[-1]

        # Component health scores (0-1, higher is better)
        cpu_health = max(0, 1.0 - (latest_metrics.cpu_percent / 100))
        memory_health = max(0, 1.0 - (latest_metrics.memory_percent / 100))
        disk_health = max(0, 1.0 - (latest_metrics.disk_percent / 100))
        hardware_health = self.hardware_system.calculate_system_health()

        # Alert penalty
        alert_penalty = 0.0
        for alert in self._active_alerts.values():
            if alert.level == AlertLevel.CRITICAL:
                alert_penalty += 0.2
            elif alert.level == AlertLevel.ERROR:
                alert_penalty += 0.1
            elif alert.level == AlertLevel.WARNING:
                alert_penalty += 0.05

        # Weighted average
        health_score = (
            cpu_health * 0.3 +
            memory_health * 0.3 +
            disk_health * 0.2 +
            hardware_health * 0.2
        ) - alert_penalty

        return max(0.0, min(1.0, health_score))

    def _calculate_trend(self, values: List[float]) -> Dict[str, float]:
        """Calculate trend information for a series of values"""

        if len(values) < 2:
            return {"trend": "stable", "change_percent": 0.0}

        # Simple linear trend
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        if first_avg == 0:
            change_percent = 0.0
        else:
            change_percent = ((second_avg - first_avg) / first_avg) * 100

        if abs(change_percent) < 1.0:
            trend = "stable"
        elif change_percent > 0:
            trend = "increasing"
        else:
            trend = "decreasing"

        return {
            "trend": trend,
            "change_percent": change_percent,
            "first_half_avg": first_avg,
            "second_half_avg": second_avg
        }

    def _alert_to_dict(self, alert: Alert) -> Dict[str, Any]:
        """Convert alert to dictionary"""

        return {
            "id": alert.id,
            "timestamp": alert.timestamp.isoformat(),
            "level": alert.level.value,
            "category": alert.category,
            "message": alert.message,
            "details": alert.details,
            "acknowledged": alert.acknowledged,
            "resolved": alert.resolved
        }

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get monitoring service status"""

        return {
            "is_monitoring": self._is_monitoring,
            "monitoring_interval_seconds": self._monitoring_interval_seconds,
            "metrics_history_count": len(self._performance_history),
            "active_alerts_count": len(self._active_alerts),
            "alert_history_count": len(self._alert_history),
            "overall_health_score": self._calculate_overall_health_score(),
            "last_check": self._last_performance_check.isoformat(),
            "alert_thresholds": self._alert_thresholds
        }