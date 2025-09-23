# System Overview

## Project Purpose

The ISI Macroscope Control System is a comprehensive neuroscience research platform designed for Intrinsic Signal Imaging (ISI) retinotopic mapping. The system implements modern versions of proven methods from Marshel et al. (2011) and related work, providing precise control over visual stimulus presentation and brain imaging acquisition for mapping the mouse visual cortex.

## Scientific Goals

- **Retinotopic Mapping**: Generate detailed maps of how the mouse visual cortex responds to visual stimuli
- **Modern ISI Implementation**: Leverage contemporary hardware (RTX 4070, Intel 13700K) for enhanced precision and performance
- **Scientific Reproducibility**: Ensure consistent, repeatable experimental protocols with comprehensive data integrity
- **Research Acceleration**: Streamline the experimental workflow from setup through analysis

## System Architecture

### High-Level Design

The system follows a **thin client architecture** with clear separation between user interface and scientific operations:

```
┌─────────────────────┐    IPC/WebSocket    ┌──────────────────────────┐
│  Electron Frontend  │ ◄────────────────► │   Python Backend        │
│  (Monitoring Only)  │                    │   (Scientific Control)  │
└─────────────────────┘                    └──────────────────────────┘
                                                       │
                                           ┌───────────▼───────────┐
                                           │  Hardware Interfaces  │
                                           │  • RTX 4070 Display   │
                                           │  • PCO Panda Camera   │
                                           │  • Samsung 990 PRO    │
                                           └───────────────────────┘
```

### Component Relationships

**Frontend (Electron + React)**
- **Purpose**: User interface for configuration, monitoring, and visualization
- **Data Access**: Receives only downsampled previews for monitoring
- **Responsibilities**: Workflow navigation, parameter configuration, real-time status display
- **Isolation**: Scientific data never passes through frontend

**Backend (Python + C++ Extensions)**
- **Purpose**: Scientific control, hardware management, data processing
- **Responsibilities**: Hardware timing, data acquisition, stimulus generation, analysis
- **Communication**: IPC/WebSocket for frontend coordination (no internal APIs)
- **Performance**: Direct hardware control for time-critical operations

## Technology Stack (2025)

### Frontend Stack
- **Electron 32+**: Cross-platform desktop application framework (Node 22 support)
- **React 18/19**: UI framework with component-based architecture
- **TypeScript**: Type safety and development tooling
- **Vite**: Modern build tool and development server
- **Tailwind CSS**: Utility-first styling framework
- **Zustand 5.0.8**: Lightweight state management with excellent TypeScript support
- **React Three Fiber 9.3.0**: 3D visualization for spatial configuration (WebGPU support)
- **Chart.js + react-chartjs-2**: Data visualization for analysis results
- **Electron IPC**: Native communication with backend
- **Vitest**: Testing framework (Vite-integrated)

### Backend Stack
- **Python 3.11+**: Core runtime with asyncio for concurrent operations
- **Poetry**: Dependency management and packaging
- **Pydantic V2**: Data validation, settings management, and IPC message validation
- **h5py**: HDF5 file handling for stimulus datasets and acquisition data
- **CuPy 13.6.0**: CUDA acceleration (supports CUDA 11.x-13.x, NumPy 1.22-2.3)
- **pybind11 2.13.6+**: C++ bindings for DirectX and PCO SDK integration
- **NumPy/SciPy**: Scientific computing foundation
- **OpenCV + Pillow**: Image processing and computer vision
- **multiprocessing**: Parallel processing and hardware isolation
- **pytest**: Testing framework

### Development Tools
- **ESLint + Prettier**: Frontend code quality and formatting
- **black + ruff**: Python code formatting and linting
- **GitHub Actions**: Cross-platform builds and CI/CD
- **npm/pnpm**: Frontend package management

## Workflow Overview

The system implements a **12-state workflow** managed by a comprehensive state machine:

```
STARTUP → SETUP_READY → SETUP → GENERATION_READY → GENERATION →
ACQUISITION_READY → ACQUISITION → ANALYSIS_READY → ANALYSIS

                    ↕ (Error Handling) ↕
            ERROR ↔ RECOVERY ↔ DEGRADED
```

### Workflow Phases

**Setup Phase**
- Interactive 3D spatial configuration using React Three Fiber
- Monitor positioning, distance, and angle calibration
- Real-time parameter validation and visual feedback

**Generation Phase**
- CUDA-accelerated visual stimulus creation
- HDF5 dataset management with parameter matching
- Spherical coordinate correction for flat display

**Acquisition Phase**
- 60 FPS stimulus presentation with frame-perfect timing
- 30 FPS camera capture with microsecond synchronization
- Real-time data streaming to Samsung 990 PRO storage

**Analysis Phase**
- GPU-accelerated frame correlation and ISI processing
- Retinotopic map generation with interactive visualization
- Statistical validation and export capabilities

## Key Design Principles

### Data Integrity
- **Scientific Data Isolation**: Full-resolution stimulus and camera data never passes through Electron frontend
- **State Persistence**: Complete workflow state survives application restarts
- **Parameter Separation**: Generation-time parameters distinct from acquisition-time protocols
- **Timestamp Preservation**: Microsecond-precision correlation between stimulus and camera events

### Hardware Control
- **Direct Hardware Access**: Backend maintains exclusive control over timing-critical operations
- **Performance Isolation**: Dedicated CPU cores for real-time display and camera control
- **Error Recovery**: Comprehensive hardware failure detection with graceful degradation
- **Cross-Platform**: Consistent operation between macOS development and Windows production

### Architectural Constraints
- **Single-User Design**: Optimized for dedicated research station (not networked/multi-user)
- **Fixed System**: Intentionally non-extensible for focused scientific workflow
- **Memory Constraints**: Operates within 32 GB system RAM with careful allocation
- **Non-Linear Navigation**: Users can return to previous phases for experimental iteration

## Hardware Integration

### Production Hardware (Windows)
- **CPU**: Intel 13700K (P-cores for real-time tasks, E-cores for background processing)
- **GPU**: NVIDIA RTX 4070 (12 GB VRAM, CUDA acceleration, DirectX 12 control)
- **Memory**: 32 GB DDR4/DDR5 with careful allocation budgeting
- **Storage**: Samsung 990 PRO NVMe (6.9 GB/s sustained writes)
- **Camera**: PCO Panda 4.2 (16-bit, 2048×2048, USB 3.1)
- **Display**: Hardware-controlled mouse monitor with exclusive fullscreen access

### Development Support (macOS)
- **Metal Backend**: GPU acceleration for development workflow
- **Mock Hardware**: Software simulation for algorithm development
- **Cross-Platform Validation**: Ensure consistent behavior across platforms

## Performance Specifications

### Real-Time Requirements
- **Stimulus Display**: Exactly 60 FPS (16.667ms ±10μs) via DirectX 12 hardware control
- **Camera Capture**: 30 FPS (33.333ms ±100μs) with zero dropped frames
- **Data Streaming**: 125 MB/sec sustained writes during acquisition
- **Memory Efficiency**: Operation within 32 GB constraint using HDF5 streaming

### Analysis Performance
- **Frame Correlation**: Process 1800 frames (1 minute @ 30 FPS) in <60 seconds
- **GPU Acceleration**: CUDA-optimized algorithms for ISI temporal processing
- **Interactive Visualization**: 60 FPS retinotopic map rendering
- **Memory Streaming**: Handle datasets larger than available RAM

## Error Handling and Recovery

### Comprehensive Error Management
- **Hardware Monitoring**: Real-time validation of all hardware components
- **Graceful Degradation**: Continue operation with reduced capability when possible
- **Data Preservation**: Never lose scientific data during failures
- **Transparent Logging**: Complete audit trail for troubleshooting
- **State Recovery**: Automatic restoration from interruptions

### Development Mode
- **Hardware Bypass**: Complete mock hardware for development without production equipment
- **Algorithm Testing**: Full analysis pipeline with simulated data
- **Cross-Platform Development**: Consistent development experience on macOS and Windows

## Integration Points

This system overview ties together the complete design documentation:

- **[WORKFLOW_STATES.md](./WORKFLOW_STATES.md)**: Detailed state machine implementation
- **[STREAMING_ARCHITECTURE.md](./STREAMING_ARCHITECTURE.md)**: Display and data flow architecture
- **[HARDWARE_INTERFACES.md](./HARDWARE_INTERFACES.md)**: Hardware control specifications
- **[STIMULUS_GENERATION.md](./STIMULUS_GENERATION.md)**: Visual stimulus creation and HDF5 management
- **[ACQUISITION_PIPELINE.md](./ACQUISITION_PIPELINE.md)**: Real-time data capture implementation
- **[ANALYSIS_PIPELINE.md](./ANALYSIS_PIPELINE.md)**: ISI processing and retinotopic mapping
- **[DATA_MANAGEMENT.md](./DATA_MANAGEMENT.md)**: Storage organization and data integrity
- **[PERFORMANCE_SPECIFICATIONS.md](./PERFORMANCE_SPECIFICATIONS.md)**: Hardware requirements and benchmarks
- **[ERROR_RECOVERY.md](./ERROR_RECOVERY.md)**: Comprehensive error handling strategies
- **[APPLICATION_STARTUP.md](./APPLICATION_STARTUP.md)**: System initialization and validation

The ISI Macroscope Control System represents a modern, high-performance platform for neuroscience research, combining proven scientific methods with contemporary software engineering practices and cutting-edge hardware acceleration.