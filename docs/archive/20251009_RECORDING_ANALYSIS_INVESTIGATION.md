# ARCHIVED DOCUMENTATION

**Original File**: RECORDING_ANALYSIS_INVESTIGATION.md
**Archived**: 2025-10-09
**Reason**: Documentation restructure - content consolidated into new docs/ structure

**Status**: Historical reference only. For current documentation, see:
- [Documentation Index](../README.md)
- [Architecture Overview](../architecture/overview.md)
- [Component Documentation](../components/)
- [Technical Decisions](../technical-decisions/)

---

# Original Content

# ISI Macroscope System: Recording-to-Analysis Transition Workflow Investigation

**Date**: October 8, 2025
**Investigator**: Claude Code (Sonnet 4.5)
**Scope**: Complete analysis of data flow from acquisition → storage → analysis
**Status**: CRITICAL GAPS IDENTIFIED

---

## Executive Summary

### CRITICAL FINDING: ANALYSIS PIPELINE IS INCOMPLETE

The ISI Macroscope system has a **scientifically rigorous recording infrastructure** but **NO INTEGRATION between recording and analysis**. The analysis code (`isi_analysis.py`) exists but is **completely disconnected** from the recording workflow.

**Key Findings**:
1. **Recording Infrastructure**: EXCELLENT (A+)
   - Proper data recorder with HDF5/JSON storage
   - Comprehensive metadata and timestamp provenance
   - Camera-triggered synchronous acquisition

2. **Analysis Code**: SCIENTIFICALLY SOUND but ISOLATED (B)
   - Complete Fourier-based retinotopic analysis (Kalatsky & Stryker 2003)
   - Proper bidirectional phase analysis
   - Visual field sign mapping (Zhuang et al. 2017)
   - **BUT**: No way to run it from the system!

3. **Integration**: MISSING (F)
   - No IPC handlers for analysis
   - No CLI tools to run analysis on saved sessions
   - No automatic post-acquisition analysis trigger
   - Frontend has placeholder AnalysisViewport but backend has no handlers

**Impact**: Researchers must manually write Python scripts to load and analyze recorded data. This violates the "single integrated system" principle and introduces human error.

---

## Section 1: Current State Analysis

### 1.1 Recording Infrastructure (EXCELLENT)

#### Data Recorder (`data_recorder.py`)
**Status**: Well-implemented, scientifically rigorous

**Architecture**:
```python
class AcquisitionRecorder:
    def __init__(self, session_path, metadata)
    def start_recording(direction)
    def record_stimulus_event(timestamp_us, frame_id, frame_index, direction, angle_degrees)
    def record_camera_frame(timestamp_us, frame_index, frame_data)
    def save_session()
```

**Key Features**:
- Thread-safe recording during acquisition
- Separate data streams per direction (LR, RL, TB, BT)
- Comprehensive metadata with timestamp provenance
- HDF5 compression for camera frames (gzip level 4)
- JSON for stimulus events and metadata

**Data Provenance** (EXCELLENT):
```json
{
  "timestamp_info": {
    "camera_timestamp_source": "hardware" | "software",
    "stimulus_timestamp_source": "camera_triggered_synchronous",
    "synchronization_method": "camera_capture_triggers_stimulus_generation",
    "timing_architecture": {
      "frame_index_is_ground_truth": true
    }
  }
}
```

This is **publication-quality** timestamp tracking.

#### Session Directory Structure
```
data/sessions/names n stuff/
├── metadata.json                 # Session parameters and timestamp info
├── LR_camera.h5                  # Camera frames (52 frames, 1080x1920x3, 78 MB)
├── LR_events.json                # Stimulus events with timestamps
├── LR_stimulus.h5                # Stimulus angles array
├── RL_camera.h5
├── RL_events.json
├── RL_stimulus.h5
├── TB_camera.h5
├── TB_events.json
├── TB_stimulus.h5
├── BT_camera.h5
├── BT_events.json
└── BT_stimulus.h5
```

**Analysis**:
- Clean separation by direction (enables independent processing)
- All data needed for analysis is present
- File format compatible with `isi_analysis.py` expectations

**HDF5 Structure** (verified):
```python
# Camera data
{
  'frames': (52, 1080, 1920, 3),    # [n_frames, height, width, channels]
  'timestamps': (52,)                # Microsecond timestamps
}

# Stimulus data
{
  'angles': (N,)                     # Degrees, one per stimulus event
}
```

**Events JSON Structure**:
```json
[
  {
    "timestamp": 1759976070718252,   # Microseconds
    "frame_id": 0,
    "frame_index": 0,
    "angle": 87.42243848455092
  }
]
```

**VERDICT**: Recording infrastructure is **production-ready** and follows best practices.

---

### 1.2 Analysis Code (`isi_analysis.py`) (SCIENTIFICALLY SOUND)

#### Implementation Quality: EXCELLENT

**Complete Pipeline** (554 lines):
```python
class ISIAnalysis:
    # PREPROCESSING
    def load_acquisition_data(session_path)
    def correlate_temporal_data(direction)
    def compensate_hemodynamic_delay(frames, delay_sec=1.5)

    # FOURIER ANALYSIS (Kalatsky & Stryker 2003)
    def compute_fft_phase_maps(frames, angles)
    def bidirectional_analysis(forward_phase, reverse_phase)

    # RETINOTOPIC MAPPING
    def generate_azimuth_map(LR_phase, RL_phase)
    def generate_elevation_map(TB_phase, BT_phase)

    # VISUAL FIELD SIGN (Zhuang et al. 2017)
    def compute_spatial_gradients(azimuth_map, elevation_map)
    def calculate_visual_field_sign(gradients)
    def detect_area_boundaries(sign_map)
    def segment_visual_areas(sign_map, boundary_map)

    # PIPELINE
    def analyze_session(session_path)
    def save_results(output_path)
```

**Scientific Methods Implemented**:
1. **Kalatsky & Stryker (2003)**: Fourier-based retinotopic mapping
   - Per-pixel FFT at stimulus frequency
   - Phase and magnitude extraction
   - Hemodynamic delay compensation

2. **Marshel et al. (2011)**: ISI experimental procedures
   - Bidirectional sweep analysis
   - LR/RL and TB/BT pairing

3. **Zhuang et al. (2017)**: Visual field sign analysis
   - Spatial gradient computation (Jacobian)
   - Sign map calculation (determinant)
   - Area boundary detection
   - Connected component segmentation

**Code Quality**: GOOD
- Clear separation of concerns (preprocessing → fourier → mapping → VFS)
- Proper scientific citations in docstrings
- Handles all 4 directions (LR, RL, TB, BT)
- Exports results as HDF5 + PNG images

---

#### Analysis Workflow (Current)

**Step 1: Load Session Data**
```python
def load_acquisition_data(self, session_path: str):
    # Load metadata
    metadata = json.load(f"{session_path}/metadata.json")

    # Load anatomical image (if exists)
    anatomical = np.load(f"{session_path}/anatomical.npy")  # MISSING from recorder!

    # For each direction:
    for direction in ['LR', 'RL', 'TB', 'BT']:
        # Load camera frames
        with h5py.File(f"{direction}_camera.h5") as f:
            frames = f['frames'][:]
            timestamps = f['timestamps'][:]

        # Load stimulus events
        events = json.load(f"{direction}_events.json")

        # Load stimulus angles
        with h5py.File(f"{direction}_stimulus.h5") as f:
            angles = f['angles'][:]
```

**ISSUE #1**: Expects `anatomical.npy` but recorder doesn't save it!
- Anatomical image is used for overlay visualization
- Should be captured before or after acquisition
- Currently: **MISSING FROM RECORDING WORKFLOW**

**Step 2: Correlate Temporal Data**
```python
def correlate_temporal_data(self, direction):
    camera_timestamps = camera_data['timestamps']
    event_timestamps = [e['timestamp'] for e in events]
    event_angles = [e['angle'] for e in events]

    # Match camera frames to closest stimulus event
    for cam_timestamp in camera_timestamps:
        time_diffs = abs(event_timestamps - cam_timestamp)
        closest_idx = argmin(time_diffs)

        if time_diffs[closest_idx] < 50000:  # 50ms threshold
            correlated_frames.append(camera_frames[i])
            correlated_angles.append(event_angles[closest_idx])
```

**Analysis**:
- Uses timestamp matching with 50ms tolerance
- Handles 30 FPS camera vs stimulus timing
- **QUESTION**: Is 50ms threshold appropriate for 30 FPS camera? (33ms frame period)

**Step 3: Hemodynamic Delay Compensation**
```python
def compensate_hemodynamic_delay(frames, delay_sec=1.5):
    fps = 30
    delay_frames = int(delay_sec * fps)  # 45 frames
    compensated = np.roll(frames, -delay_frames, axis=0)
```

**ISSUE #2**: Simple temporal shift, not hemodynamic response modeling
- Comment says "would use more sophisticated modeling"
- For publication: Should implement proper HRF convolution
- Current approach: **ACCEPTABLE for initial analysis, INSUFFICIENT for publication**

**Step 4: FFT Phase Analysis**
```python
def compute_fft_phase_maps(frames, angles):
    # Per-pixel Fourier analysis
    for y, x in image_coordinates:
        pixel_timeseries = frames[:, y, x]
        pixel_timeseries -= mean(pixel_timeseries)  # Remove DC

        fft_result = fft(pixel_timeseries)
        freqs = fftfreq(n_frames)

        # Find stimulus frequency component
        freq_idx = argmin(abs(freqs - stimulus_freq))

        # Extract phase and magnitude
        phase_map[y, x] = angle(fft_result[freq_idx])
        magnitude_map[y, x] = abs(fft_result[freq_idx])
```

**Analysis**: CORRECT implementation of Kalatsky & Stryker method

**Step 5: Generate Retinotopic Maps**
```python
# Azimuth (horizontal)
azimuth_map = generate_azimuth_map(LR_phase, RL_phase)
# Maps phase [-π, π] to visual angle [-60°, +60°]

# Elevation (vertical)
elevation_map = generate_elevation_map(TB_phase, BT_phase)
# Maps phase [-π, π] to visual angle [-30°, +30°]
```

**Step 6: Visual Field Sign Analysis**
```python
# Compute spatial gradients
gradients = compute_spatial_gradients(azimuth_map, elevation_map)

# Calculate VFS (sign of Jacobian determinant)
sign_map = sign(d_azimuth_dx * d_elevation_dy - d_azimuth_dy * d_elevation_dx)

# Detect boundaries and segment areas
boundary_map = detect_area_boundaries(sign_map)
area_map = segment_visual_areas(sign_map, boundary_map)
```

**Output**:
```python
results = {
    'phase_maps': {LR, RL, TB, BT},
    'magnitude_maps': {LR, RL, TB, BT},
    'azimuth_map': azimuth retinotopy,
    'elevation_map': elevation retinotopy,
    'sign_map': visual field sign,
    'boundary_map': area boundaries,
    'area_map': segmented visual areas,
    'metadata': session metadata
}
```

**VERDICT**: Analysis pipeline is **scientifically rigorous** and ready for use.

---

### 1.3 Current Integration (COMPLETELY MISSING)

#### What EXISTS:
1. Recording infrastructure: ✅ COMPLETE
2. Analysis code: ✅ COMPLETE
3. Data format compatibility: ✅ VERIFIED

#### What is MISSING:
1. **IPC Handlers for Analysis**: ❌ NONE
   - No `start_analysis` handler
   - No `get_analysis_results` handler
   - No `stop_analysis` handler
   - Frontend sends these commands but backend doesn't handle them!

2. **CLI Tools**: ❌ NONE
   - No `python -m isi_control.analyze_session <session_path>`
   - No command-line interface for analysis
   - Researchers must write custom scripts

3. **Automatic Post-Acquisition Analysis**: ❌ NONE
   - Recording finishes but analysis doesn't start
   - No prompt to run analysis
   - No automatic trigger

4. **Frontend Integration**: ⚠️ PLACEHOLDER ONLY
   - `AnalysisViewport.tsx` exists but only shows mock UI
   - Sends `start_analysis` command but backend doesn't respond
   - No actual analysis results displayed

**Evidence from Frontend**:
```typescript
// AnalysisViewport.tsx
const startAnalysis = async () => {
  await sendCommand({ type: 'start_analysis' })  // ❌ NO BACKEND HANDLER
}

// Expects messages that never arrive:
if (lastMessage?.type === 'analysis_result') { }      // ❌ NEVER SENT
if (lastMessage?.type === 'analysis_started') { }     // ❌ NEVER SENT
if (lastMessage?.type === 'analysis_stopped') { }     // ❌ NEVER SENT
```

**Evidence from Backend**:
```python
# main.py command_handlers dictionary
{
    "start_acquisition": handle_start_acquisition,  # ✅ EXISTS
    "start_analysis": ???,                          # ❌ MISSING
    # ... no analysis handlers at all
}
```

**Current Workflow** (BROKEN):
```
1. User clicks "Start Recording" ✅
2. Data is recorded ✅
3. Session is saved to disk ✅
4. User clicks "Start Analysis" ❌ (frontend sends command)
5. Backend receives command ❌ (no handler registered)
6. Nothing happens ❌
7. User must manually:
   - Exit the app
   - Write a Python script
   - Load isi_analysis.py
   - Run analysis manually
   - Open results separately
```

**VERDICT**: Integration is **NON-EXISTENT**. Analysis exists but is unreachable.

---

## Section 2: Data Flow Diagram

### Current State (Recording Only)

```
┌─────────────┐
│   Frontend  │
│  (Electron) │
└──────┬──────┘
       │ IPC: start_acquisition
       ↓
┌──────────────────────────────────────────────────┐
│              Backend (Python)                    │
│                                                  │
│  ┌────────────────────┐                         │
│  │ Acquisition        │                         │
│  │ Orchestrator       │                         │
│  └────────┬───────────┘                         │
│           │ start_recording(direction)          │
│           ↓                                      │
│  ┌────────────────────┐    ┌─────────────────┐ │
│  │  Camera Manager    │───→│ Data Recorder   │ │
│  │  (captures frames) │    │ (saves to disk) │ │
│  └────────────────────┘    └─────────┬───────┘ │
│                                       │         │
└───────────────────────────────────────┼─────────┘
                                        │
                                        ↓
                            ┌───────────────────────┐
                            │ Session Directory     │
                            │ ├─ metadata.json      │
                            │ ├─ LR_camera.h5       │
                            │ ├─ LR_events.json     │
                            │ ├─ LR_stimulus.h5     │
                            │ └─ (repeat for RL,    │
                            │     TB, BT)           │
                            └───────────────────────┘
                                        │
                                        │ ❌ DISCONNECTED
                                        ↓
                            ┌───────────────────────┐
                            │ isi_analysis.py       │
                            │ (ORPHANED CODE)       │
                            │ - No IPC handlers     │
                            │ - No CLI interface    │
                            │ - Manual use only     │
                            └───────────────────────┘
```

### Required State (Integrated Workflow)

```
┌─────────────┐
│   Frontend  │
│  (Electron) │
└──────┬──────┘
       │ IPC: start_acquisition
       ↓
┌──────────────────────────────────────────────────┐
│              Backend (Python)                    │
│                                                  │
│  ┌────────────────────┐                         │
│  │ Acquisition        │                         │
│  │ Orchestrator       │                         │
│  └────────┬───────────┘                         │
│           │                                      │
│           ↓                                      │
│  ┌────────────────────┐    ┌─────────────────┐ │
│  │  Camera Manager    │───→│ Data Recorder   │ │
│  └────────────────────┘    └─────────┬───────┘ │
│                                       │         │
│           ┌───────────────────────────┘         │
│           │ save_session()                      │
│           ↓                                      │
│  ┌────────────────────┐                         │
│  │ Analysis Manager   │ ← NEW COMPONENT         │
│  │ - IPC handlers     │                         │
│  │ - Background       │                         │
│  │   analysis thread  │                         │
│  │ - Progress updates │                         │
│  └────────┬───────────┘                         │
│           │                                      │
└───────────┼──────────────────────────────────────┘
            │
            ↓
┌───────────────────────┐
│ Session Directory     │
│ ├─ metadata.json      │
│ ├─ LR_camera.h5       │
│ ├─ LR_events.json     │
│ ├─ *_stimulus.h5      │
│ └─ analysis_results/  │ ← NEW
│    ├─ azimuth_map.png │
│    ├─ elevation_map.png│
│    ├─ sign_map.png    │
│    ├─ area_map.png    │
│    └─ results.h5      │
└───────────────────────┘
            ↑
            │ Uses
            ↓
┌───────────────────────┐
│ isi_analysis.py       │
│ (INTEGRATED)          │
│ Called by Analysis    │
│ Manager               │
└───────────────────────┘
```

---

## Section 3: Issues & Gaps Identified

### 3.1 CRITICAL: Missing Analysis Integration

**Severity**: CRITICAL
**Type**: Missing Feature
**Impact**: Analysis code is unusable within the system

**Problems**:
1. No IPC handlers for analysis commands
2. No automatic post-acquisition analysis
3. No frontend-backend integration
4. Researchers must manually run Python scripts

**Root Cause**: Analysis was implemented as standalone code, never integrated into the IPC architecture.

---

### 3.2 HIGH: Missing Anatomical Image Capture

**Severity**: HIGH
**Type**: Missing Data
**Impact**: Cannot create anatomical overlays for retinotopic maps

**Problem**: `isi_analysis.py` expects `anatomical.npy` but `data_recorder.py` never saves it.

**Code Evidence**:
```python
# isi_analysis.py line 48
anatomical_path = os.path.join(session_path, "anatomical.npy")
if os.path.exists(anatomical_path):
    session_data['anatomical'] = np.load(anatomical_path)
```

**Missing Workflow**:
- When should anatomical image be captured?
- Should it be captured before acquisition? After?
- Should it be optional or required?
- What resolution should it be?

**Scientific Impact**:
- Anatomical reference is needed to identify visual cortex regions
- Without it, retinotopic maps float without anatomical context
- Standard practice: capture before acquisition starts

---

### 3.3 MEDIUM: Hemodynamic Delay Compensation is Simplified

**Severity**: MEDIUM
**Type**: Scientific Rigor
**Impact**: Acceptable for initial analysis, insufficient for publication

**Current Implementation**:
```python
def compensate_hemodynamic_delay(frames, delay_sec=1.5):
    delay_frames = int(delay_sec * fps)
    compensated = np.roll(frames, -delay_frames, axis=0)
    return compensated
```

**Issue**: Simple temporal shift, not proper hemodynamic response modeling

**For Publication Quality**:
- Should implement HRF (Hemodynamic Response Function) convolution
- Standard: Gamma function (Boynton et al. 1996)
- Peak delay: 4-6 seconds
- Should account for individual subject variation

**Recommendation**:
- Current approach is acceptable for initial analysis
- Add proper HRF modeling before publication
- Make HRF parameters configurable in `AnalysisParameters`

---

### 3.4 MEDIUM: Timestamp Correlation Threshold

**Severity**: MEDIUM
**Type**: Data Quality
**Impact**: May lose frames with poor timestamp matching

**Current Code**:
```python
# Only include if within reasonable time window (< 50ms)
if time_diffs[closest_idx] < 50000:  # 50ms in microseconds
    correlated_frames.append(camera_frames[i])
```

**Analysis**:
- Camera FPS: 30 (33.3ms frame period)
- Threshold: 50ms (1.5× frame period)
- **QUESTION**: Is this threshold appropriate?

**Potential Issues**:
1. If timing jitter > 50ms, frames are dropped
2. No logging of how many frames are excluded
3. No validation that enough frames remain for analysis

**Recommendations**:
1. Log number of correlated vs. total frames
2. Fail hard if < 80% of frames can be correlated
3. Make threshold configurable in `AnalysisParameters`
4. Report correlation quality in analysis metadata

---

### 3.5 LOW: No Analysis Progress Reporting

**Severity**: LOW
**Type**: User Experience
**Impact**: User doesn't know if analysis is running or stuck

**Problem**: FFT computation is slow (per-pixel processing)

**Current Code**:
```python
for y in range(height):
    if y % 100 == 0:
        print(f"Row {y}/{height}")  # Console only, not IPC
```

**Missing**:
- Progress percentage sent to frontend
- ETA calculation
- Cancellation support
- Status updates

---

### 3.6 LOW: No Data Validation on Load

**Severity**: LOW
**Type**: Error Handling
**Impact**: Cryptic errors if data files are corrupted

**Problem**: `load_acquisition_data()` doesn't validate:
- HDF5 file integrity
- Expected array shapes
- Required metadata fields
- Consistent number of frames across directions

**Recommendation**: Add validation layer:
```python
def validate_session_data(session_path):
    """Validate session data integrity before analysis."""
    errors = []

    # Check metadata exists
    if not exists(f"{session_path}/metadata.json"):
        errors.append("Missing metadata.json")

    # For each direction, check files exist and shapes match
    for direction in directions:
        camera_file = f"{session_path}/{direction}_camera.h5"
        if not exists(camera_file):
            errors.append(f"Missing {direction}_camera.h5")
        else:
            with h5py.File(camera_file) as f:
                if 'frames' not in f or 'timestamps' not in f:
                    errors.append(f"{direction}_camera.h5 missing required datasets")

    if errors:
        raise ValidationError("\n".join(errors))
```

---

### 3.7 Architecture: Analysis Parameters Not Used

**Severity**: MEDIUM
**Type**: Dead Code
**Impact**: Parameters exist but are never used

**Evidence**:
```python
# parameter_manager.py defines AnalysisParameters:
@dataclass
class AnalysisParameters:
    ring_size_mm: float
    vfs_threshold_sd: float
    smoothing_sigma: float
    magnitude_threshold: float
    phase_filter_sigma: float
    gradient_window_size: int
    area_min_size_mm2: float
    response_threshold_percent: float
```

**But `isi_analysis.py` uses hard-coded values**:
```python
# Line 315: Hard-coded sigma
azimuth_smooth = ndimage.gaussian_filter(azimuth_map, sigma=2.0)

# Line 391: Hard-coded min area size
def segment_visual_areas(sign_map, boundary_map, min_area_size=1000):
```

**Problem**:
- Parameters defined but never passed to analysis functions
- No way to adjust analysis settings without code changes
- Frontend has AnalysisParameters UI but backend ignores it

**Recommendation**:
- Analysis Manager should load parameters from ParameterManager
- Pass parameters to `ISIAnalysis.analyze_session()`
- Update `ISIAnalysis` methods to use parameter values

---

## Section 4: Recommendations

### 4.1 IMMEDIATE: Create Analysis Manager (CRITICAL)

**Priority**: P0 (Blocking)
**Complexity**: HIGH
**Estimated Effort**: 2-3 days

**Create** `/apps/backend/src/isi_control/analysis_manager.py`:

```python
"""Analysis manager for ISI data processing."""

import threading
import time
from typing import Dict, Any, Optional
from pathlib import Path

from .isi_analysis import ISIAnalysis
from .logging_utils import get_logger
from .ipc_utils import ipc_handler

logger = get_logger(__name__)


class AnalysisManager:
    """Manages ISI analysis pipeline and IPC integration."""

    def __init__(self):
        self.is_running = False
        self.current_session_path: Optional[str] = None
        self.analysis_thread: Optional[threading.Thread] = None
        self.progress = 0.0
        self.results = None

    def start_analysis(self, session_path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Start analysis on a recorded session.

        Args:
            session_path: Path to session directory
            params: Analysis parameters from ParameterManager

        Returns:
            Success status and analysis info
        """
        if self.is_running:
            return {"success": False, "error": "Analysis already running"}

        if not Path(session_path).exists():
            return {"success": False, "error": f"Session not found: {session_path}"}

        self.current_session_path = session_path
        self.is_running = True
        self.progress = 0.0

        # Start analysis in background thread
        self.analysis_thread = threading.Thread(
            target=self._run_analysis,
            args=(session_path, params),
            daemon=True
        )
        self.analysis_thread.start()

        return {
            "success": True,
            "message": "Analysis started",
            "session_path": session_path
        }

    def _run_analysis(self, session_path: str, params: Dict[str, Any]):
        """Background analysis execution."""
        from .service_locator import get_services

        services = get_services()
        ipc = services.ipc

        try:
            # Send started message
            ipc.send_sync_message({
                "type": "analysis_started",
                "session_path": session_path,
                "timestamp": time.time()
            })

            # Create analysis instance
            analyzer = ISIAnalysis()

            # Run analysis with progress updates
            self.progress = 0.1
            ipc.send_sync_message({
                "type": "analysis_progress",
                "progress": 0.1,
                "stage": "Loading session data"
            })

            analyzer.load_acquisition_data(session_path)

            self.progress = 0.3
            ipc.send_sync_message({
                "type": "analysis_progress",
                "progress": 0.3,
                "stage": "Computing phase maps"
            })

            results = analyzer.analyze_session(session_path)

            self.progress = 0.9
            ipc.send_sync_message({
                "type": "analysis_progress",
                "progress": 0.9,
                "stage": "Saving results"
            })

            # Save results
            output_path = Path(session_path) / "analysis_results"
            analyzer.save_results(str(output_path))

            self.results = results
            self.progress = 1.0

            # Send completion message
            ipc.send_sync_message({
                "type": "analysis_complete",
                "session_path": session_path,
                "output_path": str(output_path),
                "timestamp": time.time(),
                "num_areas": int(results['area_map'].max())
            })

        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            ipc.send_sync_message({
                "type": "analysis_error",
                "error": str(e),
                "timestamp": time.time()
            })
        finally:
            self.is_running = False

    def get_status(self) -> Dict[str, Any]:
        """Get current analysis status."""
        return {
            "is_running": self.is_running,
            "session_path": self.current_session_path,
            "progress": self.progress
        }


# IPC Handlers
@ipc_handler("start_analysis")
def handle_start_analysis(command: Dict[str, Any]) -> Dict[str, Any]:
    """Start analysis on a recorded session."""
    from .service_locator import get_services

    services = get_services()
    analysis_manager = services.analysis_manager
    param_manager = services.parameter_manager

    session_path = command.get("session_path")
    if not session_path:
        return {"success": False, "error": "session_path is required"}

    # Get analysis parameters
    analysis_params = param_manager.get_parameter_group("analysis")

    return analysis_manager.start_analysis(session_path, analysis_params)


@ipc_handler("get_analysis_status")
def handle_get_analysis_status(command: Dict[str, Any]) -> Dict[str, Any]:
    """Get current analysis status."""
    from .service_locator import get_services

    services = get_services()
    analysis_manager = services.analysis_manager

    return analysis_manager.get_status()


# Global instance
_analysis_manager = AnalysisManager()

def get_analysis_manager() -> AnalysisManager:
    """Get global analysis manager instance."""
    return _analysis_manager
```

**Integration Steps**:
1. Create `analysis_manager.py` as above
2. Add to `service_locator.py`:
   ```python
   from .analysis_manager import get_analysis_manager

   registry.analysis_manager = get_analysis_manager()
   ```
3. Register IPC handlers in `main.py`:
   ```python
   from .analysis_manager import handle_start_analysis, handle_get_analysis_status

   self.command_handlers = {
       # ... existing handlers
       "start_analysis": handle_start_analysis,
       "get_analysis_status": handle_get_analysis_status,
   }
   ```

---

### 4.2 IMMEDIATE: Add Anatomical Image Capture

**Priority**: P0 (Blocking for analysis)
**Complexity**: MEDIUM
**Estimated Effort**: 1 day

**Workflow**:
1. Add "Capture Anatomical" button to frontend
2. Capture single frame from camera before acquisition
3. Save as `anatomical.npy` in data recorder
4. Display in AnalysisViewport after analysis

**Implementation**:

```python
# In data_recorder.py
class AcquisitionRecorder:
    def __init__(self, ...):
        self.anatomical_image: Optional[np.ndarray] = None

    def set_anatomical_image(self, frame: np.ndarray) -> None:
        """Store anatomical reference frame."""
        self.anatomical_image = frame.copy()
        logger.info(f"Anatomical image set: {frame.shape}")

    def save_session(self) -> None:
        # ... existing code ...

        # Save anatomical image if available
        if self.anatomical_image is not None:
            anatomical_path = self.session_path / "anatomical.npy"
            np.save(anatomical_path, self.anatomical_image)
            logger.info(f"Saved anatomical image: {anatomical_path}")
```

**IPC Handler**:
```python
@ipc_handler("capture_anatomical")
def handle_capture_anatomical(command: Dict[str, Any]) -> Dict[str, Any]:
    """Capture anatomical reference frame."""
    from .camera_manager import camera_manager
    from .service_locator import get_services

    # Capture current frame
    frame = camera_manager.capture_frame()
    if frame is None:
        return {"success": False, "error": "Failed to capture frame"}

    # Store in data recorder
    services = get_services()
    acquisition_manager = services.acquisition_manager

    if acquisition_manager.data_recorder:
        acquisition_manager.data_recorder.set_anatomical_image(frame)
        return {
            "success": True,
            "message": "Anatomical image captured",
            "shape": frame.shape
        }
    else:
        return {"success": False, "error": "No active recording session"}
```

---

### 4.3 HIGH: Use Analysis Parameters in Analysis Code

**Priority**: P1 (Important)
**Complexity**: MEDIUM
**Estimated Effort**: 1 day

**Problem**: `AnalysisParameters` exist but are never used

**Solution**: Update `ISIAnalysis` to accept parameters:

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
        # ...

    def segment_visual_areas(self, sign_map, boundary_map):
        # Use parameter instead of hard-coded value
        min_area_size = self.params.get('area_min_size_mm2', 1000)
        # ...
```

**Analysis Manager Integration**:
```python
def _run_analysis(self, session_path, params):
    analyzer = ISIAnalysis(params=params)  # Pass parameters
    results = analyzer.analyze_session(session_path)
```

---

### 4.4 HIGH: Add CLI Tool for Analysis

**Priority**: P1 (Important for researchers)
**Complexity**: LOW
**Estimated Effort**: 0.5 days

**Create** `/apps/backend/scripts/analyze_session.py`:

```python
#!/usr/bin/env python3
"""
CLI tool to analyze ISI recording sessions.

Usage:
    python scripts/analyze_session.py <session_path>
    python scripts/analyze_session.py data/sessions/my_experiment
"""

import sys
import argparse
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from isi_control.isi_analysis import ISIAnalysis


def main():
    parser = argparse.ArgumentParser(
        description="Analyze ISI recording session"
    )
    parser.add_argument(
        "session_path",
        type=str,
        help="Path to session directory"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory (default: session_path/analysis_results)"
    )

    args = parser.parse_args()

    session_path = Path(args.session_path)
    if not session_path.exists():
        print(f"Error: Session not found: {session_path}")
        return 1

    print(f"Analyzing session: {session_path}")

    # Run analysis
    analyzer = ISIAnalysis()
    results = analyzer.analyze_session(str(session_path))

    # Save results
    output_path = args.output or str(session_path / "analysis_results")
    analyzer.save_results(output_path)

    print(f"\nAnalysis complete!")
    print(f"Results saved to: {output_path}")
    print(f"Visual areas detected: {results['area_map'].max()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Make executable**:
```bash
chmod +x scripts/analyze_session.py
```

**Usage**:
```bash
python scripts/analyze_session.py data/sessions/my_experiment
```

---

### 4.5 MEDIUM: Improve Hemodynamic Delay Compensation

**Priority**: P2 (Before publication)
**Complexity**: MEDIUM
**Estimated Effort**: 2 days

**Implement proper HRF convolution**:

```python
def generate_hrf(duration=30, dt=0.033, peak_delay=5.0, undershoot_delay=15.0):
    """
    Generate canonical Hemodynamic Response Function.

    Based on: Boynton et al. (1996), Glover (1999)

    Args:
        duration: HRF duration in seconds
        dt: Time resolution (1/fps)
        peak_delay: Peak response delay in seconds
        undershoot_delay: Undershoot delay in seconds

    Returns:
        HRF time series
    """
    from scipy.stats import gamma

    t = np.arange(0, duration, dt)

    # Peak: Gamma(6, 1)
    peak = gamma.pdf(t, 6, scale=peak_delay/6)

    # Undershoot: Gamma(12, 1)
    undershoot = gamma.pdf(t, 12, scale=undershoot_delay/12)

    # Combined HRF
    hrf = peak - 0.35 * undershoot
    hrf = hrf / hrf.sum()  # Normalize

    return hrf


def compensate_hemodynamic_delay(frames, fps=30.0, params=None):
    """
    Compensate for hemodynamic response using HRF deconvolution.

    Args:
        frames: Camera frames [n_frames, height, width]
        fps: Frame rate
        params: Analysis parameters (optional)

    Returns:
        Compensated frames
    """
    # Generate HRF
    dt = 1.0 / fps
    hrf = generate_hrf(duration=30, dt=dt)

    # For each pixel, deconvolve HRF
    # (In practice, use Wiener deconvolution or iterative methods)
    # For initial implementation, simple convolution approach:

    n_frames, height, width = frames.shape
    compensated = np.zeros_like(frames)

    # Apply HRF correction per pixel
    for y in range(height):
        for x in range(width):
            pixel_timeseries = frames[:, y, x]
            # Deconvolve or shift based on HRF peak
            compensated[:, y, x] = pixel_timeseries  # Simplified

    return compensated
```

**Add to AnalysisParameters**:
```python
@dataclass
class AnalysisParameters:
    # ... existing fields ...
    hrf_peak_delay: float = 5.0
    hrf_undershoot_delay: float = 15.0
    use_hrf_deconvolution: bool = False  # Feature flag
```

---

### 4.6 MEDIUM: Add Data Validation Layer

**Priority**: P2 (Error prevention)
**Complexity**: LOW
**Estimated Effort**: 0.5 days

**Add validation before analysis**:

```python
# In isi_analysis.py
def validate_session_data(self, session_path: str) -> None:
    """
    Validate session data integrity.

    Raises:
        ValueError: If data validation fails
    """
    errors = []

    # Check metadata
    metadata_path = os.path.join(session_path, "metadata.json")
    if not os.path.exists(metadata_path):
        errors.append("Missing metadata.json")
    else:
        with open(metadata_path) as f:
            metadata = json.load(f)
            if 'directions' not in metadata:
                errors.append("Metadata missing 'directions' field")

    # Check each direction
    directions = metadata.get('directions', ['LR', 'RL', 'TB', 'BT'])
    for direction in directions:
        # Camera data
        camera_path = os.path.join(session_path, f"{direction}_camera.h5")
        if not os.path.exists(camera_path):
            errors.append(f"Missing {direction}_camera.h5")
        else:
            with h5py.File(camera_path, 'r') as f:
                if 'frames' not in f:
                    errors.append(f"{direction}_camera.h5 missing 'frames' dataset")
                if 'timestamps' not in f:
                    errors.append(f"{direction}_camera.h5 missing 'timestamps' dataset")
                else:
                    # Check shapes match
                    n_frames = f['frames'].shape[0]
                    n_timestamps = f['timestamps'].shape[0]
                    if n_frames != n_timestamps:
                        errors.append(
                            f"{direction}: frame count mismatch "
                            f"(frames: {n_frames}, timestamps: {n_timestamps})"
                        )

        # Events data
        events_path = os.path.join(session_path, f"{direction}_events.json")
        if not os.path.exists(events_path):
            errors.append(f"Missing {direction}_events.json")

    if errors:
        raise ValueError(
            f"Session data validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )


def load_acquisition_data(self, session_path: str) -> Dict[str, Any]:
    # Validate before loading
    self.validate_session_data(session_path)

    # ... existing loading code ...
```

---

### 4.7 LOW: Add Progress Reporting to Analysis

**Priority**: P3 (UX improvement)
**Complexity**: LOW
**Estimated Effort**: 0.5 days

**Update FFT computation to report progress**:

```python
def compute_fft_phase_maps(self, frames, angles, progress_callback=None):
    n_frames, height, width = frames.shape
    phase_map = np.zeros((height, width))
    magnitude_map = np.zeros((height, width))

    for y in range(height):
        # Report progress
        if progress_callback and y % 10 == 0:
            progress = y / height
            progress_callback(progress, f"FFT row {y}/{height}")

        for x in range(width):
            # ... FFT computation ...
```

**Use in Analysis Manager**:

```python
def _run_analysis(self, session_path, params):
    def progress_callback(progress, stage):
        ipc.send_sync_message({
            "type": "analysis_progress",
            "progress": progress,
            "stage": stage
        })

    analyzer = ISIAnalysis(
        params=params,
        progress_callback=progress_callback
    )
```

---

## Section 5: Implementation Plan

### Phase 1: Core Integration (CRITICAL - Week 1)

**Goal**: Enable basic analysis workflow

1. **Create Analysis Manager** (2 days)
   - Implement `analysis_manager.py`
   - Add IPC handlers
   - Integrate with service locator
   - Test with recorded session

2. **Add Anatomical Image Capture** (1 day)
   - Update `data_recorder.py`
   - Add IPC handler
   - Update frontend UI
   - Test capture and save

3. **Wire Analysis Parameters** (1 day)
   - Update `ISIAnalysis.__init__()` to accept params
   - Replace hard-coded values with parameter lookups
   - Test with different parameter values

**Deliverable**: User can click "Analyze" button after recording and see results

---

### Phase 2: Usability Improvements (HIGH - Week 2)

**Goal**: Make analysis accessible to researchers

1. **Create CLI Tool** (0.5 days)
   - Implement `analyze_session.py`
   - Add help documentation
   - Test on multiple sessions

2. **Add Data Validation** (0.5 days)
   - Implement `validate_session_data()`
   - Add validation before analysis
   - Improve error messages

3. **Add Progress Reporting** (0.5 days)
   - Update FFT to report progress
   - Add progress bar to frontend
   - Add ETA calculation

4. **Testing & Documentation** (1 day)
   - Test full workflow: record → analyze → view
   - Document analysis parameters
   - Create user guide for analysis

**Deliverable**: Researchers can run analysis from GUI or CLI with clear feedback

---

### Phase 3: Scientific Rigor (MEDIUM - Week 3-4)

**Goal**: Prepare for publication-quality analysis

1. **Improve HRF Compensation** (2 days)
   - Implement proper HRF generation
   - Add HRF deconvolution
   - Make HRF parameters configurable
   - Validate against literature

2. **Timestamp Correlation Validation** (1 day)
   - Add correlation quality metrics
   - Log excluded frames
   - Fail if correlation rate < threshold
   - Add timestamp QA report

3. **Analysis Quality Metrics** (1 day)
   - Add SNR calculation
   - Add response magnitude statistics
   - Add VFS boundary confidence scores
   - Export QA metrics with results

4. **Comprehensive Testing** (1 day)
   - Unit tests for all analysis functions
   - Integration tests for full pipeline
   - Validate against known datasets
   - Performance benchmarking

**Deliverable**: Publication-ready analysis pipeline with QA metrics

---

## Priority Summary

### P0 (BLOCKING - Must Do Now):
1. ✅ Create Analysis Manager (`analysis_manager.py`)
2. ✅ Add anatomical image capture workflow
3. ✅ Register IPC handlers in main.py
4. ✅ Wire analysis parameters to ISIAnalysis

### P1 (HIGH - Should Do Soon):
1. ✅ Create CLI tool for batch analysis
2. ✅ Add data validation before analysis
3. ✅ Add progress reporting to frontend
4. ✅ Test full record → analyze workflow

### P2 (MEDIUM - Before Publication):
1. ⚠️ Improve hemodynamic delay compensation
2. ⚠️ Add timestamp correlation validation
3. ⚠️ Add analysis quality metrics
4. ⚠️ Comprehensive testing

### P3 (LOW - Nice to Have):
1. ◯ Add analysis result visualization in frontend
2. ◯ Add batch analysis for multiple sessions
3. ◯ Add analysis result export formats (MATLAB, NIfTI)
4. ◯ Add comparison between sessions

---

## Conclusion

### Current State: INCOMPLETE BUT SALVAGEABLE

**Strengths**:
- Recording infrastructure is **excellent** (A+)
- Analysis code is **scientifically sound** (B)
- Data format is **compatible** (A)

**Critical Gap**:
- **ZERO integration** between recording and analysis (F)

**Impact**:
- Analysis exists but is **unusable** within the system
- Researchers must write manual scripts
- Violates "integrated system" principle

**Effort to Fix**:
- **Week 1**: Core integration (CRITICAL)
- **Week 2**: Usability improvements (HIGH)
- **Week 3-4**: Publication-quality refinements (MEDIUM)

**Total Effort**: 3-4 weeks for complete solution

### Architectural Assessment

**Good**:
- Clean separation: recording → storage → analysis
- Proper data provenance (timestamp sources documented)
- Scientific rigor in analysis methods
- HDF5/JSON format is appropriate

**Needs Work**:
- No automatic post-acquisition analysis
- Analysis parameters defined but not used
- Missing anatomical image capture
- No data validation layer
- Simplified HRF compensation

### Scientific Rigor Score

**Recording**: A+ (publication-ready)
- Hardware/software timestamp detection
- Camera-triggered synchronous acquisition
- Complete metadata and provenance
- Proper compression and storage

**Analysis**: B (acceptable for initial work, needs refinement for publication)
- Correct Fourier methods
- Proper bidirectional analysis
- Valid VFS calculation
- **BUT**: Simplified HRF, no validation layer

**Integration**: F (non-existent)
- No way to run analysis from system
- Manual scripting required
- Frontend expects features that don't exist

### Recommendation: PROCEED WITH INTEGRATION

This is a **high-quality foundation** with a **critical missing piece**. The solution is straightforward:

1. **Week 1**: Create Analysis Manager and wire IPC handlers → **USABLE**
2. **Week 2**: Add CLI, validation, progress reporting → **USER-FRIENDLY**
3. **Week 3-4**: Refine HRF and QA metrics → **PUBLICATION-READY**

The architecture is sound. The code is solid. **Just needs integration work.**

---

**Report Prepared By**: Claude Code (Sonnet 4.5)
**Investigation Date**: October 8, 2025
**Session Data Examined**: `/Users/Adam/KimLabISI/apps/backend/data/sessions/names n stuff/`
**Files Analyzed**: 27 Python files, 7 TypeScript files, 1 recorded session

**Next Steps**: Begin Phase 1 implementation (Analysis Manager creation)
