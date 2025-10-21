# Acquisition System

**Last Updated**: 2025-10-14 23:30
**Status**: ⚠️ Requires verification - documentation reflects intended functionality, not verified implementation
**Maintainer**: Backend Team

> Orchestrates independent parallel thread data collection for intrinsic signal imaging experiments.

---

## Overview

The Acquisition System coordinates all aspects of experimental data collection, managing the timing and synchronization of camera capture, visual stimulus presentation, and data recording. It provides three distinct operational modes (preview, record, playback) that support the full experimental workflow from protocol verification to data collection and review.

## Purpose

The Acquisition System solves the challenge of coordinating independent hardware systems (camera and display monitor) to capture scientifically valid retinotopic mapping data. It ensures:

- **Precise timing**: Hardware-timestamped frame correspondence between camera and stimulus
- **Protocol consistency**: Same acquisition sequence for preview and record modes
- **Data integrity**: Complete metadata preservation for reproducible experiments
- **User workflow**: Smooth transition from testing to recording to review
- **Safety verification**: Filter warning modal before recording ensures correct experimental setup
- **Scientific validity protection**: Camera capture and presentation window stimulus are protected from blocking by preview displays

## Architecture

### Three Operational Modes

#### Preview Mode

**Purpose**: Test the complete acquisition protocol without saving data

- **Sequence**: Full experimental protocol (initial baseline → multi-direction stimulus sweeps → final baseline)
- **Data saving**: DISABLED - no data recorded to disk
- **Presentation monitor**: Defaults to OFF (user can toggle ON)
- **Acquisition viewport**: Displays mini stimulus preview for user monitoring
- **Duration**: Determined by parameters (baseline_sec, cycles, directions, between_sec)
- **Use case**: Verify stimulus appearance, check timing, confirm protocol before actual recording

**Key constraint**: User must manually pre-generate stimulus library in Stimulus Generation viewport before starting preview. If library not ready, system displays error prompt directing user to pre-generate first.

#### Record Mode

**Purpose**: Execute full acquisition and save all data

- **Sequence**: Same full experimental protocol as preview mode
- **Data saving**: ENABLED - all camera frames and stimulus display logs saved to HDF5
- **Presentation monitor**: Always ON (not user-controllable) - displays stimulus to subject
- **Acquisition viewport**: Displays mini stimulus preview for user monitoring (NOT the same as presentation monitor)
- **Filter verification**: System displays filter warning modal before starting - user must confirm correct filters are in place
- **Duration**: Determined by parameters (baseline_sec, cycles, directions, between_sec)
- **Use case**: Actual experimental data collection for scientific analysis

**Key constraint**: User must manually pre-generate stimulus library first. If library not ready, system displays error prompt.

**Safety feature**: Filter warning modal is a crucial safety check to ensure user has installed correct optical filters before recording.

#### Playback Mode

**Purpose**: Replay recorded acquisition sessions

- **Behavior**: Automatically replays the full recorded sequence (not a static frame viewer)
- **Presentation monitor**: Defaults to OFF (user can toggle ON) - same as preview mode
- **Acquisition viewport**: Displays camera frames from recording
- **Controls**: Play/pause, skip forward/backward, stop (NO direction switching by user)
- **Data source**: Loads from HDF5 files in `apps/backend/data/sessions/{session_name}/`
- **Playback sequence**: Replays all directions in recorded order automatically
- **Use case**: Review recorded data, verify acquisition quality, prepare for analysis

### Acquisition Sequence

Both preview and record modes execute this sequence:

```
1. INITIAL_BASELINE (baseline_sec duration)
   - Stimulus system displays ONLY background luminance (from stimulus.background_luminance parameter)
   - Camera continues capturing frames throughout (NEVER pauses)
   - NO checkerboard stimulus displayed
   - Purpose: Establish baseline cortical activity before stimulus presentation
   ↓
2. FOR EACH DIRECTION (per directions parameter):
   ↓
   FOR EACH CYCLE (per cycles parameter):
   ↓
   2a. STIMULUS (sweep_duration_sec)
       - Stimulus controller displays pre-generated checkerboard frames sweeping across visual field
       - Camera captures cortical response frames independently
       - Both record hardware timestamps for post-hoc matching
       - NO synchronization between camera and stimulus threads
   ↓
   2b. BETWEEN_TRIALS (between_sec duration)
       - Stimulus system displays ONLY background luminance (from stimulus.background_luminance parameter)
       - Camera continues capturing frames (NEVER pauses)
       - NO checkerboard stimulus displayed
       - Purpose: Allow cortical activity to return to baseline between stimulus sweeps
   ↓
3. FINAL_BASELINE (baseline_sec duration)
   - Stimulus system displays ONLY background luminance (from stimulus.background_luminance parameter)
   - Camera continues capturing frames (NEVER pauses)
   - NO checkerboard stimulus displayed
   - Purpose: Establish final baseline for normalization in analysis
   ↓
4. COMPLETE
   - If record mode: Save all buffered data to HDF5
   - Stop camera capture and stimulus display
```

**Critical behavior**:
- **Baseline and between-trials phases**: Display ONLY background luminance (uniform gray screen), NO checkerboard stimulus
- **Camera capture**: Continues WITHOUT PAUSE throughout ALL phases (baseline, stimulus, between-trials)
- **Background luminance**: From `stimulus.background_luminance` parameter (NOT hard-coded value)
- **Independent threads**: Camera and stimulus run on separate threads with independent timing

## Key Features

### Hardware-Timestamp Synchronization

**Critical design principle**: Camera and stimulus run as **independent parallel threads** with NO triggering between them.

- **Camera thread**: Captures frames at dynamically detected camera FPS
  - Each frame records hardware timestamp from camera
  - Continuous capture throughout acquisition
  - Independent timing, not synchronized to stimulus

- **Stimulus thread**: Displays frames at dynamically detected monitor refresh rate
  - Each displayed frame records: hardware timestamp, frame_index, angle, direction
  - VSync-locked to monitor refresh rate
  - Independent timing, not synchronized to camera

- **Frame correspondence**: Post-acquisition analysis matches camera timestamps with stimulus timestamps to assign phase to each camera frame

**Note**: Stimulus is NEVER triggered by camera events. All camera-triggered stimulus code has been removed from codebase (requires verification).

### Dual Stimulus Display

The system provides two different stimulus views during acquisition:

#### Acquisition Viewport (User Monitoring - Nicety)
- **Purpose**: Allow user to monitor stimulus during acquisition
- **Location**: Embedded in Acquisition viewport in desktop application
- **Size**: Mini preview (reduced resolution)
- **Modes**: Visible in preview, record, and playback modes
- **Controls**: No user interaction - display only
- **Priority**: LOW - this is a nicety for user convenience
- **Critical constraint**: MUST NOT block camera capture or presentation window stimulus

#### Presentation Window (Subject Display - Essential)
- **Purpose**: Display full-resolution stimulus to experimental subject
- **Location**: Full-screen on secondary monitor
- **Size**: Full monitor resolution with spherical projection
- **Preview mode**: Defaults OFF, user can toggle ON
- **Record mode**: Always ON (not user-controllable)
- **Playback mode**: Defaults OFF, user can toggle ON
- **Priority**: HIGH - essential for scientific validity
- **Critical constraint**: MUST NOT be blocked by any other system

**Critical difference**:
- **Acquisition viewport preview**: Nicety for user - NOT essential - MUST NOT block essential operations
- **Presentation window**: Essential for scientific validity - MUST be protected at all cost
- **Camera capture**: Essential for scientific validity - MUST be protected at all cost

### Camera Preview Display

The acquisition viewport displays live camera feed during acquisition:

- **Purpose**: Allow user to monitor camera capture during acquisition
- **Priority**: LOW - this is a nicety for user convenience
- **Critical constraint**: MUST NOT block camera capture or presentation window stimulus
- **Frame delivery**: Best-effort basis - frames may be dropped from preview without affecting saved data
- **Essential vs nicety**: Camera CAPTURE is essential; camera DISPLAY is nicety

### Pre-Generation Requirement

The system requires stimulus library to be pre-generated before starting preview or record mode:

- **User workflow**: User must visit Stimulus Generation viewport and click "Pre-Generate All Directions"
- **Pre-generation duration**: Depends on hardware performance and stimulus parameters
- **Memory persistence**: Library stays loaded across mode switches
- **Error handling**: If user attempts preview/record without pre-generation, system displays modal: "Please pre-generate stimulus in Stimulus Generation tab before starting acquisition"

**What changed**: Auto-generation during acquisition start has been removed. System now prompts user instead of blocking on auto-generation.

### Filter Warning Modal

Before starting record mode, the system displays a filter warning modal:

- **Purpose**: Crucial safety feature to ensure user has installed correct optical filters
- **Behavior**: Modal blocks acquisition start until user confirms
- **User action**: User must verify filters are correct and confirm to proceed
- **Bypass**: Not available - this is a required safety check

### Data Recording

In record mode, the system saves two datasets per direction:

#### Camera Dataset (`{direction}_camera.h5`)
- **frames**: [N_frames, height, width] array of camera frames
- **timestamps**: [N_frames] array of hardware timestamps (microseconds)
- **metadata**: Camera parameters, acquisition settings, monitor parameters, session info

#### Stimulus Dataset (`{direction}_stimulus.h5`)
- **frame_indices**: [N_displayed] array of stimulus frame indices
- **timestamps**: [N_displayed] array of hardware timestamps (microseconds) when each frame was displayed
- **angles**: [N_displayed] array of visual field angles (degrees) for each displayed frame
- **metadata**: Direction label, monitor parameters, stimulus configuration

**Essential metadata**: Monitor parameters are saved in both datasets as essential metadata for acquisition reproducibility.

**Post-acquisition analysis** matches the camera timestamps array with the stimulus timestamps array to determine which stimulus angle corresponds to each camera frame, enabling phase calculation for retinotopic mapping.

## Data Flow

### Preview Mode Flow
1. User clicks Play in Acquisition viewport
2. System checks: Is stimulus library pre-generated?
3. If NO: Display error modal → "Please pre-generate first"
4. If YES: Start acquisition sequence
5. Camera captures frames (hardware timestamps) - ESSENTIAL, protected from blocking
6. Stimulus displays frames (hardware timestamps + metadata) on presentation window (if toggled ON) - ESSENTIAL, protected from blocking
7. Acquisition viewport shows mini stimulus preview (user monitoring) - nicety, best-effort
8. Acquisition viewport shows camera feed (user monitoring) - nicety, best-effort
9. Sequence completes automatically (all directions) → Stop camera and stimulus
10. No data saved to disk

### Record Mode Flow
1. User clicks Record in Acquisition viewport
2. System displays filter warning modal
3. User confirms correct filters are in place
4. System checks: Is stimulus library pre-generated?
5. If NO: Display error modal → "Please pre-generate first"
6. If YES: Start acquisition sequence
7. Data recorder initialized with session metadata (includes monitor parameters)
8. Camera captures frames → Records hardware timestamps → Saves to memory buffer - ESSENTIAL, protected from blocking
9. Stimulus displays frames on presentation window → Records hardware timestamps + frame_index + angle → Saves to display log - ESSENTIAL, protected from blocking
10. Acquisition viewport shows mini stimulus preview (user monitoring) - nicety, best-effort
11. Acquisition viewport shows camera feed (user monitoring) - nicety, best-effort
12. Sequence completes automatically (all directions) → Write all buffered data to HDF5
13. Session saved to `apps/backend/data/sessions/{session_name}/`

### Playback Mode Flow
1. User selects session from list
2. System loads session metadata
3. System loads all HDF5 files for all directions
4. User clicks Play → Frames replay automatically for all directions in sequence
5. Acquisition viewport displays recorded camera frames - nicety, best-effort
6. Presentation window can optionally display stimulus (defaults OFF, user can toggle ON)
7. Playback continues through all directions automatically (NO user direction switching)
8. User can pause, scrub, change speed
9. Frontend displays historical frames with acquisition timeline

**Note**: User cannot manually switch directions during playback. The sequence plays through all directions automatically.

## Integration

### Component Dependencies
- **Camera Manager**: Provides camera frame capture with hardware timestamps (dynamically detected)
- **Unified Stimulus Controller**: Provides pre-generated stimulus playback with display logging
- **Parameter Manager**: Provides acquisition configuration (baseline_sec, cycles, directions, background_luminance, etc.)
- **Shared Memory**: Transfers camera and stimulus frames to frontend (best-effort for preview)
- **IPC System**: Broadcasts acquisition progress events to frontend
- **Data Recorder**: Saves camera frames and stimulus display log to HDF5

### Frontend Integration
- **Acquisition Viewport**: Displays live camera feed, mini stimulus preview, real-time plots, acquisition controls
- **Stimulus Generation Viewport**: Pre-generates stimulus library (required before acquisition)
- **Presentation Window**: Displays full-screen stimulus on secondary monitor (preview/playback: optional, record: always on)

## Behavior

### Camera Selection

**Dynamic detection**:
- System enumerates all available cameras on startup
- Camera list is dynamically populated based on connected hardware
- NO pre-configured camera in parameters - always detected at runtime

**User selection**:
- User can select camera from dropdown in Control Panel during session
- Selection updates Parameter Manager dynamically
- If multiple cameras detected, user can switch between them
- Parameter system is updated when user changes camera selection

**Hardware compatibility**:
- System designed to work with any camera hardware
- Current camera: PCO.panda 4.2
- System should handle any camera with proper driver support
- Resolution is purely dynamic - never assumed

### Phase Transitions

The acquisition manager coordinates phase transitions with precise timing:

- **IDLE**: No acquisition running, system ready
- **INITIAL_BASELINE**: Stimulus displays ONLY background luminance (uniform gray), camera continues capturing baseline frames (NO pause)
- **STIMULUS**: Stimulus displays checkerboard sweep for current direction/cycle, camera continues capturing evoked response frames (NO pause)
- **BETWEEN_TRIALS**: Stimulus displays ONLY background luminance (uniform gray), camera continues capturing recovery frames (NO pause)
- **FINAL_BASELINE**: Stimulus displays ONLY background luminance (uniform gray), camera continues capturing final baseline frames (NO pause)
- **COMPLETE**: All data saved (if record mode), camera and stimulus stopped, system returns to IDLE

### Error Handling

**Stimulus not pre-generated**:
- Modal displayed: "Please pre-generate stimulus in Stimulus Generation tab before starting acquisition"
- Acquisition does not start
- User directed to Stimulus Generation viewport

**Camera not available**:
- Error message: "Camera not available or not detected"
- Acquisition does not start
- User directed to check camera connection and hardware detection

**Parameter validation failure**:
- Error message details missing/invalid parameters
- Common issues: directions empty, invalid baseline/cycle values
- Acquisition does not start until parameters corrected

**Filter warning not confirmed**:
- Record mode cannot start until user confirms filter warning modal
- This is a required safety check

### Presentation Monitor Control

**Preview Mode**:
- Default: Presentation monitor OFF (stimulus only in acquisition viewport mini preview)
- User can toggle: Checkbox "Show on Presentation Monitor"
- When toggled ON: Stimulus displayed full-screen on secondary monitor

**Record Mode**:
- Presentation monitor ALWAYS ON (not user-controllable)
- Stimulus displayed full-screen on secondary monitor throughout acquisition
- Ensures stimulus visibility matches what subjects see during experiments

**Playback Mode**:
- Default: Presentation monitor OFF (same as preview mode)
- User can toggle: Checkbox "Show on Presentation Monitor"
- When toggled ON: Recorded stimulus displayed full-screen on secondary monitor

## Constraints

### User Requirements
- **Must pre-generate**: User cannot start acquisition without manually pre-generating stimulus first
- **Must confirm filters**: User must confirm filter warning before recording
- **Camera must be detected**: At least one camera must be detected by hardware enumeration
- **Monitor must be detected**: At least one display must be available for presentation window

### Timing Requirements
- **Hardware timestamps only**: System uses ONLY hardware timestamps for frame correspondence, never software timing
- **Independent threads**: Camera and stimulus timing are completely independent, no synchronization
- **Post-hoc matching**: Phase assignment happens during post-acquisition analysis, not real-time

### Data Integrity
- **Complete metadata**: All acquisition parameters AND monitor parameters saved with session for reproducibility
- **Hardware timestamp source**: Camera and stimulus must provide hardware timestamps (software fallback NOT supported)
- **Atomic saves**: Data written to HDF5 only after full acquisition completes (prevents partial session files)

### Dynamic Hardware Detection
- **No hard-coded values**: All hardware parameters dynamically detected at runtime
- **Camera**: Detected from connected hardware, never pre-configured
- **Monitor**: Refresh rate and resolution dynamically detected
- **Resolution**: Camera resolution is purely dynamic, never assumed
- **No assumed memory sizes**: Memory requirements depend on user-set parameters and detected hardware
- **No assumed timing**: All durations determined by parameters, not hard-coded

### Scientific Validity Protection

**Essential operations** (MUST be protected from blocking):
1. Camera frame capture with hardware timestamps
2. Presentation window stimulus display with hardware timestamps

**Nicety operations** (best-effort, may drop frames):
1. Acquisition viewport camera preview
2. Acquisition viewport stimulus preview

**Priority enforcement**:
- Preview displays MUST NOT block essential camera capture
- Preview displays MUST NOT block essential presentation window stimulus
- Data recording happens in memory buffer - disk writes occur after acquisition completes
- Frame drops in preview are acceptable - frame drops in capture/presentation are NOT acceptable

### Legacy Code Removal

**Verification required**:
- Complete removal of camera-triggered stimulus architecture must be verified
- Old triggering code may still exist in codebase
- Documentation reflects intended functionality, not necessarily current implementation
- Audit needed to confirm all old systems have been removed

---

**Component Version**: 2.0
**Architecture**: Independent parallel threads with hardware timestamp synchronization
**Verification Status**: ⚠️ Legacy camera-triggered code removal needs verification
