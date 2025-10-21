# Development Mode CLI Flag - Complete Implementation

**Date**: 2025-10-15T19:26:00Z
**Status**: ✅ COMPLETE - Ready for testing
**Feature**: CLI flag for development mode with software timestamp support

---

## Summary

Successfully implemented `--dev-mode` CLI flag for `setup_and_run.sh` that enables development mode, allowing software timestamps for consumer webcams during development and testing.

## Implementation Timeline

### 2025-10-15T12:08 - Initial Implementation
- ✅ Added `--dev-mode` flag parsing to setup_and_run.sh
- ✅ Added help documentation with `--help` flag
- ✅ Added warning banner when dev mode enabled
- ✅ Exported `ISI_DEV_MODE=true` environment variable
- ✅ Added backend code to read environment variable and set parameter
- ✅ Tested environment variable propagation

### 2025-10-15T19:18 - Error Discovered
- ❌ Backend startup failed with `TypeError: CameraManager.__init__() got an unexpected keyword argument 'param_manager'`
- 📝 Documented error in DEV_MODE_CLI_ERROR_2025-10-15T19-18.md

### 2025-10-15T19:25 - Fix Applied
- ✅ Fixed parameter name mismatch (param_manager → config)
- ✅ Verified CameraManager signature compatibility
- 📝 Documented fix in DEV_MODE_CLI_FIX_2025-10-15T19-25.md

## Complete Workflow

```bash
# Enable development mode
./setup_and_run.sh --dev-mode

# Normal production mode (default)
./setup_and_run.sh

# Show help
./setup_and_run.sh --help
```

### What Happens When --dev-mode is Used

1. **Setup Script** (setup_and_run.sh):
   - Parses `--dev-mode` flag from command line
   - Displays prominent warning banner
   - Exports `ISI_DEV_MODE=true` environment variable
   - Starts backend with environment variable set

2. **Backend Startup** (main.py:2333-2346):
   - Checks for `ISI_DEV_MODE` environment variable
   - If `true`, creates temporary ParameterManager
   - Updates `system.development_mode = true` in parameters
   - Reloads configuration to pick up the change

3. **Camera Manager** (camera/manager.py:581-620):
   - Reads `system.development_mode` parameter on acquisition start
   - If enabled, allows software timestamps when hardware timestamps unavailable
   - Displays prominent warning about development mode
   - Records `"software_dev_mode"` in all data files for provenance

## Files Modified

1. **setup_and_run.sh**:
   - Added argument parsing (lines 7-34)
   - Added warning banner (lines 49-60)
   - Exports ISI_DEV_MODE environment variable

2. **src/main.py**:
   - Added environment variable check (lines 2331-2346)
   - Fixed CameraManager parameter name (line 109)

3. **config/isi_parameters.json**:
   - Contains `system.development_mode` flag
   - Dynamically updated by CLI flag

## Testing Performed

✅ `--help` flag displays correct documentation
✅ Environment variable propagates to backend correctly
✅ Parameter manager updates and persists the flag
✅ CameraManager parameter name mismatch fixed

## Ready for User Testing

User can now test complete workflow:
1. Run `./setup_and_run.sh --dev-mode`
2. Backend should start successfully
3. Camera acquisition should work with Mac's built-in camera
4. Warning should appear in logs about development mode
5. Data files should record `timestamp_source: "software_dev_mode"`

## Warnings and Limitations

⚠️ Development mode is NOT suitable for:
- ❌ Scientific publication data
- ❌ Final experiments
- ❌ Data shared with collaborators
- ❌ Any analysis requiring precise timing (<1ms)

✅ Development mode IS suitable for:
- ✅ UI development and testing
- ✅ Algorithm development
- ✅ System integration testing
- ✅ Learning the system
- ✅ Preliminary experiments (with clear documentation)

## Production Transition

Before publication:
1. Acquire industrial camera (FLIR Blackfly S, Basler ace, PCO.panda)
2. Run without `--dev-mode` flag (or set `system.development_mode = false`)
3. Re-run all final experiments
4. Verify `timestamp_info.camera_timestamp_source = "hardware"`

---

**Status**: Implementation complete, ready for end-to-end testing
**Next Step**: User should test `./setup_and_run.sh --dev-mode` with Mac camera
