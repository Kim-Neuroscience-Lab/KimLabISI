# Development Mode CLI Parameter Name Mismatch - FIX COMPLETE

**Date**: 2025-10-15T19:25:00Z
**Status**: ✅ FIXED
**Component**: CameraManager initialization

---

## Problem Summary

Backend failed to start with `TypeError: CameraManager.__init__() got an unexpected keyword argument 'param_manager'`

## Root Cause

**Signature Mismatch**: In main.py line 108, `CameraManager` was being instantiated with `param_manager` parameter, but `CameraManager.__init__()` signature expects `config` parameter (not `param_manager`).

### CameraManager.__init__() Actual Signature (camera/manager.py:47-54)
```python
def __init__(
    self,
    config,              # ← Expects 'config' parameter
    ipc,
    shared_memory,
    synchronization_tracker=None,
    camera_triggered_stimulus=None,
):
```

### Incorrect Call (main.py:108-113)
```python
camera = CameraManager(
    param_manager=param_manager,  # ❌ WRONG: Using 'param_manager' keyword
    ipc=ipc,
    shared_memory=shared_memory,
    synchronization_tracker=sync_tracker,
)
```

## Fix Applied (2025-10-15T19:25:00Z)

Changed parameter name from `param_manager` to `config` in main.py:108:

```python
camera = CameraManager(
    config=param_manager,  # ✅ FIXED: Using 'config' keyword
    ipc=ipc,
    shared_memory=shared_memory,
    synchronization_tracker=sync_tracker,
)
```

**Note**: The value passed is still `param_manager` (ParameterManager instance), which is correct because `CameraManager` uses it to access parameters via `self.config.get_parameter_group("system")` (see camera/manager.py:581, 655).

## Why This Happened

During refactoring, the parameter name was changed in the call site but not updated to match the `CameraManager.__init__()` signature. The `CameraManager` expects a `config` parameter (which can be any object with `get_parameter_group()` method), and we're passing `ParameterManager` which satisfies that interface.

## Verification Needed

After fix, backend should:
1. ✅ Start without TypeError
2. ✅ Create CameraManager successfully
3. ✅ Access development_mode parameter via `self.config.get_parameter_group("system")`
4. ✅ Allow camera acquisition with software timestamps when dev mode enabled

## Files Modified

- `/Users/Adam/KimLabISI/apps/backend/src/main.py` (line 109)

---

**Status**: Fix applied, ready for testing
