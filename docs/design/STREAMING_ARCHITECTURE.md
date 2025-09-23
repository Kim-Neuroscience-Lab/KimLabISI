# Display Architecture for Multi-Monitor Streaming

## Overview

This document describes the display and streaming architecture for the ISI Macroscope Control System, which must coordinate multiple display outputs with different performance requirements and data paths.

**Key Principle**: Scientific data (both stimulus presentation and camera capture) NEVER passes through the Electron frontend. The frontend only receives downsampled previews for monitoring purposes.

## Display Requirements

### Mouse Monitor (Critical Path)
- **Purpose**: Present visual stimuli directly to the experimental subject
- **Resolution**: Full native resolution (e.g., 1920x1080 or higher)
- **Frame Rate**: Exactly 60 FPS with frame-perfect timing
- **Latency**: Zero tolerance - must be deterministic
- **Control**: Direct hardware control via backend

### Scientist Workstation (Monitoring Path)
- **Purpose**: Real-time monitoring and control interface
- **Resolution**: Downsampled previews (e.g., 512x512)
- **Frame Rate**: Variable, typically 10-30 FPS
- **Latency**: Tolerant - 100-500ms acceptable
- **Control**: Electron application with renderer process

## Architecture Components

### Backend Display Controller

The backend maintains direct control over the mouse display hardware:

**Hardware Interface (RTX 4070 on Windows):**
- Direct GPU/display buffer access (DirectX 12 or Vulkan preferred for RTX 4070)
- Hardware-accelerated frame presentation with CUDA compute shaders
- Vertical sync (VSync) synchronization for tear-free display
- GPU-managed triple buffering (3 GB VRAM allocation) for smooth playback
- Windows Display Driver Model (WDDM) integration for exclusive fullscreen

**Timing Coordination (13700K + RTX 4070):**
- Hardware timer-driven presentation loop on dedicated P-core
- RTX 4070 GPU timer queries for microsecond-precision timestamps
- Guaranteed 60 FPS delivery with <1ms latency tolerance
- DirectX 12 Present() API for frame presentation
- No dependency on network or other variable-latency systems

### Streaming Architecture

The system uses multiple independent data paths:

**Path 1: Mouse Display (Direct Hardware - RTX 4070)**
```
HDF5 Stimulus Files → CUDA/DirectX Buffer → Mouse Monitor
                              ↓
                    RTX 4070 Timer Queries
```

**Path 2: Camera Capture (Direct to Disk)**
```
Camera → Backend Buffer → Disk Storage (Full Resolution)
              ↓
       Hardware Timestamps
```
Note: Full-resolution camera data NEVER passes through frontend

**Path 3: Scientist Monitoring (NVENC/IPC)**
```
Backend → NVENC Compression → IPC/WebSocket → Electron Renderer
         (RTX 4070 Hardware)                   (Preview Only)
                ↓
      NVENC Compressed Previews (50-200KB/frame)
```
Note: Frontend receives only downsampled copies for monitoring

## IPC and Streaming Protocol

### Binary Streaming Format

Communication uses binary frames for efficiency (via IPC or WebSocket):

**Frame Structure:**
```
[Header (16 bytes)]
  - Message Type (1 byte)
  - Timestamp (8 bytes)
  - Frame Number (4 bytes)
  - Data Length (3 bytes)
[Payload (variable)]
  - Compressed image data or status information
```

**Message Types:**
- `0x01`: Stimulus preview frame
- `0x02`: Camera preview frame
- `0x03`: Status update
- `0x04`: Control command
- `0x05`: Progress notification

### Compression Strategy

**Preview Streams (RTX 4070 NVENC):**
- RTX 4070 NVENC hardware JPEG compression for individual frames
- NVENC H.264/H.265 encoding for continuous streams (dual encoder support)
- CUDA-based adaptive quality adjustment based on 32 GB RAM constraints
- Typical compression: 16MB → 50-200KB per frame using NVENC encoders
- Memory-constrained optimization: aggressive compression when RAM >90%

**Status Messages:**
- JSON for structured data
- MessagePack for binary efficiency
- Minimal overhead for real-time updates

## Synchronization Mechanisms

### Hardware Synchronization

**Display Timing:**
- VSync locked presentation
- Hardware frame counters
- GPU timestamp queries
- Display refresh rate monitoring

**Cross-Device Timing:**
- Shared hardware clock source (if available)
- GPIO trigger signals between devices
- Network Time Protocol (NTP) as fallback
- Timestamp all events at hardware level

### Software Coordination

**Backend Orchestration:**
- Single timing master in backend
- Independent threads for each path
- Lock-free queues for data passing
- Priority scheduling for critical path

**Electron Renderer Synchronization:**
- Receive timestamps with preview frames
- Display correlation information
- No attempt at frame-perfect sync
- Focus on smooth monitoring experience

## Performance Considerations

### Critical Path Optimization

**Mouse Display (RTX 4070 Optimization):**
- Pre-loaded HDF5 stimulus frames in 4 GB VRAM allocation
- Zero-copy frame presentation from RTX 4070 memory buffers
- DirectX 12 page flipping with WDDM exclusive mode
- Dedicated 13700K P-core for timing loop with CUDA synchronization
- Memory streaming from Samsung 990 PRO when dataset exceeds VRAM

### Non-Critical Path Flexibility

**Monitoring Streaming:**
- GPU-accelerated downsampling for best-effort delivery via IPC/WebSocket
- GPU-based automatic quality adjustment and scaling
- Frame dropping acceptable with GPU buffer management
- GPU-accelerated bandwidth optimization for preview streams

## Data Flow Separation

### Scientific Data
- Never passes through streaming layer
- Full resolution preserved
- Hardware timestamps maintained
- Direct disk storage path

### Monitoring Data
- Downsampled for efficiency
- Compressed for bandwidth
- Delayed for buffering
- Informational only

## Error Handling

### Critical Path Failures
- **Display Failure**: Abort experiment immediately
- **Timing Violation**: Log and flag data
- **Frame Drop**: Mark in metadata, continue if possible

### Non-Critical Path Failures
- **IPC/WebSocket Disconnect**: Continue experiment, attempt reconnection
- **Preview Lag**: Reduce quality automatically
- **Renderer Process Crash**: No impact on experiment, can restart renderer

## Implementation Technologies

### Backend Technologies (Windows Production)
- **DirectX 12/Vulkan**: Hardware-accelerated display and compute for RTX 4070
- **FFmpeg with NVENC**: Hardware video encoding using RTX 4070 dual encoders
- **CUDA 12.x**: GPU-accelerated image processing optimized for RTX 4070
- **libwebsockets**: WebSocket server for IPC communication
- **DirectShow/Media Foundation**: Camera interfaces with GPU memory mapping
- **Windows Performance Toolkit**: Real-time performance monitoring

### Electron Frontend (Windows)
- **IPC**: Inter-process communication for local data with 2 GB memory budget
- **WebSocket**: Binary streaming for compressed previews from NVENC
- **WebGL 2.0/WebGPU**: Hardware-accelerated rendering using RTX 4070
- **GPU.js/WebGL Compute**: GPU-accelerated preview processing in renderer
- **Node.js Integration**: Direct NTFS file system access with 64K clusters
- **Windows-specific**: Hardware acceleration through ANGLE/D3D11

## Quality Assurance

### Timing Verification
- Measure actual frame presentation times
- Validate against expected 60 FPS
- Detect and report timing violations
- Calibrate system before experiments

### Stream Monitoring
- Track frame rates for all paths
- Monitor latency and bandwidth
- Alert on quality degradation
- Log performance metrics

## Summary

The display architecture maintains strict separation between:

1. **Critical scientific path**: Hardware-controlled, frame-perfect mouse display
2. **Data capture path**: Direct camera-to-disk with timestamps
3. **Monitoring path**: Flexible IPC/streaming for Electron renderer observation

This separation ensures experimental integrity while providing responsive monitoring capabilities. The backend maintains complete control over timing-critical operations, while the Electron frontend provides a convenient but non-critical observation interface.