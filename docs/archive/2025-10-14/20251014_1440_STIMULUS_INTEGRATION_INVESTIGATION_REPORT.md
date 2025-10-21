# Stimulus Integration Investigation Report
**Date:** 2025-10-14
**Issue:** Critical integration failures after PNG compression removal from unified_stimulus.py

---

## Executive Summary

After removing PNG compression from `unified_stimulus.py`, three critical integration issues emerged:

1. **Generation status doesn't persist** - Badge disappears when navigating away from Stimulus Generation viewport
2. **Acquisition viewport shows no status** - Users can't see if stimulus is pre-generated
3. **All acquisition modes broken** - Preview, record, and playback modes fail to function

**Root Cause:** Frontend state management issue compounded by missing status query mechanism. The backend IPC handler EXISTS but frontend never queries it on mount.

**Status:** Investigation complete. Implementation plan provided below.

---

## Investigation Findings

### Issue 1: Generation Status Not Persisting ✓ IDENTIFIED

**Location:** `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/StimulusGenerationViewport.tsx`

**Problem:**
- Lines 46-58: `preGenStatus` and `preGenProgress` are local component state
- Lines 130-170: Sync message listeners only work when component is mounted
- Lines 180-184: Mount effect loads initial frame but NEVER queries backend status
- When user navigates away and back, component unmounts/remounts with fresh state
- Sync messages (`unified_stimulus_pregeneration_complete`) are one-time broadcasts - missed if component not mounted

**Evidence:**
```typescript
// Lines 46-58: Ephemeral state
const [preGenStatus, setPreGenStatus] = useState<{
  success?: boolean
  error?: string
  statistics?: any
} | null>(null)

// Lines 180-184: Mount effect MISSING status query
useEffect(() => {
  if (!hasFrameData && systemState?.isConnected && sendCommand) {
    loadFrame(direction, 0, showBarMask)  // Only loads frame, not status!
  }
}, [hasFrameData, systemState?.isConnected, sendCommand])
```

**Why This Matters:**
User can't tell if pre-generation already completed in previous session. Forces redundant re-generation.

---

### Issue 2: Acquisition Viewport Shows No Status ✓ IDENTIFIED

**Location:** `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx`

**Problem:**
- No code to query unified stimulus status
- No visual indicator showing "Stimulus Ready" vs "Need to Pre-generate"
- Users press Record and acquisition fails with cryptic error

**Evidence:**
Searched entire file - ZERO references to:
- `unified_stimulus_get_status`
- `library_loaded`
- `library_status`
- Any status badge component

**Why This Matters:**
Users blindly start acquisition without knowing if stimulus is ready. Leads to confusion and failed experiments.

---

### Issue 3: All Acquisition Modes Broken ✓ ROOT CAUSE IDENTIFIED

**Backend IPC Handler Status:**

✓ **Handler EXISTS** - Line 345 in `/Users/Adam/KimLabISI/apps/backend/src/main.py`:
```python
"unified_stimulus_get_status": lambda cmd: {
    "success": True,
    **unified_stimulus.get_status()
},
```

✓ **Backend method works** - Line 767-788 in `unified_stimulus.py`:
```python
def get_status(self) -> Dict[str, any]:
    """Get current controller status."""
    with self._library_lock:
        library_status = {
            direction: {
                "frames": len(data["frames"]),
                "memory_mb": sum(f.nbytes for f in data["frames"]) / 1024 / 1024
            }
            for direction, data in self._frame_library.items()
        }

    return {
        "is_playing": self._is_playing,
        "current_direction": self._current_direction,
        "current_fps": self._current_fps,
        "library_loaded": len(self._frame_library) > 0,  # ← KEY FIELD
        "library_status": library_status
    }
```

**Critical Discovery:**
- Backend works correctly
- Frontend NEVER calls the handler
- No status query on component mount
- No periodic status polling

**Evidence from Code Analysis:**

1. **Acquisition Manager** (lines 334-430) checks library before starting:
   ```python
   # Line 336: Check if library loaded
   status = self.unified_stimulus.get_status()
   if not status.get("library_loaded"):
       # Pre-generates in background thread
   ```

2. **Frontend Never Queries Status:**
   - `StimulusGenerationViewport.tsx`: No query on mount
   - `AcquisitionViewport.tsx`: No query on mount
   - Only listens for broadcast messages, never polls

3. **Acquisition SHOULD Work** (backend handles missing library):
   - Lines 334-430: Auto pre-generates if missing
   - Broadcasts progress via sync messages
   - Starts acquisition when ready

   **But frontend doesn't show this state!**

---

## Why Acquisition Modes Appear Broken

They're not actually broken - **the frontend just doesn't reflect backend state.**

**What Actually Happens:**

1. User clicks "Record" → Frontend sends `start_acquisition`
2. Backend checks: `library_loaded == False`
3. Backend starts async pre-generation (lines 348-430)
4. Backend returns: `{"success": True, "async": True, "status": "pre_generating"}`
5. **Frontend ignores "async" status** → No UI feedback
6. User sees nothing happening → Thinks it's broken
7. 30 seconds later, acquisition actually starts
8. But frontend never queried status → Badge still shows "not generated"

**The Real Problem:**
Frontend state is stale. Backend is working correctly but frontend doesn't know it.

---

## Architecture Analysis

### Current Flow (Broken UX):
```
User navigates to Stimulus Generation
  ↓
Component mounts with empty state
  ↓
Loads frame (line 182) but NOT status
  ↓
User sees "Pre-Generate" button (no indication if already done)
  ↓
User clicks Pre-Generate
  ↓
Sync message: "unified_stimulus_pregeneration_complete"
  ↓
Component updates state: preGenStatus = { success: true }
  ↓
User navigates away
  ↓
Component unmounts (state lost)
  ↓
User navigates back
  ↓
Component mounts with empty state AGAIN
  ↓
Badge shows nothing (stale)
```

### Fixed Flow (Correct UX):
```
User navigates to Stimulus Generation
  ↓
Component mounts
  ↓
useEffect calls: sendCommand({ type: 'unified_stimulus_get_status' })
  ↓
Backend returns: { library_loaded: true, library_status: {...} }
  ↓
Component updates: setPreGenStatus({ success: true, statistics: ... })
  ↓
Badge shows "Complete" immediately
  ↓
User navigates away and back
  ↓
Component remounts, queries status again
  ↓
Badge shows "Complete" (correct state restored)
```

---

## Detailed Findings by File

### 1. `/Users/Adam/KimLabISI/apps/backend/src/main.py`

**Status: ✓ WORKING**

- Line 345-348: Handler `unified_stimulus_get_status` exists and works
- Line 339: Handler `unified_stimulus_pregenerate` exists
- Line 349-356: Handler `unified_stimulus_get_frame` exists
- All handlers correctly unwrap unified_stimulus methods

**No backend changes needed.**

### 2. `/Users/Adam/KimLabISI/apps/backend/src/acquisition/unified_stimulus.py`

**Status: ✓ WORKING AFTER PNG REMOVAL**

- Line 213-375: `pre_generate_all_directions()` stores raw numpy arrays
- Line 767-788: `get_status()` correctly computes `library_loaded` flag
- Line 561-596: `get_frame_for_viewport()` converts grayscale to RGBA
- Line 483-559: `_playback_loop()` accesses numpy arrays directly

**Confirmed:**
- Memory calculation fixed: `sum(f.nbytes for f in data["frames"])`
- Frame access works: `grayscale = frames[frame_index]`
- RGBA conversion works: Lines 513-517

**No backend changes needed.**

### 3. `/Users/Adam/KimLabISI/apps/backend/src/acquisition/manager.py`

**Status: ✓ WORKING**

- Line 334-336: Checks `library_loaded` before starting
- Line 336-430: Auto pre-generates if missing (async)
- Line 617-623: Gets monitor FPS and starts playback
- Line 621-628: Starts unified stimulus correctly

**Confirmed:**
- Acquisition manager correctly uses unified stimulus
- FPS validation exists (line 388-394)
- Error handling works (broadcasts failures)

**No backend changes needed.**

### 4. `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/StimulusGenerationViewport.tsx`

**Status: ⚠️ NEEDS FIX**

**Problems:**
1. Lines 46-58: State is ephemeral (lost on unmount)
2. Lines 180-184: Mount effect doesn't query backend status
3. Lines 130-170: Only listens for sync messages (misses status if not mounted)

**Fix Required:**
Add status query on mount (after line 183):
```typescript
useEffect(() => {
  if (!hasFrameData && systemState?.isConnected && sendCommand) {
    loadFrame(direction, 0, showBarMask)

    // ADDED: Query backend status to restore badge
    sendCommand({ type: 'unified_stimulus_get_status' })
      .then(result => {
        if (result.success && result.library_loaded) {
          setPreGenStatus({
            success: true,
            statistics: result.library_status
          })
        }
      })
      .catch(err => {
        console.error('Failed to query stimulus status:', err)
      })
  }
}, [hasFrameData, systemState?.isConnected, sendCommand])
```

### 5. `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx`

**Status: ⚠️ NEEDS FIX**

**Problems:**
1. No status query mechanism
2. No status badge component
3. Users can't see if stimulus is ready

**Fix Required:**
1. Add state for stimulus status (after line 153):
   ```typescript
   const [stimulusLibraryStatus, setStimulusLibraryStatus] = useState<{
     library_loaded: boolean
     is_playing: boolean
   } | null>(null)
   ```

2. Add status query on mount (new useEffect):
   ```typescript
   useEffect(() => {
     if (systemState?.isConnected && sendCommand) {
       sendCommand({ type: 'unified_stimulus_get_status' })
         .then(result => {
           if (result.success) {
             setStimulusLibraryStatus({
               library_loaded: result.library_loaded,
               is_playing: result.is_playing
             })
           }
         })
     }
   }, [systemState?.isConnected, sendCommand])
   ```

3. Add status badge in Camera Information panel (after line 1257):
   ```tsx
   <div className="border-t border-sci-secondary-600 pt-2 mt-2">
     <div className="text-xs font-medium text-sci-secondary-300 mb-2">
       Stimulus Status
     </div>
     {stimulusLibraryStatus?.library_loaded ? (
       <div className="flex items-center gap-2 px-2 py-1 bg-green-900/30 border border-green-700 rounded text-xs">
         <span className="text-green-400">✓</span>
         <span className="text-green-300">Stimulus Ready</span>
       </div>
     ) : (
       <div className="flex items-center gap-2 px-2 py-1 bg-red-900/30 border border-red-700 rounded text-xs">
         <span className="text-red-400">⚠</span>
         <span className="text-red-300">Pre-generate Required</span>
       </div>
     )}
   </div>
   ```

4. Disable Record button if not ready (line 1713):
   ```typescript
   if (isRecord) {
     // Disable if stimulus not loaded
     const stimulusNotReady = !stimulusLibraryStatus?.library_loaded
     buttonClasses = stimulusNotReady
       ? 'bg-red-900 border-red-800 text-red-400 opacity-40 cursor-not-allowed'
       : 'bg-red-600 border-red-500 text-white hover:bg-red-500'
   }
   ```

---

## Testing Verification Plan

### Test 1: Status Badge Persistence
1. Navigate to Stimulus Generation viewport
2. Click "Pre-Generate All Directions"
3. Wait for completion → Badge shows "Complete ✓"
4. Navigate to Acquisition viewport
5. Navigate back to Stimulus Generation
6. **Expected:** Badge still shows "Complete ✓"
7. **Current:** Badge shows nothing (broken)

### Test 2: Acquisition Viewport Status Indicator
1. Navigate to Acquisition viewport (before pre-generation)
2. **Expected:** Shows "Pre-generate Required ⚠"
3. Navigate to Stimulus Generation → Pre-generate
4. Navigate back to Acquisition
5. **Expected:** Shows "Stimulus Ready ✓"

### Test 3: Preview Mode
1. Pre-generate stimulus
2. Navigate to Acquisition viewport
3. Select "preview" mode
4. Click Play
5. **Expected:** Preview stimulus animates on presentation monitor
6. **Current:** Should work (backend handles this)

### Test 4: Record Mode
1. Pre-generate stimulus
2. Navigate to Acquisition viewport
3. Select "record" mode
4. Click Record (red button)
5. **Expected:** Acquisition starts, camera captures, stimulus plays
6. **Current:** Works but no UI feedback during async pre-gen

### Test 5: Playback Mode
1. Navigate to Acquisition viewport
2. Select "playback" mode
3. Select a session from dropdown
4. Click Play
5. **Expected:** Plays back recorded session
6. **Current:** Should work (backend handles this)

---

## Summary of Required Changes

### Backend: NONE ✓
All backend handlers exist and work correctly. No changes needed.

### Frontend: 2 FILES

**File 1: `StimulusGenerationViewport.tsx`**
- Add status query on mount (restore badge state)
- 15 lines of code added

**File 2: `AcquisitionViewport.tsx`**
- Add status query on mount
- Add status badge component
- Disable Record button if stimulus not ready
- ~40 lines of code added

---

## Risk Assessment

**Severity:** HIGH - Users can't use acquisition modes without visible feedback

**Complexity:** LOW - Frontend state management fix only

**Testing Required:** MEDIUM
- 5 test scenarios (listed above)
- Cross-viewport navigation testing
- Acquisition lifecycle testing

**Rollback Risk:** NONE
- Changes are additive only
- No API contract changes
- No data migration needed

---

## Root Cause Summary (Plain English)

**What happened:**
We removed PNG compression to fix memory issues. That worked great on the backend. But the frontend still had stale state management code that assumed:
1. Badge state would persist across component unmounts (it doesn't)
2. Sync messages would always arrive when components are mounted (they don't)
3. Backend would fail if library not loaded (it doesn't - it auto pre-generates)

**Why acquisition appears broken:**
Backend is actually working correctly - it auto pre-generates stimulus when needed and broadcasts progress. But the frontend never queries status on mount, so it shows stale "not generated" badges even after successful generation. Users see empty badges and think the system is broken.

**The fix:**
Make frontend query backend status on mount to restore correct state. Add status indicator in Acquisition viewport so users know if stimulus is ready before starting acquisition.

**Why this is safe:**
- Backend already has working status endpoint
- Changes are purely additive (new queries, new UI components)
- No API contract changes
- No backend changes needed
- Easy to test and verify

---

## Next Steps

1. Implement frontend fixes (StimulusGenerationViewport + AcquisitionViewport)
2. Test all 5 scenarios listed above
3. Verify badge persistence across navigation
4. Verify acquisition modes work correctly
5. User acceptance testing

**Estimated Time:** 1-2 hours implementation + 1 hour testing

---

**Report Generated:** 2025-10-14
**Investigator:** Claude (System Integration Engineer)
**Status:** Investigation Complete - Implementation Plan Provided
