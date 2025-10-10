# ARCHIVED DOCUMENTATION

**Original File**: AUDIT_REPORT_CAMERA_TRIGGERED.md
**Archived**: 2025-10-09
**Reason**: Documentation restructure - content consolidated into new docs/ structure

**Status**: Historical reference only. For current documentation, see:
- [Documentation Index](../README.md)
- [Architecture Overview](../architecture/overview.md)
- [Component Documentation](../components/)
- [Technical Decisions](../technical-decisions/)

---

# Original Content

# COMPREHENSIVE ARCHITECTURAL AUDIT: Camera-Triggered Stimulus System

**Date**: 2025-10-08
**Auditor**: Senior Software Architect
**System**: KimLabISI - Camera-Triggered Stimulus Synchronization
**Scope**: Backend refactoring from async stimulus to camera-triggered synchronous architecture

---

## EXECUTIVE SUMMARY

**OVERALL ASSESSMENT**: ⚠️ **MULTIPLE CRITICAL VIOLATIONS FOUND**

The camera-triggered stimulus system has been implemented but **COEXISTS WITH LEGACY ASYNC STIMULUS CODE**, creating a dangerous dual-path architecture that violates fundamental software engineering principles. This is **unacceptable for scientific software** where data integrity is paramount.

**Critical Issues Found**: 7
**High Priority Issues**: 5
**Medium Priority Issues**: 3
**Architectural Integrity**: **COMPROMISED**

---

## CRITICAL VIOLATIONS

### 🔴 CRITICAL #1: Dual Stimulus Generation Paths (ACTIVE SIMULTANEOUSLY)
**Severity**: CRITICAL
**Category**: Legacy Code Conflict / Architecture
**Impact**: Data corruption, unpredictable behavior, timestamp conflicts

**Location**: `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_manager.py:372-396`

**Problem**:
The acquisition loop contains BOTH camera-triggered AND async stimulus paths that can **both execute** depending on conditional logic. This violates the Single Source of Truth principle.

```python
# Lines 342-370: Camera-triggered path (NEW)
if self.camera_triggered_stimulus:
    start_result = self.camera_triggered_stimulus.start_direction(...)
    # Wait for completion

# Lines 372-396: Async stimulus path (OLD) - STILL ACTIVE!
else:  # Fallback to old async stimulus (for preview mode)
    start_result = self.stimulus_controller.start_stimulus(...)
    stimulus_duration = self._get_stimulus_duration(direction)
    completed = shared_memory.wait_for_stimulus_completion(timeout=timeout)
    stop_result = self.stimulus_controller.stop_stimulus()
```

**Why This Is Unacceptable**:
1. **Two competing timestamp systems**: Camera-triggered uses capture timestamps, async uses vsync timestamps
2. **Different frame advancement logic**: Camera-triggered is synchronous, async is timer-based
3. **Data recording ambiguity**: Which timestamp source is being recorded?
4. **Race conditions**: Both systems could theoretically write to shared memory
5. **Scientific integrity compromised**: No clear provenance of which system generated data

**Evidence of Dual Path**:
- `acquisition_manager.py:372`: `else:  # Fallback to old async stimulus (for preview mode)`
- `shared_memory_stream.py:404-566`: `RealtimeFrameProducer` class still active
- `stimulus_manager.py:795-844`: `handle_start_stimulus()` starts `RealtimeFrameProducer`

**Recommendation**:
```
IMMEDIATE ACTION REQUIRED:
1. Remove ALL async stimulus code from acquisition_manager.py (lines 372-396)
2. Make camera-triggered mode MANDATORY for record mode
3. Delete RealtimeFrameProducer class entirely (shared_memory_stream.py:404-566)
4. Remove handle_start_stimulus() async path (stimulus_manager.py:825)
5. Preview mode should use STATIC frames only (generate_frame_at_index), not async streaming
```

---

### 🔴 CRITICAL #2: RealtimeFrameProducer Still Active and Used
**Severity**: CRITICAL
**Category**: Legacy Code / Duplication
**Impact**: Async stimulus can still be started, conflicting with camera-triggered mode

**Location**: `/Users/Adam/KimLabISI/apps/backend/src/isi_control/shared_memory_stream.py:404-566`

**Problem**:
The `RealtimeFrameProducer` class (async stimulus) is **still fully functional** and **actively called** by `handle_start_stimulus()`. This is the OLD architecture that was supposed to be replaced.

```python
class RealtimeFrameProducer(threading.Thread):
    """Real-time frame producer with hardware-level timing"""
    # 162 lines of code that SHOULD NOT EXIST anymore
```

**Called By**:
- `shared_memory_stream.py:587-595`: `start_realtime_streaming()` creates RealtimeFrameProducer
- `stimulus_manager.py:825`: `handle_start_stimulus()` calls `start_realtime_streaming()`
- `acquisition_manager.py:373`: Fallback to async stimulus uses `stimulus_controller.start_stimulus()`

**Why This Violates DRY**:
- Duplicate frame generation logic (RealtimeFrameProducer vs CameraTriggeredStimulusController)
- Duplicate timestamp tracking (vsync vs camera capture)
- Duplicate metadata handling
- Two different methods to determine when stimulus is complete

**Recommendation**:
```
DELETE IMMEDIATELY:
1. RealtimeFrameProducer class (shared_memory_stream.py:404-566)
2. start_realtime_streaming() method (shared_memory_stream.py:587-595)
3. stop_realtime_streaming() method (shared_memory_stream.py:597-602)
4. wait_for_stimulus_completion() method (shared_memory_stream.py:604-617)
5. Update handle_start_stimulus() to ONLY render single preview frame
```

---

### 🔴 CRITICAL #3: wait_for_stimulus_completion() Expects Async Behavior
**Severity**: CRITICAL
**Category**: Legacy Code Conflict
**Impact**: Acquisition loop hangs waiting for async completion that never occurs

**Location**: `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_manager.py:387`

**Problem**:
In the fallback async path, the code calls `wait_for_stimulus_completion()` which expects `RealtimeFrameProducer` to set a completion event. This is **incompatible with camera-triggered mode**.

```python
# Line 387 - Expects async stimulus to signal completion
completed = shared_memory.wait_for_stimulus_completion(timeout=timeout)
```

**In Camera-Triggered Mode**:
- Completion is determined by `CameraTriggeredStimulusController.is_direction_complete()`
- Uses frame count, not threading events
- Polling-based, not event-based

**This Creates Two Different Completion Semantics**:
1. **Async**: Threading event set when frame index reaches total_frames
2. **Camera-triggered**: Polling `is_direction_complete()` every 100ms

**Recommendation**:
```
REMOVE:
- All calls to wait_for_stimulus_completion() (acquisition_manager.py:387)
- wait_for_stimulus_completion() method (shared_memory_stream.py:604-617)

KEEP ONLY:
- Camera-triggered polling loop (acquisition_manager.py:354-370)
```

---

### 🔴 CRITICAL #4: Dual Timestamp Tracking Systems Active
**Severity**: CRITICAL
**Category**: Duplication / Data Integrity
**Impact**: Timestamp correlation data may be incorrect or misleading

**Location**: Multiple files

**Problem**:
Two **independent** timestamp tracking systems exist:

**System 1: SharedMemoryService Timestamp Storage** (for async stimulus)
```python
# shared_memory_stream.py:661-678
def set_stimulus_timestamp(self, timestamp_us: int, frame_id: int):
    with self._timestamp_lock:
        self._last_stimulus_timestamp = timestamp_us
        self._last_stimulus_frame_id = frame_id

def get_stimulus_timestamp(self):
    with self._timestamp_lock:
        return self._last_stimulus_timestamp, self._last_stimulus_frame_id
```

**System 2: Camera-Triggered Direct Recording** (new system)
```python
# camera_manager.py:693-710
if self.data_recorder and self.data_recorder.is_recording:
    # Record camera frame
    self.data_recorder.record_camera_frame(...)

    # Record stimulus event (if generated)
    if stimulus_metadata:
        self.data_recorder.record_stimulus_event(...)
```

**Issues**:
1. `set_stimulus_timestamp()` is called in camera loop (line 731) but also by RealtimeFrameProducer (line 526)
2. `TimestampSynchronizationTracker` receives data from BOTH systems (line 734-740)
3. No clear indication in data which timestamp source was used
4. Camera-triggered mode uses **same timestamp** for camera and stimulus (synchronous), but old system uses **different timestamps** (asynchronous matching)

**Recommendation**:
```
REMOVE:
- set_stimulus_timestamp() from shared_memory_stream.py (lines 661-665)
- get_stimulus_timestamp() from shared_memory_stream.py (lines 667-670)
- clear_stimulus_timestamp() from shared_memory_stream.py (lines 672-678)

Camera-triggered mode does NOT need separate stimulus timestamps because:
- Camera timestamp = Stimulus timestamp (they're synchronous!)
- Recording happens directly in camera loop with single timestamp
```

---

### 🔴 CRITICAL #5: Mode Separation Is Incomplete
**Severity**: CRITICAL
**Category**: Architecture / Separation of Concerns
**Impact**: Preview mode could accidentally trigger recording, record mode could use async stimulus

**Location**: `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_manager.py:89-137`

**Problem**:
Mode switching logic does NOT enforce clean separation:

```python
def set_mode(self, mode: Literal["preview", "record", "playback"], ...):
    # Lines 112-114: Stops acquisition when switching to preview/playback
    if mode in ("preview", "playback") and self.is_running:
        self.stop_acquisition()

    # Lines 116-132: Delegates to mode controllers
    if mode == "preview":
        result = self.preview_controller.activate(...)
    elif mode == "record":
        result = self.record_controller.activate(...)
```

**Issues**:
1. **Preview mode** calls `PreviewModeController.activate()` which generates **single frame** - GOOD
2. **BUT** `handle_start_stimulus()` (async mode) can STILL be called independently via IPC - BAD
3. **Record mode** uses camera-triggered IF controller exists, ELSE falls back to async - BAD
4. No enforcement that **record mode must use camera-triggered**
5. No enforcement that **preview mode must never use async streaming**

**Current Behavior Allows**:
- Frontend could call `start_stimulus` IPC command while in preview mode → starts async RealtimeFrameProducer
- If `camera_triggered_stimulus` is None, record mode falls back to async stimulus
- No validation that data_recorder exists when starting record mode

**Recommendation**:
```
ENFORCE MODE SEPARATION:

Preview Mode:
- ONLY static frame generation (generate_frame_at_index)
- NO streaming (async or camera-triggered)
- Frontend displays single frame in viewport

Record Mode:
- MANDATORY camera-triggered stimulus
- MANDATORY data_recorder initialization
- Fail fast if camera_triggered_stimulus is None

Playback Mode:
- Read-only, no stimulus generation
```

---

### 🔴 CRITICAL #6: Data Recorder Not Passed to Camera Manager Correctly
**Severity**: CRITICAL
**Category**: Architecture / Data Recording
**Impact**: Camera frames may not be recorded if data_recorder initialization fails

**Location**:
- `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_manager.py:198-200`
- `/Users/Adam/KimLabISI/apps/backend/src/isi_control/main.py:619-623`

**Problem**:
Data recorder is created in `acquisition_manager.start_acquisition()` and passed to `camera_manager`, but there's no validation or error handling.

```python
# acquisition_manager.py:198-200
self.data_recorder = create_session_recorder(...)
# Pass data recorder to camera manager for recording
from .camera_manager import camera_manager
camera_manager.data_recorder = self.data_recorder
```

**Issues**:
1. **Global state mutation**: Directly modifying `camera_manager.data_recorder` is error-prone
2. **No validation**: If `create_session_recorder()` fails, `camera_manager.data_recorder` could be None
3. **Race condition**: Camera acquisition loop could start before `data_recorder` is assigned
4. **Cleanup issue**: When acquisition stops, `camera_manager.data_recorder` is NOT cleared

**In main.py (initialization)**:
```python
# Line 622-623: Camera manager initialized with None for data_recorder
camera_manager.synchronization_tracker = synchronization_tracker
camera_manager.camera_triggered_stimulus = camera_triggered_stimulus
# data_recorder will be passed from acquisition_manager
```

**Recommendation**:
```
ARCHITECTURAL FIX:
1. Inject data_recorder via constructor or method, not global state
2. Use ServiceRegistry to manage data_recorder lifecycle
3. Add validation in camera_manager._acquisition_loop():
   if self.data_recorder is None and self.is_recording:
       raise RuntimeError("Data recorder not initialized")
4. Clear data_recorder when acquisition stops
```

---

### 🔴 CRITICAL #7: Thread Safety Issues in Camera Loop
**Severity**: CRITICAL
**Category**: Thread Safety
**Impact**: Race conditions, data corruption

**Location**: `/Users/Adam/KimLabISI/apps/backend/src/isi_control/camera_manager.py:645-750`

**Problem**:
The camera acquisition loop accesses `self.data_recorder` and `self.camera_triggered_stimulus` without locks.

```python
# Line 670-676: No lock when accessing camera_triggered_stimulus
if self.camera_triggered_stimulus:
    stimulus_frame, stimulus_metadata = (
        self.camera_triggered_stimulus.generate_next_frame()
    )

# Line 694-710: No lock when accessing data_recorder
if self.data_recorder and self.data_recorder.is_recording:
    self.data_recorder.record_camera_frame(...)
    if stimulus_metadata:
        self.data_recorder.record_stimulus_event(...)
```

**Race Conditions**:
1. `camera_manager.data_recorder` is assigned from acquisition thread (line 200)
2. Camera loop reads `self.data_recorder` in separate thread
3. **No synchronization** between writer (acquisition thread) and reader (camera thread)
4. Same issue with `camera_triggered_stimulus` (though less likely since it's set during initialization)

**Proof**:
- Camera thread: `_acquisition_loop()` runs in separate thread (line 772-776)
- Acquisition thread: Calls `camera_manager.data_recorder = ...` (acquisition_manager.py:200)
- No shared lock between these threads

**Recommendation**:
```
ADD THREAD SAFETY:

In camera_manager.py:
1. Add lock for data_recorder access:
   with self.acquisition_lock:
       data_recorder = self.data_recorder

2. Make data_recorder assignment thread-safe:
   def set_data_recorder(self, recorder):
       with self.acquisition_lock:
           self.data_recorder = recorder

3. Use ServiceRegistry to manage data_recorder lifecycle instead of direct assignment
```

---

## HIGH PRIORITY ISSUES

### 🟠 HIGH #1: Incomplete Data Recording (Stimulus Angle May Be Missing)
**Severity**: HIGH
**Category**: Data Completeness
**Impact**: Analysis may fail if angle data is None

**Location**: `/Users/Adam/KimLabISI/apps/backend/src/isi_control/camera_manager.py:702-710`

```python
# Lines 702-710: Stimulus event recording
if stimulus_metadata:
    self.data_recorder.record_stimulus_event(
        timestamp_us=capture_timestamp,
        frame_id=stimulus_metadata.get("frame_index", camera_frame_index),
        frame_index=stimulus_metadata.get("camera_frame_index", camera_frame_index),
        direction=stimulus_metadata.get("direction", "unknown"),
        angle_degrees=stimulus_angle or 0.0,  # ← FALLBACK TO 0.0 IS DANGEROUS
    )
```

**Problem**:
If `stimulus_metadata.get("angle_degrees")` returns `None`, it falls back to `0.0`, which is a **valid angle value**. Analysis code cannot distinguish between "angle is 0 degrees" and "angle is missing".

**Recommendation**:
```python
# FAIL FAST if angle is missing:
if stimulus_metadata:
    angle_degrees = stimulus_metadata.get("angle_degrees")
    if angle_degrees is None:
        logger.error(f"Stimulus metadata missing angle_degrees: {stimulus_metadata}")
        # Don't record incomplete data
        continue

    self.data_recorder.record_stimulus_event(
        timestamp_us=capture_timestamp,
        frame_id=...,
        frame_index=...,
        direction=stimulus_metadata.get("direction", "unknown"),
        angle_degrees=angle_degrees,  # No fallback
    )
```

---

### 🟠 HIGH #2: Data Recorder save_session() Not Called on Errors
**Severity**: HIGH
**Category**: Data Recording
**Impact**: Data loss if acquisition crashes

**Location**: `/Users/Adam/KimLabISI/apps/backend/src/isi_control/acquisition_manager.py:452-458`

```python
# Lines 452-458: Save only in finally block
finally:
    # ...other cleanup...

    # Save all recorded data to disk
    if self.data_recorder:
        try:
            logger.info("Saving acquisition data...")
            self.data_recorder.save_session()
```

**Problem**:
If the acquisition loop crashes (lines 288-440), the `finally` block will execute, which is **GOOD**. However:

1. If `save_session()` itself raises an exception (line 455), the exception is logged but **not re-raised**
2. No validation that all expected data was recorded
3. No file integrity checks (did HDF5 files write correctly?)

**Additional Issue**:
In `data_recorder.py:141-160`, `save_session()` can fail silently:

```python
def save_session(self) -> None:
    try:
        # Save metadata
        # Save data for each direction
        logger.info("Session data saved successfully!")
    except Exception as e:
        logger.error(f"Failed to save session data: {e}", exc_info=True)
        raise  # ← Good, re-raises
```

But in acquisition_manager:
```python
except Exception as e:
    logger.error(f"Failed to save acquisition data: {e}", exc_info=True)
    # ← NO RE-RAISE! Error is swallowed
```

**Recommendation**:
```python
# acquisition_manager.py:452-458
finally:
    if self.data_recorder:
        try:
            logger.info("Saving acquisition data...")
            save_path = self.data_recorder.save_session()

            # VALIDATE save succeeded
            if not os.path.exists(save_path / "metadata.json"):
                raise RuntimeError(f"Save failed: metadata.json not found at {save_path}")

            logger.info(f"Acquisition data saved to: {save_path}")
        except Exception as e:
            logger.error(f"CRITICAL: Failed to save acquisition data: {e}", exc_info=True)
            # Send alert to frontend
            services.ipc.send_sync_message({
                "type": "acquisition_save_failed",
                "error": str(e),
                "session_path": str(self.data_recorder.session_path)
            })
            raise  # ← RE-RAISE to ensure error is not hidden
```

---

### 🟠 HIGH #3: Stimulus Controller Is Thin Wrapper (Violates YAGNI)
**Severity**: HIGH
**Category**: YAGNI / Architecture
**Impact**: Unnecessary abstraction layer, maintenance burden

**Location**: `/Users/Adam/KimLabISI/apps/backend/src/isi_control/stimulus_controller.py:10-100`

**Problem**:
`StimulusController` class is a **thin wrapper** around `handle_start_stimulus()` and `handle_stop_stimulus()` IPC handlers. It provides no actual business logic, just pass-through calls.

```python
class StimulusController:
    def start_stimulus(self, direction: str, show_bar_mask: bool = True, fps: float = 60.0):
        from .stimulus_manager import handle_start_stimulus
        result = handle_start_stimulus({...})
        return result

    def stop_stimulus(self):
        from .stimulus_manager import handle_stop_stimulus
        result = handle_stop_stimulus({})
        return result
```

**Why This Violates YAGNI**:
- No state management (stateless wrapper)
- No validation or business logic
- Just imports and calls IPC handlers
- Creates an extra layer of indirection for no benefit

**Current Usage**:
```python
# acquisition_manager.py:76
self.stimulus_controller = stimulus_controller or StimulusController()

# acquisition_manager.py:373
start_result = self.stimulus_controller.start_stimulus(...)
```

**Recommendation**:
```
REMOVE StimulusController ENTIRELY:

Option 1: Call IPC handlers directly
- acquisition_manager.py imports handle_start_stimulus directly
- Eliminates unnecessary abstraction

Option 2: Merge into AcquisitionOrchestrator
- If stimulus control is only needed for acquisition, put methods in AcquisitionOrchestrator
- Keeps related logic together

DO NOT create wrapper classes "just in case" - YAGNI principle
```

---

### 🟠 HIGH #4: TimestampSynchronizationTracker Still Receives Async Data
**Severity**: HIGH
**Category**: Legacy Code / Data Quality
**Impact**: Timestamp correlation data may be meaningless in camera-triggered mode

**Location**: `/Users/Adam/KimLabISI/apps/backend/src/isi_control/camera_manager.py:734-740`

```python
# Lines 734-740: Still recording synchronization for "timing QA"
if self.synchronization_tracker and stimulus_metadata:
    # Track frame timing for QA (not synchronization anymore)
    self.record_synchronization(
        camera_timestamp=capture_timestamp,
        stimulus_timestamp=capture_timestamp,  # Same in camera-triggered mode
        frame_id=camera_frame_index,
    )
```

**Problem**:
In camera-triggered mode:
- `camera_timestamp` = `stimulus_timestamp` (they're synchronous)
- Timestamp difference will **always be zero**
- `TimestampSynchronizationTracker` was designed for **asynchronous matching**, not synchronous mode

**This Creates Misleading Data**:
- Frontend displays "timestamp synchronization" plot showing perfect 0ms difference
- This is **not** synchronization validation, it's just recording the same timestamp twice
- Original purpose (detect drift between async camera and stimulus) no longer applies

**Recommendation**:
```
REMOVE synchronization tracking in camera-triggered mode:

Option 1: Remove entirely
- Camera-triggered mode doesn't need timestamp correlation
- Frame index IS the ground truth

Option 2: Repurpose for frame interval QA
- Track time between camera frames (frame rate stability)
- Rename to "FrameTimingMonitor"
- Record inter-frame intervals, not timestamp diffs
```

---

### 🟠 HIGH #5: Parameter Manager Not Used for Camera FPS in Camera Loop
**Severity**: HIGH
**Category**: Configuration / SSoT
**Impact**: Camera FPS may be inconsistent between acquisition setup and execution

**Location**:
- `/Users/Adam/KimLabISI/apps/backend/src/isi_control/camera_manager.py:744-745`
- `/Users/Adam/KimLabISI/apps/backend/src/isi_control/camera_triggered_stimulus.py:86`

**Problem**:
Camera FPS is passed to `CameraTriggeredStimulusController.start_direction()` but hardcoded as 30 FPS in the camera loop.

```python
# camera_manager.py:744-745
# Small sleep to control frame rate (30 FPS)
time.sleep(1.0 / 30.0)
```

But camera FPS **should come from parameters**:
```python
# acquisition_manager.py:150
self.camera_fps = params.get("camera_fps", 30.0)  # From parameter manager

# camera_triggered_stimulus.py:86 - Uses camera_fps passed from acquisition
total_frames = int(sweep_duration * camera_fps)
```

**This Violates SSoT**:
- Parameter manager stores `camera_fps`
- Acquisition manager reads it from parameters
- Camera manager hardcodes 30 FPS in loop
- If user changes `camera_fps` to 60, stimulus calculates frames for 60 FPS but camera captures at 30 FPS

**Recommendation**:
```python
# camera_manager.py: Read from parameter manager or service locator
def _acquisition_loop(self):
    from .service_locator import get_services
    services = get_services()
    param_manager = services.parameter_manager

    # Get camera FPS from parameters (SSoT)
    camera_fps = param_manager.get_parameter("camera", "camera_fps", 30.0)
    frame_interval = 1.0 / camera_fps

    while not self.stop_acquisition_event.is_set():
        # ... capture frame ...
        time.sleep(frame_interval)  # Use parameter value
```

---

## MEDIUM PRIORITY ISSUES

### 🟡 MEDIUM #1: Orphaned Code in shared_memory_stream.py
**Severity**: MEDIUM
**Category**: Orphaned Code
**Impact**: Code bloat, maintenance burden

**Location**: `/Users/Adam/KimLabISI/apps/backend/src/isi_control/shared_memory_stream.py`

**Orphaned Methods** (used only by RealtimeFrameProducer, which should be deleted):
- `start_realtime_streaming()` (line 587-595)
- `stop_realtime_streaming()` (line 597-602)
- `wait_for_stimulus_completion()` (line 604-617)
- `set_stimulus_timestamp()` (line 661-665)
- `get_stimulus_timestamp()` (line 667-670)
- `clear_stimulus_timestamp()` (line 672-678)

**Orphaned Variables**:
- `_last_stimulus_timestamp` (line 575)
- `_last_stimulus_frame_id` (line 576)
- `_timestamp_lock` (line 577)
- `_producer_lock` (line 578)

**Recommendation**:
```
DELETE after removing RealtimeFrameProducer:
- Lines 587-617 (streaming control methods)
- Lines 661-678 (timestamp tracking methods)
- Lines 575-578 (timestamp state variables)
```

---

### 🟡 MEDIUM #2: Unclear Error Handling in generate_next_frame()
**Severity**: MEDIUM
**Category**: Error Handling
**Impact**: Silent failures, logged but not propagated

**Location**: `/Users/Adam/KimLabISI/apps/backend/src/isi_control/camera_triggered_stimulus.py:211-213`

```python
except Exception as e:
    logger.error(f"Error generating stimulus frame {frame_index}: {e}", exc_info=True)
    return None, None
```

**Problem**:
When frame generation fails, it returns `(None, None)` and logs the error, but **does not raise an exception**. The camera loop continues without knowing why stimulus generation failed.

**In Camera Loop**:
```python
# camera_manager.py:670-676
stimulus_frame, stimulus_metadata = (
    self.camera_triggered_stimulus.generate_next_frame()
)
# ← No check if stimulus_frame is None due to error vs. completion
```

**Recommendation**:
```python
# Option 1: Fail fast (raise exception)
except Exception as e:
    logger.error(f"Error generating stimulus frame {frame_index}: {e}", exc_info=True)
    raise  # Let camera loop handle error

# Option 2: Return error indicator
except Exception as e:
    logger.error(f"Error generating stimulus frame {frame_index}: {e}", exc_info=True)
    return None, {"error": str(e)}

# Then in camera loop:
if stimulus_metadata and "error" in stimulus_metadata:
    logger.error("Stimulus generation failed, stopping acquisition")
    self.stop_acquisition_event.set()
```

---

### 🟡 MEDIUM #3: No Validation That Camera and Stimulus Frame Counts Match
**Severity**: MEDIUM
**Category**: Data Validation
**Impact**: Mismatched frame counts go undetected

**Location**: `/Users/Adam/KimLabISI/apps/backend/src/isi_control/data_recorder.py:85-94`

```python
def stop_recording(self) -> None:
    if self.current_direction:
        logger.info(
            f"Stopped recording for direction: {self.current_direction} "
            f"({len(self.stimulus_events.get(self.current_direction, []))} stimulus events, "
            f"{len(self.camera_frames.get(self.current_direction, []))} camera frames)"
        )
```

**Problem**:
Logs stimulus and camera frame counts but **does not validate they match**. In camera-triggered mode, they **should be equal** (1:1 correspondence).

**Recommendation**:
```python
def stop_recording(self) -> None:
    if self.current_direction:
        stimulus_count = len(self.stimulus_events.get(self.current_direction, []))
        camera_count = len(self.camera_frames.get(self.current_direction, []))

        logger.info(
            f"Stopped recording for direction: {self.current_direction} "
            f"({stimulus_count} stimulus events, {camera_count} camera frames)"
        )

        # VALIDATE 1:1 correspondence
        if stimulus_count != camera_count:
            logger.error(
                f"FRAME COUNT MISMATCH: {stimulus_count} stimulus events != "
                f"{camera_count} camera frames for direction {self.current_direction}"
            )
            # Optionally raise exception or set error flag
```

---

## ARCHITECTURE ASSESSMENT

### Single Responsibility Principle (SRP): ⚠️ VIOLATED
- **camera_manager.py**: Handles camera I/O, stimulus triggering, AND data recording (3 responsibilities)
- **acquisition_manager.py**: Orchestrates acquisition, manages data recorder, AND contains mode controllers

### Open/Closed Principle: ✅ ACCEPTABLE
- Mode controllers are extensible without modifying AcquisitionOrchestrator

### Liskov Substitution Principle: ✅ ACCEPTABLE
- AcquisitionModeController hierarchy is well-designed

### Interface Segregation Principle: ✅ ACCEPTABLE
- Interfaces are minimal and focused

### Dependency Inversion Principle: ⚠️ VIOLATED
- Direct `camera_manager.data_recorder = ...` assignment violates DIP
- Should use dependency injection via constructor or ServiceRegistry

### DRY (Don't Repeat Yourself): 🔴 VIOLATED
- Dual stimulus generation paths (RealtimeFrameProducer + CameraTriggeredStimulusController)
- Dual timestamp tracking systems

### SoC (Separation of Concerns): ⚠️ VIOLATED
- Camera manager mixes capture, stimulus triggering, and data recording

### SSoT (Single Source of Truth): 🔴 VIOLATED
- camera_fps hardcoded in camera loop, also in parameter manager
- Timestamp sources duplicated

### YAGNI (You Aren't Gonna Need It): ⚠️ VIOLATED
- StimulusController is unnecessary wrapper
- RealtimeFrameProducer kept "just in case"

---

## REQUIRED REFACTORING ACTIONS

### Phase 1: Remove Legacy Async Stimulus (CRITICAL - DO FIRST)

```
DELETIONS:
1. shared_memory_stream.py:
   - Delete RealtimeFrameProducer class (lines 404-566)
   - Delete start_realtime_streaming() (lines 587-595)
   - Delete stop_realtime_streaming() (lines 597-602)
   - Delete wait_for_stimulus_completion() (lines 604-617)
   - Delete set/get/clear_stimulus_timestamp() (lines 661-678)

2. acquisition_manager.py:
   - Delete async fallback path (lines 372-396)
   - Delete _get_stimulus_duration() method (lines 499-520)

3. stimulus_manager.py:
   - Refactor handle_start_stimulus() to ONLY render single preview frame
   - Remove RealtimeFrameProducer initialization (line 825)

4. stimulus_controller.py:
   - Delete entire file (unnecessary wrapper)
```

### Phase 2: Enforce Mode Separation (CRITICAL)

```
CHANGES:
1. acquisition_manager.py:
   - Add validation in start_acquisition():
     if self.camera_triggered_stimulus is None:
         raise RuntimeError("Camera-triggered stimulus required for record mode")
     if self.data_recorder is None:
         raise RuntimeError("Data recorder required for record mode")

2. Create mode enforcement decorator:
   @require_mode("record")
   def start_acquisition(self, params):
       # Only callable in record mode

3. Remove async stimulus option from acquisition loop entirely
```

### Phase 3: Fix Thread Safety (HIGH PRIORITY)

```
CHANGES:
1. camera_manager.py:
   - Add thread-safe setter for data_recorder:
     def set_data_recorder(self, recorder):
         with self.acquisition_lock:
             self.data_recorder = recorder

2. acquisition_manager.py:
   - Replace direct assignment:
     camera_manager.set_data_recorder(self.data_recorder)

3. Add validation in camera loop:
   with self.acquisition_lock:
       data_recorder = self.data_recorder

   if data_recorder and data_recorder.is_recording:
       data_recorder.record_camera_frame(...)
```

### Phase 4: Data Recording Validation (HIGH PRIORITY)

```
CHANGES:
1. data_recorder.py:
   - Add frame count validation in stop_recording()
   - Add file integrity checks in save_session()

2. acquisition_manager.py:
   - Re-raise save errors instead of swallowing
   - Add IPC notification on save failure
```

### Phase 5: Clean Up Orphaned Code (MEDIUM PRIORITY)

```
DELETIONS:
1. Remove TimestampSynchronizationTracker calls in camera-triggered mode
2. Remove orphaned methods in shared_memory_stream.py
3. Fix camera_fps hardcoding in camera loop
```

---

## TESTING RECOMMENDATIONS

After refactoring, verify:

1. **Single Path Test**: Confirm only ONE stimulus generation path exists
   - Start record mode acquisition
   - Verify RealtimeFrameProducer is NOT created
   - Verify CameraTriggeredStimulusController IS created

2. **Frame Count Validation**: Confirm 1:1 camera/stimulus correspondence
   - Record 1 direction, 1 cycle
   - Check data_recorder: camera_frames.count == stimulus_events.count

3. **Thread Safety Test**: Concurrent access to data_recorder
   - Start acquisition in one thread
   - Try to access data_recorder.get_session_info() from another thread
   - Should not crash or corrupt data

4. **Error Recovery Test**: Acquisition failure handling
   - Inject exception in camera loop
   - Verify save_session() is still called
   - Verify error is reported to frontend

5. **Mode Separation Test**: Prevent mode violations
   - Try to start async stimulus in record mode → should fail
   - Try to start recording in preview mode → should fail

---

## CONCLUSION

The camera-triggered stimulus system has been **partially implemented** but the **legacy async system has not been removed**, creating a dangerous dual-path architecture that violates fundamental software engineering principles. This is **unacceptable for scientific software** where data integrity is paramount.

### Immediate Actions Required:
1. ✅ Delete RealtimeFrameProducer and all async stimulus code (CRITICAL)
2. ✅ Remove async fallback path from acquisition_manager (CRITICAL)
3. ✅ Enforce mode separation (preview vs record vs playback) (CRITICAL)
4. ✅ Fix thread safety issues with data_recorder (CRITICAL)
5. ✅ Add data recording validation (HIGH)

### System Status After Refactoring:
- **SOLID Principles**: Will be restored
- **DRY**: No duplicate stimulus generation
- **SoC**: Clean separation between modes
- **SSoT**: Single camera_fps source, single stimulus generation path
- **Data Integrity**: Guaranteed 1:1 camera/stimulus correspondence

**Current Grade**: D (Multiple critical violations)
**Expected Grade After Refactoring**: A (Clean, maintainable, scientifically rigorous)

---

**End of Audit Report**
