# Backend Refactor Plan - Comprehensive Audit Report

**Date:** 2025-10-10
**Auditor:** Claude Code (Senior Software Architect)
**Plan Document:** `/Users/Adam/KimLabISI/docs/BACKEND_REFACTOR_PLAN.md`
**Current System:** ISI Macroscope - Hardware-in-the-loop scientific imaging system

---

## EXECUTIVE SUMMARY

**VERDICT:** ⚠️ **CONDITIONAL APPROVAL WITH CRITICAL REVISIONS**

The refactor plan successfully eliminates the service locator anti-pattern and establishes explicit dependency injection. However, there are **critical architectural flaws** in the proposed handler registration pattern that will cause runtime failures. The plan also contains several anti-patterns that violate SOLID principles and introduces hidden complexity.

**Risk Level:** HIGH
**Implementation Readiness:** 60%
**Recommended Action:** Fix critical issues before implementation

---

## CRITICAL VIOLATIONS

### 1. **BROKEN HANDLER REGISTRATION PATTERN** ❌

**Location:** Phase 7 (main.py), lines 354-372

**The Problem:**
```python
# From the plan - THIS WILL FAIL AT RUNTIME
for handler in [
    acquisition.handle_start_acquisition,
    acquisition.handle_stop_acquisition,
    # ... other handlers
]:
    from functools import partial
    bound_handler = partial(
        handler,
        acquisition_manager=acquisition_manager,
        analysis_manager=analysis_manager,
        # ... other managers
    )
    registry._handlers[handler._ipc_command_type] = bound_handler
```

**Why This Violates SOLID:**
1. **Open/Closed Violation:** Every new handler requires modifying main.py
2. **Single Responsibility Violation:** main.py must know about ALL handlers AND their dependencies
3. **Dependency Inversion Violation:** High-level composition depends on low-level handler details

**Why This Will FAIL:**
1. The `partial()` approach passes ALL managers to EVERY handler, regardless of what each handler needs
2. Handler signature is `handler(command: Dict, *args, **kwargs)` from @ipc_handler decorator
3. When registry calls `bound_handler(command)`, the partial will inject managers as positional args
4. This breaks the expected signature: handlers expect `command` as first arg, not managers

**Evidence from Current Code:**
```python
# ipc_utils.py (line 46)
def wrapper(command: Dict[str, Any], *args: P.args, **kwargs: P.kwargs) -> Dict[str, Any]:
    # Handler expects command as first positional argument
    result = func(command, *args, **kwargs)
```

```python
# acquisition_ipc_handlers.py (line 18)
@ipc_handler("start_acquisition")
def handle_start_acquisition(command: Dict[str, Any]) -> Dict[str, Any]:
    # Gets services via service_locator.get_services() - no parameters!
    from .service_locator import get_services
    services = get_services()
```

**The handlers don't currently accept manager parameters - they use the service locator!**

**CRITICAL FIX REQUIRED:**
The plan proposes passing managers as parameters, but:
1. Current handlers don't accept these parameters
2. The partial binding approach is fundamentally broken
3. The decorator wrapper signature doesn't support injected dependencies

---

### 2. **HIDDEN SERVICE LOCATOR PATTERN** ❌

**Location:** Throughout the plan

**The Problem:**
The plan claims to eliminate service locator, but handlers still need to access services somehow. The proposed solution (partial application) doesn't actually work, so handlers will likely fall back to:

```python
# This is still a service locator pattern!
@ipc_handler("start_acquisition")
def handle_start_acquisition(command: Dict[str, Any], acquisition_manager: AcquisitionManager) -> Dict[str, Any]:
    # But wait - how does the handler get parameter_manager?
    # It still needs to import it from somewhere!
    from .service_locator import get_services  # STILL HERE!
    param_manager = get_services().parameter_manager
```

**Why This Matters:**
The current handlers access MULTIPLE services (acquisition_manager, parameter_manager, ipc, shared_memory). The partial binding approach only solves one service, not all of them.

**Evidence from Current Code:**
```python
# acquisition_ipc_handlers.py
def handle_start_acquisition(command: Dict[str, Any]) -> Dict[str, Any]:
    from .service_locator import get_services
    services = get_services()
    param_manager = services.parameter_manager  # ← Need this
    camera_params = param_manager.get_parameter_group("camera")  # ← And this
    manager = get_acquisition_manager()  # ← And this
    return manager.start_acquisition(acq_params, param_manager=param_manager)
```

Each handler needs access to 2-4 different services. The plan doesn't address this.

---

### 3. **DEPENDENCY INVERSION VIOLATION** ❌

**Location:** Phase 6 (IPC Handlers), lines 276-299

**The Problem:**
```python
# ipc/handlers/acquisition.py - FROM THE PLAN
@ipc_handler("start_acquisition")
def handle_start_acquisition(
    command: dict,
    acquisition_manager: AcquisitionManager,  # ← Direct dependency
    parameter_manager: ParameterManager       # ← Direct dependency
) -> dict:
    params = parameter_manager.get_group("acquisition")
    return acquisition_manager.start_acquisition(params)
```

**What's Wrong:**
1. Handler depends on CONCRETE classes (AcquisitionManager, ParameterManager)
2. No abstraction layer - violates Dependency Inversion Principle
3. Cannot mock for testing without actual class instances
4. Tight coupling between IPC layer and domain layer

**Current Code Actually Has Better Separation:**
```python
# Current code (acquisition_ipc_handlers.py)
def handle_start_acquisition(command: Dict[str, Any]) -> Dict[str, Any]:
    from .service_locator import get_services
    services = get_services()  # ← Runtime lookup, can be mocked
    param_manager = services.parameter_manager
    manager = get_acquisition_manager()
    return manager.start_acquisition(...)
```

The current approach (despite being a service locator) is actually MORE testable because:
- `get_services()` can be mocked to return test doubles
- Handlers don't depend on concrete manager types
- No compile-time coupling to manager implementations

**The Proposed Solution Makes Testing HARDER.**

---

### 4. **GLOBAL STATE IN DISGUISE** ⚠️

**Location:** Phase 2 (camera/manager.py), line 1052

**The Problem:**
```python
# From the plan and current code
_acquisition_orchestrator = AcquisitionOrchestrator()

def get_acquisition_manager() -> AcquisitionOrchestrator:
    return _acquisition_orchestrator
```

**This is STILL a global singleton!** The plan doesn't fix this - it just moves it to a different file.

**Why This Violates Principles:**
1. **Hidden Global State:** Module-level singleton
2. **Cannot Test:** Can't create isolated instances for testing
3. **Shared Mutable State:** All code shares same instance
4. **Not Thread-Safe:** No synchronization on global access

**Same pattern exists for:**
- `camera_manager` (line 1052 in camera_manager.py)
- `_stimulus_generator` (line 503 in stimulus_manager.py)
- `_backend_instance` (line 84 in main.py)

**The refactor plan doesn't address these globals at all.**

---

### 5. **CIRCULAR DEPENDENCY RISK** ⚠️

**Location:** main.py dependency graph

**The Problem:**
```python
# main.py creates these dependencies:
acquisition_manager = AcquisitionManager(
    camera_manager=camera_manager,  # ← CameraManager needs AcquisitionManager
    stimulus_generator=stimulus_generator,
    state_coordinator=state_coordinator,
    sync_tracker=sync_tracker
)

# But camera_manager.py also imports from acquisition:
from .acquisition_manager import get_acquisition_manager
```

**Current Evidence of Circular Dependencies:**
```python
# camera_manager.py (line 297-298)
from .camera_manager import camera_manager  # global instance
camera_manager.set_data_recorder(self.data_recorder)  # acquisition sets camera's recorder
```

**Circular Flow:**
1. main.py → creates camera_manager
2. main.py → creates acquisition_manager (needs camera_manager)
3. acquisition_manager → accesses global camera_manager (circular!)
4. camera_manager → imports acquisition_manager (circular!)

**The plan doesn't break these circular dependencies - it just moves them around.**

---

## ARCHITECTURAL ISSUES

### 6. **MISSING ABSTRACTION LAYER** ⚠️

**Problem:** No interfaces or protocols defined for managers

**Current State:**
- Direct coupling between handlers and concrete managers
- No way to swap implementations
- Difficult to add new backends (e.g., simulated camera)

**Recommendation:**
```python
# Should define protocols:
from typing import Protocol

class IAcquisitionManager(Protocol):
    def start_acquisition(self, params: dict) -> dict: ...
    def stop_acquisition(self) -> dict: ...
    def get_status(self) -> dict: ...

# Handlers depend on protocols, not concrete classes
def handle_start_acquisition(
    command: dict,
    acquisition: IAcquisitionManager  # ← Abstraction
) -> dict:
    return acquisition.start_acquisition(...)
```

**Benefits:**
- Dependency Inversion Principle satisfied
- Easy to mock for testing
- Can swap implementations without changing handlers

---

### 7. **OVERLY COMPLEX HANDLER REGISTRATION** ⚠️

**Problem:** The auto-discovery pattern adds unnecessary complexity

**From the Plan:**
```python
# registry.py - lines 116-128
def register_from_module(self, module) -> None:
    """Scan module for @ipc_handler decorated functions."""
    for name in dir(module):
        obj = getattr(module, name)
        if callable(obj) and hasattr(obj, '_ipc_command_type'):
            self._handlers[obj._ipc_command_type] = obj
```

**Problems:**
1. **Magic behavior:** Registration happens via side effects
2. **Hidden dependencies:** No explicit declaration of what's registered
3. **Debugging nightmare:** Hard to trace which handlers are active
4. **Order-dependent:** Module import order affects registration

**Better Approach:**
```python
# Explicit registration - clear and simple
registry = CommandRegistry()
registry.register("start_acquisition", handle_start_acquisition)
registry.register("stop_acquisition", handle_stop_acquisition)
# etc.
```

**Benefits:**
- Explicit is better than implicit (Zen of Python)
- Easy to see what's registered
- Order-independent
- Simple to debug

---

### 8. **5-DIRECTORY STRUCTURE NOT JUSTIFIED** ⚠️

**Problem:** The proposed structure may be over-engineered

**Proposed Structure:**
```
apps/backend/src/
├── acquisition/     # 6 files
├── analysis/        # 4 files
├── camera/          # 2 files
├── stimulus/        # 2 files
├── ipc/            # 6 files + handlers/
```

**Issues:**
1. **Feature Envy:** IPC handlers separated from domain logic
2. **Scattered Concerns:** Single feature split across multiple directories
3. **Navigation Overhead:** More directories = more cognitive load

**Current Structure:**
```
isi_control/
└── *.py (31 files in one directory)
```

**Actually Better For:**
- Quick navigation
- Understanding module relationships
- Seeing the whole system at once

**Alternative Structure (Better Balance):**
```
apps/backend/src/
├── domain/
│   ├── acquisition.py
│   ├── analysis.py
│   ├── camera.py
│   └── stimulus.py
├── infrastructure/
│   ├── ipc.py
│   ├── shared_memory.py
│   └── config.py
└── main.py
```

**Benefits:**
- Clear separation (domain vs infrastructure)
- Related code stays together
- Less navigation overhead
- Easier to understand dependencies

---

## CODE QUALITY ISSUES

### 9. **INCONSISTENT ERROR HANDLING** ⚠️

**Current Pattern (Good):**
```python
# ipc_utils.py
@ipc_handler(command_type: str):
    def wrapper(command: dict) -> dict:
        try:
            result = func(command)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
```

**Proposed Pattern (Broken):**
The plan doesn't specify how partial-bound handlers handle errors. This will likely break the decorator's try/catch.

---

### 10. **PARAMETER PASSING INCONSISTENCY** ⚠️

**Problem:** Some managers get dependencies via __init__, others via property assignment

**From main.py (current):**
```python
# Method 1: Constructor injection
acquisition_manager = AcquisitionManager(
    synchronization_tracker=sync_tracker
)

# Method 2: Property assignment (lines 658-663)
acquisition_manager.synchronization_tracker = synchronization_tracker
acquisition_manager.state_coordinator = acquisition_state
acquisition_manager.stimulus_controller = stimulus_controller
```

**This is inconsistent and error-prone:**
1. Some dependencies injected via __init__
2. Others set as properties after construction
3. No clear pattern for which approach to use
4. Risk of using manager before all dependencies set

**Correct Approach:**
```python
# All dependencies via constructor
acquisition_manager = AcquisitionManager(
    synchronization_tracker=sync_tracker,
    state_coordinator=acquisition_state,
    stimulus_controller=stimulus_controller,
    camera_triggered_stimulus=camera_triggered_stimulus,
    playback_controller=playback_controller
)
```

---

## TESTABILITY CONCERNS

### 11. **HANDLERS CANNOT BE UNIT TESTED** ❌

**Problem:** Handlers require full manager instances to test

**Proposed Pattern:**
```python
def handle_start_acquisition(
    command: dict,
    acquisition_manager: AcquisitionManager,
    parameter_manager: ParameterManager
) -> dict:
    params = parameter_manager.get_group("acquisition")
    return acquisition_manager.start_acquisition(params)
```

**To Test This Handler:**
1. Must instantiate real AcquisitionManager
2. Must instantiate real ParameterManager
3. AcquisitionManager needs camera_manager, stimulus, state, sync tracker
4. Now testing 10+ classes just to test one handler

**This is an INTEGRATION test, not a UNIT test.**

**Better Approach (with protocols):**
```python
def handle_start_acquisition(
    command: dict,
    acquisition: IAcquisitionManager,
    params: IParameterManager
) -> dict:
    # Can mock both interfaces easily
    ...
```

---

### 12. **NO TESTING STRATEGY IN PLAN** ⚠️

**Phase 8 mentions testing but provides no details:**
- How to mock dependencies?
- How to test handlers in isolation?
- How to test main.py's composition logic?

**Missing:**
- Test fixture setup
- Mocking strategy
- Integration test approach
- Dependency injection for tests

---

## PERFORMANCE CONCERNS

### 13. **REAL-TIME IMPLICATIONS NOT ADDRESSED** ⚠️

**This is a hardware-in-the-loop system with real-time constraints:**
- Camera capture at 30 FPS
- Stimulus generation triggered by camera frames
- Scientific accuracy requires precise timing

**The Plan Doesn't Address:**
1. Threading model in new architecture
2. Impact of dependency passing on performance
3. Memory allocation patterns
4. Lock contention in shared managers

**Current Code Has Real-Time Concerns:**
```python
# camera_manager.py (line 614-801)
def _acquisition_loop(self):
    while not self.stop_acquisition_event.is_set():
        frame = self.capture_frame()  # CRITICAL PATH
        if self.camera_triggered_stimulus:
            stimulus_frame = self.camera_triggered_stimulus.generate_next_frame()
        # Must complete in 1/30s = 33ms for 30 FPS
```

**The refactor plan doesn't analyze if explicit parameter passing adds latency.**

---

## COMPARISON TO PREVIOUS PLAN

### What Was Removed (Good):
- ✅ Provider/DependentProvider classes (overly complex)
- ✅ ISIContainer (DI container was overkill)
- ✅ Lazy loading machinery (unnecessary)

### What Was Kept (Problematic):
- ❌ Module-level global singletons
- ❌ Property-based dependency injection
- ❌ Circular dependencies between modules
- ❌ Direct coupling to concrete classes

### What's New (Mixed):
- ✅ Explicit parameter passing (good idea)
- ⚠️ Auto-discovery pattern (adds complexity)
- ❌ Partial application for handlers (broken design)
- ⚠️ 5-directory structure (may be over-engineered)

---

## EFFORT ESTIMATE ANALYSIS

**Plan Estimates:** 44-60 hours

### Realistic Breakdown:

| Phase | Plan Estimate | Actual Estimate | Issues |
|-------|--------------|-----------------|---------|
| Phase 1: Foundation | 8-10h | 8-10h | ✓ Reasonable |
| Phase 2: Camera | 4-6h | 8-10h | Must fix globals, circular deps |
| Phase 3: Stimulus | 4-6h | 6-8h | Must fix singleton pattern |
| Phase 4: Acquisition | 8-10h | 12-16h | Most complex, circular deps |
| Phase 5: Analysis | 4-6h | 6-8h | ✓ Mostly straightforward |
| Phase 6: IPC Handlers | 4-6h | **16-20h** | Must redesign handler pattern |
| Phase 7: Main | 6-8h | **12-16h** | Must fix composition, registration |
| Phase 8: Testing | 6-8h | **20-24h** | Must add mocking strategy |
| **TOTAL** | **44-60h** | **88-112h** | **Almost DOUBLE** |

**Key Underestimates:**
1. **Handler registration redesign:** +10h (current design is broken)
2. **Fixing circular dependencies:** +8h (not addressed in plan)
3. **Testing infrastructure:** +12h (no strategy in plan)
4. **Debugging and integration:** +12h (always underestimated)

---

## CRITICAL ISSUES SUMMARY

### BLOCKERS (Must Fix Before Implementation):
1. ❌ **Handler registration pattern is fundamentally broken**
   - Partial application won't work with current decorator
   - Handlers don't accept manager parameters currently
   - Will cause runtime failures

2. ❌ **Service locator not actually eliminated**
   - Handlers still need multiple services
   - No solution for accessing all dependencies
   - Just moves the problem around

3. ❌ **Dependency Inversion violated**
   - Direct coupling to concrete classes
   - Harder to test than current code
   - No abstraction layer

### MAJOR CONCERNS (Should Fix):
4. ⚠️ **Global singletons everywhere**
   - Not addressed by refactor
   - Still have hidden global state
   - Testing will be difficult

5. ⚠️ **Circular dependencies persist**
   - main.py ↔ camera_manager ↔ acquisition_manager
   - Not fixed by refactor
   - Will cause import issues

6. ⚠️ **Testing strategy missing**
   - How to mock dependencies?
   - How to unit test handlers?
   - No fixtures defined

### MINOR ISSUES (Nice to Fix):
7. ⚠️ Directory structure may be over-engineered
8. ⚠️ Auto-discovery adds complexity
9. ⚠️ Inconsistent dependency injection patterns

---

## RECOMMENDATIONS

### IMMEDIATE FIXES (Before Implementation):

#### 1. Fix Handler Registration Pattern

**Don't use partial application. Instead:**

```python
# Option A: Handler takes registry as dependency
@ipc_handler("start_acquisition")
def handle_start_acquisition(command: dict) -> dict:
    # Handler closure captures dependencies
    services = get_registry()  # From composition root
    acquisition = services.acquisition_manager
    params = services.parameter_manager.get_group("acquisition")
    return acquisition.start_acquisition(params)

# Composition root (main.py)
def main():
    # Create all services
    registry = ServiceRegistry(
        acquisition=acquisition_manager,
        parameter=parameter_manager,
        # ...
    )

    # Make registry accessible
    set_registry(registry)

    # Register handlers (they capture registry via closure)
    command_registry = CommandRegistry()
    command_registry.register_from_module(acquisition_handlers)
```

**OR Option B: Use a proper DI container (but you said no frameworks):**

```python
# Option B: Explicit handler factory
def create_acquisition_handlers(
    acquisition: AcquisitionManager,
    params: ParameterManager
):
    @ipc_handler("start_acquisition")
    def handle_start_acquisition(command: dict) -> dict:
        # Closure captures dependencies
        acq_params = params.get_group("acquisition")
        return acquisition.start_acquisition(acq_params)

    return [handle_start_acquisition, ...]

# In main.py
handlers = create_acquisition_handlers(
    acquisition=acquisition_manager,
    params=parameter_manager
)
for handler in handlers:
    registry.register_handler(handler)
```

#### 2. Define Protocols/Interfaces

```python
# domain/protocols.py
from typing import Protocol, Dict, Any

class IAcquisitionManager(Protocol):
    def start_acquisition(self, params: Dict) -> Dict[str, Any]: ...
    def stop_acquisition(self) -> Dict[str, Any]: ...

class IParameterManager(Protocol):
    def get_group(self, name: str) -> Dict[str, Any]: ...
    def update_group(self, name: str, params: Dict) -> None: ...

# Now handlers depend on protocols, not concrete types
```

#### 3. Eliminate Global Singletons

```python
# Instead of module-level globals:
# _camera_manager = CameraManager()  # ❌ BAD

# Composition root creates and wires everything:
def main():
    camera = CameraManager(...)
    acquisition = AcquisitionManager(camera=camera)
    # Pass everything explicitly, no globals
```

#### 4. Break Circular Dependencies

```python
# Current: main.py → camera_manager → acquisition_manager → camera_manager ❌

# Fixed: Use dependency injection, not imports
class AcquisitionManager:
    def __init__(self, camera: CameraManager):  # Injected, not imported
        self.camera = camera

class CameraManager:
    def __init__(self):
        self.data_recorder = None  # Set later by acquisition

    def set_recorder(self, recorder):
        self.data_recorder = recorder
```

#### 5. Add Testing Strategy

```python
# tests/conftest.py
@pytest.fixture
def mock_camera():
    return Mock(spec=CameraManager)

@pytest.fixture
def mock_params():
    return Mock(spec=ParameterManager)

@pytest.fixture
def acquisition_manager(mock_camera, mock_params):
    return AcquisitionManager(
        camera=mock_camera,
        params=mock_params
    )

# tests/test_handlers.py
def test_start_acquisition_handler(acquisition_manager, mock_params):
    handler = create_acquisition_handlers(acquisition_manager, mock_params)
    result = handler.handle_start_acquisition({"type": "start_acquisition"})
    assert result["success"] == True
```

---

### REVISED IMPLEMENTATION PLAN

#### Phase 0: Architecture Fixes (NEW - 16-20 hours)
1. Define Protocol interfaces for all managers
2. Design handler registration without partial application
3. Eliminate global singletons
4. Map out and break circular dependencies
5. Create testing strategy document

#### Phase 1: Foundation (8-10 hours)
- Continue as planned with IPC, config
- Add protocol definitions

#### Phase 2-5: Domain Modules (24-32 hours)
- Implement with constructor injection only
- No property-based DI
- No module-level globals
- Follow protocols for interfaces

#### Phase 6: IPC Handlers (16-20 hours)
- Use revised handler registration pattern
- Implement handler factories with closures
- No partial application

#### Phase 7: Main/Composition Root (12-16 hours)
- Explicit dependency wiring
- No hidden service lookups
- Clear initialization order

#### Phase 8: Testing (20-24 hours)
- Unit tests with mocked protocols
- Integration tests with real managers
- Fixture library
- CI/CD integration

**TOTAL REVISED ESTIMATE: 96-122 hours (vs. 44-60 planned)**

---

## ALTERNATIVE APPROACH

If the goal is truly **"Simple, Explicit, Testable"**, consider this leaner approach:

### Keep It Simple (KISS)

```python
# 1. Everything in main.py composition root
def main():
    # Create infrastructure
    config = AppConfig.load()
    ipc = MultiChannelIPC(config.ipc)
    shared_mem = SharedMemoryService(config.shm)
    params = ParameterManager(config.params)

    # Create domain services
    camera = CameraManager()
    stimulus = StimulusGenerator(params)
    acquisition = AcquisitionManager(camera, stimulus, params)
    analysis = AnalysisManager(params)

    # Create handler dispatcher
    handlers = {
        "start_acquisition": lambda cmd: acquisition.start_acquisition(
            params.get_group("acquisition")
        ),
        "stop_acquisition": lambda cmd: acquisition.stop_acquisition(),
        "detect_cameras": lambda cmd: {"cameras": camera.detect()},
        # ... explicit mapping, no magic
    }

    # Event loop
    while True:
        command = ipc.receive()
        handler = handlers.get(command["type"])
        if handler:
            response = handler(command)
            ipc.send(response)

# 2. No decorators, no auto-discovery, no complexity
# 3. Everything explicit and visible
# 4. Easy to test: just pass mock managers to lambdas
```

**Benefits:**
- ✅ No service locator
- ✅ No global state
- ✅ No magic registration
- ✅ No circular dependencies
- ✅ Trivial to test
- ✅ Can understand entire system in one file
- ✅ No hidden complexity

**Drawbacks:**
- More code in main.py (but that's okay - it's the composition root!)
- Less "clever" (but simpler is better)

---

## FINAL VERDICT

### Overall Assessment: ⚠️ CONDITIONAL APPROVAL

**The Good:**
- ✅ Eliminates service locator pattern (in principle)
- ✅ Establishes explicit dependency injection
- ✅ Removes over-engineered Provider pattern
- ✅ Clear phased approach

**The Bad:**
- ❌ Handler registration pattern is fundamentally broken
- ❌ Service locator not fully eliminated (handlers need multiple services)
- ❌ Direct coupling violates Dependency Inversion
- ⚠️ Global singletons persist
- ⚠️ Circular dependencies not addressed
- ⚠️ No testing strategy

**The Ugly:**
- **Implementation will fail** without fixing handler registration
- **Effort underestimated by 50-100%** (44-60h → 88-112h)
- **More complex than current code** in some areas
- **Harder to test** than current service locator (ironically)

---

## REQUIRED ACTIONS BEFORE IMPLEMENTATION

### MUST FIX (Blockers):
1. ✋ **STOP** - Current handler registration won't work
2. 🔧 **REDESIGN** handler dependency injection (use closures or factory pattern)
3. 📋 **DEFINE** Protocol interfaces for all managers
4. 🔍 **IDENTIFY** and break all circular dependencies
5. 📝 **DOCUMENT** testing strategy with mock examples

### SHOULD FIX (Important):
6. 🧹 **ELIMINATE** all module-level global singletons
7. 🏗️ **STANDARDIZE** dependency injection (constructor-only)
8. 📐 **SIMPLIFY** directory structure (consider 2-3 dirs, not 5)
9. 🎯 **EXPLICIT** handler registration (no auto-discovery magic)

### COULD FIX (Nice to have):
10. 📊 **ANALYZE** real-time performance implications
11. 🔄 **CONSIDER** simpler alternative (KISS approach above)
12. 📚 **DOCUMENT** architectural decisions (ADRs)

---

## RECOMMENDATION

### Path Forward:

**Option 1: Fix and Proceed (Recommended)**
1. Address all MUST FIX items above
2. Implement Phases 0-1 as proof of concept
3. Validate handler pattern works with real code
4. Proceed with full implementation
5. **Budget 90-120 hours, not 44-60**

**Option 2: Simplified Approach (Alternative)**
1. Use KISS pattern (single composition root)
2. Explicit handler mapping (no decorators)
3. Constructor injection only
4. Protocol-based abstractions
5. **Budget 40-60 hours total**

**Option 3: Incremental Refactor (Conservative)**
1. Keep current service locator initially
2. Convert one subsystem at a time
3. Learn from each conversion
4. Adjust approach based on findings
5. **Budget 60-80 hours total**

---

## APPENDIX: CODE EXAMPLES

### Example: Correct Handler Pattern with Closures

```python
# ipc/handlers/acquisition.py
from typing import Dict, Any, Callable
from ..domain.protocols import IAcquisitionManager, IParameterManager

def create_acquisition_handlers(
    acquisition: IAcquisitionManager,
    parameters: IParameterManager
) -> Dict[str, Callable]:
    """
    Factory function creates handlers with injected dependencies via closures.
    No partial application, no magic, just captured variables.
    """

    def handle_start(command: Dict[str, Any]) -> Dict[str, Any]:
        # Closure captures acquisition and parameters
        params = parameters.get_group("acquisition")
        camera_params = parameters.get_group("camera")
        params["camera_fps"] = camera_params["camera_fps"]
        return acquisition.start_acquisition(params)

    def handle_stop(command: Dict[str, Any]) -> Dict[str, Any]:
        return acquisition.stop_acquisition()

    def handle_status(command: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": acquisition.get_status()}

    # Return mapping of command types to handlers
    return {
        "start_acquisition": handle_start,
        "stop_acquisition": handle_stop,
        "get_acquisition_status": handle_status,
    }

# main.py
def main():
    # Create dependencies
    acquisition_mgr = AcquisitionManager(...)
    param_mgr = ParameterManager(...)

    # Create handlers with dependencies captured via closure
    acq_handlers = create_acquisition_handlers(acquisition_mgr, param_mgr)

    # Register in command registry
    registry = CommandRegistry()
    for cmd_type, handler in acq_handlers.items():
        registry.register(cmd_type, handler)

    # IPC loop
    while True:
        command = ipc.receive()
        response = registry.handle(command)
        ipc.send(response)
```

### Example: Protocol-Based Testing

```python
# domain/protocols.py
from typing import Protocol, Dict, Any

class IAcquisitionManager(Protocol):
    def start_acquisition(self, params: Dict[str, Any]) -> Dict[str, Any]: ...
    def stop_acquisition(self) -> Dict[str, Any]: ...
    def get_status(self) -> Dict[str, Any]: ...

# tests/test_acquisition_handlers.py
import pytest
from unittest.mock import Mock
from ipc.handlers.acquisition import create_acquisition_handlers

def test_start_acquisition_handler():
    # Arrange: Create mocks that satisfy protocol
    mock_acquisition = Mock(spec=IAcquisitionManager)
    mock_acquisition.start_acquisition.return_value = {
        "success": True,
        "message": "Started"
    }

    mock_params = Mock()
    mock_params.get_group.return_value = {
        "baseline_sec": 5,
        "cycles": 10
    }

    # Act: Create handlers with mocked dependencies
    handlers = create_acquisition_handlers(mock_acquisition, mock_params)
    result = handlers["start_acquisition"]({"type": "start_acquisition"})

    # Assert
    assert result["success"] == True
    mock_acquisition.start_acquisition.assert_called_once()
    mock_params.get_group.assert_called_with("acquisition")
```

---

## CONCLUSION

The refactor plan has the right goals but critical implementation flaws. The handler registration pattern is fundamentally broken and will cause runtime failures. The effort is underestimated by 50-100%. Several anti-patterns (global singletons, circular dependencies) are not addressed.

**Recommendation: DO NOT PROCEED** with current plan. Fix critical issues first, then re-evaluate.

**If you want truly simple, explicit, testable code: Consider the KISS alternative approach.**

**Estimated Real Effort: 90-120 hours** (not 44-60 as planned)

---

*End of Audit Report*
