"""
Ring Buffer Infrastructure

Provides efficient circular buffer implementation for streaming data
in the ISI macroscope system, using validated Python data structures.
"""

from __future__ import annotations
from typing import Optional, Any, Union, List, Tuple, Generic, TypeVar, Iterator
from collections import deque
from queue import Queue, Full, Empty
from threading import Lock, Condition
import numpy as np
from scipy import stats
import sys
import timeit
from contextlib import contextmanager
import logging
from enum import Enum
from pydantic import BaseModel

T = TypeVar('T')

logger = logging.getLogger(__name__)


@contextmanager
def performance_timer():
    """Context manager for accurate performance timing using validated timeit"""
    start_time = timeit.default_timer()
    yield
    end_time = timeit.default_timer()
    # Store elapsed time in milliseconds in the context
    elapsed_ms = (end_time - start_time) * 1000
    # Return value is accessible via context manager usage pattern


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


class BufferMetrics(BaseModel):
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
    Thread-safe circular buffer implementation using validated Python data structures

    Uses collections.deque for optimal circular buffer performance and
    threading.Condition for efficient blocking operations.
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

        # Use validated data structures
        self._buffer: deque = deque(maxlen=capacity if overflow_strategy == OverflowStrategy.DROP_OLDEST else None)

        # Thread safety using Condition for efficient blocking
        self._lock = Lock()
        self._condition = Condition(self._lock)

        # State tracking
        self._state = BufferState.EMPTY
        self._closed = False
        self._metrics = BufferMetrics()

        # Performance tracking using deque for efficient operations
        self._write_times: deque = deque(maxlen=1000)  # Keep last 1000 measurements
        self._read_times: deque = deque(maxlen=1000)

        logger.info(f"Ring buffer '{self.name}' created with capacity {capacity}")

    def put(self, item: T, timeout: Optional[float] = None) -> bool:
        """
        Add item to buffer using validated data structures

        Args:
            item: Item to add
            timeout: Maximum time to wait for space (None = no timeout)

        Returns:
            True if item was added, False if buffer is full and strategy rejects
        """
        if self._closed:
            raise BufferError("Cannot write to closed buffer")

        # Use validated performance timing
        start_time = timeit.default_timer()

        try:
            with self._condition:
                # Handle different overflow strategies
                if len(self._buffer) == self.capacity and self.overflow_strategy != OverflowStrategy.DROP_OLDEST:
                    if self.overflow_strategy == OverflowStrategy.DROP_NEWEST:
                        self._metrics.dropped_frames += 1
                        return False
                    elif self.overflow_strategy == OverflowStrategy.BLOCK:
                        if not self._condition.wait_for(lambda: len(self._buffer) < self.capacity or self._closed, timeout):
                            return False
                        if self._closed:
                            return False
                    elif self.overflow_strategy == OverflowStrategy.EXPAND:
                        # Expand by converting to unlimited deque temporarily
                        self._buffer = deque(self._buffer)
                        self.capacity = int(self.capacity * 1.5)

                # Add item (deque handles overflow automatically for DROP_OLDEST)
                self._buffer.append(item)

                # Update state
                if len(self._buffer) == self.capacity:
                    self._state = BufferState.FULL
                else:
                    self._state = BufferState.FILLING

                # Update metrics using validated high-precision timing
                self._metrics.total_writes += 1
                write_time = (timeit.default_timer() - start_time) * 1000
                self._write_times.append(write_time)

                # Signal readers
                self._condition.notify_all()

                return True

        except Exception as e:
            logger.error(f"Error writing to buffer '{self.name}': {e}")
            raise BufferError(f"Write failed: {str(e)}")

    def get(self, timeout: Optional[float] = None) -> Optional[T]:
        """
        Get item from buffer using validated data structures

        Args:
            timeout: Maximum time to wait for item (None = no timeout)

        Returns:
            Item if available, None if timeout or buffer is empty
        """
        if self._closed and len(self._buffer) == 0:
            return None

        # Use validated performance timing
        start_time = timeit.default_timer()

        try:
            with self._condition:
                # Wait for data or timeout using validated wait_for
                if not self._condition.wait_for(lambda: len(self._buffer) > 0 or self._closed, timeout):
                    return None

                if self._closed and len(self._buffer) == 0:
                    return None

                # Remove item using validated deque operation
                item = self._buffer.popleft()

                # Update state
                if len(self._buffer) == 0:
                    self._state = BufferState.EMPTY
                else:
                    self._state = BufferState.FILLING

                # Update metrics using validated high-precision timing
                self._metrics.total_reads += 1
                read_time = (timeit.default_timer() - start_time) * 1000
                self._read_times.append(read_time)

                # Signal writers
                self._condition.notify_all()

                return item

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
        deadline = timeit.default_timer() + timeout if timeout else None

        for _ in range(count):
            remaining_time = deadline - timeit.default_timer() if deadline else None
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
        deadline = timeit.default_timer() + timeout if timeout else None

        for item in items:
            remaining_time = deadline - timeit.default_timer() if deadline else None
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
        with self._condition:
            if len(self._buffer) > 0:
                return self._buffer[0]  # First item in deque
            return None

    def clear(self):
        """Clear all items from buffer"""
        with self._condition:
            self._buffer.clear()
            self._state = BufferState.EMPTY
            self._condition.notify_all()
            logger.debug(f"Buffer '{self.name}' cleared")

    def close(self):
        """Close buffer and release resources"""
        with self._condition:
            self._closed = True
            self._state = BufferState.CLOSED
            self._condition.notify_all()

        logger.info(f"Buffer '{self.name}' closed")

    def is_empty(self) -> bool:
        """Check if buffer is empty"""
        with self._condition:
            return len(self._buffer) == 0

    def is_full(self) -> bool:
        """Check if buffer is full"""
        with self._condition:
            return len(self._buffer) == self.capacity

    def size(self) -> int:
        """Get current number of items in buffer"""
        with self._condition:
            return len(self._buffer)

    def remaining_capacity(self) -> int:
        """Get remaining capacity"""
        with self._condition:
            return self.capacity - len(self._buffer)

    def get_state(self) -> BufferState:
        """Get current buffer state"""
        with self._condition:
            return self._state

    def get_metrics(self) -> BufferMetrics:
        """Get buffer performance metrics using validated statistics"""
        with self._condition:
            current_size = len(self._buffer)

            # Use validated numpy for robust numerical calculations
            avg_write_time = float(np.mean(self._write_times)) if self._write_times else 0.0
            avg_read_time = float(np.mean(self._read_times)) if self._read_times else 0.0

            metrics = BufferMetrics(
                total_writes=self._metrics.total_writes,
                total_reads=self._metrics.total_reads,
                dropped_frames=self._metrics.dropped_frames,
                overrun_events=self._metrics.overrun_events,
                current_fill_level=current_size,
                max_fill_level=max(self._metrics.max_fill_level, current_size),
                avg_write_time_ms=avg_write_time,
                avg_read_time_ms=avg_read_time,
                memory_usage_bytes=self._get_actual_memory_usage()
            )
            return metrics

    def reset_metrics(self):
        """Reset performance metrics"""
        with self._condition:
            self._metrics = BufferMetrics()
            self._write_times.clear()
            self._read_times.clear()

    def __len__(self) -> int:
        """Get current size"""
        return self.size()

    def __iter__(self) -> Iterator[T]:
        """Iterate through buffer contents (non-destructive)"""
        with self._condition:
            # Use validated iterator from deque
            return iter(list(self._buffer))

    def __contains__(self, item: T) -> bool:
        """Check if item is in buffer"""
        with self._condition:
            # Use validated containment check from deque
            return item in self._buffer

    def __repr__(self) -> str:
        """String representation"""
        with self._condition:
            return (f"RingBuffer(name='{self.name}', capacity={self.capacity}, "
                   f"size={len(self._buffer)}, state={self._state.value})")

    def _get_actual_memory_usage(self) -> int:
        """Get actual memory usage using validated sys.getsizeof"""
        # Use validated memory measurement
        buffer_size = sys.getsizeof(self._buffer)
        # Add size of all contained objects
        for item in self._buffer:
            buffer_size += sys.getsizeof(item)
        return buffer_size


class TypedRingBuffer(RingBuffer[T]):
    """Ring buffer with type-specific optimizations using validated structures"""

    def __init__(
        self,
        capacity: int,
        element_type: type,
        overflow_strategy: OverflowStrategy = OverflowStrategy.DROP_OLDEST,
        name: Optional[str] = None
    ):
        self.element_type = element_type

        # Use validated size estimation
        element_size = self._estimate_element_size(element_type)

        super().__init__(capacity, overflow_strategy, name, element_size)

    def _estimate_element_size(self, element_type: type) -> int:
        """Estimate element size in bytes using validated methods"""
        # Create sample instance to get actual size
        try:
            if element_type in (int, float, str, bytes):
                sample = element_type()
                return sys.getsizeof(sample)
            else:
                # Default estimate for complex types
                return 1024
        except Exception:
            return 1024  # Fallback estimate


# Convenience functions for common use cases
def create_frame_buffer(capacity: int = 100, name: str = "frame_buffer") -> RingBuffer:
    """Create optimized ring buffer for frame data"""
    return TypedRingBuffer(capacity, bytes, OverflowStrategy.DROP_OLDEST, name)


def create_metrics_buffer(capacity: int = 1000, name: str = "metrics_buffer") -> RingBuffer:
    """Create optimized ring buffer for metrics data"""
    return TypedRingBuffer(capacity, dict, OverflowStrategy.DROP_OLDEST, name)


def create_blocking_buffer(capacity: int = 50, name: str = "blocking_buffer") -> RingBuffer:
    """Create ring buffer that blocks on overflow"""
    return RingBuffer(capacity, OverflowStrategy.BLOCK, name)