# ADR-001: Backend Modular Architecture

**Status**: Accepted
**Date**: 2025-10-10
**Deciders**: Backend Team
**Related**: [Acquisition System](../components/acquisition-system.md), [Parameter Manager](../components/parameter-manager.md)

---

## Context and Problem Statement

The original backend was organized in a single monolithic `src/isi_control/` directory with 25+ files, making it difficult to:
- Navigate and understand system boundaries
- Test components in isolation
- Modify one subsystem without affecting others
- Onboard new developers

We needed a modular architecture that clearly separates concerns and makes the system more maintainable.

## Decision Drivers

- **Maintainability**: Reduce cognitive load when working on specific subsystems
- **Testability**: Enable isolated testing of components
- **Scalability**: Support future feature additions without increasing complexity
- **Developer Experience**: Make codebase easier to navigate and understand
- **Single Responsibility**: Each module should have one clear purpose

## Options Considered

### Option 1: Keep Monolithic Structure
**Pros**:
- No migration effort required
- All files in one place

**Cons**:
- Difficult to navigate (25+ files in flat structure)
- Unclear boundaries between subsystems
- Hard to test in isolation
- Imports become tangled web

### Option 2: Modular Structure by Domain (SELECTED)
**Pros**:
- Clear separation of concerns
- Each module has well-defined responsibility
- Easier to test in isolation
- Better code organization

**Cons**:
- Requires migration effort
- Need to update all imports

### Option 3: Microservices Architecture
**Pros**:
- Maximum isolation
- Independent deployment

**Cons**:
- Overkill for single-machine application
- Added complexity (IPC, orchestration)
- Performance overhead

---

## Decision Outcome

**Chosen Option**: Option 2 - Modular Structure by Domain

Reorganized `src/isi_control/` into domain-specific modules:

```
src/
├── acquisition/          # Acquisition control and modes
│   ├── manager.py       # AcquisitionManager
│   ├── modes.py         # PreviewMode, RecordMode, PlaybackMode
│   └── unified_stimulus.py  # Stimulus generation and playback
├── camera/              # Camera hardware interface
│   ├── manager.py       # CameraManager
│   └── utils.py         # Calibration, frame processing
├── analysis/            # Data analysis pipeline
│   ├── manager.py       # AnalysisManager
│   ├── pipeline.py      # Retinotopic analysis algorithms
│   └── renderer.py      # Matplotlib figure rendering
├── stimulus/            # Stimulus generation
│   └── generator.py     # ModernGL rendering
├── parameters/          # Configuration management
│   └── manager.py       # ParameterManager (Single Source of Truth)
├── ipc/                 # Inter-process communication
│   └── shared_memory.py # Shared memory streaming
└── main.py              # Application entry point
```

---

## Implementation

### Phase 1: Create New Structure (2025-10-10)
```bash
# Created new module directories
mkdir -p src/{acquisition,camera,analysis,stimulus,parameters,ipc}

# Moved files to appropriate modules
mv src/isi_control/acquisition_manager.py src/acquisition/manager.py
mv src/isi_control/camera_manager.py src/camera/manager.py
mv src/isi_control/analysis_manager.py src/analysis/manager.py
# ... etc
```

### Phase 2: Update Imports (2025-10-10)
```python
# Before (Monolithic)
from isi_control.acquisition_manager import AcquisitionManager
from isi_control.camera_manager import CameraManager

# After (Modular)
from acquisition.manager import AcquisitionManager
from camera.manager import CameraManager
```

### Phase 3: Remove Old Directory (2025-10-10)
```bash
# Deleted old monolithic structure
rm -rf src/isi_control/
```

---

## Consequences

### Positive
- ✅ **Navigation**: Developers can quickly find relevant code
- ✅ **Testing**: Each module can be tested independently
- ✅ **Imports**: Clear module boundaries, no circular dependencies
- ✅ **Onboarding**: New developers understand system structure faster
- ✅ **Maintenance**: Changes localized to specific modules

### Negative
- ⚠️ **Migration Effort**: Required updating ~50 import statements
- ⚠️ **Learning Curve**: Team needs to learn new structure

### Neutral
- 📊 **Module Sizes**: Reasonably balanced (3-5 files per module)
- 📊 **Depth**: Only 2 levels deep (simple to navigate)

---

## Validation

### Success Criteria (All Met)
- ✅ All tests pass after migration
- ✅ No circular import dependencies
- ✅ Each module has clear, documented purpose
- ✅ Import paths follow pattern `{module}.{file}`
- ✅ No `isi_control` references remain in codebase

### Verification Commands
```bash
# Check for old import patterns
grep -r "from isi_control" src/
# Output: (none)

# Verify new structure exists
ls -la src/
# Output: acquisition/ camera/ analysis/ stimulus/ parameters/ ipc/ main.py

# Run test suite
pytest
# Output: All tests pass
```

---

## Follow-up Tasks

- [ ] Update developer onboarding documentation with new structure
- [ ] Create module-specific README files if modules grow > 10 files
- [ ] Consider extracting common utilities into `src/utils/` if duplication appears

---

## References

- **Implementation Report**: `docs/archive/2025-10-14/20251012_2322_BACKEND_ARCHITECTURE_AUDIT.md`
- **Related ADRs**:
  - [ADR-002: Unified Stimulus Controller](002-unified-stimulus-controller.md)
  - [ADR-004: Parameter Manager Refactor](004-parameter-manager-refactor.md)
- **Living Docs**:
  - [Acquisition System](../components/acquisition-system.md)
  - [Parameter Manager](../components/parameter-manager.md)

---

**Document Version**: 1.0
**Last Updated**: 2025-10-14
**Source**: BACKEND_ARCHITECTURE_AUDIT.md (2025-10-12 23:22)
