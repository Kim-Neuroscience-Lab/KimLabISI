"""
State Broadcaster Application Service

Broadcasts workflow state changes and system updates to the frontend
via IPC communication. Ensures frontend always has current system state.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Set, Callable
import logging
import asyncio
import json

from domain.value_objects.workflow_state import WorkflowState
from domain.entities.hardware import HardwareSystem
from infrastructure.communication.ipc_server import IPCServer


logger = logging.getLogger(__name__)


class BroadcastType(Enum):
    """Types of state broadcasts"""
    WORKFLOW_STATE = "workflow_state"
    HARDWARE_STATUS = "hardware_status"
    PROGRESS_UPDATE = "progress_update"
    ERROR_NOTIFICATION = "error_notification"
    SYSTEM_HEALTH = "system_health"
    DATA_UPDATE = "data_update"


class StateBroadcaster:
    """
    Application service for broadcasting state changes to frontend

    Manages real-time updates to keep the frontend synchronized with
    backend state changes without frontend needing to poll.
    """

    def __init__(self, ipc_server: IPCServer):
        self.ipc_server = ipc_server

        # State tracking
        self._last_workflow_state: Optional[WorkflowState] = None
        self._last_hardware_status: Dict[str, Any] = {}
        self._active_subscriptions: Set[str] = set()
        self._broadcast_queue: asyncio.Queue = asyncio.Queue()
        self._is_running = False

        # Broadcast configuration
        self._broadcast_interval_ms = 100  # 10 FPS updates
        self._batch_size = 10  # Max updates per batch

        # Subscribers and filters
        self._subscribers: Dict[BroadcastType, Set[Callable]] = {
            broadcast_type: set() for broadcast_type in BroadcastType
        }

        logger.info("State broadcaster initialized")

    async def start(self):
        """Start the state broadcasting service"""
        if self._is_running:
            logger.warning("State broadcaster already running")
            return

        self._is_running = True

        # Start broadcast loop
        asyncio.create_task(self._broadcast_loop())

        logger.info("State broadcaster started")

    async def stop(self):
        """Stop the state broadcasting service"""
        self._is_running = False
        logger.info("State broadcaster stopped")

    async def broadcast_workflow_state(
        self,
        current_state: WorkflowState,
        previous_state: Optional[WorkflowState] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Broadcast workflow state change"""

        # Only broadcast if state actually changed
        if current_state == self._last_workflow_state:
            return

        state_update = {
            "type": BroadcastType.WORKFLOW_STATE.value,
            "timestamp": datetime.now().isoformat(),
            "current_state": current_state.value,
            "previous_state": previous_state.value if previous_state else None,
            "metadata": metadata or {}
        }

        await self._queue_broadcast(state_update)
        self._last_workflow_state = current_state

        logger.debug(f"Queued workflow state broadcast: {current_state.value}")

    async def broadcast_hardware_status(
        self,
        hardware_system: HardwareSystem,
        changed_components: Optional[List[str]] = None
    ):
        """Broadcast hardware status update"""

        status_summary = hardware_system.get_system_status_summary()

        # Only broadcast if status changed
        if status_summary == self._last_hardware_status:
            return

        hardware_update = {
            "type": BroadcastType.HARDWARE_STATUS.value,
            "timestamp": datetime.now().isoformat(),
            "system_status": status_summary,
            "changed_components": changed_components or [],
            "health_score": hardware_system.calculate_system_health()
        }

        await self._queue_broadcast(hardware_update)
        self._last_hardware_status = status_summary

        logger.debug(f"Queued hardware status broadcast: {len(changed_components or [])} changes")

    async def broadcast_progress_update(
        self,
        operation: str,
        progress_percent: float,
        stage: str,
        estimated_remaining_s: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Broadcast operation progress update"""

        progress_update = {
            "type": BroadcastType.PROGRESS_UPDATE.value,
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "progress_percent": max(0.0, min(100.0, progress_percent)),
            "stage": stage,
            "estimated_remaining_s": estimated_remaining_s,
            "details": details or {}
        }

        await self._queue_broadcast(progress_update)

        logger.debug(f"Queued progress update: {operation} {progress_percent:.1f}%")

    async def broadcast_error_notification(
        self,
        error_message: str,
        error_type: str = "general",
        severity: str = "error",
        component: Optional[str] = None,
        recovery_suggestions: Optional[List[str]] = None
    ):
        """Broadcast error notification"""

        error_notification = {
            "type": BroadcastType.ERROR_NOTIFICATION.value,
            "timestamp": datetime.now().isoformat(),
            "error_message": error_message,
            "error_type": error_type,
            "severity": severity,
            "component": component,
            "recovery_suggestions": recovery_suggestions or []
        }

        await self._queue_broadcast(error_notification)

        logger.info(f"Queued error notification: {error_type} - {error_message}")

    async def broadcast_system_health(
        self,
        health_score: float,
        health_details: Dict[str, Any],
        alerts: Optional[List[str]] = None
    ):
        """Broadcast system health status"""

        health_update = {
            "type": BroadcastType.SYSTEM_HEALTH.value,
            "timestamp": datetime.now().isoformat(),
            "health_score": health_score,
            "health_details": health_details,
            "alerts": alerts or []
        }

        await self._queue_broadcast(health_update)

        logger.debug(f"Queued system health broadcast: {health_score:.2f}")

    async def broadcast_data_update(
        self,
        data_type: str,
        data_id: str,
        update_type: str,  # created, updated, deleted
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Broadcast data change notification"""

        data_update = {
            "type": BroadcastType.DATA_UPDATE.value,
            "timestamp": datetime.now().isoformat(),
            "data_type": data_type,
            "data_id": data_id,
            "update_type": update_type,
            "metadata": metadata or {}
        }

        await self._queue_broadcast(data_update)

        logger.debug(f"Queued data update: {data_type} {data_id} {update_type}")

    def subscribe(
        self,
        broadcast_type: BroadcastType,
        callback: Callable[[Dict[str, Any]], None]
    ):
        """Subscribe to specific broadcast types"""
        self._subscribers[broadcast_type].add(callback)
        logger.debug(f"Added subscriber for {broadcast_type.value}")

    def unsubscribe(
        self,
        broadcast_type: BroadcastType,
        callback: Callable[[Dict[str, Any]], None]
    ):
        """Unsubscribe from broadcast types"""
        self._subscribers[broadcast_type].discard(callback)
        logger.debug(f"Removed subscriber for {broadcast_type.value}")

    async def _queue_broadcast(self, update: Dict[str, Any]):
        """Queue update for broadcasting"""
        try:
            # Non-blocking queue put with size limit
            if self._broadcast_queue.qsize() < 100:  # Max queue size
                await self._broadcast_queue.put(update)
            else:
                logger.warning("Broadcast queue full, dropping update")

        except Exception as e:
            logger.error(f"Error queuing broadcast: {e}")

    async def _broadcast_loop(self):
        """Main broadcast loop"""
        logger.debug("Starting broadcast loop")

        while self._is_running:
            try:
                # Collect batch of updates
                updates = []
                batch_start = datetime.now()

                # Get updates with timeout
                try:
                    while len(updates) < self._batch_size:
                        timeout_ms = self._broadcast_interval_ms / 1000
                        update = await asyncio.wait_for(
                            self._broadcast_queue.get(),
                            timeout=timeout_ms
                        )
                        updates.append(update)

                        # Check if we've spent too long collecting
                        if (datetime.now() - batch_start).total_seconds() * 1000 > self._broadcast_interval_ms:
                            break

                except asyncio.TimeoutError:
                    # No more updates available, proceed with current batch
                    pass

                # Broadcast collected updates
                if updates:
                    await self._send_batch(updates)

                # Maintain target broadcast rate
                elapsed_ms = (datetime.now() - batch_start).total_seconds() * 1000
                remaining_ms = max(0, self._broadcast_interval_ms - elapsed_ms)

                if remaining_ms > 0:
                    await asyncio.sleep(remaining_ms / 1000)

            except Exception as e:
                logger.exception(f"Error in broadcast loop: {e}")
                await asyncio.sleep(0.1)  # Brief pause on error

        logger.debug("Broadcast loop terminated")

    async def _send_batch(self, updates: List[Dict[str, Any]]):
        """Send batch of updates to frontend and subscribers"""
        try:
            # Send to frontend via IPC
            if self.ipc_server and self.ipc_server.is_connected():
                batch_message = {
                    "type": "state_batch",
                    "timestamp": datetime.now().isoformat(),
                    "updates": updates
                }

                await self.ipc_server.send_message(json.dumps(batch_message))

            # Notify local subscribers
            for update in updates:
                await self._notify_subscribers(update)

            logger.debug(f"Sent batch of {len(updates)} updates")

        except Exception as e:
            logger.error(f"Error sending update batch: {e}")

    async def _notify_subscribers(self, update: Dict[str, Any]):
        """Notify local subscribers of update"""
        try:
            broadcast_type_str = update.get("type")
            if not broadcast_type_str:
                return

            broadcast_type = BroadcastType(broadcast_type_str)
            subscribers = self._subscribers.get(broadcast_type, set())

            for callback in subscribers:
                try:
                    # Call subscriber callback
                    if asyncio.iscoroutinefunction(callback):
                        await callback(update)
                    else:
                        callback(update)

                except Exception as e:
                    logger.error(f"Error in subscriber callback: {e}")

        except Exception as e:
            logger.error(f"Error notifying subscribers: {e}")

    def get_broadcast_stats(self) -> Dict[str, Any]:
        """Get broadcasting statistics"""
        return {
            "is_running": self._is_running,
            "queue_size": self._broadcast_queue.qsize(),
            "subscribers": {
                broadcast_type.value: len(subscribers)
                for broadcast_type, subscribers in self._subscribers.items()
            },
            "last_workflow_state": self._last_workflow_state.value if self._last_workflow_state else None,
            "broadcast_interval_ms": self._broadcast_interval_ms,
            "batch_size": self._batch_size
        }