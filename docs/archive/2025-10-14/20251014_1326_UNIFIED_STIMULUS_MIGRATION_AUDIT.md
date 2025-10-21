# Unified Stimulus Migration - Critical Issues Audit Report

**Date**: October 14, 2025
**Auditor**: Claude (Software Integrity Auditor)
**Migration Scope**: Unified `camera_stimulus.py` + `preview_stimulus.py` → `unified_stimulus.py`

---

## Executive Summary

The unified stimulus migration is **INCOMPLETE** and has **CRITICAL INTEGRATION FAILURES**. While the `UnifiedStimulusController` class itself is well-implemented, it has **NOT been properly wired** into the frontend-backend message flow. All reported user issues stem from missing IPC handlers, missing progress broadcasting, and incomplete integration with preview/record modes.

### Critical Finding
**NO PROGRESS BROADCASTING EXISTS** - The `pre_generate_all_directions()` method runs synchronously without sending any progress updates via IPC, causing the frontend progress bar to remain empty.

---

## Audit Scope

### Files Modified
1. `/Users/Adam/KimLabISI/apps/backend/src/main.py` - IPC handlers
2. `/Users/Adam/KimLabISI/apps/backend/src/acquisition/manager.py` - Record mode integration
3. `/Users/Adam/KimLabISI/apps/backend/src/acquisition/__init__.py` - Exports
4. `/Users/Adam/KimLabISI/apps/backend/src/camera/manager.py` - Camera-stimulus coupling

### Files Deleted (517 lines removed)
1. `/Users/Adam/KimLabISI/apps/backend/src/acquisition/camera_stimulus.py` - CameraTriggeredStimulusController
2. `/Users/Adam/KimLabISI/apps/backend/src/acquisition/preview_stimulus.py` - PreviewStimulusLoop

### Frontend Files Affected
1. `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/StimulusGenerationViewport.tsx`
2. `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/StimulusPresentationViewport.tsx`
3. `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx`

---

## Critical Issues Found (Priority 0 - Blocks ALL Functionality)

### Issue 1: Pre-generation Has NO Progress Broadcasting

**Root Cause**: `UnifiedStimulusController.pre_generate_all_directions()` runs synchronously without sending progress updates via IPC.

**Evidence** (`unified_stimulus.py` lines 144-254):
```python
def pre_generate_all_directions(self) -> Dict[str, any]:
    """Pre-generate and compress all stimulus directions."""
    try:
        logger.info("Pre-generating stimulus library for all directions...")
        start_time = time.time()

        # ... generates frames synchronously ...

        for direction in ["LR", "TB"]:
            logger.info(f"Generating {direction} direction...")
            # ... generation happens ...

            for i, frame in enumerate(frames):
                # ... compression happens ...

                if i % 100 == 0:
                    logger.debug(f"  Compressed {i}/{len(frames)} frames")
                    # ❌ NO IPC BROADCAST HERE!

        return {
            "success": True,
            "statistics": stats,
            "total_duration_sec": total_duration
        }
```

**Missing Code**: IPC progress broadcasts inside the compression loop:
```python
# Should broadcast progress at regular intervals:
if i % 100 == 0:
    if self.ipc:
        self.ipc.broadcast({
            "type": "unified_stimulus_pregeneration_progress",
            "direction": direction,
            "current_frame": i,
            "total_frames": len(frames),
            "current_direction_index": direction_index,
            "total_directions": 2,  # LR + TB
            "percent_complete": (direction_index * len(frames) + i) / (2 * len(frames)) * 100
        })
```

**Impact**:
- Frontend progress bar shows nothing
- User has no feedback during 10-30 second generation
- Appears frozen/broken

**Priority**: **CRITICAL** (P0)

---

### Issue 2: Frontend NOT Listening for Pre-generation Progress

**Root Cause**: Even if backend sends progress, frontend doesn't subscribe to the right IPC channel.

**Evidence** (`StimulusGenerationViewport.tsx` lines 183-220):
```typescript
const handlePreGenerate = async () => {
    setIsPreGenerating(true)
    setPreGenStatus(null)

    try {
        const result = await sendCommand({
            type: 'unified_stimulus_pregenerate'
        })
        // ❌ Waits for FINAL result only, no progress updates

        if (result.success) {
            setPreGenStatus({ success: true, statistics: result.statistics })
        }
    } finally {
        setIsPreGenerating(false)
    }
}
```

**Missing Code**: Frontend should listen for progress updates via sync channel:
```typescript
// In useEffect hook:
const handleSyncMessage = (message: any) => {
    if (message.type === 'unified_stimulus_pregeneration_progress') {
        setPreGenProgress({
            currentFrame: message.current_frame,
            totalFrames: message.total_frames,
            currentDirection: message.direction,
            percentComplete: message.percent_complete
        })
    }
}

window.electronAPI.onSyncMessage(handleSyncMessage)
```

**Impact**:
- Progress bar remains empty even if backend sends updates
- User experience is poor

**Priority**: **CRITICAL** (P0)

---

### Issue 3: "Direction LR not pre-generated" Error is Valid

**Root Cause**: The error message is **CORRECT** - pre-generation is not being called before playback starts.

**Evidence** (`main.py` lines 610-657 - `_set_presentation_stimulus_enabled`):
```python
def _set_presentation_stimulus_enabled(ipc, unified_stimulus, param_manager, cmd: Dict[str, Any]) -> Dict[str, Any]:
    enabled = cmd.get("enabled", False)

    _stimulus_status["presentation_display_enabled"] = enabled

    if enabled:
        monitor_params = param_manager.get_parameter_group("monitor")
        monitor_fps = monitor_params.get("monitor_fps", 60.0)

        # ❌ NO PRE-GENERATION CHECK HERE!
        result = unified_stimulus.start_playback(direction="LR", monitor_fps=monitor_fps)

        if not result.get("success"):
            return {"success": False, "error": f"Failed to start stimulus: {result.get('error')}"}
```

**Missing Code**: Pre-generation check before starting playback:
```python
if enabled:
    # Check if library is loaded
    status = unified_stimulus.get_status()
    if not status.get("library_loaded"):
        logger.info("Stimulus library not loaded, pre-generating...")
        pregen_result = unified_stimulus.pre_generate_all_directions()
        if not pregen_result.get("success"):
            return {
                "success": False,
                "error": f"Pre-generation failed: {pregen_result.get('error')}"
            }

    # Now start playback
    result = unified_stimulus.start_playback(direction="LR", monitor_fps=monitor_fps)
```

**Impact**:
- Preview mode fails with "Direction LR not pre-generated" error
- User must manually click "Pre-Generate All Directions" before using preview
- **BROKEN USER FLOW**

**Priority**: **CRITICAL** (P0)

---

### Issue 4: Status Bar Messages Lost on Viewport Switch

**Root Cause**: Frontend status messages are **NOT PERSISTED** across viewport switches. Each viewport uses local state that's destroyed when switching tabs.

**Evidence** (`StimulusGenerationViewport.tsx` lines 44-50):
```typescript
const [preGenStatus, setPreGenStatus] = useState<{
    success?: boolean
    error?: string
    statistics?: any
} | null>(null)
// ❌ Local state - lost when viewport unmounts
```

**Missing Architecture**: Status messages should be in **GLOBAL STATE** (React Context or app-level state), not local to viewport.

**Missing Code**: Should use shared context:
```typescript
// In parent component or context:
const [globalPreGenStatus, setGlobalPreGenStatus] = useState(null)

// Pass down to viewport:
<StimulusGenerationViewport
    preGenStatus={globalPreGenStatus}
    onPreGenStatusChange={setGlobalPreGenStatus}
/>
```

**Impact**:
- User switches viewports and loses all status messages
- Confusing UX - appears broken

**Priority**: **HIGH** (P1)

---

### Issue 5: Preview Mode Integration Incomplete

**Root Cause**: `AcquisitionViewport.tsx` calls `set_presentation_stimulus_enabled` but does NOT check if pre-generation completed.

**Evidence** (`AcquisitionViewport.tsx` lines 191-226):
```typescript
const startPreview = async () => {
    // ... camera setup ...

    // Auto-start stimulus animation when preview starts
    setShowOnPresentation(true)
    await sendCommand?.({
        type: 'set_presentation_stimulus_enabled',
        enabled: true
    })
    // ❌ No check for pre-generation success
}
```

**Missing Code**: Check result and handle pre-generation failure:
```typescript
const result = await sendCommand?.({
    type: 'set_presentation_stimulus_enabled',
    enabled: true
})

if (!result?.success) {
    if (result?.error?.includes('not pre-generated')) {
        // Show user-friendly message
        setCameraError('Stimulus not pre-generated. Please visit Stimulus Generation tab and click Pre-Generate.')
    } else {
        setCameraError(result?.error || 'Failed to start stimulus')
    }
    setShowOnPresentation(false)
    return
}
```

**Impact**:
- Preview mode fails silently
- User has no guidance on how to fix it

**Priority**: **HIGH** (P1)

---

### Issue 6: Recording Mode Integration Defensive but Incomplete

**Root Cause**: `AcquisitionManager.start_acquisition()` DOES pre-generate if library not loaded (lines 334-344), BUT error handling is incomplete and messaging is poor.

**Evidence** (`manager.py` lines 334-344):
```python
status = self.unified_stimulus.get_status()
if not status.get("library_loaded"):
    logger.info("Stimulus library not loaded, pre-generating all directions...")
    pregen_result = self.unified_stimulus.pre_generate_all_directions()
    if not pregen_result.get("success"):
        error_msg = f"Failed to pre-generate stimulus: {pregen_result.get('error')}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    logger.info(f"Pre-generation complete: {pregen_result.get('statistics')}")
```

**Issue**: This is BLOCKING SYNCHRONOUS CALL - frontend will freeze for 10-30 seconds waiting for response!

**Missing Architecture**: Pre-generation should be ASYNC with progress updates, not blocking:
```python
# Option 1: Require pre-generation BEFORE allowing record mode
if not status.get("library_loaded"):
    return {
        "success": False,
        "error": "Stimulus library not pre-generated. Please pre-generate before recording.",
        "requires_pregeneration": True
    }

# Option 2: Start pre-generation in background thread and send progress
def _async_pregen_then_start_acquisition():
    # Pre-generate with progress broadcasts
    # Then call actual start_acquisition()
    pass

threading.Thread(target=_async_pregen_then_start_acquisition).start()
return {
    "success": True,
    "message": "Pre-generating stimulus, acquisition will start when ready...",
    "async": True
}
```

**Impact**:
- Recording mode works BUT freezes frontend for 10-30 seconds
- Poor UX
- User thinks app crashed

**Priority**: **HIGH** (P1)

---

## Important Issues (Priority 1 - Degrades UX)

### Issue 7: No Status Persistence Across Sessions

**Root Cause**: Pre-generation status is not saved to disk. User must re-generate every time backend restarts.

**Missing Feature**: Cache status should be persisted:
```python
# In UnifiedStimulusController:
def _save_cache_manifest(self):
    """Save cache metadata to disk for fast startup."""
    manifest_path = Path(__file__).parent.parent.parent / "cache" / "stimulus_manifest.json"
    manifest = {
        "timestamp": time.time(),
        "parameter_hash": self._compute_parameter_hash(),
        "directions": list(self._frame_library.keys()),
        "frame_counts": {d: len(self._frame_library[d]["frames"]) for d in self._frame_library}
    }
    manifest_path.parent.mkdir(exist_ok=True)
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f)
```

**Impact**:
- User must click "Pre-Generate" every time backend restarts
- Annoying but not critical

**Priority**: **IMPORTANT** (P1)

---

### Issue 8: Error Messages Not User-Friendly

**Root Cause**: Backend error messages are developer-focused, not user-focused.

**Examples**:
- ❌ "Direction LR not pre-generated. Call pre_generate_all_directions() first."
- ✅ "Stimulus patterns not ready. Please visit the Stimulus Generation tab and click 'Pre-Generate All Directions'."

**Fix**: Update error messages in `unified_stimulus.py` line 297:
```python
return {
    "success": False,
    "error": (
        "Stimulus patterns not ready for this direction. "
        "Please visit the Stimulus Generation tab and click 'Pre-Generate All Directions' button. "
        "This is a one-time step that takes about 10-30 seconds."
    ),
    "error_code": "STIMULUS_NOT_PREGENERATED",
    "required_action": "pregenerate"
}
```

**Priority**: **IMPORTANT** (P1)

---

## Completeness Assessment

### ✅ Complete (Backend Implementation)

1. **UnifiedStimulusController Core Logic** - Well-implemented
   - Pre-generation with compression ✓
   - Playback with VSync timing ✓
   - Frame correspondence calculations ✓
   - Display log tracking ✓
   - Parameter invalidation ✓
   - Cleanup and resource management ✓

2. **Record Mode Integration** - Mostly complete
   - AcquisitionManager uses unified_stimulus ✓
   - Pre-generation check before acquisition ✓
   - Baseline display ✓
   - Start/stop playback ✓

### ⚠️ Incomplete (Missing Integration)

1. **IPC Handler Integration** - PARTIALLY COMPLETE
   - ✓ Handler exists: `unified_stimulus_pregenerate` (line 339)
   - ✓ Handler exists: `unified_stimulus_start_playback` (line 340-343)
   - ✓ Handler exists: `unified_stimulus_stop_playback` (line 344)
   - ✓ Handler exists: `unified_stimulus_get_status` (line 345-348)
   - ❌ NO PROGRESS BROADCASTING during pre-generation
   - ❌ NO AUTO PRE-GENERATION in `set_presentation_stimulus_enabled`

2. **Frontend Integration** - INCOMPLETE
   - ✓ StimulusGenerationViewport sends `unified_stimulus_pregenerate` command
   - ❌ Does NOT listen for progress updates
   - ❌ Does NOT handle pre-generation requirement in preview mode
   - ❌ Status messages not persisted across viewport switches

3. **Preview Mode Integration** - INCOMPLETE
   - ❌ `set_presentation_stimulus_enabled` does NOT check if pre-generated
   - ❌ No auto-pregeneration before starting preview
   - ❌ No user guidance when pre-generation required

4. **Error Handling** - INCOMPLETE
   - ✓ Backend validates and returns error codes
   - ❌ Frontend does NOT display backend errors clearly
   - ❌ Error messages not user-friendly
   - ❌ No recovery suggestions

---

## Competing Systems Analysis

### REMOVED (Correctly Deleted)
- `camera_stimulus.py` - CameraTriggeredStimulusController ✓
- `preview_stimulus.py` - PreviewStimulusLoop ✓

### NO COMPETING SYSTEMS DETECTED
All references to old stimulus systems have been removed. ✓

---

## Dead Code Analysis

### NO DEAD CODE DETECTED

All functions in `unified_stimulus.py` are referenced:
- `pre_generate_all_directions()` - Called by main.py handler ✓
- `start_playback()` - Called by main.py handler and manager.py ✓
- `stop_playback()` - Called by main.py handler and manager.py ✓
- `get_status()` - Called by main.py handler ✓
- `display_baseline()` - Called by manager.py ✓
- `get_frame_for_viewport()` - NOT USED YET (for future viewport scrubbing)

---

## Architectural Debt

### Issue 9: Synchronous Pre-Generation Blocks Event Loop

**Problem**: `pre_generate_all_directions()` runs in main thread, blocking IPC for 10-30 seconds.

**Recommendation**: Refactor to async with progress callbacks:
```python
def pre_generate_all_directions(self, progress_callback=None) -> Dict[str, any]:
    """Pre-generate with optional progress callback.

    Args:
        progress_callback: Optional function(direction, frame, total_frames)
    """
    for direction in ["LR", "TB"]:
        for i, frame in enumerate(frames):
            # ... compression ...

            if progress_callback and i % 100 == 0:
                progress_callback(direction, i, len(frames))
```

**Priority**: **IMPORTANT** (P1)

---

### Issue 10: No Frame Library Disk Cache

**Problem**: Pre-generated frames stored only in RAM. Lost on restart.

**Recommendation**: Implement disk cache:
```python
cache_dir = Path(__file__).parent.parent.parent / "cache" / "stimulus_frames"
cache_dir.mkdir(parents=True, exist_ok=True)

# Save compressed frames to disk
for direction, data in self._frame_library.items():
    cache_file = cache_dir / f"{direction}_frames.pkl"
    with open(cache_file, 'wb') as f:
        pickle.dump(data, f)
```

**Priority**: **MINOR** (P2)

---

## Recommended Fix Order

### Phase 1: Critical Fixes (Required for ANY functionality)

1. **Add pre-generation check to `_set_presentation_stimulus_enabled`** (30 min)
   - File: `/Users/Adam/KimLabISI/apps/backend/src/main.py`
   - Lines: 610-657
   - Fix: Add `get_status()` check + auto pre-generation before `start_playback()`

2. **Add IPC progress broadcasting to `pre_generate_all_directions`** (45 min)
   - File: `/Users/Adam/KimLabISI/apps/backend/src/acquisition/unified_stimulus.py`
   - Lines: 144-254
   - Fix: Add `self.ipc.broadcast()` calls every 100 frames

3. **Add progress listener to StimulusGenerationViewport** (30 min)
   - File: `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/StimulusGenerationViewport.tsx`
   - Lines: 183-220
   - Fix: Subscribe to sync channel for progress updates

### Phase 2: User Experience Fixes (Required for acceptable UX)

4. **Add error handling to AcquisitionViewport preview mode** (20 min)
   - File: `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx`
   - Lines: 191-226
   - Fix: Check result from `set_presentation_stimulus_enabled`, show error to user

5. **Make status messages persistent across viewports** (60 min)
   - File: `/Users/Adam/KimLabISI/apps/desktop/src/App.tsx` (or context provider)
   - Fix: Move pre-gen status to global state/context

6. **Improve error messages** (15 min)
   - File: `/Users/Adam/KimLabISI/apps/backend/src/acquisition/unified_stimulus.py`
   - Lines: 297, 303
   - Fix: Replace developer-focused errors with user-friendly guidance

### Phase 3: Performance & Polish (Nice to have)

7. **Make pre-generation async with progress** (120 min)
   - File: `/Users/Adam/KimLabISI/apps/backend/src/acquisition/unified_stimulus.py`
   - Fix: Refactor to run in background thread with progress callbacks

8. **Add disk cache for frame library** (90 min)
   - File: `/Users/Adam/KimLabISI/apps/backend/src/acquisition/unified_stimulus.py`
   - Fix: Save/load compressed frames to/from disk

---

## Code Snippets for Critical Fixes

### Fix 1: Add pre-generation check to preview mode handler

**File**: `/Users/Adam/KimLabISI/apps/backend/src/main.py`
**Location**: Lines 610-657 in `_set_presentation_stimulus_enabled()`

```python
def _set_presentation_stimulus_enabled(ipc, unified_stimulus, param_manager, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Enable or disable stimulus display on presentation monitor using UnifiedStimulusController."""
    enabled = cmd.get("enabled", False)

    _stimulus_status["presentation_display_enabled"] = enabled

    if enabled:
        # CRITICAL FIX: Check if library is loaded, pre-generate if needed
        status = unified_stimulus.get_status()
        if not status.get("library_loaded"):
            logger.info("Stimulus library not loaded, pre-generating all directions...")

            # Broadcast that pre-generation is starting
            ipc.send_sync_message({
                "type": "unified_stimulus_pregeneration_started",
                "timestamp": time.time()
            })

            pregen_result = unified_stimulus.pre_generate_all_directions()

            if not pregen_result.get("success"):
                error_msg = f"Failed to pre-generate stimulus: {pregen_result.get('error')}"
                logger.error(error_msg)

                # Broadcast failure
                ipc.send_sync_message({
                    "type": "unified_stimulus_pregeneration_failed",
                    "error": error_msg,
                    "timestamp": time.time()
                })

                return {
                    "success": False,
                    "error": (
                        "Could not prepare stimulus patterns. "
                        "Please visit Stimulus Generation tab and manually click 'Pre-Generate All Directions'. "
                        f"Technical details: {error_msg}"
                    )
                }

            # Broadcast success
            ipc.send_sync_message({
                "type": "unified_stimulus_pregeneration_complete",
                "statistics": pregen_result.get("statistics"),
                "timestamp": time.time()
            })

            logger.info("Pre-generation complete, starting playback...")

        # Get monitor FPS from parameters
        monitor_params = param_manager.get_parameter_group("monitor")
        monitor_fps = monitor_params.get("monitor_fps", 60.0)

        # Start unified stimulus playback
        result = unified_stimulus.start_playback(direction="LR", monitor_fps=monitor_fps)
        if not result.get("success"):
            logger.error(f"Failed to start unified stimulus: {result.get('error')}")
            return {"success": False, "error": f"Failed to start stimulus: {result.get('error')}"}
        logger.info(f"Started unified stimulus playback: {result.get('total_frames')} frames at {result.get('fps')} fps")
    else:
        # Stop unified stimulus playback
        result = unified_stimulus.stop_playback()
        if not result.get("success") and result.get("error") != "No playback running":
            logger.warning(f"Failed to stop unified stimulus: {result.get('error')}")
        logger.info("Unified stimulus playback stopped")

    # Broadcast state change via SYNC channel
    ipc.send_sync_message({
        "type": "presentation_stimulus_state",
        "enabled": enabled,
        "timestamp": time.time()
    })

    return {"success": True, "enabled": enabled}
```

### Fix 2: Add IPC progress broadcasting to pre-generation

**File**: `/Users/Adam/KimLabISI/apps/backend/src/acquisition/unified_stimulus.py`
**Location**: Lines 144-254 in `pre_generate_all_directions()`

```python
def pre_generate_all_directions(self) -> Dict[str, any]:
    """Pre-generate and compress all stimulus directions.

    Generates LR + TB as grayscale, derives RL and BT via reversal.
    Compresses all frames with PNG for efficient storage.

    Returns:
        Dict with success status and generation statistics
    """
    try:
        logger.info("Pre-generating stimulus library for all directions...")
        start_time = time.time()

        # Statistics tracking
        stats = {
            "total_frames": 0,
            "total_memory_bytes": 0,
            "directions": {}
        }

        with self._library_lock:
            # Generate primary directions (LR, TB) as grayscale
            for direction_index, direction in enumerate(["LR", "TB"]):
                logger.info(f"Generating {direction} direction...")
                dir_start = time.time()

                # Broadcast direction start
                if self.ipc:
                    self.ipc.send_sync_message({
                        "type": "unified_stimulus_pregeneration_progress",
                        "phase": "generating",
                        "direction": direction,
                        "direction_index": direction_index,
                        "total_directions": 2,
                        "current_frame": 0,
                        "timestamp": time.time()
                    })

                # Generate grayscale frames
                frames, angles = self.stimulus_generator.generate_sweep(
                    direction=direction,
                    output_format="grayscale"
                )

                # Compress frames with PNG
                compressed_frames = []
                total_size = 0

                for i, frame in enumerate(frames):
                    # Convert grayscale numpy array to PNG bytes
                    img = Image.fromarray(frame, mode='L')
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG', compress_level=6)
                    compressed = buffer.getvalue()
                    compressed_frames.append(compressed)
                    total_size += len(compressed)

                    # CRITICAL FIX: Broadcast progress every 100 frames
                    if i % 100 == 0:
                        logger.debug(f"  Compressed {i}/{len(frames)} frames")

                        if self.ipc:
                            progress_percent = (
                                (direction_index * len(frames) + i) / (2 * len(frames)) * 100
                            )
                            self.ipc.send_sync_message({
                                "type": "unified_stimulus_pregeneration_progress",
                                "phase": "compressing",
                                "direction": direction,
                                "direction_index": direction_index,
                                "total_directions": 2,
                                "current_frame": i,
                                "total_frames": len(frames),
                                "percent_complete": progress_percent,
                                "memory_bytes": total_size,
                                "timestamp": time.time()
                            })

                # Store in library
                self._frame_library[direction] = {
                    "frames": compressed_frames,
                    "angles": angles
                }

                dir_duration = time.time() - dir_start
                avg_size = total_size / len(compressed_frames)

                logger.info(
                    f"{direction} complete: {len(frames)} frames, "
                    f"{total_size / 1024 / 1024:.1f} MB, "
                    f"avg {avg_size / 1024:.1f} KB/frame, "
                    f"{dir_duration:.1f}s"
                )

                # Broadcast direction complete
                if self.ipc:
                    self.ipc.send_sync_message({
                        "type": "unified_stimulus_pregeneration_progress",
                        "phase": "direction_complete",
                        "direction": direction,
                        "direction_index": direction_index,
                        "total_directions": 2,
                        "frames": len(frames),
                        "size_bytes": total_size,
                        "duration_sec": dir_duration,
                        "timestamp": time.time()
                    })

                stats["total_frames"] += len(frames)
                stats["total_memory_bytes"] += total_size
                stats["directions"][direction] = {
                    "frames": len(frames),
                    "size_bytes": total_size,
                    "avg_frame_bytes": avg_size,
                    "duration_sec": dir_duration
                }

            # Derive reversed directions (RL from LR, BT from TB)
            self._frame_library["RL"] = {
                "frames": list(reversed(self._frame_library["LR"]["frames"])),
                "angles": list(reversed(self._frame_library["LR"]["angles"]))
            }
            self._frame_library["BT"] = {
                "frames": list(reversed(self._frame_library["TB"]["frames"])),
                "angles": list(reversed(self._frame_library["TB"]["angles"]))
            }

            logger.info(f"Derived RL from reversed LR ({len(self._frame_library['RL']['frames'])} frames)")
            logger.info(f"Derived BT from reversed TB ({len(self._frame_library['BT']['frames'])} frames)")

            # Copy stats for derived directions
            stats["directions"]["RL"] = stats["directions"]["LR"].copy()
            stats["directions"]["BT"] = stats["directions"]["TB"].copy()
            stats["total_frames"] *= 2  # LR+RL and TB+BT

            total_duration = time.time() - start_time
            total_mb = stats["total_memory_bytes"] / 1024 / 1024

            logger.info(
                f"Pre-generation complete: {stats['total_frames']} total frames, "
                f"{total_mb:.1f} MB, {total_duration:.1f}s"
            )

            # Broadcast final completion
            if self.ipc:
                self.ipc.send_sync_message({
                    "type": "unified_stimulus_pregeneration_complete",
                    "statistics": stats,
                    "total_duration_sec": total_duration,
                    "timestamp": time.time()
                })

            return {
                "success": True,
                "statistics": stats,
                "total_duration_sec": total_duration
            }

    except Exception as e:
        logger.error(f"Pre-generation failed: {e}", exc_info=True)

        # Broadcast failure
        if self.ipc:
            self.ipc.send_sync_message({
                "type": "unified_stimulus_pregeneration_failed",
                "error": str(e),
                "timestamp": time.time()
            })

        return {
            "success": False,
            "error": str(e)
        }
```

### Fix 3: Add progress listener to frontend

**File**: `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/StimulusGenerationViewport.tsx`
**Location**: Add new useEffect hook after line 119

```typescript
// Listen for pre-generation progress updates via sync channel
useEffect(() => {
  const handleSyncMessage = (message: any) => {
    if (message.type === 'unified_stimulus_pregeneration_progress') {
      // Update progress state
      setPreGenProgress({
        phase: message.phase,
        direction: message.direction,
        currentFrame: message.current_frame,
        totalFrames: message.total_frames,
        percentComplete: message.percent_complete,
        memoryBytes: message.memory_bytes
      })
    } else if (message.type === 'unified_stimulus_pregeneration_complete') {
      // Pre-generation finished successfully
      setIsPreGenerating(false)
      setPreGenStatus({
        success: true,
        statistics: message.statistics
      })
      componentLogger.info('Pre-generation complete via sync message', message.statistics)
    } else if (message.type === 'unified_stimulus_pregeneration_failed') {
      // Pre-generation failed
      setIsPreGenerating(false)
      setPreGenStatus({
        success: false,
        error: message.error
      })
      componentLogger.error('Pre-generation failed via sync message', message.error)
    }
  }

  let unsubscribe: (() => void) | undefined
  if (window.electronAPI?.onSyncMessage) {
    unsubscribe = window.electronAPI.onSyncMessage(handleSyncMessage)
    componentLogger.debug('Pre-generation progress listener registered')
  }

  return () => {
    unsubscribe?.()
  }
}, [])
```

**Also add state for progress**:
```typescript
// Add after line 50:
const [preGenProgress, setPreGenProgress] = useState<{
  phase?: string
  direction?: string
  currentFrame?: number
  totalFrames?: number
  percentComplete?: number
  memoryBytes?: number
} | null>(null)
```

**Update progress bar UI** (replace lines 312-323):
```tsx
{/* Progress indicator while pre-generating */}
{isPreGenerating && (
  <div className="flex flex-col gap-2">
    <div className="flex items-center gap-2 text-sci-secondary-300">
      <div className="animate-spin h-4 w-4 border-2 border-sci-primary-500 border-t-transparent rounded-full"></div>
      <span className="text-sm">
        {preGenProgress?.phase === 'generating'
          ? `Generating ${preGenProgress.direction} frames...`
          : preGenProgress?.phase === 'compressing'
          ? `Compressing ${preGenProgress.direction}: ${preGenProgress.currentFrame}/${preGenProgress.totalFrames}`
          : 'Initializing...'}
      </span>
    </div>
    <div className="w-full bg-sci-secondary-700 rounded-full h-2 overflow-hidden">
      <div
        className="h-full bg-sci-primary-500 rounded-full transition-all duration-300"
        style={{ width: `${preGenProgress?.percentComplete || 0}%` }}
      ></div>
    </div>
    {preGenProgress?.percentComplete !== undefined && (
      <div className="text-xs text-sci-secondary-400 text-right">
        {preGenProgress.percentComplete.toFixed(1)}% complete
        {preGenProgress.memoryBytes && ` (${(preGenProgress.memoryBytes / 1024 / 1024).toFixed(1)} MB)`}
      </div>
    )}
  </div>
)}
```

---

## Summary of All Issues

| ID | Issue | Priority | Est. Fix Time | File(s) |
|----|-------|----------|--------------|---------|
| 1 | No progress broadcasting in pre-generation | P0 (CRITICAL) | 45 min | `unified_stimulus.py` |
| 2 | Frontend not listening for progress | P0 (CRITICAL) | 30 min | `StimulusGenerationViewport.tsx` |
| 3 | No pre-check in preview mode handler | P0 (CRITICAL) | 30 min | `main.py` |
| 4 | Status lost on viewport switch | P1 (HIGH) | 60 min | `App.tsx` |
| 5 | Preview mode error handling incomplete | P1 (HIGH) | 20 min | `AcquisitionViewport.tsx` |
| 6 | Record mode pre-gen blocks UI | P1 (HIGH) | 30 min | `manager.py` |
| 7 | No status persistence | P1 (IMPORTANT) | 90 min | `unified_stimulus.py` |
| 8 | Error messages not user-friendly | P1 (IMPORTANT) | 15 min | `unified_stimulus.py` |
| 9 | Synchronous pre-gen blocks event loop | P1 (IMPORTANT) | 120 min | `unified_stimulus.py` |
| 10 | No frame library disk cache | P2 (MINOR) | 90 min | `unified_stimulus.py` |

**Total P0 Issues**: 3 (blocks ALL functionality)
**Total P1 Issues**: 4 (degrades UX significantly)
**Total P2 Issues**: 3 (nice to have)

---

## Verification Checklist

After implementing fixes, verify:

- [ ] Pre-generation shows progress bar with percentage
- [ ] Pre-generation shows current direction and frame count
- [ ] Preview mode auto-pre-generates if needed
- [ ] Preview mode shows clear error if pre-generation fails
- [ ] Recording mode pre-generates if needed (with progress)
- [ ] Status messages persist when switching viewports
- [ ] Error messages guide user to solution
- [ ] Presentation window shows stimulus when enabled
- [ ] Presentation window is blank when disabled
- [ ] Parameter changes invalidate cache and require re-generation

---

## Conclusion

The unified stimulus migration has a **SOLID IMPLEMENTATION** but **INCOMPLETE INTEGRATION**. The core `UnifiedStimulusController` class is well-designed and functional. However, critical IPC wiring is missing:

1. **NO PROGRESS BROADCASTING** during pre-generation (P0)
2. **NO AUTO PRE-GENERATION** in preview mode handler (P0)
3. **NO PROGRESS LISTENING** in frontend (P0)

All reported user issues stem from these 3 missing pieces. Once fixed, the system should work as designed.

**Estimated time to fix P0 issues**: **2 hours**
**Estimated time for all P1 fixes**: **+3 hours**
**Total for production-ready**: **5 hours**

---

**Audit Complete**
**Report Generated**: October 14, 2025
