# ADR-004: Parameter Manager Refactor

**Status**: Accepted
**Date**: 2025-10-11
**Deciders**: Backend Team
**Related**: [Parameter Manager](../components/parameter-manager.md), All Components

---

## Context and Problem Statement

The original architecture passed frozen parameter snapshots to components at initialization:

```python
# OLD APPROACH (Problematic)
config = ParameterManager()
camera_params = config.get_group('camera')  # Frozen dict snapshot
camera_manager = CameraManager(camera_params)
```

This caused critical issues:
- **Stale Parameters**: Components never saw parameter updates
- **Coupling**: Components tightly coupled to parameter structure
- **No Validation**: Parameter changes not validated against live system state
- **Single Source of Truth Violation**: Multiple frozen copies diverged from source

We needed a **Single Source of Truth** architecture where all components reference the same live parameter manager.

## Decision Drivers

- **Single Source of Truth**: One authoritative source for all configuration
- **NO Hardcoded Defaults**: Zero tolerance for hardcoded parameter values
- **Live Updates**: Components automatically see parameter changes
- **Validation**: Centralized validation against system state
- **Decoupling**: Components depend on interface, not structure
- **Testability**: Easy to mock parameter manager for testing
- **Thread Safety**: Concurrent parameter access must be safe

## Options Considered

### Option 1: Keep Frozen Snapshots
**Pros**:
- Simple to implement
- No thread safety concerns

**Cons**:
- Parameters become stale immediately
- Need manual refresh mechanism
- Multiple copies diverge from truth
- No centralized validation

### Option 2: Dependency Injection + Observer Pattern (SELECTED)
**Pros**:
- Single source of truth
- Components automatically notified of changes
- Centralized validation
- Clean separation of concerns

**Cons**:
- Requires refactoring all components
- Need to implement observer pattern
- Thread safety considerations

### Option 3: Global Singleton
**Pros**:
- Easy to access from anywhere

**Cons**:
- Implicit dependencies
- Hard to test
- Violates dependency injection principle

---

## Decision Outcome

**Chosen Option**: Option 2 - Dependency Injection + Observer Pattern

All components receive a **live reference** to ParameterManager and subscribe to changes:

```python
# NEW APPROACH (Correct)
param_manager = ParameterManager()  # Single source of truth

# Dependency injection
camera_manager = CameraManager(param_manager)
stimulus_generator = StimulusGenerator(param_manager)
acquisition_manager = AcquisitionManager(param_manager)

# Components subscribe to relevant groups
camera_manager.subscribe('camera')
stimulus_generator.subscribe('stimulus')
```

---

## Architecture

### Before (Single Source of Truth Violation)

```
ParameterManager
   ↓
   get_group('camera') → frozen dict copy
   ↓
CameraManager(frozen_dict)
   ↓
Uses stale parameters forever
```

**Problem**: When user changes camera parameters, CameraManager never knows.

### After (Single Source of Truth)

```
ParameterManager (Single Source of Truth)
   ↑ (live reference)
   ├─ CameraManager.param_manager
   ├─ StimulusGenerator.param_manager
   ├─ AcquisitionManager.param_manager
   └─ AnalysisPipeline.param_manager

Observer Pattern:
   param_manager.update('camera', {...})
      ↓ (notify subscribers)
   camera_manager._on_camera_params_changed({...})
```

---

## Implementation

### Phase 1: Add Observer Pattern (2025-10-11)

```python
# src/parameters/manager.py

class ParameterManager:
    """Single source of truth for all configuration."""

    def __init__(self):
        self._params = self._load_parameters()
        self._lock = threading.RLock()  # Thread safety
        self._subscribers = defaultdict(list)  # Group -> [callbacks]

    def subscribe(self, group_name: str, callback: Callable):
        """Subscribe to parameter changes for a specific group."""
        with self._lock:
            self._subscribers[group_name].append(callback)

    def update(self, group_name: str, params: dict):
        """Update parameters and notify subscribers."""
        with self._lock:
            # Validate parameters
            self._validate_group(group_name, params)

            # Update parameters
            self._params[group_name].update(params)

            # Save to disk (atomic write)
            self._save_parameters()

            # Notify subscribers
            for callback in self._subscribers[group_name]:
                callback(params)

    def get(self, group_name: str, param_name: str):
        """Thread-safe parameter access."""
        with self._lock:
            return self._params[group_name][param_name]
```

### Phase 2: Refactor Components (2025-10-11 to 2025-10-12)

**CameraManager** (Before):
```python
class CameraManager:
    def __init__(self, camera_params: dict):
        self.fps = camera_params['fps']  # Frozen value
        self.exposure = camera_params['exposure']
```

**CameraManager** (After):
```python
class CameraManager:
    def __init__(self, param_manager: ParameterManager):
        self.param_manager = param_manager  # Live reference
        self.param_manager.subscribe('camera', self._on_camera_params_changed)

        # CRITICAL: NO hardcoded defaults allowed
        # Parameters MUST be None until loaded from param_manager
        self.fps: Optional[float] = None
        self.exposure: Optional[float] = None

    def _on_camera_params_changed(self, params: dict):
        """React to camera parameter changes."""
        if 'fps' in params:
            self._update_fps(params['fps'])
        if 'exposure' in params:
            self._update_exposure(params['exposure'])

    def get_fps(self) -> float:
        """Always returns current value from source of truth."""
        return self.param_manager.get('camera', 'fps')
```

**StimulusGenerator** (After):
```python
class StimulusGenerator:
    def __init__(self, param_manager: ParameterManager):
        self.param_manager = param_manager
        self.param_manager.subscribe('stimulus', self._on_stimulus_params_changed)

    def _on_stimulus_params_changed(self, params: dict):
        """Invalidate pre-generated library if stimulus params changed."""
        logger.info("Stimulus parameters changed, clearing library")
        self._clear_library()

    def generate_stimulus(self):
        """Always uses current parameters from source of truth."""
        spatial_freq = self.param_manager.get('stimulus', 'spatial_freq_cpm')
        temporal_freq = self.param_manager.get('stimulus', 'temporal_freq_hz')
        # ... generate with current values
```

### Phase 3: Update Main Entry Point (2025-10-12)

```python
# src/main.py

async def main():
    # Create single source of truth
    param_manager = ParameterManager()

    # Inject into all components
    shared_memory = SharedMemory()
    ipc = MultiChannelIPC()

    camera_manager = CameraManager(param_manager)
    stimulus_generator = StimulusGenerator(param_manager)
    unified_stimulus = UnifiedStimulusController(param_manager, stimulus_generator, shared_memory, ipc)
    acquisition_manager = AcquisitionManager(param_manager, camera_manager, unified_stimulus, ipc)
    analysis_manager = AnalysisManager(param_manager, shared_memory, ipc)

    # All components now share single source of truth
```

---

## Consequences

### Positive
- ✅ **Single Source of Truth**: One authoritative parameter source
- ✅ **NO Hardcoded Defaults**: All parameters come from param_manager only
- ✅ **Live Updates**: Components automatically see changes
- ✅ **Centralized Validation**: Validation logic in one place
- ✅ **Decoupling**: Components depend on manager interface, not structure
- ✅ **Thread Safety**: RLock ensures safe concurrent access
- ✅ **Testability**: Easy to mock ParameterManager in tests
- ✅ **Maintainability**: Clear data flow from source to consumers
- ✅ **Scientific Reproducibility**: No hidden defaults, all config explicit

### Negative
- ⚠️ **Refactoring Effort**: Required updating 8 components
- ⚠️ **Callback Complexity**: Need to handle parameter changes carefully

### Neutral
- 📊 **Performance**: Negligible overhead (single lock acquisition)
- 📊 **Memory**: Minimal increase (callback list storage)

---

## Validation

### Success Criteria (All Met)
- ✅ All components receive ParameterManager via dependency injection
- ✅ No components store frozen parameter copies
- ✅ Parameter updates propagate to all subscribers
- ✅ Thread-safe concurrent parameter access
- ✅ Atomic file writes prevent corruption
- ✅ Validation occurs before updates
- ✅ All tests pass

### Test Cases

**Test 1: Live Parameter Updates**
```python
# Update camera FPS
param_manager.update('camera', {'fps': 120.0})

# Verify camera manager sees change immediately
assert camera_manager.get_fps() == 120.0

# Verify parameter file updated on disk
saved_params = json.load(open('config/isi_parameters.json'))
assert saved_params['camera']['fps'] == 120.0
```

**Test 2: Observer Notifications**
```python
# Track notification
notification_received = False

def callback(params):
    global notification_received
    notification_received = True

param_manager.subscribe('stimulus', callback)
param_manager.update('stimulus', {'bar_width_deg': 25.0})

assert notification_received == True
```

**Test 3: Thread Safety**
```python
# Concurrent parameter access from 10 threads
threads = [
    threading.Thread(target=lambda: param_manager.get('camera', 'fps'))
    for _ in range(10)
]
for t in threads:
    t.start()
for t in threads:
    t.join()

# No exceptions = thread-safe
```

---

## Migration Guide

### For Component Authors

**Before** (Frozen Snapshot):
```python
class MyComponent:
    def __init__(self, my_params: dict):
        self.value = my_params['key']  # Stale forever
```

**ANTI-PATTERN** (Hardcoded Defaults - NEVER DO THIS):
```python
class MyComponent:
    def __init__(self, param_manager: ParameterManager):
        self.param_manager = param_manager
        self.value = 42  # ❌ WRONG! Hardcoded default violates SSoT
```

**After** (Dependency Injection - CORRECT):
```python
class MyComponent:
    def __init__(self, param_manager: ParameterManager):
        self.param_manager = param_manager
        self.param_manager.subscribe('my_group', self._on_params_changed)

        # ✅ CORRECT: No hardcoded defaults
        # Parameters MUST be loaded from param_manager before use
        self.value: Optional[int] = None

    def _on_params_changed(self, params: dict):
        """React to parameter changes."""
        if 'key' in params:
            self.value = params['key']

    def get_value(self) -> int:
        """Always fetch from source of truth."""
        value = self.param_manager.get('my_group', 'key')
        if value is None:
            raise RuntimeError(
                "Parameter 'my_group.key' not configured. "
                "Parameters must be explicitly set in param_manager."
            )
        return value
```

**Key Rules**:
1. **NEVER hardcode parameter defaults** (e.g., `self.value = 42`)
2. **Initialize to None** to indicate "not yet loaded from param_manager"
3. **Validate explicitly** before use, fail with clear error if missing
4. **Always read from param_manager** for current value
5. **Fail loudly** if required parameters not configured

---

## Follow-up Tasks

- [x] Add observer pattern to ParameterManager (2025-10-11)
- [x] Refactor CameraManager (2025-10-11)
- [x] Refactor StimulusGenerator (2025-10-11)
- [x] Refactor AcquisitionManager (2025-10-12)
- [x] Refactor AnalysisPipeline (2025-10-12)
- [x] Update main.py entry point (2025-10-12)
- [x] Add thread safety tests (2025-10-12)
- [x] Document migration guide (2025-10-12)
- [ ] Add parameter validation schema (future)

---

## References

- **Implementation Report**: `docs/archive/2025-10-14/20251012_2350_PARAMETER_MANAGER_REFACTOR_COMPLETE.md`
- **Parameter Updates**: `docs/archive/2025-10-14/20251012_1125_PARAMETER_UPDATE_SUMMARY.md`
- **Related ADRs**:
  - [ADR-001: Backend Modular Architecture](001-backend-modular-architecture.md)
  - [ADR-002: Unified Stimulus Controller](002-unified-stimulus-controller.md)
- **Living Docs**:
  - [Parameter Manager](../components/parameter-manager.md) (complete API reference)
- **Code Locations**:
  - `src/parameters/manager.py:1-300` (ParameterManager implementation)
  - `src/main.py:50-150` (Dependency injection setup)

---

**Document Version**: 1.1
**Last Updated**: 2025-10-15 01:05
**Changes**: Added explicit "NO Hardcoded Defaults" rule and anti-pattern documentation
**Source**: PARAMETER_MANAGER_REFACTOR_COMPLETE.md (2025-10-12 23:50)
