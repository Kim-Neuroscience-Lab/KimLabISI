"""
Acquisition Data Formatter

This module handles all data formatting and processing for acquisition viewport display.
ALL business logic for transforming raw acquisition data into chart-ready formats
belongs here, NOT in the frontend.

Functions:
    - format_histogram_chart_data: Transform histogram data into Chart.js format
    - format_correlation_chart_data: Transform correlation data into Chart.js format
    - format_elapsed_time: Format elapsed time as HH:MM:SS:FF
"""

from typing import Dict, Any, List, Optional
import numpy as np


def format_histogram_chart_data(histogram: np.ndarray, bin_edges: np.ndarray, statistics: Dict[str, float]) -> Dict[str, Any]:
    """
    Format histogram data for Chart.js display.

    Args:
        histogram: Array of histogram bin counts
        bin_edges: Array of histogram bin edges
        statistics: Dictionary with 'mean' and 'std' keys

    Returns:
        Dictionary with 'labels', 'data', and 'statistics' keys ready for Chart.js
    """
    # Create labels from bin edges (show every 32nd bin for readability)
    labels = []
    for i in range(len(bin_edges) - 1):
        if i % 32 == 0:
            labels.append(str(round(bin_edges[i])))
        else:
            labels.append('')

    # Convert histogram to list of integers
    data = histogram.astype(int).tolist()

    return {
        'labels': labels,
        'data': data,
        'statistics': {
            'mean': round(statistics.get('mean', 0), 1),
            'std': round(statistics.get('std', 0), 1)
        }
    }


def format_correlation_chart_data(
    synchronization: List[Dict[str, Any]],
    statistics: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Format correlation/timing data for Chart.js line chart display.

    This function:
    1. Filters to only valid time differences (no null/undefined)
    2. Converts timestamps to relative time (seconds from start)
    3. Extracts time differences in milliseconds
    4. Returns Chart.js-ready data structure

    Args:
        synchronization: List of synchronization records with:
            - camera_timestamp: Camera timestamp in microseconds
            - time_difference_ms: Time difference in milliseconds (can be None)
        statistics: Optional dict with correlation statistics

    Returns:
        Dictionary with 'labels', 'data', and 'statistics' keys ready for Chart.js
        Returns empty structure if no valid data
    """
    # Check if we have synchronization data with actual matches
    if not synchronization or not statistics or statistics.get('matched_count', 0) == 0:
        return {
            'labels': [],
            'data': [],
            'statistics': None
        }

    # Filter to only include entries with valid time differences (no null/undefined)
    valid_data = [
        entry for entry in synchronization
        if entry.get('time_difference_ms') is not None
    ]

    if len(valid_data) == 0:
        return {
            'labels': [],
            'data': [],
            'statistics': None
        }

    # Get the earliest timestamp for relative time calculation
    earliest_timestamp = min(entry['camera_timestamp'] for entry in valid_data)

    # Convert to relative time (seconds from start) and time difference (milliseconds)
    time_points = [
        (entry['camera_timestamp'] - earliest_timestamp) / 1_000_000  # Convert to seconds
        for entry in valid_data
    ]

    time_diffs = [
        entry['time_difference_ms']  # Already in milliseconds
        for entry in valid_data
    ]

    # Format labels as strings with 2 decimal places
    labels = [f"{t:.2f}" for t in time_points]

    return {
        'labels': labels,
        'data': time_diffs,
        'statistics': {
            'mean_diff_ms': round(statistics.get('mean_diff_ms', 0), 2),
            'std_diff_ms': round(statistics.get('std_diff_ms', 0), 2),
            'matched_count': statistics.get('matched_count', 0)
        }
    }


def format_elapsed_time(start_time_ms: int, current_frame_count: int, camera_fps: float = 30.0) -> str:
    """
    Format elapsed time as HH:MM:SS:FF (hours:minutes:seconds:frames).

    Args:
        start_time_ms: Acquisition start time in milliseconds (from epoch)
        current_frame_count: Current frame count
        camera_fps: Camera frames per second (default 30.0)

    Returns:
        Formatted time string as 'HH:MM:SS:FF'
    """
    import time

    # Calculate elapsed milliseconds
    elapsed_ms = int(time.time() * 1000) - start_time_ms

    # Break down into components
    hours = elapsed_ms // 3600000
    minutes = (elapsed_ms % 3600000) // 60000
    seconds = (elapsed_ms % 60000) // 1000

    # Calculate frames (modulo fps)
    frames = current_frame_count % int(camera_fps)

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


def format_camera_correlation_statistics(timing_correlations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate and format camera-stimulus timing correlation statistics.

    Args:
        timing_correlations: List of correlation records with:
            - correlation_status: 'matched' or 'timeout'
            - time_difference: Time difference in microseconds (optional)

    Returns:
        Dictionary with formatted statistics for display
    """
    if not timing_correlations:
        return {
            'total': 0,
            'matched': 0,
            'timeout': 0,
            'match_rate_percent': 0
        }

    total = len(timing_correlations)
    matched = sum(1 for c in timing_correlations if c.get('correlation_status') == 'matched')
    timeout = sum(1 for c in timing_correlations if c.get('correlation_status') == 'timeout')
    match_rate = (matched / total * 100) if total > 0 else 0

    return {
        'total': total,
        'matched': matched,
        'timeout': timeout,
        'match_rate_percent': round(match_rate, 0)
    }


def format_time_ago(timestamp_us: int, current_time_us: int) -> str:
    """
    Format time difference as 'X.Xs ago'.

    Args:
        timestamp_us: Event timestamp in microseconds
        current_time_us: Current time in microseconds

    Returns:
        Formatted string like '2.3s ago'
    """
    diff_seconds = (current_time_us - timestamp_us) / 1_000_000
    return f"{diff_seconds:.1f}s ago"
