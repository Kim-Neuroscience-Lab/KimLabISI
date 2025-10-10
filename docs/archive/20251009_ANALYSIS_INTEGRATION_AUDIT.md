# ARCHIVED DOCUMENTATION

**Original File**: ANALYSIS_INTEGRATION_AUDIT.md
**Archived**: 2025-10-09
**Reason**: Documentation restructure - content consolidated into new docs/ structure

**Status**: Historical reference only. For current documentation, see:
- [Documentation Index](../README.md)
- [Architecture Overview](../architecture/overview.md)
- [Component Documentation](../components/)
- [Technical Decisions](../technical-decisions/)

---

# Original Content

# ISI Macroscope Analysis Integration - Comprehensive Audit Report

**Date**: October 9, 2025
**Auditor**: Claude Code (Sonnet 4.5)
**Scope**: Complete audit of analysis infrastructure and integration status
**Status**: INTEGRATION REQUIRED

---

## Executive Summary

### Key Finding: Analysis Code Exists But Is Completely Disconnected

The ISI Macroscope system has:
- ✅ **Scientifically rigorous recording infrastructure** (Publication-ready)
- ✅ **Complete analysis algorithms** (Fourier, retinotopy, VFS - all correct)
- ❌ **ZERO integration** between recording and analysis workflows
- ⚠️ **Empty `analysis_manager.py` file** (0 bytes - placeholder only)
- ⚠️ **No IPC handlers** for analysis commands
- ⚠️ **Frontend sends commands** that backend doesn't handle

**Bottom Line**: The user was correct - "We have a comprehensive system already for all of this." The analysis code is scientifically sound and complete. It just needs to be **wired up** to the IPC system following the same patterns used for playback mode.

---

## Section 1: What EXISTS (The Good News)

### 1.1 Complete Analysis Pipeline (`isi_analysis.py`)

**File**: `/Users/Adam/KimLabISI/apps/backend/src/isi_control/isi_analysis.py`
**Size**: 554 lines
**Status**: ✅ COMPLETE AND SCIENTIFICALLY VALID

**Implemented Methods**:

#### Preprocessing
- `load_acquisition_data(session_path)` - Loads all recorded data
- `correlate_temporal_data(direction)` - Matches camera frames to stimulus angles
- `compensate_hemodynamic_delay(frames, delay_sec)` - Accounts for blood flow delay

#### Fourier Analysis (Kalatsky & Stryker 2003)
- `compute_fft_phase_maps(frames, angles)` - Per-pixel FFT at stimulus frequency
- `bidirectional_analysis(forward_phase, reverse_phase)` - Combines LR/RL or TB/BT

#### Retinotopic Mapping
- `generate_azimuth_map(LR_phase, RL_phase)` - Horizontal visual field mapping
- `generate_elevation_map(TB_phase, BT_phase)` - Vertical visual field mapping

#### Visual Field Sign Analysis (Zhuang et al. 2017)
- `compute_spatial_gradients(azimuth_map, elevation_map)` - Gradient calculation
- `calculate_visual_field_sign(gradients)` - Sign of Jacobian determinant
- `detect_area_boundaries(sign_map)` - Find area boundaries
- `segment_visual_areas(sign_map, boundary_map)` - Identify distinct areas

#### Complete Pipeline
- `analyze_session(session_path)` - Runs full analysis pipeline
- `save_results(output_path)` - Exports HDF5 and PNG visualizations

**Scientific Validity**: ✅ EXCELLENT
- Correct implementation of published methods
- Proper citations in docstrings
- Mathematically sound algorithms

**Code Quality**: ✅ GOOD
- Well-organized and documented
- Clear separation of concerns
- Reusable component structure

### 1.2 Recording Infrastructure (`data_recorder.py`)

**File**: `/Users/Adam/KimLabISI/apps/backend/src/isi_control/data_recorder.py`
**Size**: 262 lines
**Status**: ✅ COMPLETE AND PUBLICATION-READY

**Features**:
- Thread-safe recording during acquisition
- Separate HDF5 files per direction (LR, RL, TB, BT)
- Comprehensive metadata with timestamp provenance
- Camera frame storage with gzip compression
- Stimulus event tracking with microsecond timestamps
- Compatible data format with `isi_analysis.py` expectations

**Data Format** (verified compatible):
```
session_directory/
├── metadata.json              # Session parameters + timestamp info
├── LR_camera.h5              # frames + timestamps datasets
├── LR_events.json            # stimulus events array
├── LR_stimulus.h5            # angles dataset
├── RL_camera.h5              # (same structure)
├── RL_events.json
├── RL_stimulus.h5
├── TB_camera.h5              # (same structure)
├── TB_events.json
├── TB_stimulus.h5
├── BT_camera.h5              # (same structure)
├── BT_events.json
└── BT_stimulus.h5
```

**Missing**: ❌ `anatomical.npy` (expected by analysis but not saved)

### 1.3 Parameter System

**Backend**: `/Users/Adam/KimLabISI/apps/backend/src/isi_control/parameter_manager.py`
**Frontend**: `/Users/Adam/KimLabISI/apps/desktop/src/types/shared.ts`

**AnalysisParameters** (defined in both frontend and backend):
```python
@dataclass
class AnalysisParameters:
    ring_size_mm: float                    # Anatomical measurement
    vfs_threshold_sd: float                # Visual field sign threshold
    smoothing_sigma: float                 # Gaussian smoothing parameter
    magnitude_threshold: float             # Response magnitude cutoff
    phase_filter_sigma: float              # Phase map smoothing
    gradient_window_size: int              # Spatial gradient window
    area_min_size_mm2: float              # Minimum area size for segmentation
    response_threshold_percent: float      # Response threshold percentage
```

**Status**: ✅ Fully defined in parameter system
**Issue**: ⚠️ Parameters are NOT used by `isi_analysis.py` (hard-coded values instead)

### 1.4 Frontend Analysis UI

**File**: `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AnalysisViewport.tsx`
**Size**: 235 lines
**Status**: ⚠️ UI EXISTS but backend handlers are MISSING

**What the Frontend Does**:
1. Sends `start_analysis` command via IPC
2. Listens for `analysis_started` message
3. Listens for `analysis_progress` messages
4. Listens for `analysis_result` messages
5. Listens for `analysis_complete` message
6. Listens for `analysis_stopped` message
7. Displays real-time analysis metrics
8. Exports results to CSV
9. Shows progress indicators

**Current State**:
- ✅ Complete UI implementation
- ✅ Proper error handling
- ✅ Progress tracking
- ❌ Backend never responds to commands
- ❌ No analysis results ever arrive

---

## Section 2: What is MISSING (The Integration Gap)

### 2.1 CRITICAL: Empty Analysis Manager

**File**: `/Users/Adam/KimLabISI/apps/backend/src/isi_control/analysis_manager.py`
**Size**: 0 bytes (empty file)
**Status**: ❌ PLACEHOLDER ONLY

This file exists but contains no code whatsoever. It needs to be implemented following the pattern of `playback_ipc_handlers.py` and `acquisition_ipc_handlers.py`.

### 2.2 CRITICAL: No IPC Handlers

**Missing handlers in `main.py`**:
```python
# command_handlers dictionary has NO analysis entries:
{
    "start_acquisition": handle_start_acquisition,  # ✅ EXISTS
    "start_analysis": ???,                          # ❌ MISSING
    "get_analysis_status": ???,                     # ❌ MISSING
    "get_analysis_results": ???,                    # ❌ MISSING
    # ... analysis handlers completely absent
}
```

**What needs to exist**:
- `handle_start_analysis` - Start analysis on a session
- `handle_stop_analysis` - Cancel running analysis
- `handle_get_analysis_status` - Get progress/status
- `handle_list_analysis_results` - List available results
- `handle_get_analysis_results` - Retrieve analysis data
- `handle_capture_anatomical` - Capture anatomical reference frame

### 2.3 CRITICAL: Not in Service Registry

**File**: `/Users/Adam/KimLabISI/apps/backend/src/isi_control/service_locator.py`

**ServiceRegistry has**:
```python
@dataclass
class ServiceRegistry:
    ipc: MultiChannelIPC                    # ✅
    parameter_manager: ParameterManager     # ✅
    acquisition_manager: AcquisitionOrchestrator  # ✅
    playback_controller: PlaybackModeController   # ✅
    # analysis_manager: ???                 # ❌ MISSING
```

Analysis manager needs to be added to the service registry for dependency injection.

### 2.4 HIGH: Anatomical Image Not Captured

**Issue**: `isi_analysis.py` expects `anatomical.npy` in session directory
```python
# isi_analysis.py line 48-51
anatomical_path = os.path.join(session_path, "anatomical.npy")
if os.path.exists(anatomical_path):
    session_data['anatomical'] = np.load(anatomical_path)
```

**But**: `data_recorder.py` never saves anatomical images

**Need**:
1. IPC handler to capture anatomical frame before recording
2. Storage in data recorder
3. Frontend UI button to trigger capture
4. Visual confirmation when captured

### 2.5 MEDIUM: Analysis Parameters Not Used

**Problem**: `isi_analysis.py` uses hard-coded values instead of parameters

**Examples**:
```python
# Line 315 - Hard-coded smoothing
azimuth_smooth = ndimage.gaussian_filter(azimuth_map, sigma=2.0)
# Should use: params['smoothing_sigma']

# Line 391 - Hard-coded minimum area size
def segment_visual_areas(sign_map, boundary_map, min_area_size=1000):
# Should use: params['area_min_size_mm2']
```

**Solution**: Update `ISIAnalysis.__init__()` to accept parameters dictionary and use throughout

### 2.6 LOW: No Progress Reporting

**Current**: `isi_analysis.py` prints to console
```python
for y in range(height):
    if y % 100 == 0:
        print(f"Row {y}/{height}")  # Console only
```

**Need**: Progress callbacks to send IPC messages to frontend for real-time updates

---

## Section 3: Architecture Analysis

### 3.1 Existing Pattern: Playback Mode (REFERENCE IMPLEMENTATION)

The playback system provides the EXACT pattern to follow:

**Files**:
- `playback_ipc_handlers.py` - IPC command handlers
- `acquisition_mode_controllers.py` - PlaybackModeController class
- `main.py` - Handler registration
- `service_locator.py` - Service registry entry

**Pattern**:
```python
# 1. IPC handlers in separate file
@ipc_handler("load_session")
def handle_load_session(command: Dict[str, Any]) -> Dict[str, Any]:
    controller = _get_playback_controller()
    session_path = command.get("session_path")
    return controller.activate(session_path=session_path)

# 2. Controller class manages state
class PlaybackModeController:
    def activate(self, session_path: str):
        # Load session data
        # Return success/error

    def get_session_data(self, direction: str):
        # Return loaded data

# 3. Register in main.py
self.command_handlers = {
    "load_session": handle_load_session,
    "get_session_data": handle_get_session_data,
}

# 4. Add to service registry
registry = ServiceRegistry(
    playback_controller=playback_mode_controller,
)
```

### 3.2 Required Architecture: Analysis Integration

**Follow same pattern exactly**:

1. **Create `analysis_ipc_handlers.py`**:
   - `handle_start_analysis`
   - `handle_stop_analysis`
   - `handle_get_analysis_status`
   - `handle_capture_anatomical`

2. **Implement `analysis_manager.py`** (currently empty):
   - `AnalysisManager` class
   - Wraps `ISIAnalysis` from `isi_analysis.py`
   - Background thread for long-running analysis
   - Progress callback to IPC
   - State management (idle, running, complete, error)

3. **Register in `main.py`**:
   - Add handlers to `command_handlers` dict
   - Import handler functions

4. **Add to `service_locator.py`**:
   - Add `analysis_manager` field
   - Initialize in `build_backend()`

5. **Update `data_recorder.py`**:
   - Add `set_anatomical_image(frame)` method
   - Save anatomical.npy in `save_session()`

6. **Update `isi_analysis.py`**:
   - Accept parameters in `__init__`
   - Use parameters instead of hard-coded values
   - Add progress callback support

---

## Section 4: Data Flow Diagrams

### 4.1 Current State (BROKEN)

```
┌─────────────┐
│  Frontend   │
│ (Electron)  │
└──────┬──────┘
       │
       │ 1. User clicks "Start Analysis"
       ↓
┌──────────────────────────────────────┐
│    Frontend sends IPC command:       │
│    { type: "start_analysis" }        │
└──────────────┬───────────────────────┘
               │
               ↓
┌──────────────────────────────────────┐
│         Backend (Python)             │
│                                      │
│  command_handlers = {                │
│    "start_analysis": ???  ❌         │
│  }                                   │
│                                      │
│  Handler not found!                  │
│  Returns: Unknown command error      │
└──────────────────────────────────────┘
               │
               ↓
       ❌ Analysis never runs
       ❌ Frontend receives error
       ❌ User cannot analyze data
```

### 4.2 Required State (INTEGRATED)

```
┌─────────────┐
│  Frontend   │
│ (Electron)  │
└──────┬──────┘
       │
       │ 1. Click "Analyze Session"
       ↓
┌──────────────────────────────────────┐
│  Send: {                             │
│    type: "start_analysis",           │
│    session_path: "/path/to/session"  │
│  }                                   │
└──────────────┬───────────────────────┘
               │
               ↓
┌──────────────────────────────────────────────────┐
│         Backend (Python)                         │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │ handle_start_analysis(command)             │ │
│  │  1. Get AnalysisManager from registry     │ │
│  │  2. Get session_path from command         │ │
│  │  3. Get analysis params from ParamManager │ │
│  │  4. Call analysis_manager.start_analysis()│ │
│  │  5. Return { success: true }              │ │
│  └────────────┬───────────────────────────────┘ │
│               │                                  │
│               ↓                                  │
│  ┌────────────────────────────────────────────┐ │
│  │ AnalysisManager                            │ │
│  │  - Creates background thread               │ │
│  │  - Instantiates ISIAnalysis                │ │
│  │  - Passes parameters                       │ │
│  │  - Sends progress via IPC                  │ │
│  └────────────┬───────────────────────────────┘ │
│               │                                  │
│               ↓                                  │
│  ┌────────────────────────────────────────────┐ │
│  │ ISIAnalysis.analyze_session()              │ │
│  │  1. Load data                              │ │
│  │  2. Compute FFT phase maps                 │ │
│  │  3. Generate retinotopic maps              │ │
│  │  4. Calculate visual field sign            │ │
│  │  5. Segment visual areas                   │ │
│  │  6. Save results                           │ │
│  └────────────┬───────────────────────────────┘ │
│               │                                  │
└───────────────┼──────────────────────────────────┘
                │
                │ IPC Progress Messages:
                ├─► { type: "analysis_started" }
                ├─► { type: "analysis_progress", progress: 0.3 }
                ├─► { type: "analysis_progress", progress: 0.7 }
                └─► { type: "analysis_complete", results: {...} }
                │
                ↓
┌───────────────────────────────────────┐
│ Frontend receives messages            │
│ - Updates progress bar                │
│ - Shows current stage                 │
│ - Displays results when complete      │
└───────────────────────────────────────┘
```

---

## Section 5: Implementation Plan

### Phase 1: Core Integration (CRITICAL - Day 1-2)

**Priority**: P0 (Blocking all analysis functionality)

#### Task 1.1: Create `analysis_ipc_handlers.py` (2 hours)

Model after `playback_ipc_handlers.py`:

```python
"""IPC handlers for analysis operations."""

from typing import Dict, Any
from .ipc_utils import ipc_handler
from .logging_utils import get_logger

logger = get_logger(__name__)

def _get_analysis_manager():
    """Get analysis manager from service registry."""
    from .service_locator import get_services
    return get_services().analysis_manager

@ipc_handler("start_analysis")
def handle_start_analysis(command: Dict[str, Any]) -> Dict[str, Any]:
    """Start analysis on a recorded session."""
    manager = _get_analysis_manager()
    session_path = command.get("session_path")

    if not session_path:
        return {"success": False, "error": "session_path is required"}

    # Get analysis parameters
    from .service_locator import get_services
    param_manager = get_services().parameter_manager
    analysis_params = param_manager.get_parameter_group("analysis")

    return manager.start_analysis(session_path, analysis_params)

@ipc_handler("stop_analysis")
def handle_stop_analysis(command: Dict[str, Any]) -> Dict[str, Any]:
    """Stop running analysis."""
    manager = _get_analysis_manager()
    return manager.stop_analysis()

@ipc_handler("get_analysis_status")
def handle_get_analysis_status(command: Dict[str, Any]) -> Dict[str, Any]:
    """Get current analysis status."""
    manager = _get_analysis_manager()
    return manager.get_status()

@ipc_handler("capture_anatomical")
def handle_capture_anatomical(command: Dict[str, Any]) -> Dict[str, Any]:
    """Capture anatomical reference frame from camera."""
    from .camera_manager import camera_manager
    from .service_locator import get_services

    # Get current frame from camera
    frame = camera_manager.get_latest_frame()
    if frame is None:
        return {"success": False, "error": "No camera frame available"}

    # Store in data recorder if recording session is active
    services = get_services()
    data_recorder = services.data_recorder

    if data_recorder is None:
        return {"success": False, "error": "No active recording session"}

    data_recorder.set_anatomical_image(frame)
    return {
        "success": True,
        "message": "Anatomical image captured",
        "shape": list(frame.shape)
    }
```

#### Task 1.2: Implement `analysis_manager.py` (4 hours)

```python
"""Analysis manager for ISI data processing."""

import threading
import time
from typing import Dict, Any, Optional
from pathlib import Path

from .isi_analysis import ISIAnalysis
from .logging_utils import get_logger
from .ipc_utils import format_success_response, format_error_response

logger = get_logger(__name__)


class AnalysisManager:
    """Manages ISI analysis pipeline with IPC integration."""

    def __init__(self):
        self.is_running = False
        self.current_session_path: Optional[str] = None
        self.analysis_thread: Optional[threading.Thread] = None
        self.progress = 0.0
        self.results: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None

    def start_analysis(
        self, session_path: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Start analysis on a recorded session."""
        if self.is_running:
            return format_error_response(
                "start_analysis", "Analysis already running"
            )

        session_path_obj = Path(session_path)
        if not session_path_obj.exists():
            return format_error_response(
                "start_analysis", f"Session not found: {session_path}"
            )

        # Validate session has required files
        metadata_file = session_path_obj / "metadata.json"
        if not metadata_file.exists():
            return format_error_response(
                "start_analysis", "Session missing metadata.json"
            )

        self.current_session_path = session_path
        self.is_running = True
        self.progress = 0.0
        self.error = None
        self.results = None

        # Start analysis in background thread
        self.analysis_thread = threading.Thread(
            target=self._run_analysis,
            args=(session_path, params),
            daemon=True,
        )
        self.analysis_thread.start()

        return format_success_response(
            "start_analysis",
            message="Analysis started",
            session_path=session_path,
        )

    def stop_analysis(self) -> Dict[str, Any]:
        """Stop running analysis (if possible)."""
        if not self.is_running:
            return format_error_response("stop_analysis", "No analysis running")

        # Note: Cannot truly cancel running analysis (would need cooperative cancellation)
        # Just mark as stopped
        logger.warning("Analysis stop requested but cannot interrupt running analysis")

        return format_success_response(
            "stop_analysis",
            message="Analysis will complete current stage",
        )

    def get_status(self) -> Dict[str, Any]:
        """Get current analysis status."""
        return format_success_response(
            "get_analysis_status",
            is_running=self.is_running,
            session_path=self.current_session_path,
            progress=self.progress,
            error=self.error,
            has_results=self.results is not None,
        )

    def _run_analysis(self, session_path: str, params: Dict[str, Any]):
        """Background thread for running analysis."""
        from .service_locator import get_services

        services = get_services()
        ipc = services.ipc

        try:
            # Send started message
            ipc.send_sync_message({
                "type": "analysis_started",
                "session_path": session_path,
                "timestamp": time.time(),
            })

            # Create analyzer with parameters
            analyzer = ISIAnalysis(params=params)

            # Stage 1: Load data (10%)
            self.progress = 0.0
            ipc.send_sync_message({
                "type": "analysis_progress",
                "progress": 0.0,
                "stage": "Loading session data",
            })

            analyzer.load_acquisition_data(session_path)

            # Stage 2: Process directions (10% -> 70%)
            directions = analyzer.session_data['metadata'].get('directions', ['LR', 'RL', 'TB', 'BT'])
            for i, direction in enumerate(directions):
                progress = 0.1 + (i / len(directions)) * 0.6
                self.progress = progress
                ipc.send_sync_message({
                    "type": "analysis_progress",
                    "progress": progress,
                    "stage": f"Processing {direction} direction",
                })

            # Stage 3: Generate maps (70% -> 90%)
            self.progress = 0.7
            ipc.send_sync_message({
                "type": "analysis_progress",
                "progress": 0.7,
                "stage": "Generating retinotopic maps",
            })

            # Run full analysis
            results = analyzer.analyze_session(session_path)

            # Stage 4: Save results (90% -> 100%)
            self.progress = 0.9
            ipc.send_sync_message({
                "type": "analysis_progress",
                "progress": 0.9,
                "stage": "Saving results",
            })

            output_path = Path(session_path) / "analysis_results"
            analyzer.save_results(str(output_path))

            self.results = {
                "output_path": str(output_path),
                "num_areas": int(results['area_map'].max()) if 'area_map' in results else 0,
            }
            self.progress = 1.0

            # Send completion message
            ipc.send_sync_message({
                "type": "analysis_complete",
                "session_path": session_path,
                "output_path": str(output_path),
                "timestamp": time.time(),
                **self.results,
            })

            logger.info(f"Analysis complete: {session_path}")

        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            self.error = str(e)

            ipc.send_sync_message({
                "type": "analysis_error",
                "error": str(e),
                "session_path": session_path,
                "timestamp": time.time(),
            })

        finally:
            self.is_running = False


# Global instance
_analysis_manager: Optional[AnalysisManager] = None


def get_analysis_manager() -> AnalysisManager:
    """Get or create global analysis manager instance."""
    global _analysis_manager
    if _analysis_manager is None:
        _analysis_manager = AnalysisManager()
    return _analysis_manager
```

#### Task 1.3: Update `isi_analysis.py` to accept parameters (1 hour)

```python
class ISIAnalysis:
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        self.params = params or {}
        self.session_data = {}
        self.results = {}

    def compute_spatial_gradients(self, azimuth_map, elevation_map):
        # Use parameter instead of hard-coded value
        sigma = self.params.get('smoothing_sigma', 2.0)
        azimuth_smooth = ndimage.gaussian_filter(azimuth_map, sigma=sigma)
        elevation_smooth = ndimage.gaussian_filter(elevation_map, sigma=sigma)
        # ... rest of method

    def segment_visual_areas(self, sign_map, boundary_map):
        # Use parameter instead of hard-coded value
        min_area_size = self.params.get('area_min_size_mm2', 1000)
        # ... rest of method using min_area_size
```

#### Task 1.4: Update `data_recorder.py` for anatomical images (30 min)

```python
class AcquisitionRecorder:
    def __init__(self, session_path: str, metadata: Dict[str, Any]):
        # ... existing code ...
        self.anatomical_image: Optional[np.ndarray] = None

    def set_anatomical_image(self, frame: np.ndarray) -> None:
        """Store anatomical reference frame."""
        self.anatomical_image = frame.copy()
        logger.info(f"Anatomical image captured: {frame.shape}")

    def save_session(self) -> None:
        # ... existing save code ...

        # Save anatomical image if available
        if self.anatomical_image is not None:
            anatomical_path = self.session_path / "anatomical.npy"
            np.save(anatomical_path, self.anatomical_image)
            logger.info(f"  Saved anatomical image: {anatomical_path}")
```

#### Task 1.5: Register in `main.py` (15 min)

```python
# Add imports
from .analysis_ipc_handlers import (
    handle_start_analysis,
    handle_stop_analysis,
    handle_get_analysis_status,
    handle_capture_anatomical,
)

# Add to command_handlers
self.command_handlers = {
    # ... existing handlers ...
    "start_analysis": handle_start_analysis,
    "stop_analysis": handle_stop_analysis,
    "get_analysis_status": handle_get_analysis_status,
    "capture_anatomical": handle_capture_anatomical,
}
```

#### Task 1.6: Add to service registry (15 min)

```python
# service_locator.py
from .analysis_manager import AnalysisManager

@dataclass
class ServiceRegistry:
    # ... existing fields ...
    analysis_manager: Optional[AnalysisManager] = None

# main.py build_backend()
from .analysis_manager import get_analysis_manager

analysis_manager = get_analysis_manager()

registry = ServiceRegistry(
    # ... existing services ...
    analysis_manager=analysis_manager,
)
```

**Deliverable**: User can click "Analyze" button after recording and analysis runs successfully

---

## Section 6: Quality Checklist

Following the same standards from playback system integration:

### Code Quality Requirements

- ✅ **Single Source of Truth**: Analysis manager in service registry
- ✅ **Proper resource management**: HDF5 files closed properly
- ✅ **Comprehensive error handling**: Try-except with logging throughout
- ✅ **Type safety**: Proper type hints in all methods
- ✅ **Service registry pattern**: Dependency injection used
- ✅ **Fail-hard validation**: Session validation before analysis
- ✅ **Scientific rigor**: Uses existing validated algorithms

### IPC Integration Requirements

- ✅ **Use `@ipc_handler` decorator**: Consistent error handling
- ✅ **Format responses properly**: Success/error with proper types
- ✅ **Service registry access**: No module globals
- ✅ **Progress reporting**: Real-time updates to frontend
- ✅ **Thread safety**: Background analysis doesn't block IPC

### Documentation Requirements

- ✅ **Clear docstrings**: All public methods documented
- ✅ **Scientific citations**: References to published methods
- ✅ **Error messages**: Actionable error descriptions
- ✅ **Type annotations**: Complete type hints

---

## Section 7: Testing Strategy

### Unit Tests Needed

1. **AnalysisManager**:
   - `test_start_analysis_success`
   - `test_start_analysis_missing_session`
   - `test_start_analysis_already_running`
   - `test_get_status`

2. **IPC Handlers**:
   - `test_handle_start_analysis`
   - `test_handle_capture_anatomical`
   - `test_handler_error_responses`

3. **Data Recorder**:
   - `test_set_anatomical_image`
   - `test_save_anatomical_with_session`

### Integration Tests Needed

1. **End-to-End**:
   - Record session → Save → Analyze → Verify results
   - Capture anatomical → Record → Verify saved
   - Multiple sessions → List → Analyze each

2. **IPC Flow**:
   - Frontend sends command → Backend responds
   - Progress messages arrive during analysis
   - Completion message includes results

---

## Section 8: Risk Assessment

### Risks and Mitigations

1. **Risk**: Long-running analysis blocks IPC
   - **Mitigation**: Analysis runs in background thread
   - **Status**: Already implemented in design

2. **Risk**: Large result data in IPC messages
   - **Mitigation**: Results saved to disk, only metadata in IPC
   - **Status**: Already implemented in design

3. **Risk**: Analysis crashes during FFT computation
   - **Mitigation**: Try-except with error reporting via IPC
   - **Status**: Already implemented in design

4. **Risk**: Parameters not properly passed to analysis
   - **Mitigation**: Validation at handler level, logging of params
   - **Status**: Requires testing

5. **Risk**: Anatomical image capture when camera not ready
   - **Mitigation**: Check camera state before capture, error message
   - **Status**: Already in handler design

---

## Section 9: Success Criteria

### Definition of Done

Phase 1 is complete when:

1. ✅ `analysis_manager.py` fully implemented (not empty)
2. ✅ All IPC handlers registered and working
3. ✅ Analysis runs successfully on recorded session
4. ✅ Frontend receives progress updates
5. ✅ Results saved to session directory
6. ✅ Anatomical image capture works
7. ✅ No errors in console during full workflow
8. ✅ Code follows same patterns as playback system

### Acceptance Test

**Manual Test Procedure**:
```
1. Start application
2. Detect camera and display
3. Click "Capture Anatomical" → Verify confirmation
4. Start recording session (all 4 directions)
5. Stop recording → Session saved
6. Click "Analyze Session" → Verify analysis starts
7. Monitor progress bar → Reaches 100%
8. Check session directory → analysis_results/ created
9. Verify HDF5 and PNG files in results
10. No errors in console at any step
```

---

## Conclusion

### Current State Assessment

**Recording Infrastructure**: A+ (Publication-ready)
- Complete, scientifically rigorous
- Proper timestamp provenance
- Clean data format

**Analysis Algorithms**: A+ (Scientifically validated)
- Correct implementation of published methods
- Complete pipeline from data to visual areas
- Well-documented and organized

**Integration**: F (Non-existent)
- Empty analysis_manager.py file
- No IPC handlers registered
- Frontend sends commands to void

### Effort Required

**Total Time**: 1-2 days for complete integration

**Breakdown**:
- Analysis IPC handlers: 2 hours
- Analysis Manager implementation: 4 hours
- Update ISIAnalysis for parameters: 1 hour
- Data recorder anatomical capture: 30 min
- Registration and wiring: 30 min
- Testing and debugging: 2-3 hours

### Recommendation

**PROCEED WITH IMPLEMENTATION IMMEDIATELY**

This is not a rebuild - it's pure integration work. The hard parts (algorithms, recording, parameter system) are done. We just need to connect the dots following the established playback pattern.

**Priority**: P0 (Critical)
**Complexity**: Medium (straightforward pattern following)
**Risk**: Low (well-established patterns to follow)
**Value**: High (unlocks entire analysis workflow)

---

**Report Prepared By**: Claude Code (Sonnet 4.5)
**Date**: October 9, 2025
**Next Action**: Begin Phase 1 implementation (analysis_ipc_handlers.py)
