# Preview/Record Mode Diagnostic Analysis

## Problem Statement

User reports: "Still, neither preview nor recording is working properly" despite:
- Stimulus library IS pre-generated (confirmed by user: "I definitely pregenerated the library")
- Backend acknowledges library is ready in Acquisition viewport

## Diagnostic Analysis

### Backend Flow Analysis

**Preview Mode Flow:**
```
1. User clicks "Play" button in preview mode
2. Frontend: startPreview() function executes
3. Frontend: Calls start_camera_acquisition command → Camera starts ✓
4. Frontend: Calls start_preview command with direction
5. Backend: _start_preview_mode() handler executes
   - Validates direction ✓
   - Checks library loaded ✓ (user confirmed it's loaded)
   - Checks if already playing → Stops existing playback (idempotent fix) ✓
   - Calls unified_stimulus.start_playback(direction, monitor_fps)
   - Returns success response to frontend
6. Backend: UnifiedStimulusController starts playback thread
   - Loops through pre-generated frames
   - Publishes frames to shared_memory channel="stimulus"
   - Updates display log
7. Frontend: Should receive frames via window.electronAPI.onSharedMemoryFrame()
```

**Record Mode Flow:**
```
1. User clicks "Record" button
2. Frontend: Shows filter warning modal
3. User confirms → startAcquisition() executes
4. Frontend: Calls start_acquisition command
5. Backend: AcquisitionManager.start_acquisition()
   - Checks if library loaded
   - If NOT loaded → Triggers async pre-generation
   - Broadcasts unified_stimulus_pregeneration_started event
   - Waits for pre-generation (takes ~3 seconds)
   - Broadcasts unified_stimulus_pregeneration_complete event
   - Starts acquisition sequence
6. Backend: Publishes stimulus frames to shared_memory
7. Frontend: Should receive frames
```

### Most Likely Root Causes

#### **#1: Presentation Window Not Visible/Active**

The user might not be seeing the stimulus because the presentation window is hidden, minimized, or not focused.

**Evidence:**
- Backend code is working (playback starts, frames published)
- Frontend receives frames (mini preview works in Acquisition viewport)
- But full-screen presentation window might not be showing

**Solution:** Check if presentation window is:
- Actually created and visible
- On the correct monitor (should be secondary display)
- Full-screen and focused
- Receiving frame events

#### **#2: Shared Memory Channel Subscription Issue**

The presentation window might not be subscribed to the "stimulus" channel properly.

**Evidence:**
- Frontend has listener: `window.electronAPI.onSharedMemoryFrame(handleStimulusFrame)`
- But there might be competing listeners
- AcquisitionViewport also listens to stimulus frames for mini preview

**Solution:** Verify presentation window has separate, dedicated listener

#### **#3: Frame Rate Mismatch**

Stimulus might be playing too fast/slow to be visible.

**Evidence:**
- monitor_fps is read from parameters (default 60 Hz)
- If FPS is misconfigured, frames might flicker too fast to see

**Solution:** Verify monitor_fps matches actual display refresh rate

#### **#4: Display Selection Wrong**

Stimulus might be showing on wrong monitor (primary instead of secondary).

**Evidence:**
- Backend selects secondary display by default (correct behavior)
- But if only one display exists, falls back to primary

**Solution:** Check which display is actually selected in parameters

## Immediate Diagnostic Steps

### Step 1: Check Backend Logs

The user should look for these log messages:

**If preview works:**
```
Preview mode started: LR at 60.0 fps
Playback loop started: LR, 180 frames at 60.0 fps (frame interval: 16.67ms)
```

**If library NOT loaded:**
```
Stimulus library not loaded. Please visit Stimulus Generation tab...
```

**If already playing:**
```
Stopping existing playback before starting preview
```

### Step 2: Check Frontend Console

Look for these messages in browser DevTools console:

**If preview successful:**
```
Preview started successfully {direction: 'LR', fps: 60}
```

**If preview failed:**
```
Failed to start preview: <error message>
```

**If frames received:**
```
Received stimulus frame metadata for mini preview {frame_index: 0, ...}
```

### Step 3: Check Presentation Window

- Is it visible on the screen?
- Is it full-screen?
- Is it on the correct monitor?
- Does it show black or does it show stimulus pattern?

## Quick Fix Suggestions

### Fix #1: Explicit Presentation Window Show

Add explicit command to show/focus presentation window when preview starts.

**File:** `apps/desktop/src/electron/main.ts`

Look for presentation window creation and add:
```typescript
// When preview starts, ensure presentation window is visible
ipcMain.on('start_preview', () => {
  if (presentationWindow) {
    presentationWindow.show()
    presentationWindow.focus()
  }
})
```

### Fix #2: Monitor Test First

Before trying preview/record, user should:
1. Click "Test Monitor" button in Acquisition viewport
2. Verify colored quadrants appear on presentation monitor
3. If quadrants work → Shared memory delivery is working
4. If quadrants DON'T work → Presentation window issue

### Fix #3: Check Stimulus Mini Preview

The Acquisition viewport has a small stimulus preview canvas (right side).
- If THIS shows the moving bars → Backend is working, frames are being generated
- If this is BLACK → Backend playback not starting

## Code Locations for Investigation

### Backend Files:
- `/Users/Adam/KimLabISI/apps/backend/src/main.py:772-833` - Preview mode handlers
- `/Users/Adam/KimLabISI/apps/backend/src/acquisition/unified_stimulus.py:377-454` - Playback start
- `/Users/Adam/KimLabISI/apps/backend/src/acquisition/unified_stimulus.py:89-165` - Playback loop

### Frontend Files:
- `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx:200-247` - startPreview()
- `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/StimulusPresentationViewport.tsx` - Presentation window listener
- `/Users/Adam/KimLabISI/apps/desktop/src/electron/main.ts` - Presentation window creation

## Expected User Experience

### Working Preview Mode:
1. User pre-generates stimulus (sees "Stimulus Ready" badge)
2. User clicks "Play" in preview mode
3. Camera feed shows live video in left panel
4. Mini stimulus preview (right panel) shows moving bars
5. Presentation monitor shows full-screen moving bars
6. Status shows "PREVIEW" in cyan
7. User can change direction using dropdown → bars update live

### Working Record Mode:
1. User clicks "Record" button
2. Filter warning modal appears
3. User clicks "Proceed"
4. If library not ready:
   - Status shows "PRE-GENERATING" in yellow
   - Modal stays open showing progress
   - Takes ~3 seconds
   - Status changes to "ACQUIRING" in green
   - Modal closes
5. Camera records frames
6. Stimulus plays on presentation monitor
7. Histogram and timing plots update in real-time
8. Phase indicator shows current sweep direction
9. Recording stops automatically after all cycles complete

## Next Steps for User

**To help diagnose the issue, please report:**

1. **What exactly happens when you click "Play" in preview mode?**
   - Does status change from "STOPPED" to "PREVIEW"?
   - Does camera feed show live video?
   - Does mini stimulus preview (right panel) show moving bars?
   - Does presentation monitor show anything?

2. **What exactly happens when you click "Record" button?**
   - Does filter warning modal appear?
   - After clicking "Proceed", what happens?
   - Does status show "PRE-GENERATING" then "ACQUIRING"?
   - Does modal close or show error?

3. **Check the backend terminal logs:**
   - Does it say "Preview mode started: LR at 60.0 fps"?
   - Does it say "Playback loop started"?
   - Any error messages visible?

4. **Check browser DevTools console:**
   - Open DevTools (Cmd+Option+I on Mac)
   - Switch to Console tab
   - Try starting preview again
   - Copy any red error messages

With this information, we can pinpoint the exact failure point!
