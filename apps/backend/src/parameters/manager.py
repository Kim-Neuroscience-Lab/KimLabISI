"""Parameter manager for runtime configuration.

This is a minimal replacement for the deleted isi_control.parameter_manager.
Provides mutable parameter management (unlike frozen AppConfig).
"""

import json
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Callable, List
from datetime import datetime

logger = logging.getLogger(__name__)


class ParameterManager:
    """Manages runtime parameters from JSON file.

    Provides mutable parameter access for runtime updates, unlike the
    frozen AppConfig which is immutable.

    Thread-safe with atomic file writes.

    VOLATILE PARAMETERS:
    Camera and monitor parameters are VOLATILE (runtime-only, never persisted).
    These are detected fresh on every startup for scientific reproducibility:
    - Different lab setups (office vs lab)
    - Hardware changes (cameras unplugged, monitors disconnected)
    - Multiple users on same machine
    - Scientific rigor (explicit hardware detection every time)

    Volatile groups are loaded from defaults on startup, then populated by
    hardware detection at runtime. They are NEVER written back to disk.
    """

    # Parameter groups that are NEVER persisted to disk (runtime-only)
    VOLATILE_GROUPS = {"camera", "monitor"}

    def __init__(self, config_file: str = "isi_parameters.json", config_dir: str = None):
        """Initialize parameter manager.

        Args:
            config_file: Name of the configuration file
            config_dir: Directory containing the configuration file
        """
        if config_dir is None:
            # Default to backend/config directory
            backend_root = Path(__file__).resolve().parents[2]
            config_dir = str(backend_root / "config")

        self.config_file = Path(config_dir) / config_file
        self._lock = threading.RLock()  # Thread-safe parameter updates
        self.data = self._load()

        # Subscription mechanism for parameter change notifications
        self._subscribers: Dict[str, List[Any]] = {}  # group_name -> [callbacks]
        self._subscriber_lock = threading.Lock()

        logger.info(f"ParameterManager initialized with {self.config_file}")
        logger.info(f"Volatile parameter groups (runtime-only): {self.VOLATILE_GROUPS}")

    def _load(self) -> Dict[str, Any]:
        """Load parameters from JSON file."""
        if not self.config_file.exists():
            logger.error(f"Configuration file not found: {self.config_file}")
            # Return minimal structure
            return {
                "config": {},
                "current": {},
                "default": {}
            }

        with open(self.config_file, 'r') as f:
            data = json.load(f)

        logger.info(f"Loaded parameters from {self.config_file}")
        return data

    def _save(self):
        """Save parameters to JSON file with atomic write.

        Uses temp file + rename for atomicity (no corruption on crash).

        CRITICAL: This NEVER saves volatile parameter groups (camera, monitor).
        Hardware parameters are detected fresh on every startup for scientific
        reproducibility and must not persist between sessions.
        """
        # Update last_modified timestamp
        if "current" in self.data and "session" in self.data["current"]:
            self.data["current"]["session"]["last_modified"] = datetime.now().isoformat()

        # Create a deep copy of data for saving, excluding volatile groups
        import copy
        data_to_save = copy.deepcopy(self.data)

        # Remove volatile parameter groups from the copy before saving
        # This ensures camera/monitor params are NEVER persisted to disk
        if "current" in data_to_save:
            for volatile_group in self.VOLATILE_GROUPS:
                if volatile_group in data_to_save["current"]:
                    # Log what we're NOT saving (for debugging)
                    logger.debug(
                        f"Skipping volatile group '{volatile_group}' from disk persistence "
                        f"(runtime-only hardware detection)"
                    )
                    # Keep structure but reset to defaults for clean JSON
                    default_group = self.data.get("default", {}).get(volatile_group, {})
                    data_to_save["current"][volatile_group] = copy.deepcopy(default_group)

        # Atomic write: write to temp file, then rename
        temp_file = self.config_file.with_suffix('.json.tmp')
        try:
            with open(temp_file, 'w') as f:
                json.dump(data_to_save, f, indent=2)
                f.flush()  # Flush to OS buffer

            # Atomic rename (replaces old file)
            temp_file.replace(self.config_file)

            logger.info(
                f"Saved parameters to {self.config_file} "
                f"(skipped volatile groups: {self.VOLATILE_GROUPS})"
            )
        except Exception as e:
            logger.error(f"Failed to save parameters: {e}")
            # Clean up temp file if it exists
            if temp_file.exists():
                temp_file.unlink()
            raise

    def get_all_parameters(self) -> Dict[str, Any]:
        """Get all current parameters.

        Returns:
            Dict with all parameter groups
        """
        with self._lock:
            return self.data.get("current", {})

    def get_parameter_group(self, group_name: str) -> Dict[str, Any]:
        """Get parameters for a specific group.

        Args:
            group_name: Name of the parameter group (e.g., "camera", "monitor")

        Returns:
            Dict with parameters for that group
        """
        with self._lock:
            current = self.data.get("current", {})
            return current.get(group_name, {})

    def update_parameter_group(self, group_name: str, updates: Dict[str, Any]):
        """Update parameters in a group (thread-safe with atomic file write).

        Args:
            group_name: Name of the parameter group
            updates: Dict with parameter updates

        Raises:
            ValueError: If parameter validation fails

        Note:
            Volatile groups (camera, monitor) are updated in-memory but
            never persisted to disk. They are re-detected on every startup.
        """
        with self._lock:
            if "current" not in self.data:
                self.data["current"] = {}

            if group_name not in self.data["current"]:
                self.data["current"][group_name] = {}

            # Get current values to merge with updates for validation
            current_group = self.data["current"][group_name].copy()
            current_group.update(updates)

            # Validate parameters BEFORE applying
            self._validate_parameter_group(group_name, current_group)

            # Update parameters in-memory
            self.data["current"][group_name].update(updates)

            # Save to file (atomic) - volatile groups will be automatically excluded
            self._save()

            # Log with clarity about volatile vs persistent
            if group_name in self.VOLATILE_GROUPS:
                logger.info(
                    f"Updated {group_name} parameters (runtime-only): {list(updates.keys())}"
                )
            else:
                logger.info(
                    f"Updated {group_name} parameters (persisted): {list(updates.keys())}"
                )

        # Notify subscribers AFTER releasing lock (avoid deadlock)
        self._notify_subscribers(group_name, updates)

    def get_parameter_info(self) -> Dict[str, Any]:
        """Get parameter configuration metadata.

        Returns:
            Dict with parameter_config (validation, types, etc.)
        """
        with self._lock:
            return {
                "parameter_config": self.data.get("config", {})
            }

    def reset_to_defaults(self):
        """Reset all parameters to default values (thread-safe with atomic file write)."""
        with self._lock:
            defaults = self.data.get("default", {})

            # Deep copy defaults to current
            import copy
            self.data["current"] = copy.deepcopy(defaults)

            # Save to file (atomic)
            self._save()

            logger.info("Parameters reset to defaults")

    def reload_from_disk(self):
        """Force reload parameters from disk and notify all subscribers.

        Useful when the config file was modified externally.
        """
        with self._lock:
            old_data = self.data.copy()
            self.data = self._load()

            logger.info("Parameters reloaded from disk")

            # Notify subscribers of all changed groups
            old_current = old_data.get("current", {})
            new_current = self.data.get("current", {})

            for group_name in set(list(old_current.keys()) + list(new_current.keys())):
                old_params = old_current.get(group_name, {})
                new_params = new_current.get(group_name, {})

                if old_params != new_params:
                    # Find what changed
                    changes = {}
                    for key in set(list(old_params.keys()) + list(new_params.keys())):
                        old_val = old_params.get(key)
                        new_val = new_params.get(key)
                        if old_val != new_val:
                            changes[key] = new_val

                    if changes:
                        logger.info(f"Detected changes in {group_name}: {list(changes.keys())}")
                        self._notify_subscribers(group_name, changes)

    def subscribe(self, group_name: str, callback) -> None:
        """Subscribe to parameter changes for a specific group.

        Args:
            group_name: Parameter group to monitor ("camera", "stimulus", etc.)
            callback: Function called with (group_name, updates) when parameters change
        """
        with self._subscriber_lock:
            if group_name not in self._subscribers:
                self._subscribers[group_name] = []
            self._subscribers[group_name].append(callback)
            logger.debug(f"Component subscribed to {group_name} parameter changes")

    def unsubscribe(self, group_name: str, callback) -> None:
        """Unsubscribe from parameter changes.

        Args:
            group_name: Parameter group name
            callback: Callback function to remove
        """
        with self._subscriber_lock:
            if group_name in self._subscribers:
                try:
                    self._subscribers[group_name].remove(callback)
                    logger.debug(f"Component unsubscribed from {group_name} parameter changes")
                except ValueError:
                    pass

    def _notify_subscribers(self, group_name: str, updates: Dict[str, Any]) -> None:
        """Notify all subscribers of parameter changes.

        Args:
            group_name: Parameter group that changed
            updates: Dictionary of updated parameters
        """
        with self._subscriber_lock:
            callbacks = self._subscribers.get(group_name, []).copy()

        for callback in callbacks:
            try:
                callback(group_name, updates)
            except Exception as e:
                logger.error(f"Error in parameter change callback: {e}", exc_info=True)

    def _validate_parameter_group(self, group_name: str, params: Dict[str, Any]) -> None:
        """Validate parameter group for scientific correctness.

        Args:
            group_name: Parameter group name
            params: Complete parameter group (current + updates merged)

        Raises:
            ValueError: If validation fails with detailed error message
        """
        # Stimulus parameter validation (CRITICAL for pattern rendering)
        if group_name == "stimulus":
            # Get background_luminance - REQUIRED parameter
            bg_lum = params.get("background_luminance")
            if bg_lum is None:
                raise ValueError(
                    "background_luminance is required in stimulus parameters. "
                    "Please ensure isi_parameters.json contains this parameter. "
                    "Recommended: background_luminance=0.5 for full [0,1] range."
                )

            # Get contrast - REQUIRED parameter
            contrast = params.get("contrast")
            if contrast is None:
                raise ValueError(
                    "contrast is required in stimulus parameters. "
                    "Please ensure isi_parameters.json contains this parameter. "
                    "Recommended: contrast=0.5 for full [0,1] range."
                )

            # CRITICAL: Background luminance must be >= contrast
            # Otherwise pattern goes negative and gets clamped to black
            if bg_lum < contrast:
                raise ValueError(
                    f"Invalid stimulus parameters: background_luminance ({bg_lum}) must be >= contrast ({contrast}). "
                    f"Otherwise the dark checkers will be clamped to black and invisible. "
                    f"Recommended: background_luminance=0.5, contrast=0.5 for full [0,1] range."
                )

            # Warn if background is at extremes (reduces visible contrast range)
            if bg_lum == 0.0:
                logger.warning(
                    f"background_luminance=0.0 with contrast={contrast} will produce pattern in range [0, {contrast}] "
                    f"(half of the checkerboard invisible). Recommended: background_luminance=0.5"
                )
            elif bg_lum == 1.0:
                logger.warning(
                    f"background_luminance=1.0 with contrast={contrast} will produce pattern in range [{1.0-contrast}, 1.0] "
                    f"(half of the checkerboard invisible). Recommended: background_luminance=0.5"
                )

            # Validate other stimulus parameters are reasonable
            checker_size = params.get("checker_size_deg")
            if checker_size is None:
                raise ValueError(
                    "checker_size_deg is required in stimulus parameters. "
                    "Please ensure isi_parameters.json contains this parameter. "
                    "Recommended: 10-30 degrees for mouse retinotopy."
                )

            bar_width = params.get("bar_width_deg")
            if bar_width is None:
                raise ValueError(
                    "bar_width_deg is required in stimulus parameters. "
                    "Please ensure isi_parameters.json contains this parameter. "
                    "Recommended: 10-30 degrees for mouse retinotopy."
                )

            # Checkerboard size sanity check (typical FOV is 70-120 degrees)
            if checker_size > 90:
                logger.warning(
                    f"checker_size_deg={checker_size} is unusually large (typical FOV is 70-120 deg). "
                    f"Recommended: 10-30 degrees for mouse retinotopy."
                )

            # Bar width sanity check
            if bar_width > 90:
                logger.warning(
                    f"bar_width_deg={bar_width} is unusually large (typical FOV is 70-120 deg). "
                    f"Recommended: 10-30 degrees for mouse retinotopy."
                )

        # Monitor parameter validation
        elif group_name == "monitor":
            width_px = params.get("monitor_width_px")
            if width_px is None:
                raise ValueError(
                    "monitor_width_px is required in monitor parameters. "
                    "Please ensure isi_parameters.json contains this parameter or run hardware detection."
                )

            height_px = params.get("monitor_height_px")
            if height_px is None:
                raise ValueError(
                    "monitor_height_px is required in monitor parameters. "
                    "Please ensure isi_parameters.json contains this parameter or run hardware detection."
                )

            fps = params.get("monitor_fps")
            if fps is None:
                raise ValueError(
                    "monitor_fps is required in monitor parameters. "
                    "Please ensure isi_parameters.json contains this parameter or run hardware detection."
                )

            if width_px <= 0 or height_px <= 0:
                raise ValueError(f"Invalid monitor resolution: {width_px}x{height_px}")

            if fps <= 0:
                raise ValueError(f"Invalid monitor frame rate: {fps} fps")

        # Camera parameter validation
        elif group_name == "camera":
            width_px = params.get("camera_width_px")
            if width_px is None:
                raise ValueError(
                    "camera_width_px is required in camera parameters. "
                    "Please ensure isi_parameters.json contains this parameter or run hardware detection."
                )

            height_px = params.get("camera_height_px")
            if height_px is None:
                raise ValueError(
                    "camera_height_px is required in camera parameters. "
                    "Please ensure isi_parameters.json contains this parameter or run hardware detection."
                )

            fps = params.get("camera_fps")
            if fps is None:
                raise ValueError(
                    "camera_fps is required in camera parameters. "
                    "Please ensure isi_parameters.json contains this parameter or run hardware detection."
                )

            # Allow -1 as sentinel for "not detected"
            if width_px != -1 and width_px <= 0:
                raise ValueError(f"Invalid camera width: {width_px}")

            if height_px != -1 and height_px <= 0:
                raise ValueError(f"Invalid camera height: {height_px}")

            if fps != -1 and fps <= 0:
                raise ValueError(f"Invalid camera frame rate: {fps}")
