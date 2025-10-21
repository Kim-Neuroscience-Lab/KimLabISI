# Unified Stimulus Controller - Quick Reference

## IPC Commands

### Pre-generate Stimulus Library

**Command:** `unified_stimulus_pregenerate`

**Description:** Generate and compress all 4 sweep directions (LR, RL, TB, BT). Call once at startup.

**Request:**
```json
{
  "type": "unified_stimulus_pregenerate"
}
```

**Response:**
```json
{
  "success": true,
  "statistics": {
    "total_frames": 2400,
    "total_memory_bytes": 419430400,
    "directions": {
      "LR": {
        "frames": 600,
        "size_bytes": 209715200,
        "avg_frame_bytes": 349525,
        "duration_sec": 12.5
      },
      "RL": { /* same as LR */ },
      "TB": { /* similar to LR */ },
      "BT": { /* same as TB */ }
    }
  },
  "total_duration_sec": 25.3
}
```

---

### Start Playback

**Command:** `unified_stimulus_start_playback`

**Description:** Start continuous VSync-locked playback loop for given direction.

**Request:**
```json
{
  "type": "unified_stimulus_start_playback",
  "direction": "LR",
  "monitor_fps": 60.0
}
```

**Response:**
```json
{
  "success": true,
  "direction": "LR",
  "fps": 60.0,
  "total_frames": 600
}
```

**Notes:**
- Only one playback can be active at a time
- Call `unified_stimulus_stop_playback` before starting a new direction
- Playback loops continuously until stopped

---

### Stop Playback

**Command:** `unified_stimulus_stop_playback`

**Description:** Stop current playback loop.

**Request:**
```json
{
  "type": "unified_stimulus_stop_playback"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Playback stopped: LR"
}
```

---

### Get Frame for Viewport

**Command:** `unified_stimulus_get_frame`

**Description:** Get single frame for viewport display (scrubbing, preview).

**Request:**
```json
{
  "type": "unified_stimulus_get_frame",
  "direction": "LR",
  "frame_index": 150
}
```

**Response:**
```json
{
  "success": true,
  "frame_id": 12345,
  "direction": "LR",
  "frame_index": 150
}
```

**Notes:**
- Frame is written to shared memory, use `frame_id` to retrieve
- Frame is RGBA format (H, W, 4) ready for display
- No need to stop playback to get frames

---

### Get Status

**Command:** `unified_stimulus_get_status`

**Description:** Get current controller status and library statistics.

**Request:**
```json
{
  "type": "unified_stimulus_get_status"
}
```

**Response:**
```json
{
  "success": true,
  "is_playing": true,
  "current_direction": "LR",
  "current_fps": 60.0,
  "library_loaded": true,
  "library_status": {
    "LR": {
      "frames": 600,
      "memory_mb": 200.5
    },
    "RL": {
      "frames": 600,
      "memory_mb": 200.5
    },
    "TB": {
      "frames": 600,
      "memory_mb": 200.5
    },
    "BT": {
      "frames": 600,
      "memory_mb": 200.5
    }
  }
}
```

---

### Clear Display Log

**Command:** `unified_stimulus_clear_log`

**Description:** Clear display event log (for fresh recording).

**Request:**
```json
{
  "type": "unified_stimulus_clear_log",
  "direction": "LR"  // Optional: clear specific direction, or omit to clear all
}
```

**Response:**
```json
{
  "success": true,
  "message": "Display log cleared"
}
```

---

## Typical Usage Patterns

### Pattern 1: Startup Initialization

```typescript
// 1. Wait for backend ready
await waitForBackendReady()

// 2. Pre-generate stimulus library
console.log("Pre-generating stimulus library...")
const result = await ipc.send({type: "unified_stimulus_pregenerate"})
console.log(`Pre-generation complete: ${result.statistics.total_frames} frames, ${result.total_duration_sec}s`)
```

### Pattern 2: Preview Mode (Continuous Playback)

```typescript
// Start continuous playback for preview
const result = await ipc.send({
  type: "unified_stimulus_start_playback",
  direction: "LR",
  monitor_fps: 60.0
})

// Playback runs in background...

// Stop when done
await ipc.send({type: "unified_stimulus_stop_playback"})
```

### Pattern 3: Viewport Scrubbing

```typescript
// User scrubs slider to frame 150
const result = await ipc.send({
  type: "unified_stimulus_get_frame",
  direction: "LR",
  frame_index: 150
})

// Display frame from shared memory
displayFrameFromSharedMemory(result.frame_id)
```

### Pattern 4: Record Mode (with frame correspondence logging)

```typescript
// 1. Clear display log before recording
await ipc.send({
  type: "unified_stimulus_clear_log",
  direction: "LR"
})

// 2. Start playback during recording
await ipc.send({
  type: "unified_stimulus_start_playback",
  direction: "LR",
  monitor_fps: 60.0
})

// 3. Recording happens...
// Display events are logged automatically in background

// 4. Stop playback when done
await ipc.send({type: "unified_stimulus_stop_playback"})

// 5. Display log now contains precise timestamp + frame_index + angle for each displayed frame
// This enables camera-stimulus frame correspondence analysis
```

### Pattern 5: Switching Directions

```typescript
// Stop current direction
await ipc.send({type: "unified_stimulus_stop_playback"})

// Start new direction
await ipc.send({
  type: "unified_stimulus_start_playback",
  direction: "TB",  // Changed from LR to TB
  monitor_fps: 60.0
})
```

---

## Display Event Log Structure

Each displayed frame is logged with:

```typescript
interface StimulusDisplayEvent {
  timestamp_us: number      // Display timestamp (microseconds since epoch)
  frame_index: number       // Frame index in sweep (0 to total_frames-1)
  angle_degrees: number     // Bar angle at this frame
  direction: string         // Sweep direction ("LR", "RL", "TB", "BT")
}
```

**Usage:**
- Access via Python backend: `unified_stimulus.get_display_log("LR")`
- Enables post-hoc camera-stimulus correspondence analysis
- Each camera frame can be matched to nearest stimulus frame via timestamp

---

## Memory Usage

**Typical values for 1728×1117 monitor:**
- LR: ~200 MB (600 frames × ~350 KB/frame)
- RL: ~0 MB additional (references LR)
- TB: ~200 MB (600 frames × ~350 KB/frame)
- BT: ~0 MB additional (references TB)
- **Total: ~400 MB for all 4 directions**

**Comparison to unoptimized approach:**
- Uncompressed RGBA: ~18 GB (4 directions × 600 frames × 7.5 MB/frame)
- **Savings: 45x reduction**

---

## Performance Characteristics

**Pre-generation (one-time):**
- LR + TB generation: ~10-15 seconds on M1 Mac
- PNG compression: ~5-10 seconds
- RL + BT derivation: <1 second (list reversal)
- **Total: ~20-30 seconds**

**Playback (continuous):**
- Frame decompression: ~5-10 ms/frame
- Grayscale → RGBA conversion: ~1-2 ms/frame
- Shared memory write: ~1-2 ms/frame
- **Total: ~10-15 ms/frame at 60 fps (target: 16.67 ms)**

**Viewport retrieval (on-demand):**
- Frame decompression: ~5-10 ms
- Grayscale → RGBA conversion: ~1-2 ms
- **Total: ~10-15 ms per request**

---

## Error Handling

### Library Not Pre-generated

**Error:**
```json
{
  "success": false,
  "error": "Direction LR not pre-generated. Call pre_generate_all_directions() first."
}
```

**Solution:** Call `unified_stimulus_pregenerate` before starting playback.

### Playback Already Running

**Error:**
```json
{
  "success": false,
  "error": "Playback already running - stop current playback first"
}
```

**Solution:** Call `unified_stimulus_stop_playback` before starting new direction.

### Frame Not Available

**Error:**
```json
{
  "success": false,
  "error": "Frame not available: LR[999]"
}
```

**Solution:** Check frame_index is within valid range (0 to total_frames-1).

---

## Tips and Best Practices

1. **Pre-generate at startup:** Call once after backend initializes, before user interaction
2. **Stop before switching:** Always stop playback before starting a new direction
3. **Clear logs before recording:** Clear display log before each recording session
4. **Monitor memory:** Check `library_status` to monitor memory usage
5. **Cache viewport frames:** Consider implementing LRU cache for frequently accessed frames
6. **Thread safety:** Controller is thread-safe, multiple viewports can call `get_frame` concurrently

---

*Last updated: 2025-10-14*
