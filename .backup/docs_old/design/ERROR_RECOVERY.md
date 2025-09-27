# Error Recovery

## Overview

This document defines practical error detection, graceful degradation, and recovery strategies for the ISI Macroscope Control System. The approach prioritizes essential robustness without over-engineering, while maintaining complete transparency about any issues that could affect scientific validity, system maintainability, or diagnostic capability.

## Core Principles

### Graceful Degradation with Full Transparency
- Continue operation where scientifically acceptable
- Never mask issues that affect experimental validity
- Provide complete visibility into system performance
- Maintain diagnostic information for troubleshooting

### Practical Recovery Focus
- Essential hardware health monitoring
- Simple retry logic and component restart procedures
- Clear user guidance for manual intervention
- Data preservation during failures

## Hardware Health Monitoring

### PCO Panda 4.2 USB Camera

**Connection Status Checks:**
- USB 3.1 Gen 1 connectivity verification
- PCO SDK communication test
- Frame capture capability validation
- Camera temperature and exposure settings verification

**Performance Monitoring:**
- Actual frame rate vs 30 FPS target
- USB bandwidth utilization (target: 125 MB/sec)
- Frame drop detection and counting
- Timestamp precision validation (<1μs accuracy)

**Health Check Frequency:**
- **Continuous**: Frame rate and USB bandwidth during acquisition
- **Per-trial**: Connection status and basic functionality
- **On-demand**: Full camera diagnostic when issues detected

### RTX 4070 GPU Display System

**Display Availability Checks:**
- DirectX 12 context validation
- Display hardware connection status
- VRAM allocation success (4 GB stimulus cache)
- Hardware page flipping capability

**Performance Monitoring:**
- Actual stimulus presentation rate vs 60 FPS target
- GPU timer query precision (<1μs accuracy)
- VRAM usage within 12 GB total allocation
- Display driver stability and context integrity

**Critical Thresholds:**
- **Frame Rate**: >59.9 FPS (0.1% tolerance)
- **Timing Precision**: <10μs deviation from target
- **VRAM Usage**: <90% of allocated 4 GB stimulus cache

### Samsung 990 PRO Storage System

**Storage Accessibility:**
- File system mount verification
- Write permission validation
- Available disk space monitoring (minimum 10 GB free)
- NTFS performance optimization status

**Performance Monitoring:**
- Actual write speed vs 125 MB/sec requirement
- Queue depth and I/O latency
- File system fragmentation level
- Storage temperature and health metrics

**Warning Thresholds:**
- **Write Speed**: <100 MB/sec sustained
- **Free Space**: <5 GB remaining
- **Queue Depth**: >80% utilization
- **Temperature**: >70°C

### System Resource Monitoring

**Memory Management (32 GB Total):**
- Component allocation tracking per [PERFORMANCE_SPECIFICATIONS.md](./PERFORMANCE_SPECIFICATIONS.md)
- System-wide memory pressure detection
- Virtual memory usage monitoring
- Memory leak detection in long-running sessions

**CPU Performance (Intel 13700K):**
- Real-time thread CPU utilization
- Thermal throttling detection
- Core assignment validation (P-cores vs E-cores)
- System load average monitoring

**Critical Alerts:**
- **Memory Usage**: >90% of allocated budget per component
- **CPU Temperature**: >85°C sustained
- **Thread Starvation**: Real-time threads blocked >10ms

## Critical Failure Detection

### Timing Violations

**60 FPS Stimulus Display Failures:**
- Frame presentation timing outside ±10μs tolerance
- Consecutive frame drops (>2 frames)
- Display driver context loss or corruption
- GPU hardware page flipping failures

**Detection Methods:**
- RTX 4070 timer query validation per frame
- Frame sequence number gap detection
- DirectX 12 present call success monitoring
- VSYNC synchronization status checking

**Response:**
- **Immediate**: Log violation with precise timestamp
- **Alert**: Real-time notification to user interface
- **Recovery**: Attempt display context recreation (1 retry)
- **Escalation**: Stop acquisition if recovery fails

### Data Acquisition Interruptions

**30 FPS Camera Capture Failures:**
- PCO Panda 4.2 frame delivery interruption
- USB 3.1 bandwidth saturation or disconnection
- Frame corruption or invalid data detection
- Timestamp synchronization loss with display

**Detection Methods:**
- Frame sequence continuity validation
- USB transfer completion status monitoring
- PCO SDK error code checking
- Cross-reference with display timing

**Response:**
- **Immediate**: Preserve all captured frames to disk
- **Recovery**: USB connection reset and camera reinitialize (2 retries)
- **Degradation**: Continue with reduced frame rate if acceptable
- **Termination**: Graceful stop with data preservation if unrecoverable

### Storage System Failures

**Write Operation Failures:**
- Samsung 990 PRO write errors or timeouts
- File system corruption or inconsistency
- Disk space exhaustion during acquisition
- NTFS allocation failures

**Detection Methods:**
- Write operation success/failure status monitoring
- File integrity verification after writes
- Available space checking before each trial
- File system health monitoring

**Response:**
- **Retry**: Immediate write retry (1 attempt)
- **Alternative**: Switch to backup storage location if available
- **Preservation**: Flush all buffers and sync file system
- **Alert**: Immediate user notification with recommended actions

## Graceful Degradation Strategies

### Performance Degradation Handling

**Preview Quality Reduction:**
- **Trigger**: NVENC compression failure or bandwidth constraints
- **Action**: Fall back to software JPEG compression
- **Warning**: "Preview quality reduced - using CPU compression (performance impact)"
- **Monitoring**: Track CPU usage increase and thermal impact

**Frame Rate Tolerance:**
- **Stimulus Display**: Accept 59.8-60.2 FPS with clear logging
- **Camera Capture**: Accept 29-31 FPS with quality assessment
- **Warning**: "Frame rate deviation detected - verify scientific validity"
- **Data Marking**: Flag affected frames in analysis correlation

**Memory Pressure Management:**
- **Trigger**: >85% memory usage in any component allocation
- **Action**: Reduce buffer sizes while maintaining functionality
- **Warning**: "Memory constraints - buffer sizes reduced"
- **Monitoring**: Track impact on frame drop rates

### Hardware Fault Tolerance

**GPU Performance Degradation:**
- **Thermal Throttling**: Continue with performance monitoring
- **VRAM Pressure**: Stream from Samsung 990 PRO more aggressively
- **Driver Issues**: Attempt context recreation with user notification
- **Warning**: Always indicate when GPU is not performing optimally

**Storage Performance Degradation:**
- **Slow Writes**: Continue with potential frame drop warnings
- **High Latency**: Increase buffer sizes if memory allows
- **Warning**: "Storage performance degraded - monitor for frame drops"
- **Fallback**: Emergency RAM buffering for critical periods

**USB Bandwidth Issues:**
- **Reduced Throughput**: Lower camera resolution if scientifically acceptable
- **Intermittent Drops**: Increase USB retry attempts with timeout
- **Warning**: "USB performance degraded - monitoring for data loss"
- **Escalation**: Consider manual intervention if persistent

## Recovery Procedures

### Connection Recovery

**PCO Panda 4.2 Reconnection:**
```
1. Detect USB disconnection via PCO SDK status
2. Close existing camera context
3. Wait 2 seconds for USB subsystem stabilization
4. Re-enumerate USB devices
5. Reinitialize PCO SDK connection
6. Validate camera functionality
7. Resume acquisition or notify user if failed
```

**RTX 4070 Display Recovery:**
```
1. Detect DirectX context loss or timing violations
2. Preserve current stimulus state and timing position
3. Release display context and GPU resources
4. Reinitialize DirectX 12 exclusive fullscreen mode
5. Reload stimulus frames to VRAM
6. Resume presentation from preserved state
7. Validate timing accuracy before continuing
```

**Storage System Recovery:**
```
1. Detect write failure or file system error
2. Flush all pending buffers to ensure data persistence
3. Verify file system integrity with basic checks
4. Attempt write retry to same location
5. Switch to backup directory if main location fails
6. Alert user if storage capacity or health concerns
```

### Component Restart Procedures

**Camera Subsystem Restart:**
- **Safe Window**: Only during inter-trial periods
- **State Preservation**: Save current exposure and timing settings
- **Process**: Stop capture → Close PCO SDK → Reinitialize → Validate
- **Verification**: Test frame capture before resuming acquisition

**Display Subsystem Restart:**
- **Safe Window**: During natural stimulus breaks between directions
- **State Preservation**: Current HDF5 file position and trial progress
- **Process**: Release DirectX → Reinitialize exclusive mode → Reload VRAM
- **Verification**: Frame rate and timing validation before resuming

**Emergency Session Termination:**
```
1. Immediately stop all new data capture
2. Flush camera frame buffers to disk
3. Sync all file system writes
4. Save session state and metadata
5. Close hardware connections gracefully
6. Generate diagnostic report with failure details
7. Preserve all captured data for recovery
```

## Transparency and User Communication

### Real-time Status Display

**Performance Metrics Dashboard:**
- **Stimulus Display**: Current FPS, timing deviation, frame count
- **Camera Capture**: Current FPS, dropped frames, data throughput
- **Storage**: Write speed, queue depth, available space
- **Memory**: Usage per component, pressure indicators
- **GPU**: Temperature, VRAM usage, performance status

**Alert Classifications:**
- **🟢 Normal**: All systems operating within specifications
- **🟡 Warning**: Performance degraded but scientifically acceptable
- **🔴 Critical**: Issues requiring immediate attention or affecting validity
- **⚪ Recovering**: System attempting automatic recovery

### Issue Logging and Documentation

**Comprehensive Event Log:**
```
Timestamp | Component | Severity | Event | Impact | Action
----------|-----------|----------|--------|---------|--------
12:34:56.789 | PCO_Panda | WARNING | Frame_Rate_Drop | 29.2_FPS | CONTINUE_MONITOR
12:35:12.123 | RTX_4070 | CRITICAL | Display_Context_Lost | STIM_INTERRUPTED | RESTART_DISPLAY
12:35:15.456 | System | INFO | Display_Recovery_Success | RESUMED_60FPS | NONE
```

**Diagnostic Data Collection:**
- Hardware performance metrics during failures
- Timing precision measurements
- Memory allocation snapshots
- USB bandwidth utilization patterns
- Temperature and thermal throttling events

### User Guidance System

**Decision Support:**
- **Continue**: Clear indication when safe to proceed despite warnings
- **Manual Intervention**: Specific steps when automatic recovery insufficient
- **Data Quality**: Assessment of scientific validity after recovery
- **Session Management**: Recommendations for save, restart, or continue

**Error Message Format:**
```
[COMPONENT] [SEVERITY]: [ISSUE DESCRIPTION]
Impact: [SCIENTIFIC/OPERATIONAL IMPACT]
Automatic Action: [WHAT SYSTEM IS DOING]
User Action: [WHAT USER SHOULD DO]
Data Status: [SAFETY OF EXISTING DATA]
```

## Data Integrity Protection

### HDF5 File Integrity During Failures

**Acquisition Data Protection:**
- **Write Buffering**: Ensure atomic writes to prevent partial corruption
- **Immediate Sync**: Force file system sync after critical writes
- **Backup Strategy**: Maintain session metadata separately from frame data
- **Recovery Validation**: Verify file structure integrity after failures

**Timestamp Correlation Preservation:**
- **Event Logging**: Maintain separate event logs independent of frame data
- **Cross-validation**: Multiple timestamp sources for correlation verification
- **Gap Detection**: Identify and mark timing discontinuities
- **Recovery Correlation**: Post-failure timestamp synchronization validation

### Session State Recovery

**Partial Session Continuation:**
- **Progress Tracking**: Maintain trial completion status
- **Hardware State**: Preserve calibration and configuration data
- **Resume Capability**: Restart from last completed trial
- **Data Continuity**: Ensure seamless integration of recovered sessions

**Quality Validation After Recovery:**
- **Timing Analysis**: Statistical validation of timestamp consistency
- **Frame Completeness**: Verify no data loss during recovery
- **Correlation Integrity**: Validate stimulus-camera frame relationships
- **Scientific Validity**: Assessment of recovered data quality for analysis

## Testing and Validation

### Failure Simulation

**Controlled Testing:**
- **Connection Interruption**: Simulated USB and display disconnections
- **Performance Degradation**: Artificial load testing for graceful degradation
- **Storage Stress**: Write failure simulation and recovery validation
- **Memory Pressure**: Allocation testing near 32 GB limits

**Recovery Validation:**
- **Data Integrity**: Verify no corruption during simulated failures
- **Timing Consistency**: Validate timestamp accuracy after recovery
- **User Experience**: Ensure clear communication during test scenarios
- **Performance Impact**: Measure recovery time and system overhead

### Production Monitoring

**Long-term Health Tracking:**
- **Failure Pattern Analysis**: Identify recurring issues for prevention
- **Performance Trending**: Monitor degradation over time
- **Hardware Longevity**: Track component health and replacement needs
- **Recovery Effectiveness**: Measure success rates of automatic recovery

**Continuous Improvement:**
- **Error Log Analysis**: Regular review of failure patterns
- **Threshold Optimization**: Adjust warning levels based on experience
- **Recovery Refinement**: Improve procedures based on real-world usage
- **Documentation Updates**: Maintain current guidance based on observed issues