# "Playback already running" Error - Fix Applied

## Problem

User encountered this error when trying to start preview mode:

```
⚠️
Camera Error
Error: Playback already running - stop current playback first
```

## Root Cause

The `UnifiedStimulusController.start_playback()` method checks if playback is already running (line 397-401) and returns an error if `self._is_playing` is True.

This happens when:
1. User was previously in preview mode
2. User navigated away or changed modes
3. Frontend didn't properly stop the playback
4. User tries to start preview again → Error!

## Solution Implemented

Added idempotent playback stopping in `_start_preview_mode()` handler (main.py lines 804-810):

```python
# CRITICAL FIX: Stop any existing playback first (idempotent)
# This allows preview mode to be restarted or switched between directions
if unified_stimulus.is_playing():
    logger.info("Stopping existing playback before starting preview")
    stop_result = unified_stimulus.stop_playback()
    if not stop_result.get("success") and stop_result.get("error") != "No playback running":
        logger.warning(f"Failed to stop existing playback: {stop_result.get('error')}")
```

## How It Works

**Before Fix:**
```
User clicks "Start Preview"
→ Check if library loaded ✓
→ Start playback
→ Error: "Playback already running" ✗
```

**After Fix:**
```
User clicks "Start Preview"
→ Check if library loaded ✓
→ Check if playback already running → Yes, stop it first ✓
→ Start new playback ✓
```

## Benefits

1. **Idempotent**: Calling `start_preview` multiple times works correctly
2. **User-friendly**: No error if user accidentally clicks preview twice
3. **Robust**: Handles edge cases where frontend cleanup fails
4. **Clean state**: Always starts with fresh playback state

## Files Modified

- `/Users/Adam/KimLabISI/apps/backend/src/main.py` (lines 804-810)

## Testing

Try these scenarios:
1. **Double-click preview**: Click "Start Preview" twice quickly → Should work without error
2. **Mode switching**: Start preview, switch to another viewport, come back, start preview again → Should work
3. **Direction changes**: Already handled by `_update_preview_direction()` which also stops playback first

The fix ensures preview mode is always startable regardless of previous state.
