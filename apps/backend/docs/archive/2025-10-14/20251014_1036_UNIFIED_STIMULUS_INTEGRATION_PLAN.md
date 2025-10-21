# Unified Stimulus Integration Plan

## Overview

This document tracks the integration of `UnifiedStimulusController` to replace the two competing stimulus systems:
- `CameraTriggeredStimulusController` (used in record mode)
- `PreviewStimulusLoop` (used in preview mode)

## Status: IN PROGRESS

### Completed ✓

1. **Priority 0 Fixes (CRITICAL)**
   - ✓ Added parameter subscriptions (stimulus, monitor groups)
   - ✓ Added cache invalidation on parameter changes
   - ✓ Added FPS validation in `start_playback()`
   - ✓ Added direction validation
   - ✓ Added empty library validation
   - ✓ Fixed display log unbounded growth (using `deque(maxlen=10000)`)
   - ✓ Added cleanup/unsubscribe in `cleanup()` method

2. **Priority 1 Fixes (HIGH)**
   - ✓ Implemented frame correspondence logic
     - `get_stimulus_frame_index_for_camera_frame()`
     - `get_stimulus_angle_for_camera_frame()`
   - ✓ Frame-index-based mapping: `camera_frame_N → stimulus_frame_M` where `M = N * (monitor_fps / camera_fps)`

### In Progress 🔄

3. **Integration with AcquisitionManager**

   **Current Architecture (OLD):**
   ```
   AcquisitionManager._acquisition_loop()
     ├─ Phase: INITIAL_BASELINE → _publish_baseline_frame()
     ├─ For each direction:
     │   ├─ For each cycle:
     │   │   ├─ Phase: STIMULUS
     │   │   ├─ camera_triggered_stimulus.start_direction(direction, camera_fps)
     │   │   ├─ Poll until is_direction_complete()
     │   │   ├─ camera_triggered_stimulus.stop_direction()
     │   │   └─ Phase: BETWEEN_TRIALS → _publish_baseline_frame()
     │   └─ data_recorder.stop_recording()
     └─ Phase: FINAL_BASELINE → _publish_baseline_frame()
   ```

   **New Architecture (UNIFIED):**
   ```
   AcquisitionManager._acquisition_loop()
     ├─ Phase: INITIAL_BASELINE → unified_stimulus.display_baseline()
     ├─ For each direction:
     │   ├─ unified_stimulus.pre_generate_all_directions() [if not cached]
     │   ├─ For each cycle:
     │   │   ├─ Phase: STIMULUS
     │   │   ├─ unified_stimulus.start_playback(direction, monitor_fps)
     │   │   ├─ Wait for duration = stimulus_duration (calculated from camera_fps)
     │   │   ├─ unified_stimulus.stop_playback()
     │   │   └─ Phase: BETWEEN_TRIALS → unified_stimulus.display_baseline()
     │   └─ data_recorder.stop_recording()
     └─ Phase: FINAL_BASELINE → unified_stimulus.display_baseline()
   ```

   **Key Changes:**
   - Replace `camera_triggered_stimulus` with `unified_stimulus`
   - Stimulus plays at `monitor_fps` (not `camera_fps`)
   - Camera captures independently at `camera_fps`
   - Duration calculated as: `total_frames / camera_fps` (where total_frames comes from stimulus generator)
   - Frame correspondence via `get_stimulus_frame_index_for_camera_frame()`

4. **Preview Mode Integration**

   **Current Architecture (OLD):**
   ```
   _set_presentation_stimulus_enabled(enabled=True)
     └─ preview_stimulus_loop.start(direction="LR")

   _set_presentation_stimulus_enabled(enabled=False)
     └─ preview_stimulus_loop.stop()
   ```

   **New Architecture (UNIFIED):**
   ```
   _set_presentation_stimulus_enabled(enabled=True)
     ├─ unified_stimulus.pre_generate_all_directions() [if not cached]
     └─ unified_stimulus.start_playback(direction="LR", monitor_fps)

   _set_presentation_stimulus_enabled(enabled=False)
     └─ unified_stimulus.stop_playback()
   ```

### Pending ⏳

5. **Mutual Exclusion Implementation**
   - Need to add checks in `start_playback()` to prevent conflicts
   - Add global state flag or check existing stimulus systems
   - Ensure old systems are stopped before new one starts

6. **Remove Competing Systems**
   - Mark `camera_stimulus.py` as DEPRECATED
   - Mark `preview_stimulus.py` as DEPRECATED
   - Remove from imports (but keep files for reference)
   - Update all IPC handlers

7. **Testing**
   - Test preview mode with unified stimulus
   - Test record mode with unified stimulus
   - Test parameter changes invalidate cache
   - Test frame correspondence calculations
   - Test mutual exclusion prevents conflicts

## Implementation Steps

### Step 1: Add baseline display method to UnifiedStimulusController

Need to add:
```python
def display_baseline(self) -> Dict[str, Any]:
    """Display background luminance screen (for baseline phases)."""
    # Read parameters
    monitor_params = self.param_manager.get_parameter_group("monitor")
    stimulus_params = self.param_manager.get_parameter_group("stimulus")

    width = monitor_params["monitor_width_px"]
    height = monitor_params["monitor_height_px"]
    luminance = stimulus_params.get("background_luminance", 0.5)

    # Publish to shared memory
    self.shared_memory.publish_black_frame(width, height, luminance)

    return {"success": True}
```

### Step 2: Refactor AcquisitionManager

Changes needed in `/Users/Adam/KimLabISI/apps/backend/src/acquisition/manager.py`:

1. **Constructor** (line 53):
   - Add `unified_stimulus=None` parameter
   - Remove `camera_triggered_stimulus=None` parameter (mark deprecated)
   - Keep `preview_stimulus_loop=None` for defensive cleanup only

2. **start_acquisition()** (line 231):
   - Remove validation for `camera_triggered_stimulus`
   - Add validation for `unified_stimulus`
   - Pre-generate stimulus if not cached

3. **_acquisition_loop()** (line 529-600):
   - Replace `camera_triggered_stimulus.start_direction()` with `unified_stimulus.start_playback()`
   - Replace polling logic with simple `time.sleep(stimulus_duration)`
   - Replace `camera_triggered_stimulus.stop_direction()` with `unified_stimulus.stop_playback()`
   - Get `monitor_fps` from parameters

4. **_get_stimulus_duration_camera_fps()** (line 695):
   - Change to use stimulus_generator.get_dataset_info() instead of camera_triggered_stimulus
   - Calculate: `total_frames / camera_fps`

5. **_publish_baseline_frame()** (line 791):
   - Change to: `unified_stimulus.display_baseline()`

### Step 3: Update main.py IPC handlers

Changes in `/Users/Adam/KimLabISI/apps/backend/src/main.py`:

1. **_set_presentation_stimulus_enabled()** (line 628):
   - Replace `preview_stimulus_loop` with `unified_stimulus`
   - Get `monitor_fps` from parameters
   - Call `unified_stimulus.start_playback()` / `stop_playback()`

2. **Services dict** (line 199):
   - Add `"unified_stimulus": unified_stimulus`
   - Mark `"preview_stimulus_loop"` as deprecated

3. **Shutdown** (line 2044):
   - Ensure `unified_stimulus.cleanup()` called before old systems

### Step 4: Add mutual exclusion

In `UnifiedStimulusController.start_playback()`:
```python
# Check if old systems are running
# (This will be removed once old systems are deleted)
if hasattr(self, 'preview_stimulus_loop') and self.preview_stimulus_loop.is_running():
    return {
        "success": False,
        "error": "Legacy preview_stimulus_loop is running. Stop it before starting unified playback."
    }

if hasattr(self, 'camera_triggered_stimulus') and self.camera_triggered_stimulus.is_running():
    return {
        "success": False,
        "error": "Legacy camera_triggered_stimulus is running. Stop it before starting unified playback."
    }
```

## File Status

### Modified ✓
- `/Users/Adam/KimLabISI/apps/backend/src/acquisition/unified_stimulus.py` - Priority 0 & 1 fixes complete

### To Modify 🔄
- `/Users/Adam/KimLabISI/apps/backend/src/acquisition/manager.py` - Integration in progress
- `/Users/Adam/KimLabISI/apps/backend/src/main.py` - IPC handler updates needed

### To Deprecate 🗑️
- `/Users/Adam/KimLabISI/apps/backend/src/acquisition/camera_stimulus.py` - Keep for reference, mark deprecated
- `/Users/Adam/KimLabISI/apps/backend/src/acquisition/preview_stimulus.py` - Keep for reference, mark deprecated

## Testing Checklist

- [ ] Preview mode: start/stop stimulus works
- [ ] Record mode: full acquisition cycle completes
- [ ] Parameter changes invalidate cache and regenerate
- [ ] Frame correspondence calculates correctly
- [ ] Mutual exclusion prevents conflicts
- [ ] Baseline phases show background_luminance
- [ ] Display log doesn't grow unbounded
- [ ] Cleanup properly unsubscribes and releases resources
