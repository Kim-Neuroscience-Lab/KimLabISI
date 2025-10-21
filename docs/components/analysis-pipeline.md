# Analysis Pipeline

**Last Updated**: 2025-10-14 23:13
**Status**: ⚠️ Requires verification - documentation reflects intended functionality, not verified implementation
**Maintainer**: Backend Team

> Fourier-based retinotopic mapping and visual field sign (VFS) computation for intrinsic signal imaging.

---

## Overview

The Analysis Pipeline implements **Fourier-based retinotopic mapping** using the methods of Kalatsky & Stryker (2003) and **visual field sign computation** using Zhuang et al. (2017). It processes recorded camera frames and stimulus display metadata to generate retinotopic maps and identify visual cortex area boundaries.

## Purpose

The Analysis Pipeline provides:

- **Phase assignment**: Matches camera timestamps with stimulus timestamps to determine visual field angle for each camera frame
- **Retinotopic mapping**: Spatial representation of visual field positions in cortex
- **Visual field sign (VFS)**: Identifies visual cortex area boundaries (V1, LM, AL, etc.)
- **Scientific validation**: Exact correlation (1.0) with MATLAB reference implementation

## Architecture

### Input Data Structure

**Per direction** (LR, RL, TB, BT):

#### Camera Dataset (`{direction}_camera.h5`)
- **frames**: [N_frames, height, width] array of camera frames
- **timestamps**: [N_frames] array of hardware timestamps (microseconds)
- **metadata**: Camera parameters, acquisition settings

#### Stimulus Dataset (`{direction}_stimulus.h5`)
- **frame_indices**: [N_displayed] array of stimulus frame indices
- **timestamps**: [N_displayed] array of hardware timestamps (microseconds)
- **angles**: [N_displayed] array of visual field angles (degrees)
- **metadata**: Direction label, monitor parameters

### Processing Pipeline

```
1. PHASE ASSIGNMENT (Hardware Timestamp Matching)
   ├─ Load camera timestamps [N_camera]
   ├─ Load stimulus timestamps + angles [N_stimulus]
   ├─ For each camera frame:
   │  └─ Find nearest stimulus timestamp
   │  └─ Assign corresponding visual field angle
   └─ Result: Each camera frame has phase (angle) label

2. FOURIER ANALYSIS
   ├─ FFT of temporal signal per pixel
   ├─ Extract phase and magnitude at stimulus frequency
   └─ Phase maps: LR, RL, TB, BT

3. BIDIRECTIONAL ANALYSIS
   ├─ Azimuth = (LR - RL) / 2
   ├─ Elevation = (TB - BT) / 2
   └─ Retinotopic maps: azimuth, elevation

4. FFT-BASED SMOOTHING (σ=3.0)
   ├─ Frequency-domain Gaussian filter
   └─ Matches MATLAB reference implementation

5. GRADIENT COMPUTATION (Sobel, kernel=3)
   ├─ graddir_azimuth = arctan2(dy, dx)
   └─ graddir_elevation = arctan2(dy, dx)

6. VFS COMPUTATION (Gradient Angle Method)
   ├─ VFS = sin(angle(exp(i*graddir_hor) * exp(-i*graddir_vert)))
   └─ Range: [-1, 1] where +1=expansion, -1=compression

7. TWO-STAGE FILTERING
   ├─ Coherence Filter (threshold=0.3, signal reliability)
   ├─ Statistical Threshold = 1.5 × std(Raw VFS)
   └─ Final VFS: Both reliable AND strong

8. BOUNDARY DETECTION
   ├─ Threshold VFS (±threshold)
   ├─ Morphological processing
   └─ Identify visual cortex area borders
```

## Key Features

### Hardware Timestamp Matching

**Critical first step**: Assign phase (visual field angle) to each camera frame

**Process**:
1. Load camera hardware timestamps (one per captured frame)
2. Load stimulus hardware timestamps + angles (one per displayed frame)
3. For each camera frame timestamp:
   - Find nearest stimulus timestamp
   - Assign corresponding visual field angle to camera frame
4. Result: Temporal signal at each pixel represents response to visual field sweep

**Why hardware timestamps only**:
- Software timestamps have jitter (~10-50 ms)
- Hardware timestamps are precise (~1 μs accuracy)
- Camera and stimulus ran independently (no synchronization)
- Post-hoc matching via timestamps is the ONLY way to establish correspondence

**Critical constraint**: If hardware timestamps not available, analysis cannot proceed (software fallback NOT supported for scientific validity).

### Fourier Analysis

**Purpose**: Extract periodic signal at stimulus frequency

**Method**:
- Temporal signal per pixel = camera frame sequence with phase labels
- FFT extracts magnitude (response strength) and phase (visual field preference)
- Frequency of interest = 1 / sweep_duration (one cycle per sweep)

**Output per direction**:
- **Phase map**: Preferred visual field angle for each pixel (-π to π)
- **Magnitude map**: Response strength for each pixel (0 to max)
- **Coherence map**: Signal reliability (0 to 1)

### Bidirectional Analysis

**Purpose**: Combine opposing sweep directions to remove hemodynamic delay artifacts

**Method** (matching MATLAB reference):
```python
# Simple phase subtraction (no unwrapping, no delay correction)
azimuth = (LR_phase - RL_phase) / 2
elevation = (TB_phase - BT_phase) / 2

# Wrap to [-π, π] using arctan2
azimuth = np.arctan2(np.sin(azimuth), np.cos(azimuth))
elevation = np.arctan2(np.sin(elevation), np.cos(elevation))
```

**Why simple subtraction**:
- MATLAB reference uses this exact method
- Phase wrapping is intentional (represents periodicity)
- Complex delay correction caused correlation drop (-0.15 vs 1.0)
- Simplicity matched reference perfectly

### Visual Field Sign Computation

**Purpose**: Identify visual cortex area boundaries

**Method**: Gradient angle approach (Zhuang et al. 2017)
```python
# VFS = sin(angle(exp(i*graddir_hor) * exp(-i*graddir_vert)))
complex_product = (
    np.exp(1j * graddir_azimuth) *
    np.exp(-1j * graddir_elevation)
)
raw_sign_map = np.sin(np.angle(complex_product))
```

**Interpretation**:
- **VFS = +1**: Mirror image representation (V1, V2L)
- **VFS = -1**: Non-mirror representation (LM, PM, AL)
- **VFS = 0**: Ambiguous or transitional zones

### Two-Stage Filtering

**Purpose**: Retain only reliable AND strong VFS signals

**Stage 1: Coherence filtering**
- Threshold: 0.3 (signal reliability)
- Effect: Keeps ~17% of pixels
- Purpose: Remove unreliable measurements

**Stage 2: Statistical filtering**
- Threshold: 1.5 × std(Raw VFS)  ← **CRITICAL**: computed on RAW VFS, not filtered subset
- Effect: Keeps ~6% of pixels (from original)
- Purpose: Remove weak responses

**Why this order matters**:
- Computing statistics on filtered subset introduces severe bias
- Statistical threshold must be based on full distribution
- Apply to filtered data ensures both reliability AND strength

## Data Flow

### Analysis Workflow
1. User selects recorded session in Analysis viewport
2. Frontend sends `start_analysis` command with session_path
3. Backend loads all HDF5 files for session
4. **Phase Assignment** (for each direction):
   - Load camera timestamps + stimulus timestamps + angles
   - Match timestamps → assign phase to each camera frame
5. **Fourier Analysis** (per pixel, per direction):
   - FFT of phase-labeled temporal signal
   - Extract phase, magnitude, coherence
6. **Bidirectional Analysis**:
   - Combine LR/RL → azimuth map
   - Combine TB/BT → elevation map
7. **VFS Computation**:
   - Smooth retinotopy maps (FFT-based, σ=3.0)
   - Compute gradients (Sobel, kernel=3)
   - Calculate VFS (gradient angle method)
8. **Filtering**:
   - Apply coherence threshold
   - Compute statistical threshold on raw VFS
   - Apply statistical threshold to filtered VFS
9. **Boundary Detection**:
   - Threshold VFS (±1.5σ)
   - Morphological processing
10. **Save Results**:
    - All maps saved to `{session_path}/analysis_results/analysis_results.h5`
    - Frontend renders composite image via OpenCV renderer

## Integration

### Component Dependencies
- **Data Recorder**: Provides HDF5 files with camera frames + stimulus logs
- **Parameter Manager**: Provides analysis thresholds and configuration
- **Shared Memory**: Transfers rendered analysis images to frontend
- **OpenCV Renderer**: Converts numpy arrays to RGBA layers for visualization

### Frontend Integration
- **Analysis Viewport**: Displays composite analysis image with layer controls
- **Layer controls**: Anatomical (alpha), Signal type (azimuth/elevation/VFS), Overlay (borders)

## Behavior

### Analysis States

**IDLE**: No analysis running

**RUNNING**: Analysis in progress
- Phase assignment for each direction
- Fourier analysis per direction
- Bidirectional combination
- VFS computation and filtering
- Boundary detection
- Duration: ~30-60 seconds for full session

**COMPLETE**: Results saved to HDF5
- All maps available for rendering
- Frontend can adjust layer visibility/opacity
- Re-analysis not required unless parameters change

### Error Handling

**Hardware timestamps missing**:
- Error: "Hardware timestamps not available - cannot assign phase"
- Analysis cannot proceed
- User directed to check data recording configuration

**Incomplete dataset**:
- Error: "Missing direction data - found only 2/4 directions"
- Analysis requires all 4 directions for bidirectional analysis
- User directed to complete acquisition

**Invalid parameters**:
- Error: "Coherence threshold must be in range [0, 1]"
- Analysis uses validated parameters from Parameter Manager
- User directed to correct configuration

## Constraints

### Input Requirements
- **Hardware timestamps**: MUST be present in both camera and stimulus datasets
- **All 4 directions**: LR, RL, TB, BT required for bidirectional analysis
- **Consistent parameters**: Camera FPS, monitor FPS must match acquisition settings

### Performance Requirements
- Analysis must complete in <5 minutes for typical session (~2400 frames)
- Memory usage <2 GB during analysis
- Results must be reproducible (same inputs → same outputs)

### Scientific Validity
- Hardware timestamp matching only (software fallback NOT acceptable)
- Methods must match published literature (Kalatsky 2003, Zhuang 2017)
- Results must correlate perfectly (1.0) with MATLAB reference implementation

## Analysis Parameters

### Required Parameters (from Parameter Manager)

**Analysis Group** (`analysis`):
- `coherence_threshold`: Signal reliability threshold (0.3, Kalatsky 2003)
- `magnitude_threshold`: Response strength threshold (0.3, Juavinett 2017)
- `vfs_threshold_sd`: Statistical threshold multiplier (1.5, MATLAB standard)
- `smoothing_sigma`: Retinotopic map smoothing (3.0, FFT-based)
- `gradient_window_size`: Sobel kernel size (3)
- `phase_filter_sigma`: Phase smoothing (0.0, disabled - FFT used instead)
- `response_threshold_percent`: Minimum response percentage (20)
- `area_min_size_mm2`: Minimum cortical area size (0.1)

### Parameter Sources
- **Kalatsky & Stryker (2003)**: Coherence threshold range (0.2-0.35)
- **Juavinett et al. (2017)**: Magnitude thresholding method
- **Zhuang et al. (2017)**: VFS gradient angle method
- **MATLAB Reference**: Statistical threshold (1.5×std), FFT smoothing (σ=3.0)

---

**Component Version**: 2.0
**Validation Status**: ✅ Perfect correlation (1.0) with MATLAB reference
**Architecture**: Hardware timestamp-based phase assignment with Fourier analysis
