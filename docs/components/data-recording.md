# Data Recording System

**Last Updated**: 2025-10-15 01:15
**Status**: ✅ Verified - All critical features implemented and verified
**Maintainer**: Backend Team

> HDF5-based session storage for camera frames and stimulus display metadata.

---

## Overview

The Data Recording System manages persistent storage of experimental data during record mode. It buffers camera frames and stimulus display metadata in memory during acquisition, then writes complete datasets to HDF5 files after acquisition completes.

## Purpose

The Data Recording System provides:

- **Camera data storage**: Camera frames + hardware timestamps saved per direction
- **Stimulus data storage**: Display metadata (frame_index + timestamp + angle + direction) saved per direction
- **Session metadata**: All acquisition and hardware parameters saved for reproducibility
- **Atomic writes**: Data written only after successful acquisition (prevents partial sessions)
- **HDF5 format**: Scientific data format with compression and efficient access

**Terminology**: "Display metadata" refers to in-memory tracking of stimulus display events, NOT console logging.

## Architecture

### Data Storage Structure

```
apps/backend/data/sessions/{session_name}/
├── metadata.json                           # Session metadata
├── anatomical.npy                          # Reference anatomical frame
├── LR_camera.h5                            # Camera data for LR direction
│   ├── frames [N, H, W]                    # Camera frames array
│   ├── timestamps [N]                      # Hardware timestamps (μs)
│   └── metadata (attributes)               # Camera parameters
├── LR_stimulus.h5                          # Stimulus data for LR direction
│   ├── frame_indices [M]                   # Displayed frame indices
│   ├── timestamps [M]                      # Display timestamps (μs)
│   ├── angles [M]                          # Visual field angles (degrees)
│   └── metadata (attributes)               # Direction, monitor parameters
├── RL_camera.h5                            # Camera data for RL direction
├── RL_stimulus.h5                          # Stimulus data for RL direction
├── TB_camera.h5                            # Camera data for TB direction
├── TB_stimulus.h5                          # Stimulus data for TB direction
├── BT_camera.h5                            # Camera data for BT direction
└── BT_stimulus.h5                          # Stimulus data for BT direction
```

### Recording Flow

```
Acquisition starts
   ↓
Initialize data recorder with session metadata
   ↓
FOR EACH DIRECTION:
   ├─ start_recording(direction)
   ├─ Camera captures frames → Buffer in memory
   ├─ Stimulus displays frames → Track display metadata in memory
   └─ stop_recording(direction)
   ↓
Acquisition completes
   ↓
Flush all buffers to HDF5 files
   ↓
Save session metadata to JSON
   ↓
Recording complete
```

## Key Features

### Camera Dataset Structure

**File**: `{direction}_camera.h5`

#### Datasets

**frames**: [N_frames, height, width]
- Data type: uint8 or uint16 (depends on camera bit depth, dynamically determined)
- Compression: gzip level 4 (balance speed vs size)
- Chunk size: (1, height, width) for sequential access
- Purpose: Raw camera frames as captured

**timestamps**: [N_frames]
- Data type: int64 (microseconds since epoch)
- No compression (small size, fast access)
- Purpose: Hardware timestamp for each frame

#### Metadata (HDF5 attributes)
- `direction`: Direction label (LR, RL, TB, BT)
- `camera_fps`: Camera frame rate (dynamically detected)
- `camera_name`: Camera device name (dynamically selected)
- `frame_width`: Frame width in pixels (dynamically detected)
- `frame_height`: Frame height in pixels (dynamically detected)
- `bit_depth`: Camera bit depth (dynamically determined)
- `acquisition_start_time`: Unix timestamp
- `total_frames`: Number of frames recorded

**Essential monitor metadata** (saved in camera dataset for reproducibility):
- `monitor_fps`: Monitor refresh rate (dynamically detected)
- `monitor_width_px`: Monitor resolution width (dynamically detected)
- `monitor_height_px`: Monitor resolution height (dynamically detected)
- `monitor_distance_cm`: Viewing distance for spherical projection (essential for visual field calculations)
- `monitor_width_cm`: Physical monitor width (essential for field-of-view calculations)
- `monitor_height_cm`: Physical monitor height (essential for field-of-view calculations)
- `monitor_lateral_angle_deg`: Monitor lateral angle (essential for spherical transform)
- `monitor_tilt_angle_deg`: Monitor tilt angle (essential for spherical transform)

**Critical importance**: All monitor spatial parameters (distance, physical dimensions, angles) are crucial metadata for reproducing visual field calculations and spherical projection used during stimulus generation. These parameters are saved in every camera dataset to ensure scientific reproducibility.

**✅ VERIFIED (2025-10-15)**: Implementation confirmed in `recorder.py` lines 255-264. All 8 monitor metadata attributes correctly saved to camera HDF5 files. See ISSUE-008 resolution.

### Stimulus Dataset Structure

**File**: `{direction}_stimulus.h5`

#### Datasets

**frame_indices**: [N_displayed]
- Data type: int32
- No compression
- Purpose: Which stimulus frame was displayed

**timestamps**: [N_displayed]
- Data type: int64 (microseconds since epoch)
- No compression
- Purpose: Hardware timestamp when frame was displayed

**angles**: [N_displayed]
- Data type: float32 (degrees)
- No compression
- Purpose: Visual field angle represented by displayed frame

**✅ VERIFIED (2025-10-15)**: Implementation confirmed in `recorder.py` lines 210-219. All 3 required datasets (timestamps, frame_indices, angles) correctly created with proper dtypes. See ISSUE-010 resolution.

#### Metadata (HDF5 attributes)
- `direction`: Direction label (LR, RL, TB, BT)
- `total_displayed`: Number of frames displayed
- `sweep_start_angle`: Starting angle (degrees, from parameters)
- `sweep_end_angle`: Ending angle (degrees, from parameters)

**Essential monitor metadata** (saved in stimulus dataset for reproducibility):
- `monitor_fps`: Monitor refresh rate (dynamically detected)
- `monitor_width_px`: Monitor resolution width (dynamically detected)
- `monitor_height_px`: Monitor resolution height (dynamically detected)
- `monitor_distance_cm`: Viewing distance for spherical projection (essential for visual field calculations)
- `monitor_width_cm`: Physical monitor width (essential for field-of-view calculations)
- `monitor_height_cm`: Physical monitor height (essential for field-of-view calculations)
- `monitor_lateral_angle_deg`: Monitor lateral angle (essential for spherical transform)
- `monitor_tilt_angle_deg`: Monitor tilt angle (essential for spherical transform)

**✅ VERIFIED (2025-10-15)**: Implementation confirmed in `recorder.py` lines 221-230. All 8 monitor metadata attributes correctly saved to stimulus HDF5 files. See ISSUE-009 resolution.

### Session Metadata Structure

**File**: `metadata.json`

Example (values are dynamic and depend on hardware/parameters):
```json
{
  "session_name": "my_experiment_20251014_2200",
  "animal_id": "mouse_001",
  "animal_age": "P60",
  "timestamp": 1697324400.123,
  "acquisition": {
    "baseline_sec": 5.0,
    "between_sec": 5.0,
    "cycles": 10,
    "directions": ["LR", "RL", "TB", "BT"]
  },
  "camera": {
    "selected_camera": "PCO.panda 4.2",
    "camera_fps": 30.0,
    "camera_width_px": 2048,
    "camera_height_px": 2048
  },
  "monitor": {
    "monitor_fps": 60.0,
    "monitor_width_px": 3840,
    "monitor_height_px": 2160,
    "monitor_distance_cm": 25.0,
    "monitor_width_cm": 50.0,
    "monitor_height_cm": 28.0,
    "monitor_lateral_angle_deg": 0.0,
    "monitor_tilt_angle_deg": 0.0
  },
  "stimulus": {
    "bar_width_deg": 20.0,
    "bar_speed_deg_per_sec": 9.6,
    "spatial_freq_cpm": 0.05,
    "temporal_freq_hz": 3.0,
    "background_luminance": 0.5,
    "contrast": 0.5
  },
  "timestamp_info": {
    "camera_timestamp_source": "hardware",
    "stimulus_timestamp_source": "hardware",
    "synchronization_method": "independent_parallel_threads",
    "correspondence_method": "post_hoc_timestamp_matching"
  }
}
```

**Note**: All values shown are examples - actual values depend on detected hardware and user-configured parameters.

## Data Flow

### Memory Buffering (During Acquisition)
1. Camera captures frame → adds {frame, timestamp} to buffer
2. Stimulus displays frame → adds {frame_index, timestamp, angle, direction} to display metadata in memory
3. Buffers grow in memory throughout acquisition
4. No disk I/O during acquisition (prevents frame drops)

**Terminology**: "Display metadata" = in-memory tracking of stimulus display events for HDF5 saving, NOT console logging.

### Disk Writing (After Acquisition)
1. Acquisition completes successfully
2. Data recorder creates session directory
3. For each direction:
   - Write camera frames + timestamps to HDF5
   - Write stimulus display metadata to HDF5
4. Write session metadata to JSON
5. Close all HDF5 files
6. Recording complete

### Error Handling
**If acquisition fails**:
- Buffers discarded (no partial session written)
- User can retry without incomplete data cluttering filesystem

**If disk full**:
- Error during write: "Insufficient disk space"
- Partial data may exist (user should delete)
- System prevents acquisition start if disk space low

## Integration

### Component Dependencies
- **Acquisition Manager**: Orchestrates recording start/stop for each direction
- **Camera Manager**: Provides captured frames + timestamps
- **Unified Stimulus Controller**: Provides display metadata (frame_index + timestamp + angle)
- **Parameter Manager**: Provides all session metadata

### Frontend Integration
- **Acquisition Viewport**: Displays recording progress
- **Analysis Viewport**: Loads recorded sessions for analysis
- **Playback Mode**: Replays recorded camera frames

## Behavior

### Recording States

**IDLE**: No recording active, ready to start new session

**RECORDING**: Active recording for specific direction
- Buffer accumulating in memory
- No disk writes yet
- Direction label tracked

**FLUSHING**: Writing buffered data to disk
- All directions recorded
- HDF5 files being created
- Session metadata being saved
- Duration: Depends on data size and disk speed

**COMPLETE**: Session saved to disk
- All HDF5 files closed
- Session appears in session list
- Ready for analysis or playback

### Session Naming

**Default**: `session_{unix_timestamp}`

**User-provided**: From Parameter Manager (`session.session_name`)

**Conflict handling**: If session name exists, append `_N` suffix

## Constraints

### Performance Requirements
- Memory buffers must accommodate full acquisition (size depends on camera FPS, resolution, and acquisition duration)
- HDF5 write must complete in reasonable time (depends on data size and disk speed)
- No disk I/O during acquisition (prevents frame drops)

### Storage Requirements
- Camera data: Depends on resolution, bit depth, compression, frame count
- Stimulus data: Depends on frame count (typically small compared to camera)
- Session metadata: Typically small (kilobytes)
- **Total per session**: Depends on all above factors

### Data Integrity
- Atomic writes: Complete session or nothing (no partial data)
- HDF5 checksums enabled (detects corruption)
- Metadata always saved with data (ensures reproducibility)
- Hardware timestamps preserved with microsecond precision

### Dynamic Size Dependencies
- **No hard-coded storage sizes**: All depends on detected hardware and parameters
- **No assumed frame counts**: Determined by FPS and acquisition duration
- **No assumed resolution**: Determined by detected camera resolution
- **No assumed timing**: Write duration depends on data size and hardware

## HDF5 Configuration

### Compression Settings

**Camera frames**: gzip level 4
- Balance: Speed vs compression ratio
- Compression ratio depends on image content
- Write speed depends on hardware

**Stimulus data**: No compression
- Datasets too small to benefit
- Fast access more important

### Chunk Size

**Camera frames**: (1, H, W)
- Optimized for sequential frame access
- Allows efficient playback
- Matches typical access pattern
- H and W are dynamically detected

### Dataset Creation

**Fixed-size datasets**:
- Frame count known before writing
- More efficient than resizable datasets
- Prevents fragmentation

## Data Recovery

### Incomplete Sessions

**Indicators**:
- Missing HDF5 files for some directions
- metadata.json missing or incomplete
- HDF5 files exist but not closed properly

**Recovery**: Not possible - discard incomplete session

### Corrupted HDF5 Files

**Indicators**:
- HDF5 library reports checksum error
- Cannot open file or read datasets

**Recovery**: Use HDF5 repair tools (h5recover) or discard session

---

**Component Version**: 2.0
**Architecture**: Memory-buffered atomic writes with HDF5 storage
