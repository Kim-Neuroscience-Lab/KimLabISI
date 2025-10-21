# Camera System

**Last Updated**: 2025-10-15 16:55
**Status**: ✅ Verified - implementation matches documentation
**Maintainer**: Backend Team

> Independent camera frame capture with hardware timestamping for intrinsic signal imaging.

---

## Overview

The Camera System manages camera hardware for continuous frame capture during intrinsic signal imaging experiments. It operates completely independently from the stimulus system, capturing frames at dynamically detected camera FPS with hardware timestamps for post-acquisition synchronization.

## Purpose

The Camera System provides:

- **Independent capture**: Captures frames at dynamically detected camera FPS, completely independent of stimulus display
- **Hardware timestamps**: Records precise hardware timestamp for each captured frame
- **Continuous streaming**: Maintains consistent frame rate throughout acquisition
- **Frame buffering**: Buffers frames in memory for recording or live display (preview is best-effort nicety)

## Architecture

### Independent Capture Thread

**Critical design principle**: Camera runs in separate thread from stimulus with NO triggering or synchronization

```
Camera Thread (dynamically detected FPS)
   ↓
Capture frame from hardware
   ↓
Get hardware timestamp from camera
   ↓
Write frame + timestamp to buffer
   ↓
If recording: Add to data recorder queue (ESSENTIAL)
   ↓
Best-effort publish to shared memory for frontend display (nicety)
   ↓
Loop
```

**Note**: Camera NEVER triggers stimulus display. All camera-triggered stimulus code has been removed from codebase (requires verification).

### Frame Capture Loop

**Continuous operation**:
- Starts when user opens Acquisition viewport
- Runs continuously in background thread WITHOUT PAUSE
- Independent of stimulus state (playing or not)
- Continues capturing during ALL acquisition phases:
  - **Initial baseline**: Camera captures while stimulus displays background luminance
  - **Stimulus sweep**: Camera captures while stimulus displays checkerboard frames
  - **Between-trials**: Camera captures while stimulus displays background luminance
  - **Final baseline**: Camera captures while stimulus displays background luminance
- NEVER pauses or stops during acquisition sequence
- Stops only when explicitly requested or application exits

**Frame rate**:
- Dynamically detected from camera hardware
- Must be detected and stored in Parameter Manager (camera_fps)
- Independent of monitor refresh rate
- Maintains consistent FPS throughout ALL acquisition phases

## Key Features

### Hardware Timestamp Acquisition

**Critical for scientific validity**: Each frame must have precise timestamp

**Timestamp source priority**:
1. **Preferred (Production)**: Camera hardware timestamp (microsecond precision)
   - Required for publication-quality data
   - Provided by industrial cameras (FLIR, Basler, PCO, etc.)
   - Accessed via CAP_PROP_TIMESTAMP in OpenCV

2. **Acceptable (Development/Testing)**: Software timestamp (millisecond precision with ~1-2ms jitter)
   - Generated using `time.time()` at frame capture
   - Suitable for development, UI testing, and algorithm development
   - **Timestamp source recorded in all data files** for scientific provenance
   - Adequate for preliminary experiments and testing

**Verification**:
- System checks if camera supports hardware timestamps on startup
- If not supported: Warning logged, software timestamps used
- Timestamp source explicitly recorded in session metadata and HDF5 attributes

**Storage**:
- Timestamp stored with each frame in memory buffer
- Saved to `timestamps` array in HDF5 during recording

### Frame Buffering

**Memory buffer**:
- Circular buffer holds recent frames
- Allows live display without blocking capture
- Prevents frame drops during disk I/O

**Buffer usage**:
- **Preview mode**: Frames displayed best-effort, not saved (buffer overwritten)
- **Record mode**: Frames queued for data recorder (ESSENTIAL), preview display best-effort (nicety)

**Priority**:
- Camera CAPTURE is ESSENTIAL and MUST NOT be blocked
- Camera DISPLAY (preview) is nicety and best-effort

### Camera Detection and Selection

**Dynamic detection**:
- System enumerates all available cameras on startup
- Updates Parameter Manager with available_cameras list
- NO pre-configured camera - always detected from hardware

**User selection**:
- User can select camera from dropdown in Control Panel during session
- Selection updates Parameter Manager dynamically
- If multiple cameras detected, user can switch between them

**Hardware compatibility**:
- System designed to work with any camera hardware
- Current camera: PCO.panda 4.2
- System should handle any camera with proper driver support
- Resolution is purely dynamic - never assumed

## Data Flow

### Capture Flow (Preview Mode)
1. Camera thread captures frame from hardware
2. Read hardware timestamp from camera
3. Write frame + timestamp to buffer
4. Best-effort publish to shared memory (camera channel) for frontend display (nicety - MUST NOT block capture)
5. Frontend receives frame → displays in Acquisition viewport (best-effort)
6. Buffer overwrites old frames (no disk save)

### Capture Flow (Record Mode)
1. Camera thread captures frame from hardware
2. Read hardware timestamp from camera
3. Write frame + timestamp to buffer
4. **Add to data recorder queue** (ESSENTIAL): {frame, timestamp}
5. Best-effort publish to shared memory (camera channel) for frontend display (nicety - MUST NOT block capture or recording)
6. Frontend receives frame → displays in Acquisition viewport (best-effort)
7. Data recorder flushes queue to HDF5 after acquisition completes

**Priority enforcement**: Recording and capture are ESSENTIAL and MUST NOT be blocked by preview display.

## Integration

### Component Dependencies
- **Parameter Manager**: Provides camera_fps (dynamically detected), selected_camera configuration
- **Shared Memory**: Transfers frames to frontend for live display (best-effort, nicety)
- **Data Recorder**: Queues frames for HDF5 storage (record mode only, ESSENTIAL)
- **IPC**: Broadcasts camera state changes

### Frontend Integration
- **Acquisition Viewport**: Displays live camera feed (best-effort, nicety)
- **Control Panel**: Camera selection dropdown (updates parameters dynamically)

## Behavior

### Camera States

**IDLE**: Camera not opened, no capture running

**OPENED**: Camera opened and ready
- Camera device handle acquired
- Capabilities verified
- Ready to start capture

**CAPTURING**: Continuous frame capture running WITHOUT PAUSE
- Capture thread active
- Continues capturing during ALL acquisition phases (baseline, stimulus, between-trials)
- NEVER pauses during acquisition sequence
- Frames queued for recording (if record mode)
- Frames published to shared memory best-effort (preview)
- Hardware timestamps recorded for every frame

**ERROR**: Camera unavailable or capture failed
- Camera disconnected during capture
- Hardware error
- Thread exception

### Frame Rate Management

**Detected FPS**:
- Read from camera hardware on startup
- Stored in Parameter Manager (camera_fps)
- Used for acquisition timing calculations

**Actual FPS**:
- Measured from hardware timestamps
- May differ from detected due to hardware limitations
- Displayed in frontend for user feedback

### Error Handling

**Camera not available**:
- Error: "Camera not found or already in use"
- Capture does not start
- User directed to check camera connection

**Hardware timestamp not supported**:
- Warning: "Camera does not support hardware timestamps - using software timestamps"
- System continues with software timestamps (`time.time()`)
- Timestamp source recorded in session metadata for scientific provenance
- User warned that publication-quality data requires industrial camera

**Frame drop detected**:
- Warning: "Frame dropped - timestamp gap detected"
- Logged for debugging
- Recording continues but data quality may be affected

## Development Mode

**Purpose**: Enable development and testing with consumer webcams that lack hardware timestamp support.

### Enabling Development Mode

Set `system.development_mode = true` in parameter configuration:

```json
{
  "system": {
    "development_mode": true
  }
}
```

### Development Mode Behavior

**When enabled**:
- ✅ Allows camera acquisition without hardware timestamps
- ✅ Uses software timestamps (`time.time()`) with ~1-2ms jitter
- ⚠️ Logs prominent WARNING on every acquisition start
- ⚠️ Records `"software_dev_mode"` in all data files
- ✅ Suitable for UI development, testing, and algorithm work

**When disabled** (default):
- ❌ Requires hardware timestamps (production mode)
- ❌ Raises RuntimeError if camera lacks hardware timestamp support
- ✅ Enforces scientific validity requirements
- ✅ Production-ready behavior

### Limitations

**Development mode is NOT suitable for**:
- ❌ Scientific publication data
- ❌ Final experiments
- ❌ Data shared with collaborators
- ❌ Any analysis requiring precise timing (<1ms)

**Development mode IS suitable for**:
- ✅ UI development and testing
- ✅ Algorithm development
- ✅ System integration testing
- ✅ Learning the system
- ✅ Preliminary experiments (with clear documentation)

### Data Provenance

All data files explicitly record timestamp source:
- `timestamp_info.camera_timestamp_source = "software_dev_mode"`
- Reviewers and collaborators can see development mode was used
- No ambiguity about data quality

### Production Transition

**Before publication**:
1. Acquire industrial camera (FLIR Blackfly S, Basler ace, PCO.panda)
2. Set `system.development_mode = false`
3. Re-run all final experiments
4. Verify `timestamp_info.camera_timestamp_source = "hardware"`

## Constraints

### Hardware Requirements
- **Camera**: Any camera with proper driver support
  - **Production**: Industrial camera with hardware timestamp support (FLIR, Basler, PCO, etc.)
  - **Development**: Consumer webcam with software timestamp fallback (timestamp source recorded)
- **FPS**: Consistent frame rate (dynamically detected)
- **Timestamps**:
  - Hardware timestamps preferred (industrial cameras)
  - Software timestamps acceptable for development/testing (provenance recorded)
- **Resolution**: Purely dynamic - never assumed

### Performance Requirements
- Frame capture must complete within frame interval (determined by detected FPS)
- Buffer must not overflow (indicates capture slower than camera FPS)
- No frame drops during typical acquisition

### Scientific Validity
- **Hardware timestamps preferred** for phase assignment in analysis
- **Software timestamps acceptable** for development, testing, and preliminary experiments
  - Timestamp source explicitly recorded in all data files
  - Data provenance maintained - reviewers can see timestamp source
  - ~1-2ms jitter may introduce minor phase errors in high-frequency analysis
- **Publication-quality data**: Use industrial camera with hardware timestamps
- Frame rate must be accurately detected (affects phase calculation)

### Dynamic Hardware Detection
- **No hard-coded values**: Camera FPS, resolution all dynamically detected at runtime
- **Camera never pre-configured**: Always detected from connected hardware
- **No assumed resolution**: Camera resolution is purely dynamic
- **No assumed timing**: Frame intervals calculated from detected FPS

### Scientific Validity Protection

**Essential operations** (MUST be protected from blocking):
1. Camera frame capture with hardware timestamps
2. Data recorder queue (in record mode)

**Nicety operations** (best-effort, may drop frames):
1. Shared memory delivery to frontend for preview display

**Priority enforcement**:
- Preview display MUST NOT block camera capture
- Preview display MUST NOT block data recording
- Frame drops in preview are acceptable - frame drops in capture/recording are NOT acceptable

## Camera Parameters

### Required Parameters (from Parameter Manager)

**Camera Group** (`camera`):
- `selected_camera`: Camera device name (dynamically selected by user)
- `camera_fps`: Actual camera frame rate (dynamically detected)
- `camera_width_px`: Frame width in pixels (dynamically detected)
- `camera_height_px`: Frame height in pixels (dynamically detected)
- `available_cameras`: List of detected cameras (auto-populated from hardware enumeration)

### Parameter Configuration

**Camera FPS**:
- Dynamically detected from camera hardware
- Must match actual hardware frame rate
- Incorrect value causes phase assignment errors in analysis
- Verify with hardware detection or measure from timestamps

**Camera selection**:
- Detected: All available cameras enumerated from hardware
- User-selected: Via Control Panel dropdown during session
- Selection updates Parameter Manager dynamically
- Re-detection available via Control Panel

---

**Component Version**: 2.1
**Architecture**: Independent capture thread with hardware timestamping
**Verification Status**: ✅ Verified 2025-10-15
**Verification Details**:
- ✅ Dynamic camera detection (no hard-coded values)
- ✅ Hardware timestamp support with fallback
- ✅ Development mode properly implemented
- ✅ Required camera startup enforced
- ✅ Startup sequence matches documentation
- ✅ ZeroMQ synchronization handshake working
