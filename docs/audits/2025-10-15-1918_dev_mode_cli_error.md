# Development Mode CLI Implementation Error

**Date**: 2025-10-15T19:18:15Z
**Status**: ❌ CRITICAL - Backend startup failure
**Component**: Camera Manager initialization

---

## Error Summary

Backend fails to start with `TypeError: CameraManager.__init__() got an unexpected keyword argument 'param_manager'`

## Error Details

### Primary Error (2025-10-15T19:18:15.262Z)
```
TypeError: CameraManager.__init__() got an unexpected keyword argument 'param_manager'
  File "/Users/Adam/KimLabISI/apps/backend/src/main.py", line 2423, in main
    services = create_services(config)
  File "/Users/Adam/KimLabISI/apps/backend/src/main.py", line 108, in create_services
    camera = CameraManager(
```

### Secondary Error (Destructor)
```
AttributeError: 'CameraManager' object has no attribute 'is_streaming'
  File "/Users/Adam/KimLabISI/apps/backend/src/camera/manager.py", line 885, in __del__
    self.shutdown()
  File "/Users/Adam/KimLabISI/apps/backend/src/camera/manager.py", line 879, in shutdown
    self.stop_acquisition()
  File "/Users/Adam/KimLabISI/apps/backend/src/camera/manager.py", line 820, in stop_acquisition
    if not self.is_streaming:
```

## Root Cause

In `main.py` line 108, `CameraManager` is being instantiated with `param_manager` parameter:

```python
camera = CameraManager(
    param_manager=param_manager,  # ❌ Not in CameraManager.__init__() signature
    ipc=ipc,
    shared_memory=shared_memory,
    synchronization_tracker=sync_tracker,
)
```

But `CameraManager.__init__()` does NOT accept `param_manager` parameter. Need to check actual signature.

## Impact

- ❌ Backend cannot start
- ❌ Development mode CLI flag cannot be tested
- ❌ All camera functionality unavailable

## Investigation Needed

1. Check `CameraManager.__init__()` signature in `src/camera/manager.py`
2. Determine if `param_manager` should be added to signature or removed from call
3. Fix destructor issue with `is_streaming` attribute

---

**Next Steps**: Investigate CameraManager signature and fix initialization
