# Hardware Parameter Architecture

## Problem Statement

Hardware parameters (camera and monitor settings) were being persisted to `config/isi_parameters.json`, causing stale selections between sessions. For example, users would see "FaceTime HD Camera" in the UI even though the backend had detected and opened "Camera 1" at startup.

### Why This Is Critical

Hardware parameters MUST NOT persist between sessions because:

1. **Different setups**: Lab vs office environments have different hardware configurations
2. **Hardware changes**: Cameras get unplugged, monitors get disconnected between sessions
3. **Multiple users**: Different users on the same machine may have different hardware available
4. **Scientific rigor**: Explicit hardware detection on every startup ensures reproducibility

## Solution: Volatile Parameter Groups

The system now treats camera and monitor parameters as **volatile** (runtime-only, never persisted to disk).

### Architecture Components

#### 1. ParameterManager (`src/parameters/manager.py`)

**Key Changes:**
- Added `VOLATILE_GROUPS = {"camera", "monitor"}` constant
- Modified `_save()` to exclude volatile groups from disk writes
- Volatile groups are replaced with sentinel values (from `default`) when saving
- Added clear logging to distinguish between runtime-only and persisted updates

**How It Works:**
```python
# When saving parameters to disk
data_to_save = copy.deepcopy(self.data)
for volatile_group in self.VOLATILE_GROUPS:
    # Reset to sentinel values before writing
    default_group = self.data.get("default", {}).get(volatile_group, {})
    data_to_save["current"][volatile_group] = copy.deepcopy(default_group)
```

#### 2. Hardware Detection (`src/main.py` - `_verify_hardware()`)

**Key Changes:**
- Hardware detection updates `param_manager.data` directly (bypasses save)
- Never calls `param_manager._save()` or `update_parameter_group()`
- Explicitly logs "runtime only" to clarify behavior

**How It Works:**
```python
# Direct in-memory update (no save)
param_manager.data["current"]["camera"].update(camera_updates)
logger.info(f"Camera parameters updated (runtime only): {list(camera_updates.keys())}")
```

#### 3. JSON Configuration (`config/isi_parameters.json`)

**Key Changes:**
- `current.camera` section reset to sentinel values (empty arrays, -1 for numbers)
- `current.monitor` section reset to sentinel values
- These sentinel values match the `default` section exactly

**Sentinel Values:**
```json
"camera": {
  "available_cameras": [],
  "camera_fps": -1,
  "camera_height_px": -1,
  "camera_width_px": -1,
  "selected_camera": ""
}
```

#### 4. IPC Handlers (`src/main.py`)

**Key Changes:**
- `_detect_displays()`: Added comments clarifying runtime-only behavior
- `_select_display()`: Added comments clarifying runtime-only behavior
- `_update_parameters()`: Already had validation blocking hardware capability updates from frontend

**Frontend Protection:**
The parameter update handler blocks attempts to modify hardware capabilities from the frontend:
```python
if group_name == "camera":
    allowed_keys = {"selected_camera"}  # Only selection, not capabilities

if group_name == "monitor":
    allowed_keys = {
        "selected_display",           # Hardware selection
        "monitor_distance_cm",        # User-configurable geometry
        "monitor_lateral_angle_deg",  # User-configurable geometry
        "monitor_tilt_angle_deg",     # User-configurable geometry
        "monitor_height_cm",          # User-configurable geometry
        "monitor_width_cm"            # User-configurable geometry
    }
    # NOT: available_displays, resolution, fps (hardware detection only)
```

## Validation

### Test Results

All tests pass, confirming:

✅ Camera parameters are runtime-only (NOT persisted)
✅ Monitor parameters are runtime-only (NOT persisted)
✅ Non-volatile parameters (stimulus, etc.) ARE persisted
✅ JSON file always has sentinel values for hardware params

### Test Output
```
Test 2: Modify camera parameters (should be runtime-only)
✓ In-memory: TestCam1, 1920x1080@60fps

Test 3: Verify camera params were NOT persisted to disk
✓ Disk has sentinel values: True
  - width_px: -1 (should be -1)
  - selected: "" (should be empty)
```

## Data Flow

### Startup Sequence

1. **ParameterManager loads JSON**
   - Camera/monitor sections have sentinel values (-1, empty arrays)

2. **Hardware detection runs** (`_verify_hardware()`)
   - Detects available cameras and monitors
   - Updates `param_manager.data` directly (no save)
   - Logs "runtime only" for clarity

3. **Frontend receives parameters**
   - Gets fresh hardware detection results
   - Cannot modify hardware capabilities (validation blocks it)

### During Session

1. **User selects different camera/monitor**
   - Frontend sends update
   - ParameterManager updates in-memory
   - `_save()` excludes volatile groups
   - JSON file retains sentinel values

2. **User modifies stimulus parameters**
   - Frontend sends update
   - ParameterManager updates in-memory
   - `_save()` persists to disk (not volatile)
   - JSON file updated with new values

### Next Startup

1. **ParameterManager loads JSON**
   - Camera/monitor sections STILL have sentinel values
   - No stale hardware data persists

2. **Hardware detection runs again**
   - Detects current hardware (may be different)
   - Updates runtime parameters
   - System uses fresh detection

## Benefits

### Clean Architecture
- No backward compatibility hacks
- No dead code for "migration" or "legacy support"
- Single source of truth for volatility: `VOLATILE_GROUPS`

### Scientific Rigor
- Hardware always detected fresh
- No hidden state from previous sessions
- Reproducible across different environments

### User Experience
- UI always shows correct current hardware
- No confusion from stale cached data
- Clear error messages if hardware missing

## Related Files

- `/Users/Adam/KimLabISI/apps/backend/src/parameters/manager.py` - Core volatility logic
- `/Users/Adam/KimLabISI/apps/backend/src/main.py` - Hardware detection and IPC handlers
- `/Users/Adam/KimLabISI/apps/backend/config/isi_parameters.json` - Configuration with sentinel values

## Future Considerations

### Adding More Volatile Groups

To make other parameter groups volatile:

1. Add to `VOLATILE_GROUPS` in `ParameterManager.__init__()`
2. Ensure defaults exist in JSON for the group
3. Update validation if needed

Example:
```python
VOLATILE_GROUPS = {"camera", "monitor", "new_volatile_group"}
```

### Monitoring

Look for these log messages to verify correct behavior:

```
ParameterManager initialized with /path/to/isi_parameters.json
Volatile parameter groups (runtime-only): {'camera', 'monitor'}
```

```
Updated camera parameters (runtime-only): ['selected_camera', 'camera_width_px', ...]
Saved parameters to /path/to/isi_parameters.json (skipped volatile groups: {'camera', 'monitor'})
```

```
Camera parameters updated (runtime only): ['available_cameras', 'selected_camera', ...]
```
