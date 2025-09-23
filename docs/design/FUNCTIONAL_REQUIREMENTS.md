# Functional Purpose of the ISI Macroscope Control System

## Core Scientific Purpose

This software controls a neuroscience imaging system that maps how the mouse visual cortex responds to visual stimuli, creating detailed maps of brain organization through intrinsic signal imaging.

## Primary Workflow Functions

### Experiment Setup

- **Spatial Configuration**: Define where the stimulus monitor sits relative to the mouse in 3D space through a visual interface
- **Hardware Verification**: Check that camera, displays, and filters are responsive before starting
- **Protocol Definition**: Set how many times each stimulus direction will be presented

### Stimulus Generation

- **GPU-Accelerated Pattern Generation**: Generate moving bar stimuli with counter-phase checkerboard patterns using GPU compute shaders for all directions (LR, RL, TB, BT)
- **HDF5 Storage with GPU Optimization**: Store all four directions as identical HDF5 datasets optimized for GPU memory mapping
- **GPU-Calculated Angles**: Each stimulus frame has its angle computed during GPU generation and stored in HDF5 `/angles` dataset
- **GPU-Optimized Metadata**: Store frame data, angles, timestamps, and metadata in GPU-accessible HDF5 format
- **GPU-Accelerated Preview**: View generated stimuli using hardware-accelerated rendering before running experiment
- **GPU-Efficient Library Management**: Save and reuse HDF5 stimulus sets with GPU-optimized access patterns

### Data Acquisition

- **Reference Capture**: Take anatomical brain image using manually-switched green filter for structural reference
- **GPU-Controlled Presentation**: Display stimuli via direct GPU hardware control to mouse monitor at exactly 60 FPS
- **GPU Timestamp Collection**: Capture hardware timestamps using GPU timer queries for each stimulus frame presentation and camera frame capture
- **GPU-Accelerated Recording**: Capture brain response images through manually-switched red filter with GPU processing while stimulus plays at 30 FPS
- **GPU-Optimized Data Paths**: Separate critical GPU display path from GPU-accelerated monitoring path (GPU→IPC→Electron)
- **GPU-Accelerated Monitoring**: Watch GPU-downsampled previews in hardware-accelerated Electron interface while full-resolution data saves to disk
- **Protocol Execution**: Automatically cycle through all HDF5 direction files (LR, RL, TB, BT) with identical loading patterns
- **Direct Storage**: Full-resolution camera frames saved directly to disk, bypassing network streaming
- **Event Recording**: Store stimulus presentation events (timestamp, frame number, angle from HDF5 `/angles` dataset) and camera capture events separately

### Live Monitoring During Acquisition

- **Dual View**: See both stimulus being presented and brain response simultaneously
- **Stream Statistics**: Monitor frame rates, dropped frames, buffer status
- **Progress Tracking**: View which direction/trial is currently running
- **Quality Assurance**: Ensure data is being captured properly in real-time

### Data Analysis (Post-Acquisition)

- **GPU Frame Correlation**: Match camera frames to stimulus angles using GPU-accelerated timestamp processing
- **GPU Aggregation**: Combine frames by stimulus direction and angle using parallel GPU computation
- **GPU Retinotopic Calculation**: Compute how each brain region responds to different angles using GPU-accelerated correlation algorithms
- **GPU Map Generation**: Create 2D activation maps using GPU compute shaders showing magnitude of response at each angle
- **GPU-Accelerated Visualization**: Display brain maps with hardware-accelerated rendering, customizable colormaps and real-time scaling
- **GPU Re-analysis**: Process same data with different GPU-accelerated correlation strategies or parameters without re-acquiring
- **GPU-Optimized Export**: Save results using GPU-accelerated format conversion suitable for publication or further analysis

## Key Operational Features

### Session Continuity

- **State Persistence**: Resume exactly where you left off if program closes
- **Workflow Flexibility**: Move between setup, acquisition, and analysis without losing work
- **Parameter Memory**: Remember all settings between sessions
- **Data Protection**: Never lose acquisition data due to software issues

### Performance Features

- **GPU-Accelerated Acquisition**: Handle camera frame rates up to 30+ fps with GPU buffer management
- **GPU Frame Rate Coordination**: GPU-synchronized coordination of 60 fps stimulus display with 30 fps camera capture
- **GPU Large Frame Support**: Manage 2048×2048 pixel frames or larger using GPU memory optimization
- **GPU Real-time Preview**: Show GPU-downsampled live views without affecting data collection
- **GPU Concurrent Operations**: GPU-accelerated display to mouse, preview to scientist, and save to disk simultaneously
- **GPU Bandwidth Management**: Hardware-accelerated compression of previews while maintaining full-resolution storage
- **GPU-Efficient Timestamping**: Capture hardware timestamps using GPU timer queries without impacting real-time performance

### Scientific Reproducibility

- **Complete Parameter Tracking**: Record every setting used in experiment
- **Stimulus Reproducibility**: Exact same stimulus can be regenerated from parameters
- **Analysis Repeatability**: Re-run analysis with different parameters on same data
- **Session Documentation**: Automatic logging of what happened when

### Multi-Monitor Support

- **Mouse Display**: Hardware-controlled, full-resolution, frame-perfect 60 FPS stimulus presentation
- **Scientist Workstation**: Electron control interface with downsampled live previews
- **Independent Data Paths**: Critical display path isolated from monitoring streams
- **Backend Control**: Direct hardware control for mouse display, not browser-based
- **Flexible Monitoring**: Adjust preview quality without affecting mouse stimulus

## What Makes This Different from Generic Image Acquisition

- **Integrated Stimulus Generation**: Not just capturing, but creating precise visual stimuli with pre-calculated angles stored in HDF5 datasets
- **Direction-Based Organization**: Data organized by stimulus direction using uniform HDF5 file structure
- **Post-hoc Frame Correlation**: Match camera frames to stimulus angles using timestamps and HDF5 angle datasets
- **Retinotopic Analysis**: Specialized algorithms for computing angle preference maps
- **Filter Coordination**: Manual switching between anatomical (green) and functional (red) imaging
- **Scientific Workflow**: Designed specifically for retinotopic mapping protocols
- **Real-time Requirements**: Must maintain precise timestamp capture between stimulus and acquisition
- **Event-based Architecture**: Store discrete timestamped events, correlate during analysis

## End Result

The scientist gets:

- Detailed maps showing how different parts of the visual cortex respond to different angles
- Quantitative measurements of brain activation patterns
- Publication-ready visualizations of retinotopic organization
- Complete experimental documentation for reproducibility
- Ability to re-analyze with different parameters without repeating experiments

This is a complete experimental control system, not just software - it orchestrates hardware, manages timing, processes data, and produces scientific results, all while maintaining the precise control needed for neuroscience research.
