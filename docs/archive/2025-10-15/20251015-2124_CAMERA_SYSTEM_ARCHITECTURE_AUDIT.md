# Camera System Architecture Audit Report
**Date**: 2025-10-15
**System**: ISI Macroscope Camera Data Flow
**Status**: ❌ CRITICAL ARCHITECTURAL VIOLATION FOUND

---

## Executive Summary

**CRITICAL ISSUE IDENTIFIED**: Camera system reports "degraded" status because camera acquisition is being started **BEFORE** shared memory frame readers are initialized on the frontend. This violates the ZeroMQ "slow joiner" synchronization pattern and causes frame loss.

**Root Cause**: The `_handle_shared_memory_ready()` handler (lines 2126-2156 in `/Users/Adam/KimLabISI/apps/backend/src/main.py`) starts camera acquisition when the frontend signals readiness, but the camera may already be open from hardware verification, causing frames to be published before subscribers connect.

**Impact**:
- Camera frames published to port 5559 are lost if frontend subscriber not ready
- Frontend never receives initial frames, causing "degraded" status
- Race condition in startup sequence

---

## 1. Camera Frame Data Flow (As Designed)

### 1.1 Backend: Camera Manager → Shared Memory

**File**: `/Users/Adam/KimLabISI/apps/backend/src/camera/manager.py`

#### Camera Capture Loop (Lines 572-789)
```python
def _acquisition_loop(self):
    """Continuous camera frame capture loop (runs in separate thread)."""

    while not self.stop_acquisition_event.is_set():
        # STEP 1: Capture camera frame
        frame = self.capture_frame()  # Line 644

        # STEP 2: Get hardware timestamp
        capture_timestamp = self.get_camera_hardware_timestamp_us()  # Line 648

        # STEP 3: Crop to square and convert to RGBA
        cropped = self.crop_to_square(frame)  # Line 687
        rgba = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGBA)  # Line 691

        # STEP 4: Write to shared memory for frontend display
        self.shared_memory.write_camera_frame(
            rgba,
            camera_name=camera_name,
            capture_timestamp_us=capture_timestamp,
        )  # Lines 733-737
```

**Channel Used**: `write_camera_frame()` method (dedicated camera channel)

---

### 1.2 Backend: Shared Memory Service Publishing

**File**: `/Users/Adam/KimLabISI/apps/backend/src/ipc/shared_memory.py`

#### Camera Frame Publishing (Lines 340-421)
```python
def write_camera_frame(
    self,
    frame_data: np.ndarray,
    camera_name: str = "unknown",
    capture_timestamp_us: Optional[int] = None,
    exposure_us: Optional[int] = None,
    gain: Optional[float] = None,
) -> int:
    """Write camera frame to shared memory on separate channel.

    Returns:
        Frame ID
    """
    # Write frame data to camera shared memory buffer
    self.camera_shm_mmap[
        self.camera_write_offset : self.camera_write_offset + data_size
    ] = frame_bytes  # Line 375-377

    # Create metadata
    camera_metadata = CameraFrameMetadata(
        frame_id=self.camera_frame_counter,
        timestamp_us=timestamp_us,
        capture_timestamp_us=capture_timestamp_us,
        width_px=frame_data.shape[1],
        height_px=frame_data.shape[0],
        data_size_bytes=data_size,
        offset_bytes=self.camera_write_offset,
        camera_name=camera_name,
        exposure_us=exposure_us,
        gain=gain,
    )  # Lines 386-397

    # Publish metadata to ZeroMQ
    self.camera_metadata_socket.send_json(metadata_msg, zmq.NOBLOCK)  # Line 410
```

**Port**: 5559 (camera metadata port)
**Shared Memory Path**: `/tmp/stimulus_stream_camera_shm`

---

### 1.3 Frontend: Electron Shared Memory Reader

**File**: `/Users/Adam/KimLabISI/apps/desktop/src/electron/main.ts`

#### Camera Frame Reader Initialization (Lines 518-522)
```typescript
cameraFrameReader = await initializeWithRetry(
  'Camera frame reader',
  'camera-frame',  // IPC channel name
  IPC_CONFIG.CAMERA_METADATA_PORT  // Port 5559
)
```

#### Frame Metadata Listener (Lines 76-92)
```typescript
private async startMetadataListener(): Promise<void> {
  for await (const [msg] of this.zmqSocket!) {
    try {
      const metadata = JSON.parse(msg.toString())
      await this.handleFrameMetadata(metadata)  // Forward to renderer
    } catch (error) {
      mainLogger.error('Error processing frame metadata:', error)
    }
  }
}
```

**Connects To**: `tcp://localhost:5559` (camera metadata port)
**Subscribes To**: All messages (no topic filter)
**IPC Channel**: `camera-frame` → forwards to renderer process

---

### 1.4 Frontend: React Component Subscription

**File**: `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx`

#### Camera Frame Handler (Lines 676-748)
```typescript
useEffect(() => {
  const handleCameraFrame = async (metadata: any) => {
    // Read frame data from shared memory
    const frameDataBuffer = await window.electronAPI.readSharedMemoryFrame(
      metadata.offset_bytes,
      metadata.data_size_bytes,
      metadata.shm_path  // /tmp/stimulus_stream_camera_shm
    )

    // Create ImageData from RGBA buffer
    const imageData = new ImageData(
      new Uint8ClampedArray(frameDataBuffer),
      width,
      height
    )

    // Render to canvas
    ctx.putImageData(imageData, 0, 0)
  }

  // Subscribe to camera frames
  let unsubscribe: (() => void) | undefined
  if (window.electronAPI?.onCameraFrame) {
    unsubscribe = window.electronAPI.onCameraFrame(handleCameraFrame)
  }

  return () => {
    unsubscribe?.()
  }
}, [])  // Always listen, no dependencies
```

**Listens On**: `window.electron.onCameraFrame()` event
**Reads From**: Shared memory file at `/tmp/stimulus_stream_camera_shm`

---

## 2. Camera Initialization Sequence

### 2.1 Backend Startup Flow

**File**: `/Users/Adam/KimLabISI/apps/backend/src/main.py`

#### Step 1: Hardware Verification (Lines 1615-1872)
```python
def _verify_hardware(camera, param_manager, ipc) -> Dict[str, Any]:
    """Verify all hardware during startup before reporting ready state."""

    # Detect cameras (may open first camera)
    detected_cameras = camera.detect_cameras(force=True, keep_first_open=True)  # Line 1654

    # Try to open the selected camera
    if camera_to_use:
        if camera.open_camera(camera_to_use[0]):
            logger.info(f"Camera '{camera_to_use[1]}' opened at index {camera_to_use[0]}")
        # Line 1707
```

**⚠️ ISSUE**: Camera is opened during hardware verification, but acquisition is NOT started here.

#### Step 2: Frontend Ready Handler (Lines 2012-2123)
```python
def _handle_frontend_ready(services: Dict[str, Any], cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Handle frontend_ready message, verify hardware, and send system_state: ready."""

    # 1. Verify hardware (cameras, displays)
    hardware_check = _verify_hardware(camera, param_manager, ipc)  # Line 2034

    # Note: Camera acquisition NOT started here
    # Will be started after frontend sends shared_memory_readers_ready signal
    # (Line 2071-2073)

    # 4. Send system_state ready message
    ipc.send_sync_message({
        "type": "system_state",
        "state": "ready",
        "is_ready": True,
    })  # Lines 2105-2113
```

**⚠️ ISSUE**: Camera is open but NOT streaming yet.

#### Step 3: Shared Memory Ready Handler (Lines 2126-2156)
```python
def _handle_shared_memory_ready(services: Dict[str, Any], cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Handle shared_memory_readers_ready message and start camera acquisition."""

    camera = services["camera"]

    # Start camera acquisition now that frontend is ready to receive frames
    if camera.active_camera and camera.active_camera.isOpened():
        try:
            camera.start_acquisition()  # Line 2154
            logger.info("Camera acquisition started for preview (after frame readers ready)")

            # Broadcast camera state for frontend
            ipc.send_sync_message({
                "type": "camera_state_changed",
                "is_running": True,
                "timestamp": time.time()
            })  # Lines 2158-2162
        except Exception as e:
            logger.warning(f"Failed to start camera acquisition: {e}")
```

**✅ CORRECT DESIGN**: Camera acquisition starts AFTER frontend signals shared memory readers are ready.

---

### 2.2 Frontend Startup Flow

**File**: `/Users/Adam/KimLabISI/apps/desktop/src/electron/main.ts`

#### Step 1: Backend ZeroMQ Ready (Lines 581-598)
```typescript
if (message.type === 'zeromq_ready') {
  logger.info('Backend ZeroMQ ready - initializing ALL subscriptions...')

  // Initialize health and sync channels
  await this.initializeZeroMQConnections()

  // CRITICAL FIX: Initialize shared memory frame readers BEFORE frontend_ready signal
  await this.initializeSharedMemoryReader()  // Line 591

  logger.info('All ZeroMQ subscriptions established (including frame readers)')

  // Send explicit ready signal to backend
  await this.sendStartupCommand({ type: 'shared_memory_readers_ready' })  // Line 596
}
```

#### Step 2: Initialize Shared Memory Readers (Lines 470-550)
```typescript
private async initializeSharedMemoryReader(): Promise<void> {
  // Initialize stimulus frame reader (port 5557)
  sharedMemoryReader = await initializeWithRetry(
    'Stimulus frame reader',
    'shared-memory-frame',
    IPC_CONFIG.SHARED_MEMORY_PORT
  )

  // Initialize camera frame reader (port 5559)
  cameraFrameReader = await initializeWithRetry(
    'Camera frame reader',
    'camera-frame',
    IPC_CONFIG.CAMERA_METADATA_PORT  // 5559
  )

  // Initialize analysis frame reader (port 5561)
  analysisFrameReader = await initializeWithRetry(
    'Analysis frame reader',
    'analysis-frame',
    IPC_CONFIG.ANALYSIS_METADATA_PORT
  )
}
```

**✅ CORRECT DESIGN**: All shared memory readers initialized BEFORE sending `shared_memory_readers_ready` signal.

---

## 3. ❌ CRITICAL ISSUE IDENTIFIED

### 3.1 The Problem

**Timing Race Condition**: The ZeroMQ "slow joiner" problem is occurring in the camera system.

**Sequence of Events** (as observed):
1. Backend starts and initializes shared memory service
2. Backend verifies hardware and **opens camera** (line 1707 in `_verify_hardware()`)
3. Backend sends `zeromq_ready` message to frontend
4. Frontend receives `zeromq_ready` and initializes frame readers
5. Frontend sends `shared_memory_readers_ready` to backend
6. **Backend starts camera acquisition** (line 2154 in `_handle_shared_memory_ready()`)
7. Camera starts publishing frames to port 5559 immediately
8. **⚠️ RACE CONDITION**: Frontend may not have completed ZeroMQ subscription yet

**Why This Happens**:
- ZeroMQ PUB/SUB has inherent "slow joiner" problem
- Publisher can send messages before subscriber connects
- Even with 100ms delay (line 113 in `main.ts`), network timing is unpredictable
- Camera starts streaming immediately after `start_acquisition()` returns

### 3.2 Evidence of the Issue

**From System Status**: Camera is reporting "degraded" state
**Expected Behavior**: Camera should report "online" if frames are flowing correctly
**Actual Behavior**: Frontend not receiving initial camera frames

**Code Path Analysis**:
- Camera Manager `_acquisition_loop()` starts immediately when `start_acquisition()` is called (line 809-812)
- Frames are published to shared memory without any acknowledgment from frontend
- If frontend subscriber not ready, first few frames are lost
- Frontend shows "degraded" status because no frames received

### 3.3 Why Current Synchronization Is Insufficient

The code attempts to prevent this with:
1. ✅ 100ms delay after `zeromq_ready` (line 113, `main.ts`)
2. ✅ Initialize readers BEFORE sending `shared_memory_readers_ready` (line 591, `main.ts`)
3. ✅ Backend waits for `shared_memory_readers_ready` before starting camera (line 2154, `main.py`)

**But this is NOT enough** because:
- 100ms delay is arbitrary and not guaranteed
- `initializeSharedMemoryReader()` is async and may not complete instantly
- Network timing is unpredictable
- Camera starts publishing **immediately** after `start_acquisition()` returns

---

## 4. Recommended Fixes

### Option 1: Add Explicit Subscriber Ready Signal (BEST)

**Concept**: Frontend sends explicit `camera_subscriber_ready` message AFTER ZeroMQ subscription is confirmed active.

**Implementation**:
1. Add `await cameraFrameReader.waitForFirstMessage()` in frontend
2. Send `camera_subscriber_ready` signal to backend
3. Backend waits for this signal before calling `camera.start_acquisition()`

**Pros**:
- Eliminates race condition completely
- Explicit handshake ensures subscriber is ready
- No arbitrary delays

**Cons**:
- Requires additional IPC message
- Slightly more complex startup flow

---

### Option 2: Backend Self-Test Before Publishing

**Concept**: Backend verifies frontend subscriber is connected before starting camera.

**Implementation**:
1. Backend sends test frame to port 5559 after `shared_memory_readers_ready`
2. Frontend sends acknowledgment when test frame received
3. Backend waits for ack before starting continuous camera acquisition

**Pros**:
- Guarantees frontend is listening
- No lost frames

**Cons**:
- Adds latency to startup
- Requires test frame protocol

---

### Option 3: Increase Delay and Add Retry Logic (SUBOPTIMAL)

**Concept**: Increase delay to 500ms-1000ms and add retry if frontend still not ready.

**Implementation**:
1. Increase delay from 100ms to 500ms
2. Check frontend connection status before starting camera
3. Retry if not ready

**Pros**:
- Minimal code changes

**Cons**:
- ❌ Still a race condition (just less likely)
- ❌ Arbitrary delays hurt UX
- ❌ Not a principled solution

---

## 5. Port Configuration Verification

### 5.1 Backend Configuration

**File**: `/Users/Adam/KimLabISI/apps/backend/src/ipc/shared_memory.py`

```python
def __init__(
    self,
    stream_name: str = "stimulus_stream",
    buffer_size_mb: int = 100,
    metadata_port: int = 5557,  # Stimulus frames
    camera_metadata_port: int = 5559,  # ✅ Camera frames
    analysis_metadata_port: int = 5561  # Analysis frames
):
```

**Camera Port**: 5559 ✅ CORRECT

---

### 5.2 Frontend Configuration

**File**: `/Users/Adam/KimLabISI/apps/desktop/src/config/constants.ts`

```typescript
export const IPC_CONFIG = {
  SHARED_MEMORY_PORT: 5557,  // Stimulus
  CAMERA_METADATA_PORT: 5559,  // ✅ Camera
  ANALYSIS_METADATA_PORT: 5561,  // Analysis
}
```

**Camera Port**: 5559 ✅ CORRECT

---

### 5.3 Port Binding Verification

**Backend Initialization** (`shared_memory.py`, lines 192-196):
```python
# Camera metadata socket (separate channel)
self.camera_metadata_socket = self.zmq_context.socket(zmq.PUB)
self.camera_metadata_socket.bind(
    f"tcp://*:{self.camera_metadata_port}"  # 5559
)
```

**Frontend Subscription** (`main.ts`, line 62):
```typescript
this.zmqSocket.connect(`tcp://localhost:${zmqPort}`)  // 5559
```

**Port Matching**: ✅ CORRECT

---

## 6. Shared Memory File Paths

### 6.1 Backend Writing

**File**: `/Users/Adam/KimLabISI/apps/backend/src/ipc/shared_memory.py`

```python
# Initialize CAMERA shared memory buffer
camera_path = f"/tmp/{self.stream_name}_camera_shm"  # /tmp/stimulus_stream_camera_shm
self.camera_shm_fd = os.open(
    camera_path, os.O_CREAT | os.O_RDWR | os.O_TRUNC, 0o666
)
```

**Path**: `/tmp/stimulus_stream_camera_shm` ✅

---

### 6.2 Frontend Reading

**File**: `/Users/Adam/KimLabISI/apps/desktop/src/electron/main.ts`

```typescript
ipcMain.handle('read-shared-memory-frame', async (_event, offset: number, size: number, shmPath: string) => {
  // Read directly from the specified shared memory file
  if (!fs.existsSync(shmPath)) {
    throw new Error(`Shared memory file does not exist: ${shmPath}`)
  }

  const fd = fs.openSync(shmPath, 'r')
  const buffer = Buffer.alloc(size)
  const bytesRead = fs.readSync(fd, buffer, 0, size, offset)
  fs.closeSync(fd)

  return buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength)
})
```

**Path**: Provided by metadata (should be `/tmp/stimulus_stream_camera_shm`) ✅

---

## 7. System Health Monitoring

### 7.1 Backend Health Broadcast

**File**: `/Users/Adam/KimLabISI/apps/backend/src/main.py`

```python
def broadcast_component_health(health_status):
    """Collect and broadcast component health status."""
    camera = self.services["camera"]
    shared_memory = self.services["shared_memory"]
    hardware_status = {
        "multi_channel_ipc": "online",
        "parameters": "online",
        "display": "online",
        "camera": "online" if camera.active_camera and camera.active_camera.isOpened() else "offline",  # Line 136
        "realtime_streaming": "online" if shared_memory._stream and shared_memory._stream._running else "offline",  # Line 137
        "analysis": "online",
    }
```

**Camera Status Logic**:
- Reports "online" if `camera.active_camera` exists and is opened
- Reports "offline" otherwise
- **Does NOT check** if camera is actively streaming frames

**⚠️ ISSUE**: Health check only verifies camera is OPENED, not that frames are flowing.

---

### 7.2 Why Camera Reports "Degraded"

**Hypothesis**: Camera is:
1. ✅ Detected during hardware verification
2. ✅ Opened successfully
3. ✅ Acquisition started
4. ❌ Frames not reaching frontend due to race condition

**Health Status**:
- Backend reports: `camera: "online"` (because camera is opened)
- Frontend reports: "degraded" (because no frames received)

---

## 8. Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│ BACKEND (Python)                                                        │
│                                                                         │
│  ┌──────────────────┐      ┌──────────────────┐                       │
│  │ Camera Manager   │─────▶│ Shared Memory    │                       │
│  │                  │      │ Service          │                       │
│  │ _acquisition_loop│      │                  │                       │
│  │   capture_frame()│      │ write_camera_    │                       │
│  │   crop_to_square()      │   frame()         │                       │
│  │   COLOR_BGR2RGBA │      │                  │                       │
│  └──────────────────┘      └─────────┬────────┘                       │
│                                      │                                │
│                                      ▼                                │
│                          ┌─────────────────────────┐                  │
│                          │ ZeroMQ PUB Socket       │                  │
│                          │ Port: 5559              │                  │
│                          │                         │                  │
│                          │ Publishes metadata:     │                  │
│                          │ - frame_id              │                  │
│                          │ - timestamp_us          │                  │
│                          │ - width, height         │                  │
│                          │ - offset_bytes          │                  │
│                          │ - shm_path              │                  │
│                          └─────────┬───────────────┘                  │
└────────────────────────────────────┼────────────────────────────────────┘
                                     │
                                     │ TCP/IP
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ FRONTEND (Electron Main Process)                                       │
│                                                                         │
│                          ┌─────────────────────────┐                  │
│                          │ ZeroMQ SUB Socket       │                  │
│                          │ Port: 5559              │                  │
│                          │                         │                  │
│                          │ Subscribes to:          │                  │
│                          │   tcp://localhost:5559  │                  │
│                          └─────────┬───────────────┘                  │
│                                    │                                  │
│                                    ▼                                  │
│                    ┌──────────────────────────────┐                   │
│                    │ SharedMemoryFrameReader      │                   │
│                    │                              │                   │
│                    │ handleFrameMetadata():       │                   │
│                    │   1. Parse JSON metadata     │                   │
│                    │   2. Forward to renderer:    │                   │
│                    │      mainWindow.webContents  │                   │
│                    │        .send('camera-frame') │                   │
│                    └──────────────┬───────────────┘                   │
└───────────────────────────────────┼─────────────────────────────────────┘
                                    │ IPC
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ FRONTEND (Renderer Process / React)                                    │
│                                                                         │
│  ┌──────────────────────────────────────────┐                         │
│  │ AcquisitionViewport.tsx                  │                         │
│  │                                          │                         │
│  │ useEffect(() => {                        │                         │
│  │   const handleCameraFrame = async () => {│                         │
│  │     // 1. Read from shared memory        │                         │
│  │     const buffer = await                 │                         │
│  │       window.electronAPI                 │                         │
│  │         .readSharedMemoryFrame(          │                         │
│  │           offset_bytes,                  │                         │
│  │           data_size_bytes,               │                         │
│  │           "/tmp/stimulus_stream_camera_shm"│                       │
│  │         )                                │                         │
│  │                                          │                         │
│  │     // 2. Create ImageData               │                         │
│  │     const imageData = new ImageData(     │                         │
│  │       new Uint8ClampedArray(buffer),     │                         │
│  │       width, height                      │                         │
│  │     )                                    │                         │
│  │                                          │                         │
│  │     // 3. Render to canvas               │                         │
│  │     ctx.putImageData(imageData, 0, 0)    │                         │
│  │   }                                      │                         │
│  │                                          │                         │
│  │   window.electronAPI.onCameraFrame(      │                         │
│  │     handleCameraFrame                    │                         │
│  │   )                                      │                         │
│  │ }, [])                                   │                         │
│  └──────────────────────────────────────────┘                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Acquisition Manager Integration

### 9.1 Camera Acquisition NOT Started by Acquisition Manager

**File**: `/Users/Adam/KimLabISI/apps/backend/src/acquisition/manager.py`

The acquisition manager does NOT start camera acquisition. It assumes camera is already streaming.

**Line 218-221**:
```python
# Defensive cleanup: ensure camera is streaming
if not self.camera.is_streaming:
    logger.info("Starting camera acquisition for record mode (defensive startup)")
    if not self.camera.start_acquisition():
        return {"success": False, "error": "Failed to start camera"}
```

**This is DEFENSIVE** - acquisition manager checks if camera is streaming, and starts it if not. But the primary camera startup happens in `_handle_shared_memory_ready()`.

---

## 10. Conclusion

### 10.1 Architecture Assessment

**Overall Design**: ✅ SOLID
**Communication Channels**: ✅ CORRECT (port 5559 for camera)
**Shared Memory Paths**: ✅ CORRECT (`/tmp/stimulus_stream_camera_shm`)
**Data Flow**: ✅ WELL STRUCTURED (camera → shared memory → ZeroMQ → frontend)

**CRITICAL ISSUE**: ❌ RACE CONDITION IN STARTUP

---

### 10.2 Specific Issues

| Issue | Location | Severity | Impact |
|-------|----------|----------|--------|
| Race condition in camera startup | `main.py:2154` | 🔴 CRITICAL | Frames lost before subscriber ready |
| Health check doesn't verify frame flow | `main.py:136` | 🟡 MEDIUM | "degraded" status not detected correctly |
| No subscriber ready confirmation | `main.ts:591` | 🟡 MEDIUM | No guarantee subscriber is active |
| Arbitrary 100ms delay insufficient | `main.ts:113` | 🟡 MEDIUM | Network timing unpredictable |

---

### 10.3 Recommended Fix Priority

**Priority 1** (CRITICAL - Fix Immediately):
- Add explicit subscriber ready signal from frontend AFTER ZeroMQ subscription confirmed active
- Backend waits for this signal before starting camera acquisition
- Eliminates race condition completely

**Priority 2** (HIGH - Improve Health Monitoring):
- Add frame flow verification to health check
- Report "degraded" if camera open but no frames flowing for > 2 seconds
- Helps diagnose future issues

**Priority 3** (MEDIUM - Add Telemetry):
- Log timestamp of first frame received by frontend
- Log timestamp of camera acquisition start
- Calculate delta to measure race condition timing

---

## 11. Files Requiring Changes

### 11.1 Backend Changes

**File**: `/Users/Adam/KimLabISI/apps/backend/src/main.py`

**Lines 2126-2156**: `_handle_shared_memory_ready()`
- Add wait for explicit `camera_subscriber_confirmed` signal
- Only start camera after confirmation received

---

### 11.2 Frontend Changes

**File**: `/Users/Adam/KimLabISI/apps/desktop/src/electron/main.ts`

**Lines 470-550**: `initializeSharedMemoryReader()`
- Add `waitForFirstMessage()` method to `SharedMemoryFrameReader`
- Send `camera_subscriber_confirmed` after ZeroMQ subscription active

**Lines 49-135**: `SharedMemoryFrameReader` class
- Add method to verify subscription is active (e.g., receive test message)

---

## 12. Implementation Roadmap

### Phase 1: Add Subscriber Confirmation (1 hour)

1. ✅ Add `camera_subscriber_confirmed` message type
2. ✅ Frontend sends confirmation after ZeroMQ subscription established
3. ✅ Backend waits for confirmation before starting camera
4. ✅ Test with multiple restarts to verify no race condition

### Phase 2: Improve Health Monitoring (30 minutes)

1. ✅ Add frame flow verification to health check
2. ✅ Report "degraded" if no frames for > 2 seconds
3. ✅ Test with camera disconnected

### Phase 3: Add Telemetry (30 minutes)

1. ✅ Log startup timing metrics
2. ✅ Measure time between camera start and first frame received
3. ✅ Add dashboard for monitoring startup performance

---

## CRITICAL VIOLATIONS SUMMARY

### ❌ VIOLATION 1: Race Condition in Camera Startup
**Principle Violated**: Synchronization Invariant
**Location**: `/Users/Adam/KimLabISI/apps/backend/src/main.py:2154`
**Issue**: Camera acquisition starts before frontend subscriber confirmed ready
**Impact**: Frame loss, "degraded" status
**Fix**: Add explicit subscriber ready signal

### ❌ VIOLATION 2: Health Check Insufficient
**Principle Violated**: Observable State Invariant
**Location**: `/Users/Adam/KimLabISI/apps/backend/src/main.py:136`
**Issue**: Health check only verifies camera is OPENED, not that frames are FLOWING
**Impact**: "degraded" status not properly detected
**Fix**: Add frame flow verification to health check

### ❌ VIOLATION 3: Arbitrary Timing Delays
**Principle Violated**: Explicit Synchronization
**Location**: `/Users/Adam/KimLabISI/apps/desktop/src/electron/main.ts:113`
**Issue**: 100ms delay is arbitrary and not guaranteed sufficient
**Impact**: Race condition still possible under network stress
**Fix**: Replace with explicit handshake protocol

---

**END OF AUDIT REPORT**
