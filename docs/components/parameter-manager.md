# Parameter Manager

**Last Updated**: 2025-10-15 01:05
**Status**: Stable
**Maintainer**: Backend Team

> Configuration management and single source of truth for all system parameters. **CRITICAL**: NO hardcoded parameter defaults allowed.

---

## Overview

The Parameter Manager is the **Single Source of Truth** for all system configuration. It provides centralized parameter storage with real-time updates, thread-safe access, automatic persistence to JSON, and change notifications using dependency injection and the observer pattern.

## Purpose

The Parameter Manager provides:

- **Single Source of Truth**: All components read from one authoritative parameter store
- **Real-time updates**: Parameter changes propagate immediately to all subscribed components without restart
- **Dependency injection**: Components receive ParameterManager reference instead of frozen configs
- **Observer pattern**: Components subscribe to parameter groups and rebuild state when notified
- **Thread safety**: All operations protected by reentrant lock (RLock)
- **Atomic persistence**: Temp file + rename pattern prevents JSON corruption on crash
- **Parameter validation**: Scientific constraints enforced before persistence

## Architecture

### Component Integration Pattern

```
ParameterManager (single source of truth)
   ↓
Components inject ParameterManager (dependency injection)
   ↓
Components subscribe to parameter groups (observer pattern)
   ↓
User changes parameters
   ↓
ParameterManager validates parameters
   ↓
ParameterManager persists to JSON (atomic write)
   ↓
ParameterManager notifies subscribers
   ↓
Components rebuild state immediately
   ↓
Changes visible instantly (no restart)
```

### Dependency Injection

Components receive ParameterManager instead of frozen configs:

```python
# Component initialization
class StimulusGenerator:
    def __init__(self, param_manager: ParameterManager):
        self.param_manager = param_manager  # Live reference
        self.param_manager.subscribe("stimulus", self._handle_stimulus_params_changed)
        self.param_manager.subscribe("monitor", self._handle_monitor_params_changed)
        self._setup_from_parameters()  # Initialize from current parameters
```

### Observer Pattern

Components subscribe to parameter group changes:

```python
# Subscribe to parameter group
self.param_manager.subscribe("stimulus", self._handle_stimulus_params_changed)

# Handle parameter changes
def _handle_stimulus_params_changed(self, group_name: str, updates: Dict[str, Any]):
    logger.info(f"Stimulus parameters changed: {list(updates.keys())}")
    self._setup_from_parameters()  # Rebuild GPU state with new parameters
```

## Key Features

### Parameter Groups

All parameters organized into logical groups:

**Core Parameter Groups**:
- `stimulus`: Stimulus generation parameters (bar width, checker size, background luminance, contrast, etc.)
- `monitor`: Display hardware parameters (FPS, resolution, physical dimensions, viewing geometry)
- `camera`: Camera hardware parameters (selected camera, FPS, resolution)
- `acquisition`: Acquisition protocol parameters (baseline duration, cycles, directions)
- `analysis`: Analysis pipeline parameters (coherence threshold, VFS threshold, smoothing, gradient computation)
- `session`: Session metadata (session name, animal ID, animal age)

### Real-Time Parameter Updates

**Parameter update flow**:
1. User changes parameter in frontend control panel
2. Frontend sends parameter update command to backend
3. Backend validates parameter values (scientific constraints checked)
4. Backend persists to JSON file (atomic write with temp + rename)
5. Backend notifies all subscribers for affected parameter group
6. Components rebuild state with new parameters
7. Changes visible immediately (no restart required)

**Benefit**: User sees instant feedback, system feels responsive

### Thread Safety

**Reentrant lock (RLock)**:
- All parameter access protected by RLock
- Allows same thread to acquire lock multiple times
- Prevents deadlock in nested calls
- Safe for concurrent access from multiple threads

**Notification outside lock**:
- Subscriber callbacks execute OUTSIDE of lock
- Prevents deadlock if callback calls back into ParameterManager
- Callback list copied inside lock for thread safety

### Atomic Persistence

**Temp file + rename pattern**:
```python
# Write to temporary file
temp_file = config_path.with_suffix('.json.tmp')
with open(temp_file, 'w') as f:
    json.dump(self.data, f, indent=2)
    f.flush()

# Atomic rename (OS-level guarantee)
temp_file.replace(config_path)
```

**Benefits**:
- Never corrupts JSON file (all-or-nothing write)
- Safe if application crashes during write
- OS-level atomicity guarantee (POSIX)

## Anti-Patterns: What NOT to Do

### ❌ ANTI-PATTERN: Hardcoded Parameter Defaults

**NEVER hardcode parameter values in component initialization**:

```python
# ❌ WRONG - Hardcoded defaults violate Single Source of Truth
class AcquisitionManager:
    def __init__(self, param_manager: ParameterManager):
        self.param_manager = param_manager
        self.baseline_sec = 5  # ❌ BAD! Hardcoded default
        self.between_sec = 5   # ❌ BAD! Hardcoded default
        self.cycles = 10       # ❌ BAD! Hardcoded default
```

**Why this is wrong**:
- Creates hidden configuration that users can't see or change
- Violates Single Source of Truth principle
- Makes scientific reproducibility impossible (defaults not recorded)
- Parameters may silently fall back to hardcoded values
- No validation or constraints on hardcoded values

**✅ CORRECT - Initialize to None, load from param_manager**:

```python
# ✅ CORRECT - NO hardcoded defaults
class AcquisitionManager:
    def __init__(self, param_manager: ParameterManager):
        self.param_manager = param_manager

        # Initialize to None - indicates "not yet loaded"
        self.baseline_sec: Optional[float] = None
        self.between_sec: Optional[float] = None
        self.cycles: Optional[int] = None

    def start_acquisition(self):
        """Load parameters from param_manager before use."""
        # Read from Single Source of Truth
        params = self.param_manager.get_parameter_group("acquisition")

        # Validate explicitly - fail with clear error if missing
        baseline_sec = params.get("baseline_sec")
        if baseline_sec is None:
            raise RuntimeError(
                "baseline_sec must be configured in param_manager before acquisition. "
                "Please set acquisition.baseline_sec parameter."
            )

        # Type-safe assignment after validation
        self.baseline_sec = float(baseline_sec)
```

**Key rules**:
1. **NEVER hardcode parameter defaults** (e.g., `self.value = 42`)
2. **Initialize to None** to indicate "not yet loaded from param_manager"
3. **Validate explicitly** before use, fail with clear error if missing
4. **Always read from param_manager** for current value
5. **Fail loudly** if required parameters not configured
6. **Document parameter requirements** in component docs

### ❌ ANTI-PATTERN: Frozen Parameter Snapshots

**NEVER store frozen parameter copies**:

```python
# ❌ WRONG - Frozen snapshot becomes stale
class CameraManager:
    def __init__(self, param_manager: ParameterManager):
        self.camera_params = param_manager.get_parameter_group("camera")  # ❌ Frozen!
        self.fps = self.camera_params["fps"]  # Stale forever
```

**✅ CORRECT - Always read from param_manager**:

```python
# ✅ CORRECT - Live reference to source of truth
class CameraManager:
    def __init__(self, param_manager: ParameterManager):
        self.param_manager = param_manager  # Live reference
        self.param_manager.subscribe("camera", self._on_camera_params_changed)

    def get_fps(self) -> float:
        """Always returns current value from source of truth."""
        return self.param_manager.get("camera", "fps")
```

### ❌ ANTI-PATTERN: Parameter Fallback Values

**NEVER use fallback defaults for missing parameters**:

```python
# ❌ WRONG - Silent fallback hides configuration errors
def get_baseline_duration(self) -> float:
    params = self.param_manager.get_parameter_group("acquisition")
    return params.get("baseline_sec", 5.0)  # ❌ Silent fallback!
```

**✅ CORRECT - Fail explicitly with clear error**:

```python
# ✅ CORRECT - Explicit validation, fail loudly
def get_baseline_duration(self) -> float:
    params = self.param_manager.get_parameter_group("acquisition")
    baseline_sec = params.get("baseline_sec")

    if baseline_sec is None:
        raise RuntimeError(
            "baseline_sec must be configured in param_manager. "
            "Please set acquisition.baseline_sec parameter."
        )

    return float(baseline_sec)
```

---

### Parameter Validation

**Scientific constraints enforced before persistence**:

**Stimulus validation** (prevents invisible checkerboard):
- Background luminance must be >= contrast
- Otherwise dark checkers clip to black and become invisible
- Validation failure blocks parameter update with clear error message

**Monitor validation** (prevents invalid display settings):
- Monitor resolution must be positive (width_px > 0, height_px > 0)
- Monitor FPS must be positive (fps > 0)

**Camera validation** (allows sentinel -1 for "not detected"):
- Camera resolution must be positive OR -1 (width_px, height_px)
- Camera FPS must be positive OR -1 (fps)

## Data Flow

### Parameter Update Flow
1. User modifies parameter in frontend
2. Frontend sends `update_parameters` command with {group_name, updates}
3. Backend validates parameter values
4. If validation fails: Return error message to user
5. If validation passes: Apply updates to in-memory store
6. Persist updated parameters to JSON file (atomic write)
7. Notify all subscribers for affected parameter group
8. Subscribers rebuild state with new parameters
9. Frontend receives success confirmation

### Parameter Read Flow
1. Component needs parameter values
2. Component calls `param_manager.get_parameter_group(group_name)`
3. ParameterManager acquires lock
4. ParameterManager returns parameter dictionary
5. ParameterManager releases lock
6. Component uses current parameter values

### Subscription Flow
1. Component initializes with ParameterManager reference
2. Component subscribes to relevant parameter groups
3. ParameterManager registers callback in subscriber list
4. When parameters change: ParameterManager calls callback
5. Component rebuilds state in callback
6. Component can unsubscribe when cleanup needed

## Integration

### Component Dependencies
- **IPC System**: Receives parameter update commands from frontend
- **All Components**: All major components inject ParameterManager

### Component Subscriptions

**StimulusGenerator**:
- Subscribes to: `stimulus`, `monitor`
- Rebuilds: GPU tensors (spherical coordinates, checkerboard patterns)

**CameraManager**:
- Subscribes to: `camera`
- Behavior: Logs warning if parameters change during streaming

**AcquisitionManager**:
- Subscribes to: `acquisition`
- Behavior: Reads parameters at start of each acquisition

**AnalysisManager**:
- Subscribes to: `analysis`, `acquisition`
- Behavior: Reads parameters when running analysis (no caching)

### Frontend Integration
- **Control Panel**: Parameter editor with real-time validation
- **All Viewports**: Components reflect parameter changes immediately

## Behavior

### Parameter Update Behavior

**Immediate effect parameters**:
- Stimulus parameters (bar width, checker size, etc.) - rebuild GPU state immediately
- Analysis parameters (thresholds, smoothing) - used in next analysis run

**Restart required parameters**:
- Camera hardware parameters (FPS, resolution) if camera is streaming
- Monitor resolution (requires pre-generation invalidation)

**Invalidation triggers**:
- Stimulus parameter changes: Invalidate pre-generated stimulus library
- Monitor spatial parameter changes: Invalidate pre-generated stimulus library

### Validation Behavior

**On parameter update**:
- Validate ALL parameters in update dictionary
- If ANY parameter fails validation: Reject entire update (atomic)
- Return detailed error message indicating which parameter failed

**Validation enforced**:
- Stimulus: background_luminance >= contrast (prevents invisible checkerboard)
- Monitor: positive resolution and FPS
- Camera: positive resolution and FPS (or -1 sentinel for "not detected")

### Persistence Behavior

**When parameters persist**:
- After every successful parameter update
- Atomic write ensures corruption never occurs
- JSON file at `apps/backend/config/isi_parameters.json`

**JSON file structure**:
```json
{
  "config": {
    "stimulus": { /* parameter metadata */ },
    "monitor": { /* parameter metadata */ },
    ...
  },
  "current": {
    "stimulus": { /* current values */ },
    "monitor": { /* current values */ },
    ...
  },
  "default": {
    "stimulus": { /* default values */ },
    "monitor": { /* default values */ },
    ...
  }
}
```

## Constraints

### Thread Safety Requirements
- All parameter access MUST be protected by RLock
- Subscriber callbacks MUST execute outside lock (prevent deadlock)
- Callback list copied inside lock for thread safety

### Validation Requirements
- Parameters MUST be validated before persistence
- Invalid parameters MUST be rejected atomically
- Validation errors MUST provide clear user feedback

### Persistence Requirements
- JSON writes MUST be atomic (temp + rename)
- JSON file MUST never be corrupted
- Parameter changes MUST persist across application restarts

## Parameter Groups

### Stimulus Parameters (`stimulus`)

All parameters for stimulus generation:

- `bar_width_deg`: Bar width in degrees of visual angle
- `checker_size_deg`: Checkerboard checker size in degrees
- `background_luminance`: Background gray level (0.0-1.0)
- `contrast`: Checkerboard contrast (0.0-1.0)
- `drift_speed_deg_per_sec`: Bar sweep speed
- `strobe_rate_hz`: Checkerboard temporal frequency

**Critical constraint**: `background_luminance >= contrast` (otherwise dark checkers clip to black)

### Monitor Parameters (`monitor`)

Display hardware and physical geometry parameters:

**Display resolution** (dynamically detected):
- `monitor_fps`: Refresh rate in Hz
- `monitor_width_px`: Width in pixels
- `monitor_height_px`: Height in pixels
- `selected_display`: Selected display from available displays
- `available_displays`: List of detected displays (auto-populated)

**Physical geometry** (essential metadata for spherical projection):
- `monitor_distance_cm`: Viewing distance in cm
- `monitor_width_cm`: Physical width in cm
- `monitor_height_cm`: Physical height in cm
- `monitor_lateral_angle_deg`: Monitor lateral angle for spherical transform
- `monitor_tilt_angle_deg`: Monitor tilt angle for spherical transform

**Note**: All monitor spatial parameters are crucial metadata for reproducing visual field calculations.

### Camera Parameters (`camera`)

Camera hardware parameters (dynamically detected):

- `selected_camera`: Device name
- `camera_fps`: Frame rate in Hz (-1 if not detected)
- `camera_width_px`: Width in pixels (-1 if not detected)
- `camera_height_px`: Height in pixels (-1 if not detected)
- `available_cameras`: List of detected cameras (auto-populated)

**Note**: Sentinel value -1 indicates "not detected" for FPS and resolution.

### Acquisition Parameters (`acquisition`)

Acquisition protocol timing and structure:

- `baseline_sec`: Initial/final baseline duration
- `between_sec`: Between-trials baseline duration
- `cycles`: Number of repeats per direction
- `directions`: List of sweep directions (array of 'LR' | 'RL' | 'TB' | 'BT')

### Analysis Parameters (`analysis`)

Analysis pipeline thresholds and processing parameters:

**Filtering thresholds**:
- `coherence_threshold`: Signal reliability filter (0.0-1.0, default 0.3, from Kalatsky 2003)
- `magnitude_threshold`: Response strength filter (0.0-1.0, default 0.3, from Juavinett 2017)
- `response_threshold_percent`: Minimum response as % of max (0-100, default 20)

**VFS computation**:
- `vfs_threshold_sd`: Statistical threshold in standard deviations (default 1.5, from MATLAB reference)
- `smoothing_sigma`: Retinotopic map smoothing (default 3.0, FFT-based)
- `phase_filter_sigma`: Phase map smoothing (default 0.0 - disabled, MATLAB uses FFT)

**Spatial processing**:
- `gradient_window_size`: Sobel kernel size (default 3)
- `area_min_size_mm2`: Minimum cortical area size (default 0.1)
- `ring_size_mm`: Spatial calibration (user-specific)

**Literature sources**: Kalatsky & Stryker 2003, Juavinett et al. 2017, MATLAB ISI-master reference

### Session Parameters (`session`)

Session metadata for experimental records:

- `session_name`: Recording session identifier
- `animal_id`: Subject identifier
- `animal_age`: Subject age
- `created_at`: Session creation timestamp (auto-generated)
- `last_modified`: Last modification timestamp (auto-updated)

---

**Component Version**: 2.0 (Dependency Injection Refactor)
**Architecture**: Dependency injection with observer pattern for real-time updates
**Verification Status**: ✅ All tests passing
