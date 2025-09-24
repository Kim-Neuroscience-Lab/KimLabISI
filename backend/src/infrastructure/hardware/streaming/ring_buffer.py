"""
Ring Buffer Infrastructure

Provides efficient circular buffer implementation for streaming data
in the ISI macroscope system, optimized for real-time acquisition.
"""

from __future__ import annotations
from typing import Optional, Any, Union, List, Tuple, Generic, TypeVar, Iterator
from threading import Lock, Event
import time
import numpy as np
import logging
from enum import Enum
from dataclasses import dataclass
from abc import ABC, abstractmethod

T = TypeVar('T')

logger = logging.getLogger(__name__)


class BufferState(Enum):
    """Buffer state enumeration"""
    EMPTY = "empty"
    FILLING = "filling"
    FULL = "full"
    OVERRUN = "overrun"
    CLOSED = "closed"


class OverflowStrategy(Enum):
    """Strategy for handling buffer overflow"""
    DROP_OLDEST = "drop_oldest"  # Overwrite oldest data
    DROP_NEWEST = "drop_newest"  # Reject new data
    EXPAND = "expand"  # Dynamically expand buffer
    BLOCK = "block"  # Block until space available


@dataclass
class BufferMetrics:
    """Buffer performance metrics"""
    total_writes: int = 0
    total_reads: int = 0
    dropped_frames: int = 0
    overrun_events: int = 0
    current_fill_level: int = 0
    max_fill_level: int = 0
    avg_write_time_ms: float = 0.0
    avg_read_time_ms: float = 0.0
    memory_usage_bytes: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "total_writes": self.total_writes,
            "total_reads": self.total_reads,
            "dropped_frames": self.dropped_frames,
            "overrun_events": self.overrun_events,
            "current_fill_level": self.current_fill_level,
            "max_fill_level": self.max_fill_level,
            "avg_write_time_ms": self.avg_write_time_ms,
            "avg_read_time_ms": self.avg_read_time_ms,
            "memory_usage_bytes": self.memory_usage_bytes
        }


class BufferError(Exception):
    """Ring buffer related errors"""
    pass


class RingBuffer(Generic[T]):
    """
    Thread-safe circular buffer implementation for streaming data

    Optimized for high-throughput, low-latency data acquisition scenarios
    common in microscopy and imaging applications.
    """

    def __init__(
        self,
        capacity: int,
        overflow_strategy: OverflowStrategy = OverflowStrategy.DROP_OLDEST,
        name: Optional[str] = None,
        element_size_hint: Optional[int] = None
    ):
        if capacity <= 0:
            raise ValueError("Buffer capacity must be positive")

        self.capacity = capacity
        self.overflow_strategy = overflow_strategy
        self.name = name or f"RingBuffer_{id(self)}"
        self.element_size_hint = element_size_hint or 1024

        # Buffer storage
        self._buffer: List[Optional[T]] = [None] * capacity
        self._head = 0  # Next write position
        self._tail = 0  # Next read position
        self._size = 0  # Current number of elements

        # Thread safety
        self._lock = Lock()
        self._write_event = Event()
        self._read_event = Event()

        # State tracking
        self._state = BufferState.EMPTY
        self._closed = False
        self._metrics = BufferMetrics()

        # Performance tracking
        self._write_times: List[float] = []
        self._read_times: List[float] = []

        logger.info(f"Ring buffer '{self.name}' created with capacity {capacity}")

    def put(self, item: T, timeout: Optional[float] = None) -> bool:
        """
        Add item to buffer

        Args:
            item: Item to add
            timeout: Maximum time to wait for space (None = no timeout)

        Returns:
            True if item was added, False if buffer is full and strategy rejects
        """
        if self._closed:
            raise BufferError("Cannot write to closed buffer")

        start_time = time.perf_counter()

        try:
            with self._lock:
                # Handle different overflow strategies
                if self._size == self.capacity:
                    success = self._handle_overflow(item, timeout)
                    if not success:
                        return False
                else:
                    self._add_item(item)

                # Update metrics
                self._metrics.total_writes += 1
                write_time = (time.perf_counter() - start_time) * 1000
                self._update_write_time(write_time)

                # Signal readers
                self._write_event.set()
                self._write_event.clear()

                return True

        except Exception as e:
            logger.error(f"Error writing to buffer '{self.name}': {e}")
            raise BufferError(f"Write failed: {str(e)}")

    def get(self, timeout: Optional[float] = None) -> Optional[T]:
        """
        Get item from buffer

        Args:
            timeout: Maximum time to wait for item (None = no timeout)

        Returns:
            Item if available, None if timeout or buffer is empty
        """
        if self._closed and self._size == 0:
            return None

        start_time = time.perf_counter()
        deadline = start_time + timeout if timeout else None

        try:
            while True:
                with self._lock:
                    if self._size > 0:
                        item = self._remove_item()

                        # Update metrics
                        self._metrics.total_reads += 1
                        read_time = (time.perf_counter() - start_time) * 1000
                        self._update_read_time(read_time)

                        # Signal writers
                        self._read_event.set()
                        self._read_event.clear()

                        return item

                    if self._closed:
                        return None

                # Wait for data or timeout
                if deadline and time.perf_counter() >= deadline:
                    return None

                # Wait for write event (with timeout)
                wait_time = min(0.001, deadline - time.perf_counter()) if deadline else 0.001
                self._write_event.wait(timeout=wait_time)

        except Exception as e:
            logger.error(f"Error reading from buffer '{self.name}': {e}")
            raise BufferError(f"Read failed: {str(e)}")

    def get_many(self, count: int, timeout: Optional[float] = None) -> List[T]:
        """
        Get multiple items from buffer efficiently

        Args:
            count: Number of items to get
            timeout: Maximum time to wait

        Returns:
            List of items (may be fewer than requested if timeout)
        """
        items = []
        deadline = time.perf_counter() + timeout if timeout else None

        for _ in range(count):
            remaining_time = deadline - time.perf_counter() if deadline else None
            if remaining_time is not None and remaining_time <= 0:
                break

            item = self.get(timeout=remaining_time)
            if item is None:
                break

            items.append(item)

        return items

    def put_many(self, items: List[T], timeout: Optional[float] = None) -> int:
        """
        Put multiple items into buffer efficiently

        Args:
            items: Items to add
            timeout: Maximum time to wait for space

        Returns:
            Number of items actually added
        """
        added_count = 0
        deadline = time.perf_counter() + timeout if timeout else None

        for item in items:
            remaining_time = deadline - time.perf_counter() if deadline else None
            if remaining_time is not None and remaining_time <= 0:
                break

            if self.put(item, timeout=remaining_time):
                added_count += 1
            else:
                break

        return added_count

    def peek(self) -> Optional[T]:
        """
        Peek at next item without removing it

        Returns:
            Next item if available, None if empty
        """
        with self._lock:
            if self._size > 0:
                return self._buffer[self._tail]
            return None

    def clear(self):
        """Clear all items from buffer"""
        with self._lock:
            self._buffer = [None] * self.capacity
            self._head = 0
            self._tail = 0
            self._size = 0
            self._state = BufferState.EMPTY
            logger.debug(f"Buffer '{self.name}' cleared")

    def close(self):
        """Close buffer and release resources"""
        with self._lock:
            self._closed = True
            self._state = BufferState.CLOSED

        # Wake up any waiting threads
        self._write_event.set()
        self._read_event.set()

        logger.info(f"Buffer '{self.name}' closed")

    def is_empty(self) -> bool:
        """Check if buffer is empty"""
        with self._lock:
            return self._size == 0

    def is_full(self) -> bool:
        """Check if buffer is full"""
        with self._lock:
            return self._size == self.capacity

    def size(self) -> int:
        """Get current number of items in buffer"""
        with self._lock:
            return self._size

    def remaining_capacity(self) -> int:
        """Get remaining capacity"""
        with self._lock:
            return self.capacity - self._size

    def get_state(self) -> BufferState:
        """Get current buffer state"""
        with self._lock:
            return self._state

    def get_metrics(self) -> BufferMetrics:
        """Get buffer performance metrics"""
        with self._lock:
            metrics = BufferMetrics(
                total_writes=self._metrics.total_writes,
                total_reads=self._metrics.total_reads,
                dropped_frames=self._metrics.dropped_frames,
                overrun_events=self._metrics.overrun_events,
                current_fill_level=self._size,
                max_fill_level=self._metrics.max_fill_level,
                avg_write_time_ms=self._metrics.avg_write_time_ms,
                avg_read_time_ms=self._metrics.avg_read_time_ms,
                memory_usage_bytes=self._estimate_memory_usage()
            )
            return metrics

    def reset_metrics(self):
        """Reset performance metrics"""
        with self._lock:
            self._metrics = BufferMetrics()
            self._write_times.clear()
            self._read_times.clear()

    def __len__(self) -> int:
        """Get current size"""
        return self.size()

    def __iter__(self) -> Iterator[T]:
        """Iterate through buffer contents (non-destructive)"""
        with self._lock:
            for i in range(self._size):
                idx = (self._tail + i) % self.capacity
                yield self._buffer[idx]

    def __contains__(self, item: T) -> bool:
        """Check if item is in buffer"""
        with self._lock:
            for i in range(self._size):
                idx = (self._tail + i) % self.capacity
                if self._buffer[idx] == item:
                    return True
            return False

    def __repr__(self) -> str:
        """String representation"""
        with self._lock:
            return (f"RingBuffer(name='{self.name}', capacity={self.capacity}, "
                   f"size={self._size}, state={self._state.value})")

    # Private methods

    def _add_item(self, item: T):
        """Add item to buffer (assumes lock is held)"""
        self._buffer[self._head] = item
        self._head = (self._head + 1) % self.capacity
        self._size += 1

        # Update state
        if self._size == self.capacity:
            self._state = BufferState.FULL
        else:
            self._state = BufferState.FILLING

        # Update metrics
        self._metrics.max_fill_level = max(self._metrics.max_fill_level, self._size)

    def _remove_item(self) -> T:
        """Remove item from buffer (assumes lock is held)"""
        item = self._buffer[self._tail]
        self._buffer[self._tail] = None  # Help GC
        self._tail = (self._tail + 1) % self.capacity
        self._size -= 1

        # Update state
        if self._size == 0:
            self._state = BufferState.EMPTY
        else:
            self._state = BufferState.FILLING

        return item

    def _handle_overflow(self, item: T, timeout: Optional[float]) -> bool:
        """Handle buffer overflow according to strategy"""
        if self.overflow_strategy == OverflowStrategy.DROP_OLDEST:
            # Remove oldest item and add new one
            self._remove_item()
            self._add_item(item)
            self._metrics.dropped_frames += 1
            self._state = BufferState.OVERRUN
            return True

        elif self.overflow_strategy == OverflowStrategy.DROP_NEWEST:
            # Reject new item
            self._metrics.dropped_frames += 1
            return False

        elif self.overflow_strategy == OverflowStrategy.EXPAND:
            # Expand buffer capacity
            self._expand_buffer()
            self._add_item(item)
            return True

        elif self.overflow_strategy == OverflowStrategy.BLOCK:
            # Wait for space (timeout handled by caller)
            return False

        else:
            raise BufferError(f"Unknown overflow strategy: {self.overflow_strategy}")

    def _expand_buffer(self):
        """Expand buffer capacity dynamically"""
        new_capacity = int(self.capacity * 1.5)
        logger.info(f"Expanding buffer '{self.name}' from {self.capacity} to {new_capacity}")

        # Create new buffer
        new_buffer = [None] * new_capacity

        # Copy existing data in order
        for i in range(self._size):
            src_idx = (self._tail + i) % self.capacity
            new_buffer[i] = self._buffer[src_idx]

        # Update buffer
        self._buffer = new_buffer
        self.capacity = new_capacity
        self._tail = 0
        self._head = self._size

    def _update_write_time(self, write_time_ms: float):
        """Update average write time"""
        self._write_times.append(write_time_ms)
        if len(self._write_times) > 1000:  # Keep last 1000 measurements
            self._write_times.pop(0)

        self._metrics.avg_write_time_ms = sum(self._write_times) / len(self._write_times)

    def _update_read_time(self, read_time_ms: float):
        """Update average read time"""
        self._read_times.append(read_time_ms)
        if len(self._read_times) > 1000:  # Keep last 1000 measurements
            self._read_times.pop(0)

        self._metrics.avg_read_time_ms = sum(self._read_times) / len(self._read_times)

    def _estimate_memory_usage(self) -> int:
        """Estimate memory usage in bytes"""
        # Rough estimate based on capacity and element size hint
        base_overhead = 1024  # Object overhead
        buffer_size = self.capacity * self.element_size_hint
        return base_overhead + buffer_size


class TypedRingBuffer(RingBuffer[T]):
    """Ring buffer with type-specific optimizations"""

    def __init__(
        self,
        capacity: int,
        element_type: type,
        overflow_strategy: OverflowStrategy = OverflowStrategy.DROP_OLDEST,
        name: Optional[str] = None
    ):
        self.element_type = element_type

        # Estimate element size based on type
        element_size = self._estimate_element_size(element_type)

        super().__init__(capacity, overflow_strategy, name, element_size)

    def _estimate_element_size(self, element_type: type) -> int:
        """Estimate element size in bytes"""
        if element_type == int:
            return 8
        elif element_type == float:
            return 8
        elif element_type == str:
            return 100  # Rough estimate
        elif element_type == bytes:
            return 1024  # Rough estimate
        elif hasattr(element_type, '__sizeof__'):
            try:
                return element_type().__sizeof__()
            except:
                pass

        return 1024  # Default estimate


class FrameBuffer(TypedRingBuffer[np.ndarray]):
    """
    Specialized ring buffer for image frames

    Optimized for numpy arrays representing image data
    """

    def __init__(
        self,
        capacity: int,
        frame_shape: Tuple[int, ...],
        dtype: np.dtype = np.uint16,
        overflow_strategy: OverflowStrategy = OverflowStrategy.DROP_OLDEST,
        name: Optional[str] = None
    ):
        self.frame_shape = frame_shape
        self.dtype = dtype

        # Calculate frame size
        frame_size = int(np.prod(frame_shape) * np.dtype(dtype).itemsize)

        super().__init__(
            capacity=capacity,
            element_type=np.ndarray,
            overflow_strategy=overflow_strategy,
            name=name or "FrameBuffer"
        )

        self.element_size_hint = frame_size

        logger.info(
            f"Frame buffer '{self.name}' created: "
            f"capacity={capacity}, shape={frame_shape}, dtype={dtype}"
        )

    def put_frame(self, frame: np.ndarray, validate: bool = True) -> bool:
        """
        Add frame with optional validation

        Args:
            frame: Numpy array frame
            validate: Whether to validate frame shape/dtype

        Returns:
            True if frame was added successfully
        """
        if validate:
            if frame.shape != self.frame_shape:
                raise BufferError(
                    f"Frame shape mismatch: expected {self.frame_shape}, "
                    f"got {frame.shape}"
                )

            if frame.dtype != self.dtype:
                logger.warning(
                    f"Frame dtype mismatch: expected {self.dtype}, "
                    f"got {frame.dtype}. Converting..."
                )
                frame = frame.astype(self.dtype)

        return self.put(frame)

    def get_frame_copy(self, timeout: Optional[float] = None) -> Optional[np.ndarray]:
        """Get frame as a copy (safer for concurrent access)"""
        frame = self.get(timeout)
        return frame.copy() if frame is not None else None

    def get_latest_frames(self, count: int) -> List[np.ndarray]:
        """Get the most recent frames (up to count)"""
        with self._lock:
            available = min(count, self._size)
            frames = []

            for i in range(available):
                # Get frames from most recent backwards
                idx = (self._head - 1 - i) % self.capacity
                frame = self._buffer[idx]
                if frame is not None:
                    frames.append(frame.copy())

            return frames

    def calculate_frame_rate(self, window_seconds: float = 1.0) -> float:
        """Calculate approximate frame rate based on recent activity"""
        recent_writes = 0
        current_time = time.time()

        # Count recent writes (simplified - would need timestamp tracking)
        # For now, estimate based on average write time
        if self._metrics.avg_write_time_ms > 0:
            writes_per_second = 1000 / self._metrics.avg_write_time_ms
            return min(writes_per_second, self._metrics.total_writes)

        return 0.0


class BufferManager:
    """
    Manager for multiple ring buffers

    Provides centralized management and monitoring of buffer pools
    """

    def __init__(self, name: str = "BufferManager"):
        self.name = name
        self._buffers: Dict[str, RingBuffer] = {}
        self._lock = Lock()

        logger.info(f"Buffer manager '{self.name}' initialized")

    def create_buffer(
        self,
        buffer_id: str,
        capacity: int,
        overflow_strategy: OverflowStrategy = OverflowStrategy.DROP_OLDEST,
        buffer_type: str = "generic"
    ) -> RingBuffer:
        """Create and register a new buffer"""
        with self._lock:
            if buffer_id in self._buffers:
                raise BufferError(f"Buffer '{buffer_id}' already exists")

            if buffer_type == "frame":
                # Would need additional parameters for frame buffer
                buffer = RingBuffer(capacity, overflow_strategy, buffer_id)
            else:
                buffer = RingBuffer(capacity, overflow_strategy, buffer_id)

            self._buffers[buffer_id] = buffer
            logger.info(f"Created buffer '{buffer_id}' with capacity {capacity}")

            return buffer

    def get_buffer(self, buffer_id: str) -> Optional[RingBuffer]:
        """Get existing buffer by ID"""
        with self._lock:
            return self._buffers.get(buffer_id)

    def remove_buffer(self, buffer_id: str) -> bool:
        """Remove and close buffer"""
        with self._lock:
            buffer = self._buffers.pop(buffer_id, None)
            if buffer:
                buffer.close()
                logger.info(f"Removed buffer '{buffer_id}'")
                return True
            return False

    def list_buffers(self) -> List[str]:
        """List all buffer IDs"""
        with self._lock:
            return list(self._buffers.keys())

    def get_all_metrics(self) -> Dict[str, BufferMetrics]:
        """Get metrics for all buffers"""
        with self._lock:
            metrics = {}
            for buffer_id, buffer in self._buffers.items():
                metrics[buffer_id] = buffer.get_metrics()
            return metrics

    def close_all(self):
        """Close all managed buffers"""
        with self._lock:
            for buffer in self._buffers.values():
                buffer.close()
            self._buffers.clear()
            logger.info(f"All buffers in manager '{self.name}' closed")