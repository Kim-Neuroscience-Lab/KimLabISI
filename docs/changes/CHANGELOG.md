# Changelog

**Last Updated**: 2025-10-16 12:25 PDT

> Living document of all significant changes to the ISI Macroscope system. Most recent changes appear first.

---

## 2025-10-16

### Camera Preview Continuous Streaming Fix
**Component**: Backend - Camera & Main
**Type**: Enhancement (Architecture Compliance)
**Timestamp**: 2025-10-16 12:25 PDT
**Files**:
- `apps/backend/src/main.py:2069-2116` (_handle_camera_subscriber_confirmed - added auto-start)
- `apps/backend/src/main.py:875-897` (_stop_preview_mode - removed camera stop)
**Problem**: Camera preview only showed during Preview/Record modes, not during idle state
**Architecture Requirement**: Per docs/components/acquisition-system.md lines 49-58, camera preview should be "always showing when camera connected"
**Fix**:
- Added camera auto-start in `_handle_camera_subscriber_confirmed()` after ZeroMQ handshake
- Removed camera stop logic in `_stop_preview_mode()` to keep camera running continuously
- Camera now provides best-effort continuous preview regardless of acquisition mode state
**Impact**: Camera preview displays continuously when camera is connected (idle, preview, record modes)
**Testing**:
- ✅ Camera auto-starts after backend handshake completes
- ✅ Camera continues streaming during idle state (no acquisition running)
- ✅ Preview mode works with pre-started camera (defensive check prevents restart)
- ✅ Camera continues after preview stops (continuous streaming maintained)
- ✅ Record mode works correctly with pre-started camera
**Architecture Compliance**: Fully compliant with docs/components/acquisition-system.md specification
**Related**: [Fix Details](2025-10-16-1225_camera_preview_continuous_streaming_fix.md)

### Preview/Record Mode Fix - Camera Acquisition State Management
**Component**: Backend - Camera & Acquisition
**Type**: Critical Bug Fix
**Timestamp**: 2025-10-16 12:13 PDT
**Files**:
- `apps/backend/src/main.py:2063-2093` (removed premature camera start)
- `apps/backend/src/main.py:875-896` (added camera cleanup in stop_preview)
**Problem**: Preview and record modes broken with "Acquisition already running" error
**Root Cause**: Camera started during ZeroMQ handshake instead of when user explicitly requests preview/record
**Fix**:
- Removed `camera.start_acquisition()` from `_handle_camera_subscriber_confirmed()`
- Camera now starts when user clicks Preview or Record (via `acquisition.start_acquisition()`)
- Added proper `camera.stop_acquisition()` in `_stop_preview_mode()` handler
**Impact**: Preview and record modes now work correctly, no leaked state between modes
**Testing**:
- ✅ Backend starts without auto-starting camera
- ✅ Preview mode: starts camera → runs sequence → stops camera cleanly
- ✅ Record mode: starts camera → records data → stops camera → saves data
- ✅ Mode switching works cleanly (no "already running" errors)
**Related**: [Fix Details](2025-10-16-1213_preview_record_mode_fix.md)

### Stimulus Library Save/Load with Parameter Validation
**Component**: Stimulus System
**Type**: Feature
**Timestamp**: 2025-10-16 11:00 PDT
**Files**:
- `apps/backend/src/acquisition/unified_stimulus.py` (added save/load methods)
- `apps/backend/src/main.py` (added command handlers)
- `apps/desktop/src/components/viewports/StimulusGenerationViewport.tsx` (added UI controls)
**Added**: Save/load functionality for pre-generated stimulus libraries with strict parameter validation
**Why**: Allow reuse of expensive pre-generation (~30-60s) across sessions, prevent use of stimulus with wrong parameters
**How**:
- HDF5 storage with embedded generation parameters (~2.5-3.2 GB compressed)
- Automatic validation of monitor + stimulus parameters on load
- Detailed error display if parameters don't match (shows which params differ)
- UI buttons: "Load from Disk" (always available) and "Save to Disk" (enabled when library exists)
**Impact**:
- Load time ~10s vs generation time ~30-60s (3-6x faster)
- Scientific integrity protected (cannot load library with wrong parameters)
- Optional feature (existing workflows unaffected)
**Related**: [Component: Stimulus System](../components/stimulus-system.md#library-persistence), [Feature Details](2025-10-16-1100_stimulus_library_save_load_feature.md)

---

## 2025-10-15

### Camera Viewport Rendering Issue - Investigation
**Component**: Electron IPC + Frontend
**Type**: Bug Investigation
**Timestamp**: 2025-10-15 15:25:52 PDT
**Status**: Root Cause Identified - Fix Proposed
**Files**:
- `apps/desktop/src/electron/main.ts:581-586` (race condition in initialization)
- `apps/desktop/src/electron/main.ts:447` (duplicate frame reader init)
**Problem**: Camera frames not displaying in acquisition viewport despite backend successfully capturing and writing to shared memory
**Root Cause**: Race condition - backend starts publishing frames BEFORE frontend initializes shared memory frame readers (ZeroMQ "slow joiner" problem)
**Impact**: 100% reproducible on every startup, blocks critical acquisition workflow
**Proposed Fix**: Initialize shared memory frame readers earlier in Electron startup sequence, before sending `frontend_ready` signal to backend
**Related**: [Audit: Camera Viewport Rendering](../audits/2025-10-15-1525_camera_viewport_rendering_issue.md)

### Unified Logging Architecture
**Component**: Backend + Frontend
**Type**: Architecture
**Timestamp**: 2025-10-15 14:45:00 PDT
**Files**:
- `apps/backend/src/logging_config.py` (root logger enforcement)
- `apps/desktop/src/utils/logger.ts` (default WARN level)
- `apps/desktop/src/main.tsx` (removed 6 console.log statements)
- `apps/desktop/src/components/viewports/StimulusPresentationViewport.tsx` (removed 1 console.log)
**Changed**: Enforced WARN-level logging across entire codebase
**Why**: Console output cluttered with 437 INFO messages + 7 console.log statements, making errors invisible
**Impact**: Clean console output (<10 lines vs 100+ at startup), 100% signal-to-noise ratio
**Statistics**:
- Backend: 437 logger.info() calls automatically silenced (no code refactoring)
- Frontend: 7 console.log() statements removed
- Console output reduction: ~90%
**Related**: [ADR-006: Unified Logging](decisions/006-unified-logging.md), [Logging Architecture](architecture/logging.md)

### Development Mode CLI Implementation
**Component**: Backend + Setup Script
**Type**: Feature
**Timestamp**: 2025-10-15 12:08 PDT (initial), 19:25 PDT (fix applied)
**Files**:
- `setup_and_run.sh` (added --dev-mode flag)
- `apps/backend/src/main.py:2405-2420` (environment variable handling)
- `apps/backend/src/camera/manager.py:581-620` (development mode check)
**Changed**: Added CLI flag for development mode with software timestamp support
**Why**: Allow consumer webcam usage during development without modifying parameters manually
**Impact**: Developers can test with Mac camera using `./setup_and_run.sh --dev-mode`
**Warning**: Development mode NOT suitable for publication data (software timestamps have ~1-2ms jitter)
**Related**: DEV_MODE_CLI_COMPLETE_2025-10-15T19-26.md

---

## 2025-10-14

### SYNC Logging Spam Fix
**Component**: Electron Main Process
**Type**: Bug Fix
**Files**: `apps/desktop/src/electron/main.ts:404-424`
**Changed**: Added filtering for high-frequency SYNC messages (`camera_histogram_update`, `correlation_update`, `acquisition_progress`)
**Why**: Console was flooded with 30-60 messages/sec making errors invisible
**Impact**: Clean console output, easier debugging
**Related**: [Investigation: Critical Integration Issues](investigations/resolved/2025-10/20251014_critical_integration_issues.md)

### Preview Mode Auto-Generation
**Component**: Acquisition Manager
**Type**: Enhancement
**Files**: `apps/backend/src/main.py:796-837`
**Changed**: Added automatic stimulus pre-generation in preview mode
**Why**: Prevent "library not loaded" errors when user clicks Play
**Impact**: Preview mode now works without manual pre-generation step (5-10 second delay on first use)
**Related**: [ADR-002: Unified Stimulus Controller](decisions/002-unified-stimulus-controller.md)

---

## 2025-10-13

### Stimulus Persistence Fix
**Component**: Unified Stimulus Controller
**Type**: Bug Fix
**Files**: `apps/backend/src/acquisition/unified_stimulus.py:89-165`
**Changed**: Fixed library invalidation on parameter changes
**Why**: Library was being cleared unnecessarily, causing repeated 5-10 second pre-generation delays
**Impact**: Parameter changes no longer invalidate pre-generated library
**Related**: [Component: Stimulus System](components/stimulus-system.md#persistence)

---

## 2025-10-12

### VFS Pipeline Fixes - Phase Wrapping
**Component**: Analysis Pipeline
**Type**: Bug Fix
**Files**: `apps/backend/src/analysis/pipeline.py:450-520`
**Changed**: Fixed phase wrapping artifacts in VFS calculation
**Why**: MATLAB compatibility + scientific accuracy (Zhuang et al. 2017)
**Impact**: VFS maps now match reference implementation
**Related**: [Component: Analysis Pipeline](components/analysis-pipeline.md#vfs-calculation)

### VFS Pipeline Fixes - Statistical Filter
**Component**: Analysis Pipeline
**Type**: Bug Fix
**Files**: `apps/backend/src/analysis/pipeline.py:380-448`
**Changed**: Corrected statistical VFS calculation to match MATLAB implementation
**Why**: Previous implementation used incorrect magnitude masking
**Impact**: Statistical VFS now produces correct V1/V2 boundaries
**Related**: [Investigation: VFS Pipeline Fixes](investigations/resolved/2025-10/20251012_vfs_pipeline_fixes.md)

### Direction Mapping Fix
**Component**: Analysis Pipeline
**Type**: Bug Fix
**Files**: `apps/backend/src/analysis/pipeline.py:220-310`
**Changed**: Fixed direction-to-phase mapping (LR=0°, RL=180°, TB=90°, BT=270°)
**Why**: Previous mapping was off by 90°, causing incorrect retinotopic maps
**Impact**: Phase maps now correctly represent visual stimulus positions
**Related**: [Investigation: Direction Mapping](investigations/resolved/2025-10/20251012_direction_mapping_fix.md)

---

## 2025-10-11

### Parameter Manager Refactor
**Component**: Parameter System
**Type**: Refactor
**Files**: `apps/backend/src/parameters/manager.py` (new), removed `isi_control/parameter_manager.py`
**Changed**: Moved parameter manager to dedicated module with cleaner API
**Why**: Better separation of concerns, easier testing, clearer ownership
**Impact**: All backend modules now import from `src.parameters.manager`
**Related**: [ADR-004: Parameter Manager Refactor](decisions/004-parameter-manager-refactor.md)

---

## 2025-10-10

### Unified Stimulus Integration
**Component**: Acquisition System
**Type**: Feature
**Files**: `apps/backend/src/acquisition/unified_stimulus.py` (new)
**Changed**: Created unified controller for stimulus pre-generation and playback
**Why**: Eliminate duplication between preview and record modes
**Impact**: Single source of truth for stimulus, consistent behavior across modes
**Related**: [ADR-002: Unified Stimulus Controller](decisions/002-unified-stimulus-controller.md)

### Backend Architecture Refactor
**Component**: Backend Core
**Type**: Refactor
**Files**: Reorganized `src/isi_control/` → `src/acquisition/`, `src/analysis/`, etc.
**Changed**: Restructured backend into logical modules by domain
**Why**: Improve maintainability, clearer module boundaries
**Impact**: Better code organization, easier navigation
**Related**: [ADR-001: Backend Modular Architecture](decisions/001-backend-modular-architecture.md)

---

## 2025-10-09

### Startup Performance Optimization
**Component**: Backend Initialization
**Type**: Performance
**Files**: `apps/backend/src/main.py:50-150`
**Changed**: Deferred stimulus pre-generation to first use
**Why**: Reduce startup time from 15 seconds to <1 second
**Impact**: Backend starts immediately, pre-generation happens on-demand
**Related**: [Component: Stimulus System](components/stimulus-system.md#pre-generation)

### Backend Rendering for Analysis
**Component**: Analysis System
**Type**: Feature
**Files**: `apps/backend/src/analysis/renderer.py` (new)
**Changed**: Moved matplotlib rendering to backend
**Why**: Preserve float32 precision, avoid browser RGBA conversion
**Impact**: Analysis figures are pre-rendered, frontend displays PNG images
**Related**: [ADR-003: Backend Rendering](decisions/003-backend-rendering.md)

---

## Historical Changes

<details>
<summary>2025-10-08 - Analysis Pipeline Refactor</summary>

**Component**: Analysis System
**Type**: Refactor
**Files**: `apps/backend/src/analysis/pipeline.py`, `apps/backend/src/analysis/manager.py`
**Changed**: Separated analysis computation from result management
**Why**: Better separation of concerns, easier testing
**Impact**: Analysis pipeline is now pure functions, manager handles state

</details>

<details>
<summary>2025-10-07 - Camera-Triggered Acquisition</summary>

**Component**: Acquisition System
**Type**: Feature
**Files**: `apps/backend/src/acquisition/manager.py`, `apps/backend/src/acquisition/modes.py`
**Changed**: Implemented camera-triggered synchronous stimulus generation
**Why**: Ensure perfect frame-to-frame synchronization
**Impact**: Hardware timestamps align with stimulus frames
**Related**: [ADR-001: Camera-Triggered Acquisition](decisions/001-camera-triggered-acquisition.md)

</details>

---

**Changelog Version**: 1.0
**Last Review**: 2025-10-14
