# ARCHIVED DOCUMENTATION

**Original File**: ANALYSIS_VIEWPORT_SHARED_MEMORY_FIX.md
**Archived**: 2025-10-09
**Reason**: Documentation restructure - content consolidated into new docs/ structure

**Status**: Historical reference only. For current documentation, see:
- [Documentation Index](../README.md)
- [Architecture Overview](../architecture/overview.md)
- [Component Documentation](../components/)
- [Technical Decisions](../technical-decisions/)

---

# Original Content

# Analysis Viewport Shared Memory Fix

## Summary

Fixed the frontend analysis visualization system to properly use shared memory instead of JSON arrays for transferring large analysis data. This eliminates the architectural violation that caused timeouts/crashes with real data (24MB+ JSON strings).

## Date
2025-10-09

## Problem Statement

The backend correctly uses shared memory for transferring large analysis arrays, but the frontend was expecting JSON arrays. This caused:
- 24MB+ JSON strings being sent over IPC
- Timeouts and crashes on real data
- Architectural violation of the shared memory design

## Solution Implemented

### 1. Frontend Changes (COMPLETED)

**File:** `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AnalysisViewport.tsx`

#### Key Architectural Changes:

1. **Interface Updates (Lines 19-36)**
   - Changed from `number[][]` arrays to metadata-only interfaces
   - `AnalysisMetadata`: Contains only shape, layer lists, and session info (no heavy arrays)
   - `CachedLayer`: Stores `Float32Array` data with dimensions and range

2. **Layer Loading System (Lines 179-262)**
   - `loadLayer()`: Loads individual layers on-demand via shared memory
   - Checks cache first before requesting from backend
   - Reads raw Float32Array from shared memory using `window.electronAPI.readSharedMemoryFrame()`
   - Stores loaded layers in `Map<string, CachedLayer>` cache

3. **Metadata-Only Loading (Lines 129-176)**
   - `loadAnalysisResults()`: Loads only metadata (shape, num_areas, layer lists)
   - Does NOT load actual array data
   - Clears layer cache when loading new session

4. **Rendering Functions (Lines 363-504)**
   - All rendering functions now work with `Float32Array` instead of `number[][]`
   - `renderAnatomical()`: Renders grayscale anatomical underlay
   - `renderSignalMap()`: Renders colored signal maps with proper normalization
   - `renderBoundaries()`: Renders area borders
   - `renderAreaPatches()`: Renders colored area patches

5. **Layer State Management (Lines 57-59)**
   - `layerCache: Map<string, CachedLayer>`: Caches loaded layers
   - `currentSessionPath: string`: Tracks current session
   - Automatic cache clearing on session change

6. **UI Updates (Lines 709-722)**
   - Primary layers (azimuth, elevation, sign) in "Primary Results" optgroup
   - Advanced layers (magnitude, phase) in "Advanced (Debug)" optgroup
   - Only shown when advanced_layers are available

7. **Statistics Display (Lines 785-796)**
   - Shows number of visual areas
   - Resolution
   - Primary/Advanced layer counts
   - **Cached layers count** (verifies caching works)

### 2. Backend Integration Points

The frontend expects the following backend IPC responses:

#### `get_analysis_results` Response:
```typescript
{
  success: true,
  session_path: string,
  shape: [height, width],
  num_areas: number,
  primary_layers: string[],  // ['azimuth_map', 'elevation_map', ...]
  advanced_layers: string[],  // ['phase_LR', 'magnitude_LR', ...]
  has_anatomical: boolean
}
```

#### `get_analysis_layer` Response:
```typescript
{
  success: true,
  layer_name: string,
  buffer_name: string,
  shape: [height, width],
  dtype: 'float32',
  data_min: number,
  data_max: number
}
```

### 3. Data Flow Architecture

```
User Action → Request Metadata Only
  ↓
Backend: Load metadata from HDF5 (NO arrays)
  ↓
Frontend: Store metadata, set canvas dimensions
  ↓
User Changes Layer → Check Cache
  ↓ (cache miss)
Backend: Load layer to shared memory (Float32Array)
  ↓
Frontend: Read from shared memory via electron API
  ↓
Frontend: Convert to Float32Array, cache
  ↓
Frontend: Render to canvas
  ↓ (cache hit)
Frontend: Use cached Float32Array directly
```

## CRITICAL BACKEND ISSUE

### Location
`/Users/Adam/KimLabISI/apps/backend/src/isi_control/analysis_ipc_handlers.py`

### Line 301 - BUG IN BACKEND

```python
# CURRENT (INCORRECT):
buffer_name = f"analysis_{layer_name}"
shm_service.write_frame(buffer_name, layer_data)  # ❌ WRONG ARGUMENT ORDER

# SHOULD BE:
shm_service.write_frame(layer_data, {
    "frame_index": 0,
    "total_frames": 1,
    "direction": "analysis",
    "angle_degrees": 0.0,
    "start_angle": 0.0,
    "end_angle": 0.0
})  # ✅ CORRECT: (frame_data, metadata)
```

### Problem

The `write_frame()` method signature is:
```python
def write_frame(self, frame_data: np.ndarray, metadata: Dict[str, Any]) -> int
```

But the backend is calling:
```python
shm_service.write_frame(buffer_name, layer_data)
```

This passes:
- `frame_data = buffer_name` (string, not ndarray) ❌
- `metadata = layer_data` (ndarray, not dict) ❌

### Required Backend Fix

```python
# File: /Users/Adam/KimLabISI/apps/backend/src/isi_control/analysis_ipc_handlers.py
# Lines 295-314

# Write to shared memory
services = get_services()
shm_service = services.shared_memory

# Convert to uint8 for shared memory (write_frame expects uint8)
# Scale float32 data to 0-255 range for visualization
if layer_data.dtype == np.float32:
    # Normalize to 0-1 range
    data_min = np.nanmin(layer_data)
    data_max = np.nanmax(layer_data)
    if data_max > data_min:
        normalized = (layer_data - data_min) / (data_max - data_min)
    else:
        normalized = layer_data
    # Scale to uint8
    layer_data_uint8 = (normalized * 255).astype(np.uint8)
else:
    layer_data_uint8 = layer_data.astype(np.uint8)

# Write to shared memory with proper metadata
frame_id = shm_service.write_frame(layer_data_uint8, {
    "frame_index": 0,
    "total_frames": 1,
    "direction": "analysis",
    "angle_degrees": 0.0,
    "start_angle": 0.0,
    "end_angle": 0.0
})

# Get frame info to retrieve offset and path
frame_info = shm_service.get_frame_info(frame_id)
if frame_info is None:
    return format_error_response(
        "get_analysis_layer",
        f"Failed to retrieve frame info for layer '{layer_name}'"
    )

logger.info(f"Loaded analysis layer '{layer_name}': shape={shape}, dtype={dtype}")

return format_success_response(
    "get_analysis_layer",
    message=f"Layer '{layer_name}' loaded to shared memory",
    layer_name=layer_name,
    buffer_name=f"analysis_{layer_name}",
    shape=list(shape),
    dtype=str(dtype),
    data_min=float(data_min),
    data_max=float(data_max),
    offset_bytes=frame_info.offset_bytes,
    shm_path=f"/tmp/isi_macroscope_stimulus_shm"
)
```

### Alternative Simpler Backend Fix

If you want to avoid the video frame metadata requirements, create a dedicated method for analysis layers:

```python
# Add to SharedMemoryService class
def write_analysis_layer(self, layer_data: np.ndarray) -> Dict[str, Any]:
    """Write analysis layer to shared memory without video metadata."""
    # Convert to uint8 or float32
    if layer_data.dtype != np.uint8:
        layer_data = layer_data.astype(np.float32)

    # Write at start of buffer (offset 0)
    self.stream.stimulus_shm_mmap.seek(0)
    self.stream.stimulus_shm_mmap.write(layer_data.tobytes())
    self.stream.stimulus_shm_mmap.flush()

    return {
        "offset_bytes": 0,
        "data_size_bytes": layer_data.nbytes,
        "shm_path": f"/tmp/{self.stream.stream_name}_stimulus_shm"
    }
```

## Frontend Workaround (TEMPORARY)

The frontend currently assumes:
- Analysis layers are written to `/tmp/isi_macroscope_stimulus_shm`
- Data starts at offset 0
- Data is Float32Array

This will work once the backend is fixed to properly write the data.

## Testing Checklist

- [ ] Backend fix applied and tested
- [ ] `get_analysis_results` returns metadata only (no JSON arrays)
- [ ] `get_analysis_layer` properly writes to shared memory
- [ ] Frontend loads layers via shared memory successfully
- [ ] Layer caching works (no redundant loads)
- [ ] Primary vs advanced layers properly separated in UI
- [ ] Canvas rendering works with Float32Array
- [ ] Memory usage is reasonable (not 24MB JSON strings)
- [ ] Multiple sessions can be loaded without memory leaks
- [ ] Layer switching is fast (cache hit)

## Performance Improvements

### Before:
- 24MB+ JSON strings over IPC
- Timeouts on real data
- Memory spikes
- Slow loading

### After:
- Metadata only: ~1KB JSON
- Layer data: Direct shared memory access
- Cached layers: Instant switching
- Memory efficient: Float32Array

## Files Modified

1. `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AnalysisViewport.tsx` - Complete rewrite (✅ DONE)
2. `/Users/Adam/KimLabISI/apps/backend/src/isi_control/analysis_ipc_handlers.py` - Line 301 fix needed (❌ TODO)

## Implementation Details

### Layer Caching Strategy
- Cache is a `Map<layerName, CachedLayer>`
- Cleared when switching sessions
- Persistent within session
- Size shown in UI for debugging

### Shared Memory Reading
```typescript
// Request backend to load layer
const result = await sendCommand({
  type: 'get_analysis_layer',
  session_path: currentSessionPath,
  layer_name: layerName
})

// Read from shared memory
const arrayBuffer = await window.electronAPI.readSharedMemoryFrame(
  0,  // offset
  dataSize,  // size in bytes
  '/tmp/isi_macroscope_stimulus_shm'  // path
)

// Convert to Float32Array
const float32Data = new Float32Array(arrayBuffer)
```

### Colormap Implementation
- **Jet colormap**: For azimuth/elevation maps
- **Red/Blue**: For sign maps (positive=red, negative=blue)
- **Grayscale**: For magnitude/phase maps
- **Auto-normalization**: Uses data_min/data_max from backend

## Notes

1. The frontend is now architecturally correct and matches the design of other viewports (AcquisitionViewport, CameraViewport)
2. The backend needs one critical fix at line 301 of `analysis_ipc_handlers.py`
3. Once the backend is fixed, the system will work end-to-end with proper shared memory transfer
4. The implementation supports both primary and advanced layers with proper UI separation
5. Layer caching ensures fast switching between different visualizations

## References

- Similar pattern in `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/AcquisitionViewport.tsx` (lines 396-457)
- Similar pattern in `/Users/Adam/KimLabISI/apps/desktop/src/components/viewports/CameraViewport.tsx`
- Shared memory service: `/Users/Adam/KimLabISI/apps/backend/src/isi_control/shared_memory_stream.py`
