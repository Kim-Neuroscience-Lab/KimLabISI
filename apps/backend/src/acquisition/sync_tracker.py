"""Camera-stimulus timestamp synchronization tracking.

Refactored from isi_control/timestamp_synchronization_tracker.py with KISS approach.
This file was already perfect - no service_locator dependencies!
"""

from typing import Optional, Dict, Any, List
import threading
import logging

import numpy as np

logger = logging.getLogger(__name__)


class TimestampSynchronizationTracker:
    """Tracks and analyzes camera-stimulus timestamp synchronization quality."""

    def __init__(self, max_history: int = 100000):
        """
        Initialize the timestamp synchronization tracker.

        Args:
            max_history: Maximum number of synchronization entries to retain
                       Default 100,000 entries supports ~30 minutes at 60fps
        """
        self.synchronization_history: List[Dict[str, Any]] = []
        self.max_history = max_history
        self._enabled = False
        self._lock = threading.RLock()  # Thread-safe access to synchronization_history

    def enable(self) -> None:
        """Enable timestamp synchronization tracking."""
        with self._lock:
            self._enabled = True
        logger.info("Timestamp synchronization tracking enabled")

    def disable(self) -> None:
        """Disable timestamp synchronization tracking."""
        with self._lock:
            self._enabled = False
        logger.info("Timestamp synchronization tracking disabled")

    def clear(self) -> None:
        """Clear all synchronization history."""
        with self._lock:
            previous_count = len(self.synchronization_history)
            self.synchronization_history.clear()
            logger.info(f"Synchronization history cleared (removed {previous_count} entries)")

    def record_synchronization(
        self,
        camera_timestamp_us: int,
        stimulus_timestamp_us: Optional[int],
        frame_id: Optional[int],
    ) -> None:
        """
        Record a camera-stimulus timestamp synchronization sample.

        Only records synchronization when:
        - Tracking is enabled
        - Stimulus timestamp is available
        - Timestamps are recent (within 100ms of each other)

        The timestamp age validation filters out stale timestamps from
        previous stimulus phases, preventing synchronization plot spikes
        during phase transitions while maintaining continuous tracking.

        Args:
            camera_timestamp_us: Camera timestamp in microseconds
            stimulus_timestamp_us: Stimulus timestamp in microseconds (None if no match)
            frame_id: Stimulus frame ID (None if no match)
        """
        # Check if tracking is enabled (with lock for thread safety)
        with self._lock:
            if not self._enabled:
                logger.debug(f"Timestamp synchronization tracking disabled, skipping (cam_ts={camera_timestamp_us})")
                return

        # Early exit checks (no lock needed)
        if stimulus_timestamp_us is None:
            logger.debug(f"No stimulus timestamp, skipping (cam_ts={camera_timestamp_us})")
            return

        # Validate timestamps are recent to avoid synchronization spikes from stale data
        # Only record if timestamps are within reasonable window
        time_diff_us = abs(camera_timestamp_us - stimulus_timestamp_us)
        MAX_SYNC_AGE_US = 100_000  # 100ms

        if time_diff_us >= MAX_SYNC_AGE_US:
            # Timestamp too old - likely from previous stimulus phase
            # Skip to prevent synchronization plot spikes during phase transitions
            logger.info(
                f"REJECTED stale synchronization: timestamp age {time_diff_us/1000:.1f}ms "
                f"exceeds maximum {MAX_SYNC_AGE_US/1000:.0f}ms "
                f"(cam={camera_timestamp_us}, stim={stimulus_timestamp_us})"
            )
            return

        # Calculate signed time difference for synchronization analysis
        signed_time_diff_us = camera_timestamp_us - stimulus_timestamp_us
        time_diff_ms = signed_time_diff_us / 1000.0

        # Append to history (with lock for thread safety)
        with self._lock:
            self.synchronization_history.append(
                {
                    "camera_timestamp": camera_timestamp_us,
                    "stimulus_timestamp": stimulus_timestamp_us,
                    "frame_id": frame_id,
                    "time_difference_us": signed_time_diff_us,
                    "time_difference_ms": time_diff_ms,
                }
            )

            # Log periodically for monitoring
            if len(self.synchronization_history) % 100 == 0:
                logger.info(f"Synchronization history: {len(self.synchronization_history)} entries recorded")

            # Maintain maximum history size
            if len(self.synchronization_history) > self.max_history:
                dropped = self.synchronization_history.pop(0)
                logger.warning(
                    f"Synchronization history limit reached ({self.max_history}), "
                    f"dropping oldest entry from {dropped['camera_timestamp']}"
                )

    def get_synchronization_data(self) -> Dict[str, Any]:
        """
        Return timestamp synchronization dataset and summary statistics.

        Returns the most recent 5 seconds of synchronization data based on
        synchronization timestamps (not wall-clock time). This ensures the
        plot "freezes" during non-stimulus periods rather than flushing.

        Returns:
            Dictionary containing synchronization list and statistics
        """
        with self._lock:
            # Return recent synchronization based on synchronization timestamps
            # During between-trials, this returns the same data, freezing the plot
            # rather than flushing it with empty data
            recent_entries = self._get_recent_synchronization_internal(window_seconds=5.0)

            if not recent_entries:
                return {
                    "synchronization": [],
                    "statistics": {
                        "count": 0,
                        "matched_count": 0,
                        "mean_diff_ms": 0.0,
                        "std_diff_ms": 0.0,
                        "min_diff_ms": 0.0,
                        "max_diff_ms": 0.0,
                        "histogram": [],
                        "bin_edges": [],
                    },
                }

            diffs_ms = np.array(
                [
                    c["time_difference_ms"]
                    for c in recent_entries
                    if c["time_difference_ms"] is not None
                ],
                dtype=float,
            )

            if diffs_ms.size == 0:
                stats = {
                    "count": len(recent_entries),
                    "matched_count": 0,
                    "mean_diff_ms": 0.0,
                    "std_diff_ms": 0.0,
                    "min_diff_ms": 0.0,
                    "max_diff_ms": 0.0,
                    "histogram": [],
                    "bin_edges": [],
                }
            else:
                hist, bin_edges = np.histogram(diffs_ms, bins=50)

                stats = {
                    "count": len(recent_entries),
                    "matched_count": int(diffs_ms.size),
                    "mean_diff_ms": float(np.mean(diffs_ms)),
                    "std_diff_ms": float(np.std(diffs_ms)),
                    "min_diff_ms": float(np.min(diffs_ms)),
                    "max_diff_ms": float(np.max(diffs_ms)),
                    "histogram": hist.tolist(),
                    "bin_edges": bin_edges.tolist(),
                }

            # Include window metadata for debugging
            window_info = {}
            if self.synchronization_history:
                window_info = {
                    "window_anchor_timestamp": self.synchronization_history[-1]["camera_timestamp"],
                    "window_start_timestamp": self.synchronization_history[-1]["camera_timestamp"] - (5.0 * 1_000_000),
                    "total_history_count": len(self.synchronization_history),
                    "window_entry_count": len(recent_entries),
                }

            result = {
                "synchronization": recent_entries,
                "statistics": stats,
                "window_info": window_info,
            }

            logger.info(
                f"get_synchronization_data: {len(recent_entries)} entries in window "
                f"(total history: {len(self.synchronization_history)}), "
                f"window_anchor={window_info.get('window_anchor_timestamp', 'N/A')}, "
                f"enabled={self._enabled}"
            )

            return result

    def _get_recent_synchronization_internal(
        self, window_seconds: float = 5.0
    ) -> List[Dict[str, Any]]:
        """
        Internal method to get recent synchronization WITHOUT acquiring lock.
        Must be called while holding self._lock.

        Args:
            window_seconds: Time window to retrieve (default: 5.0 seconds)

        Returns:
            List of synchronization entries within the time window
        """
        if not self.synchronization_history:
            return []

        # Use most recent SYNCHRONIZATION timestamp, not wall-clock time
        # This freezes the window during between-trials periods
        latest_timestamp = self.synchronization_history[-1]["camera_timestamp"]
        threshold = latest_timestamp - (window_seconds * 1_000_000)

        recent = [
            entry
            for entry in self.synchronization_history
            if entry["camera_timestamp"] >= threshold
        ]

        return recent

    def get_recent_synchronization(
        self, window_seconds: float = 5.0
    ) -> List[Dict[str, Any]]:
        """
        Return synchronization within the most recent window based on synchronization timestamps.

        Uses the most recent synchronization's timestamp as the anchor, not wall-clock time.
        This ensures the window "freezes" during non-stimulus periods rather than
        advancing and flushing the data.

        Args:
            window_seconds: Time window to retrieve (default: 5.0 seconds)

        Returns:
            List of synchronization entries within the time window
        """
        with self._lock:
            return self._get_recent_synchronization_internal(window_seconds)

    @property
    def is_enabled(self) -> bool:
        """Check if timestamp synchronization tracking is enabled."""
        with self._lock:
            return self._enabled
