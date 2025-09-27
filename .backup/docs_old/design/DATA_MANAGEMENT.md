# Data Management

## Overview

This document defines the data storage, organization, and lifecycle management strategies for the ISI Macroscope Control System, optimized for the production hardware environment (RTX 4070, 13700K, Samsung 990 PRO) and scientific reproducibility requirements.

## HDF5 Stimulus Dataset Format

### Storage Structure

All stimulus directions use identical HDF5 file structures for uniform access patterns:

```
stimulus_sets/
├── LR_direction.h5
│   ├── /frames          # Dataset: (n_frames, height, width, channels)
│   ├── /angles          # Dataset: (n_frames,) - frame angles in degrees
│   ├── /timestamps      # Dataset: (n_frames,) - frame timing
│   └── /metadata        # Group: spherical correction, protocol config
├── RL_direction.h5      # Identical structure to LR
├── TB_direction.h5      # Identical structure to LR
└── BT_direction.h5      # Identical structure to LR
```

### HDF5 Optimization for Production Hardware

**Samsung 990 PRO Optimization:**
- **Chunk Size**: 64K chunks aligned with NTFS allocation units
- **Compression**: GZIP level 6 for 60-80% storage reduction
- **Sequential Access**: Optimized for 6.9 GB/s NVMe performance
- **Parallel I/O**: Multiple direction files loaded concurrently

**RTX 4070 GPU Memory Mapping:**
- **Direct CUDA Access**: Memory-mapped HDF5 datasets for zero-copy frame loading
- **VRAM Streaming**: 4 GB stimulus cache with overflow streaming from Samsung 990 PRO
- **Memory Coalescing**: Contiguous frame access patterns for optimal GPU throughput

**32 GB RAM Constraints:**
- **Streaming Access**: HDF5 chunked reading to minimize memory footprint
- **Cache Management**: 8 GB HDF5 stimulus cache allocation within memory budget
- **Memory Mapping**: OS virtual memory for datasets larger than available RAM

### Dataset Specifications

**Frame Dataset (`/frames`):**
- **Dimensions**: (n_frames, 2048, 2048, 1) for monochrome
- **Data Type**: uint8 for stimulus display optimization
- **Chunk Size**: (1, 2048, 2048, 1) - single frame per chunk
- **Compression**: GZIP level 6 for storage efficiency

**Angle Dataset (`/angles`):**
- **Dimensions**: (n_frames,)
- **Data Type**: float64 for sub-degree precision
- **Pre-calculated**: All angles computed during generation, not runtime
- **Indexing**: Direct frame-to-angle mapping for analysis correlation

**Timestamp Dataset (`/timestamps`):**
- **Dimensions**: (n_frames,)
- **Data Type**: float64 for microsecond precision
- **Purpose**: Frame timing information for acquisition correlation
- **Resolution**: 1 μs precision matching PCO Panda 4.2 capabilities

**Metadata Group (`/metadata`):**
- **Complete Parameter Set**: All spatial and stimulus parameters for exact matching
- **Parameter Hashes**: MD5/SHA256 hashes for fast comparison and integrity verification
- **Spherical Correction**: Parameters for altitude/azimuth correction
- **Stimulus Configuration**: Bar width, drift speed, checkerboard pattern settings
- **Generation Info**: Creation timestamp, hardware used, software version
- **Calibration Data**: Monitor distance, angle, display specifications
- **Integrity Hash**: SHA256 of entire file for corruption detection

## Acquisition Session Data Organization

### Session Directory Structure

```
sessions/
└── YYYY-MM-DD_HH-MM-SS_SessionName/
    ├── metadata/
    │   ├── session_config.json      # Experiment parameters
    │   ├── hardware_info.json       # PCO Panda settings, display config
    │   └── stimulus_manifest.json   # HDF5 files used
    ├── acquisition/
    │   ├── camera_frames/           # Raw PCO Panda 4.2 captures
    │   │   ├── LR_trial_001.h5     # 16-bit, 2048×2048 frames
    │   │   ├── LR_trial_002.h5
    │   │   └── ...
    │   ├── stimulus_events/         # Presentation timing logs
    │   │   ├── LR_events.csv       # Frame numbers, timestamps, angles
    │   │   └── ...
    │   └── system_logs/            # Performance monitoring
    │       ├── timing_violations.log
    │       ├── memory_usage.log
    │       └── gpu_performance.log
    └── analysis/                   # Generated during analysis phase
        ├── correlation/            # Timestamp correlation results
        ├── retinotopy/            # Generated maps
        └── quality_metrics/       # Statistical validation
```

### PCO Panda 4.2 Frame Storage

**Camera Frame Files:**
- **Format**: HDF5 with 16-bit datasets
- **Compression**: LZF for real-time compression during acquisition
- **Chunk Size**: Optimized for USB 3.1 Gen 1 throughput (125 MB/sec)
- **Metadata**: Exposure settings, timestamp precision, frame rate

**16-bit Processing Pipeline:**
- **Dynamic Range**: Preserve full 87 dB range from PCO Panda
- **Storage Efficiency**: ~16.7 MB per frame (2048×2048×16-bit)
- **GPU Processing**: Direct CUDA 16-bit to 8-bit conversion for display
- **Memory Management**: 2 GB frame buffer allocation within 32 GB constraint

### Event Correlation Data

**Stimulus Events CSV Format:**
```csv
frame_number,hardware_timestamp,hdf5_angle,direction,trial_number
0,1234567890.123456,0.0,LR,1
1,1234567890.140123,-0.5,LR,1
...
```

**Camera Events CSV Format:**
```csv
frame_number,hardware_timestamp,exposure_duration,file_path
0,1234567890.125000,0.033333,LR_trial_001.h5:frame_0
1,1234567890.158333,0.033333,LR_trial_001.h5:frame_1
...
```

## File Naming Conventions

### Session Naming
- **Format**: `YYYY-MM-DD_HH-MM-SS_SessionName`
- **Example**: `2024-03-15_14-30-45_V1_Mapping_Mouse123`
- **Requirements**: No spaces, Windows/NTFS compatible

### Stimulus Files
- **Direction Format**: `{direction}_direction.h5`
- **Examples**: `LR_direction.h5`, `RL_direction.h5`, `TB_direction.h5`, `BT_direction.h5`
- **Versioning**: Include generation timestamp in metadata, not filename

### Acquisition Files
- **Camera Data**: `{direction}_trial_{number:03d}.h5`
- **Event Logs**: `{direction}_events.csv`
- **System Logs**: `{component}_{metric}.log`

### Analysis Results
- **Correlation**: `correlation_{direction}_{trial}.h5`
- **Maps**: `retinotopy_{map_type}_{parameters}.h5`
- **Figures**: `{map_type}_{colormap}_{timestamp}.png`

## Directory Structure Standards

### Root Organization
```
ISI_Data/
├── stimulus_library/          # Reusable HDF5 stimulus sets
├── sessions/                  # Acquisition session data
├── analysis_templates/        # Standard analysis configurations
└── calibration/              # Hardware calibration data
```

### Storage Location Strategy
- **Stimulus Library**: Samsung 990 PRO for fast loading (read-optimized)
- **Active Acquisition**: Samsung 990 PRO for real-time writes
- **Archived Sessions**: Secondary storage after analysis completion
- **Temporary Processing**: RAM disk for intermediate analysis results

## Import/Export Capabilities

### HDF5 Import/Export
- **Cross-platform**: Consistent format between macOS development and Windows production
- **Version Compatibility**: HDF5 1.12+ with backward compatibility
- **Metadata Preservation**: Complete parameter and calibration tracking
- **Batch Operations**: GPU-accelerated bulk format conversions

### Scientific Format Support
- **Export Formats**: MATLAB (.mat), Python pickle, NumPy (.npz)
- **Visualization**: PNG, TIFF for publication-quality figures
- **Analysis**: CSV for statistical software integration
- **Archival**: Compressed HDF5 for long-term storage

### CUDA-Accelerated Processing
- **Format Conversion**: GPU-accelerated transcoding between formats
- **Compression**: RTX 4070 hardware compression for export optimization
- **Validation**: GPU-based data integrity checking during transfer
- **Parallel I/O**: Concurrent read/write operations using CUDA streams

## Dataset Discovery and Reuse

### HDF5 Dataset Scanning

**Fast Metadata Extraction:**
```cpp
// Efficient metadata scanning without loading full datasets
struct DatasetInfo {
    std::string filepath;
    std::string parameter_hash;
    std::string integrity_hash;
    bool is_valid;
    json metadata;
};

std::vector<DatasetInfo> scanForDatasets(const std::string& directory) {
    std::vector<DatasetInfo> datasets;

    for (const auto& entry : std::filesystem::recursive_directory_iterator(directory)) {
        if (entry.path().extension() == ".h5") {
            DatasetInfo info;
            info.filepath = entry.path();

            // Fast metadata extraction
            hid_t file = H5Fopen(info.filepath.c_str(), H5F_ACC_RDONLY, H5P_DEFAULT);
            if (file >= 0) {
                // Extract parameter hash for fast comparison
                H5LTread_dataset_string(file, "/metadata/spatial_configuration/config_hash",
                                       info.parameter_hash);

                // Extract integrity hash
                H5LTread_dataset_string(file, "/metadata/dataset_info/integrity_hash",
                                       info.integrity_hash);

                // Read full metadata for UI display
                readMetadataGroup(file, "/metadata", info.metadata);

                // Quick validation check
                info.is_valid = validateDatasetQuick(file);

                H5Fclose(file);
                datasets.push_back(info);
            }
        }
    }

    return datasets;
}
```

**Parameter Comparison Logic:**
- **Hash-Based Matching**: Compare parameter hashes before detailed comparison
- **Exact Match Requirement**: All spatial and stimulus parameters must match exactly
- **Fast Rejection**: Use hashes to quickly eliminate incompatible datasets
- **Detailed Comparison**: Full parameter diff only for matching hashes

### Dataset Index Management

**In-Memory Index:**
- **Startup Scanning**: Build dataset index during application initialization
- **Incremental Updates**: Monitor filesystem for new/changed datasets
- **Cache Management**: Store metadata in memory for fast access
- **Persistence**: Save index to disk for faster subsequent startups

**Index Structure:**
```json
{
  "dataset_index": {
    "version": "1.0",
    "last_scan": "2024-03-15T14:30:45Z",
    "datasets": [
      {
        "filepath": "/path/to/LR_direction.h5",
        "parameter_hash": "md5:abc123...",
        "integrity_hash": "sha256:def456...",
        "spatial_config": {...},
        "stimulus_params": {...},
        "created": "2024-03-15T14:25:30Z",
        "file_size": 2147483648,
        "is_valid": true
      }
    ]
  }
}
```

### File Discovery Mechanisms

**Directory Monitoring:**
- **Filesystem Watchers**: Monitor stimulus directories for changes
- **Event-Driven Updates**: Update index when files are added/removed/modified
- **Background Scanning**: Periodic full scans to catch missed changes
- **Cross-Platform**: Use appropriate filesystem monitoring APIs

**Discovery Performance:**
- **Parallel Scanning**: Multi-threaded directory traversal
- **Metadata Caching**: Cache metadata to avoid repeated HDF5 opens
- **Selective Scanning**: Only scan files with recent modification times
- **Index Optimization**: Sort and index datasets for fast lookup

## Data Integrity and Validation

### HDF5 File Integrity
- **Checksums**: Built-in HDF5 checksums for corruption detection
- **Validation**: Automated integrity checks during session loading
- **Repair**: Limited repair capabilities for minor corruption
- **Backup Strategy**: Redundant copies during critical acquisition phases

### Timestamp Correlation Validation
- **Precision Checks**: Verify microsecond-level timestamp accuracy
- **Drift Detection**: Monitor systematic timing drift between hardware
- **Correlation Quality**: Statistical measures of timestamp alignment
- **Error Flagging**: Mark frames with questionable timing data

### Session Completeness
- **Manifest Verification**: Check all expected files present
- **Frame Count Validation**: Verify frame sequences are complete
- **Metadata Consistency**: Cross-check settings across all components
- **Quality Metrics**: Automated assessment of acquisition quality

## Performance Monitoring

### Storage Performance
- **Throughput Monitoring**: Real-time write speed tracking to Samsung 990 PRO
- **Queue Depth**: Monitor storage queue utilization during acquisition
- **Fragmentation**: NTFS defragmentation status for optimal performance
- **Free Space**: Ensure adequate space for complete sessions

### Memory Management
- **32 GB Budget Tracking**: Monitor allocation across all components
- **GPU VRAM Usage**: Track RTX 4070 memory allocation efficiency
- **Cache Hit Rates**: HDF5 cache performance for stimulus loading
- **Memory Leaks**: Long-running session memory stability monitoring

### Access Pattern Optimization
- **Sequential vs Random**: Optimize for Samsung 990 PRO characteristics
- **Prefetching**: Predictive loading for analysis workflows
- **Concurrent Access**: Multiple thread/process coordination
- **Bandwidth Utilization**: Maximize PCIe 4.0 NVMe performance