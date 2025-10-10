# ISI Macroscope Documentation

**Last Updated:** 2025-10-10

This documentation accurately reflects the **current state** of the codebase, including its organizational issues.

## ⚠️ Current State Warning

This codebase is **functional but organizationally messy**:
- Backend has 31 Python files in a single flat directory (no subdirectories)
- Some duplicate systems exist (e.g., async + sync stimulus paths)
- Code needs refactoring for better organization

This documentation describes **what actually exists**, not idealized architecture.

## Quick Reference

### Actual Project Structure

```
KimLabISI/
├── apps/
│   ├── backend/                    # Python backend (Poetry)
│   │   ├── config/
│   │   │   └── isi_parameters.json # Single config file
│   │   ├── data/sessions/          # Recorded session data (HDF5)
│   │   ├── logs/                   # Application logs
│   │   └── src/isi_control/        # All 31 Python files (flat structure)
│   │
│   └── desktop/                    # Electron + React frontend
│       ├── src/
│       │   ├── components/         # React components (13 files)
│       │   ├── electron/           # Electron main/preload
│       │   ├── types/              # TypeScript types
│       │   ├── context/            # React context
│       │   └── utils/              # Frontend utilities
│       └── package.json
│
├── docs/
│   └── archive/                    # Historical documentation
│
└── README.md                       # Project readme
```

### Backend Files (31 files, all in `apps/backend/src/isi_control/`)

**Core Infrastructure:**
- `main.py` - Backend entry point
- `service_locator.py` - Dependency injection registry
- `config.py` - Configuration dataclasses
- `schemas.py` - IPC message schemas
- `startup_coordinator.py` - Startup sequencing
- `health_monitor.py` - System health monitoring
- `logging_utils.py` - Centralized logging

**Managers (Main Business Logic):**
- `acquisition_manager.py` - Acquisition orchestration
- `analysis_manager.py` - Analysis pipeline controller
- `camera_manager.py` - Camera hardware control
- `stimulus_manager.py` - Stimulus generation (async preview)
- `parameter_manager.py` - Configuration management
- `display_manager.py` - Display detection
- `data_recorder.py` - Session data persistence

**Acquisition System:**
- `acquisition_state.py` - State coordinator
- `acquisition_mode_controllers.py` - Preview/Record/Playback controllers
- `camera_triggered_stimulus.py` - Synchronous stimulus (record mode)
- `timestamp_synchronization_tracker.py` - Timing QA tracking
- `stimulus_controller.py` - Legacy stimulus controller (may be unused)

**Analysis System:**
- `isi_analysis.py` - Fourier analysis algorithms (Kalatsky & Stryker 2003)
- `analysis_image_renderer.py` - Backend PNG rendering
- `acquisition_data_formatter.py` - Chart.js data formatting
- `spherical_transform.py` - Coordinate transformations

**IPC Handlers:**
- `multi_channel_ipc.py` - IPC infrastructure (ZeroMQ)
- `ipc_utils.py` - IPC decorator and utilities
- `acquisition_ipc_handlers.py` - Acquisition commands
- `analysis_ipc_handlers.py` - Analysis commands
- `playback_ipc_handlers.py` - Playback commands

**Hardware/Utilities:**
- `shared_memory_stream.py` - Zero-copy frame streaming
- `hardware_utils.py` - Hardware detection utilities

### Frontend Components (13 React components)

**Core UI:**
- `App.tsx` - Main application
- `Header.tsx` - Top navigation
- `ControlPanel.tsx` - Parameter controls
- `MainViewport.tsx` - Central display area
- `Console.tsx` - Status console
- `ErrorBoundary.tsx` - Error handling

**Shared UI:**
- `FormField.tsx` - Reusable form inputs
- `ParameterSection.tsx` - Collapsible parameter sections

**Viewports (Display Components):**
- `StartupViewport.tsx` - Startup screen
- `AcquisitionViewport.tsx` - Real-time acquisition display
- `AnalysisViewport.tsx` - Analysis results display
- `CameraViewport.tsx` - DEBUG ONLY: WebRTC camera testing
- `StimulusGenerationViewport.tsx` - Stimulus preview
- `StimulusPresentationViewport.tsx` - Secondary display window

## Key Architectural Concepts

### 1. Backend/Frontend Separation

**Backend (Python) Handles:**
- ALL business logic
- Hardware control (camera, display)
- Data processing and analysis
- Scientific algorithms
- State management

**Frontend (React) Handles:**
- ONLY presentation
- User input collection
- Pre-formatted data display
- IPC communication

**Rule:** No business logic in frontend. Frontend displays what backend tells it to display.

### 2. IPC Communication

Three separate ZeroMQ channels:
- **Control** (port 5556): Command/response (REQ/REP)
- **Sync** (port 5558): Status updates (PUB/SUB)
- **Health** (port 5560): System health (PUB/SUB)

Commands use `@ipc_handler` decorator pattern:
```python
@ipc_handler("command_name")
def handle_command(command: Dict[str, Any]) -> Dict[str, Any]:
    # Implementation
    return {"success": True, "result": data}
```

### 3. Shared Memory Streaming

Three isolated buffers for zero-copy frame transfer:
- `/tmp/isi_macroscope_stimulus_shm` (100MB) - Stimulus frames
- `/tmp/isi_macroscope_camera_shm` (100MB) - Camera frames
- `/tmp/isi_macroscope_analysis_shm` (50MB) - Analysis layers

### 4. Service Registry Pattern

Global singleton registry (`service_locator.py`) provides dependency injection:
```python
from .service_locator import get_services
services = get_services()
camera_manager = services.camera_manager
```

Ensures single instance of each manager.

### 5. Acquisition Modes

Three mutually exclusive modes:
- **Preview**: Static frame preview for parameter tuning (async stimulus)
- **Record**: Camera-triggered acquisition with precise timing (sync stimulus)
- **Playback**: Session data replay

## Backend Refactor Plan

**Status:** ✅ Ready for Implementation (Critical fixes applied 2025-10-10)

The backend is being refactored from global service locator pattern to clean dependency injection:

### Target Architecture
- ✅ Explicit constructor dependencies
- ✅ Lazy provider pattern for services
- ✅ Type-safe dependency container
- ✅ Auto-registered IPC handlers
- ✅ Zero global state

### Implementation Plan

See `BACKEND_REFACTOR_PLAN.md` for complete details.

**Effort:** 56-77 hours total
- Pre-work (critical fixes): ✅ DONE (16-20 hours)
- Implementation phases: ⏭️ TODO (40-57 hours)

**Critical Fixes Applied (2025-10-10):**
1. ✅ Fixed @ipc_handler decorator for auto-registration
2. ✅ Removed circular dependency from ISIContainer
3. ✅ Added all missing services to container
4. ✅ Implemented cycle detection in DependentProvider
5. ✅ Revised timeline to realistic estimates

See `docs/archive/20251010_CRITICAL_FIXES_APPLIED.md` for fix details.

## Known Issues & Technical Debt

### Backend Organization (Being Addressed by Refactor)
- All 31 files in single flat directory → Will be organized into domain/infrastructure
- Service locator anti-pattern → Replacing with dependency injection
- Global state → Eliminating with Provider pattern

### Code Quality
- Need comprehensive testing suite (planned in refactor Phase 8)

See `docs/archive/20251009_BACKEND_CLEANUP_AUDIT.md` for historical analysis.

## Scientific Foundation

**Intrinsic Signal Imaging** measures hemodynamic responses in visual cortex during periodic visual stimulation.

**Key Papers:**
- **Kalatsky & Stryker, Neuron 2003** - Fourier-based retinotopic mapping
- **Zhuang et al., Cell 2017** - Visual field sign calculation

**Analysis Pipeline:**
1. Periodic stimulus presentation (4 directions: LR, RL, TB, BT)
2. Camera captures hemodynamic responses
3. Fourier analysis extracts phase at stimulus frequency
4. Phase maps indicate retinotopic position
5. Visual field sign identifies mirror/non-mirror representations
6. Automated visual area segmentation

## Getting Started

### Prerequisites
- Python 3.10+ with Poetry
- Node.js 18+
- OpenCV-compatible camera
- Secondary display for stimulus presentation

### Running the Application

**Backend:**
```bash
cd apps/backend
poetry install
poetry run python -m isi_control.main
```

**Frontend:**
```bash
cd apps/desktop
npm install
npm run dev
```

### Basic Workflow
1. Start backend and frontend
2. Configure camera and display in control panel
3. Set stimulus parameters
4. Preview stimulus on secondary display
5. Start acquisition (camera-triggered recording)
6. Run analysis on recorded session
7. View retinotopic maps in analysis viewport

## Documentation Index

### Current Documentation
- **Main README** (this file) - System overview and current state
- **Backend Refactor Plan** (`BACKEND_REFACTOR_PLAN.md`) - Clean architecture implementation guide

### Source Code Reference
For current implementation details:
- **Acquisition flow:** `acquisition_manager.py`, `acquisition_mode_controllers.py`
- **Camera control:** `camera_manager.py`
- **Analysis algorithms:** `isi_analysis.py`
- **IPC handlers:** `*_ipc_handlers.py` files
- **Frontend UI:** `apps/desktop/src/components/`

### Archive
- `docs/archive/` - Historical audits and analysis (may be outdated)
- `docs/archive/20251010_CRITICAL_FIXES_APPLIED.md` - Refactor pre-work fixes
- `docs/archive/20251009_BACKEND_CLEANUP_AUDIT.md` - Initial architecture analysis

## Contributing

When updating this documentation:
1. Verify against actual code (don't document imaginary structure)
2. Update this file's "Last Updated" date
3. Document technical debt honestly (don't hide problems)
4. Include code examples from actual codebase
5. Cross-check file paths exist before documenting them

## License

Copyright (c) 2025 KimLab. All rights reserved.
