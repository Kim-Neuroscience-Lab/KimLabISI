# Design Documentation Index

## Overview

This directory contains the architectural design and system specifications for the ISI Macroscope Control System. The system controls a neuroscience imaging setup that maps how the mouse visual cortex responds to visual stimuli through intrinsic signal imaging.

## Workflow Overview

The system follows this workflow:
**Application Startup → Setup → Stimulus Generation → Acquisition → Analysis**

Parameters are configured proximally to their usage for immediate feedback and quick iteration.

## Core Design Documents

### System Architecture

#### [SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md)

**Purpose**: High-level system architecture and goals
**Topics**:

- Project purpose and scientific goals
- Workflow overview
- Architecture components (Electron + Python backend)
- Component relationships
- Technology decisions

#### [APPLICATION_STARTUP.md](./APPLICATION_STARTUP.md)

**Purpose**: System initialization and startup procedures
**Topics**:

- Hardware detection and driver validation
- Performance baselines and calibration
- Application state recovery
- Development mode bypass functionality
- Cross-platform startup considerations

#### [FUNCTIONAL_REQUIREMENTS.md](./FUNCTIONAL_REQUIREMENTS.md)

**Purpose**: Complete functional specifications
**Topics**:

- Scientific workflows and use cases
- Performance requirements
- User capabilities per workflow stage
- Scientific accuracy requirements
- Key operational features

### Workflow Management

#### [WORKFLOW_STATES.md](./WORKFLOW_STATES.md)

**Purpose**: State machine and workflow control
**Topics**:

- Setup, Generation, Acquisition, Analysis states
- State transitions and guards
- Operations allowed in each state
- State persistence across sessions

#### [STATE_PERSISTENCE.md](./STATE_PERSISTENCE.md)

**Purpose**: Session continuity and recovery
**Topics**:

- Session state management
- Recovery from interruptions
- Parameter memory between sessions
- Partial work preservation
- Resume capabilities per stage

### Workflow Stages

#### [SETUP_PHASE.md](./SETUP_PHASE.md)

**Purpose**: Experiment setup and configuration
**Topics**:

- Spatial configuration (monitor-to-mouse positioning)
- Hardware verification procedures
- Protocol parameter definition
- Calibration workflows
- Configuration validation

#### [STIMULUS_GENERATION.md](./STIMULUS_GENERATION.md)

**Purpose**: Visual stimulus creation and management
**Topics**:

- Pattern generation algorithms (bars, gratings)
- Direction optimization strategies
- Angle pre-calculation methods
- Preview capabilities
- Stimulus library management
- Memory optimization

#### [ACQUISITION_PIPELINE.md](./ACQUISITION_PIPELINE.md)

**Purpose**: Real-time data acquisition flow
**Topics**:

- Frame-perfect display control (60 FPS)
- Camera capture pipeline (30 FPS)
- Timestamp synchronization strategy
- Live monitoring streams
- Protocol execution
- Data streaming to disk

#### [ANALYSIS_PIPELINE.md](./ANALYSIS_PIPELINE.md)

**Purpose**: Post-acquisition data processing
**Topics**:

- Frame correlation algorithms
- Retinotopy calculations
- Statistical aggregation
- Map generation
- Re-analysis capabilities
- Visualization approaches

### Technical Architecture

#### [HARDWARE_INTERFACES.md](./HARDWARE_INTERFACES.md)

**Purpose**: Hardware control and interfaces
**Topics**:

- Display control architecture
- Camera interfaces and triggers
- Filter management
- Hardware timing requirements
- Calibration procedures

#### [STREAMING_ARCHITECTURE.md](./STREAMING_ARCHITECTURE.md)

**Purpose**: Display control and monitoring streams
**Topics**:

- Hardware-controlled mouse display (60 FPS)
- Camera-to-disk capture path
- Electron frontend monitoring (downsampled previews)
- IPC/WebSocket protocols
- Binary streaming format

#### [DATA_MANAGEMENT.md](./DATA_MANAGEMENT.md)

**Purpose**: Data storage and organization
**Topics**:

- Stimulus datasets format and storage
- Acquisition session data organization
- Analysis results management
- File naming conventions
- Directory structure
- Import/export capabilities

### System Qualities

#### [PERFORMANCE_SPECIFICATIONS.md](./PERFORMANCE_SPECIFICATIONS.md)

**Purpose**: Performance requirements and constraints
**Topics**:

- Frame timing requirements
- Memory budgets
- Disk I/O requirements
- Processing latency limits
- Resource allocation strategies

#### [ERROR_RECOVERY.md](./ERROR_RECOVERY.md)

**Purpose**: Error handling and recovery strategies
**Topics**:

- Hardware failure handling
- Interrupted acquisition recovery
- Data corruption detection
- State restoration procedures
- Graceful degradation paths

## Key Architectural Principles

### 1. Separation of Critical and Non-Critical Paths

- Scientific data (stimulus + camera) **never** passes through Electron frontend
- Frontend receives only downsampled previews for monitoring
- Hardware-controlled paths for time-critical operations

### 2. Event-Based Synchronization

- Hardware timestamps captured at source
- Post-hoc correlation during analysis phase
- No real-time correlation requirements

### 3. Data Integrity

- Never lose scientific data
- Complete timestamp preservation
- State persistence across sessions
- Recovery from interruptions

### 4. Fixed System Design

- Not extensible by design
- Single-user, non-networked
- Optimized for specific scientific workflow

## Reading Order for New Contributors

1. **[SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md)** - Understand the system purpose
2. **[FUNCTIONAL_REQUIREMENTS.md](./FUNCTIONAL_REQUIREMENTS.md)** - Learn what the system does
3. **[APPLICATION_STARTUP.md](./APPLICATION_STARTUP.md)** - Understand system initialization
4. **[WORKFLOW_STATES.md](./WORKFLOW_STATES.md)** - Understand the operational flow
5. **[STREAMING_ARCHITECTURE.md](./STREAMING_ARCHITECTURE.md)** - Learn the technical architecture
6. Stage-specific documents as needed

## Document Status

### Completed Documents

- ✅ [APPLICATION_STARTUP.md](./APPLICATION_STARTUP.md) - Complete system initialization with dev-mode bypass functionality
- ✅ [FUNCTIONAL_REQUIREMENTS.md](./FUNCTIONAL_REQUIREMENTS.md) - Complete functional specifications with GPU acceleration
- ✅ [STREAMING_ARCHITECTURE.md](./STREAMING_ARCHITECTURE.md) - Complete display and streaming architecture with RTX 4070/Windows specifics
- ✅ [ACQUISITION_PIPELINE.md](./ACQUISITION_PIPELINE.md) - Complete real-time data capture flow with PCO Panda 4.2 integration
- ✅ [ANALYSIS_PIPELINE.md](./ANALYSIS_PIPELINE.md) - Complete ISI analysis methods with CUDA acceleration and scientific references
- ✅ [STIMULUS_GENERATION.md](./STIMULUS_GENERATION.md) - Complete with ISI methods, HDF5 storage, dataset reuse, and parameter separation
- ✅ [PERFORMANCE_SPECIFICATIONS.md](./PERFORMANCE_SPECIFICATIONS.md) - Complete with production hardware specifications (13700K, RTX 4070, PCO Panda 4.2)
- ✅ [DATA_MANAGEMENT.md](./DATA_MANAGEMENT.md) - Complete with HDF5 optimization and GPU considerations
- ✅ [ERROR_RECOVERY.md](./ERROR_RECOVERY.md) - Complete error handling with graceful degradation and transparency
- ✅ [SETUP_PHASE.md](./SETUP_PHASE.md) - Complete 3D spatial configuration interface with Three.js visualization
- ✅ [HARDWARE_INTERFACES.md](./HARDWARE_INTERFACES.md) - Complete hardware control specifications with DirectX 12, PCO SDK, and timing synchronization
- ✅ [WORKFLOW_STATES.md](./WORKFLOW_STATES.md) - Complete state machine with 12 states, transitions, error handling, and session persistence
- ✅ [SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md) - Complete high-level architecture with modern 2025 technology stack
- ✅ [STATE_PERSISTENCE.md](./STATE_PERSISTENCE.md) - Complete session continuity and recovery mechanisms

## Design Principles

- **DRY (Don't Repeat Yourself)**: Each concept documented once
- **SoC (Separation of Concerns)**: Each document owns its domain
- **Cross-References**: Documents reference related topics
- **Workflow-Centric**: Organization follows the scientific workflow
