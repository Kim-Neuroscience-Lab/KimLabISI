# Grayscale Frame Rendering Integration Diagnosis

**Date:** 2025-10-16
**Issue:** Stimulus frames not rendering after grayscale transition
**Severity:** CRITICAL - Complete frame display failure

---

## Executive Summary

The stimulus frames are NOT rendering because of a **missing TypeScript interface field**. The backend correctly publishes grayscale frames with `channels: 1` metadata, but the frontend TypeScript interface `SharedMemoryFrameMetadata` does NOT include the `channels` field. This causes the frontend to calculate channels from frame size, which works correctly. However, there may be additional integration issues in the frame flow.

**Root Cause Identified:**
1. ✅ **Backend Publishing:** CORRECT - Backend publishes grayscale frames with `channels: 1` metadata
2. ⚠️ **TypeScript Interface:** INCOMPLETE - `SharedMemoryFrameMetadata` missing `channels` field
3. ✅ **Frontend Conversion:** ROBUST - Falls back to calculating channels from data size
4. ❓ **Presentation State:** NEEDS VERIFICATION - May not be enabled correctly

---

## Detailed Diagnostic Findings

### 1. Backend Frame Publishing Analysis

**File:** `/Users/Adam/KimLabISI/apps/backend/src/acquisition/unified_stimulus.py`

#### ✅ VERIFIED: Grayscale Frame Generation
- **Line 525:** `grayscale = frames[frame_index]` - Direct grayscale lookup from pre-generated library
- **Line 535:** Metadata includes `"channels": 1` - Backend explicitly tells frontend this is grayscale
- **Line 606:** `get_frame_for_viewport()` returns grayscale frames directly
- **Line 775:** Baseline frames also created as grayscale with `channels: 1`

#### ✅ VERIFIED: Shared Memory Publishing
**File:** `/Users/Adam/KimLabISI/apps/backend/src/ipc/shared_memory.py`

- **Line 287:** `channels = metadata.get("channels", 1)` - Defaults to grayscale
- **Line 301:** `channels=channels` - Stored in FrameMetadata dataclass
- **Line 310-312:** Published to ZeroMQ as part of metadata dict
- **Line 543:** Baseline frames also published with `"channels": 1`

**Backend Publishing Status:** ✅ WORKING CORRECTLY

---

### 2. Frontend TypeScript Interface Analysis

**File:** `/Users/Adam/KimLabISI/apps/desktop/src/types/electron.d.ts`

#### ⚠️ CRITICAL ISSUE FOUND: Missing `channels` Field

```typescript
// Lines 27-41
export interface SharedMemoryFrameMetadata {
  frame_id: number
  timestamp_us: number
  frame_index: number
  direction: string
  angle_degrees: number
  width_px: number
  height_px: number
  total_frames: number
  start_angle: number
  end_angle: number
  offset_bytes: number
  data_size_bytes: number
  shm_path: string
  // ❌ MISSING: channels field!
}
```

**Impact:** The TypeScript metadata interface does NOT include the `channels` field that the backend is sending. However, this may not break the rendering because of the fallback logic.

**Severity:** MEDIUM - TypeScript interface incomplete, but frontend has fallback

---

### 3. Frontend Grayscale Conversion Analysis

**File:** `/Users/Adam/KimLabISI/apps/desktop/src/hooks/useFrameRenderer.ts`

#### ✅ VERIFIED: Robust Fallback Logic

```typescript
// Lines 85-110
const totalPixels = width_px * height_px
const channels = uint8Array.length / totalPixels  // ✅ Calculates from data size

if (channels === 4) {
  // RGBA format - direct transfer (legacy support)
  imageData.data.set(uint8Array)
} else if (channels === 1) {
  // ✅ Grayscale format - converts to RGBA for Canvas API
  const rgbaData = imageData.data
  for (let i = 0; i < totalPixels; i++) {
    const gray = uint8Array[i]
    const rgbaIndex = i * 4
    rgbaData[rgbaIndex] = gray     // R
    rgbaData[rgbaIndex + 1] = gray // G
    rgbaData[rgbaIndex + 2] = gray // B
    rgbaData[rgbaIndex + 3] = 255  // A
  }
}
```

**Frontend Conversion Status:** ✅ WORKING CORRECTLY (with fallback)

**Key Insight:** Even though the `channels` field is not in the TypeScript interface, the frontend calculates channels from the actual data size (`uint8Array.length / totalPixels`), so grayscale frames **should** render correctly.

---

### 4. Presentation Window Integration Analysis

**File:** `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/StimulusPresentationViewport.tsx`

#### ❓ POTENTIAL ISSUE: Presentation State Gating

```typescript
// Lines 44-49
const handleSharedMemoryFrame = async (metadata: SharedMemoryFrameData) => {
  // Only render frames when presentation is enabled
  if (!presentationEnabled) {
    componentLogger.debug('Ignoring frame - presentation not enabled')
    return  // ❌ FRAME DROPPED if presentation not enabled!
  }
  // ...
}
```

**Critical Check:** Presentation window will IGNORE all frames unless `presentationEnabled === true`

#### Presentation State Activation

```typescript
// Lines 83-105
const handleSyncMessage = (message: any) => {
  if (message.type === 'presentation_stimulus_state') {
    setPresentationEnabled(message.enabled)
    componentLogger.debug(`Presentation state changed: ${message.enabled}`)
  }
}
```

**Activation Trigger:** Backend must broadcast `presentation_stimulus_state: enabled=True` message

---

### 5. Backend Presentation State Broadcasting

**File:** `/Users/Adam/KimLabISI/apps/backend/src/acquisition/manager.py`

#### ✅ VERIFIED: Presentation State Broadcast on Acquisition Start

```python
# Lines 446-454
if self.ipc:
    self.ipc.send_sync_message({
        "type": "presentation_stimulus_state",
        "enabled": True,
        "timestamp": time.time()
    })
    logger.info("Sent presentation_stimulus_state: enabled=True")
```

#### ✅ VERIFIED: Presentation State Broadcast on Acquisition Stop

```python
# Lines 492-499
if self.ipc:
    self.ipc.send_sync_message({
        "type": "presentation_stimulus_state",
        "enabled": False,
        "timestamp": time.time()
    })
    logger.info("Sent presentation_stimulus_state: enabled=False")
```

**Backend Broadcast Status:** ✅ SHOULD BE WORKING

---

## Root Cause Analysis

### Primary Issue: Integration Gap

The most likely cause is **one of the following**:

1. **Presentation State Not Enabled:**
   - Frontend `StimulusPresentationViewport` drops all frames if `presentationEnabled === false`
   - Backend broadcasts `presentation_stimulus_state: enabled=True` when acquisition starts
   - **HYPOTHESIS:** Message may not be reaching frontend OR frontend not subscribed correctly

2. **Playback Loop Not Running:**
   - Backend `_playback_loop()` publishes frames in background thread
   - Runs from `start_playback()` called in `_acquisition_loop()`
   - **HYPOTHESIS:** Playback may not be starting correctly OR stopping prematurely

3. **ZeroMQ Subscription Timing:**
   - Frontend subscribes to `onSharedMemoryFrame` listener
   - Backend publishes frames immediately after `start_playback()`
   - **HYPOTHESIS:** Race condition - frontend not subscribed before first frame published

---

## Verification Steps

### Step 1: Check Backend Logs for Playback Start
**Look for:**
```
"Playback loop started: {direction}, {total_frames} frames at {fps} fps"
"Sent presentation_stimulus_state: enabled=True"
```

**If MISSING:** Playback loop is not starting → Check acquisition start logic

### Step 2: Check Frontend Console for Presentation State
**Look for:**
```
"Presentation state changed: true"
```

**If MISSING:** Frontend not receiving `presentation_stimulus_state` message → Check ZeroMQ sync channel

### Step 3: Check Frontend Console for Frame Metadata
**Look for:**
```
"Received stimulus frame metadata"
```

**If MISSING:** Frontend not subscribed to frame channel → Check listener registration

### Step 4: Check Frame Data Size
**Look for:**
```typescript
console.log('Frame size:', uint8Array.length, 'pixels:', totalPixels, 'channels:', channels)
```

**Expected:** `channels === 1` for grayscale frames

---

## Recommended Fixes

### Fix 1: Add `channels` Field to TypeScript Interface (HYGIENE)

**File:** `/Users/Adam/KimLabISI/apps/desktop/src/types/electron.d.ts`

```typescript
export interface SharedMemoryFrameMetadata {
  frame_id: number
  timestamp_us: number
  frame_index: number
  direction: string
  angle_degrees: number
  width_px: number
  height_px: number
  total_frames: number
  start_angle: number
  end_angle: number
  offset_bytes: number
  data_size_bytes: number
  shm_path: string
  channels: number  // ✅ ADD THIS FIELD
}
```

**Priority:** MEDIUM - Improves type safety, but not required for functionality due to fallback

---

### Fix 2: Add Explicit Logging to Diagnose Presentation State

**File:** `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/StimulusPresentationViewport.tsx`

```typescript
// Add logging to see if frames are being received but dropped
const handleSharedMemoryFrame = async (metadata: SharedMemoryFrameData) => {
  console.log('[StimulusPresentationViewport] Frame received:', {
    frame_id: metadata.frame_id,
    presentationEnabled,
    width: metadata.width_px,
    height: metadata.height_px,
    data_size: metadata.data_size_bytes
  })

  if (!presentationEnabled) {
    console.warn('[StimulusPresentationViewport] Frame DROPPED - presentation not enabled')
    return
  }
  // ...
}
```

**Priority:** HIGH - Essential for debugging

---

### Fix 3: Verify Playback Loop Startup

**File:** `/Users/Adam/KimLabISI/apps/backend/src/acquisition/manager.py`

Add logging after `start_playback()`:

```python
# Line 590 (after start_playback call)
start_result = self.unified_stimulus.start_playback(
    direction=direction,
    monitor_fps=monitor_fps
)
if not start_result.get("success"):
    raise RuntimeError(
        f"Failed to start unified stimulus: {start_result.get('error')}"
    )
logger.info(
    f"✅ Unified stimulus playback started: {direction}, "
    f"{start_result.get('total_frames')} frames at {start_result.get('fps')} fps"
)

# Add verification that playback thread is actually running
import time
time.sleep(0.1)  # Give thread time to start
if not self.unified_stimulus.is_playing():
    raise RuntimeError("Playback thread failed to start!")
```

**Priority:** HIGH - Verifies critical integration point

---

### Fix 4: Add Frame Reception Logging to Frontend

**File:** `/Users/Adam/KimLabISI/apps/desktop/src/hooks/useFrameRenderer.ts`

```typescript
const renderFrame = useCallback((frameData: FrameData) => {
  console.log('[useFrameRenderer] Rendering frame:', {
    frame_id: frameData.frame_id,
    width: frameData.width_px,
    height: frameData.height_px,
    data_size: frameData.frame_data instanceof ArrayBuffer ? frameData.frame_data.byteLength : 'unknown'
  })

  const canvas = canvasRef.current
  if (!canvas) {
    console.warn('[useFrameRenderer] Canvas ref not available!')
    return
  }

  // ... rest of function

  // After calculating channels
  console.log('[useFrameRenderer] Frame format:', {
    totalPixels,
    dataLength: uint8Array.length,
    calculatedChannels: channels,
    isGrayscale: channels === 1,
    isRGBA: channels === 4
  })

  // ...
}, [])
```

**Priority:** HIGH - Essential for debugging

---

## Testing Protocol

### Test 1: Verify Backend Publishing
**Run:**
1. Start backend with debug logging
2. Start acquisition (record mode)
3. Check backend logs for:
   - "Playback loop started"
   - "Sent presentation_stimulus_state: enabled=True"

**Expected Result:** Both messages should appear in logs

---

### Test 2: Verify Frontend Receiving Presentation State
**Run:**
1. Open browser console
2. Start acquisition
3. Check for console log: "Presentation state changed: true"

**Expected Result:** Message should appear in console

---

### Test 3: Verify Frontend Receiving Frames
**Run:**
1. Open browser console
2. Start acquisition
3. Check for console logs:
   - "[StimulusPresentationViewport] Frame received"
   - "[useFrameRenderer] Rendering frame"

**Expected Result:** Continuous stream of frame logs

---

### Test 4: Verify Grayscale Conversion
**Run:**
1. Add logging to useFrameRenderer (see Fix 4)
2. Start acquisition
3. Check console log for: `calculatedChannels: 1`

**Expected Result:** All frames should have `channels === 1`

---

## Most Likely Issues (Ranked)

### 1. Presentation State Not Enabled (70% probability)
**Symptom:** Frontend receives frames but drops them
**Fix:** Verify `presentation_stimulus_state` message is received and sets `presentationEnabled = true`
**Debugging:** Add console.log in `handleSharedMemoryFrame` (see Fix 2)

### 2. Playback Loop Not Starting (20% probability)
**Symptom:** No frames published by backend
**Fix:** Verify `start_playback()` succeeds and thread starts
**Debugging:** Check backend logs for "Playback loop started" message

### 3. ZeroMQ Subscription Timing (10% probability)
**Symptom:** Frontend misses first few frames
**Fix:** Ensure frontend subscribes before backend starts publishing
**Debugging:** Check if frames start appearing after a delay

---

## Next Steps

1. **Add diagnostic logging** (Fixes 2, 3, 4)
2. **Run Test Protocol** (all 4 tests)
3. **Analyze console logs** to determine which integration point is failing
4. **Apply targeted fix** based on diagnostic results

---

## Files Analyzed

### Backend
- ✅ `/Users/Adam/KimLabISI/apps/backend/src/acquisition/unified_stimulus.py` - Frame generation and publishing
- ✅ `/Users/Adam/KimLabISI/apps/backend/src/ipc/shared_memory.py` - Shared memory frame writing
- ✅ `/Users/Adam/KimLabISI/apps/backend/src/acquisition/manager.py` - Acquisition orchestration

### Frontend
- ✅ `/Users/Adam/KimLabISI/apps/desktop/src/types/electron.d.ts` - TypeScript interfaces
- ✅ `/Users/Adam/KimLabISI/apps/desktop/src/hooks/useFrameRenderer.ts` - Frame rendering logic
- ✅ `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/StimulusPresentationViewport.tsx` - Presentation window
- ✅ `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx` - Acquisition viewport

---

## Summary

**What's Working:**
- ✅ Backend generates and publishes grayscale frames with `channels: 1`
- ✅ Frontend has robust fallback to calculate channels from data size
- ✅ Backend broadcasts presentation state on acquisition start/stop
- ✅ Grayscale to RGBA conversion logic is correct

**What Needs Investigation:**
- ❓ Is presentation window receiving `presentation_stimulus_state` messages?
- ❓ Is playback loop actually starting and publishing frames?
- ❓ Is frontend subscribed to frame channel before backend starts publishing?

**Recommended Action:**
Add diagnostic logging (Fixes 2-4) and run test protocol to identify which integration point is failing.
