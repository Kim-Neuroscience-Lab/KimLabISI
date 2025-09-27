# Acquisition Pipeline

## Overview

This document describes the real-time data acquisition pipeline for the ISI Macroscope Control System, focusing on the synchronization strategy for correlating stimulus presentation with camera capture.

## Core Challenge

The system must coordinate:

- Visual stimulus display at 60 FPS (16.67ms per frame)
- Camera capture at 30 FPS (33.33ms per frame)
- Real-time data streaming and storage
- Hardware timestamp collection for post-hoc correlation

Each camera frame captures brain response during approximately 2 stimulus frames, requiring careful temporal correlation.

## Data Capture Approach

### Real-time Event Recording

During acquisition, the system captures timestamped events from multiple sources:

**Stimulus Events (RTX 4070 Timestamps):**

- RTX 4070 hardware timestamp for each frame presentation (<1μs precision)
- Frame number (sequential identifier from HDF5 dataset)
- Pre-calculated angle from HDF5 `/angles` dataset
- Direction identifier (LR, RL, TB, BT from filename)

**Camera Events (PCO Panda 4.2 USB):**

- PCO SDK timestamp with RTX 4070 synchronization for each 16-bit frame capture
- Frame number (sequential identifier from USB 3.1 stream)
- Exposure duration (PCO Panda range: 21 μs - 5 s, with 1 μs timestamp resolution)
- Direct storage to Samsung 990 PRO at 30 FPS (16.7 MB per 16-bit frame)

### Key Principles

1. **Separation of Capture and Correlation**: Real-time systems focus solely on accurate timestamping and data preservation. Correlation happens during analysis.

2. **Hardware-level Timestamping**: Use hardware clocks or trigger signals for microsecond-precision timestamps, not software system time.

3. **Event-based Architecture**: Store discrete events with timestamps rather than trying to maintain synchronized streams.

4. **Full Data Preservation**: Never drop or interpolate data due to timing mismatches. Preserve everything and make correlation decisions during analysis.

## Protocol Execution

The acquisition system automatically cycles through all stimulus directions:

- Left-to-Right (LR_direction.h5)
- Right-to-Left (RL_direction.h5)
- Top-to-Bottom (TB_direction.h5)
- Bottom-to-Top (BT_direction.h5)

Each direction loads identically from its HDF5 file and is presented for the specified number of repetitions according to the experimental protocol.

## Data Streaming Paths

### Critical Path - Stimulus Display (RTX 4070)

- DirectX 12 exclusive fullscreen control to mouse monitor using RTX 4070
- CUDA/DirectX managed frame-perfect 60 FPS with WDDM hardware page flipping
- RTX 4070 timer query hardware timestamps with microsecond precision
- Dedicated 13700K P-core for timing loop with zero network/IPC involvement
- 4 GB VRAM allocation for stimulus frame cache with Samsung 990 PRO streaming

### Critical Path - Camera Capture (PCO Panda 4.2 USB)

- USB 3.1 Gen 1 interface with DirectShow/Media Foundation integration
- PCO SDK camera control with 16-bit, 4.2 MPixel frame capture at 30 FPS
- CUDA-synchronized timestamp alignment with RTX 4070 display pipeline
- 2 GB system RAM buffers for 16-bit frame processing (87 dB dynamic range)
- Samsung 990 PRO sustained 125 MB/sec write rate (16.7 MB/frame at 30 FPS)

### Monitoring Path - Live Preview (NVENC)

- NVENC hardware-compressed downsampled streams to Electron frontend
- RTX 4070 dual encoder best-effort delivery via IPC (2 GB frontend budget)
- Tolerates latency/drops with aggressive compression during 32 GB RAM pressure
- See [STREAMING_ARCHITECTURE.md](./STREAMING_ARCHITECTURE.md) for RTX 4070 NVENC implementation details

## Performance Requirements (Production Hardware)

- **RTX 4070 Stimulus Display**: Exactly 60 FPS ±10μs using DirectX 12 hardware control
- **Windows Camera Capture**: 30 FPS zero-drop using DirectShow + CUDA buffers
- **RTX 4070 Timestamps**: <1μs precision using hardware timer queries
- **Samsung 990 PRO Storage**: 125 MB/sec sustained with RTX 4070 memory optimization
- **NVENC Preview Streams**: Flexible quality with hardware compression (50-200KB/frame)
- **32 GB RAM Management**: Stay within memory budget allocations per [PERFORMANCE_SPECIFICATIONS.md](./PERFORMANCE_SPECIFICATIONS.md)

## Data Output

The acquisition pipeline produces:

- Stimulus event log with timestamps (correlated to HDF5 frame indices)
- Camera frames with timestamps (full resolution, 30 FPS)
- Protocol metadata (which HDF5 files used, repetition counts)
- Session configuration (stimulus parameters, hardware settings)
- Quality metrics (dropped frames, timing violations)

All data is stored for post-acquisition correlation and analysis using HDF5 angle datasets.
