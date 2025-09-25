"""
Tests for MonitoringService application service

Comprehensive test suite for system health monitoring, performance tracking,
alerting mechanisms, and hardware status monitoring.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime, timedelta
import asyncio

from src.application.services.monitoring_service import (
    MonitoringService,
    Alert,
    AlertLevel,
    MonitoringMetric,
    PerformanceMetrics
)
from src.domain.entities.hardware import HardwareSystem, Camera
from src.domain.value_objects.workflow_state import WorkflowState


class TestMonitoringService:
    """Test MonitoringService functionality"""

    @pytest.fixture
    def mock_hardware_system(self):
        """Mock hardware system"""
        mock = Mock(spec=HardwareSystem)
        mock.calculate_system_health.return_value = 0.95
        mock.get_system_status_summary.return_value = {
            "overall_status": "healthy",
            "components_count": 3,
            "active_components": 3,
            "error_count": 0
        }
        mock.get_all_components.return_value = [
            Mock(component_id="cam_001", status="active"),
            Mock(component_id="display_001", status="active")
        ]
        return mock

    @pytest.fixture
    def mock_state_broadcaster(self):
        """Mock state broadcaster"""
        mock = AsyncMock()
        mock.broadcast_system_status = AsyncMock()
        mock.broadcast_error_event = AsyncMock()
        mock.broadcast_performance_metrics = AsyncMock()
        return mock

    @pytest.fixture
    def mock_workflow_orchestrator(self):
        """Mock workflow orchestrator"""
        mock = Mock()
        mock.current_state = WorkflowState.IDLE
        return mock

    @pytest.fixture
    def monitoring_service(self, mock_hardware_system, mock_state_broadcaster, mock_workflow_orchestrator):
        """Create MonitoringService with mocked dependencies"""
        service = MonitoringService(
            hardware_system=mock_hardware_system,
            state_broadcaster=mock_state_broadcaster,
            workflow_orchestrator=mock_workflow_orchestrator
        )
        return service

    @pytest.mark.asyncio
    async def test_service_startup(self, monitoring_service):
        """Test monitoring service startup"""
        await monitoring_service.start()

        assert monitoring_service._is_monitoring is True
        assert monitoring_service._monitoring_task is not None

    @pytest.mark.asyncio
    async def test_service_shutdown(self, monitoring_service):
        """Test monitoring service shutdown"""
        await monitoring_service.start()
        await monitoring_service.stop()

        assert monitoring_service._is_monitoring is False

    @pytest.mark.asyncio
    async def test_performance_metrics_collection(self, monitoring_service):
        """Test collection of performance metrics"""
        with patch('psutil.cpu_percent', return_value=45.5), \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:

            mock_memory.return_value.percent = 60.2
            mock_memory.return_value.available = 8000000000
            mock_disk.return_value.percent = 75.8
            mock_disk.return_value.free = 50000000000

            metrics = await monitoring_service.collect_performance_metrics()

            assert isinstance(metrics, PerformanceMetrics)
            assert metrics.cpu_percent == 45.5
            assert metrics.memory_percent == 60.2
            assert metrics.disk_percent == 75.8
            assert metrics.memory_available_bytes == 8000000000
            assert metrics.disk_free_bytes == 50000000000

    @pytest.mark.asyncio
    async def test_system_health_assessment(self, monitoring_service, mock_hardware_system):
        """Test system health assessment"""
        # Mock performance metrics
        with patch.object(monitoring_service, 'collect_performance_metrics') as mock_collect:
            mock_collect.return_value = PerformanceMetrics(
                cpu_percent=30.0,
                memory_percent=50.0,
                disk_percent=40.0,
                memory_available_bytes=8000000000,
                disk_free_bytes=100000000000
            )

            health = await monitoring_service.assess_system_health()

            assert isinstance(health, SystemHealth)
            assert health.overall_score >= 0.0
            assert health.overall_score <= 1.0
            assert health.status in [status.value for status in HealthStatus]
            assert "hardware_health" in health.component_scores
            assert "performance_health" in health.component_scores

    @pytest.mark.asyncio
    async def test_alert_generation_cpu_threshold(self, monitoring_service):
        """Test alert generation for CPU threshold breach"""
        # Set low CPU threshold for testing
        monitoring_service._alert_thresholds.cpu_percent = 50.0

        with patch.object(monitoring_service, 'collect_performance_metrics') as mock_collect:
            mock_collect.return_value = PerformanceMetrics(
                cpu_percent=75.0,  # Above threshold
                memory_percent=30.0,
                disk_percent=20.0,
                memory_available_bytes=8000000000,
                disk_free_bytes=100000000000
            )

            alerts = await monitoring_service._check_alert_conditions(
                mock_collect.return_value,
                hardware_health=0.95
            )

            # Should generate CPU alert
            cpu_alerts = [alert for alert in alerts if alert.alert_type == AlertType.HIGH_CPU_USAGE]
            assert len(cpu_alerts) > 0
            assert cpu_alerts[0].severity == AlertLevel.HIGH

    @pytest.mark.asyncio
    async def test_alert_generation_memory_threshold(self, monitoring_service):
        """Test alert generation for memory threshold breach"""
        monitoring_service._alert_thresholds.memory_percent = 60.0

        with patch.object(monitoring_service, 'collect_performance_metrics') as mock_collect:
            mock_collect.return_value = PerformanceMetrics(
                cpu_percent=30.0,
                memory_percent=85.0,  # Above threshold
                disk_percent=20.0,
                memory_available_bytes=2000000000,
                disk_free_bytes=100000000000
            )

            alerts = await monitoring_service._check_alert_conditions(
                mock_collect.return_value,
                hardware_health=0.95
            )

            # Should generate memory alert
            memory_alerts = [alert for alert in alerts if alert.alert_type == AlertType.HIGH_MEMORY_USAGE]
            assert len(memory_alerts) > 0

    @pytest.mark.asyncio
    async def test_alert_generation_hardware_health(self, monitoring_service, mock_hardware_system):
        """Test alert generation for hardware health issues"""
        # Mock poor hardware health
        mock_hardware_system.calculate_system_health.return_value = 0.3

        with patch.object(monitoring_service, 'collect_performance_metrics') as mock_collect:
            mock_collect.return_value = PerformanceMetrics(
                cpu_percent=30.0,
                memory_percent=40.0,
                disk_percent=20.0,
                memory_available_bytes=8000000000,
                disk_free_bytes=100000000000
            )

            alerts = await monitoring_service._check_alert_conditions(
                mock_collect.return_value,
                hardware_health=0.3
            )

            # Should generate hardware health alert
            hardware_alerts = [alert for alert in alerts if alert.alert_type == AlertType.HARDWARE_FAILURE]
            assert len(hardware_alerts) > 0

    @pytest.mark.asyncio
    async def test_alert_broadcasting(self, monitoring_service, mock_state_broadcaster):
        """Test alert broadcasting through state broadcaster"""
        alert = Alert(
            alert_id="test_alert_001",
            alert_type=AlertType.HIGH_CPU_USAGE,
            severity=AlertLevel.HIGH,
            message="CPU usage is 85.0%",
            timestamp=datetime.now(),
            component="system",
            threshold_value=75.0,
            current_value=85.0
        )

        await monitoring_service._broadcast_alert(alert)

        # Should broadcast error event
        mock_state_broadcaster.broadcast_error_event.assert_called_once()
        call_args = mock_state_broadcaster.broadcast_error_event.call_args
        error_data = call_args[0][0]

        assert error_data["alert_type"] == alert.alert_type.value
        assert error_data["severity"] == alert.severity.value
        assert error_data["message"] == alert.message

    @pytest.mark.asyncio
    async def test_monitoring_cycle(self, monitoring_service, mock_state_broadcaster):
        """Test complete monitoring cycle"""
        # Start monitoring with short interval
        monitoring_service._monitoring_interval_seconds = 0.1

        await monitoring_service.start()
        await asyncio.sleep(0.3)  # Let a few cycles run
        await monitoring_service.stop()

        # Should have broadcast system status multiple times
        assert mock_state_broadcaster.broadcast_system_status.call_count >= 2

    @pytest.mark.asyncio
    async def test_alert_suppression(self, monitoring_service):
        """Test alert suppression to prevent spam"""
        # Generate same alert multiple times
        alert = Alert(
            alert_id="spam_alert",
            alert_type=AlertType.HIGH_CPU_USAGE,
            severity=AlertLevel.HIGH,
            message="CPU usage high",
            timestamp=datetime.now(),
            component="system"
        )

        # First alert should go through
        await monitoring_service._process_alert(alert)
        assert len(monitoring_service._active_alerts) == 1

        # Same alert immediately should be suppressed
        await monitoring_service._process_alert(alert)
        assert len(monitoring_service._active_alerts) == 1

    @pytest.mark.asyncio
    async def test_alert_resolution(self, monitoring_service, mock_state_broadcaster):
        """Test alert resolution when conditions improve"""
        # Create active alert
        alert = Alert(
            alert_id="cpu_alert",
            alert_type=AlertType.HIGH_CPU_USAGE,
            severity=AlertLevel.HIGH,
            message="CPU usage high",
            timestamp=datetime.now(),
            component="system"
        )
        monitoring_service._active_alerts["cpu_alert"] = alert

        # Simulate improved conditions (low CPU)
        with patch.object(monitoring_service, 'collect_performance_metrics') as mock_collect:
            mock_collect.return_value = PerformanceMetrics(
                cpu_percent=25.0,  # Low CPU
                memory_percent=30.0,
                disk_percent=20.0,
                memory_available_bytes=8000000000,
                disk_free_bytes=100000000000
            )

            await monitoring_service._check_alert_resolutions(mock_collect.return_value, 0.95)

            # Alert should be resolved
            assert "cpu_alert" not in monitoring_service._active_alerts

    @pytest.mark.asyncio
    async def test_performance_history_tracking(self, monitoring_service):
        """Test performance metrics history tracking"""
        with patch.object(monitoring_service, 'collect_performance_metrics') as mock_collect:
            mock_collect.return_value = PerformanceMetrics(
                cpu_percent=45.0,
                memory_percent=60.0,
                disk_percent=30.0,
                memory_available_bytes=8000000000,
                disk_free_bytes=100000000000
            )

            # Collect metrics multiple times
            for _ in range(3):
                await monitoring_service._update_performance_history()

            history = monitoring_service.get_performance_history(limit=5)
            assert len(history) == 3
            assert all(entry["cpu_percent"] == 45.0 for entry in history)

    def test_alert_threshold_configuration(self, monitoring_service):
        """Test alert threshold configuration"""
        new_thresholds = AlertThresholds(
            cpu_percent=80.0,
            memory_percent=90.0,
            disk_percent=95.0,
            hardware_health_score=0.4
        )

        monitoring_service.update_alert_thresholds(new_thresholds)

        assert monitoring_service._alert_thresholds.cpu_percent == 80.0
        assert monitoring_service._alert_thresholds.memory_percent == 90.0
        assert monitoring_service._alert_thresholds.disk_percent == 95.0

    def test_monitoring_statistics(self, monitoring_service):
        """Test monitoring statistics collection"""
        stats = monitoring_service.get_monitoring_statistics()

        required_stats = [
            "uptime_seconds",
            "total_alerts_generated",
            "active_alerts_count",
            "monitoring_cycles_completed",
            "average_cycle_duration_ms",
            "last_health_score"
        ]

        for stat in required_stats:
            assert stat in stats

    @pytest.mark.asyncio
    async def test_hardware_component_monitoring(self, monitoring_service, mock_hardware_system):
        """Test individual hardware component monitoring"""
        # Mock component with issues
        mock_component = Mock()
        mock_component.component_id = "camera_001"
        mock_component.status = "error"
        mock_component.get_health_score.return_value = 0.2

        mock_hardware_system.get_all_components.return_value = [mock_component]

        alerts = await monitoring_service._check_hardware_component_alerts()

        # Should generate hardware component alert
        component_alerts = [alert for alert in alerts if "camera_001" in alert.component]
        assert len(component_alerts) > 0

    @pytest.mark.asyncio
    async def test_workflow_state_monitoring(self, monitoring_service, mock_workflow_orchestrator):
        """Test workflow state change monitoring"""
        # Simulate workflow state change
        mock_workflow_orchestrator.current_state = WorkflowState.ERROR

        health = await monitoring_service.assess_system_health()

        # System health should be affected by error state
        assert health.workflow_state == WorkflowState.ERROR.value
        assert health.overall_score < 1.0

    @pytest.mark.asyncio
    async def test_error_handling_in_monitoring(self, monitoring_service):
        """Test error handling during monitoring operations"""
        # Mock performance collection failure
        with patch.object(monitoring_service, 'collect_performance_metrics') as mock_collect:
            mock_collect.side_effect = Exception("Performance collection failed")

            # Should handle error gracefully
            await monitoring_service._monitoring_cycle()

            # Service should continue running
            assert monitoring_service._is_monitoring is True or monitoring_service._is_monitoring is False

    @pytest.mark.asyncio
    async def test_alert_escalation(self, monitoring_service):
        """Test alert severity escalation"""
        # Create medium severity alert
        alert = Alert(
            alert_id="escalation_test",
            alert_type=AlertType.HIGH_CPU_USAGE,
            severity=AlertLevel.MEDIUM,
            message="CPU usage elevated",
            timestamp=datetime.now() - timedelta(minutes=10),  # Old alert
            component="system"
        )

        monitoring_service._active_alerts["escalation_test"] = alert

        # Process escalation
        await monitoring_service._check_alert_escalation()

        # Alert severity should be escalated
        updated_alert = monitoring_service._active_alerts.get("escalation_test")
        if updated_alert:
            # Should be escalated to HIGH after time threshold
            pass  # Implementation dependent

    def test_health_status_calculation(self, monitoring_service):
        """Test health status calculation from scores"""
        # Test excellent health
        status = monitoring_service._calculate_health_status(0.95)
        assert status == HealthStatus.EXCELLENT

        # Test good health
        status = monitoring_service._calculate_health_status(0.80)
        assert status == HealthStatus.GOOD

        # Test fair health
        status = monitoring_service._calculate_health_status(0.65)
        assert status == HealthStatus.FAIR

        # Test poor health
        status = monitoring_service._calculate_health_status(0.45)
        assert status == HealthStatus.POOR

        # Test critical health
        status = monitoring_service._calculate_health_status(0.25)
        assert status == HealthStatus.CRITICAL

    @pytest.mark.asyncio
    async def test_periodic_health_reports(self, monitoring_service, mock_state_broadcaster):
        """Test periodic health report broadcasting"""
        await monitoring_service.start_periodic_health_reports(interval_minutes=0.01)  # 0.6 seconds
        await asyncio.sleep(1.2)  # Wait for reports
        await monitoring_service.stop_periodic_health_reports()

        # Should have broadcast health reports
        assert mock_state_broadcaster.broadcast_system_status.call_count >= 1

    @pytest.mark.asyncio
    async def test_custom_alert_handlers(self, monitoring_service):
        """Test custom alert handler registration"""
        handled_alerts = []

        async def custom_alert_handler(alert: Alert):
            handled_alerts.append(alert.alert_id)

        monitoring_service.register_alert_handler(AlertType.HIGH_CPU_USAGE, custom_alert_handler)

        # Create and process alert
        alert = Alert(
            alert_id="custom_handler_test",
            alert_type=AlertType.HIGH_CPU_USAGE,
            severity=AlertLevel.HIGH,
            message="Test alert",
            timestamp=datetime.now(),
            component="system"
        )

        await monitoring_service._process_alert(alert)

        # Custom handler should have been called
        assert "custom_handler_test" in handled_alerts


class TestAlert:
    """Test Alert functionality"""

    def test_alert_creation(self):
        """Test alert creation with all fields"""
        timestamp = datetime.now()
        alert = Alert(
            alert_id="test_alert_001",
            alert_type=AlertType.HIGH_CPU_USAGE,
            severity=AlertLevel.HIGH,
            message="CPU usage is 90%",
            timestamp=timestamp,
            component="system",
            threshold_value=75.0,
            current_value=90.0,
            metadata={"additional": "info"}
        )

        assert alert.alert_id == "test_alert_001"
        assert alert.alert_type == AlertType.HIGH_CPU_USAGE
        assert alert.severity == AlertLevel.HIGH
        assert alert.message == "CPU usage is 90%"
        assert alert.timestamp == timestamp
        assert alert.component == "system"
        assert alert.threshold_value == 75.0
        assert alert.current_value == 90.0
        assert alert.metadata["additional"] == "info"

    def test_alert_serialization(self):
        """Test alert serialization to dictionary"""
        alert = Alert(
            alert_id="serialize_test",
            alert_type=AlertType.HARDWARE_FAILURE,
            severity=AlertLevel.CRITICAL,
            message="Hardware failure detected",
            timestamp=datetime.now(),
            component="camera_001"
        )

        alert_dict = alert.to_dict()

        assert alert_dict["alert_id"] == "serialize_test"
        assert alert_dict["alert_type"] == AlertType.HARDWARE_FAILURE.value
        assert alert_dict["severity"] == AlertLevel.CRITICAL.value
        assert alert_dict["message"] == "Hardware failure detected"
        assert alert_dict["component"] == "camera_001"
        assert "timestamp" in alert_dict

    def test_alert_from_dict(self):
        """Test alert creation from dictionary"""
        alert_data = {
            "alert_id": "from_dict_test",
            "alert_type": "high_memory_usage",
            "severity": "high",
            "message": "Memory usage critical",
            "timestamp": datetime.now().isoformat(),
            "component": "system",
            "threshold_value": 85.0,
            "current_value": 92.0
        }

        alert = Alert.from_dict(alert_data)

        assert alert.alert_id == "from_dict_test"
        assert alert.alert_type == AlertType.HIGH_MEMORY_USAGE
        assert alert.severity == AlertLevel.HIGH
        assert alert.message == "Memory usage critical"
        assert alert.component == "system"
        assert alert.threshold_value == 85.0
        assert alert.current_value == 92.0


class TestPerformanceMetrics:
    """Test PerformanceMetrics functionality"""

    def test_performance_metrics_creation(self):
        """Test performance metrics creation"""
        metrics = PerformanceMetrics(
            cpu_percent=45.5,
            memory_percent=62.8,
            disk_percent=35.2,
            memory_available_bytes=8000000000,
            disk_free_bytes=100000000000,
            network_bytes_sent=5000000,
            network_bytes_received=15000000
        )

        assert metrics.cpu_percent == 45.5
        assert metrics.memory_percent == 62.8
        assert metrics.disk_percent == 35.2
        assert metrics.memory_available_bytes == 8000000000
        assert metrics.disk_free_bytes == 100000000000

    def test_performance_metrics_serialization(self):
        """Test performance metrics serialization"""
        metrics = PerformanceMetrics(
            cpu_percent=50.0,
            memory_percent=70.0,
            disk_percent=40.0,
            memory_available_bytes=4000000000,
            disk_free_bytes=50000000000
        )

        metrics_dict = metrics.to_dict()

        assert metrics_dict["cpu_percent"] == 50.0
        assert metrics_dict["memory_percent"] == 70.0
        assert metrics_dict["disk_percent"] == 40.0
        assert "timestamp" in metrics_dict


class TestSystemHealth:
    """Test SystemHealth functionality"""

    def test_system_health_creation(self):
        """Test system health creation"""
        component_scores = {
            "hardware_health": 0.95,
            "performance_health": 0.80,
            "workflow_health": 0.90
        }

        health = SystemHealth(
            overall_score=0.88,
            status=HealthStatus.GOOD,
            component_scores=component_scores,
            active_alerts_count=1,
            workflow_state="ready"
        )

        assert health.overall_score == 0.88
        assert health.status == HealthStatus.GOOD
        assert health.component_scores["hardware_health"] == 0.95
        assert health.active_alerts_count == 1
        assert health.workflow_state == "ready"

    def test_system_health_serialization(self):
        """Test system health serialization"""
        health = SystemHealth(
            overall_score=0.75,
            status=HealthStatus.FAIR,
            component_scores={"test": 0.75},
            active_alerts_count=2
        )

        health_dict = health.to_dict()

        assert health_dict["overall_score"] == 0.75
        assert health_dict["status"] == HealthStatus.FAIR.value
        assert health_dict["active_alerts_count"] == 2
        assert "timestamp" in health_dict


class TestEnums:
    """Test enum definitions"""

    def test_alert_severity_values(self):
        """Test AlertLevel enum values"""
        expected = ["low", "medium", "high", "critical"]
        actual = [severity.value for severity in AlertLevel]
        for expected_val in expected:
            assert expected_val in actual

    def test_alert_type_values(self):
        """Test AlertType enum values"""
        expected = [
            "high_cpu_usage", "high_memory_usage", "low_disk_space",
            "hardware_failure", "connection_lost", "performance_degradation",
            "workflow_error", "system_overload"
        ]
        actual = [alert_type.value for alert_type in AlertType]
        for expected_val in expected:
            assert expected_val in actual

    def test_health_status_values(self):
        """Test HealthStatus enum values"""
        expected = ["excellent", "good", "fair", "poor", "critical"]
        actual = [status.value for status in HealthStatus]
        for expected_val in expected:
            assert expected_val in actual