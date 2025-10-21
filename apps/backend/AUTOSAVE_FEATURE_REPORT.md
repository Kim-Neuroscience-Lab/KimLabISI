# Auto-Save Stimulus Library Feature

## Overview

Implemented automatic saving of pre-generated stimulus datasets to disk, ensuring that the load feature always has a dataset available if one has ever been generated. This enhancement improves user experience by persisting stimulus libraries across sessions without manual intervention.

## Motivation

Previously, users had to manually save stimulus libraries after pre-generation. If they forgot or the application crashed, the pre-generated data would be lost and would need to be regenerated (a time-consuming process taking 5-10 seconds). The auto-save feature eliminates this friction by automatically persisting the library whenever pre-generation succeeds.

## Implementation Details

### Changes Made

#### 1. New Handler Function: `_unified_stimulus_pregenerate_handler`
**Location:** `/Users/Adam/KimLabISI/apps/backend/src/main.py` (lines 825-865)

Created a wrapper handler that:
- Calls `unified_stimulus.pre_generate_all_directions()`
- On success, automatically calls `unified_stimulus.save_library_to_disk()`
- Returns combined results with auto-save status
- Handles save failures gracefully (logs warning but doesn't fail pre-generation)

**Key Features:**
- Non-blocking: Save failures don't affect pre-generation success
- Transparent: Happens automatically without user intervention
- Informative: Returns save status in response for debugging

#### 2. Updated Command Handler
**Location:** `/Users/Adam/KimLabISI/apps/backend/src/main.py` (line 340-342)

Changed from:
```python
"unified_stimulus_pregenerate": lambda cmd: unified_stimulus.pre_generate_all_directions(),
```

To:
```python
"unified_stimulus_pregenerate": lambda cmd: _unified_stimulus_pregenerate_handler(
    unified_stimulus, cmd
),
```

#### 3. Auto-Save in Preview Mode
**Location:** `/Users/Adam/KimLabISI/apps/backend/src/main.py` (lines 937-943)

Added auto-save logic after successful auto-generation in `_start_preview_mode`:
```python
# Auto-save library to disk after successful pre-generation
logger.info("Auto-generation successful, automatically saving library to disk...")
save_result = unified_stimulus.save_library_to_disk()
if save_result.get("success"):
    logger.info(f"Library auto-saved to: {save_result.get('save_path')}")
else:
    logger.warning(f"Auto-save failed (non-fatal): {save_result.get('error')}")
```

#### 4. Auto-Save in Presentation Stimulus Enable
**Location:** `/Users/Adam/KimLabISI/apps/backend/src/main.py` (lines 687-693)

Added auto-save logic after successful auto-generation in `_set_presentation_stimulus_enabled`:
```python
# Auto-save library to disk after successful pre-generation
logger.info("Pre-generation successful, automatically saving library to disk...")
save_result = unified_stimulus.save_library_to_disk()
if save_result.get("success"):
    logger.info(f"Library auto-saved to: {save_result.get('save_path')}")
else:
    logger.warning(f"Auto-save failed (non-fatal): {save_result.get('error')}")
```

### Default Save Location

The library is automatically saved to:
```
/Users/Adam/KimLabISI/apps/backend/data/stimulus_library/
```

This directory is created automatically if it doesn't exist (via `mkdir(parents=True, exist_ok=True)`).

### Saved Files

The auto-save creates the following files:
1. `LR_frames.h5` - Left-to-right stimulus frames (HDF5 with gzip compression)
2. `TB_frames.h5` - Top-to-bottom stimulus frames (HDF5 with gzip compression)
3. `RL_frames.h5` - Right-to-left stimulus frames (HDF5 with gzip compression)
4. `BT_frames.h5` - Bottom-to-top stimulus frames (HDF5 with gzip compression)
5. `library_metadata.json` - Generation parameters and metadata

### Response Format

The handler now returns additional fields in the success response:

```python
{
    "success": True,
    "statistics": {...},  # Original pre-generation stats
    "total_duration_sec": 10.5,
    "auto_saved": True,  # NEW: Auto-save succeeded
    "save_path": "/path/to/library",  # NEW: Where files were saved
    "saved_files": ["LR_frames.h5", ...]  # NEW: List of saved files
}
```

If save fails (non-fatal):
```python
{
    "success": True,  # Pre-generation succeeded
    "statistics": {...},
    "total_duration_sec": 10.5,
    "auto_saved": False,  # NEW: Auto-save failed
    "save_warning": "Disk full"  # NEW: Save error message
}
```

## Error Handling

### Graceful Degradation
Auto-save failures do NOT fail the pre-generation operation. The system logs a warning but continues normally. This ensures that:
1. Pre-generation success is not affected by save failures
2. Memory-cached library remains usable even if save fails
3. User is informed via logs but not interrupted

### Logged Events
- **Success:** `"Library auto-saved to: /path/to/library"`
- **Failure:** `"Auto-save failed (non-fatal): [error message]"`
- **Pre-generation:** `"Pre-generation successful, automatically saving library to disk..."`

## Testing

### Unit Tests
Created comprehensive unit tests in `test_autosave_logic.py`:

1. **Test 1: Auto-save after successful pre-generation**
   - Verifies save is called after success
   - Validates response includes auto-save info

2. **Test 2: Pre-generation succeeds even if auto-save fails**
   - Ensures pre-generation success is not affected
   - Validates save warning is included in response

3. **Test 3: No auto-save when pre-generation fails**
   - Ensures save is not attempted on failure
   - Validates response indicates no auto-save

All tests pass successfully ✓

## Usage Flow

### User Perspective
1. User clicks "Pre-Generate All Directions" button
2. Backend generates stimulus patterns (~5-10 seconds)
3. **Backend automatically saves library to disk** (transparent)
4. User can now use load feature to restore library in future sessions

### Developer Perspective
```python
# Frontend sends command
await sendBackendCommand({ type: "unified_stimulus_pregenerate" });

# Backend automatically:
# 1. Pre-generates all directions
# 2. Saves to data/stimulus_library/
# 3. Returns combined status

# Response includes auto-save status:
{
  success: true,
  auto_saved: true,
  save_path: "/Users/Adam/KimLabISI/apps/backend/data/stimulus_library",
  saved_files: ["LR_frames.h5", "TB_frames.h5", "RL_frames.h5", "BT_frames.h5", "library_metadata.json"]
}
```

## Benefits

1. **No Manual Intervention:** Users no longer need to remember to save
2. **Persistent Data:** Libraries survive application restarts
3. **Faster Subsequent Sessions:** Load existing library instead of regenerating
4. **Consistency:** All pre-generation paths (explicit, preview, presentation) auto-save
5. **Backward Compatible:** Existing load functionality works without changes

## Future Enhancements

Potential improvements for future consideration:
1. **UI Indicator:** Show auto-save status in frontend UI
2. **Multiple Libraries:** Allow saving different parameter configurations
3. **Auto-Load on Startup:** Optionally load last saved library on launch
4. **Compression Options:** User-configurable compression levels
5. **Cloud Storage:** Optional cloud backup for stimulus libraries

## Files Modified

1. `/Users/Adam/KimLabISI/apps/backend/src/main.py`
   - Added `_unified_stimulus_pregenerate_handler` function
   - Updated command handler registration
   - Added auto-save in `_start_preview_mode`
   - Added auto-save in `_set_presentation_stimulus_enabled`

## Files Created

1. `/Users/Adam/KimLabISI/apps/backend/test_autosave_logic.py` - Unit tests
2. `/Users/Adam/KimLabISI/apps/backend/AUTOSAVE_FEATURE_REPORT.md` - This report

## Verification

To verify the feature is working:

1. **Check logs:** Look for "Library auto-saved to: ..." messages
2. **Check filesystem:** Verify files exist in `data/stimulus_library/`
3. **Test load:** Use load command to restore saved library
4. **Test parameters:** Verify parameter validation on load

## Conclusion

The auto-save feature enhances user experience by automatically persisting stimulus libraries after pre-generation. The implementation is robust, transparent, and handles errors gracefully without disrupting the core pre-generation functionality.
