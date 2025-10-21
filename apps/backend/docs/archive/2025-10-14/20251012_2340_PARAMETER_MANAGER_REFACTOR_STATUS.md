# Parameter Manager Refactoring Status

## Critical Architecture Violation Identified

**Problem:** Single Source of Truth violation in the parameter system

**Current (BROKEN) Architecture:**
- Components initialized with frozen `AppConfig` (loaded once at startup)
- `ParameterManager` exists separately and persists to JSON
- When users change parameters → ParameterManager updates → JSON persists → **but components never see the changes**

**Required (PROPER) Architecture:**
- `ParameterManager` is the Single Source of Truth for ALL runtime parameters
- Components inject `ParameterManager` dependency
- Components ALWAYS read current values from ParameterManager (no frozen copies)
- Components subscribe to parameter changes and react accordingly

## Implementation Progress

### ✅ COMPLETED: Phase 1 - Subscription Mechanism

**File:** `/Users/Adam/KimLabISI/apps/backend/src/parameters/manager.py`

Added observer pattern to ParameterManager:

```python
class ParameterManager:
    def __init__(self, ...):
        # ... existing init ...
        self._subscribers: Dict[str, List[Callable]] = {}
        self._subscriber_lock = threading.Lock()

    def subscribe(self, group_name: str, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Subscribe to parameter changes for a specific group."""
        # Implementation complete

    def unsubscribe(self, group_name: str, callback: Callable) -> None:
        """Unsubscribe from parameter changes."""
        # Implementation complete

    def update_parameter_group(self, group_name: str, updates: Dict[str, Any]) -> None:
        """Update parameters and notify subscribers."""
        # Updated to call _notify_subscribers()

    def _notify_subscribers(self, group_name: str, updates: Dict[str, Any]) -> None:
        """Notify all subscribers of parameter changes."""
        # Implementation complete with error handling
```

**Status:** ✅ Complete and tested (subscription mechanism works)

---

### ❌ TODO: Phase 2 - Refactor StimulusGenerator

**File:** `/Users/Adam/KimLabISI/apps/backend/src/stimulus/generator.py`

**Current Signature:**
```python
def __init__(
    self,
    stimulus_config: StimulusConfig,
    monitor_config: MonitorConfig
):
```

**Required Changes:**

1. **Change constructor signature:**
```python
def __init__(
    self,
    param_manager: ParameterManager,
    logger=None
):
```

2. **Replace all `self.stimulus_config.X` with live parameter reads:**
```python
# OLD (frozen):
bar_width = self.stimulus_config.bar_width_deg

# NEW (live):
stimulus_params = self.param_manager.get_parameter_group("stimulus")
bar_width = stimulus_params.get("bar_width_deg")
```

3. **Subscribe to parameter changes:**
```python
self.param_manager.subscribe("stimulus", self._handle_stimulus_params_changed)
self.param_manager.subscribe("monitor", self._handle_monitor_params_changed)
```

4. **Implement change handlers:**
```python
def _handle_stimulus_params_changed(self, group_name: str, updates: Dict[str, Any]):
    if any(key in updates for key in ["checker_size_deg", "bar_width_deg", "contrast"]):
        self._setup_from_parameters()  # Rebuild GPU tensors

def _handle_monitor_params_changed(self, group_name: str, updates: Dict[str, Any]):
    spatial_keys = ["monitor_distance_cm", "monitor_width_px", ...]
    if any(key in updates for key in spatial_keys):
        self._setup_from_parameters()  # Rebuild spherical transform
```

5. **Extract `_setup_from_parameters()` method:**
```python
def _setup_from_parameters(self):
    """Initialize/reinitialize from current parameter values."""
    stimulus_params = self.param_manager.get_parameter_group("stimulus")
    monitor_params = self.param_manager.get_parameter_group("monitor")

    # Extract all values
    self.bar_width_deg = stimulus_params.get("bar_width_deg")
    self.checker_size_deg = stimulus_params.get("checker_size_deg")
    # ... etc

    # Rebuild GPU state
    self._setup_spherical_transform()
    self._precompute_invariants()
```

**Impact:** ~200 lines of changes across the file

---

### ❌ TODO: Phase 3 - Refactor CameraManager

**File:** `/Users/Adam/KimLabISI/apps/backend/src/camera/manager.py`

**Current Signature:**
```python
def __init__(
    self,
    config,  # CameraConfig
    ipc,
    shared_memory,
    synchronization_tracker,
    camera_triggered_stimulus,
):
```

**Required Changes:**

1. **Change constructor signature:**
```python
def __init__(
    self,
    param_manager: ParameterManager,
    ipc,
    shared_memory,
    synchronization_tracker,
    camera_triggered_stimulus,
):
```

2. **Subscribe to camera parameter changes:**
```python
self.param_manager.subscribe("camera", self._handle_camera_params_changed)
```

3. **Implement change handler:**
```python
def _handle_camera_params_changed(self, group_name: str, updates: Dict[str, Any]):
    if self._is_streaming:
        needs_reconfigure = any(key in updates for key in
            ["camera_fps", "camera_width_px", "camera_height_px", "exposure_us", "gain"])

        if needs_reconfigure:
            camera_name = self.param_manager.get_parameter_group("camera").get("selected_camera")
            self.stop_acquisition()
            self.start_acquisition(camera_name)
```

4. **Update `start_acquisition()` to read live parameters:**
```python
def start_acquisition(self, camera_name: Optional[str] = None):
    if camera_name is None:
        camera_name = self.param_manager.get_parameter_group("camera").get("selected_camera")

    camera_params = self.param_manager.get_parameter_group("camera")
    width = camera_params.get("camera_width_px")
    height = camera_params.get("camera_height_px")
    fps = camera_params.get("camera_fps")
    # ... use live values
```

**Impact:** ~50 lines of changes

---

### ❌ TODO: Phase 4 - Refactor AcquisitionManager

**File:** `/Users/Adam/KimLabISI/apps/backend/src/acquisition/manager.py`

**Current Status:** Already uses `param_manager`, but doesn't subscribe to changes

**Required Changes:**

1. **Add subscription in `__init__`:**
```python
self.param_manager.subscribe("acquisition", self._handle_acquisition_params_changed)
```

2. **Implement change handler:**
```python
def _handle_acquisition_params_changed(self, group_name: str, updates: Dict[str, Any]):
    if self.is_running:
        self.logger.warning(
            "Acquisition parameters changed during active acquisition. "
            "Changes will apply to next acquisition."
        )
```

3. **Update `start_acquisition()` to always read from ParameterManager:**
```python
def start_acquisition(self, params: Optional[Dict[str, Any]] = None, param_manager=None):
    # Read acquisition parameters from ParameterManager (ignore passed params)
    acq_params = self.param_manager.get_parameter_group("acquisition")

    self.baseline_sec = acq_params.get("baseline_sec")
    self.between_sec = acq_params.get("between_sec")
    self.cycles = acq_params.get("cycles")
    self.directions = acq_params.get("directions", ["LR", "RL", "TB", "BT"])
```

**Impact:** ~20 lines of changes

---

### ❌ TODO: Phase 5 - Refactor AnalysisManager

**File:** `/Users/Adam/KimLabISI/apps/backend/src/analysis/manager.py`

**Current Signature:**
```python
def __init__(
    self,
    config: AnalysisConfig,
    acquisition_config: AcquisitionConfig,
    ipc: MultiChannelIPC,
    shared_memory: SharedMemoryService,
    pipeline: AnalysisPipeline
):
```

**Required Changes:**

1. **Change constructor signature:**
```python
def __init__(
    self,
    param_manager: ParameterManager,
    ipc: MultiChannelIPC,
    shared_memory: SharedMemoryService,
    pipeline: AnalysisPipeline
):
```

2. **Subscribe to analysis parameter changes:**
```python
self.param_manager.subscribe("analysis", self._handle_analysis_params_changed)
```

3. **Implement change handler:**
```python
def _handle_analysis_params_changed(self, group_name: str, updates: Dict[str, Any]):
    self.logger.info(f"Analysis parameters changed: {updates}")
    # Analysis uses params at analysis time, not continuously
```

4. **Update `run_analysis()` to read live parameters:**
```python
def run_analysis(self, session_data):
    analysis_params = self.param_manager.get_parameter_group("analysis")

    coherence_threshold = analysis_params.get("coherence_threshold")
    magnitude_threshold = analysis_params.get("magnitude_threshold")
    smoothing_sigma = analysis_params.get("smoothing_sigma")
    vfs_threshold_sd = analysis_params.get("vfs_threshold_sd")
```

5. **Update acquisition config reads:**
```python
# Replace self.acquisition_config.directions with:
acquisition_params = self.param_manager.get_parameter_group("acquisition")
directions = acquisition_params.get("directions", ["LR", "RL", "TB", "BT"])
```

**Impact:** ~40 lines of changes

---

### ❌ TODO: Phase 6 - Update Composition Root (main.py)

**File:** `/Users/Adam/KimLabISI/apps/backend/src/main.py`

**Required Changes:**

1. **Remove frozen AppConfig injection from components:**
```python
# OLD (lines 89-92):
stimulus_generator = StimulusGenerator(
    stimulus_config=config.stimulus,
    monitor_config=config.monitor
)

# NEW:
stimulus_generator = StimulusGenerator(
    param_manager=param_manager,
    logger=logger
)
```

2. **Update CameraManager construction:**
```python
# OLD (lines 105-111):
camera = CameraManager(
    config=config.camera,
    ipc=ipc,
    shared_memory=shared_memory,
    synchronization_tracker=sync_tracker,
    camera_triggered_stimulus=camera_triggered_stimulus,
)

# NEW:
camera = CameraManager(
    param_manager=param_manager,
    ipc=ipc,
    shared_memory=shared_memory,
    synchronization_tracker=sync_tracker,
    camera_triggered_stimulus=camera_triggered_stimulus,
)
```

3. **Update AnalysisManager construction:**
```python
# OLD (lines 129-135):
analysis_manager = AnalysisManager(
    config=config.analysis,
    acquisition_config=config.acquisition,
    ipc=ipc,
    shared_memory=shared_memory,
    pipeline=analysis_pipeline
)

# NEW:
analysis_manager = AnalysisManager(
    param_manager=param_manager,
    ipc=ipc,
    shared_memory=shared_memory,
    pipeline=analysis_pipeline
)
```

4. **Keep AppConfig for initial hardware detection only:**
```python
# Load initial config ONLY for hardware paths and static configuration
initial_config = AppConfig.from_file(str(config_path))

# Create ParameterManager as Single Source of Truth
param_manager = ParameterManager(
    config_file=config_path,
    logger=logger
)

# Detect hardware and update ParameterManager
available_cameras = detect_cameras()
available_displays = detect_displays()

param_manager.update_parameter_group("camera", {
    "available_cameras": available_cameras
})
param_manager.update_parameter_group("monitor", {
    "available_displays": available_displays
})
```

**Impact:** ~60 lines of changes

---

### ❌ TODO: Phase 7 - Clean Up AppConfig (Optional)

**File:** `/Users/Adam/KimLabISI/apps/backend/src/config.py`

**Optional Cleanup:**

Keep `AppConfig` for initial hardware detection and paths, but document that the frozen `@dataclass` parameter configs (CameraConfig, StimulusConfig, etc.) are legacy and NOT the source of truth.

Alternatively, remove them entirely and use ParameterManager for everything.

**Impact:** Documentation only, or ~100 lines removed if deleted

---

## Testing Strategy

After completing all phases, test each parameter group:

### 1. Stimulus Parameters Test
```
1. Start preview mode
2. Change `bar_width_deg` in control panel
3. Verify stimulus immediately shows wider/narrower bars
```

### 2. Camera Parameters Test
```
1. Start preview mode
2. Change `camera_fps` in control panel
3. Verify camera reconfigures and preview shows new frame rate
```

### 3. Monitor Parameters Test
```
1. Start preview mode
2. Change `monitor_distance_cm` in control panel
3. Verify stimulus FOV calculations update (bar size in pixels changes)
```

### 4. Acquisition Parameters Test
```
1. Set `cycles` to 5
2. Start acquisition
3. Verify 5 cycles run
4. Change `cycles` to 10 while still acquiring
5. Verify next direction uses 10 cycles
```

### 5. Parameter Persistence Test
```
1. Change any parameter
2. Restart backend
3. Verify parameter value restored from JSON
```

---

## Estimated Remaining Work

- **Phase 2 (StimulusGenerator):** ~2-3 hours
- **Phase 3 (CameraManager):** ~1 hour
- **Phase 4 (AcquisitionManager):** ~30 minutes
- **Phase 5 (AnalysisManager):** ~1 hour
- **Phase 6 (main.py):** ~1 hour
- **Phase 7 (Optional cleanup):** ~30 minutes
- **Testing:** ~2 hours

**Total:** ~8-9 hours of focused development work

---

## Important Notes

1. **Hardware-Detected Parameters:** Available cameras/displays come from hardware detection and populate ParameterManager. Users select from dropdowns.

2. **No Hacks:** This is a proper architectural refactoring using dependency injection and observer pattern.

3. **Thread Safety:** ParameterManager subscriber mechanism uses locks for thread safety.

4. **Backwards Compatibility:** JSON file format remains unchanged.

5. **Real-Time Updates:** After completion, all components will see parameter changes immediately without restart.

---

## Why This Matters

**User Experience Before Fix:**
- User changes bar width in control panel
- Parameter updates in JSON
- Stimulus still shows old bar width
- User confused, thinks system is broken
- User must restart application to see changes

**User Experience After Fix:**
- User changes bar width in control panel
- Parameter updates in JSON
- StimulusGenerator receives notification
- GPU tensors rebuild with new bar width
- Stimulus immediately shows new bar width
- User sees instant feedback, system feels responsive

**This is the difference between a broken system and a professional scientific instrument.**

---

## Next Steps

1. Continue with Phase 2 (StimulusGenerator refactoring)
2. Then Phase 3 (CameraManager refactoring)
3. Then Phase 4-6 (remaining components)
4. Finally, comprehensive testing

The foundation (Phase 1) is now complete and working correctly. The subscription mechanism is ready and will notify all subscribers when parameters change. We just need to refactor the components to use it.
