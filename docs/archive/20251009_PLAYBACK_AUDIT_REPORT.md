# ARCHIVED DOCUMENTATION

**Original File**: PLAYBACK_AUDIT_REPORT.md
**Archived**: 2025-10-09
**Reason**: Documentation restructure - content consolidated into new docs/ structure

**Status**: Historical reference only. For current documentation, see:
- [Documentation Index](../README.md)
- [Architecture Overview](../architecture/overview.md)
- [Component Documentation](../components/)
- [Technical Decisions](../technical-decisions/)

---

# Original Content

# ISI Macroscope Playback System - Architectural & Implementation Audit

**Date:** 2025-10-08
**Auditor:** Claude Code (Senior Software Architect)
**System:** ISI Macroscope Neuroscience Data Acquisition System
**Component:** Playback Mode Implementation

---

## Executive Summary

This audit evaluates the playback system implementation for recorded acquisition sessions. The system was designed with on-demand frame loading from HDF5 files, RGB-to-grayscale conversion, service registry integration, and IPC-based communication.

**Overall Assessment:** ⚠️ **CRITICAL ISSUES FOUND - SYSTEM WILL FAIL**

Multiple critical bugs will cause the playback system to fail completely. The implementation contains fundamental errors in data loading, state management, and IPC communication that violate basic software engineering principles.

---

## Critical Issues (MUST FIX IMMEDIATELY)

### 🚨 CRITICAL #1: Incorrect On-Demand Loading Implementation

**Location:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_mode_controllers.py:392-406`

**Issue:** The `get_session_data()` method LOADS ALL FRAMES INTO MEMORY despite claiming to implement "on-demand" loading.

```python
# Lines 392-408 - THIS IS WRONG
with h5py.File(camera_path, 'r') as f:
    frames_data = f['frames'][:]  # ❌ LOADS ENTIRE DATASET INTO MEMORY
    timestamps_data = f['timestamps'][:]  # ❌ LOADS ALL TIMESTAMPS

    logger.info(f"📹 Loaded {len(frames_data)} frames from {direction}_camera.h5")

    # Don't load frames into memory - just store metadata
    # Frames will be loaded on-demand via get_playback_frame
    camera_data = {
        "frame_count": len(frames_data),  # ❌ Uses loaded data
        "frame_shape": frames_data[0].shape if len(frames_data) > 0 else None,
        "has_frames": True,
        "camera_path": camera_path
    }
```

**Why This Is Wrong:**
- The comment says "Don't load frames into memory" but the code DOES load frames with `f['frames'][:]`
- The `[:]` operator creates a NumPy array copy of the ENTIRE dataset
- For a 10,000 frame session at 640×480 RGB, this loads ~900MB into memory
- This defeats the entire purpose of on-demand loading
- HDF5 file is closed immediately after loading, so `camera_path` is useless

**Consequence:** Memory exhaustion for large sessions, slow loading times, system crashes.

**Fix Required:**
```python
# CORRECT implementation - only read metadata
with h5py.File(camera_path, 'r') as f:
    frame_count = len(f['frames'])
    frame_shape = f['frames'].shape[1:] if frame_count > 0 else None

    camera_data = {
        "frame_count": frame_count,
        "frame_shape": list(frame_shape) if frame_shape else None,
        "has_frames": True,
        # No frames loaded - get_playback_frame will load on-demand
    }
```

**Severity:** CRITICAL - This violates the core architectural requirement for on-demand loading.

---

### 🚨 CRITICAL #2: HDF5 File Not Kept Open for On-Demand Access

**Location:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_mode_controllers.py:392-406, 446-473`

**Issue:** The HDF5 file is opened and closed in `get_session_data()`, then `get_playback_frame()` reopens it for EVERY SINGLE FRAME.

**Why This Is Wrong:**
- Opening/closing HDF5 files has significant overhead (~5-10ms per open)
- At 30fps playback, you need a frame every 33ms
- Each frame requires file open → seek → read → close cycle
- This will cause stuttering, dropped frames, and poor performance
- File locking issues may occur on some systems

**Consequence:** Playback will be jerky and unreliable. Performance will be unacceptable.

**Architectural Flaw:** The `PlaybackModeController` needs to maintain an open HDF5 file handle between `load_session()` and `deactivate()`.

**Fix Required:**
```python
class PlaybackModeController(AcquisitionModeController):
    def __init__(self, state_coordinator=None):
        super().__init__(state_coordinator)
        self.current_session_path = None
        self.session_metadata = None
        self._hdf5_file = None  # ← Keep file open during playback
        self._current_direction = None

    def get_session_data(self, direction):
        # Close previous file if different direction
        if self._hdf5_file and self._current_direction != direction:
            self._hdf5_file.close()
            self._hdf5_file = None

        # Open file for this direction and keep it open
        camera_path = os.path.join(self.current_session_path, f"{direction}_camera.h5")
        if os.path.exists(camera_path):
            self._hdf5_file = h5py.File(camera_path, 'r')
            self._current_direction = direction
            # ... return metadata

    def get_playback_frame(self, direction, frame_index):
        # Use already-open file
        if not self._hdf5_file:
            return {"success": False, "error": "No session loaded"}

        frame_data = self._hdf5_file['frames'][frame_index]
        timestamp = self._hdf5_file['timestamps'][frame_index]
        # ... convert and return

    def deactivate(self):
        # Close file on deactivation
        if self._hdf5_file:
            self._hdf5_file.close()
            self._hdf5_file = None
        # ... rest of cleanup
```

**Severity:** CRITICAL - Performance will be unacceptable without this fix.

---

### 🚨 CRITICAL #3: Frontend References Non-Existent Data Structure

**Location:** `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx:342-343`

**Issue:** Frontend code expects `camera_data.frames` array which DOES NOT EXIST in the new architecture.

```typescript
// Lines 342-343 - INCORRECT
console.log('🎬 Has camera frames:', !!directionData?.camera_data?.frames)
console.log('🎬 Frame count:', directionData?.camera_data?.frames?.length)
```

**Why This Is Wrong:**
- The backend returns `camera_data.has_frames` and `camera_data.frame_count`
- The backend does NOT return `camera_data.frames` array (on-demand loading)
- This console.log will always show `false` and `undefined`
- Developer will think loading failed when it actually succeeded

**Consequence:** Misleading debug output, potential for developer confusion.

**Fix Required:**
```typescript
// CORRECT
console.log('🎬 Has camera frames:', !!directionData?.camera_data?.has_frames)
console.log('🎬 Frame count:', directionData?.camera_data?.frame_count)
```

**Severity:** HIGH - Incorrect but doesn't break functionality, just misleading.

---

### 🚨 CRITICAL #4: Duplicate PlaybackModeController Instances

**Location:**
- `/Users/Adam/KimLabISI/apps/backend/src/isi_control/main.py:629-633`
- `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_manager.py:87`

**Issue:** TWO separate `PlaybackModeController` instances are created, violating Single Source of Truth.

**In main.py:**
```python
# Line 629
playback_mode_controller = PlaybackModeController(state_coordinator=acquisition_state)

# Line 633
playback_ipc.playback_controller = playback_mode_controller
```

**In acquisition_manager.py:**
```python
# Line 87
self.playback_controller = PlaybackModeController(state_coordinator)
```

**Why This Is Wrong:**
- The `AcquisitionOrchestrator` creates its own instance
- `main.py` creates a different instance and registers it in IPC handlers
- These instances have separate state (different loaded sessions, different file handles)
- IPC handlers use one instance, orchestrator uses another
- This violates the service registry pattern you're trying to implement

**Consequence:** State divergence, undefined behavior, potential crashes.

**Fix Required:**
```python
# In main.py - USE THE REGISTERED INSTANCE
playback_mode_controller = PlaybackModeController(state_coordinator=acquisition_state)

# Set globally for IPC handlers
playback_ipc.playback_controller = playback_mode_controller

# In acquisition_manager.py - REMOVE local creation
# Line 87 - DELETE THIS
# self.playback_controller = PlaybackModeController(state_coordinator)

# acquisition_manager should get it from service registry or injection
acquisition_manager.playback_controller = playback_mode_controller  # Inject from main.py
```

**Severity:** CRITICAL - Violates SSoT principle and service registry architecture.

---

## Architecture Violations

### ⚠️ ARCH #1: Inconsistent Service Registry Usage

**Location:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/playback_ipc_handlers.py:9-10`

**Issue:** Module-level global variable instead of service registry.

```python
# Line 10
playback_controller = None  # ❌ Global mutable state
```

**Why This Violates Principles:**
- Service registry exists specifically to avoid global variables
- This bypasses the dependency injection pattern
- Testing becomes harder (can't mock the controller)
- Multiple code paths to access the same service

**Fix Required:**
```python
# Remove module-level global
# Get from service registry in each handler:

@ipc_handler("list_sessions")
def handle_list_sessions(command: Dict[str, Any]) -> Dict[str, Any]:
    from .service_locator import get_services
    playback_controller = get_services().playback_controller

    if playback_controller is None:
        return {"success": False, "error": "Playback controller not initialized"}

    return playback_controller.activate(session_path=None)
```

**Severity:** HIGH - Architectural inconsistency, harder to maintain.

---

### ⚠️ ARCH #2: Missing State Coordination Integration

**Location:** `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx:843-849`

**Issue:** Frontend manually stops camera when entering playback mode, but this isn't coordinated with backend state.

```typescript
// Lines 843-849
useEffect(() => {
  if (acquisitionMode === 'playback' && (isPreviewing || isAcquiring)) {
    console.log('🎬 Entering playback mode - stopping live camera')
    stopPreview()  // ❌ Frontend initiates state change
  }
}, [acquisitionMode, isPreviewing, isAcquiring])
```

**Why This Violates Principles:**
- Business logic (mode transitions) in frontend component
- Backend should handle state transitions via `AcquisitionStateCoordinator`
- Frontend should only send `set_acquisition_mode` command
- Backend should stop camera and update state

**Fix Required:**

**Backend - in PlaybackModeController.activate():**
```python
def activate(self, session_path=None, **kwargs):
    # Stop any active camera/acquisition
    from .service_locator import get_services
    services = get_services()

    # Use state coordinator to transition
    if self.state_coordinator:
        if self.state_coordinator.camera_active:
            # Stop camera via camera manager
            from .camera_manager import camera_manager
            camera_manager.stop_acquisition()

        self.state_coordinator.transition_to_playback()

    # ... rest of activation logic
```

**Frontend - simplified:**
```typescript
// Just switch mode - backend handles everything
const handleModeChange = async (newMode: AcquisitionMode) => {
  await sendCommand?.({ type: 'set_acquisition_mode', mode: newMode })
  setAcquisitionMode(newMode)
}
```

**Severity:** HIGH - Business logic in wrong layer violates separation of concerns.

---

### ⚠️ ARCH #3: No Error Handling for Missing Session Directory

**Location:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_mode_controllers.py:296-313`

**Issue:** When session directory doesn't exist, returns success with empty list.

```python
# Lines 306-313
if not os.path.exists(base_path):
    logger.warning(f"⚠️  Sessions directory not found: {base_path}")
    return {
        "success": True,  # ❌ Should this be success?
        "mode": "playback",
        "sessions": [],
        "message": f"No recorded sessions directory found at {base_path}"
    }
```

**Why This Is Questionable:**
- Is "no session directory" a success or failure case?
- Frontend might not check the `message` field
- Should probably create the directory on first use
- Or return `success: False` if directory is required

**Recommendation:**
```python
if not os.path.exists(base_path):
    # Create directory if it doesn't exist
    try:
        os.makedirs(base_path, exist_ok=True)
        logger.info(f"Created sessions directory: {base_path}")
    except Exception as e:
        return {
            "success": False,
            "error": f"Cannot access sessions directory: {str(e)}"
        }

    return {
        "success": True,
        "mode": "playback",
        "sessions": [],
        "message": "No recorded sessions yet"
    }
```

**Severity:** MEDIUM - Edge case handling, but could cause UX confusion.

---

## Data Flow & Integration Issues

### ⚠️ DATA #1: Race Condition in Playback Frame Loading

**Location:** `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx:762-785`

**Issue:** Frame loading is async but playback timer doesn't wait for completion.

```typescript
// Lines 762-785
useEffect(() => {
  if (!loadedSessionData?.camera_data?.has_frames || acquisitionMode !== 'playback') return

  const loadFrame = async () => {
    // ... async frame loading
  }

  loadFrame()  // ❌ Fire and forget - no await
}, [playbackFrameIndex, loadedSessionData, acquisitionMode, sendCommand])

// Lines 788-803 - Playback timer
useEffect(() => {
  if (!isPlayingBack || !loadedSessionData?.camera_data?.has_frames) return

  const interval = setInterval(() => {
    setPlaybackFrameIndex(prev => {
      const next = prev + 1
      if (next >= loadedSessionData.camera_data.frame_count) {
        setIsPlayingBack(false)
        return prev
      }
      return next  // ❌ Advances even if previous frame not loaded
    })
  }, 1000 / 30)  // 30fps

  return () => clearInterval(interval)
}, [isPlayingBack, loadedSessionData])
```

**Why This Is Wrong:**
- Timer advances frame index every 33ms regardless of whether frame loaded
- If network/IPC is slow, frames will be skipped
- No backpressure mechanism
- `currentPlaybackFrame` state may lag behind `playbackFrameIndex`

**Consequence:** Dropped frames during playback, desynchronization.

**Fix Required:**
```typescript
// Track loading state
const [isLoadingFrame, setIsLoadingFrame] = useState(false)

// Frame loading effect
useEffect(() => {
  if (!loadedSessionData?.camera_data?.has_frames || acquisitionMode !== 'playback') return

  const loadFrame = async () => {
    setIsLoadingFrame(true)
    try {
      const result = await sendCommand?.({ /* ... */ })
      if (result?.success && result?.frame_data) {
        setCurrentPlaybackFrame(result)
      }
    } finally {
      setIsLoadingFrame(false)
    }
  }

  loadFrame()
}, [playbackFrameIndex, loadedSessionData, acquisitionMode, sendCommand])

// Playback timer - only advance when not loading
useEffect(() => {
  if (!isPlayingBack || !loadedSessionData?.camera_data?.has_frames || isLoadingFrame) return

  const interval = setInterval(() => {
    if (!isLoadingFrame) {  // Only advance if current frame loaded
      setPlaybackFrameIndex(prev => /* ... */)
    }
  }, 1000 / 30)

  return () => clearInterval(interval)
}, [isPlayingBack, loadedSessionData, isLoadingFrame])
```

**Severity:** HIGH - Will cause dropped frames and poor playback quality.

---

### ⚠️ DATA #2: Missing Session Metadata Structure Validation

**Location:** `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx:1008`

**Issue:** Accesses deeply nested metadata without validation.

```typescript
// Line 1008
{loadedSessionData?.metadata?.session?.session_name || 'None'}
```

**Why This Is Fragile:**
- Assumes `metadata.session.session_name` structure
- Backend returns `metadata` at root level in data_recorder.py
- The `session` nested object may not exist
- Should check backend response structure

**Verification Needed:** Check what `create_session_recorder()` actually returns in metadata structure.

From `/Users/Adam/KimLabISI/apps/backend/src/isi_control/data_recorder.py:253-260`:
```python
session_metadata = {
    "session_name": session_name,  # ← At root level
    "timestamp": time.time(),
}
```

**Correct Access:**
```typescript
{loadedSessionData?.metadata?.session_name || 'None'}
```

**Severity:** MEDIUM - Will show wrong data but won't crash.

---

## Edge Cases & Error Handling

### ⚠️ EDGE #1: No Handling for Empty Session (No Frames)

**Location:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_mode_controllers.py:388-421`

**Issue:** What if a session has stimulus data but no camera frames?

```python
# Lines 388-408
camera_path = os.path.join(session_path, f"{direction}_camera.h5")
camera_data = None
if os.path.exists(camera_path):
    # ... load camera data
```

**If camera_path doesn't exist:**
- `camera_data` stays `None`
- Returns `"camera_data": None` to frontend
- Frontend checks `camera_data?.has_frames` → `undefined`
- Controls get disabled ✓ (correct behavior)

**But:** No user feedback about why playback is unavailable.

**Recommendation:**
```python
if os.path.exists(camera_path):
    # ... load camera data
else:
    camera_data = {
        "has_frames": False,
        "frame_count": 0,
        "message": "No camera data recorded for this direction"
    }
```

**Severity:** LOW - Already handles the case, but UX could be better.

---

### ⚠️ EDGE #2: Corrupted HDF5 File Handling

**Location:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_mode_controllers.py:392-421, 446-473`

**Issue:** No try-except around HDF5 file operations in `get_session_data()`.

```python
# Line 392 - NO ERROR HANDLING
with h5py.File(camera_path, 'r') as f:
    frames_data = f['frames'][:]  # ❌ Could raise exception
```

**Potential Failures:**
- File corrupted → `OSError` or `HDF5Error`
- Missing 'frames' dataset → `KeyError`
- Wrong dataset shape → `ValueError`

**Fix Required:**
```python
try:
    with h5py.File(camera_path, 'r') as f:
        if 'frames' not in f or 'timestamps' not in f:
            logger.error(f"Invalid camera file: missing datasets in {camera_path}")
            camera_data = {
                "has_frames": False,
                "error": "Invalid camera data file (missing datasets)"
            }
        else:
            frame_count = len(f['frames'])
            # ... rest of logic
except Exception as e:
    logger.error(f"Failed to read camera file {camera_path}: {e}", exc_info=True)
    camera_data = {
        "has_frames": False,
        "error": f"Cannot read camera data: {str(e)}"
    }
```

**Severity:** HIGH - Will crash on corrupted files instead of graceful degradation.

---

### ⚠️ EDGE #3: Playback at End of Session

**Location:** `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx:788-803`

**Issue:** Timer stops playback at end, but what about edge cases?

```typescript
// Lines 792-799
setPlaybackFrameIndex(prev => {
  const next = prev + 1
  if (next >= loadedSessionData.camera_data.frame_count) {
    setIsPlayingBack(false)  // ✓ Stops playback
    return prev  // ✓ Doesn't advance past end
  }
  return next
})
```

**This is actually CORRECT!** ✅

Edge cases handled:
- ✓ Stops at last frame
- ✓ Doesn't advance past end
- ✓ Sets playback state to paused

**Severity:** NONE - This is implemented correctly.

---

## Performance & Memory Issues

### ⚠️ PERF #1: Reopening HDF5 File Every Frame (Already Covered in CRITICAL #2)

See CRITICAL #2 above.

---

### ⚠️ PERF #2: Inefficient RGB→Grayscale Conversion

**Location:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_mode_controllers.py:453-461`

**Issue:** Conversion done in Python instead of NumPy vectorization.

```python
# Lines 453-461
if len(frame_data.shape) == 3 and frame_data.shape[2] == 3:
    frame_gray = (
        frame_data[:, :, 0] * 0.299 +
        frame_data[:, :, 1] * 0.587 +
        frame_data[:, :, 2] * 0.114
    ).astype(np.uint8)
    frame_data = frame_gray
```

**This is actually EFFICIENT!** ✅
- Uses NumPy vectorization
- Standard luminance formula (ITU-R BT.601)
- Single operation, no loops

**Potential optimization:**
```python
# Slightly faster with cv2 if available
import cv2
frame_gray = cv2.cvtColor(frame_data, cv2.COLOR_RGB2GRAY)
```

**But current implementation is fine.** No action needed.

**Severity:** NONE - Already optimized.

---

### ⚠️ PERF #3: Frame Data Serialization Overhead

**Location:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_mode_controllers.py:465`

**Issue:** Frame data converted to list for JSON serialization.

```python
# Line 465
"frame_data": frame_data.tolist(),
```

**Why This Is Suboptimal:**
- `tolist()` creates Python list from NumPy array
- JSON serialization is slow for large arrays
- For 640×480 frame: 307,200 bytes
- Could use base64 encoding or binary transfer

**But:** IPC uses JSON, so this is unavoidable without changing architecture.

**Recommendation for future:** Use shared memory for playback frames (same as live camera).

**Severity:** MEDIUM - Works but not optimal for large frames.

---

## Code Quality Issues

### ⚠️ QUALITY #1: Inconsistent Logging with Emoji

**Location:** Multiple files

**Issue:** Some logs use emoji, others don't. No consistent pattern.

```python
# acquisition_mode_controllers.py
logger.info(f"🔍 Looking for sessions in: {base_path}")  # Emoji
logger.info(f"Playback mode activated: loaded session {session_path}")  # No emoji
```

**Why This Matters:**
- Emoji in logs make grep/parsing harder
- Not all terminals render emoji correctly
- Professional logging should be machine-readable

**Recommendation:** Remove emoji from logger calls, use structured logging.

**Severity:** LOW - Style issue, doesn't affect functionality.

---

### ⚠️ QUALITY #2: Magic Numbers in Frontend

**Location:** `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx:800, 628`

**Issue:** Hardcoded frame rates.

```typescript
// Line 800
}, 1000 / 30)  // ❌ Magic number 30fps

// Line 628
const frames = currentFrameCount % 30  // ❌ Assumes 30fps
```

**Why This Is Wrong:**
- Frame rate should come from session metadata
- Different sessions might have different camera FPS
- Hardcoding violates DRY principle

**Fix Required:**
```typescript
const playbackFps = loadedSessionData?.metadata?.acquisition?.camera_fps || 30

const interval = setInterval(() => {
  // ...
}, 1000 / playbackFps)
```

**Severity:** MEDIUM - Wrong playback speed for non-30fps sessions.

---

### ⚠️ QUALITY #3: Unused State Variables

**Location:** `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx:110`

**Issue:** `currentPlaybackFrame` state might be redundant.

```typescript
const [currentPlaybackFrame, setCurrentPlaybackFrame] = useState<any>(null)
```

**Used for:**
- Storing loaded frame data
- Rendering to canvas

**Could be simplified:** Render directly in the effect without intermediate state.

**Severity:** LOW - Minor inefficiency, not a bug.

---

## Testing & Validation Gaps

### ⚠️ TEST #1: No Validation of Frame Data Shape

**Location:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_mode_controllers.py:446-473`

**Issue:** `get_playback_frame()` doesn't validate frame shape before conversion.

```python
frame_data = f['frames'][frame_index]  # ❌ What if shape is unexpected?

if len(frame_data.shape) == 3 and frame_data.shape[2] == 3:
    # RGB conversion
```

**Missing validation:**
- What if frame is already grayscale? (shape (H, W))
- What if frame has alpha channel? (shape (H, W, 4))
- What if frame dimensions are wrong?

**Fix Required:**
```python
frame_data = f['frames'][frame_index]

# Validate shape
if len(frame_data.shape) not in [2, 3]:
    return {"success": False, "error": f"Invalid frame shape: {frame_data.shape}"}

if len(frame_data.shape) == 3:
    if frame_data.shape[2] == 3:
        # Convert RGB to grayscale
        frame_gray = (
            frame_data[:, :, 0] * 0.299 +
            frame_data[:, :, 1] * 0.587 +
            frame_data[:, :, 2] * 0.114
        ).astype(np.uint8)
        frame_data = frame_gray
    elif frame_data.shape[2] == 4:
        # RGBA - drop alpha channel first
        frame_data = frame_data[:, :, :3]
        # Then convert to grayscale
        frame_gray = (
            frame_data[:, :, 0] * 0.299 +
            frame_data[:, :, 1] * 0.587 +
            frame_data[:, :, 2] * 0.114
        ).astype(np.uint8)
        frame_data = frame_gray
    else:
        return {"success": False, "error": f"Unsupported channel count: {frame_data.shape[2]}"}
# else: Already grayscale, use as-is
```

**Severity:** MEDIUM - Will fail on unexpected data formats.

---

## Path Handling

### ✅ PATH #1: Absolute Path Resolution - CORRECT

**Location:** `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_mode_controllers.py:301-302`

```python
base_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "sessions")
base_path = os.path.abspath(base_path)
```

**This is CORRECT!** ✅
- Uses `__file__` as anchor
- Converts to absolute path
- Works regardless of working directory

**Also correct in data_recorder.py:248-250:**
```python
if not os.path.isabs(base_path):
    base_path = os.path.join(os.path.dirname(__file__), "..", "..", base_path)
    base_path = os.path.abspath(base_path)
```

**Severity:** NONE - Implemented correctly.

---

## Business Logic Separation

### ⚠️ BL #1: Frontend Contains Playback Control Logic

**Location:** `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx:364-392`

**Issue:** Playback control logic (play/pause/step/skip) is implemented in frontend.

```typescript
// Lines 364-392
const togglePlayback = () => {
  setIsPlayingBack(!isPlayingBack)
}

const stepForward = () => {
  if (loadedSessionData?.camera_data?.has_frames) {
    setPlaybackFrameIndex(prev =>
      Math.min(prev + 1, loadedSessionData.camera_data.frame_count - 1)
    )
  }
}

const stepBackward = () => {
  setPlaybackFrameIndex(prev => Math.max(prev - 1, 0))
}

const skipToStart = () => {
  setPlaybackFrameIndex(0)
}

const skipToEnd = () => {
  if (loadedSessionData?.camera_data?.has_frames) {
    setPlaybackFrameIndex(loadedSessionData.camera_data.frame_count - 1)
  }
}
```

**Analysis:** Is this business logic or view logic?

**Verdict:** This is **acceptable view-layer logic** ✅

**Why it's OK:**
- Playback controls are UI concerns (state local to component)
- Backend doesn't need to track playback position
- Frame index is sent to backend only when requesting a frame
- This is stateless from backend's perspective

**However:** The 30fps timer logic could be in backend for consistency.

**Severity:** NONE - Acceptable architecture for this use case.

---

## Summary of Critical Fixes Required

### Must Fix Before System Works:

1. **CRITICAL #1:** Remove `frames_data = f['frames'][:]` from `get_session_data()` - only read metadata
2. **CRITICAL #2:** Keep HDF5 file open between frame requests - add `self._hdf5_file` to controller
3. **CRITICAL #3:** Fix frontend console.log to check `has_frames` not `frames`
4. **CRITICAL #4:** Remove duplicate PlaybackModeController instance in acquisition_manager.py

### Should Fix for Production Quality:

5. **ARCH #1:** Use service registry instead of module global in playback_ipc_handlers.py
6. **DATA #1:** Add frame loading backpressure to prevent dropped frames
7. **EDGE #2:** Add error handling for corrupted HDF5 files
8. **TEST #1:** Add frame shape validation and handle RGBA/grayscale cases
9. **QUALITY #2:** Use session metadata for FPS instead of hardcoded 30fps

### Nice to Have:

10. **QUALITY #1:** Remove emoji from logger calls
11. **PERF #3:** Consider shared memory for playback frames (future optimization)
12. **ARCH #2:** Move camera stop logic to backend (cleaner separation)

---

## Detailed Fix Priority

**Priority 1 (MUST FIX - System Broken):**
- CRITICAL #1: On-demand loading not implemented
- CRITICAL #2: HDF5 file opened/closed every frame
- CRITICAL #4: Duplicate controller instances

**Priority 2 (SHOULD FIX - Poor Quality):**
- DATA #1: Frame loading race condition
- EDGE #2: No error handling for corrupted files
- QUALITY #2: Hardcoded FPS

**Priority 3 (NICE TO HAVE):**
- ARCH #1: Service registry consistency
- TEST #1: Frame shape validation
- CRITICAL #3: Console log fix (cosmetic)

---

## Conclusion

The playback system has a solid architectural foundation but contains **critical implementation errors** that will prevent it from working correctly:

1. ❌ On-demand loading is **not actually implemented** - all frames loaded into memory
2. ❌ HDF5 files reopened for **every single frame** - performance disaster
3. ❌ **Duplicate controller instances** violate service registry pattern
4. ❌ Missing error handling for **corrupted or malformed data**

**Current State:** 🔴 **NON-FUNCTIONAL** - Will fail in testing

**After Priority 1 Fixes:** 🟡 **FUNCTIONAL** - Basic playback works

**After Priority 2 Fixes:** 🟢 **PRODUCTION READY** - Robust and performant

**Estimated Fix Time:**
- Priority 1: 2-3 hours
- Priority 2: 3-4 hours
- Priority 3: 1-2 hours
- **Total: 6-9 hours**

---

## Positive Aspects (What's Done Right)

Despite the critical issues, several aspects are well-implemented:

✅ RGB→Grayscale conversion uses efficient NumPy operations
✅ Path handling correctly uses absolute paths
✅ Frame boundary checking prevents out-of-bounds errors
✅ IPC handler registration is complete and consistent
✅ Error messages are descriptive and helpful
✅ Service registry pattern is architecturally sound (just not fully used)
✅ Playback stop at end of session works correctly

---

**End of Audit Report**

**Recommendations:** Fix Priority 1 issues immediately before any testing. The system will not work until these critical bugs are resolved.
