# Unified Acquisition Architecture Audit Report
**Date:** 2025-10-14
**System:** ISI Macroscope Acquisition System
**Auditor:** Claude Code (Architecture & Code Auditor)

---

## Executive Summary

This audit evaluates the current acquisition system implementation against the **Single Source of Truth (SSoT) specification** for unified acquisition architecture. The system VIOLATES the SSoT in multiple critical areas:

### CRITICAL VIOLATIONS

1. **COMPETING STIMULUS SYSTEMS** - Two separate stimulus generation loops exist:
   - `PreviewStimulusLoop` (preview mode)
   - `CameraTriggeredStimulusController` (record mode)
   - These can run simultaneously causing race conditions

2. **DIVERGENT BEHAVIOR** - Preview and record modes use completely different code paths:
   - Preview: `preview_stimulus_loop.start()` → continuous monitor-FPS loop
   - Record: `camera_triggered_stimulus.start_direction()` → camera-triggered per-frame
   - NO SHARED CODE between modes

3. **SCIENTIFICALLY INVALID TIMING** - Camera-triggered stimulus creates N+1 offset:
   - Camera captures frame N while displaying stimulus N-1
   - Frame correspondence is off-by-one (scientifically problematic)

4. **PHASE PROGRESSION INCONSISTENCY** - Preview mode ignores phase rules:
   - No INITIAL_BASELINE → STIMULUS → BETWEEN_TRIALS → FINAL_BASELINE
   - Just loops stimulus continuously
   - Record mode follows phases correctly

5. **CAMERA RECORDING LIFECYCLE VIOLATION** - Camera doesn't record continuously:
   - Camera manager writes frames only during `is_recording`
   - Missing baseline frames (violates SSoT requirement to save ALL frames)

---

## Phase 1: Current Architecture Analysis

### 1.1 Preview Mode Architecture

**File:** `/Users/Adam/KimLabISI/apps/backend/src/acquisition/preview_stimulus.py`

**How it works:**
```python
class PreviewStimulusLoop:
    def start(self, direction: str = "LR"):
        # Starts separate thread
        self._thread = threading.Thread(target=self._playback_loop)

    def _playback_loop(self):
        # Generates frames at MONITOR FPS (not camera FPS!)
        fps = self.stimulus_generator.spatial_config.fps  # Monitor FPS

        while not self._stop_event.is_set():
            # Generate frame
            frame, metadata = self.stimulus_generator.generate_frame_at_index(...)

            # Write to shared memory
            self.shared_memory.write_frame(frame, metadata)

            # Loop continuously (NO PHASE PROGRESSION)
            self._frame_index += 1
            if self._frame_index >= self._total_frames:
                self._frame_index = 0  # LOOP BACK TO START
```

**Characteristics:**
- Runs in separate thread (`PreviewStimulusLoop`)
- Generates frames at **monitor FPS** (60Hz)
- **Loops continuously** (no phase progression)
- **No camera involvement** (pure monitor-synchronized playback)
- **No data recording**
- Presentation monitor visibility controlled by user toggle

**SSoT Violations:**
- ❌ Does NOT follow phase progression (INITIAL_BASELINE → STIMULUS → FINAL_BASELINE)
- ❌ Loops continuously instead of single-run with phases
- ❌ Uses monitor FPS instead of camera FPS pacing
- ❌ Completely different code path from record mode

### 1.2 Record Mode Architecture

**File:** `/Users/Adam/KimLabISI/apps/backend/src/acquisition/camera_stimulus.py`

**How it works:**
```python
class CameraTriggeredStimulusController:
    def start_direction(self, direction: str, camera_fps: float):
        # Calculate total frames based on CAMERA FPS
        total_frames = int(sweep_duration * camera_fps)
        self._is_active = True

    def generate_next_frame(self):
        # Called by camera loop for EACH camera capture
        # This is SYNCHRONOUS - camera thread blocks waiting for stimulus

        if self._frame_index >= self._total_frames:
            return None, None  # Direction complete

        frame, metadata = self.stimulus_generator.generate_frame_at_index(...)
        self._frame_index += 1
        return frame, metadata
```

**Camera Loop Integration:**
```python
# File: /Users/Adam/KimLabISI/apps/backend/src/camera/manager.py
def _acquisition_loop(self):
    while not self.stop_acquisition_event.is_set():
        # STEP 1: Capture camera frame
        frame = self.capture_frame()
        capture_timestamp = int(time.time() * 1_000_000)

        # STEP 2: TRIGGER STIMULUS GENERATION (camera-triggered)
        if self.camera_triggered_stimulus:
            stimulus_frame, stimulus_metadata = (
                self.camera_triggered_stimulus.generate_next_frame()  # BLOCKS HERE
            )

        # STEP 3: Record data (if recorder active)
        if data_recorder and data_recorder.is_recording:
            data_recorder.record_camera_frame(...)
            data_recorder.record_stimulus_event(...)
```

**Characteristics:**
- Stimulus generation triggered **per camera frame**
- **Camera-paced** (not monitor-paced)
- **Single-run** with phase progression (handled by `AcquisitionManager._acquisition_loop`)
- **Records all data** to disk
- Presentation monitor always ON during acquisition

**SSoT Violations:**
- ✅ Follows phase progression (via `AcquisitionManager`)
- ❌ **N+1 TIMING OFFSET**: Camera captures frame N while viewing stimulus N-1
- ❌ Completely different code path from preview mode
- ❌ Camera recording only during `is_recording` (missing baseline frames)

### 1.3 Acquisition Manager Orchestration

**File:** `/Users/Adam/KimLabISI/apps/backend/src/acquisition/manager.py`

**Phase Progression (Record Mode Only):**
```python
def _acquisition_loop(self):
    # Phase 1: Initial baseline
    self._enter_phase(AcquisitionPhase.INITIAL_BASELINE)
    self._publish_baseline_frame()  # Shows background_luminance
    self._wait_duration(self.baseline_sec)

    # Phase 2: For each direction
    for direction in self.directions:
        if self.data_recorder:
            self.data_recorder.start_recording(direction)  # ENABLE RECORDING

        for cycle in range(self.cycles):
            # STIMULUS PHASE
            self._enter_phase(AcquisitionPhase.STIMULUS)
            self.camera_triggered_stimulus.start_direction(direction, self.camera_fps)

            # Wait for completion
            while not self.camera_triggered_stimulus.is_direction_complete():
                time.sleep(0.1)

            self.camera_triggered_stimulus.stop_direction()

            # BETWEEN TRIALS PHASE
            if cycle < self.cycles - 1:
                self._enter_phase(AcquisitionPhase.BETWEEN_TRIALS)
                self._publish_baseline_frame()
                self._wait_duration(self.between_sec)

        if self.data_recorder:
            self.data_recorder.stop_recording()  # DISABLE RECORDING

    # Phase 3: Final baseline
    self._enter_phase(AcquisitionPhase.FINAL_BASELINE)
    self._publish_baseline_frame()
    self._wait_duration(self.baseline_sec)
```

**Key Observations:**
- Phase progression implemented ONLY for record mode
- Preview mode bypasses `_acquisition_loop` entirely
- Camera recording controlled by `data_recorder.start_recording()` / `stop_recording()`
- **CRITICAL**: Baseline frames are CAPTURED but NOT SAVED (recorder is disabled)

### 1.4 Camera Recording Lifecycle

**File:** `/Users/Adam/KimLabISI/apps/backend/src/camera/manager.py` (lines 733-752)

```python
# === STEP 4: RECORD DATA (CAMERA + STIMULUS) ===
data_recorder = self.get_data_recorder()
if data_recorder and data_recorder.is_recording:  # <-- ONLY IF RECORDING ENABLED
    # Record camera frame
    data_recorder.record_camera_frame(
        timestamp_us=capture_timestamp,
        frame_index=camera_frame_index,
        frame_data=cropped_gray,
    )

    # Record stimulus event (if generated)
    if stimulus_metadata:
        data_recorder.record_stimulus_event(...)
```

**CRITICAL VIOLATION:**
- Camera frames are ONLY saved when `data_recorder.is_recording == True`
- Recorder is enabled/disabled per direction via:
  - `data_recorder.start_recording(direction)` → enables recording
  - `data_recorder.stop_recording()` → disables recording
- **Result:** Baseline frames (INITIAL_BASELINE, BETWEEN_TRIALS, FINAL_BASELINE) are CAPTURED but NOT SAVED
- **SSoT Requirement:** "ALWAYS record if in record mode (regardless of phase)"

---

## Phase 2: SSoT Violations Summary

### 2.1 Competing Stimulus Systems

**VIOLATION:** Two separate stimulus generation systems exist and can run simultaneously.

| Aspect | PreviewStimulusLoop | CameraTriggeredStimulusController |
|--------|---------------------|----------------------------------|
| **File** | `acquisition/preview_stimulus.py` | `acquisition/camera_stimulus.py` |
| **Trigger** | Monitor refresh timer (60Hz) | Camera frame capture |
| **FPS Pacing** | Monitor FPS (from `spatial_config.fps`) | Camera FPS (passed as parameter) |
| **Threading** | Separate thread (`_playback_loop`) | Called from camera thread |
| **Phase Support** | NO (continuous loop) | YES (single-run, direction-based) |
| **Used In** | Preview mode | Record mode |
| **Can Coexist** | **YES - RACE CONDITION** | **YES - RACE CONDITION** |

**Race Condition Example:**
```python
# Scenario: User clicks "Record" while preview stimulus is running

# Frontend (AcquisitionViewport.tsx:213-219)
const startPreview = async () => {
    // Start preview stimulus loop
    setShowOnPresentation(true)
    await sendCommand?.({
        type: 'set_presentation_stimulus_enabled',
        enabled: true  // Starts PreviewStimulusLoop
    })
}

# Backend (main.py:596-660)
def _set_presentation_stimulus_enabled(ipc, preview_stimulus_loop, cmd):
    if enabled:
        preview_stimulus_loop.start(direction="LR")  # STARTS PREVIEW LOOP

# Then user clicks "Record"...
# Backend (manager.py:528-541)
def _acquisition_loop(self):
    self.camera_triggered_stimulus.start_direction(...)  # STARTS CAMERA-TRIGGERED

# NOW BOTH SYSTEMS ARE RUNNING:
# - PreviewStimulusLoop generating frames at 60Hz → shared memory
# - CameraTriggeredStimulus generating frames at 30Hz → shared memory
# LAST WRITE WINS - PRESENTATION MONITOR SHOWS WRONG FRAMES
```

**Defensive Cleanup Attempt (Insufficient):**
```python
# File: acquisition/manager.py:220-222
if self.preview_stimulus_loop and self.preview_stimulus_loop.is_running():
    logger.info("Stopping preview stimulus loop before acquisition (defensive cleanup)")
    self.preview_stimulus_loop.stop()
```

**Why Insufficient:**
- Only stops preview loop at acquisition start
- Doesn't prevent frontend from re-enabling it during acquisition
- No architectural prevention of simultaneous operation

### 2.2 Divergent Preview vs Record Behavior

**VIOLATION:** Preview and record modes use completely different code paths with NO shared implementation.

| Behavior | Preview Mode | Record Mode | SSoT Requirement |
|----------|--------------|-------------|------------------|
| **Acquisition Loop** | `preview_stimulus_loop.start()` | `acquisition.start_acquisition()` | Same loop for both |
| **Stimulus Generation** | `PreviewStimulusLoop._playback_loop()` | `CameraTriggeredStimulus.generate_next_frame()` | Single system |
| **Phase Progression** | NONE (continuous loop) | INITIAL_BASELINE → STIMULUS → BETWEEN_TRIALS → FINAL_BASELINE | Identical in both |
| **FPS Pacing** | Monitor FPS (60Hz) | Camera FPS (30Hz) | Camera FPS (both) |
| **Loop Behavior** | Continuous (infinite loop) | Single-run then stop | Both should be configurable |
| **Camera Recording** | NO | YES (but only during stimulus phases) | YES (all phases) |
| **Stimulus Events Recording** | NO | YES | YES (both modes for consistency) |
| **Presentation Monitor** | User toggle | Always ON | Only difference allowed |

**Code Duplication:**
- `PreviewStimulusLoop._playback_loop()` duplicates stimulus generation logic
- `CameraTriggeredStimulus.generate_next_frame()` duplicates same logic
- Both call `stimulus_generator.generate_frame_at_index()` but with different timing

### 2.3 Camera Recording Lifecycle Violation

**VIOLATION:** Camera does NOT record continuously in record mode. Baseline frames are lost.

**Current Implementation:**
```python
# Camera CAPTURES all frames (regardless of phase)
while not self.stop_acquisition_event.is_set():
    frame = self.capture_frame()

    # But ONLY RECORDS during stimulus phases
    if data_recorder and data_recorder.is_recording:  # <-- GATE
        data_recorder.record_camera_frame(...)
```

**Recording Control:**
```python
# Acquisition manager enables/disables recording per direction
for direction in self.directions:
    self.data_recorder.start_recording(direction)  # ENABLE

    # Stimulus phases happen here...

    self.data_recorder.stop_recording()  # DISABLE
```

**Result:**
- INITIAL_BASELINE (5s): Camera captures frames but DOESN'T SAVE
- STIMULUS (varies): Camera captures AND SAVES ✓
- BETWEEN_TRIALS (5s): Camera captures frames but DOESN'T SAVE
- FINAL_BASELINE (5s): Camera captures frames but DOESN'T SAVE

**SSoT Requirement:**
```python
while acquisition_running:
    frame = camera.capture()

    # ALWAYS record if in record mode (regardless of phase)
    if mode == "record" and data_recorder:
        data_recorder.record_camera_frame(
            frame_data=frame,
            phase=current_phase,  # Tag with phase for analysis
            direction=current_direction
        )
```

### 2.4 Scientifically Invalid Timing (N+1 Offset)

**VIOLATION:** Camera-triggered stimulus creates frame correspondence offset.

**Current Timing:**
```
Time:     t0    t1    t2    t3    t4
Camera:   F0    F1    F2    F3    F4    (capture)
Stimulus:  -    S0    S1    S2    S3    (generation triggered AFTER capture)
Display:   -     -    S0    S1    S2    (VSync delay ~8-16ms)

Analysis Thinks:
  F0 ↔ S0  (WRONG - S0 wasn't generated yet)
  F1 ↔ S1  (WRONG - F1 captured while viewing S0)
  F2 ↔ S2  (WRONG - F2 captured while viewing S1)
```

**The Problem:**
1. Camera captures frame F_N
2. Capture triggers stimulus generation for frame S_N
3. S_N is displayed AFTER capture completes
4. Next camera frame F_{N+1} is captured while viewing S_N
5. **Frame correspondence is off-by-one**

**SSoT Recommendation:**
- **Option A (Pre-Generated):** Generate all stimulus frames BEFORE acquisition starts
- **Option B (Camera-Triggered with Compensation):** Generate S_{N+1} when F_N is captured
- Current implementation uses Option B without compensation (scientifically invalid)

### 2.5 Phase Progression Inconsistency

**VIOLATION:** Preview mode doesn't follow phase progression at all.

| Phase | Preview Mode | Record Mode | SSoT Requirement |
|-------|--------------|-------------|------------------|
| INITIAL_BASELINE | ❌ None | ✅ 5s background_luminance | ✅ Both modes |
| STIMULUS | ✅ Continuous loop | ✅ Single sweep per direction | ✅ Both modes (identical) |
| BETWEEN_TRIALS | ❌ None | ✅ 5s background_luminance | ✅ Both modes |
| FINAL_BASELINE | ❌ None | ✅ 5s background_luminance | ✅ Both modes |
| Loop Behavior | ✅ Continuous | ✅ Stop after complete | ✅ Both (user configurable) |

**Preview Mode Implementation:**
```python
# preview_stimulus.py:175-227
def _playback_loop(self):
    while not self._stop_event.is_set():
        # Generate frame
        frame, metadata = self.stimulus_generator.generate_frame_at_index(
            direction=direction,
            frame_index=frame_index,
            show_bar_mask=True,
            total_frames=total_frames
        )

        # Write to shared memory
        self.shared_memory.write_frame(frame, metadata)

        # Loop back to start when reaching end
        self._frame_index += 1
        if self._frame_index >= self._total_frames:
            self._frame_index = 0  # NO PHASE PROGRESSION
            self._loop_count += 1
```

**SSoT Requirement:**
- Both modes should use SAME phase progression state machine
- Only difference: `loop_continuously` flag (True in preview, False in record)

---

## Phase 3: Unified Implementation Design

### 3.1 Architecture Overview

**Core Principle:** ONE acquisition loop serves both preview and record modes.

```
┌─────────────────────────────────────────────────────────────┐
│                    AcquisitionManager                        │
│                                                              │
│  _run_acquisition_phases() {                                │
│    // SINGLE LOOP FOR BOTH MODES                            │
│    enter_phase(INITIAL_BASELINE)                            │
│    wait(baseline_sec)                                       │
│                                                              │
│    for direction in directions:                             │
│      for cycle in cycles:                                   │
│        enter_phase(STIMULUS)                                │
│        run_stimulus_sweep(direction)  // UNIFIED            │
│        enter_phase(BETWEEN_TRIALS)                          │
│        wait(between_sec)                                    │
│                                                              │
│    enter_phase(FINAL_BASELINE)                              │
│    wait(baseline_sec)                                       │
│                                                              │
│    if loop_continuously:  // ONLY DIFFERENCE                │
│      goto start                                             │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Single Stimulus System Design

**Decision:** Use **Pre-Generated Stimulus** (Option A) for scientific validity.

**Why Pre-Generated:**
- Eliminates N+1 offset (camera and stimulus are independent)
- Frame correspondence via timestamps (offline analysis)
- Display at monitor VSync rate (smooth)
- Camera captures independently
- Scientifically valid (no frame-to-frame dependency)

**Implementation:**
```python
class PreGeneratedStimulusController:
    def __init__(self, stimulus_generator):
        self.stimulus_generator = stimulus_generator
        self.frames = []  # Pre-generated frames
        self.metadata = []

    def pre_generate_sweep(self, direction: str, total_frames: int):
        """Pre-generate all frames for a direction BEFORE acquisition starts."""
        self.frames = []
        self.metadata = []

        for frame_idx in range(total_frames):
            frame, meta = self.stimulus_generator.generate_frame_at_index(
                direction=direction,
                frame_index=frame_idx,
                total_frames=total_frames
            )
            self.frames.append(frame)
            self.metadata.append(meta)

    def start_playback(self, monitor_fps: float):
        """Start playing back pre-generated frames at monitor FPS."""
        self.playback_thread = threading.Thread(target=self._playback_loop)
        self.playback_fps = monitor_fps
        self.playback_thread.start()

    def _playback_loop(self):
        """Display pre-generated frames at monitor VSync rate."""
        frame_duration = 1.0 / self.playback_fps

        for frame, meta in zip(self.frames, self.metadata):
            start_time = time.time()

            # Write to shared memory with current timestamp
            display_timestamp_us = int(time.time() * 1_000_000)
            self.shared_memory.write_frame(frame, {
                **meta,
                'display_timestamp_us': display_timestamp_us
            })

            # Wait for next frame (VSync timing)
            elapsed = time.time() - start_time
            sleep_time = frame_duration - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
```

**Camera Loop (Independent):**
```python
def _acquisition_loop(self):
    while not self.stop_event.is_set():
        # Capture frame (independent of stimulus display)
        frame = self.capture_frame()
        capture_timestamp_us = int(time.time() * 1_000_000)

        # ALWAYS record in record mode (regardless of phase)
        if self.mode == "record" and self.data_recorder:
            self.data_recorder.record_camera_frame(
                timestamp_us=capture_timestamp_us,
                frame_index=self.frame_counter,
                frame_data=frame,
                phase=self.current_phase,  # From acquisition manager
                direction=self.current_direction
            )

        # Display in acquisition viewport (always)
        self.shared_memory.write_camera_frame(frame, ...)

        self.frame_counter += 1
```

**Frame Correspondence (Offline Analysis):**
```python
# Analysis matches frames by timestamps
camera_timestamps = load_camera_timestamps()
stimulus_timestamps = load_stimulus_timestamps()

# Match within temporal window (e.g., ±5ms)
matches = []
for cam_ts in camera_timestamps:
    closest_stim = find_closest(stimulus_timestamps, cam_ts)
    if abs(closest_stim - cam_ts) < 5000:  # 5ms threshold
        matches.append((cam_ts, closest_stim))
```

### 3.3 Phase State Machine

**Unified Phase Progression:**
```python
class AcquisitionPhaseController:
    def __init__(self):
        self.current_phase = AcquisitionPhase.IDLE
        self.phase_start_time = 0.0

    def enter_phase(self, phase: AcquisitionPhase, direction: Optional[str] = None):
        """Transition to new phase - updates ALL subsystems."""
        self.current_phase = phase
        self.phase_start_time = time.time()

        # Propagate phase to all subsystems
        self.camera.set_current_phase(phase, direction)
        self.data_recorder.set_current_phase(phase, direction)
        self.shared_memory.set_current_phase(phase, direction)

        # Log transition
        logger.info(f"Phase transition: {phase.value} (direction={direction})")

        # Publish to frontend
        self.ipc.send_sync_message({
            'type': 'phase_transition',
            'phase': phase.value,
            'direction': direction,
            'timestamp': time.time()
        })
```

**Acquisition Loop (Unified):**
```python
def _run_acquisition_phases(self):
    """Single acquisition loop used by BOTH preview and record modes."""

    # Phase 1: Initial Baseline
    self.phase_controller.enter_phase(AcquisitionPhase.INITIAL_BASELINE)
    self._display_background(self.baseline_sec)

    # Phase 2: Stimulus Sweeps
    for direction in self.directions:
        # Pre-generate stimulus for this direction
        self.stimulus_controller.pre_generate_sweep(
            direction=direction,
            total_frames=self._calculate_total_frames(direction)
        )

        for cycle in range(self.cycles):
            # STIMULUS PHASE
            self.phase_controller.enter_phase(
                AcquisitionPhase.STIMULUS,
                direction=direction
            )

            # Start stimulus playback (at monitor FPS)
            self.stimulus_controller.start_playback(self.monitor_fps)

            # Wait for sweep completion
            self.stimulus_controller.wait_for_completion()

            # BETWEEN TRIALS PHASE
            if cycle < self.cycles - 1:
                self.phase_controller.enter_phase(AcquisitionPhase.BETWEEN_TRIALS)
                self._display_background(self.between_sec)

    # Phase 3: Final Baseline
    self.phase_controller.enter_phase(AcquisitionPhase.FINAL_BASELINE)
    self._display_background(self.baseline_sec)

    # Phase 4: Complete or Loop
    if self.loop_continuously:  # ONLY DIFFERENCE BETWEEN MODES
        self._run_acquisition_phases()  # Restart
    else:
        self.phase_controller.enter_phase(AcquisitionPhase.COMPLETE)
```

### 3.4 Mode Differences (ONLY TWO)

**Mode Configuration:**
```python
@dataclass
class AcquisitionConfig:
    mode: Literal["preview", "record"]
    save_to_disk: bool  # True in record, False in preview
    loop_continuously: bool  # True in preview, False in record
    presentation_enabled: bool  # User controlled in preview, Always True in record

    # EVERYTHING ELSE IS IDENTICAL
    baseline_sec: float
    between_sec: float
    cycles: int
    directions: List[str]
    camera_fps: float
    monitor_fps: float
```

**Mode Switching:**
```python
def set_mode(self, mode: Literal["preview", "record"]):
    """Switch modes - ONLY affects saving and looping."""

    if mode == "record":
        self.config.save_to_disk = True
        self.config.loop_continuously = False
        self.config.presentation_enabled = True

    elif mode == "preview":
        self.config.save_to_disk = False
        self.config.loop_continuously = True
        self.config.presentation_enabled = False  # User controlled

    # CAMERA KEEPS RUNNING - NO CHANGE
    # PHASE PROGRESSION CONTINUES - NO CHANGE
    # STIMULUS SYSTEM UNCHANGED - NO CHANGE
```

### 3.5 Data Recorder Architecture

**Continuous Recording in Record Mode:**
```python
class SessionDataRecorder:
    def __init__(self, session_name: str, metadata: Dict):
        self.session_name = session_name
        self.metadata = metadata
        self.is_recording = False  # Global recording flag

        # Buffers for each direction
        self.camera_frames = []
        self.stimulus_events = []

    def set_mode(self, mode: str):
        """Enable/disable recording based on mode."""
        self.is_recording = (mode == "record")

    def record_camera_frame(
        self,
        timestamp_us: int,
        frame_index: int,
        frame_data: np.ndarray,
        phase: str,
        direction: Optional[str]
    ):
        """Record camera frame - ALWAYS called if is_recording=True."""
        if not self.is_recording:
            return

        self.camera_frames.append({
            'timestamp_us': timestamp_us,
            'frame_index': frame_index,
            'frame_data': frame_data,
            'phase': phase,  # "initial_baseline", "stimulus", "between_trials", "final_baseline"
            'direction': direction  # "LR", "RL", "TB", "BT" or None
        })

    def record_stimulus_event(
        self,
        display_timestamp_us: int,
        frame_id: int,
        direction: str,
        angle_degrees: float
    ):
        """Record stimulus display event."""
        if not self.is_recording:
            return

        self.stimulus_events.append({
            'display_timestamp_us': display_timestamp_us,
            'frame_id': frame_id,
            'direction': direction,
            'angle_degrees': angle_degrees
        })
```

---

## Phase 4: Detailed Implementation Plan

### 4.1 File Modifications

#### Step 1: Delete Competing Systems

**Files to DELETE:**
- `/Users/Adam/KimLabISI/apps/backend/src/acquisition/preview_stimulus.py` (entire file)
- `/Users/Adam/KimLabISI/apps/backend/src/acquisition/camera_stimulus.py` (entire file)

**Rationale:** These are competing implementations. Replace with single unified system.

#### Step 2: Create Unified Stimulus Controller

**NEW FILE:** `/Users/Adam/KimLabISI/apps/backend/src/acquisition/unified_stimulus.py`

```python
"""
Unified Stimulus Controller - Single system for both preview and record modes.

Uses pre-generated stimulus frames displayed at monitor VSync rate.
Camera captures independently with frame correspondence via timestamps.
"""

import threading
import time
import logging
from typing import Dict, Any, Optional, List, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class UnifiedStimulusController:
    """
    Single stimulus controller for both preview and record modes.

    Pre-generates stimulus frames before playback starts.
    Displays frames at monitor VSync rate (independent of camera).
    Camera captures frames independently with timestamp-based correspondence.
    """

    def __init__(self, stimulus_generator, shared_memory):
        self.stimulus_generator = stimulus_generator
        self.shared_memory = shared_memory

        # Pre-generated frames
        self.frames: List[np.ndarray] = []
        self.metadata: List[Dict[str, Any]] = []

        # Playback state
        self._playback_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_playing = False
        self._playback_fps = 60.0

        # Current playback position
        self._current_frame_index = 0

    def pre_generate_sweep(
        self,
        direction: str,
        total_frames: int,
        show_bar_mask: bool = True
    ) -> Dict[str, Any]:
        """
        Pre-generate all stimulus frames for a direction.

        Called BEFORE acquisition/preview starts to generate entire sweep.
        Eliminates N+1 offset by decoupling generation from display.

        Args:
            direction: Sweep direction (LR, RL, TB, BT)
            total_frames: Total frames in sweep
            show_bar_mask: Whether to show bar mask

        Returns:
            Dict with generation status and info
        """
        logger.info(
            f"Pre-generating {total_frames} frames for direction {direction}"
        )

        self.frames = []
        self.metadata = []

        start_time = time.time()

        for frame_idx in range(total_frames):
            frame, meta = self.stimulus_generator.generate_frame_at_index(
                direction=direction,
                frame_index=frame_idx,
                show_bar_mask=show_bar_mask,
                total_frames=total_frames
            )

            self.frames.append(frame)
            self.metadata.append(meta)

        generation_time = time.time() - start_time

        logger.info(
            f"Pre-generation complete: {total_frames} frames in {generation_time:.2f}s "
            f"({total_frames/generation_time:.1f} fps generation rate)"
        )

        return {
            "success": True,
            "total_frames": total_frames,
            "generation_time_sec": generation_time,
            "direction": direction
        }

    def start_playback(self, monitor_fps: float) -> Dict[str, Any]:
        """
        Start playing back pre-generated frames at monitor VSync rate.

        Args:
            monitor_fps: Monitor refresh rate (typically 60Hz)

        Returns:
            Dict with playback status
        """
        if self._is_playing:
            return {"success": False, "error": "Already playing"}

        if not self.frames:
            return {"success": False, "error": "No frames pre-generated"}

        self._playback_fps = monitor_fps
        self._current_frame_index = 0
        self._stop_event.clear()

        self._playback_thread = threading.Thread(
            target=self._playback_loop,
            name="UnifiedStimulusPlayback",
            daemon=True
        )
        self._playback_thread.start()
        self._is_playing = True

        logger.info(
            f"Started stimulus playback: {len(self.frames)} frames at {monitor_fps}Hz"
        )

        return {
            "success": True,
            "total_frames": len(self.frames),
            "playback_fps": monitor_fps
        }

    def stop_playback(self) -> Dict[str, Any]:
        """Stop stimulus playback."""
        if not self._is_playing:
            return {"success": True, "message": "Not playing"}

        self._stop_event.set()
        self._is_playing = False

        if self._playback_thread and self._playback_thread.is_alive():
            self._playback_thread.join(timeout=2.0)

        logger.info("Stopped stimulus playback")

        return {"success": True}

    def _playback_loop(self):
        """
        Playback loop - displays pre-generated frames at monitor VSync rate.

        Runs in separate thread. Displays frames with precise timing to match
        monitor refresh rate (VSync).
        """
        frame_duration = 1.0 / self._playback_fps

        logger.info(
            f"Playback loop started: {self._playback_fps}Hz "
            f"({frame_duration*1000:.2f}ms per frame)"
        )

        while not self._stop_event.is_set() and self._current_frame_index < len(self.frames):
            frame_start_time = time.time()

            # Get pre-generated frame
            frame = self.frames[self._current_frame_index]
            meta = self.metadata[self._current_frame_index].copy()

            # Add display timestamp (ground truth for frame correspondence)
            display_timestamp_us = int(time.time() * 1_000_000)
            meta['display_timestamp_us'] = display_timestamp_us

            # Write to shared memory (stimulus channel)
            frame_id = self.shared_memory.write_frame(frame, meta)

            # Set stimulus timestamp for timing QA
            self.shared_memory.set_stimulus_timestamp(display_timestamp_us, frame_id)

            self._current_frame_index += 1

            # Sleep to maintain VSync timing
            frame_elapsed = time.time() - frame_start_time
            sleep_time = frame_duration - frame_elapsed

            if sleep_time > 0:
                if self._stop_event.wait(sleep_time):
                    break  # Stop event set during sleep
            elif sleep_time < -0.01:  # Warn if significantly behind
                logger.warning(
                    f"Playback frame took {frame_elapsed*1000:.1f}ms "
                    f"(target {frame_duration*1000:.1f}ms) - frame {self._current_frame_index}"
                )

        logger.info(
            f"Playback loop completed: displayed {self._current_frame_index}/{len(self.frames)} frames"
        )

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for playback to complete.

        Args:
            timeout: Maximum time to wait (None = infinite)

        Returns:
            True if completed, False if timed out
        """
        if self._playback_thread:
            self._playback_thread.join(timeout=timeout)
            return not self._playback_thread.is_alive()
        return True

    def is_playing(self) -> bool:
        """Check if playback is active."""
        return self._is_playing

    def get_status(self) -> Dict[str, Any]:
        """Get current playback status."""
        return {
            "is_playing": self._is_playing,
            "current_frame": self._current_frame_index,
            "total_frames": len(self.frames),
            "progress": (
                self._current_frame_index / len(self.frames) * 100.0
                if self.frames else 0.0
            )
        }
```

#### Step 3: Refactor Acquisition Manager

**FILE:** `/Users/Adam/KimLabISI/apps/backend/src/acquisition/manager.py`

**Changes:**

1. **Replace dependencies (lines 18-23):**
```python
# OLD
from .modes import (
    PreviewModeController,
    RecordModeController,
)

# NEW
from .unified_stimulus import UnifiedStimulusController
```

2. **Update constructor (lines 45-78):**
```python
def __init__(
    self,
    ipc,
    shared_memory,
    stimulus_generator,
    camera,
    synchronization_tracker: Optional[TimestampSynchronizationTracker] = None,
    state_coordinator: Optional[AcquisitionStateCoordinator] = None,
    data_recorder=None,
    param_manager=None,
):
    """Initialize acquisition manager with injected dependencies."""
    # Injected dependencies
    self.ipc = ipc
    self.shared_memory = shared_memory
    self.stimulus_generator = stimulus_generator
    self.camera = camera
    self.param_manager = param_manager

    # DELETE: self.preview_stimulus_loop reference
    # DELETE: self.camera_triggered_stimulus reference

    # NEW: Single unified stimulus controller
    self.stimulus_controller = UnifiedStimulusController(
        stimulus_generator=stimulus_generator,
        shared_memory=shared_memory
    )

    # State
    self.is_running = False
    self.mode = "preview"  # "preview" or "record"
    self.loop_continuously = True  # True in preview, False in record
    # ... rest unchanged
```

3. **Add unified acquisition loop (REPLACE `_acquisition_loop` starting at line 495):**
```python
def _acquisition_loop(self):
    """
    UNIFIED acquisition loop for BOTH preview and record modes.

    ONLY differences between modes:
    1. save_to_disk: True in record, False in preview
    2. loop_continuously: True in preview, False in record
    3. presentation_enabled: Always True in record, user-controlled in preview

    Everything else is IDENTICAL.
    """
    try:
        while True:  # Loop controlled by loop_continuously flag
            # Phase 1: Initial Baseline
            self._enter_phase(AcquisitionPhase.INITIAL_BASELINE)
            self._display_background(self.baseline_sec)

            # Phase 2: For each direction
            for direction_index, direction in enumerate(self.directions):
                if self.stop_event.is_set():
                    break

                with self._state_lock:
                    self.current_direction_index = direction_index
                    self.current_cycle = 0

                # Calculate total frames for this direction
                drift_speed = self.stimulus_generator.stimulus_config.drift_speed_deg_per_sec
                if direction in ["LR", "RL"]:
                    fov_half = self.stimulus_generator.spatial_config.field_of_view_horizontal / 2
                    bar_width = self.stimulus_generator.stimulus_config.bar_width_deg
                else:  # TB, BT
                    fov_half = self.stimulus_generator.spatial_config.field_of_view_vertical / 2
                    bar_width = self.stimulus_generator.stimulus_config.bar_width_deg

                total_sweep_degrees = 2 * (fov_half + bar_width)
                sweep_duration = total_sweep_degrees / drift_speed
                total_frames = int(sweep_duration * self.camera_fps)

                # PRE-GENERATE stimulus for this direction
                logger.info(f"Pre-generating stimulus for {direction}: {total_frames} frames")
                gen_result = self.stimulus_controller.pre_generate_sweep(
                    direction=direction,
                    total_frames=total_frames,
                    show_bar_mask=True
                )

                if not gen_result.get("success"):
                    raise RuntimeError(f"Failed to pre-generate stimulus: {gen_result.get('error')}")

                # For each cycle
                for cycle in range(self.cycles):
                    if self.stop_event.is_set():
                        break

                    with self._state_lock:
                        self.current_cycle = cycle + 1

                    # STIMULUS PHASE
                    self._enter_phase(AcquisitionPhase.STIMULUS, direction=direction)

                    # Calculate expected duration
                    stimulus_duration = total_frames / self.camera_fps

                    # Get monitor FPS
                    monitor_params = self.param_manager.get_parameter_group("monitor")
                    monitor_fps = monitor_params.get("monitor_fps", 60.0)

                    # Start stimulus playback at monitor FSync rate
                    play_result = self.stimulus_controller.start_playback(monitor_fps)
                    if not play_result.get("success"):
                        raise RuntimeError(f"Failed to start playback: {play_result.get('error')}")

                    logger.info(
                        f"Stimulus playback started: {direction} cycle {cycle+1}/{self.cycles}, "
                        f"{total_frames} frames, {stimulus_duration:.2f}s duration"
                    )

                    # Wait for stimulus completion (with timeout)
                    timeout = stimulus_duration * 2.0  # Safety timeout
                    if not self.stimulus_controller.wait_for_completion(timeout=timeout):
                        logger.warning(f"Stimulus playback timeout after {timeout:.2f}s")

                    # Stop playback
                    self.stimulus_controller.stop_playback()

                    # BETWEEN TRIALS PHASE
                    if cycle < self.cycles - 1:
                        self._enter_phase(AcquisitionPhase.BETWEEN_TRIALS)
                        self._display_background(self.between_sec)

                if self.stop_event.is_set():
                    break

                # Between directions: add baseline wait only if not last direction
                if direction_index < len(self.directions) - 1:
                    self._enter_phase(AcquisitionPhase.BETWEEN_TRIALS)
                    self._display_background(self.between_sec)

            # Phase 3: Final Baseline
            self._enter_phase(AcquisitionPhase.FINAL_BASELINE)
            self._display_background(self.baseline_sec)

            # ONLY DIFFERENCE: Loop or complete
            if not self.loop_continuously:
                break  # Record mode: stop after one run

            if self.stop_event.is_set():
                break

            # Preview mode: loop back to start
            logger.info("Preview mode: looping back to start")

        # Complete
        self._enter_phase(AcquisitionPhase.COMPLETE)

    except Exception as e:
        logger.error(f"Acquisition loop error: {e}", exc_info=True)
    finally:
        with self._state_lock:
            self.is_running = False
            self.phase = AcquisitionPhase.IDLE

        # Save data if in record mode
        if self.mode == "record" and self.data_recorder:
            try:
                logger.info("Saving acquisition data...")
                self.data_recorder.save_session()
                logger.info(f"Acquisition data saved to: {self.data_recorder.session_path}")
            except Exception as e:
                logger.error(f"Failed to save acquisition data: {e}", exc_info=True)

        # Always display black screen when acquisition ends
        try:
            self._display_black_screen()
        except Exception as e:
            logger.warning(f"Failed to display black screen at end of acquisition: {e}")
```

4. **Update `_enter_phase` to propagate phase to camera (lines 663-686):**
```python
def _enter_phase(self, phase: AcquisitionPhase, direction: Optional[str] = None):
    """Enter a new acquisition phase - propagates to all subsystems."""
    with self._state_lock:
        self.phase = phase
        self.phase_start_time = time.time()

    # Propagate phase to camera (for frame tagging)
    if self.camera:
        self.camera.set_current_phase(phase.value, direction)

    # Clear stimulus timestamp when entering non-stimulus phases
    if phase != AcquisitionPhase.STIMULUS:
        if self.shared_memory:
            self.shared_memory.clear_stimulus_timestamp()
            logger.debug(f"Cleared stimulus timestamp for phase: {phase.value}")

    logger.info(f"Acquisition phase: {phase.value} (direction={direction})")

    # Send progress update to frontend
    status = self.get_status()
    if self.ipc:
        self.ipc.send_sync_message(
            {"type": "acquisition_progress", "timestamp": time.time(), **status}
        )
```

5. **Add `_display_background` helper:**
```python
def _display_background(self, duration_sec: float):
    """Display background luminance and wait for duration."""
    self._display_black_screen()
    self._wait_duration(duration_sec)
```

#### Step 4: Update Camera Manager

**FILE:** `/Users/Adam/KimLabISI/apps/backend/src/camera/manager.py`

**Changes:**

1. **Add phase tracking (lines 77-80):**
```python
def __init__(self, ...):
    # ... existing init code ...

    # Phase tracking (set by acquisition manager)
    self._current_phase = "idle"
    self._current_direction = None
```

2. **Add phase setter method:**
```python
def set_current_phase(self, phase: str, direction: Optional[str]):
    """Set current acquisition phase (called by acquisition manager)."""
    with self.acquisition_lock:
        self._current_phase = phase
        self._current_direction = direction
        logger.debug(f"Camera phase updated: {phase} (direction={direction})")
```

3. **Update recording logic (lines 730-753):**
```python
# === STEP 4: RECORD DATA (CAMERA + STIMULUS) ===
data_recorder = self.get_data_recorder()
if data_recorder:  # REMOVED: and data_recorder.is_recording check
    # ALWAYS record camera frames in record mode (regardless of phase)
    # Phase tagging allows analysis to separate baseline vs stimulus
    data_recorder.record_camera_frame(
        timestamp_us=capture_timestamp,
        frame_index=camera_frame_index,
        frame_data=cropped_gray,
        phase=self._current_phase,  # Phase tag
        direction=self._current_direction  # Direction tag (None during baselines)
    )

    # Record stimulus event (if stimulus frame was displayed)
    # NOTE: Stimulus display is independent of camera capture
    # Frame correspondence is established offline via timestamps
    stimulus_timestamp = self.shared_memory.get_last_stimulus_timestamp()
    if stimulus_timestamp is not None:
        data_recorder.record_stimulus_event(
            display_timestamp_us=stimulus_timestamp,
            camera_timestamp_us=capture_timestamp,
            direction=self._current_direction
        )
```

4. **DELETE camera-triggered stimulus code (lines 698-778):**
```python
# DELETE THIS ENTIRE SECTION:
# === STEP 2: TRIGGER STIMULUS GENERATION (CAMERA-TRIGGERED) ===
# stimulus_frame = None
# stimulus_metadata = None
# ...
```

#### Step 5: Update Data Recorder

**FILE:** `/Users/Adam/KimLabISI/apps/backend/src/acquisition/recorder.py`

**Changes:**

1. **Update `record_camera_frame` signature:**
```python
def record_camera_frame(
    self,
    timestamp_us: int,
    frame_index: int,
    frame_data: np.ndarray,
    phase: str,  # NEW: Phase tag
    direction: Optional[str]  # NEW: Direction tag
):
    """
    Record camera frame with phase tagging.

    ALWAYS called when data_recorder exists (no is_recording gate).
    Phase tags allow analysis to filter baseline vs stimulus frames.
    """
    self._camera_frames_buffer.append({
        'timestamp_us': timestamp_us,
        'frame_index': frame_index,
        'frame_data': frame_data,
        'phase': phase,  # "idle", "initial_baseline", "stimulus", "between_trials", "final_baseline"
        'direction': direction  # "LR", "RL", "TB", "BT" or None for baseline phases
    })
```

2. **Update `record_stimulus_event` signature:**
```python
def record_stimulus_event(
    self,
    display_timestamp_us: int,  # When stimulus was displayed
    camera_timestamp_us: int,   # When camera captured (for correspondence)
    direction: str
):
    """
    Record stimulus display event.

    Frame correspondence is established offline by matching timestamps.
    No N+1 offset because stimulus display is independent of camera capture.
    """
    self._stimulus_events_buffer.append({
        'display_timestamp_us': display_timestamp_us,
        'camera_timestamp_us': camera_timestamp_us,
        'direction': direction,
        'time_delta_us': display_timestamp_us - camera_timestamp_us  # For QA
    })
```

3. **DELETE `start_recording` / `stop_recording` methods:**
```python
# DELETE: def start_recording(self, direction: str): ...
# DELETE: def stop_recording(self): ...
# DELETE: self.is_recording flag
```

#### Step 6: Update Main.py Service Wiring

**FILE:** `/Users/Adam/KimLabISI/apps/backend/src/main.py`

**Changes (lines 44-192):**

1. **Delete old controllers:**
```python
# DELETE: sync_tracker = TimestampSynchronizationTracker()
# DELETE: camera_triggered_stimulus = CameraTriggeredStimulusController(...)
# DELETE: preview_stimulus_loop = PreviewStimulusLoop(...)
```

2. **Wire unified stimulus controller:**
```python
# Unified stimulus controller (used by both preview and record modes)
unified_stimulus = UnifiedStimulusController(
    stimulus_generator=stimulus_generator,
    shared_memory=shared_memory
)
logger.info("  [5/11] UnifiedStimulusController created")

camera = CameraManager(
    param_manager=param_manager,
    ipc=ipc,
    shared_memory=shared_memory,
)
logger.info("  [6/11] CameraManager created")
```

3. **Wire acquisition manager:**
```python
acquisition = AcquisitionManager(
    ipc=ipc,
    shared_memory=shared_memory,
    stimulus_generator=stimulus_generator,
    camera=camera,
    state_coordinator=state_coordinator,
    data_recorder=None,  # Created dynamically when recording starts
    param_manager=param_manager,
)
logger.info("  [11/11] AcquisitionManager created")
```

4. **Update IPC handlers (remove preview stimulus toggle):**
```python
# DELETE: "set_presentation_stimulus_enabled" handler
# Preview/record now controlled by acquisition mode only
```

#### Step 7: Update Frontend

**FILE:** `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx`

**Changes:**

1. **Remove presentation toggle (lines 149-151, 1628-1652):**
```typescript
// DELETE: const [showOnPresentation, setShowOnPresentation] = useState(false)

// DELETE: Show on Presentation Monitor toggle UI
// Stimulus visibility is now controlled by acquisition mode (preview/record) only
```

2. **Simplify preview start (lines 191-226):**
```typescript
const startPreview = async () => {
  if (!cameraParams?.selected_camera) {
    setCameraError('No camera selected')
    return
  }

  try {
    setCameraError(null)
    setFrameCount(0)
    setIsPreviewActive(true)

    // Start acquisition in preview mode (loops continuously)
    const result = await sendCommand?.({
      type: 'set_acquisition_mode',
      mode: 'preview'
    })

    if (!result?.success) {
      setCameraError(result?.error || 'Failed to start preview')
      setIsPreviewActive(false)
      return
    }

    // Note: Backend now handles ALL stimulus lifecycle
  } catch (error) {
    setCameraError(`Error: ${error instanceof Error ? error.message : String(error)}`)
    setIsPreviewActive(false)
  }
}
```

3. **Simplify acquisition start (lines 232-279):**
```typescript
const startAcquisition = async (): Promise<boolean> => {
  try {
    setAcquisitionError(null)
    setAcquisitionStartTime(Date.now())
    setFrameCount(0)

    // Backend reads ALL parameters from param_manager (SSoT)
    const result = await sendCommand?.({
      type: 'set_acquisition_mode',
      mode: 'record'
    })

    if (!result?.success) {
      const errorMsg = result?.error || 'Failed to start acquisition'
      setAcquisitionError(errorMsg)
      return false
    }

    return true
  } catch (error) {
    const errorMsg = `Error: ${error instanceof Error ? error.message : String(error)}`
    setAcquisitionError(errorMsg)
    return false
  }
}
```

4. **Simplify stop (lines 281-322, 324-358):**
```typescript
const stopAcquisition = async () => {
  // Stop acquisition (backend handles ALL cleanup)
  await sendCommand?.({ type: 'stop_acquisition' })

  setAcquisitionStartTime(null)
  setAcquisitionStatus(null)
  setFrameCount(0)
}

const stopPreview = async () => {
  setIsPreviewActive(false)

  // Stop acquisition (backend handles ALL cleanup)
  await sendCommand?.({ type: 'stop_acquisition' })

  setAcquisitionStartTime(null)
  setAcquisitionStatus(null)
  setFrameCount(0)
}
```

### 4.2 Testing Strategy

#### Test 1: Preview Mode Verification

**Objective:** Verify preview mode uses unified acquisition loop with phase progression.

**Steps:**
1. Start backend
2. Select camera
3. Switch to preview mode
4. Click "Play"
5. Observe acquisition viewport

**Expected Behavior:**
- [ ] See INITIAL_BASELINE (5s background_luminance)
- [ ] See STIMULUS (animated sweep for all directions)
- [ ] See BETWEEN_TRIALS (5s background_luminance between directions)
- [ ] See FINAL_BASELINE (5s background_luminance)
- [ ] Loop restarts automatically (preview mode)
- [ ] Mini stimulus preview shows current frame
- [ ] Camera feed shows continuous capture
- [ ] Frame counter increments smoothly

**Verification:**
```bash
# Check backend logs for phase transitions
tail -f apps/backend/isi_macroscope.log | grep "Acquisition phase"
```

Expected log output:
```
Acquisition phase: initial_baseline (direction=None)
Acquisition phase: stimulus (direction=LR)
Acquisition phase: between_trials (direction=None)
Acquisition phase: stimulus (direction=RL)
Acquisition phase: between_trials (direction=None)
Acquisition phase: stimulus (direction=TB)
Acquisition phase: between_trials (direction=None)
Acquisition phase: stimulus (direction=BT)
Acquisition phase: final_baseline (direction=None)
Preview mode: looping back to start
```

#### Test 2: Record Mode Verification

**Objective:** Verify record mode uses same acquisition loop, saves all frames with phase tags.

**Steps:**
1. Start backend
2. Select camera
3. Configure acquisition parameters:
   - baseline_sec: 2
   - between_sec: 1
   - cycles: 1
   - directions: ["LR", "RL"]
4. Switch to record mode
5. Click "Record" (confirm filter warning)
6. Wait for completion
7. Check saved data

**Expected Behavior:**
- [ ] See same phase progression as preview
- [ ] Acquisition stops after single run (no loop)
- [ ] All frames saved to disk with phase tags
- [ ] Stimulus events saved with timestamps

**Verification:**
```python
# Check saved data structure
import h5py
import json

session_path = "apps/backend/data/sessions/test_session"

# Check camera frames
with h5py.File(f"{session_path}/LR_camera.h5", 'r') as f:
    print(f"Camera frames: {len(f['frames'])} total")
    print(f"Phases: {list(f['phases'][:])}")
    print(f"Directions: {list(f['directions'][:])}")

    # Verify baseline frames are included
    baseline_frames = [i for i, phase in enumerate(f['phases']) if 'baseline' in phase]
    print(f"Baseline frames: {len(baseline_frames)}")

# Check stimulus events
with open(f"{session_path}/LR_events.json", 'r') as f:
    events = json.load(f)
    print(f"Stimulus events: {len(events)}")
    print(f"First event: {events[0]}")
```

Expected output:
```
Camera frames: 300 total  (includes ALL frames from all phases)
Phases: ['initial_baseline', 'initial_baseline', ..., 'stimulus', 'stimulus', ..., 'between_trials', ..., 'final_baseline', ...]
Directions: [None, None, ..., 'LR', 'LR', ..., None, ..., None, ...]
Baseline frames: 90  (2s initial + 1s between + 2s final = 5s at 30fps)
Stimulus events: 210  (stimulus frames only)
First event: {'display_timestamp_us': 1234567890, 'camera_timestamp_us': 1234567895, 'direction': 'LR', 'time_delta_us': 5}
```

#### Test 3: No Competing Systems

**Objective:** Verify preview stimulus loop cannot run during record mode.

**Steps:**
1. Start backend in preview mode
2. Manually enable presentation stimulus via IPC (should fail)
3. Start record mode
4. Check no preview stimulus loop is active

**Verification:**
```bash
# Check backend logs for defensive cleanup
tail -f apps/backend/isi_macroscope.log | grep "preview stimulus"
```

Expected: No "preview stimulus" mentions during record mode.

#### Test 4: Frame Correspondence Accuracy

**Objective:** Verify camera-stimulus timestamp correspondence with pre-generated stimulus.

**Steps:**
1. Record short session (1 cycle, 1 direction)
2. Analyze timestamp alignment

**Verification:**
```python
import h5py
import json
import numpy as np

session_path = "apps/backend/data/sessions/timing_test"

# Load camera timestamps
with h5py.File(f"{session_path}/LR_camera.h5", 'r') as f:
    camera_timestamps = f['timestamps'][:]

# Load stimulus timestamps
with open(f"{session_path}/LR_events.json", 'r') as f:
    events = json.load(f)
    stimulus_timestamps = [e['display_timestamp_us'] for e in events]

# Calculate frame correspondence
matches = []
for cam_ts in camera_timestamps:
    closest_stim = min(stimulus_timestamps, key=lambda s: abs(s - cam_ts))
    delta = abs(closest_stim - cam_ts)
    matches.append(delta)

print(f"Mean delta: {np.mean(matches)/1000:.2f}ms")
print(f"Std delta: {np.std(matches)/1000:.2f}ms")
print(f"Max delta: {np.max(matches)/1000:.2f}ms")
print(f"Within 5ms: {sum(1 for d in matches if d < 5000)}/{len(matches)}")
```

Expected output:
```
Mean delta: 1.2ms  (typical VSync + capture timing)
Std delta: 0.8ms   (low jitter)
Max delta: 3.5ms   (well within acceptable range)
Within 5ms: 300/300  (100% correspondence accuracy)
```

### 4.3 Migration Checklist

**Phase 1: Preparation**
- [ ] Create feature branch: `git checkout -b unified-acquisition-architecture`
- [ ] Back up current working system
- [ ] Review all files to be modified
- [ ] Ensure all tests pass on current implementation

**Phase 2: Implementation**
- [ ] Create `unified_stimulus.py` with pre-generation logic
- [ ] Update `acquisition/manager.py` with unified loop
- [ ] Update `camera/manager.py` with phase tracking
- [ ] Update `acquisition/recorder.py` with phase tagging
- [ ] Delete `preview_stimulus.py`
- [ ] Delete `camera_stimulus.py`
- [ ] Update `main.py` service wiring
- [ ] Update frontend `AcquisitionViewport.tsx`

**Phase 3: Testing**
- [ ] Test preview mode (verify phase progression)
- [ ] Test record mode (verify data saving)
- [ ] Test mode switching (preview → record)
- [ ] Test frame correspondence accuracy
- [ ] Verify no competing systems can run
- [ ] Load test (10 cycles, 4 directions)

**Phase 4: Validation**
- [ ] Compare recorded data structure to spec
- [ ] Verify baseline frames are saved
- [ ] Verify phase tags are correct
- [ ] Check timestamp alignment quality
- [ ] Performance test (measure FPS stability)

**Phase 5: Documentation**
- [ ] Update architecture diagrams
- [ ] Document SSoT compliance
- [ ] Update API documentation
- [ ] Create migration guide for users

---

## Conclusion

### Critical Findings

The current implementation **VIOLATES the SSoT specification in 5 major areas:**

1. **Competing Stimulus Systems** - Two separate loops can run simultaneously
2. **Divergent Code Paths** - Preview and record use completely different implementations
3. **Scientifically Invalid Timing** - N+1 offset from camera-triggered stimulus
4. **Phase Progression Inconsistency** - Preview mode ignores phase rules
5. **Incomplete Data Recording** - Baseline frames are captured but not saved

### Recommended Solution

**Implement Unified Architecture with Pre-Generated Stimulus:**

1. **Single Acquisition Loop** - Both modes use `_run_acquisition_phases()`
2. **Pre-Generated Stimulus** - Eliminates N+1 offset, scientifically valid
3. **Phase State Machine** - All subsystems synchronized via phase tags
4. **Continuous Recording** - All frames saved with phase/direction tags
5. **Mode Differences Limited** - Only `save_to_disk` and `loop_continuously` differ

### Estimated Effort

- **Implementation:** 16-20 hours
- **Testing:** 8-12 hours
- **Documentation:** 4-6 hours
- **Total:** 28-38 hours (3.5-5 days)

### Success Criteria

After implementation, the system will:

- ✅ Use IDENTICAL acquisition loop for preview and record
- ✅ Follow phase progression in BOTH modes
- ✅ Record ALL frames with phase tags (no missing baselines)
- ✅ Have ONLY ONE stimulus generation system
- ✅ Use pre-generated stimulus (scientifically valid timing)
- ✅ Prevent competing systems from running simultaneously
- ✅ Differ ONLY in: save_to_disk, loop_continuously, presentation_enabled

---

**End of Audit Report**

