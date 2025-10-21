# Architecture Overview

**Last Updated**: 2025-10-14

> High-level system design, patterns, and architectural principles.

---

## Architecture Documents

- [Backend Architecture](backend.md) - Python backend structure
- [Frontend Architecture](frontend.md) - Electron/React UI structure
- [Data Flow](data-flow.md) - IPC and shared memory
- [System Diagram](system-diagram.md) - Visual overview

---

## Design Philosophy

### Core Principles

1. **Separation of Concerns**: Backend handles data/computation, frontend handles presentation
2. **Single Source of Truth**: Parameter manager is authoritative source for all config
3. **Real-time First**: Optimized for 30-60 fps camera + stimulus synchronization
4. **Scientific Accuracy**: Algorithms match published literature (Kalatsky 2003, Zhuang 2017)
5. **Maintainability**: Clear module boundaries, minimal dependencies

### Key Patterns

- **Dependency Injection**: Services registered in service locator
- **Event-Driven**: IPC pub/sub for loose coupling
- **Shared Memory**: Zero-copy frame transfer for performance
- **Living Documents**: Components track their own status via changelog sections

---

## System Components

### Backend (Python 3.11)

- **Acquisition Manager**: Orchestrates camera-triggered data collection
- **Camera Manager**: OpenCV-based camera control
- **Stimulus Generator**: ModernGL-based visual stimulus
- **Analysis Pipeline**: Fourier analysis + VFS calculation
- **Parameter Manager**: Configuration management (Single Source of Truth)
- **IPC System**: ZeroMQ multi-channel communication

### Frontend (Electron + React + TypeScript)

- **Main Process**: IPC bridge, shared memory access, window management
- **Renderer Process**: React UI, Chart.js visualization, canvas rendering
- **Viewports**: Acquisition, Analysis, Stimulus Generation, Stimulus Presentation

---

## Data Flow

```
Camera → Shared Memory → Frontend Canvas
   ↓
Acquisition Manager → HDF5 Storage
   ↓
Analysis Pipeline → Results → Frontend Charts
```

See [Data Flow](data-flow.md) for detailed diagrams.

---

## Thread Model

### Backend Threads

- **Main Thread**: IPC message handlers (stdin/stdout CONTROL channel)
- **SYNC Publisher**: Pub/sub for broadcasts (histogram, progress, etc.)
- **Acquisition Thread**: Phase orchestration (baseline, stimulus, etc.)
- **Camera Thread**: Frame capture loop (OpenCV)
- **Stimulus Thread**: Playback loop (publishing to shared memory)

### Frontend Threads

- **Main Process**: Electron IPC, shared memory reads
- **Renderer Process**: React UI, canvas rendering

**Thread Safety**: All shared state protected by locks. IPC for cross-thread communication.

---

## Technology Stack

**Backend**:
- Python 3.11
- NumPy, OpenCV, h5py
- ModernGL (stimulus rendering)
- ZeroMQ (IPC)
- matplotlib (figure generation)

**Frontend**:
- Electron 27
- React 18 + TypeScript
- Chart.js (real-time plots)
- HTML5 Canvas (frame rendering)

**Data**:
- HDF5 (session storage)
- JSON (metadata, events)
- Shared memory (frame transfer)

---

## Related Documentation

- [ADR-001: Backend Modular Architecture](../decisions/001-backend-modular-architecture.md)
- [ADR-002: Unified Stimulus Controller](../decisions/002-unified-stimulus-controller.md)
- [Component: Acquisition System](../components/acquisition-system.md)

---

**Architecture Version**: 2.0 (After Backend Refactor)
**Last Major Change**: 2025-10-10 (Backend modularization)
