# Performance Specifications

## Overview

This document defines the performance requirements and constraints for the ISI Macroscope Control System, with specifications tailored for the production hardware environment and cross-platform development considerations.

## Target Hardware Environment

### Production System (Windows Workstation)
- **CPU**: Intel Core i7-13700K (16 cores: 8P + 8E cores, 3.4-5.4 GHz)
- **Memory**: 32 GB DDR4/DDR5 RAM
- **GPU**: NVIDIA GeForce RTX 4070 (12 GB GDDR6X VRAM)
- **Storage**: Samsung SSD 990 PRO 2TB (6,900 MB/s sequential read/write)
- **OS**: Windows 11

### Development System (Reference)
- **CPU**: Apple M2 Max (12 cores: 8P + 4E cores)
- **Memory**: 64 GB unified memory
- **GPU**: Apple M2 Max integrated (unified memory architecture)
- **OS**: macOS

## Critical Performance Requirements

### Real-time Display Performance
**Target**: Frame-perfect 60 FPS stimulus presentation to mouse monitor

**RTX 4070 Specifications:**
- **GPU Control**: DirectX 12 or Vulkan for hardware display control
- **VRAM Allocation**: 2-4 GB for pre-loaded stimulus frames in GPU memory
- **Page Flipping**: Hardware triple buffering for tear-free presentation
- **Latency**: <1ms trigger-to-display using GPU timer queries
- **Tolerance**: Zero dropped frames during acquisition periods

**13700K CPU Allocation:**
- **Dedicated Core**: 1 P-core reserved for display timing loop
- **Priority**: Real-time thread priority for display control
- **Isolation**: No other processes on display timing core

### Camera Capture Performance (PCO Panda 4.2 USB)
**Target**: Sustained 30 FPS capture without frame drops (camera max: 40 FPS at 2048×2048)

**PCO Panda 4.2 Specifications:**
- **Resolution**: 2048×2048 pixels (4.2 MPixel) with 16-bit dynamic range
- **Interface**: USB 3.1 Gen 1 with single-cable power and data
- **Frame Rate**: 40 FPS max at full resolution, 30 FPS target for ISI
- **Pixel Size**: 6.5 μm × 6.5 μm (13.3 mm × 13.3 mm sensor)
- **Dynamic Range**: 87 dB (21,500:1) for high-quality ISI imaging

**System Requirements:**
- **USB 3.1 Throughput**: 125 MB/sec sustained (16.7 MB per 16-bit frame at 30 FPS)
- **Buffer Management**: 2 GB system RAM for 16-bit frame buffers from PCO Panda
- **Processing**: CUDA preprocessing for 16-bit to display format conversion
- **Latency**: <33ms from PCO Panda capture to Samsung 990 PRO storage

### Memory Budget Allocation (32 GB System RAM)

**Critical Constraint**: 32 GB total system memory requires careful allocation

**Memory Distribution (with PCO Panda 4.2):**
```
Operating System & Base:     4 GB  (12.5%)
Electron Frontend:           2 GB  (6.25%)
Backend Core Process:        4 GB  (12.5%)
HDF5 Stimulus Cache:         8 GB  (25%)
PCO Panda Frame Buffers:     2 GB  (6.25%) - 16-bit, 4.2 MPixel frames
Analysis Working Set:        8 GB  (25%)  - 16-bit processing workspace
System Reserve/Other:        4 GB  (12.5%)
Total:                      32 GB  (100%)
```

**GPU VRAM Allocation (12 GB RTX 4070):**
```
Display Frame Buffers:       3 GB  (25%)
Stimulus Frame Cache:        4 GB  (33.3%)
Processing Workspace:        2 GB  (16.7%)
Analysis Computation:        2 GB  (16.7%)
System Reserve:              1 GB  (8.3%)
Total:                      12 GB  (100%)
```

## Stage-Specific Performance Requirements

### Stimulus Generation Phase

**CUDA Acceleration Requirements:**
- **Generation Speed**: Complete 4-direction stimulus set in <30 seconds
- **GPU Utilization**: 70-90% RTX 4070 compute during generation
- **Memory Pattern**: Stream generation to minimize VRAM usage
- **Storage**: Parallel HDF5 writing to Samsung 990 PRO

**Performance Targets:**
- **Frame Generation**: 200+ frames/second using CUDA kernels
- **HDF5 Compression**: Real-time compression during generation
- **Preview Rendering**: 60 FPS preview without affecting generation

### Acquisition Phase (Most Critical)

**Real-time Constraints:**
- **Stimulus Display**: Exactly 60.000 FPS (16.667ms period) ±10μs
- **Camera Capture**: 30.000 FPS (33.333ms period) ±100μs
- **Timestamp Precision**: <1μs using RTX 4070 timer queries
- **Storage Latency**: <50ms from capture to disk

**Resource Allocation:**
- **CPU Cores**:
  - 2 P-cores for real-time display/capture
  - 4 P-cores for data processing
  - 6 E-cores for background tasks
  - 4 E-cores reserved for OS
- **GPU Compute**: 30% reserved for real-time operations
- **Memory Bandwidth**: Priority allocation to display pipeline

### Analysis Phase

**Computational Requirements:**
- **FFT Processing**: CUDA-accelerated for 2048×2048 frames
- **Throughput**: Process 1800 frames (1 minute @ 30 FPS) in <60 seconds
- **Memory Streaming**: Process datasets larger than 32 GB RAM
- **Visualization**: 60 FPS interactive retinotopic map rendering

**13700K Optimization:**
- **Parallel Processing**: Utilize all 16 cores for analysis
- **Thread Strategy**: P-cores for compute, E-cores for I/O
- **Memory Access**: Optimize for DDR4/DDR5 bandwidth patterns

## Storage Performance Specifications

### Samsung 990 PRO Optimization

**Sequential Performance:**
- **Write Rate**: 125 MB/sec sustained (camera frames)
- **Read Rate**: 500+ MB/sec (HDF5 stimulus loading)
- **Queue Depth**: 32+ for optimal throughput

**Random Access Performance:**
- **HDF5 Chunks**: 4K-64K chunk sizes for optimal access
- **Metadata Access**: <1ms random read latency
- **Concurrent Operations**: Support simultaneous read/write

### File System Considerations

**NTFS Optimization (Windows):**
- **Allocation Unit Size**: 64K for large media files
- **Disable Indexing**: On acquisition data directories
- **Reserved Space**: 10% free space for optimal performance

## Cross-Platform Development Considerations

### macOS Development Environment

**Metal vs CUDA:**
- **Abstraction Layer**: GPU compute abstraction for cross-platform
- **Performance Parity**: Equivalent operations on Metal and CUDA
- **Testing Strategy**: Validate performance on both platforms

**Memory Differences:**
- **Unified Memory**: M2 Max advantage for large datasets
- **Discrete GPU**: RTX 4070 requires explicit memory management
- **Buffer Strategies**: Different optimal patterns per platform

## Performance Monitoring & Metrics

### Real-time Monitoring

**Critical Metrics:**
- **Frame Rate Deviation**: Track actual vs target frame rates
- **Timestamp Accuracy**: Monitor timing precision violations
- **Memory Usage**: Track allocation against budgets
- **GPU Utilization**: Monitor compute and memory usage

**Alert Thresholds:**
- **Frame Rate**: >0.1% deviation from target
- **Memory**: >90% allocation in any category
- **Storage**: >80% bandwidth utilization
- **Temperature**: GPU >83°C sustained

### Performance Validation

**Benchmark Requirements:**
- **Sustained Load**: 10+ minute continuous acquisition test
- **Memory Stress**: Full 32 GB allocation test
- **GPU Stress**: 100% utilization during analysis
- **Storage Stress**: Sustained max write rate test

## Optimization Strategies

### Memory Optimization

**32 GB Constraint Mitigation:**
- **Streaming Algorithms**: Process data larger than RAM
- **Memory Mapping**: Use OS virtual memory for large datasets
- **Garbage Collection**: Aggressive cleanup in non-critical phases
- **Compression**: Use HDF5 compression to reduce memory footprint

### GPU Optimization

**RTX 4070 Maximization:**
- **CUDA Streams**: Overlap computation and memory transfer
- **Tensor Cores**: Use for appropriate matrix operations
- **Memory Coalescing**: Optimize GPU memory access patterns
- **Occupancy**: Maximize SM utilization for compute kernels

### CPU Optimization

**13700K Hybrid Architecture:**
- **P-Core Assignment**: Real-time and compute-intensive tasks
- **E-Core Assignment**: Background processing and I/O
- **NUMA Awareness**: Optimize memory locality
- **Thread Affinity**: Pin critical threads to specific cores

## Fallback Strategies

### Performance Degradation Handling

**Graceful Degradation:**
- **Reduced Resolution**: Drop to 1024×1024 if memory constrained
- **Lower Frame Rate**: Accept 15 FPS camera capture if necessary
- **CPU Fallback**: Use CPU for GPU operations if needed
- **Quality Reduction**: Reduce preview quality to maintain acquisition

### Hardware Failure Responses

**GPU Failure:**
- **CPU Rendering**: Fallback to software rendering for display
- **Analysis Mode**: CPU-only analysis pipeline
- **Reduced Features**: Disable GPU-dependent preview features

**Memory Pressure:**
- **Disk Caching**: Use SSD as extended memory
- **Reduced Buffers**: Minimize buffer sizes
- **Streaming Mode**: Process data in smaller chunks

## Validation Criteria

### Acceptance Testing

**Performance Gates:**
- **60 FPS Display**: Must maintain for 30+ minutes
- **30 FPS Capture**: Zero dropped frames in 10+ minute test
- **Memory Budget**: Stay within 32 GB allocation limits
- **Analysis Speed**: Process 1-hour dataset in <1 hour

**Quality Assurance:**
- **Timing Precision**: <1μs timestamp accuracy
- **Data Integrity**: Zero corruption in 24+ hour stress test
- **Cross-Platform**: Identical results on macOS dev and Windows prod
- **Reproducibility**: Bit-identical output across multiple runs