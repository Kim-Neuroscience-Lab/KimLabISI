# Components

**Last Updated**: 2025-10-14 23:30

> Detailed documentation for each major system component.

---

## Component Index

### Core Systems

- [Acquisition System](acquisition-system.md) - Independent parallel thread acquisition with hardware timestamps
- [Analysis Pipeline](analysis-pipeline.md) - Fourier-based retinotopic mapping with timestamp-based phase assignment
- [Camera System](camera-system.md) - Independent camera capture with hardware timestamping
- [Stimulus System](stimulus-system.md) - Pre-generated GPU-accelerated stimulus with independent VSync-locked playback

### Supporting Systems

- [Parameter Manager](parameter-manager.md) - Configuration management and single source of truth
- [Data Recording](data-recording.md) - HDF5 session storage for camera frames and stimulus logs

---

## Component Status

| Component | Status | Last Updated | Documentation |
|-----------|--------|--------------|---------------|
| Acquisition | ⚠️ Unverified | 2025-10-14 23:30 | Intended functionality documented |
| Stimulus | ⚠️ Unverified | 2025-10-14 23:30 | Intended functionality documented (GPU-accelerated) |
| Analysis | ⚠️ Unverified | 2025-10-14 23:13 | Intended functionality documented |
| Camera | ✅ Verified | 2025-10-15 16:55 | Complete and verified |
| Data Recording | ⚠️ Unverified | 2025-10-14 23:30 | Intended functionality documented |
| Parameters | ✅ Stable | 2025-10-14 23:33 | Complete |

---

## Component Lifecycle

### Startup Order

1. **Parameter Manager**: Load config from `isi_parameters.json`
2. **Shared Memory**: Initialize buffers (camera, stimulus, analysis)
3. **IPC System**: Setup ZeroMQ channels (CONTROL, SYNC, HEALTH)
4. **Camera Manager**: Enumerate available cameras, open selected camera
5. **Stimulus Generator**: Initialize GPU acceleration (PyTorch with CUDA/MPS/CPU fallback)
6. **Unified Stimulus**: Create pre-generation controller
7. **Acquisition Manager**: Wire up dependencies
8. **Analysis Manager**: Load pipeline stages

Total startup time: <1 second

### Shutdown Order

1. Stop acquisition if running
2. Stop camera if streaming
3. Stop stimulus playback if active
4. Close shared memory buffers
5. Close IPC channels
6. Save parameters if modified

---

## Component Dependencies

```
Parameter Manager (no dependencies)
   ↓
Shared Memory (no dependencies)
   ↓
IPC System (no dependencies)
   ↓
Camera Manager → Parameter Manager
   ↓
Stimulus Generator → Parameter Manager, Shared Memory
   ↓
Unified Stimulus → Stimulus Generator, Shared Memory, IPC
   ↓
Acquisition Manager → Camera, Unified Stimulus, IPC, Parameters
   ↓
Analysis Manager → Parameter Manager, IPC
   ↓
Data Recorder → Camera, Unified Stimulus, Parameters
```

---

## Architecture Principles

### Independent Parallel Threads

**Camera and stimulus run independently with NO triggering**:
- Camera thread: Captures at camera FPS, records hardware timestamps
- Stimulus thread: Displays at monitor FPS, logs hardware timestamps
- Frame correspondence: Post-hoc matching via hardware timestamps

### Hardware Timestamps Only

**Scientific validity requires hardware timestamps**:
- Camera timestamps: From camera hardware (microsecond precision)
- Stimulus timestamps: From system clock during display (microsecond precision)
- Software timestamps NOT acceptable (millisecond precision with jitter)

### Pre-Generation Requirement

**User must manually pre-generate stimulus before acquisition**:
- No auto-generation during acquisition start
- System prompts user if library not ready
- Ensures user awareness and control

### Single Source of Truth

**Parameter Manager is authoritative for all configuration**:
- All components subscribe to parameter changes
- Parameters persisted to `isi_parameters.json`
- No duplicate configuration storage

---

## Data Flow

### Acquisition (Record Mode)

```
User clicks Record
   ↓
Check stimulus library pre-generated
   ↓
Start acquisition sequence
   ↓
FOR EACH DIRECTION:
   ├─ Camera captures frames (hardware timestamps)
   ├─ Stimulus displays frames (hardware timestamps + metadata)
   ├─ Both buffer data in memory
   └─ No disk I/O during capture
   ↓
Acquisition completes
   ↓
Write all buffered data to HDF5
   ↓
Session saved: camera frames + stimulus logs + metadata
```

### Analysis

```
User selects session
   ↓
Load HDF5 files (camera + stimulus)
   ↓
Phase Assignment:
   ├─ Match camera timestamps with stimulus timestamps
   └─ Assign visual field angle to each camera frame
   ↓
Fourier Analysis:
   ├─ FFT of phase-labeled temporal signals
   └─ Extract phase, magnitude, coherence per direction
   ↓
Bidirectional Analysis:
   ├─ Combine LR/RL → azimuth
   └─ Combine TB/BT → elevation
   ↓
VFS Computation:
   ├─ Smooth retinotopy (FFT-based, σ=3.0)
   ├─ Compute gradients (Sobel)
   └─ Calculate visual field sign
   ↓
Filtering:
   ├─ Coherence threshold (0.3)
   └─ Statistical threshold (1.5×std)
   ↓
Save results to analysis_results.h5
```

---

## Related Documentation

- [Architecture Overview](../architecture/README.md)
- [Data Flow](../architecture/data-flow.md)
- [Getting Started](../guides/getting-started.md)
- [Architecture Decisions](../decisions/README.md)

---

**Component Index Version**: 2.0
**Last Major Update**: 2025-10-14 23:30
**Documentation Status**: ⚠️ All core components documented with intended functionality - requires verification of actual implementation
**GPU Acceleration**: Stimulus generation uses PyTorch with automatic hardware detection (CUDA > MPS > CPU)
