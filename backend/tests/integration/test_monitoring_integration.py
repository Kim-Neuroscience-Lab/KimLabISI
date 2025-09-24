"""
Integration tests for monitoring system

Tests the integration between MonitoringService (application layer)
and SystemMonitor (infrastructure layer), ensuring end-to-end
monitoring functionality works correctly.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime
import logging

from src.application.services.monitoring_service import (
    MonitoringService,
    AlertSeverity,
    AlertType
)
from src.infrastructure.monitoring.system_monitor import (
    SystemMonitor,
    SystemMetricType
)
from src.domain.entities.hardware import HardwareSystem, Camera
from src.domain.value_objects.workflow_state import WorkflowState


class TestMonitoringIntegration:
    """Integration tests for monitoring system"""

    @pytest.fixture
    async def system_monitor(self):
        """Create and start system monitor"""
        monitor = SystemMonitor(
            collection_interval=0.1,  # Fast collection for testing
            enable_process_monitoring=True,
            enable_disk_monitoring=True,
            enable_network_monitoring=True
        )

        monitor.start_monitoring()
        await asyncio.sleep(0.2)  # Let it collect some initial metrics

        yield monitor

        monitor.stop_monitoring()

    @pytest.fixture
    def mock_hardware_system(self):
        """Mock hardware system with realistic components"""
        hardware = Mock(spec=HardwareSystem)

        # Mock camera component
        camera = Mock(spec=Camera)
        camera.component_id = "test_camera_001"
        camera.status = "active"
        camera.get_health_score.return_value = 0.95

        hardware.get_all_components.return_value = [camera]
        hardware.calculate_system_health.return_value = 0.92
        hardware.get_system_status_summary.return_value = {
            "overall_status": "healthy",
            "components_count": 1,
            "active_components": 1,
            "error_count": 0
        }

        return hardware

    @pytest.fixture
    def mock_state_broadcaster(self):
        """Mock state broadcaster"""
        broadcaster = AsyncMock()
        broadcaster.broadcast_system_status = AsyncMock()
        broadcaster.broadcast_error_event = AsyncMock()
        broadcaster.broadcast_performance_metrics = AsyncMock()
        return broadcaster

    @pytest.fixture
    def mock_workflow_orchestrator(self):
        """Mock workflow orchestrator"""
        orchestrator = Mock()
        orchestrator.current_state = WorkflowState.IDLE
        return orchestrator

    @pytest.fixture
    async def monitoring_service(self, mock_hardware_system, mock_state_broadcaster,
                               mock_workflow_orchestrator):
        """Create monitoring service with mocked dependencies"""
        service = MonitoringService(
            hardware_system=mock_hardware_system,
            state_broadcaster=mock_state_broadcaster,
            workflow_orchestrator=mock_workflow_orchestrator
        )

        # Set aggressive thresholds for testing
        service._alert_thresholds.cpu_percent = 50.0
        service._alert_thresholds.memory_percent = 60.0
        service._monitoring_interval_seconds = 0.1

        yield service

        await service.stop()

    @pytest.mark.asyncio
    async def test_end_to_end_monitoring_flow(self, system_monitor, monitoring_service,
                                            mock_state_broadcaster):
        """Test complete monitoring flow from system metrics to broadcasts"""
        # Start monitoring service
        await monitoring_service.start()

        # Wait for several monitoring cycles
        await asyncio.sleep(0.5)

        # Check that system monitoring is working
        current_metrics = system_monitor.get_current_metrics()
        assert len(current_metrics) > 0
        assert SystemMetricType.CPU_USAGE in current_metrics
        assert SystemMetricType.MEMORY_USAGE in current_metrics

        # Check that monitoring service collected performance metrics
        performance_metrics = await monitoring_service.collect_performance_metrics()
        assert performance_metrics.cpu_percent >= 0
        assert performance_metrics.memory_percent >= 0

        # Verify state broadcaster was called
        assert mock_state_broadcaster.broadcast_system_status.called

        await monitoring_service.stop()

    @pytest.mark.asyncio
    async def test_alert_generation_and_broadcasting(self, system_monitor, monitoring_service,
                                                   mock_state_broadcaster):
        """Test alert generation when thresholds are exceeded"""

        # Patch performance collection to return high CPU usage
        async def mock_collect_performance():
            from src.application.services.monitoring_service import PerformanceMetrics
            return PerformanceMetrics(
                cpu_percent=85.0,  # Above 50% threshold
                memory_percent=30.0,
                disk_percent=20.0,
                memory_available_bytes=8000000000,
                disk_free_bytes=100000000000
            )

        monitoring_service.collect_performance_metrics = mock_collect_performance

        # Start monitoring
        await monitoring_service.start()
        await asyncio.sleep(0.3)  # Wait for alert generation

        # Check that alert was generated and broadcast
        mock_state_broadcaster.broadcast_error_event.assert_called()

        # Verify alert content
        call_args = mock_state_broadcaster.broadcast_error_event.call_args
        error_data = call_args[0][0]

        assert error_data["alert_type"] == AlertType.HIGH_CPU_USAGE.value
        assert error_data["severity"] == AlertSeverity.HIGH.value
        assert "85.0%" in error_data["message"]

        await monitoring_service.stop()

    @pytest.mark.asyncio
    async def test_hardware_health_integration(self, system_monitor, monitoring_service,
                                             mock_hardware_system, mock_state_broadcaster):
        """Test integration with hardware health monitoring"""

        # Simulate hardware health degradation
        mock_hardware_system.calculate_system_health.return_value = 0.25  # Poor health

        await monitoring_service.start()
        await asyncio.sleep(0.3)

        # Should generate hardware health alert
        mock_state_broadcaster.broadcast_error_event.assert_called()

        # Check alert details
        calls = mock_state_broadcaster.broadcast_error_event.call_args_list
        hardware_alerts = [
            call for call in calls
            if call[0][0]["alert_type"] == AlertType.HARDWARE_FAILURE.value
        ]
        assert len(hardware_alerts) > 0

        await monitoring_service.stop()

    @pytest.mark.asyncio
    async def test_system_health_assessment_integration(self, system_monitor, monitoring_service):
        """Test system health assessment using real system metrics"""

        # Let system monitor collect real metrics
        await asyncio.sleep(0.2)

        # Assess system health
        health = await monitoring_service.assess_system_health()

        assert health.overall_score >= 0.0
        assert health.overall_score <= 1.0
        assert "hardware_health" in health.component_scores
        assert "performance_health" in health.component_scores
        assert health.workflow_state == WorkflowState.IDLE.value

    @pytest.mark.asyncio
    async def test_performance_metrics_collection_integration(self, system_monitor,
                                                            monitoring_service):
        """Test performance metrics collection using system monitor data"""

        # Ensure system monitor has collected some metrics
        await asyncio.sleep(0.2)

        # Collect performance metrics through monitoring service
        metrics = await monitoring_service.collect_performance_metrics()

        # Should have realistic values from system monitor
        assert 0 <= metrics.cpu_percent <= 100
        assert 0 <= metrics.memory_percent <= 100
        assert 0 <= metrics.disk_percent <= 100
        assert metrics.memory_available_bytes > 0
        assert metrics.disk_free_bytes > 0

    @pytest.mark.asyncio
    async def test_monitoring_service_statistics(self, system_monitor, monitoring_service):
        """Test monitoring service statistics collection"""

        await monitoring_service.start()
        await asyncio.sleep(0.3)  # Let some monitoring cycles complete

        stats = monitoring_service.get_monitoring_statistics()

        # Should have recorded monitoring activity
        assert "uptime_seconds" in stats
        assert stats["uptime_seconds"] > 0
        assert "monitoring_cycles_completed" in stats
        assert stats["monitoring_cycles_completed"] > 0
        assert "last_health_score" in stats
        assert 0 <= stats["last_health_score"] <= 1

        await monitoring_service.stop()

    @pytest.mark.asyncio
    async def test_alert_suppression_and_resolution(self, system_monitor, monitoring_service,
                                                  mock_state_broadcaster):
        """Test alert suppression and resolution mechanisms"""

        # First, trigger high CPU alert
        async def high_cpu_metrics():
            from src.application.services.monitoring_service import PerformanceMetrics
            return PerformanceMetrics(
                cpu_percent=85.0,  # High CPU
                memory_percent=30.0,
                disk_percent=20.0,
                memory_available_bytes=8000000000,
                disk_free_bytes=100000000000
            )

        monitoring_service.collect_performance_metrics = high_cpu_metrics

        await monitoring_service.start()
        await asyncio.sleep(0.3)

        # Should have generated alert
        initial_alert_calls = mock_state_broadcaster.broadcast_error_event.call_count
        assert initial_alert_calls > 0

        # Wait for more cycles - same alert should be suppressed
        await asyncio.sleep(0.3)
        suppressed_alert_calls = mock_state_broadcaster.broadcast_error_event.call_count

        # Should not have many more calls (alert suppression working)
        assert suppressed_alert_calls <= initial_alert_calls + 2

        # Now simulate CPU returning to normal
        async def normal_cpu_metrics():
            from src.application.services.monitoring_service import PerformanceMetrics
            return PerformanceMetrics(
                cpu_percent=25.0,  # Normal CPU
                memory_percent=30.0,
                disk_percent=20.0,
                memory_available_bytes=8000000000,
                disk_free_bytes=100000000000
            )

        monitoring_service.collect_performance_metrics = normal_cpu_metrics
        await asyncio.sleep(0.3)

        # Alert should be resolved (not in active alerts)
        assert len(monitoring_service._active_alerts) == 0

        await monitoring_service.stop()

    @pytest.mark.asyncio
    async def test_concurrent_monitoring_operations(self, system_monitor, monitoring_service):
        """Test concurrent monitoring operations don't interfere"""

        await monitoring_service.start()

        # Start multiple concurrent operations
        tasks = [
            monitoring_service.collect_performance_metrics(),
            monitoring_service.assess_system_health(),
            monitoring_service.collect_performance_metrics(),
            monitoring_service.assess_system_health(),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All operations should succeed
        for result in results:
            assert not isinstance(result, Exception)

        await monitoring_service.stop()

    @pytest.mark.asyncio
    async def test_error_resilience(self, system_monitor, monitoring_service,
                                   mock_hardware_system):
        """Test monitoring system resilience to component errors"""

        # Make hardware system raise exceptions
        mock_hardware_system.calculate_system_health.side_effect = Exception("Hardware error")

        await monitoring_service.start()
        await asyncio.sleep(0.3)

        # Monitoring should continue despite hardware errors
        assert monitoring_service._is_monitoring is True

        # Should still be able to collect performance metrics
        try:
            metrics = await monitoring_service.collect_performance_metrics()
            assert metrics is not None
        except Exception as e:
            pytest.fail(f"Performance collection failed: {e}")

        await monitoring_service.stop()

    @pytest.mark.asyncio
    async def test_monitoring_cleanup(self, system_monitor, monitoring_service):
        """Test proper cleanup of monitoring resources"""

        await monitoring_service.start()
        assert monitoring_service._is_monitoring is True

        # Stop monitoring
        await monitoring_service.stop()
        assert monitoring_service._is_monitoring is False

        # System monitor should also be properly managed
        # (In integration, would test resource cleanup)

    def test_system_monitor_callback_integration(self, system_monitor):
        """Test system monitor callbacks work with monitoring service"""

        received_metrics = []

        def metric_callback(metric):
            received_metrics.append(metric)

        system_monitor.add_metric_callback(metric_callback)
        system_monitor.start_monitoring()

        # Wait for metrics collection
        import time
        time.sleep(0.3)

        # Should have received metrics through callback
        assert len(received_metrics) > 0

        system_monitor.stop_monitoring()
        system_monitor.remove_metric_callback(metric_callback)

    @pytest.mark.asyncio
    async def test_metric_history_tracking(self, system_monitor, monitoring_service):
        """Test metric history is properly tracked across components"""

        await monitoring_service.start()
        await asyncio.sleep(0.3)

        # Check system monitor has history
        cpu_history = system_monitor.get_metric_history(SystemMetricType.CPU_USAGE, limit=5)
        assert len(cpu_history) > 0

        # Check monitoring service has performance history
        perf_history = monitoring_service.get_performance_history(limit=5)
        assert len(perf_history) > 0

        await monitoring_service.stop()


class TestMonitoringConfigurationIntegration:
    """Test monitoring system configuration and customization"""

    @pytest.mark.asyncio
    async def test_alert_threshold_configuration(self):
        """Test alert threshold configuration affects behavior"""
        from src.application.services.monitoring_service import AlertThresholds

        hardware = Mock(spec=HardwareSystem)
        hardware.calculate_system_health.return_value = 0.95

        broadcaster = AsyncMock()
        orchestrator = Mock()
        orchestrator.current_state = WorkflowState.IDLE

        service = MonitoringService(hardware, broadcaster, orchestrator)

        # Set very low CPU threshold
        new_thresholds = AlertThresholds(
            cpu_percent=1.0,  # Very low threshold
            memory_percent=90.0,
            disk_percent=95.0,
            hardware_health_score=0.3
        )

        service.update_alert_thresholds(new_thresholds)

        # Any CPU usage should trigger alert
        await service.start()
        await asyncio.sleep(0.3)

        # Should have triggered CPU alert
        broadcaster.broadcast_error_event.assert_called()

        await service.stop()

    @pytest.mark.asyncio
    async def test_monitoring_interval_configuration(self):
        """Test monitoring interval configuration"""

        hardware = Mock(spec=HardwareSystem)
        hardware.calculate_system_health.return_value = 0.95

        broadcaster = AsyncMock()
        orchestrator = Mock()

        # Very fast monitoring interval
        service = MonitoringService(hardware, broadcaster, orchestrator)
        service._monitoring_interval_seconds = 0.05  # 50ms

        start_time = asyncio.get_event_loop().time()

        await service.start()
        await asyncio.sleep(0.3)
        await service.stop()

        # Should have made multiple broadcast calls due to fast interval
        assert broadcaster.broadcast_system_status.call_count >= 3

    def test_system_monitor_configuration_options(self):
        """Test system monitor configuration options"""

        # Test different configuration options
        monitor1 = SystemMonitor(
            collection_interval=0.5,
            enable_process_monitoring=False,
            enable_disk_monitoring=False,
            enable_network_monitoring=False
        )

        monitor2 = SystemMonitor(
            collection_interval=0.1,
            enable_process_monitoring=True,
            enable_disk_monitoring=True,
            enable_network_monitoring=True
        )

        assert monitor1.collection_interval == 0.5
        assert monitor1.enable_process_monitoring is False

        assert monitor2.collection_interval == 0.1
        assert monitor2.enable_process_monitoring is True


@pytest.mark.integration
class TestMonitoringPerformance:
    """Performance and stress tests for monitoring integration"""

    @pytest.mark.asyncio
    async def test_high_frequency_monitoring(self):
        """Test monitoring system under high frequency collection"""

        hardware = Mock(spec=HardwareSystem)
        hardware.calculate_system_health.return_value = 0.95
        hardware.get_system_status_summary.return_value = {"status": "ok"}

        broadcaster = AsyncMock()
        orchestrator = Mock()
        orchestrator.current_state = WorkflowState.IDLE

        # Very high frequency monitoring
        service = MonitoringService(hardware, broadcaster, orchestrator)
        service._monitoring_interval_seconds = 0.01  # 10ms

        start_time = asyncio.get_event_loop().time()

        await service.start()
        await asyncio.sleep(0.5)  # Run for 500ms
        await service.stop()

        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time

        # Should have completed many monitoring cycles
        stats = service.get_monitoring_statistics()
        cycles_per_second = stats["monitoring_cycles_completed"] / duration

        # Should achieve reasonable throughput
        assert cycles_per_second > 10  # At least 10 cycles per second

    @pytest.mark.asyncio
    async def test_monitoring_memory_usage(self):
        """Test monitoring system doesn't have memory leaks"""

        import gc
        import sys

        hardware = Mock(spec=HardwareSystem)
        hardware.calculate_system_health.return_value = 0.95

        broadcaster = AsyncMock()
        orchestrator = Mock()

        service = MonitoringService(hardware, broadcaster, orchestrator)

        # Baseline memory usage
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Run monitoring for a while
        await service.start()
        await asyncio.sleep(1.0)
        await service.stop()

        # Clean up and check memory
        del service
        gc.collect()
        final_objects = len(gc.get_objects())

        # Should not have significant object growth
        object_growth = final_objects - initial_objects
        assert object_growth < 1000  # Reasonable threshold