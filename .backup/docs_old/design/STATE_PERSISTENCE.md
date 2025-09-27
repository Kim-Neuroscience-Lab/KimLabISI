# State Persistence

## Overview

This document defines the session continuity and recovery mechanisms for the ISI Macroscope Control System. The state persistence system ensures that all workflow progress, parameter configurations, and partial work survive application restarts, system failures, and hardware interruptions while maintaining scientific data integrity.

## Session State Management

### Persistent State Structure

The system maintains comprehensive session state in a structured JSON format that captures all aspects of workflow progress and configuration:

```json
{
  "session_state": {
    "current_phase": "ACQUISITION_READY",
    "last_active": "2024-03-15T14:30:45Z",
    "session_id": "20240315-143045-V1_Mapping_Mouse123",
    "workflow_progress": {
      "setup_completed": true,
      "setup_config_hash": "abc123...",
      "setup_timestamp": "2024-03-15T14:20:30Z",
      "generation_completed": true,
      "generation_timestamp": "2024-03-15T14:25:30Z",
      "generation_dataset_paths": [
        "/path/to/LR_direction.h5",
        "/path/to/RL_direction.h5",
        "/path/to/TB_direction.h5",
        "/path/to/BT_direction.h5"
      ],
      "acquisition_completed": false,
      "acquisition_progress": {
        "completed_directions": ["LR", "RL"],
        "current_direction": "TB",
        "interruption_point": null
      },
      "analysis_completed": false
    },
    "hardware_state": {
      "last_validation": "2024-03-15T14:20:15Z",
      "dev_mode_active": false,
      "degraded_components": [],
      "calibration_status": {
        "display_calibrated": true,
        "timing_calibrated": true,
        "last_calibration": "2024-03-14T10:30:00Z"
      }
    },
    "configurations": {
      "spatial_config": {
        "monitor_distance_cm": 10.0,
        "monitor_angle_degrees": 20.0,
        "screen_width_cm": 52.0,
        "screen_height_cm": 52.0,
        "screen_width_pixels": 2048,
        "screen_height_pixels": 2048,
        "config_hash": "md5:spatial_abc123"
      },
      "stimulus_params": {
        "bar_width_degrees": 20.0,
        "drift_speed_deg_per_sec": 9.0,
        "pattern_type": "counter_phase_checkerboard",
        "checkerboard_size_degrees": 25.0,
        "flicker_frequency_hz": 6.0,
        "transform": "spherical",
        "params_hash": "md5:stimulus_def456"
      }
    },
    "user_preferences": {
      "auto_resume": true,
      "resume_timeout_hours": 1,
      "default_configurations": {
        "last_used_spatial": "md5:spatial_abc123",
        "preferred_dev_mode": false
      }
    }
  }
}
```

### State Storage Location

**Cross-Platform Storage:**
- **Windows**: `%APPDATA%/ISIMacroscope/session_state.json`
- **macOS**: `~/Library/Application Support/ISIMacroscope/session_state.json`
- **Backup**: Secondary copy in project data directory for redundancy

**Atomic Updates:**
- Write to temporary file first (`session_state.tmp`)
- Atomic rename to `session_state.json` on successful write
- Maintain backup of previous state (`session_state.backup`)

## Recovery from Interruptions

### Recovery Scenarios

**Clean Application Restart:**
```
Application Launch → Read session_state.json → Validate timestamps →
Check hardware state → Offer resume options → Restore or restart
```

**Recovery Decision Logic:**
- **Recent Session** (< 1 hour): Automatic resume option presented
- **Stale Session** (1-24 hours): Resume with validation warnings
- **Old Session** (> 24 hours): Fresh start recommended, preserve configurations

**User Resume Options:**
```
┌─────────────────────────────────────────┐
│  Session Recovery                       │
├─────────────────────────────────────────┤
│  Last session: 45 minutes ago          │
│  Phase: ACQUISITION_READY               │
│  Progress: Setup ✓ Generation ✓        │
├─────────────────────────────────────────┤
│  [ Resume from last phase ]            │
│  [ Start fresh workflow ]              │
│  [ Load configurations only ]          │
└─────────────────────────────────────────┘
```

### Interrupted Acquisition Recovery

**Acquisition Interruption Handling:**
1. **Immediate Data Preservation**: Flush all buffers to Samsung 990 PRO
2. **State Snapshot**: Record exact interruption point (direction, frame, timestamp)
3. **Data Integrity Check**: Validate partial acquisition data completeness
4. **Metadata Update**: Mark session as incomplete with recovery information

**Resume Options for Interrupted Acquisition:**
```json
{
  "acquisition_progress": {
    "session_interrupted": true,
    "interruption_timestamp": "2024-03-15T14:45:30Z",
    "completed_directions": ["LR", "RL"],
    "partial_direction": {
      "direction": "TB",
      "frames_captured": 450,
      "total_frames_expected": 900,
      "last_frame_timestamp": "2024-03-15T14:45:29.123Z",
      "data_path": "/sessions/.../acquisition/TB_trial_001.h5"
    },
    "remaining_directions": ["BT"]
  }
}
```

**Resume Strategies:**
- **Continue from Interruption**: Resume current direction from interruption point
- **Restart Current Direction**: Discard partial data, restart current direction
- **Full Acquisition Restart**: Start entire acquisition protocol over

### Hardware State Validation

**Pre-Resume Hardware Checks:**
```
Hardware State Validation:
├── Camera Connection (PCO Panda 4.2)
├── Display Calibration Status
├── Storage Availability (Samsung 990 PRO)
├── Memory Allocation (32 GB constraints)
└── Timing Synchronization Status
```

**Hardware Change Detection:**
- **Configuration Hash Comparison**: Detect hardware config changes
- **Performance Baseline Validation**: Ensure hardware still meets specifications
- **Calibration Verification**: Check if recalibration needed

**Hardware Change Responses:**
- **Minor Changes**: Warning with option to continue
- **Major Changes**: Force recalibration or fresh workflow start
- **Missing Hardware**: Offer dev-mode or wait for hardware restoration

## Parameter Memory Between Sessions

### Configuration Persistence

**Spatial Configuration Memory:**
- Persist all spatial parameters (monitor distance, angle, screen dimensions)
- Maintain parameter hash for change detection
- Store calculation results (spherical transformation matrices)
- Remember validation status and quality metrics

**Stimulus Parameter Memory:**
- Save last successful stimulus generation parameters
- Maintain HDF5 dataset paths and integrity hashes
- Store generation quality metrics and validation results
- Preserve parameter combinations for quick reuse

**User Preference Persistence:**
```json
{
  "user_preferences": {
    "workflow": {
      "auto_resume": true,
      "resume_timeout_hours": 1,
      "default_spatial_config": "md5:spatial_abc123",
      "preferred_generation_quality": "high"
    },
    "interface": {
      "last_used_session_name_pattern": "V1_Mapping_Mouse{id}",
      "default_export_formats": ["png", "hdf5"],
      "notification_level": "important"
    },
    "development": {
      "dev_mode_preference": false,
      "mock_hardware_defaults": ["camera"],
      "debug_logging_enabled": false
    }
  }
}
```

### Configuration Version Management

**Schema Versioning:**
- **Current Version**: "1.0" with backward compatibility
- **Migration Support**: Automatic upgrade of older session formats
- **Validation**: Schema validation on load with error recovery

**Configuration Migration:**
```
Old Session Format → Validation → Migration → New Format → Verification
```

## Partial Work Preservation

### Incomplete Session Handling

**Work-in-Progress Preservation:**
- **Setup Phase**: Partial spatial configurations auto-saved during interaction
- **Generation Phase**: Incomplete generation progress and temporary files preserved
- **Acquisition Phase**: Partial acquisition data with metadata for resume
- **Analysis Phase**: Intermediate results and processing checkpoints saved

**Temporary Data Management:**
```
temp_data/
├── spatial_config_draft.json        # Live spatial configuration editing
├── generation_progress/             # Incomplete stimulus generation
│   ├── progress.json               # Generation state tracking
│   └── temp_frames/                # Temporary frame data
├── acquisition_buffers/             # Acquisition in progress
│   ├── frame_buffer_000.tmp       # Temporary frame buffers
│   └── metadata_buffer.json       # Real-time metadata
└── analysis_checkpoints/           # Analysis progress saves
    ├── correlation_progress.json   # Analysis state
    └── intermediate_maps.h5        # Partial analysis results
```

**Cleanup Strategies:**
- **Successful Completion**: Move temp data to permanent storage
- **Interruption**: Preserve temp data with recovery metadata
- **Fresh Start**: Offer to clean temp data or preserve for debugging

### Progressive Save System

**Auto-Save Implementation:**
- **Spatial Configuration**: Save every parameter change (debounced 2 seconds)
- **Generation Progress**: Checkpoint every 100 frames generated
- **Acquisition**: Continuous metadata logging with buffer flush every 10 seconds
- **Analysis**: Progress checkpoints every 1% completion

**Recovery Granularity:**
- **Configuration Changes**: Restore exact parameter state at interruption
- **Generation**: Resume from last completed frame batch
- **Acquisition**: Frame-level precision recovery possible
- **Analysis**: Resume from last checkpoint with minimal reprocessing

## Cross-Session State Synchronization

### Session Coordination

**Single-Session Enforcement:**
- **Lock File**: Create session lock to prevent multiple concurrent sessions
- **PID Tracking**: Track process ID for crash detection and cleanup
- **Lock Timeout**: Automatic lock release after process termination

**Session Transition Handling:**
```
Previous Session End → State Save → Lock Release → New Session Start →
State Load → Validation → Resume or Fresh Start
```

### Data Consistency Maintenance

**State Coherence Checks:**
- **File System Verification**: Ensure referenced files still exist and are accessible
- **Parameter Validation**: Verify loaded parameters are still scientifically valid
- **Hardware Compatibility**: Check loaded configs match current hardware
- **Timestamp Consistency**: Validate temporal relationships in loaded state

**Corruption Recovery:**
- **Backup State**: Automatic fallback to backup session state
- **Partial Recovery**: Extract valid portions from corrupted state
- **Fresh Start Protection**: Never lose user work, always offer data preservation options

### Integration with Error Recovery

**Coordination with ERROR_RECOVERY.md:**
- **Graceful Shutdown**: State persistence during error conditions
- **Recovery Procedures**: State restoration as part of error recovery
- **Data Preservation**: Ensure session state survives hardware failures

**State-Aware Error Handling:**
- **Context Preservation**: Maintain state context during error recovery
- **Recovery Validation**: Verify restored state is consistent after error resolution
- **User Communication**: Clear indication of what state was preserved vs. lost

## Performance and Storage Considerations

### Efficient State Management

**Storage Optimization:**
- **Compressed JSON**: gzip compression for large session files
- **Incremental Updates**: Only save changed portions of state
- **Cleanup Policies**: Automatic removal of old session backups (keep last 10)

**Memory Efficiency:**
- **Lazy Loading**: Load session state components on demand
- **Cache Management**: Keep frequently accessed state in memory
- **Memory Limits**: State storage stays within system memory constraints

### Cross-Platform Compatibility

**File System Considerations:**
- **Path Normalization**: Convert between Windows/macOS path formats
- **Permissions**: Ensure session files are readable/writable across platforms
- **Atomic Operations**: Use platform-appropriate atomic file operations

**Platform-Specific Storage:**
- **Windows**: Leverage NTFS file system features for reliability
- **macOS**: Use HFS+/APFS atomic operations for consistency
- **Development**: Seamless state transfer between platforms for development workflow

This comprehensive state persistence system ensures that scientific workflows can be interrupted and resumed at any point while maintaining complete data integrity and providing users with flexible recovery options.