"""
Tests for QueryHandler application service

Comprehensive test suite for frontend query handling with caching,
structured responses, and query type management.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta
import json
import tempfile
from pathlib import Path

from src.application.handlers.query_handler import (
    QueryHandler,
    QueryType,
    QueryResult,
    QueryError,
    CacheEntry
)
from src.domain.value_objects.workflow_state import WorkflowState
from src.domain.value_objects.parameters import CombinedParameters
from src.domain.entities.dataset import StimulusDataset, AcquisitionSession
from src.domain.entities.hardware import HardwareSystem, Camera


class TestQueryHandler:
    """Test QueryHandler functionality"""

    @pytest.fixture
    def mock_workflow_orchestrator(self):
        """Mock workflow orchestrator"""
        mock = AsyncMock()
        mock.current_state = WorkflowState.IDLE
        mock.get_state_history.return_value = [
            {"state": WorkflowState.IDLE, "timestamp": datetime.now().isoformat()},
            {"state": WorkflowState.READY, "timestamp": datetime.now().isoformat()}
        ]
        return mock

    @pytest.fixture
    def mock_dataset_repository(self):
        """Mock dataset repository"""
        mock = AsyncMock()
        mock.list_datasets.return_value = [
            {"dataset_id": "test_001", "name": "Test Dataset 1"},
            {"dataset_id": "test_002", "name": "Test Dataset 2"}
        ]
        return mock

    @pytest.fixture
    def mock_hardware_system(self):
        """Mock hardware system"""
        mock = Mock(spec=HardwareSystem)
        mock.get_system_status_summary.return_value = {
            "overall_status": "healthy",
            "components_count": 3,
            "active_components": 2
        }
        mock.get_component_details.return_value = {
            "camera_001": {"status": "active", "temperature": 25.0},
            "display_001": {"status": "active", "brightness": 80}
        }
        return mock

    @pytest.fixture
    def mock_session_manager(self):
        """Mock session manager"""
        mock = AsyncMock()
        mock.get_current_session.return_value = {
            "session_id": "session_001",
            "status": "active",
            "start_time": datetime.now().isoformat()
        }
        mock.list_sessions.return_value = [
            {"session_id": "session_001", "status": "active"},
            {"session_id": "session_002", "status": "completed"}
        ]
        return mock

    @pytest.fixture
    def query_handler(self, mock_workflow_orchestrator, mock_dataset_repository,
                     mock_hardware_system, mock_session_manager):
        """Create QueryHandler with mocked dependencies"""
        handler = QueryHandler(
            workflow_orchestrator=mock_workflow_orchestrator,
            dataset_repository=mock_dataset_repository,
            hardware_system=mock_hardware_system,
            session_manager=mock_session_manager
        )
        return handler

    @pytest.mark.asyncio
    async def test_handle_system_status_query(self, query_handler, mock_workflow_orchestrator,
                                            mock_hardware_system):
        """Test system status query handling"""
        result = await query_handler.handle_query(QueryType.SYSTEM_STATUS.value)

        assert result["success"] is True
        assert result["query_type"] == QueryType.SYSTEM_STATUS.value
        assert "data" in result
        assert "workflow_state" in result["data"]
        assert "hardware_status" in result["data"]

        mock_workflow_orchestrator.current_state
        mock_hardware_system.get_system_status_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_dataset_list_query(self, query_handler, mock_dataset_repository):
        """Test dataset list query handling"""
        result = await query_handler.handle_query(QueryType.DATASET_LIST.value)

        assert result["success"] is True
        assert result["query_type"] == QueryType.DATASET_LIST.value
        assert "data" in result
        assert "datasets" in result["data"]
        assert len(result["data"]["datasets"]) == 2

        mock_dataset_repository.list_datasets.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_hardware_details_query(self, query_handler, mock_hardware_system):
        """Test hardware details query handling"""
        parameters = {"component_id": "camera_001"}
        result = await query_handler.handle_query(QueryType.HARDWARE_DETAILS.value, parameters)

        assert result["success"] is True
        assert result["query_type"] == QueryType.HARDWARE_DETAILS.value
        assert "data" in result

        mock_hardware_system.get_component_details.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_workflow_history_query(self, query_handler, mock_workflow_orchestrator):
        """Test workflow history query handling"""
        parameters = {"limit": 10}
        result = await query_handler.handle_query(QueryType.WORKFLOW_HISTORY.value, parameters)

        assert result["success"] is True
        assert result["query_type"] == QueryType.WORKFLOW_HISTORY.value
        assert "data" in result
        assert "history" in result["data"]

        mock_workflow_orchestrator.get_state_history.assert_called_once_with(limit=10)

    @pytest.mark.asyncio
    async def test_handle_session_status_query(self, query_handler, mock_session_manager):
        """Test session status query handling"""
        result = await query_handler.handle_query(QueryType.SESSION_STATUS.value)

        assert result["success"] is True
        assert result["query_type"] == QueryType.SESSION_STATUS.value
        assert "data" in result
        assert "current_session" in result["data"]

        mock_session_manager.get_current_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_caching_basic(self, query_handler):
        """Test basic query result caching"""
        # First query - should hit the handler
        result1 = await query_handler.handle_query(QueryType.SYSTEM_STATUS.value)

        # Second identical query - should hit cache
        result2 = await query_handler.handle_query(QueryType.SYSTEM_STATUS.value)

        assert result1 == result2
        assert result2["from_cache"] is True

    @pytest.mark.asyncio
    async def test_query_caching_with_parameters(self, query_handler):
        """Test caching with different parameters"""
        parameters1 = {"component_id": "camera_001"}
        parameters2 = {"component_id": "display_001"}

        # Different parameters should result in different cache entries
        result1 = await query_handler.handle_query(
            QueryType.HARDWARE_DETAILS.value, parameters1
        )
        result2 = await query_handler.handle_query(
            QueryType.HARDWARE_DETAILS.value, parameters2
        )

        assert result1 != result2
        assert result1.get("from_cache") is not True
        assert result2.get("from_cache") is not True

    @pytest.mark.asyncio
    async def test_cache_expiry(self, query_handler):
        """Test cache entry expiration"""
        # Set very short cache TTL for testing
        query_handler._cache_ttl_seconds = 0.1

        # First query
        result1 = await query_handler.handle_query(QueryType.SYSTEM_STATUS.value)
        assert result1.get("from_cache") is not True

        # Wait for cache expiry
        import asyncio
        await asyncio.sleep(0.2)

        # Second query should not use cache
        result2 = await query_handler.handle_query(QueryType.SYSTEM_STATUS.value)
        assert result2.get("from_cache") is not True

    @pytest.mark.asyncio
    async def test_invalid_query_type(self, query_handler):
        """Test handling of invalid query types"""
        with pytest.raises(ValueError) as exc_info:
            await query_handler.handle_query("invalid_query_type")

        assert "is not a valid QueryType" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_query_handler_error_handling(self, query_handler, mock_workflow_orchestrator):
        """Test error handling in query processing"""
        # Mock an exception in workflow orchestrator
        mock_workflow_orchestrator.current_state = Mock(side_effect=Exception("Test error"))

        result = await query_handler.handle_query(QueryType.SYSTEM_STATUS.value)

        assert result["success"] is False
        assert result["error_type"] == "QueryProcessingError"
        assert "Test error" in result["error_message"]

    @pytest.mark.asyncio
    async def test_session_list_query(self, query_handler, mock_session_manager):
        """Test session list query handling"""
        parameters = {"status": "active", "limit": 5}
        result = await query_handler.handle_query(QueryType.SESSION_LIST.value, parameters)

        assert result["success"] is True
        assert result["query_type"] == QueryType.SESSION_LIST.value
        assert "data" in result

        mock_session_manager.list_sessions.assert_called_once()

    @pytest.mark.asyncio
    async def test_performance_metrics_query(self, query_handler):
        """Test performance metrics query"""
        with patch('psutil.cpu_percent', return_value=45.5), \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:

            mock_memory.return_value.percent = 60.2
            mock_disk.return_value.percent = 75.8

            result = await query_handler.handle_query(QueryType.PERFORMANCE_METRICS.value)

            assert result["success"] is True
            assert "data" in result
            assert "cpu_percent" in result["data"]
            assert "memory_percent" in result["data"]
            assert "disk_percent" in result["data"]

    @pytest.mark.asyncio
    async def test_configuration_query(self, query_handler):
        """Test configuration query"""
        result = await query_handler.handle_query(QueryType.CONFIGURATION.value)

        assert result["success"] is True
        assert "data" in result
        assert "cache_enabled" in result["data"]
        assert "cache_ttl_seconds" in result["data"]
        assert "cache_max_entries" in result["data"]

    def test_cache_key_generation(self, query_handler):
        """Test cache key generation"""
        # Test with no parameters
        key1 = query_handler._generate_cache_key(QueryType.SYSTEM_STATUS, None)
        key2 = query_handler._generate_cache_key(QueryType.SYSTEM_STATUS, {})
        assert key1 == key2

        # Test with parameters
        key3 = query_handler._generate_cache_key(
            QueryType.HARDWARE_DETAILS,
            {"component_id": "camera_001"}
        )
        key4 = query_handler._generate_cache_key(
            QueryType.HARDWARE_DETAILS,
            {"component_id": "display_001"}
        )
        assert key3 != key4

    def test_cache_cleanup(self, query_handler):
        """Test automatic cache cleanup"""
        # Set low max entries for testing
        query_handler._cache_max_entries = 2

        # Manually add cache entries
        now = datetime.now()
        query_handler._query_cache["key1"] = CacheEntry({"data": "test1"}, now)
        query_handler._query_cache["key2"] = CacheEntry({"data": "test2"}, now)
        query_handler._query_cache["key3"] = CacheEntry({"data": "test3"}, now)

        # Trigger cleanup
        query_handler._cleanup_expired_cache()

        # Should have removed oldest entry
        assert len(query_handler._query_cache) <= query_handler._cache_max_entries

    def test_cache_entry_expiry_check(self, query_handler):
        """Test cache entry expiry checking"""
        # Create expired entry
        expired_time = datetime.now() - timedelta(seconds=query_handler._cache_ttl_seconds + 1)
        expired_entry = CacheEntry({"data": "test"}, expired_time)

        # Create fresh entry
        fresh_time = datetime.now()
        fresh_entry = CacheEntry({"data": "test"}, fresh_time)

        assert query_handler._is_cache_entry_expired(expired_entry) is True
        assert query_handler._is_cache_entry_expired(fresh_entry) is False

    @pytest.mark.asyncio
    async def test_concurrent_queries(self, query_handler):
        """Test handling concurrent queries"""
        import asyncio

        # Launch multiple concurrent queries
        tasks = [
            query_handler.handle_query(QueryType.SYSTEM_STATUS.value),
            query_handler.handle_query(QueryType.DATASET_LIST.value),
            query_handler.handle_query(QueryType.SESSION_STATUS.value)
        ]

        results = await asyncio.gather(*tasks)

        # All queries should succeed
        for result in results:
            assert result["success"] is True

    def test_query_metrics_tracking(self, query_handler):
        """Test query metrics tracking"""
        initial_stats = query_handler.get_query_stats()
        assert "total_queries" in initial_stats
        assert "cache_hits" in initial_stats
        assert "cache_misses" in initial_stats

        # The counts should be numeric
        assert isinstance(initial_stats["total_queries"], int)
        assert isinstance(initial_stats["cache_hits"], int)
        assert isinstance(initial_stats["cache_misses"], int)

    @pytest.mark.asyncio
    async def test_query_validation(self, query_handler):
        """Test query parameter validation"""
        # Test with invalid parameter types
        with pytest.raises(QueryError):
            await query_handler.handle_query(
                QueryType.HARDWARE_DETAILS.value,
                "invalid_parameters"  # Should be dict, not string
            )

    def test_query_result_structure(self, query_handler):
        """Test query result structure compliance"""
        # Create a sample result
        test_result = query_handler._create_success_result(
            QueryType.SYSTEM_STATUS,
            {"status": "ok"},
            from_cache=False
        )

        # Check required fields
        required_fields = ["success", "query_type", "timestamp", "data", "from_cache"]
        for field in required_fields:
            assert field in test_result

        assert test_result["success"] is True
        assert test_result["query_type"] == QueryType.SYSTEM_STATUS.value
        assert isinstance(test_result["timestamp"], str)
        assert test_result["data"] == {"status": "ok"}
        assert test_result["from_cache"] is False


class TestQueryType:
    """Test QueryType enum"""

    def test_query_type_values(self):
        """Test all query type enum values"""
        expected_types = [
            "system_status",
            "dataset_list",
            "dataset_details",
            "hardware_status",
            "hardware_details",
            "workflow_history",
            "session_status",
            "session_list",
            "performance_metrics",
            "configuration",
            "analysis_results",
            "calibration_status"
        ]

        actual_types = [qt.value for qt in QueryType]
        for expected in expected_types:
            assert expected in actual_types

    def test_query_type_uniqueness(self):
        """Test that all query type values are unique"""
        values = [qt.value for qt in QueryType]
        assert len(values) == len(set(values))


class TestCacheEntry:
    """Test CacheEntry functionality"""

    def test_cache_entry_creation(self):
        """Test cache entry creation and properties"""
        data = {"test": "value"}
        timestamp = datetime.now()

        entry = CacheEntry(data, timestamp)

        assert entry.result == data
        assert entry.timestamp == timestamp
        assert isinstance(entry.timestamp, datetime)

    def test_cache_entry_serialization(self):
        """Test cache entry can be serialized"""
        data = {"test": "value", "number": 42}
        timestamp = datetime.now()

        entry = CacheEntry(data, timestamp)

        # Should be JSON serializable
        serialized = json.dumps({
            "result": entry.result,
            "timestamp": entry.timestamp.isoformat()
        })

        assert isinstance(serialized, str)
        assert "test" in serialized
        assert "42" in serialized


class TestQueryError:
    """Test QueryError exception handling"""

    def test_query_error_creation(self):
        """Test QueryError exception creation"""
        error = QueryError("Test error message", "TestErrorType")

        assert str(error) == "Test error message"
        assert error.error_type == "TestErrorType"

    def test_query_error_without_type(self):
        """Test QueryError without explicit error type"""
        error = QueryError("Test error message")

        assert str(error) == "Test error message"
        assert error.error_type == "QueryError"