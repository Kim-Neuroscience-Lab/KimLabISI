# Stimulus System

**Last Updated**: 2025-10-14 23:26
**Status**: ⚠️ Requires verification - documentation reflects intended functionality, not verified implementation
**Maintainer**: Backend Team

> GPU-accelerated visual stimulus generation and playback system for retinotopic mapping.

---

## Overview

The Stimulus System generates GPU-accelerated checkerboard patterns for retinotopic mapping experiments. It consists of two main components: **StimulusGenerator** (GPU rendering with PyTorch) and **UnifiedStimulusController** (pre-generation and playback orchestration).

## Purpose

The Stimulus System provides:

- **Pre-generated stimulus library**: All frames generated once, stored as raw numpy arrays in memory for zero-overhead playback
- **GPU acceleration**: Uses CUDA (NVIDIA), MPS (Apple Metal), or CPU fallback via PyTorch for maximum performance
- **Hardware timestamp tracking**: Records display timestamp + frame_index + angle + direction for each displayed frame in memory
- **Independent playback**: Runs in separate thread from camera, VSync-locked to dynamically detected monitor refresh rate
- **Memory efficiency**: Bi-directional optimization reduces memory footprint by 50%
- **Single source of truth**: Unified controller used by both preview and record modes

## Architecture

### Two-Layer Design

#### Layer 1: StimulusGenerator
**Responsibility**: GPU-accelerated frame rendering

- **Technology**: PyTorch (GPU: CUDA/MPS, fallback: CPU)
- **Output**: Grayscale checkerboard patterns with spherical projection correction
- **Resolution**: Matches dynamically detected monitor resolution
- **Frame generation**: On-demand rendering using GPU-accelerated tensor operations

#### Layer 2: UnifiedStimulusController
**Responsibility**: Pre-generation, playback orchestration, display metadata tracking

- **Pre-generation**: Generates all directions once, stores as raw numpy arrays in memory (NO compression)
- **Playback loop**: Background thread displays frames at dynamically detected monitor refresh rate (VSync-locked)
- **Display metadata tracking**: Records hardware timestamp + frame_index + angle + direction for each frame in memory
- **Shared memory delivery**: Publishes frames to shared memory for frontend preview (best-effort, nicety)

### Component Hierarchy

```
UnifiedStimulusController
   ├─ StimulusGenerator (PyTorch GPU rendering)
   ├─ SharedMemory (frame delivery to frontend - best-effort)
   ├─ IPC (event broadcasting)
   └─ ParameterManager (configuration source of truth)
```

## Key Features

### GPU Acceleration

**Hardware detection**:
- **Priority**: CUDA (NVIDIA GPUs) > MPS (Apple Metal/Silicon) > CPU fallback
- **Framework**: PyTorch for cross-platform GPU acceleration
- **Performance**: GPU acceleration significantly speeds up frame generation
- **Fallback**: Automatic fallback to CPU if no GPU available

**Operations accelerated**:
- Spherical coordinate transformation
- Checkerboard pattern generation
- Frame rendering and compositing

### Pre-Generation

**Purpose**: Generate all stimulus frames once for instant, zero-overhead playback

**Process**:
1. User clicks "Pre-Generate All Directions" in Stimulus Generation viewport
2. System generates LR direction (frame count determined by parameters, stored as raw numpy arrays)
3. System generates TB direction (frame count determined by parameters, stored as raw numpy arrays)
4. Derives RL from LR (reverses BOTH frame order AND angle order, stores all 4 directions in library)
5. Derives BT from TB (reverses BOTH frame order AND angle order, stores all 4 directions in library)
6. Broadcasts completion event

**Storage format**: Raw grayscale numpy arrays (uint8, H×W) - NO compression
**Reason**: Zero decompression overhead during playback, essential for maintaining consistent frame rate during recording

**Duration**: Depends on hardware performance (GPU vs CPU) and stimulus parameters

**Memory**: Depends on monitor resolution and frame count (bi-directional optimization provides 50% savings by generating only 2 directions, but all 4 directions stored in library)

### Hardware Timestamp and Metadata Tracking

**Critical feature**: System tracks display metadata for each displayed frame in memory

**Data tracked per frame** (stored in memory during acquisition):
- **timestamp**: Hardware timestamp (microseconds since epoch) when frame was displayed
- **frame_index**: Which frame in the sequence (indexed from 0)
- **angle**: Visual field angle (degrees) represented by this frame
- **direction**: Sweep direction (LR, RL, TB, BT)

**Purpose**: This in-memory stimulus display metadata becomes the **stimulus dataset** saved to HDF5 during record mode. Post-acquisition analysis matches stimulus timestamps with camera timestamps to assign phase to each camera frame.

**Important**: This is NOT console logging for debugging - this is the scientific data required for retinotopic mapping analysis, accumulated in memory for saving to HDF5.

### Independent Playback

**Critical design principle**: Stimulus thread runs completely independently from camera thread

- **Stimulus thread**: Displays at dynamically detected monitor refresh rate, VSync-locked
- **Camera thread**: Captures at dynamically detected camera FPS, independent timing
- **NO triggering**: Camera NEVER triggers stimulus display
- **NO synchronization**: Threads run on separate timelines with independent hardware timestamps
- **Frame correspondence**: Determined post-acquisition by matching hardware timestamps

**Note**: Stimulus is NEVER triggered by camera events. All camera-triggered stimulus code has been removed from codebase (requires verification).

### Bi-Directional Optimization

**Key insight**: RL is time-reversed LR, BT is time-reversed TB

**Implementation**:
- Generate LR: GPU-accelerated generation, stored as raw numpy arrays
- Derive RL: Reverse BOTH frame list AND angle list (all 4 directions stored in library)
- Generate TB: GPU-accelerated generation, stored as raw numpy arrays
- Derive BT: Reverse BOTH frame list AND angle list (all 4 directions stored in library)

**Memory savings**: 50% reduction in generation time (only generate 2 directions), but all 4 directions stored for instant access

**Note**: Even though derived, all 4 directions are saved in the pre-generated library

### VSync-Locked Playback

**Purpose**: Ensure smooth, consistent stimulus display at monitor refresh rate (crucial for scientific validity)

**Mechanism**:
- Playback loop runs in background thread
- Each frame: Get grayscale numpy array from library → Convert to RGBA → Display on presentation window
- NO decompression step (frames stored as raw numpy arrays for zero overhead)
- Frame also published to shared memory for frontend preview (best-effort, MUST NOT block presentation window)
- Loop timing matched to dynamically detected monitor refresh rate using VSync approximation
- Loop continues until stop_playback() called

**Zero-overhead design**: Frames transferred as numpy arrays directly, no decompression processing during playback/recording

**Priority**: Presentation window display is ESSENTIAL and MUST NOT be blocked by preview delivery

## Data Flow

### Pre-Generation Flow
1. User clicks "Pre-Generate All Directions" in Stimulus Generation viewport
2. Frontend sends `unified_stimulus_pregenerate` command
3. Backend broadcasts `pregeneration_started` event
4. UnifiedStimulusController generates all frames using GPU acceleration (duration depends on hardware and parameters)
5. Frames stored as raw numpy arrays (NO compression)
6. Backend broadcasts `pregeneration_complete` event with statistics
7. Frontend displays "Complete ✓" badge
8. Library with all 4 directions stays in memory, ready for preview/record

### Playback Flow (Preview or Record Mode)
1. Acquisition manager starts acquisition sequence
2. For each direction/cycle: calls `unified_stimulus.start_playback(direction)`
3. Playback thread starts in background
4. **For each frame in loop**:
   - Get grayscale numpy array from library (NO decompression - zero overhead)
   - Convert grayscale to RGBA (lightweight operation)
   - Display on presentation window (ESSENTIAL - protected from blocking)
   - Best-effort publish to shared memory for frontend preview (nicety - may drop frames)
   - **Track display metadata in memory**: {timestamp, frame_index, angle, direction}
5. Acquisition manager calls `unified_stimulus.stop_playback()`
6. Playback thread exits gracefully
7. In-memory display metadata contains complete record of displayed frames with hardware timestamps

### Display Metadata Usage (Record Mode)
1. During acquisition: display metadata accumulates in memory
2. After acquisition completes: data recorder saves display metadata to `{direction}_stimulus.h5`
3. Dataset contains: frame_indices array, timestamps array, angles array, direction metadata
4. Post-acquisition analysis: match stimulus timestamps with camera timestamps to assign phase

**Terminology clarification**: "Display metadata" refers to in-memory tracking of stimulus display events for HDF5 saving, NOT console logging.

## Integration

### Component Dependencies
- **StimulusGenerator**: GPU frame rendering (PyTorch with CUDA/MPS/CPU)
- **Parameter Manager**: Configuration source (spatial frequency, temporal frequency, etc.)
- **Shared Memory**: Frame delivery to frontend (best-effort, nicety)
- **IPC**: Event broadcasting (pregeneration_started, pregeneration_complete)
- **Acquisition Manager**: Orchestrates playback timing during acquisition

### Frontend Integration
- **Stimulus Generation Viewport**: Displays pre-generation progress, shows status badge, has similar controls to playback mode
- **Acquisition Viewport**: Displays mini stimulus preview during preview/record (nicety - best-effort)
- **Presentation Window**: Displays full-screen stimulus on secondary monitor (ESSENTIAL - protected from blocking)

## Behavior

### Pre-Generation Requirement

**User must pre-generate before acquisition**:
- If user attempts preview/record without pre-generation: error modal displayed
- Modal message: "Please pre-generate stimulus in Stimulus Generation tab before starting acquisition"
- Acquisition does NOT start until library is pre-generated
- **No auto-generation**: System prompts user instead of auto-generating

**Library persistence**:
- Library stays loaded across mode switches (preview ↔ record)
- Library invalidated only when stimulus or relevant monitor parameters change
- Re-generation required after parameter changes (bar width, spatial frequency, monitor dimensions, etc.)

### Playback States

**IDLE**: No playback active, library may or may not be loaded

**PLAYING**: Playback loop running for specific direction
- Only one direction can play at a time
- Attempting to start second playback while first is running: error returned
- Stop current playback before starting new direction

**Library Status**:
- **library_loaded: false**: Pre-generation required before any playback
- **library_loaded: true**: All 4 directions ready for playback

### Error Handling

**Library not pre-generated**:
- Error message: "Direction LR not pre-generated. Call pre_generate_all_directions() first."
- User directed to Stimulus Generation viewport

**Playback already running**:
- Error message: "Playback already running - stop current playback first"
- Frontend should call stop_playback() before starting new direction

**Invalid frame index**:
- Error message: "Frame not available: LR[999]"
- Check frame_index is within valid range

## Constraints

### Performance Requirements
- Pre-generation duration depends on hardware (GPU significantly faster than CPU) and stimulus parameters
- Playback must maintain consistent frame rate at dynamically detected monitor refresh rate
- NO decompression overhead during playback (frames stored as raw numpy arrays)
- Presentation window display MUST NOT be blocked by preview delivery

### Memory Requirements
- Library size depends on monitor resolution and frame count
- Frames stored as raw grayscale numpy arrays (uint8, H×W)
- Bi-directional optimization provides 50% generation time savings
- All 4 directions stored in library for instant access
- Peak memory during pre-generation includes temporary buffers

### Hardware Requirements
- GPU: CUDA-capable NVIDIA GPU or Apple Silicon/Metal (MPS) for acceleration (CPU fallback available)
- Display with stable refresh rate (dynamically detected)
- Hardware timestamp source for display (system clock with microsecond precision)

### Dynamic Hardware Detection
- **No hard-coded values**: Monitor resolution and refresh rate dynamically detected
- **No assumed memory sizes**: Depends on detected resolution and user parameters
- **No assumed timing**: Frame timing based on detected monitor refresh rate
- **No assumed frame counts**: Determined by user parameters
- **GPU auto-detection**: Automatic detection of available GPU acceleration

### Scientific Validity Protection

**Essential operations** (MUST be protected from blocking):
1. Presentation window stimulus display with hardware timestamps
2. Display metadata tracking in memory
3. Zero-overhead playback (no decompression)

**Nicety operations** (best-effort, may drop frames):
1. Shared memory delivery to frontend for preview display

**Priority enforcement**:
- Presentation window display MUST NOT be blocked by preview delivery
- Display metadata tracking happens in-thread (no blocking)
- Preview frame drops are acceptable - presentation window drops are NOT acceptable
- No processing overhead during recording (frames stored ready-to-use)

## Stimulus Parameters

### Required Parameters (from Parameter Manager)

**Stimulus Group** (`stimulus`):
- `bar_width_deg`: Bar width in degrees of visual angle
- `bar_speed_deg_per_sec`: Bar sweep speed
- `spatial_freq_cpm`: Checkerboard spatial frequency (cycles per meter)
- `temporal_freq_hz`: Checkerboard temporal frequency (Hz, flickering)
- `background_luminance`: Background gray level (0.0-1.0)
- `contrast`: Checkerboard contrast (0.0-1.0)

**Monitor Group** (`monitor`):
- `monitor_fps`: Display refresh rate (dynamically detected, essential)
- `monitor_width_px`: Display resolution width (dynamically detected, essential)
- `monitor_height_px`: Display resolution height (dynamically detected, essential)
- `monitor_distance_cm`: Viewing distance for spherical projection (essential metadata)
- `monitor_width_cm`: Physical monitor width for FOV calculation (essential metadata)
- `monitor_height_cm`: Physical monitor height for FOV calculation (essential metadata)
- `monitor_lateral_angle_deg`: Monitor lateral angle for spherical transform (essential metadata)
- `monitor_tilt_angle_deg`: Monitor tilt angle for spherical transform (essential metadata)

**Note**: All monitor parameters (distance, physical dimensions, angles) are crucial metadata for reproducing visual field calculations and spherical projection.

### Parameter Change Behavior

**When stimulus parameters change**:
- Library is invalidated (cleared from memory)
- User must re-run pre-generation
- Ensures stimulus always matches current parameter configuration

**When monitor spatial parameters change** (dimensions, distance, angles):
- Library is invalidated (affects spherical projection and FOV)
- User must re-run pre-generation

**When non-spatial parameters change**:
- Library is NOT invalidated
- Pre-generation not required
- Example: changing acquisition baseline_sec does not affect stimulus library

## Library Persistence

**Added**: 2025-10-16

The stimulus system now supports saving and loading pre-generated stimulus libraries to/from disk. This allows users to:
- Save generated libraries for reuse across sessions
- Load previously generated libraries without re-generation (~10s vs ~30-60s)
- Avoid repeated generation when parameters haven't changed

### Save/Load Features

**Save Library** (`unified_stimulus_save_library` command):
- Saves all 4 directions to HDF5 files with gzip compression (level 4)
- Embeds generation parameters as metadata
- Default location: `data/stimulus_library/`
- Total size: ~2.5-3.2 GB compressed
- Frontend: "Save to Disk" button (enabled when library exists)

**Load Library** (`unified_stimulus_load_library` command):
- Loads pre-generated library from disk
- **Critical**: Validates parameters match before loading
- If mismatch detected, returns detailed error showing which parameters differ
- Optional `force=True` bypasses validation (advanced use only)
- Frontend: "Load from Disk" button with parameter mismatch detection

### Parameter Validation

When loading a saved library, the system validates that ALL stimulus-affecting parameters match:

**Monitor Parameters Validated**:
- Resolution: `monitor_width_px`, `monitor_height_px`
- Timing: `monitor_fps`
- Physical geometry: `monitor_width_cm`, `monitor_height_cm`, `monitor_distance_cm`
- Angles: `monitor_lateral_angle_deg`, `monitor_tilt_angle_deg`

**Stimulus Parameters Validated**:
- All parameters in `stimulus` group: `bar_width_deg`, `checker_size_deg`, `drift_speed_deg_per_sec`, `contrast`, `background_luminance`, etc.

**Validation Failure**:
- Load operation aborted
- Frontend displays red error panel with list of mismatched parameters
- Shows saved vs current value for each mismatch
- User must regenerate library with current parameters

**Validation Success**:
- Library loaded into memory (~10s)
- Frontend displays green "Loaded from disk" badge
- Library ready for preview/record modes

### Storage Format

**Directory Structure**:
```
data/stimulus_library/
  ├── LR_frames.h5       (~600-800 MB compressed)
  ├── RL_frames.h5       (~600-800 MB compressed)
  ├── TB_frames.h5       (~600-800 MB compressed)
  ├── BT_frames.h5       (~600-800 MB compressed)
  └── library_metadata.json  (~1 KB)
```

**HDF5 Structure** (per direction):
```
{direction}_frames.h5:
  /frames [dataset]      - 3D array (num_frames, height, width) uint8
  /angles [dataset]      - 1D array of float32 angles (degrees)
  .attrs:
    - generation_params  - JSON string of monitor + stimulus params
    - direction         - Direction string (LR/RL/TB/BT)
    - num_frames        - Total frame count
    - frame_shape       - (height, width)
```

**Metadata JSON**:
```json
{
  "generation_params": {
    "monitor": { "monitor_fps": 60, ... },
    "stimulus": { "bar_width_deg": 15.0, ... }
  },
  "directions": ["LR", "RL", "TB", "BT"],
  "timestamp": 1234567890.123,
  "total_frames": 12000
}
```

### UI Integration

**Stimulus Generation Viewport**:
- Three buttons: "Pre-Generate All Directions" | "Load from Disk" | "Save to Disk"
- "Save to Disk" only enabled when library exists in memory
- Status badges show load/save success or errors
- Parameter mismatch panel shows detailed validation failures

**Workflow**:
1. **Save**: Pre-generate → Click "Save to Disk" → Green badge appears
2. **Load**: Click "Load from Disk" → Parameters validated → Library loaded or error shown
3. **Mismatch**: Red error panel shows which parameters differ and requires regeneration

### Performance

**Save**: ~10-15 seconds (4 directions, ~12,000 frames)
**Load**: ~8-12 seconds (faster than generation)
**Validation**: <1ms (negligible overhead)

### Scientific Integrity

Parameter validation is **required by default** to prevent:
- Using stimulus with wrong spatial frequency
- Using stimulus with wrong monitor geometry
- Using stimulus with wrong temporal parameters
- Any parameter mismatch that could invalidate experimental results

The `force=True` option exists for advanced debugging but should never be used for data collection.

**Related Documentation**:
- [Feature Implementation Details](../changes/2025-10-16-1100_stimulus_library_save_load_feature.md)

---

**Component Version**: 2.1
**Architecture**: GPU-accelerated pre-generation with zero-overhead VSync-locked playback + disk persistence
**Verification Status**: ⚠️ Legacy camera-triggered code removal needs verification
