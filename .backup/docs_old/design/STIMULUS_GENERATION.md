# Stimulus Generation for ISI Retinotopic Mapping

## Overview

This document describes the visual stimulus generation pipeline for Intrinsic Signal Imaging (ISI) retinotopic mapping, implementing modern versions of the proven methods from Marshel et al. (2011) and related work.

## Dataset Discovery and Reuse

### Existing Dataset Detection

**HDF5 Metadata Scanning:**
- **Startup Scan**: Automatic discovery of existing stimulus datasets in configured directories
- **Parameter Extraction**: Fast metadata query without loading full datasets
- **Compatibility Check**: Exact parameter matching against current spatial configuration
- **Integrity Validation**: HDF5 file structure and data validation

**Discovery Process:**
```
Application Startup → Scan stimulus directories → Extract HDF5 metadata →
Compare parameters → Build available dataset index → Present options to user
```

**Metadata Comparison (Exact Match Required):**
- **Spatial Configuration**: Monitor distance, angle, screen dimensions
- **Stimulus Parameters**: Bar width, drift speed, checkerboard pattern, flicker frequency, spherical transform
- **Generation Quality**: Compression settings, geometric validation
- **Note**: Acquisition parameters (repetitions, frame rate) are configured separately during acquisition phase

### Dataset Management Interface

**Available Datasets Display:**
- **Dataset List**: All discovered stimulus datasets with metadata summary
- **Parameter Preview**: Quick view of spatial and generation parameters
- **Compatibility Status**: Clear indication of parameter match/mismatch with current settings
- **File Information**: Size, creation date, integrity status

**User Operations:**
- **Load Compatible Dataset**: Immediate use of existing dataset with matching parameters
- **Load Different Parameters**: Option to load spatial configuration from existing dataset
- **Preview Dataset**: Quick visualization of stimulus patterns
- **Delete Dataset**: Remove datasets with confirmation and disk cleanup
- **Regenerate**: Force regeneration even if compatible dataset exists (with warning)

**Duplicate Prevention:**
```
User initiates generation → Check for existing dataset with identical parameters →
If exact match found → Present options:
  - "Use existing dataset (recommended)"
  - "Regenerate anyway (will overwrite)"
  - "Cancel generation"
If no exact match → Proceed with generation
```

### Parameter Reuse Workflow

**Loading Existing Parameters:**
When user selects a dataset with different parameters:
1. **Parameter Comparison**: Show detailed diff of current vs. dataset parameters
2. **User Confirmation**: "Load these parameters and return to Setup phase?"
3. **State Transition**: Return to SETUP phase with loaded spatial configuration
4. **Validation**: Ensure loaded parameters are compatible with current hardware

**Spatial Configuration Integration:**
- **Setup Phase Link**: Changes to spatial configuration invalidate existing datasets
- **Parameter Hash**: Generate consistent hash for parameter comparison
- **Change Detection**: Track when spatial changes affect dataset compatibility
- **User Notification**: Clear indication when configuration changes invalidate existing work

## Core Stimulus Design

### Periodic Drifting Bar Stimulus (Primary for ISI)

**Based on Marshel et al. 2011 methods:**
- **Bar Width**: 20° visual angle
- **Coverage**: Full visual hemifield (153° vertical, 147° horizontal)
- **Pattern**: Counter-phase checkerboard within the bar
  - 25° squares alternating black/white
  - 6 Hz flicker rate
- **Drift Speed**: 8.5-9.5°/s for ISI experiments
- **Note**: Repetitions are configured during acquisition phase, not generation

### Direction Generation Strategy

**Efficient Generation with Uniform Storage:**
1. **Generate Primary Directions**:
   - Left-to-Right (LR) - horizontal sweep
   - Top-to-Bottom (TB) - vertical sweep

2. **Derive Reverse Directions**:
   - Right-to-Left (RL) = LR sequence reversed
   - Bottom-to-Top (BT) = TB sequence reversed

3. **Store All Identically**:
   - Four identical .h5 files with same structure
   - No special cases for derived vs generated directions
   - Uniform access patterns for all directions

4. **Benefits**:
   - 50% reduction in generation time
   - Identical access patterns for all directions
   - No runtime special cases or conditional logic
   - Simplified debugging and validation

## Spherical Coordinate Correction

### Modern Implementation of Marshel Method

**Challenge**: Flat monitor distorts visual field representation
**Solution**: Spherical-to-Cartesian transformation

**Key Parameters**:
- **Monitor Distance**: 10 cm from eye (beyond "infinite focus" point)
- **Monitor Angle**: 20° inward toward nose to match retinal orientation
- **Coordinate System**: Eye as origin, perpendicular bisector as (0°,0°)

**Mathematical Transformation**:
```
Spherical: S(θ,φ) → Cartesian: S(y,z)
- θ = altitude (vertical position)
- φ = azimuth (horizontal position)
- Maintains constant spatial frequency across visual field
```

### Correction Types

**Altitude Correction** (Vertical retinotopy):
- Applied to TB/BT directions
- Creates curved bars on flat screen
- Maintains constant eccentricity spacing

**Azimuth Correction** (Horizontal retinotopy):
- Applied to LR/RL directions
- Creates width-modulated bars on flat screen
- Maintains constant angular spacing

## Modern Enhancements

### Computational Improvements (RTX 4070 Production)
- **CUDA-Accelerated Generation**: Parallel processing using RTX 4070's 5888 CUDA cores
- **VRAM Management**: 4 GB VRAM allocation for stimulus frame cache with streaming from Samsung 990 PRO
- **32 GB RAM Constraint**: Generate directly to HDF5 to minimize system memory usage
- **Memory Mapping**: HDF5 chunk-based access optimized for 64K NTFS allocation units
- **NVENC Preview**: Hardware-accelerated preview generation using RTX 4070 encoders

### Quality Assurance
- **Geometric Validation**: Verify spherical correction accuracy
- **Timing Precision**: Frame-accurate sequence generation
- **Pattern Verification**: Automated checkerboard pattern validation
- **Calibration Integration**: Account for monitor-specific characteristics

## Stimulus Library Management

### Storage Organization (HDF5-Based)
```
stimulus_sets/
├── LR_direction.h5
│   ├── /frames          # Dataset: (n_frames, height, width, channels)
│   ├── /angles          # Dataset: (n_frames,) - frame angles in degrees
│   ├── /timestamps      # Dataset: (n_frames,) - frame timing
│   └── /metadata        # Group: complete parameter set for reuse validation
├── RL_direction.h5
│   ├── /frames          # Dataset: (n_frames, height, width, channels)
│   ├── /angles          # Dataset: (n_frames,) - frame angles in degrees
│   ├── /timestamps      # Dataset: (n_frames,) - frame timing
│   └── /metadata        # Group: complete parameter set for reuse validation
├── TB_direction.h5
│   ├── /frames          # Dataset: (n_frames, height, width, channels)
│   ├── /angles          # Dataset: (n_frames,) - frame angles in degrees
│   ├── /timestamps      # Dataset: (n_frames,) - frame timing
│   └── /metadata        # Group: complete parameter set for reuse validation
└── BT_direction.h5
    ├── /frames          # Dataset: (n_frames, height, width, channels)
    ├── /angles          # Dataset: (n_frames,) - frame angles in degrees
    ├── /timestamps      # Dataset: (n_frames,) - frame timing
    └── /metadata        # Group: complete parameter set for reuse validation
```

**Structure Notes:**
- All four direction files have identical internal structure
- No distinction in access patterns between generated and derived directions
- Each file is completely self-contained and independently loadable
- Metadata includes complete parameter set for exact matching and reuse validation

### HDF5 Metadata Schema (Dataset Reuse)

**Complete Metadata for Parameter Comparison:**
```json
/metadata {
  "dataset_info": {
    "version": "1.0",
    "created": "2024-03-15T14:30:45Z",
    "direction": "LR",
    "generation_method": "primary",
    "integrity_hash": "sha256:abc123..."
  },
  "spatial_configuration": {
    "monitor_distance_cm": 10.0,
    "monitor_angle_degrees": 20.0,
    "screen_width_cm": 52.0,
    "screen_height_cm": 52.0,
    "screen_width_pixels": 2048,
    "screen_height_pixels": 2048,
    "config_hash": "md5:def456..."
  },
  "stimulus_parameters": {
    "bar_width_degrees": 20.0,
    "drift_speed_deg_per_sec": 9.0,
    "pattern_type": "counter_phase_checkerboard",
    "checkerboard_size_degrees": 25.0,
    "flicker_frequency_hz": 6.0,
    "transform": "spherical"
  },
  "generation_quality": {
    "frame_count": 3600,
    "bit_depth": 8,
    "compression": "gzip_level_6",
    "geometric_validation_passed": true,
    "timing_precision_us": 50.0
  },
  "hardware_context": {
    "generated_on": "windows_production",
    "gpu_model": "RTX_4070",
    "cuda_version": "12.1",
    "memory_allocation_gb": 4.0
  }
}
```

**Parameter Hash Generation:**
- **Spatial Hash**: MD5 of all spatial configuration parameters in canonical order
- **Stimulus Hash**: MD5 of all stimulus generation parameters
- **Combined Hash**: SHA256 of spatial_hash + stimulus_hash for exact matching
- **Integrity Hash**: SHA256 of entire HDF5 file for corruption detection

### HDF5 Advantages (Production Optimization)
- **Uniform Interface**: All directions accessed identically on Windows and macOS
- **NTFS-Optimized Storage**: 64K chunks aligned with NTFS allocation units for Samsung 990 PRO
- **GPU Memory Mapping**: Direct CUDA memory mapping for RTX 4070 frame access
- **32 GB RAM Efficiency**: Streaming access reduces memory footprint within constraints
- **Cross-platform**: Consistent format between macOS development and Windows production
- **Samsung 990 PRO Optimization**: Sequential read patterns leverage NVMe performance
- **CUDA Parallel I/O**: Multiple directions loaded concurrently using RTX 4070

### Dataset Integrity Validation

**HDF5 File Validation (On Load):**
```cpp
// Integrity checking sequence
bool validateDataset(const std::string& filepath) {
    // 1. HDF5 File Structure Validation
    if (!H5Fis_hdf5(filepath.c_str())) return false;

    // 2. Required Dataset Presence
    hid_t file = H5Fopen(filepath.c_str(), H5F_ACC_RDONLY, H5P_DEFAULT);
    bool hasFrames = H5Lexists(file, "/frames", H5P_DEFAULT);
    bool hasAngles = H5Lexists(file, "/angles", H5P_DEFAULT);
    bool hasMetadata = H5Lexists(file, "/metadata", H5P_DEFAULT);

    // 3. Data Consistency Validation
    hsize_t frame_dims[4], angle_dims[1];
    H5LTget_dataset_info(file, "/frames", frame_dims, NULL, NULL);
    H5LTget_dataset_info(file, "/angles", angle_dims, NULL, NULL);
    bool consistent = (frame_dims[0] == angle_dims[0]); // Frame count match

    // 4. Metadata Integrity Hash Verification
    std::string stored_hash, calculated_hash;
    H5LTread_dataset_string(file, "/metadata/dataset_info/integrity_hash", stored_hash);
    calculated_hash = calculateFileHash(filepath);
    bool hashValid = (stored_hash == calculated_hash);

    H5Fclose(file);
    return hasFrames && hasAngles && hasMetadata && consistent && hashValid;
}
```

**Corruption Detection:**
- **File Structure**: HDF5 internal consistency checks
- **Data Dimensions**: Frame count consistency across datasets
- **Hash Verification**: SHA256 file hash validation against stored metadata
- **Geometric Validation**: Verify angle progression and spherical correction accuracy
- **Never Load Partial Data**: Reject any dataset failing validation checks

**Validation Results:**
- **Valid**: Dataset ready for immediate use
- **Corrupted**: Dataset marked for deletion with user notification
- **Incomplete**: Dataset removed from available list
- **Version Mismatch**: Dataset flagged for regeneration with current parameters

## Parameter Configuration

### Display Requirements (Windows Production)
- **Resolution**: 2048×2048 native with RTX 4070 VRAM optimization
- **Refresh Rate**: 60 Hz via DirectX 12 Present() with WDDM exclusive mode
- **Color Depth**: 8-bit optimized for RTX 4070 render targets
- **Gamma Correction**: Hardware gamma via DirectX 12 color space management

### Stimulus Parameters
- **Eccentricity Range**: Configurable based on experimental needs
- **Angular Resolution**: Fine-grained angle calculation (0.1° precision)
- **Temporal Resolution**: Frame-accurate timing
- **Contrast Levels**: Adjustable checkerboard contrast

## Performance Specifications

### Generation Requirements (Production Hardware)
- **Pre-generation Time**: Complete 4-direction stimulus set in <30 seconds using RTX 4070
- **Memory Constraints**: Work within 8 GB HDF5 cache allocation from 32 GB total RAM
- **Storage Optimization**: HDF5 compression + Samsung 990 PRO sequential writes at 6.9 GB/s
- **CUDA Verification**: GPU-accelerated quality checks using RTX 4070 compute shaders
- **Windows Access**: <1ms HDF5 chunk access with NTFS optimization and GPU streaming

### Real-time Requirements (13700K + RTX 4070)
- **Frame Delivery**: Exactly 60 FPS via DirectX 12 exclusive fullscreen to mouse monitor
- **Latency**: <1ms trigger-to-display using RTX 4070 hardware page flipping
- **Synchronization**: Microsecond precision timestamps using RTX 4070 timer queries
- **Stability**: Zero dropped frames using dedicated P-core + triple buffering in 3 GB VRAM

## Integration with Analysis

### Angle Pre-calculation
- **Generation Phase**: All angles computed during stimulus creation
- **Storage**: Frame-to-angle mapping preserved in metadata
- **Consistency**: Identical angle values across trials and sessions
- **Precision**: Sub-degree accuracy for fine retinotopic mapping

### Acquisition Integration
- **Uniform Direction Loading**: Load any direction file with identical code
- **File Access**: Simple access to LR.h5, RL.h5, TB.h5, BT.h5 datasets
- **Angle Mapping**: Pre-calculated angles available for correlation with acquisition data
- **Parameter Consistency**: Stimulus parameters remain constant across acquisition sessions
- **Note**: Protocol control (repetitions, timing, sequencing) handled during acquisition phase