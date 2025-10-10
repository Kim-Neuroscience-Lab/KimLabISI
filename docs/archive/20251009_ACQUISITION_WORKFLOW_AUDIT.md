# ARCHIVED DOCUMENTATION

**Original File**: ACQUISITION_WORKFLOW_AUDIT.md
**Archived**: 2025-10-09
**Reason**: Documentation restructure - content consolidated into new docs/ structure

**Status**: Historical reference only. For current documentation, see:
- [Documentation Index](../README.md)
- [Architecture Overview](../architecture/overview.md)
- [Component Documentation](../components/)
- [Technical Decisions](../technical-decisions/)

---

# Original Content

# ISI Macroscope - Acquisition Workflow Architectural Audit

**Date:** October 8, 2025
**Auditor:** Claude Code (Senior Software Architect)
**Scope:** Complete acquisition workflow system (Preview / Record / Playback modes)

---

## Executive Summary

### Overall Architecture Grade: B+ (GOOD with Critical Issues)

**CRITICAL VIOLATIONS FOUND:** 4
**PRINCIPLE VIOLATIONS:** 8
**ARCHITECTURE ISSUES:** 3
**DEAD CODE:** 2
**LEGACY TERMINOLOGY:** 1

The three-mode acquisition workflow (Preview/Record/Playback) is **architecturally sound** with clear separation of responsibilities between mode controllers. However, there are **critical state management issues**, **duplicate state flags** in the frontend, and **architectural violations** where business logic has leaked into UI components.

---

## 1. CRITICAL VIOLATIONS

### 1.1 DUPLICATE STATE FLAGS - Frontend vs Backend State Divergence

**File:** `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx`
**Lines:** 97-99, 108

```typescript
const [isPreviewing, setIsPreviewing] = useState(false)
const [isAcquiring, setIsAcquiring] = useState(false)
const [acquisitionMode, setAcquisitionMode] = useState<AcquisitionMode>('preview')
const [isPlayingBack, setIsPlayingBack] = useState(false)
```

**VIOLATION:** **SINGLE SOURCE OF TRUTH (SSoT) VIOLATION**

The backend has `AcquisitionStateCoordinator` which maintains authoritative state:
- `mode` (IDLE/PREVIEW/RECORDING/PLAYBACK)
- `camera_active`
- `stimulus_active`
- `acquisition_running`

Yet the frontend maintains **competing state flags** (`isPreviewing`, `isAcquiring`, `isPlayingBack`) that can **diverge from backend truth**.

**IMPACT:**
- State synchronization bugs during mode transitions
- Race conditions where frontend shows "ACQUIRING" but backend is IDLE
- Impossible to debug state mismatches (two sources of truth)

**FIX REQUIRED:**
```typescript
// REMOVE local state flags
// const [isPreviewing, setIsPreviewing] = useState(false) ❌
// const [isAcquiring, setIsAcquiring] = useState(false) ❌

// INSTEAD: Derive from backend state
const isPreviewing = systemState?.acquisitionMode === 'preview'
const isAcquiring = systemState?.acquisitionMode === 'record'
const isPlayingBack = systemState?.acquisitionMode === 'playback'
```

---

### 1.2 BUSINESS LOGIC IN UI COMPONENT

**File:** `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx`
**Lines:** 151-254, 289-304

**VIOLATION:** **SEPARATION OF CONCERNS (SoC) VIOLATION**

The `AcquisitionViewport` component contains **extensive business logic** for:
1. Starting/stopping acquisition sequences (lines 175-254)
2. Managing camera preview lifecycle (lines 151-172)
3. Handling mode transitions manually (lines 210-211, 276-277)
4. Manual state flag management (lines 210-211, 276-286, 298-299)

```typescript
// UNACCEPTABLE: UI component doing orchestration
const startAcquisition = async () => {
  setAcquisitionStartTime(Date.now())
  setFrameCount(0)

  if (isPreviewing) {
    await sendCommand({ type: 'stop_stimulus' })
    await sendCommand({ type: 'stop_acquisition' })
    setIsPreviewing(false)  // ❌ Manual state management
    setIsAcquiring(true)    // ❌ Manual state management
    await sendCommand({ type: 'start_acquisition' })
    return
  }
  // ... more orchestration logic
}
```

**ARCHITECTURAL REQUIREMENT VIOLATION:**
> "Backend contains ALL business logic without exception"
> "Frontend is a thin client serving only as a view/interface layer"

**FIX REQUIRED:**
```typescript
// UI component should be THIN - just send commands and react to state
const startAcquisition = async () => {
  await sendCommand({ type: 'start_acquisition' })
  // State updates come from backend via systemState prop
}
```

Backend should handle ALL orchestration in `RecordModeController.activate()`.

---

### 1.3 MODE CONTROLLER INSTANTIATION INCONSISTENCY

**File:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_manager.py`
**Lines:** 84-87

```python
# Mode controllers
self.preview_controller = PreviewModeController(state_coordinator)
self.record_controller = RecordModeController(state_coordinator, self)
self.playback_controller = PlaybackModeController(state_coordinator)
```

**File:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/main.py`
**Lines:** 627, 631

```python
playback_mode_controller = PlaybackModeController(state_coordinator=acquisition_state)
# ... later ...
playback_ipc.playback_controller = playback_mode_controller
```

**VIOLATION:** **DEPENDENCY INVERSION PRINCIPLE (DIP) VIOLATION**

The `PlaybackModeController` is instantiated **TWICE**:
1. In `AcquisitionOrchestrator.__init__()` (line 87)
2. In `build_backend()` main.py (line 627)

The second instance is injected into `playback_ipc_handlers.py` globally, while the first instance inside `AcquisitionOrchestrator` is **never used**.

**IMPACT:**
- Playback mode uses a **different controller instance** than acquisition_manager expects
- State managed by acquisition_manager's playback_controller is **never read**
- Confusing dependency graph with duplicate objects

**FIX REQUIRED:**
Remove duplicate instantiation. Only create controller ONCE and inject everywhere:

```python
# main.py
playback_mode_controller = PlaybackModeController(state_coordinator=acquisition_state)
playback_ipc.playback_controller = playback_mode_controller

# acquisition_manager should RECEIVE controller, not create it
def __init__(self, ..., playback_controller=None):
    self.playback_controller = playback_controller  # Injected
```

---

### 1.4 MISSING PLAYBACK MODE INTEGRATION IN ACQUISITION MANAGER

**File:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_manager.py`
**Lines:** 89-137

```python
def set_mode(self, mode: Literal["preview", "record", "playback"], ...) -> Dict[str, Any]:
    # Delegate to appropriate mode controller
    if mode == "preview":
        result = self.preview_controller.activate(...)
    elif mode == "record":
        result = self.record_controller.activate(...)
    else:  # playback
        result = self.playback_controller.activate()  # ✅ Calls playback controller
```

**VIOLATION:** **OPEN/CLOSED PRINCIPLE (OCP) VIOLATION**

The `set_mode()` method **does call** playback_controller, but the **playback_controller** it calls is the **wrong instance** (the one created in `__init__` that's never registered with IPC handlers).

Playback IPC handlers use `playback_ipc.playback_controller` which is a **separate instance** set in main.py.

**IMPACT:**
- Calling `acquisition_manager.set_mode("playback")` will activate a **different controller** than IPC commands use
- State managed by acquisition_manager.playback_controller is isolated from IPC
- Two playback controllers with **divergent state**

---

## 2. PRINCIPLE VIOLATIONS

### 2.1 DON'T REPEAT YOURSELF (DRY) - Camera FPS Validation

**Files:**
- `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_manager.py` (lines 215-227)
- `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_ipc_handlers.py` (lines 28-40)
- `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_mode_controllers.py` (lines 172-185)

**VIOLATION:** Camera FPS validation is duplicated **THREE TIMES**:

1. **AcquisitionOrchestrator.start_acquisition():**
```python
camera_fps_value = params.get("camera_fps")
if camera_fps_value is None or not isinstance(camera_fps_value, (int, float)) or camera_fps_value <= 0:
    error_msg = (
        "camera_fps is required but not provided in acquisition parameters. "
        "Camera FPS must be set to the actual frame rate of your camera hardware "
        "for scientifically valid acquisition timing. "
        f"Received: {camera_fps_value}"
    )
    logger.error(error_msg)
    return {"success": False, "error": error_msg}
```

2. **handle_start_acquisition():**
```python
camera_fps = camera_params.get("camera_fps")
if camera_fps is None or camera_fps <= 0:
    return {
        "success": False,
        "error": (
            "camera_fps is required but not configured in camera parameters. "
            "Camera FPS must be set to the actual frame rate of your camera hardware "
            "for scientifically valid acquisition timing."
        )
    }
```

3. **RecordModeController.activate():**
```python
camera_fps = camera_params.get("camera_fps")
if camera_fps is None or camera_fps <= 0:
    return {
        "success": False,
        "error": (
            "camera_fps is required but not configured in camera parameters. "
            "Camera FPS must be set to the actual frame rate of your camera hardware "
            "for scientifically valid acquisition timing."
        )
    }
```

**FIX REQUIRED:** Extract to single validation function:
```python
def validate_camera_fps(params: Dict) -> tuple[Optional[float], Optional[str]]:
    """Validate camera FPS parameter. Returns (fps, error_message)."""
    camera_fps = params.get("camera_fps")
    if camera_fps is None or camera_fps <= 0:
        return None, "camera_fps is required and must be > 0"
    return float(camera_fps), None
```

---

### 2.2 DRY VIOLATION - Baseline Frame Display

**File:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_manager.py`
**Lines:** 650-689

```python
def _display_black_screen(self) -> None:
    # Monitor dimension validation (lines 661-681)
    width = monitor_params.get("monitor_width_px")
    if width is None:
        raise RuntimeError("monitor_width_px is required...")
    if not isinstance(width, int) or width <= 0:
        raise RuntimeError(f"monitor_width_px must be a positive integer...")
    # ... same for height

    shared_memory.publish_black_frame(width, height)

def _publish_baseline_frame(self) -> float:
    self._display_black_screen()
    return float(self.baseline_sec)
```

`_publish_baseline_frame()` is called **5 times** in acquisition_loop:
- Line 392 (initial baseline)
- Line 476 (between trials)
- Line 481 (after last cycle)
- Line 500 (between directions)
- Line 506 (final baseline)

Each call retrieves and validates monitor parameters **redundantly**. Should pre-fetch once.

---

### 2.3 SINGLE RESPONSIBILITY PRINCIPLE (SRP) - AcquisitionOrchestrator Does Too Much

**File:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_manager.py`

`AcquisitionOrchestrator` has **8 distinct responsibilities**:

1. **Acquisition sequencing** (lines 380-537: `_acquisition_loop()`)
2. **Phase management** (lines 538-561: `_enter_phase()`)
3. **Timing calculations** (lines 571-648: stimulus duration methods)
4. **Display rendering** (lines 650-689: black screen display)
5. **Mode controller management** (lines 84-87, 89-137: mode controllers)
6. **Data recorder lifecycle** (lines 248-293: recorder creation)
7. **Timestamp synchronization** (lines 694-718: synchronization tracking)
8. **Camera-triggered stimulus control** (lines 405-418, 434-469, 484-489)

**VIOLATION:** Class has **8 reasons to change** (violates SRP).

**FIX REQUIRED:** Split into focused classes:
- `AcquisitionSequencer` - Phase transitions only
- `AcquisitionTimingCalculator` - Timing math
- `DisplayController` - Screen rendering
- `ModeCoordinator` - Mode switching

---

### 2.4 INTERFACE SEGREGATION PRINCIPLE (ISP) - ModeController Base Class Too Sparse

**File:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_mode_controllers.py`
**Lines:** 12-39

```python
class AcquisitionModeController(ABC):
    @abstractmethod
    def activate(self, **kwargs) -> Dict[str, Any]:
        pass

    @abstractmethod
    def deactivate(self) -> Dict[str, Any]:
        pass
```

**VIOLATION:** Base class defines only 2 methods but:
- `PreviewModeController` needs only `activate()` (deactivate is no-op)
- `RecordModeController` needs orchestrator reference
- `PlaybackModeController` needs `get_session_data()` which isn't in base class

**FIX:** Either:
1. Make `deactivate()` optional (not abstract)
2. Add `get_data()` to base class for polymorphism
3. Split into mode-specific interfaces

---

### 2.5 DEPENDENCY INVERSION - Global Module Instance

**File:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/playback_ipc_handlers.py`
**Lines:** 9-10

```python
# Global playback controller instance (will be set by main.py)
playback_controller = None
```

**VIOLATION:** IPC handlers depend on **global mutable state** set by main.py.

This violates dependency injection - handlers should receive controller via proper DI, not global assignment.

**FIX:** Use service locator pattern or pass controller to handler registration.

---

### 2.6 YAGNI VIOLATION - Unused Mode Controllers in AcquisitionOrchestrator

**File:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_manager.py`
**Lines:** 84-87

```python
# Mode controllers
self.preview_controller = PreviewModeController(state_coordinator)
self.record_controller = RecordModeController(state_coordinator, self)
self.playback_controller = PlaybackModeController(state_coordinator)
```

**VIOLATION:** These controllers are instantiated but:
- Only used in `set_mode()` (lines 117-128)
- `set_mode()` is only called from IPC handler (lines 61-82 in acquisition_ipc_handlers.py)
- Preview/playback modes don't use acquisition_manager orchestration loop

**QUESTION:** Why does acquisition_manager own these controllers if:
1. Playback IPC uses a different controller instance?
2. Preview mode just generates single frames (no orchestration)?
3. Only record mode uses the acquisition loop?

**RECOMMENDATION:** Move controllers to service registry, not acquisition_manager.

---

### 2.7 LISKOV SUBSTITUTION PRINCIPLE (LSP) - Mode Controllers Not Interchangeable

**File:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_mode_controllers.py`

```python
# RecordModeController requires orchestrator
def __init__(self, state_coordinator, acquisition_orchestrator):
    super().__init__(state_coordinator)
    self.acquisition_orchestrator = acquisition_orchestrator  # ❌ Extra dependency

# PlaybackModeController has extra method not in base class
def get_session_data(self, direction: Optional[str] = None):
    # Not in AcquisitionModeController interface
```

**VIOLATION:** Cannot substitute controllers polymorphically because:
1. RecordModeController requires extra orchestrator parameter
2. PlaybackModeController adds methods not in base class
3. activate() signatures differ (param_manager vs session_path)

---

### 2.8 OPEN/CLOSED PRINCIPLE - Mode Switching via If/Else Chain

**File:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_manager.py`
**Lines:** 116-128

```python
if mode == "preview":
    result = self.preview_controller.activate(...)
elif mode == "record":
    result = self.record_controller.activate(...)
else:  # playback
    result = self.playback_controller.activate()
```

**VIOLATION:** Adding new mode requires modifying `set_mode()`. Should use strategy pattern with mode registry.

---

## 3. ARCHITECTURE ISSUES

### 3.1 CAMERA ACQUISITION PATH - No Playback Bypass

**File:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/camera_manager.py`
**Lines:** 614-802 (`_acquisition_loop`)

**ISSUE:** Camera acquisition loop always runs when camera is active. There's **no check for playback mode** to bypass live camera capture.

```python
def _acquisition_loop(self):
    # Should check: if playback mode, don't capture from camera
    while not self.stop_acquisition_event.is_set():
        frame = self.capture_frame()  # ❌ Always captures from live camera
```

**IMPACT:** During playback mode, if camera is active, it will **still capture live frames** even though playback should use **recorded frames**.

**FIX REQUIRED:**
```python
def _acquisition_loop(self):
    from .service_locator import get_services
    services = get_services()

    while not self.stop_acquisition_event.is_set():
        # Skip live capture in playback mode
        if services.acquisition_state.is_playback:
            time.sleep(0.1)
            continue

        frame = self.capture_frame()
        # ...
```

---

### 3.2 STIMULUS GENERATION - Three Systems, Unclear Separation

**Files:**
- `stimulus_manager.py` - Base stimulus generation + IPC handlers
- `camera_triggered_stimulus.py` - Record mode synchronous generation
- `stimulus_controller.py` - Preview mode async wrapper

**ISSUE:** Documentation claims clear separation, but:

**stimulus_controller.py (lines 1-10):**
```python
"""⚠️  WARNING: PREVIEW MODE ONLY - NOT FOR RECORD MODE

This module uses async/real-time stimulus generation and is ONLY suitable for preview mode.
For scientifically valid data recording, use CameraTriggeredStimulusController instead.
"""
```

**HOWEVER:**
- `stimulus_controller` is injected into acquisition_manager (line 636 in main.py)
- acquisition_manager also has `camera_triggered_stimulus` (line 637)
- Both are available simultaneously - nothing prevents using wrong one

**RECOMMENDATION:**
- Make `stimulus_controller` raise error if used during record mode
- Add state checks in both controllers to validate they're used in correct mode

---

### 3.3 DATA RECORDING - Thread Safety Concerns

**File:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/camera_manager.py`
**Lines:** 71-80, 720-740

**Issue:** Data recorder is accessed from camera acquisition thread:

```python
# Thread-safe getter
def get_data_recorder(self):
    with self.acquisition_lock:
        return self._data_recorder

# But used without re-acquiring lock
data_recorder = self.get_data_recorder()
if data_recorder and data_recorder.is_recording:  # ❌ Lock released, could change
    data_recorder.record_camera_frame(...)  # ❌ No lock protection
```

**IMPACT:** `data_recorder` could be set to `None` between check and use, causing AttributeError.

**FIX:** Hold lock during entire read-check-use sequence or use local copy.

---

## 4. COMPETING SYSTEMS REPORT

### 4.1 DUPLICATE PLAYBACK CONTROLLER INSTANCES

**CONFIRMED DUPLICATE:**

**Instance 1 (acquisition_manager.py line 87):**
```python
self.playback_controller = PlaybackModeController(state_coordinator)
```

**Instance 2 (main.py line 627):**
```python
playback_mode_controller = PlaybackModeController(state_coordinator=acquisition_state)
playback_ipc.playback_controller = playback_mode_controller
```

**WHO USES WHICH:**
- acquisition_manager.set_mode("playback") → Uses Instance 1
- IPC handler "list_sessions" → Uses Instance 2
- IPC handler "load_session" → Uses Instance 2
- IPC handler "get_session_data" → Uses Instance 2

**RESULT:** **COMPETING PLAYBACK CONTROLLERS** with divergent state.

---

### 4.2 DUPLICATE IPC HANDLERS - NONE FOUND ✅

All IPC handlers are registered exactly once. No duplicates detected.

**Verified handlers:**
- Acquisition: 5 handlers (start/stop/status/mode/black_screen)
- Camera: 10 handlers (detect/capabilities/stream/capture/histogram/correlation/etc)
- Stimulus: 11 handlers (parameters/config/frame/preview/start/stop/etc)
- Playback: 4 handlers (list/load/get_data/unload)
- Display: 3 handlers (detect/capabilities/select)

**Total:** 33 unique IPC handlers, all registered once in their respective modules.

---

### 4.3 DUPLICATE STATE TRACKING - Frontend vs Backend

**Backend (AcquisitionStateCoordinator):**
- `_mode` (IDLE/PREVIEW/RECORDING/PLAYBACK)
- `_camera_active`
- `_stimulus_active`
- `_acquisition_running`
- `_current_session`

**Frontend (AcquisitionViewport.tsx):**
- `isPreviewing` (line 97)
- `isAcquiring` (line 98)
- `acquisitionMode` (line 99)
- `isPlayingBack` (line 108)

**VIOLATION:** Two sources of truth with no synchronization mechanism. Frontend state is set manually (lines 210-211, 276-277, 298-299) and can diverge from backend.

---

## 5. DEAD CODE REPORT

### 5.1 Unused Imports

**File:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_manager.py`
**Line:** 5

```python
from typing import Optional, Dict, Any, List, Literal
```

`List` is imported but never used (all lists use lowercase `list` from Python 3.9+).

---

### 5.2 Unreachable Code Path

**File:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_manager.py`
**Lines:** 343-345

```python
with self._state_lock:
    self.phase = AcquisitionPhase.IDLE
    self.target_mode = "preview"
```

This code executes after acquisition stops, setting mode to "preview". However, this state is never read - the next acquisition always calls `set_mode()` explicitly.

---

## 6. LEGACY CODE / TERMINOLOGY

### 6.1 LEGACY TERMINOLOGY - "correlation" vs "synchronization"

**Found in:**
- `/Users/Adam/KimLabISI/apps/backend/src/isi_control/camera_manager.py` line 952

```python
@ipc_handler("get_correlation_data")  # Keep IPC command name for backward compatibility
def handle_get_synchronization_data(command: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_correlation_data IPC command - get timestamp synchronization statistics"""
```

**Comment says:** "Keep IPC command name for backward compatibility"

**ISSUE:** IPC command is named `get_correlation_data` but:
- Handler is named `handle_get_synchronization_data`
- Returns synchronization data, not correlation
- File is named `timestamp_synchronization_tracker.py` (not correlation_tracker.py)

**RECOMMENDATION:**
- Rename IPC command to `get_synchronization_data`
- Update frontend to use new name
- Remove "backward compatibility" comment (no legacy clients exist)

---

## 7. MODE CONTROLLER ANALYSIS

### 7.1 PreviewModeController ✅ CLEAN

**Responsibilities:**
1. Transition to preview state
2. Generate single stimulus frame
3. Write to shared memory
4. Notify frontend via IPC

**Dependencies:**
- StimulusGenerator (via service locator)
- SharedMemoryService (via service locator)
- AcquisitionStateCoordinator (injected)

**Verdict:** Clean, focused, no issues.

---

### 7.2 RecordModeController ⚠️ NEEDS REFACTORING

**Issues:**
1. Requires orchestrator reference (breaks LSP)
2. Duplicates camera FPS validation
3. activate() starts acquisition but doesn't wait for completion
4. No way to query recording progress

**Responsibilities:**
1. Validate acquisition parameters
2. Transition to recording state
3. Start acquisition orchestrator
4. Deactivate stops acquisition

**Verdict:** Functional but violates DRY and LSP.

---

### 7.3 PlaybackModeController ⚠️ DUPLICATE INSTANCES

**Issues:**
1. **CRITICAL:** Two instances exist (see Section 4.1)
2. Missing from acquisition_manager's service injection
3. get_session_data() not in base class interface

**Responsibilities:**
1. List available sessions
2. Load session metadata
3. Read session data (events, angles, camera frames)
4. Deactivate unloads session

**Verdict:** Architecture is correct, but instantiation is broken.

---

## 8. CAMERA ACQUISITION PATHS

### 8.1 LIVE CAMERA CAPTURE ✅ CLEAN

**Path:** camera_manager._acquisition_loop() (lines 614-801)

**Workflow:**
1. Capture frame from OpenCV
2. Get timestamp (hardware or software)
3. Trigger camera-triggered stimulus (if active)
4. Crop and convert to RGBA
5. Record to data_recorder (if recording)
6. Write to shared memory for frontend
7. Track synchronization (if enabled)

**Verdict:** Clean separation, no issues.

---

### 8.2 PLAYBACK "CAPTURE" ❌ NOT IMPLEMENTED

**Expected:** PlaybackModeController.get_session_data() should return frames that frontend displays.

**Current state:**
- Playback controller loads session data ✅
- Returns camera frames from HDF5 ✅
- **BUT:** No integration with camera_manager's display path
- **Frontend** must manually read playback frames (lines 762-777 in AcquisitionViewport.tsx)

**ISSUE:** Playback doesn't use camera viewport - it should feed playback frames into the same canvas as live camera.

---

### 8.3 CAMERA BYPASS IN PLAYBACK MODE ❌ MISSING

As noted in Section 3.1, camera acquisition loop doesn't check for playback mode. Live camera will capture even during playback.

---

## 9. STIMULUS GENERATION PATHS

### 9.1 PREVIEW MODE STIMULUS ✅ CORRECT

**Path:**
1. PreviewModeController.activate() calls stimulus_generator.generate_frame_at_index()
2. Single frame generated
3. Written to shared memory
4. Frontend displays static frame

**Used by:** Preview mode only
**Verdict:** Clean, correct separation.

---

### 9.2 RECORD MODE STIMULUS ✅ CORRECT

**Path:**
1. Camera captures frame
2. camera_manager calls camera_triggered_stimulus.generate_next_frame()
3. Synchronous stimulus generation (camera-triggered)
4. Frame written to shared memory
5. Data recorder saves stimulus event

**Used by:** Record mode only
**Verdict:** Perfect 1:1 camera-stimulus correspondence.

---

### 9.3 PLAYBACK MODE STIMULUS ⚠️ UNCLEAR

**Expected:** Playback should replay recorded stimulus angles/frames.

**Current state:**
- Session data includes stimulus angles (from {direction}_stimulus.h5) ✅
- PlaybackModeController.get_session_data() returns angles ✅
- **BUT:** No code regenerates stimulus frames from angles during playback
- **Frontend** must handle stimulus display manually

**RECOMMENDATION:** Add method to regenerate stimulus frames from recorded angles:
```python
def get_playback_stimulus_frame(self, direction: str, frame_index: int):
    """Regenerate stimulus frame from recorded angle."""
    session_data = self.get_session_data(direction)
    angle = session_data['stimulus_angles'][frame_index]
    return stimulus_generator.generate_frame_at_angle(direction, angle)
```

---

### 9.4 COMPETING STIMULUS SYSTEMS? ❌ NO

**Verdict:** Three stimulus systems exist but are **properly separated by mode**:
- stimulus_manager.py - Base generation (used by all modes)
- camera_triggered_stimulus.py - Record mode only
- stimulus_controller.py - Preview mode wrapper only

No competing implementations detected.

---

## 10. STATE MANAGEMENT ANALYSIS

### 10.1 BACKEND STATE COORDINATOR ✅ CORRECT DESIGN

**File:** `acquisition_state.py`

**Single Source of Truth:**
- `_mode` (IDLE/PREVIEW/RECORDING/PLAYBACK)
- `_camera_active`
- `_stimulus_active`
- `_acquisition_running`
- `_current_session`

**Thread-safe:** Uses `threading.Lock()`

**State Transitions:**
- `transition_to_preview()` - Can't transition from RECORDING
- `transition_to_recording()` - No restrictions
- `transition_to_playback()` - Can't transition from RECORDING
- `transition_to_idle()` - Always allowed, resets all flags

**Verdict:** Excellent design, proper SSoT.

---

### 10.2 FRONTEND STATE FLAGS ❌ VIOLATES SSoT

**File:** `AcquisitionViewport.tsx`

**Local state flags:**
```typescript
const [isPreviewing, setIsPreviewing] = useState(false)
const [isAcquiring, setIsAcquiring] = useState(false)
const [acquisitionMode, setAcquisitionMode] = useState<AcquisitionMode>('preview')
const [isPlayingBack, setIsPlayingBack] = useState(false)
```

**Manual state updates:**
- Line 210: `setIsPreviewing(false)`
- Line 211: `setIsAcquiring(true)`
- Line 276: `setIsAcquiring(false)`
- Line 277: `setIsPreviewing(true)`
- Line 298-299: `setIsPreviewing(false); setIsAcquiring(false)`

**CRITICAL ISSUE:** These flags are set **manually** based on **frontend logic**, not synchronized with backend `AcquisitionStateCoordinator`.

**SYNCHRONIZATION BUG SCENARIO:**
1. User clicks "Start Acquisition"
2. Frontend sets `isAcquiring = true` (line 211)
3. Backend command fails (camera error)
4. Frontend **still shows** "ACQUIRING" because flag wasn't reset
5. Backend state is IDLE, frontend state is ACQUIRING
6. **State divergence!**

**FIX:** Derive state from `systemState.acquisitionMode` prop (which should come from backend).

---

### 10.3 STATE SYNC MECHANISM ⚠️ INCOMPLETE

**How backend state reaches frontend:**

1. Backend updates `AcquisitionStateCoordinator`
2. ??? (No explicit sync mechanism found)
3. Frontend receives state via `systemState` prop

**MISSING:**
- No IPC message sending state updates
- No polling mechanism for state
- Frontend must infer state from other messages (acquisition_progress, etc.)

**RECOMMENDATION:** Add explicit state sync:
```python
@ipc_handler("get_acquisition_state")
def handle_get_acquisition_state(command):
    services = get_services()
    return services.acquisition_state.get_state_summary()
```

Frontend should poll this or receive push updates.

---

## 11. DATA RECORDING PATH

### 11.1 RECORD MODE RECORDING ✅ CORRECT

**Path:**
1. acquisition_manager creates data_recorder (lines 248-293)
2. Passes to camera_manager (line 292)
3. Camera acquisition loop records frames (lines 722-740)
4. Acquisition loop records stimulus events (lines 730-740)
5. acquisition_manager saves session (lines 524-530)

**Thread safety:** Protected by `acquisition_lock`

**Verdict:** Clean, thread-safe recording path.

---

### 11.2 PREVIEW MODE RECORDING ✅ CORRECTLY DISABLED

**Verification:**
- data_recorder only created in `start_acquisition()` (record mode)
- Preview mode doesn't create recorder
- camera_manager checks `if data_recorder and data_recorder.is_recording` (line 722)

**Verdict:** Preview mode correctly bypasses recording.

---

### 11.3 PLAYBACK MODE RECORDING ✅ CORRECTLY DISABLED

**Verification:**
- Playback mode reads from data_recorder output files
- No recording occurs during playback
- Playback controller is read-only

**Verdict:** Playback correctly reads recorded data without recording.

---

## 12. IPC HANDLER ROUTING

### 12.1 ACQUISITION HANDLERS ✅ CLEAN

**File:** `acquisition_ipc_handlers.py`

Handlers:
1. `start_acquisition` → acquisition_manager.start_acquisition()
2. `stop_acquisition` → acquisition_manager.stop_acquisition()
3. `get_acquisition_status` → acquisition_manager.get_status()
4. `set_acquisition_mode` → acquisition_manager.set_mode()
5. `display_black_screen` → acquisition_manager.display_black_screen()

**Verdict:** Clean delegation, no duplicates.

---

### 12.2 PLAYBACK HANDLERS ⚠️ WRONG CONTROLLER INSTANCE

**File:** `playback_ipc_handlers.py`

Handlers:
1. `list_sessions` → playback_controller.activate(None)
2. `load_session` → playback_controller.activate(session_path)
3. `get_session_data` → playback_controller.get_session_data(direction)
4. `unload_session` → playback_controller.deactivate()

**ISSUE:** `playback_controller` is global variable set in main.py, **NOT** the instance in acquisition_manager.

**Verdict:** Handlers work but use wrong controller instance (see Section 4.1).

---

### 12.3 CAMERA HANDLERS ✅ CLEAN

**File:** `camera_manager.py`

10 handlers, all delegate to camera_manager singleton. No duplicates.

---

### 12.4 STIMULUS HANDLERS ✅ CLEAN

**File:** `stimulus_manager.py`

11 handlers, all delegate to stimulus_generator. No duplicates.

---

## 13. FRONTEND MODE HANDLING

### 13.1 MODE SWITCHING ⚠️ MANUAL ORCHESTRATION

**Lines 99, 819-823:**

```typescript
const [acquisitionMode, setAcquisitionMode] = useState<AcquisitionMode>('preview')

// Auto-start preview when camera selected
useEffect(() => {
  if (acquisitionMode !== 'playback' && cameraParams?.selected_camera &&
      systemState?.isConnected && !isPreviewing && !isAcquiring) {
    startPreview()
  }
}, [cameraParams?.selected_camera, systemState?.isConnected, isPreviewing, isAcquiring, acquisitionMode])
```

**ISSUE:** Mode switching logic is in frontend. Backend should control when preview starts.

---

### 13.2 LEFTOVER EFFECTS ⚠️ POTENTIAL ISSUE

When switching from record → preview:

**Lines 275-285:**
```typescript
setIsAcquiring(false)
setIsPreviewing(true)

await sendCommand?.({ type: 'start_stimulus' })
```

**ISSUE:** If `start_stimulus` fails, state flags are already updated (state divergence).

**FIX:** Update state only after backend confirms success.

---

### 13.3 PLAYBACK MODE CAMERA DISABLE ❌ NOT IMPLEMENTED

**Lines 394-456:** Camera frame listener runs when `isPreviewing || isAcquiring`

**MISSING:** Should also check `acquisitionMode !== 'playback'` to disable live camera during playback.

```typescript
// CURRENT:
if (!isPreviewing && !isAcquiring) return

// SHOULD BE:
if (acquisitionMode === 'playback' || (!isPreviewing && !isAcquiring)) return
```

---

### 13.4 CONTROL BUTTONS ✅ CORRECTLY DISABLED

**Lines 1243-1267:**

Buttons are properly disabled based on mode:
- Preview mode: All playback controls disabled
- Record mode: Only record/stop enabled
- Playback mode: All playback controls enabled

**Verdict:** Button state management is correct.

---

## 14. INTEGRATION ISSUES

### 14.1 PLAYBACK MODE NOT FULLY INTEGRATED

**Missing integration points:**

1. **Camera viewport bypass:** Playback frames should display in camera canvas, but frontend manually handles playback frames separately (lines 762-777)

2. **Shared memory integration:** Playback doesn't use camera_manager's shared memory path

3. **Controller instance mismatch:** acquisition_manager.playback_controller is not the same as playback_ipc.playback_controller

---

### 14.2 STATE SYNC PROBLEMS

Frontend and backend state can diverge (see Section 10.2).

**Recommendation:** Add periodic state sync or push-based updates.

---

### 14.3 DEPENDENCY INJECTION INCONSISTENT

**Good DI:**
- synchronization_tracker injected everywhere (lines 634-641 in main.py)
- acquisition_state injected everywhere

**Bad DI:**
- playback_controller set as global variable (line 631 in main.py)
- data_recorder created dynamically instead of injected

---

## 15. CLEANUP RECOMMENDATIONS

### 15.1 CODE TO DELETE

1. **Duplicate playback controller instantiation** (acquisition_manager.py line 87)
   ```python
   # DELETE THIS:
   self.playback_controller = PlaybackModeController(state_coordinator)
   ```

2. **Unused imports** (acquisition_manager.py line 5)
   ```python
   # REMOVE List from import:
   from typing import Optional, Dict, Any, List, Literal
   # CHANGE TO:
   from typing import Optional, Dict, Any, Literal
   ```

3. **Unreachable mode reset** (acquisition_manager.py line 344)
   ```python
   # DELETE (never read):
   self.target_mode = "preview"
   ```

---

### 15.2 CODE TO CONSOLIDATE

1. **Camera FPS validation** - Extract to single function (see Section 2.1)

2. **Monitor parameter validation** - Extract from `_display_black_screen()` to reusable validator

3. **Mode controller instantiation** - Move to service registry, remove from acquisition_manager

---

### 15.3 CODE TO MOVE

1. **Frontend state flags** - Delete local state, derive from backend (see Section 10.2)

2. **Frontend orchestration logic** - Move to backend controllers (see Section 1.2)

3. **Playback controller** - Move from global variable to service registry

---

### 15.4 NAMING TO FIX

1. **IPC command name** - Rename `get_correlation_data` to `get_synchronization_data` (see Section 6.1)

2. **Handler function name** - Rename `handle_get_synchronization_data` to match new IPC name

3. **Terminology** - Remove all "correlation" references, use "synchronization" consistently

---

## 16. CRITICAL BUGS

### 16.1 SHOW-STOPPERS

**NONE FOUND** - System is functional.

---

### 16.2 MODE SWITCHING BUGS

**Potential race condition:** Frontend sets state flags before backend confirms mode change (see Section 13.2)

**Fix:** Use async/await properly and update state only after success:

```typescript
const result = await sendCommand({ type: 'start_acquisition' })
if (result?.success) {
  // State will update from backend state sync
} else {
  // Don't update local state
}
```

---

### 16.3 STATE MANAGEMENT ISSUES

**State divergence bug:** Frontend and backend can show different modes (see Section 10.2)

**Impact:** User sees "ACQUIRING" but backend stopped due to error.

**Fix:** Implement proper state synchronization (see Section 10.3).

---

## 17. ARCHITECTURAL RECOMMENDATIONS

### 17.1 IMMEDIATE FIXES (P0 - Critical)

1. **Fix duplicate playback controller** (Section 1.3)
   - Remove instantiation from acquisition_manager
   - Inject single instance everywhere

2. **Fix frontend state management** (Section 1.1)
   - Remove local state flags
   - Derive from backend systemState

3. **Move frontend orchestration to backend** (Section 1.2)
   - Remove complex logic from AcquisitionViewport
   - Let controllers handle all orchestration

---

### 17.2 SHORT-TERM IMPROVEMENTS (P1 - High Priority)

1. **Extract camera FPS validation** (Section 2.1)
2. **Add playback camera bypass** (Section 3.1)
3. **Implement state sync mechanism** (Section 10.3)
4. **Fix playback frame display** (Section 14.1)

---

### 17.3 LONG-TERM REFACTORING (P2 - Medium Priority)

1. **Split AcquisitionOrchestrator** (Section 2.3)
   - Create AcquisitionSequencer
   - Create TimingCalculator
   - Create DisplayController

2. **Improve mode controller polymorphism** (Section 2.7)
   - Unify constructor signatures
   - Add common interface methods

3. **Replace global DI with proper injection** (Section 2.5)

---

## 18. MODE WORKFLOW DIAGRAMS

### 18.1 PREVIEW MODE WORKFLOW ✅

```
User clicks "Preview"
    ↓
Frontend: setAcquisitionMode('preview')
    ↓
Frontend: sendCommand('set_acquisition_mode', mode='preview')
    ↓
Backend: acquisition_manager.set_mode('preview')
    ↓
Backend: preview_controller.activate()
    ↓
Backend: stimulus_generator.generate_frame_at_index()
    ↓
Backend: shared_memory.write_preview_frame()
    ↓
Backend: ipc.send_sync_message('stimulus_preview')
    ↓
Frontend: Receives stimulus frame metadata
    ↓
Frontend: Reads shared memory
    ↓
Frontend: Displays frame on canvas
```

**Verdict:** Clean, correct flow.

---

### 18.2 RECORD MODE WORKFLOW ✅

```
User clicks "Record"
    ↓
Frontend: sendCommand('start_acquisition')
    ↓
Backend: acquisition_ipc_handlers.handle_start_acquisition()
    ↓
Backend: acquisition_manager.start_acquisition()
    ↓
Backend: Creates data_recorder
    ↓
Backend: Starts acquisition thread (_acquisition_loop)
    ↓
LOOP for each direction:
    ↓
    Backend: camera_triggered_stimulus.start_direction()
    ↓
    Backend: data_recorder.start_recording()
    ↓
    LOOP for each cycle:
        ↓
        Camera captures frame
        ↓
        Camera triggers stimulus generation
        ↓
        data_recorder records both
    ↓
    Backend: camera_triggered_stimulus.stop_direction()
    ↓
    Backend: data_recorder.stop_recording()
    ↓
Backend: data_recorder.save_session()
    ↓
Backend: Sends acquisition_progress updates to frontend
```

**Verdict:** Clean, camera-triggered synchronization.

---

### 18.3 PLAYBACK MODE WORKFLOW ⚠️ INCOMPLETE

```
User selects "Playback" mode
    ↓
Frontend: sendCommand('list_sessions')
    ↓
Backend: playback_ipc.handle_list_sessions()
    ↓
Backend: playback_controller.activate(None)  # Lists sessions
    ↓
Frontend: Displays session list
    ↓
User selects session
    ↓
Frontend: sendCommand('load_session', session_path=...)
    ↓
Backend: playback_ipc.handle_load_session()
    ↓
Backend: playback_controller.activate(session_path)
    ↓
Backend: Loads metadata.json
    ↓
Frontend: sendCommand('get_session_data', direction=...)
    ↓
Backend: playback_controller.get_session_data(direction)
    ↓
Backend: Loads HDF5 data (camera frames, stimulus angles)
    ↓
Frontend: Manually renders frames from returned data  # ❌ Should use camera viewport
    ↓
Frontend: Manual playback loop (setInterval)  # ❌ Should use backend timing
```

**Issues:**
1. Frontend manually handles playback rendering
2. Doesn't integrate with camera_manager's display path
3. Playback timing is frontend-driven (should be backend)

**Recommendation:** Implement backend playback streaming:
```python
@ipc_handler("start_playback")
def handle_start_playback(direction: str, fps: float):
    # Stream playback frames to shared memory at specified FPS
    # Reuse camera_manager's display path
```

---

## 19. SUMMARY & FINAL GRADE

### Overall Architecture: B+ (GOOD)

**Strengths:**
1. ✅ Clear separation of three mode controllers
2. ✅ Clean camera-triggered stimulus for record mode
3. ✅ Thread-safe data recording
4. ✅ No duplicate IPC handlers
5. ✅ Single source of truth in backend (AcquisitionStateCoordinator)
6. ✅ Proper dependency injection for most services

**Critical Issues:**
1. ❌ Duplicate playback controller instances (P0)
2. ❌ Frontend state flags violate SSoT (P0)
3. ❌ Business logic in UI component (P0)
4. ❌ Missing state synchronization (P1)

**Violations Summary:**
- **SOLID:** 5 violations (SRP, OCP, LSP, ISP, DIP)
- **DRY:** 2 violations (camera FPS, baseline display)
- **SoC:** 1 violation (UI orchestration)
- **SSoT:** 1 violation (frontend state)
- **YAGNI:** 1 violation (unused controllers)

**Code Quality:**
- Dead code: Minimal (2 instances)
- Legacy terminology: 1 instance (correlation → synchronization)
- Commented code: None found
- Unused imports: 1 instance

**Recommendation:**
Fix the 4 critical issues (Sections 1.1-1.4) immediately. The system is functional but has architectural debt that will cause bugs as complexity grows.

---

## 20. ACTION PLAN

### Phase 1: Critical Fixes (1-2 days)

1. **Fix duplicate playback controller**
   - File: `acquisition_manager.py`, `main.py`
   - Remove duplicate instantiation
   - Inject single controller instance

2. **Fix frontend state management**
   - File: `AcquisitionViewport.tsx`
   - Remove isPreviewing, isAcquiring, isPlayingBack
   - Derive from systemState.acquisitionMode

3. **Move UI orchestration to backend**
   - File: `AcquisitionViewport.tsx`, `acquisition_mode_controllers.py`
   - Simplify startAcquisition/stopAcquisition
   - Move orchestration to RecordModeController

### Phase 2: High-Priority Improvements (3-5 days)

4. **Extract DRY violations**
   - Create validate_camera_fps()
   - Create validate_monitor_params()

5. **Add state synchronization**
   - Create get_acquisition_state IPC handler
   - Frontend polls or receives push updates

6. **Fix playback integration**
   - Playback frames use camera viewport
   - Add backend-driven playback streaming

### Phase 3: Refactoring (1-2 weeks)

7. **Split AcquisitionOrchestrator**
8. **Unify mode controller interfaces**
9. **Replace global DI with proper injection**

---

**End of Audit Report**

Generated by Claude Code - Senior Software Architect
All file paths are absolute as required.
