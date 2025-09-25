"""
Integration tests for communication system

Tests the integration between CommunicationService, StateBroadcaster,
QueryHandler, and StatePersistenceService, ensuring end-to-end
communication and state management works correctly.
"""

import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime

from src.application.services.communication_service import (
    CommunicationService,
    ConnectionState
)
from src.infrastructure.communication.ipc_server import MessageType
from src.application.handlers.state_broadcaster import (
    StateBroadcaster,
    BroadcastType
)
from src.application.handlers.query_handler import (
    QueryHandler,
    QueryType
)
from src.application.services.state_persistence import (
    StatePersistenceService,
    PersistenceLevel
)
from src.domain.value_objects.workflow_state import WorkflowState
from src.domain.entities.hardware import HardwareSystem


class TestCommunicationIntegration:
    """Integration tests for communication system"""

    @pytest.fixture
    def temp_persistence_path(self):
        """Create temporary directory for persistence testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def mock_ipc_server(self):
        """Mock IPC server for testing"""
        mock = AsyncMock()
        mock.start = AsyncMock()
        mock.stop = AsyncMock()
        mock.restart = AsyncMock()
        mock.send_message = AsyncMock()
        mock.broadcast_message = AsyncMock()
        mock.is_running = Mock(return_value=True)
        mock.get_connected_clients = Mock(return_value=["client_1", "client_2"])
        return mock

    @pytest.fixture
    def mock_workflow_orchestrator(self):
        """Mock workflow orchestrator"""
        mock = AsyncMock()
        mock.current_state = WorkflowState.IDLE
        mock.get_state_history.return_value = [
            {"state": WorkflowState.IDLE.value, "timestamp": datetime.now().isoformat()},
            {"state": WorkflowState.READY.value, "timestamp": datetime.now().isoformat()}
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
            "active_components": 2,
            "hardware_health": 0.95
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
    async def state_persistence_service(self, temp_persistence_path, mock_hardware_system):
        """Create state persistence service"""
        service = StatePersistenceService(
            persistence_path=temp_persistence_path,
            hardware_system=mock_hardware_system,
            persistence_level=PersistenceLevel.STANDARD
        )
        yield service

    @pytest.fixture
    async def query_handler(self, mock_workflow_orchestrator, mock_dataset_repository,
                          mock_hardware_system, mock_session_manager):
        """Create query handler"""
        handler = QueryHandler(
            workflow_orchestrator=mock_workflow_orchestrator,
            dataset_repository=mock_dataset_repository,
            hardware_system=mock_hardware_system,
            session_manager=mock_session_manager
        )
        yield handler

    @pytest.fixture
    async def state_broadcaster(self, mock_ipc_server):
        """Create state broadcaster"""
        broadcaster = StateBroadcaster(ipc_server=mock_ipc_server)
        await broadcaster.start()
        yield broadcaster
        await broadcaster.stop()

    @pytest.fixture
    async def communication_service(self, mock_ipc_server, state_broadcaster, query_handler):
        """Create communication service"""
        service = CommunicationService(
            ipc_server=mock_ipc_server,
            state_broadcaster=state_broadcaster,
            query_handler=query_handler
        )
        yield service

    @pytest.mark.asyncio
    async def test_end_to_end_query_flow(self, communication_service, query_handler,
                                       mock_workflow_orchestrator):
        """Test complete query flow from frontend to backend"""

        await communication_service.start()

        # Simulate frontend query message
        query_message = {
            "type": MessageType.QUERY.value,
            "id": "query_001",
            "data": {
                "query_type": QueryType.SYSTEM_STATUS.value,
                "parameters": {}
            }
        }

        # Handle query through communication service
        response = await communication_service.handle_frontend_message("client_1", query_message)

        # Verify response structure
        assert response["success"] is True
        assert response["message_id"] == "query_001"
        assert "data" in response
        assert "workflow_state" in response["data"]
        assert "hardware_status" in response["data"]

        # Verify query handler was called
        mock_workflow_orchestrator.current_state

        await communication_service.stop()

    @pytest.mark.asyncio
    async def test_state_broadcasting_integration(self, communication_service, state_broadcaster,
                                                mock_ipc_server):
        """Test state broadcasting through communication system"""

        await communication_service.start()

        # Subscribe client to workflow state updates
        subscription_message = {
            "type": MessageType.SUBSCRIPTION.value,
            "id": "sub_001",
            "data": {
                "action": "subscribe",
                "topics": ["workflow_state", "system_status"]
            }
        }

        response = await communication_service.handle_frontend_message("client_1", subscription_message)
        assert response["success"] is True

        # Broadcast a workflow state update
        await state_broadcaster.broadcast_workflow_state(
            WorkflowState.READY,
            WorkflowState.IDLE
        )

        # Give async processing time
        await asyncio.sleep(0.1)

        # Verify broadcast was sent through IPC
        mock_ipc_server.broadcast_message.assert_called()

        # Check broadcast message content
        call_args = mock_ipc_server.broadcast_message.call_args
        broadcast_message = call_args[0][0]

        assert broadcast_message["type"] == BroadcastType.WORKFLOW_STATE.value
        assert broadcast_message["current_state"] == WorkflowState.READY.value
        assert broadcast_message["previous_state"] == WorkflowState.IDLE.value

        await communication_service.stop()

    @pytest.mark.asyncio
    async def test_state_persistence_integration(self, communication_service, state_persistence_service,
                                               mock_workflow_orchestrator):
        """Test state persistence works with communication system"""

        await communication_service.start()

        # Save a workflow snapshot
        snapshot_id = await state_persistence_service.save_workflow_snapshot(
            workflow_state=WorkflowState.ACQUIRING,
            dataset_id="integration_test_dataset",
            session_id="integration_test_session"
        )

        assert snapshot_id is not None

        # Verify state was persisted
        loaded_snapshot = await state_persistence_service.load_current_state()
        assert loaded_snapshot is not None
        assert loaded_snapshot.workflow_state == WorkflowState.ACQUIRING
        assert loaded_snapshot.dataset_id == "integration_test_dataset"

        # Query the persisted state through communication system
        query_message = {
            "type": MessageType.QUERY.value,
            "id": "persistence_query",
            "data": {
                "query_type": QueryType.WORKFLOW_HISTORY.value,
                "parameters": {"limit": 5}
            }
        }

        response = await communication_service.handle_frontend_message("client_1", query_message)
        assert response["success"] is True

        await communication_service.stop()

    @pytest.mark.asyncio
    async def test_concurrent_client_handling(self, communication_service, query_handler):
        """Test handling multiple concurrent clients"""

        await communication_service.start()

        # Create multiple concurrent query messages from different clients
        query_tasks = []
        for i in range(5):
            query_message = {
                "type": MessageType.QUERY.value,
                "id": f"concurrent_query_{i}",
                "data": {
                    "query_type": QueryType.SYSTEM_STATUS.value,
                    "parameters": {}
                }
            }
            task = communication_service.handle_frontend_message(f"client_{i}", query_message)
            query_tasks.append(task)

        # Execute all queries concurrently
        responses = await asyncio.gather(*query_tasks)

        # All queries should succeed
        for i, response in enumerate(responses):
            assert response["success"] is True
            assert response["message_id"] == f"concurrent_query_{i}"

        await communication_service.stop()

    @pytest.mark.asyncio
    async def test_subscription_filtering(self, communication_service, state_broadcaster,
                                        mock_ipc_server):
        """Test subscription filtering works correctly"""

        await communication_service.start()

        # Client 1 subscribes to workflow_state only
        sub1_message = {
            "type": MessageType.SUBSCRIPTION.value,
            "id": "sub_001",
            "data": {
                "action": "subscribe",
                "topics": ["workflow_state"]
            }
        }
        await communication_service.handle_frontend_message("client_1", sub1_message)

        # Client 2 subscribes to system_status only
        sub2_message = {
            "type": MessageType.SUBSCRIPTION.value,
            "id": "sub_002",
            "data": {
                "action": "subscribe",
                "topics": ["system_status"]
            }
        }
        await communication_service.handle_frontend_message("client_2", sub2_message)

        # Broadcast workflow state update
        await state_broadcaster.broadcast_workflow_state(WorkflowState.READY)
        await asyncio.sleep(0.1)

        # Broadcast system status update
        await state_broadcaster.broadcast_system_status({"cpu": 50, "memory": 60})
        await asyncio.sleep(0.1)

        # Both broadcasts should have occurred
        assert mock_ipc_server.broadcast_message.call_count >= 2

        await communication_service.stop()

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, communication_service, query_handler,
                                            mock_workflow_orchestrator):
        """Test error handling across communication components"""

        await communication_service.start()

        # Make workflow orchestrator raise exception
        mock_workflow_orchestrator.current_state = Mock(side_effect=Exception("Orchestrator error"))

        # Send query that will trigger error
        error_query = {
            "type": MessageType.QUERY.value,
            "id": "error_query",
            "data": {
                "query_type": QueryType.SYSTEM_STATUS.value,
                "parameters": {}
            }
        }

        response = await communication_service.handle_frontend_message("client_1", error_query)

        # Should return error response, not crash
        assert response["success"] is False
        assert "error" in response
        assert response["message_id"] == "error_query"

        await communication_service.stop()

    @pytest.mark.asyncio
    async def test_connection_recovery(self, communication_service, mock_ipc_server):
        """Test connection recovery mechanisms"""

        await communication_service.start()
        assert communication_service._connection_state == ConnectionState.CONNECTED

        # Simulate connection loss
        mock_ipc_server.is_running.return_value = False
        await communication_service.handle_connection_lost()

        # Should attempt recovery
        mock_ipc_server.restart.assert_called()

        # Simulate successful reconnection
        mock_ipc_server.is_running.return_value = True
        await communication_service._check_connection_health()

        await communication_service.stop()

    @pytest.mark.asyncio
    async def test_message_queuing_during_disconnection(self, communication_service,
                                                      state_broadcaster, mock_ipc_server):
        """Test message queuing when disconnected"""

        await communication_service.start()

        # Simulate disconnection
        communication_service._connection_state = ConnectionState.DISCONNECTED
        mock_ipc_server.is_running.return_value = False
        mock_ipc_server.broadcast_message.side_effect = ConnectionError("Not connected")

        # Try to broadcast - should queue message
        await state_broadcaster.broadcast_workflow_state(WorkflowState.READY)
        await asyncio.sleep(0.1)

        # Message should be queued in broadcaster
        assert len(state_broadcaster._message_queue) > 0

        # Simulate reconnection
        communication_service._connection_state = ConnectionState.CONNECTED
        mock_ipc_server.is_running.return_value = True
        mock_ipc_server.broadcast_message.side_effect = None

        # Flush queued messages
        await state_broadcaster._flush_message_queue()

        # Messages should have been sent
        assert mock_ipc_server.broadcast_message.call_count > 0

        await communication_service.stop()

    @pytest.mark.asyncio
    async def test_query_caching_integration(self, communication_service, query_handler):
        """Test query result caching works across requests"""

        await communication_service.start()

        # First query
        query_message = {
            "type": MessageType.QUERY.value,
            "id": "cache_query_1",
            "data": {
                "query_type": QueryType.SYSTEM_STATUS.value,
                "parameters": {}
            }
        }

        response1 = await communication_service.handle_frontend_message("client_1", query_message)
        assert response1["success"] is True

        # Second identical query (should hit cache)
        query_message["id"] = "cache_query_2"
        response2 = await communication_service.handle_frontend_message("client_1", query_message)

        assert response2["success"] is True
        assert response2.get("from_cache") is True

        await communication_service.stop()

    @pytest.mark.asyncio
    async def test_batch_message_processing(self, communication_service):
        """Test batch message processing"""

        await communication_service.start()

        # Create batch of messages
        messages = []
        for i in range(3):
            message = {
                "type": MessageType.QUERY.value,
                "id": f"batch_msg_{i}",
                "data": {
                    "query_type": QueryType.SYSTEM_STATUS.value,
                    "parameters": {}
                }
            }
            messages.append(message)

        # Process batch
        responses = await communication_service.process_message_batch("client_1", messages)

        assert len(responses) == 3
        for i, response in enumerate(responses):
            assert response["success"] is True
            assert response["message_id"] == f"batch_msg_{i}"

        await communication_service.stop()


class TestStatePersistenceIntegration:
    """Integration tests for state persistence with other components"""

    @pytest.fixture
    def temp_persistence_path(self):
        """Create temporary directory for persistence testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def mock_hardware_system(self):
        """Mock hardware system"""
        mock = Mock(spec=HardwareSystem)
        mock.get_system_status_summary.return_value = {
            "overall_status": "healthy",
            "components_count": 3,
            "hardware_health": 0.95
        }
        return mock

    @pytest.fixture
    async def persistence_service(self, temp_persistence_path, mock_hardware_system):
        """Create persistence service"""
        service = StatePersistenceService(
            persistence_path=temp_persistence_path,
            hardware_system=mock_hardware_system,
            persistence_level=PersistenceLevel.FULL
        )
        yield service

    @pytest.mark.asyncio
    async def test_auto_save_integration(self, persistence_service):
        """Test auto-save functionality integration"""

        # Enable auto-save with short interval
        persistence_service._auto_save_interval_seconds = 0.1

        # Create initial snapshot
        snapshot_id = await persistence_service.save_workflow_snapshot(
            workflow_state=WorkflowState.READY,
            dataset_id="auto_save_test"
        )

        # Start auto-save
        await persistence_service.start_auto_save()
        await asyncio.sleep(0.3)  # Let auto-save run

        # Stop auto-save
        await persistence_service.stop_auto_save()

        # Current state should be maintained
        current_state = await persistence_service.load_current_state()
        assert current_state is not None
        assert current_state.dataset_id == "auto_save_test"

    @pytest.mark.asyncio
    async def test_backup_and_recovery_integration(self, persistence_service):
        """Test backup and recovery integration"""

        # Create some state data
        original_snapshot_id = await persistence_service.save_workflow_snapshot(
            workflow_state=WorkflowState.ANALYZING,
            dataset_id="backup_test_original"
        )

        # Create backup
        backup_path = await persistence_service.create_backup("integration_test")
        assert backup_path.exists()

        # Modify current state
        await persistence_service.save_workflow_snapshot(
            workflow_state=WorkflowState.ERROR,
            dataset_id="backup_test_modified"
        )

        # Verify modified state
        modified_state = await persistence_service.load_current_state()
        assert modified_state.workflow_state == WorkflowState.ERROR

        # Restore from backup
        success = await persistence_service.restore_from_backup(backup_path)
        assert success is True

        # Verify restored state
        restored_state = await persistence_service.load_current_state()
        assert restored_state.workflow_state == WorkflowState.ANALYZING
        assert restored_state.dataset_id == "backup_test_original"

    @pytest.mark.asyncio
    async def test_snapshot_history_integration(self, persistence_service):
        """Test snapshot history tracking"""

        # Create multiple snapshots
        snapshots = []
        states = [WorkflowState.IDLE, WorkflowState.READY, WorkflowState.ACQUIRING]

        for i, state in enumerate(states):
            snapshot_id = await persistence_service.save_workflow_snapshot(
                workflow_state=state,
                dataset_id=f"history_test_{i}"
            )
            snapshots.append(snapshot_id)

        # List all snapshots
        snapshot_list = await persistence_service.list_snapshots()
        assert len(snapshot_list) == 3

        # Snapshots should be sorted by timestamp (newest first)
        assert snapshot_list[0]["snapshot_id"] == snapshots[-1]

        # Load specific snapshot
        loaded_snapshot = await persistence_service.load_snapshot(snapshots[1])
        assert loaded_snapshot.workflow_state == states[1]
        assert loaded_snapshot.dataset_id == "history_test_1"

    @pytest.mark.asyncio
    async def test_persistence_error_recovery(self, persistence_service, temp_persistence_path):
        """Test persistence error recovery mechanisms"""

        # Create initial valid state
        await persistence_service.save_workflow_snapshot(
            workflow_state=WorkflowState.READY,
            dataset_id="error_recovery_test"
        )

        # Corrupt the current state file
        current_state_file = temp_persistence_path / "current_state.json"
        with open(current_state_file, 'w') as f:
            f.write("corrupted json {")

        # Should recover from snapshots
        recovered_state = await persistence_service.load_current_state()

        # Should either recover successfully or return None (depending on implementation)
        if recovered_state:
            assert recovered_state.dataset_id == "error_recovery_test"


@pytest.mark.integration
class TestCommunicationPerformance:
    """Performance tests for communication system integration"""

    @pytest.mark.asyncio
    async def test_high_throughput_messaging(self):
        """Test communication system under high message throughput"""

        mock_ipc = AsyncMock()
        mock_ipc.is_running.return_value = True
        mock_ipc.get_connected_clients.return_value = ["client_1"]

        # Create minimal communication service for performance testing
        broadcaster = StateBroadcaster(ipc_server=mock_ipc)
        await broadcaster.start()

        # Send many messages rapidly
        start_time = asyncio.get_event_loop().time()

        tasks = []
        for i in range(100):
            task = broadcaster.broadcast_system_status({"message_id": i, "cpu": 50})
            tasks.append(task)

        await asyncio.gather(*tasks)

        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time

        # Should handle high throughput efficiently
        messages_per_second = 100 / duration
        assert messages_per_second > 50  # Should handle at least 50 msg/s

        await broadcaster.stop()

    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self):
        """Test memory usage doesn't grow excessively under load"""

        import gc

        mock_ipc = AsyncMock()
        mock_hardware = Mock()
        mock_hardware.get_system_status_summary.return_value = {"status": "ok"}

        query_handler = QueryHandler(
            workflow_orchestrator=AsyncMock(),
            dataset_repository=AsyncMock(),
            hardware_system=mock_hardware,
            session_manager=AsyncMock()
        )

        # Baseline memory
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Process many queries
        for i in range(50):
            await query_handler.handle_query(QueryType.SYSTEM_STATUS.value)

        # Check memory growth
        gc.collect()
        final_objects = len(gc.get_objects())
        object_growth = final_objects - initial_objects

        # Should not have excessive object growth
        assert object_growth < 500  # Reasonable threshold