# Analysis Pipeline

## Overview

This document describes the post-acquisition analysis pipeline that correlates stimulus presentation with camera capture data to generate retinotopic maps using a modernized implementation of established intrinsic signal imaging methods.

## Analysis Methodology

The analysis pipeline implements a **modernized version** of proven ISI methods from:
- **Zhuang et al., 2017** ([PMC5381647](https://pmc.ncbi.nlm.nih.gov/articles/PMC5381647/)) - Automated visual area identification
- **Marshel et al., 2011** ([Neuron](https://www.cell.com/neuron/fulltext/S0896-6273(11)01046-4)) - Foundational ISI retinotopic mapping
- **Kalatsky & Stryker, 2003** - Periodic stimulus analysis methods

**Key Approach**: We implement the validated ISI analysis methodology for hemodynamic signals while leveraging modern computational capabilities. Note: This is specifically for **Intrinsic Signal Imaging**, not calcium imaging or two-photon methods.

This document covers the complete analysis pipeline from data preprocessing through final retinotopic map generation.

## Correlation Phase

After data capture, the system correlates stimulus and camera events using the timestamps collected during acquisition.

### Correlation Algorithm

For each camera frame:

1. Identify the time window of the camera exposure
2. Find all stimulus frames that occurred during this window
3. Calculate the weighted contribution of each stimulus angle
4. Associate the camera frame with its corresponding angle data

### Handling Edge Cases

**Dropped Frames:**

- Mark gaps in the sequence
- Allow analysis to proceed with available data
- Flag affected trials for scientist review

**Timing Drift:**

- Detect systematic drift between clocks
- Apply correction factors during correlation
- Document any adjustments for reproducibility

## Retinotopy Generation

### Modern Implementation of Established Methods

With correlated data, the system implements the complete proven scientific pipeline:

#### 1. Stimulus Response Extraction
- **Aggregate by Direction**: Group camera frames by stimulus direction (LR, RL, TB, BT)
- **Temporal Averaging**: Average multiple trials for each direction to improve signal-to-noise ratio
- **Baseline Correction**: Subtract pre-stimulus baseline or use differential imaging

#### 2. ISI-Specific Fourier Analysis (Kalatsky & Stryker Method)
- **Continuous Block Analysis**: Process 16-bit data from PCO Panda 4.2 (2048×2048) during continuous stimulus
- **CUDA Fourier Processing**: Compute phase using cuFFT for 4.2 MPixel frames leveraging 87 dB dynamic range
- **Hemodynamic Delay Compensation**: Account for intrinsic signal delay relative to neural activity
- **Bidirectional Analysis**: Use opposing directions (LR vs RL, TB vs BT) to estimate center point
- **16-bit Amplitude Thresholding**: Leverage PCO Panda's 21,500:1 dynamic range for precise signal detection

#### 3. ISI Retinotopic Coordinate Generation
- **Horizontal Retinotopy**: Generate azimuth map from LR/RL stimulus directions with azimuth correction
- **Vertical Retinotopy**: Generate elevation map from TB/BT stimulus directions with altitude correction
- **Spherical Coordinate Conversion**: Convert phase values to degrees using spherical coordinate system
- **Hemodynamic Delay Correction**: Subtract intrinsic signal delays between opposing bar drift directions
- **Center Point Estimation**: Determine best estimate of cortical position responding to each visual field location

#### 4. Visual Field Sign Calculation (Zhuang et al. Method)
- **Gradient Computation**: Calculate spatial gradients of azimuth and elevation maps
- **Angle Calculation**: Compute angle between retinotopic gradients at each pixel
- **Sign Determination**: Calculate sine of gradient angle to determine visual field sign
- **Smoothing**: Apply spatial filtering to reduce noise while preserving boundaries

#### 5. Automated Area Segmentation
- **Boundary Detection**: Identify locations where visual field sign reverses
- **Patch Identification**: Segment continuous regions of consistent visual field sign
- **Size Filtering**: Remove patches below minimum area threshold
- **Topology Validation**: Ensure patches represent coherent visual space regions

#### 6. Statistical Analysis and Quality Metrics
- **Response Magnitude Maps**: Compute activation strength at each pixel
- **Coherence Analysis**: Measure consistency of retinotopic organization
- **Coverage Maps**: Identify regions with sufficient data quality
- **Confidence Scoring**: Statistical confidence in area boundary determination

### Modern Implementation Enhancements

#### ISI-Specific Computational Improvements (RTX 4070 Production)
- **CUDA Acceleration**: Leverage RTX 4070's 5888 CUDA cores for parallel FFT on ISI sequences
- **VRAM Management**: 2 GB VRAM allocation for analysis workspace with 32 GB RAM streaming
- **cuFFT Operations**: Use NVIDIA cuFFT library for optimized hemodynamic signal processing
- **Memory Efficiency**: Stream large ISI datasets through 32 GB RAM constraint using HDF5 chunking
- **13700K Parallel Processing**: Utilize all 16 cores (8P + 8E) for independent cortical regions
- **RTX 4070 ISI Pipeline**: Specialized CUDA kernels optimized for hemodynamic signal analysis

#### ISI Algorithm Refinements (CUDA Implementation)
- **CUDA Filtering**: Spatial/temporal filtering using RTX 4070 compute shaders and shared memory
- **cuDNN Statistics**: Hardware-accelerated median/percentile statistics using NVIDIA cuDNN
- **CUDA Interpolation**: RTX 4070 texture units for sub-pixel retinotopic precision
- **CUDA Temporal Processing**: Optimized CUDA kernels for 30 FPS ISI temporal averaging
- **CUDA Baseline Correction**: Memory-coalesced baseline subtraction within 32 GB constraints

#### Quality Control
- **Real-time Validation**: Immediate feedback on data quality during analysis
- **Automated Parameter Tuning**: Optimize thresholds based on data characteristics
- **Uncertainty Quantification**: Bootstrap methods for confidence interval estimation
- **Interactive Refinement**: Allow manual adjustment of automatically detected boundaries

#### Visualization and Export (Windows Production)
- **DirectX 12 Rendering**: Hardware-accelerated visualization using RTX 4070 with DirectX 12
- **CUDA Export Processing**: Hardware-accelerated HDF5/Zarr conversion using RTX 4070
- **NVENC Figure Generation**: Publication-quality visualizations using RTX 4070 encoders
- **Real-time CUDA Analysis**: Parameter adjustment with <100ms feedback using CUDA streams
- **Windows GPU Memory**: Direct CUDA memory mapping for interactive visualization within 2 GB VRAM budget

## Analysis Capabilities

### Complete Pipeline Options

#### Standard Analysis
- Full retinotopic mapping with automated area identification
- Publication-ready visualizations with standard colormaps
- Statistical significance testing for area boundaries
- Export of maps in standard formats

#### Advanced Analysis
- Custom parameter optimization for specific experimental conditions
- Alternative visual field sign calculation methods
- Manual refinement of automatically detected boundaries
- Comparative analysis across multiple sessions

#### Re-analysis Flexibility
- Modify correlation parameters without re-acquisition
- Apply different filtering strategies to same dataset
- Test alternative thresholds for area detection
- Generate maps with different visualization parameters

All analysis modes preserve the original data and maintain complete parameter tracking for reproducibility.

## Quality Metrics

The system maintains correlation quality metrics:

- **Timing Precision**: Timestamp resolution and clock synchronization quality
- **Coverage Completeness**: Percentage of frames successfully correlated
- **Drift Indicators**: Systematic timing shifts detected
- **Confidence Scores**: Statistical confidence in angle-to-activation mappings

## Complete Analysis Data Flow

```
Raw Acquisition Data
├── Stimulus Events (timestamps + angles)
└── Camera Frames (timestamps + images)
            ↓
    Temporal Correlation & Frame Matching
            ↓
    Direction-Based Aggregation (LR, RL, TB, BT)
            ↓
    Fourier Analysis (FFT at stimulus frequency)
            ↓
    Phase Map Generation (azimuth & elevation)
            ↓
    Visual Field Sign Calculation
            ↓
    Automated Area Segmentation
            ↓
    Statistical Validation & Quality Metrics
            ↓
    Visualization & Export
    ├── Retinotopic maps
    ├── Area boundary overlays
    ├── Quality assessment reports
    └── Publication-ready figures
```

## Scientific Validity

The correlation must be accurate enough to:

- Distinguish responses to different stimulus angles
- Maintain spatial resolution in retinotopic maps
- Support statistical analysis of angle preferences
- Enable comparison across trials and experiments

The acceptable timing tolerance depends on:

- Stimulus movement speed
- Angular resolution requirements
- Neural response dynamics
- Experimental protocol specifications
