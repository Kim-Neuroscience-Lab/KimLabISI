# ISI Macroscope Control System - Architecture

This document defines the complete codebase architecture based on our established architectural principles (SOLID, DRY, SoC, SSoT, YAGNI) and design decisions.

## Overview

- **Architecture Pattern**: Clean Architecture with Thin Client (ADR-0002, ADR-0003)
- **Communication**: IPC/WebSocket between Electron frontend and Python backend (ADR-0005)
- **Cross-Platform**: macOS development, Windows production with hardware abstraction (ADR-0008, ADR-0010)
- **Technology Stack**: Modern 2025 validated external packages (ADR-0004)

## Directory Structure

```
KimLabISI/
|-- .github/                           # GitHub Actions CI/CD workflows
    |-- workflows/
       |-- test-frontend.yml          # Frontend testing (Vitest, ESLint, TypeScript)
       |-- test-backend.yml           # Backend testing (pytest, ruff, mypy)
       |-- integration-tests.yml      # Cross-platform integration testing

|-- frontend/                          # Thin client display layer (zero business logic)
   |-- electron/                      # Electron main process
      |-- main.ts                    # Electron app startup, spawn Python backend
      |-- preload.ts                 # Secure IPC bridge (message passing only)
      |-- ipc-relay.ts              # Relay messages between renderer and Python
      |-- window-manager.ts          # Window display management only

   |-- src/                           # React renderer process (display only)
      |-- main.tsx                   # React app entry, connect to backend
      |-- App.tsx                    # Display root, backend determines active page

      |-- components/                # Pure display components (no logic)
         |-- common/                # Shared display elements
            |-- Button.tsx         # Button that sends command to backend
            |-- Modal.tsx          # Modal displaying backend messages
            |-- ProgressBar.tsx    # Progress display from backend updates
            |-- StatusIndicator.tsx # Status display from backend state

         |-- displays/              # Backend state display components
            |-- SetupDisplay.tsx      # Display spatial config from backend
            |-- GenerationDisplay.tsx # Display generation progress from backend
            |-- AcquisitionDisplay.tsx # Display acquisition status from backend
            |-- AnalysisDisplay.tsx   # Display analysis results from backend

         |-- visualization/         # Data visualization (display only)
             |-- SpatialViewer3D.tsx # Display 3D config from backend
             |-- RetinotopicViewer.tsx # Display maps from backend
             |-- PreviewMonitor.tsx # Display downsampled camera preview
             |-- StatusMonitor.tsx # Display hardware status from backend
             |-- ProgressTracker.tsx # Display multi-stage progress

      |-- pages/                     # Page containers (backend determines active page)
         |-- StartupPage.tsx        # Display startup status from backend
         |-- SetupPage.tsx          # Display setup UI, forward clicks to backend
         |-- GenerationPage.tsx     # Display generation progress from backend
         |-- AcquisitionPage.tsx    # Display acquisition monitors from backend
         |-- AnalysisPage.tsx       # Display analysis results from backend
         |-- ErrorPage.tsx          # Display errors from backend
         |-- DegradedPage.tsx       # Display degraded status from backend

      |-- store/                     # Zustand UI state only (no business state)
         |-- index.ts               # Store configuration
         |-- ui-store.ts            # UI-only state (modal open/closed, panel visibility)
         |-- backend-mirror.ts      # Read-only mirror of backend state for display

      |-- services/                  # Frontend communication services
         |-- ipc-client.ts          # Send commands to backend, receive state updates
         |-- formatter.ts           # Format backend data for display only
         |-- renderer.ts            # Render backend state updates to UI

      |-- types/                     # TypeScript types for display
         |-- backend-state.ts       # Types for backend state (read-only)
         |-- ipc-messages.ts        # IPC message types
         |-- ui.ts                  # UI-only types (modal state, view options)

      |-- styles/                    # Tailwind CSS styling
          |-- globals.css            # Global styles and Tailwind configuration
          |-- components.css         # Component-specific styling utilities

   |-- tests/                         # Frontend testing
      |-- components/                # Display component tests
      |-- ipc/                       # IPC communication tests
      |-- rendering/                 # UI rendering tests
      |-- integration/               # Frontend-backend communication tests
      |-- e2e/                       # End-to-end workflow tests

   |-- package.json                   # Node.js dependencies and scripts
   |-- vite.config.ts                 # Vite build configuration
   |-- tailwind.config.js             # Tailwind CSS configuration
   |-- tsconfig.json                  # TypeScript configuration
   |-- .eslintrc.json                 # ESLint configuration
   |-- electron-builder.yml           # Electron packaging configuration

|-- backend/                           # Python backend (all business logic and control)
   |-- src/                           # Python source code (Clean Architecture)
      |-- isi_control/               # Main application package
         |-- __init__.py            # Package initialization
         |-- main.py                # Application entry point and server startup

      |-- domain/                    # Domain layer (pure business logic, zero dependencies)
         |-- __init__.py

         |-- entities/              # Core business entities
            |-- __init__.py
            |-- workflow_state.py  # 12-state workflow state machine entity
            |-- parameters.py      # Generation/acquisition parameter entities
            |-- hardware.py        # Hardware capability and status entities
            |-- dataset.py         # Scientific dataset entities with metadata

         |-- value_objects/         # Immutable value objects
            |-- __init__.py
            |-- spatial_config.py  # 3D spatial configuration values
            |-- stimulus_params.py # Visual stimulus parameter values
            |-- acquisition_params.py # Data acquisition parameter values

         |-- services/              # Domain services (complex business logic)
            |-- __init__.py
            |-- parameter_validator.py # Scientific parameter validation logic
            |-- dataset_matcher.py # Dataset reuse parameter matching logic
            |-- workflow_orchestrator.py # Workflow state transition rules
            |-- stimulus_calculator.py # Spherical corrections and pattern math
            |-- isi_analyzer.py     # ISI computation and phase map algorithms

         |-- repositories/          # Abstract repository interfaces
             |-- __init__.py
             |-- hardware_repository.py # Hardware control abstractions
             |-- data_repository.py # Data storage abstractions
             |-- config_repository.py # Configuration management abstractions

      |-- application/               # Application layer (use cases, orchestration)
         |-- __init__.py

         |-- algorithms/            # Scientific algorithms
            |-- __init__.py
            |-- pattern_generators.py # Bar and checkerboard patterns
            |-- spherical_transform.py # Monitor curvature corrections
            |-- fourier_analysis.py # FFT for ISI processing
            |-- phase_unwrapping.py # Phase map computation
            |-- sign_map.py        # Visual field sign mapping

         |-- use_cases/             # Application use cases
            |-- __init__.py
            |-- system_startup.py  # System initialization and validation
            |-- hardware_calibration.py # Calibrate camera, display, timing
            |-- spatial_setup.py   # 3D spatial configuration workflow
            |-- stimulus_generation.py # Generate visual patterns with GPU
            |-- data_acquisition.py # Real-time capture with dual streaming
            |-- analysis_pipeline.py # ISI analysis and map generation
            |-- error_recovery.py  # Error handling and recovery
            |-- session_management.py # Session state and persistence

         |-- handlers/              # IPC/WebSocket message handlers
            |-- __init__.py
            |-- command_handler.py  # Process all commands from frontend
            |-- state_broadcaster.py # Broadcast state changes to frontend
            |-- query_handler.py    # Handle frontend queries for data

         |-- services/              # Application services
             |-- __init__.py
             |-- communication_service.py # IPC/WebSocket server management
             |-- state_persistence.py # Workflow state persistence and recovery
             |-- monitoring_service.py # System monitoring and health checks

      |-- infrastructure/            # Infrastructure layer (external concerns)
          |-- __init__.py

          |-- hardware/              # Hardware abstraction implementations
             |-- __init__.py
             |-- abstract/          # Hardware interface definitions
                |-- __init__.py
                |-- camera_interface.py # Abstract camera control interface
                |-- gpu_interface.py # Abstract GPU acceleration interface
                |-- timing_interface.py # Abstract timing synchronization interface
                |-- display_interface.py # Abstract display control interface

             |-- windows/           # Windows production hardware implementations
                |-- __init__.py
                |-- pco_camera.py  # PCO Panda 4.2 SDK integration (pybind11)
                |-- directx_gpu.py # DirectX 12 compute acceleration
                |-- cuda_processing.py # CUDA acceleration for analysis
                |-- windows_timing.py # Windows high-resolution timing
                |-- display_control.py # DirectX display synchronization
                |-- trigger_system.py # Hardware trigger synchronization

             |-- macos/             # macOS development mock implementations
                |-- __init__.py
                |-- mock_camera.py # Comprehensive camera simulation
                |-- metal_gpu.py   # Metal compute acceleration
                |-- mock_processing.py # CPU-based analysis simulation
                |-- macos_timing.py # macOS timing simulation
                |-- mock_display.py # Display simulation for development
                |-- mock_trigger.py # Simulated trigger events

             |-- factory.py         # Platform detection and hardware factory

             |-- streaming/         # Real-time data streaming
                |-- __init__.py
                |-- ring_buffer.py  # Lock-free ring buffers
                |-- frame_manager.py # Frame timestamping and ordering
                |-- preview_generator.py # Downsample for monitoring
                |-- stream_synchronizer.py # Multi-stream coordination

          |-- storage/               # Data storage implementations
             |-- __init__.py
             |-- hdf5_repository.py # HDF5 scientific data storage (h5py)
             |-- config_repository.py # Configuration file management
             |-- dataset_discovery.py # Dataset reuse parameter matching
             |-- session_repository.py # Session state persistence
             |-- cache_manager.py    # Stimulus cache and buffer management

          |-- communication/         # IPC/WebSocket communication
             |-- __init__.py
             |-- ipc_server.py      # Receive commands, send state updates
             |-- websocket_server.py # WebSocket fallback for development
             |-- message_dispatcher.py  # Route commands to handlers

          |-- monitoring/            # System monitoring and logging
              |-- __init__.py
              |-- system_monitor.py  # Resource usage and health monitoring
              |-- error_tracker.py   # Error logging and analytics
              |-- performance_logger.py # Performance metrics collection
              |-- timing_validator.py # Microsecond timing validation

   |-- tests/                         # Backend testing
      |-- unit/                      # Unit tests by layer
         |-- domain/                # Domain layer tests (no external dependencies)
         |-- application/           # Application layer tests (mocked infrastructure)
         |-- infrastructure/        # Infrastructure tests (real external dependencies)

      |-- integration/               # Integration tests
         |-- hardware/              # Hardware abstraction integration tests
         |-- storage/               # Data storage integration tests
         |-- communication/         # IPC/WebSocket integration tests
         |-- streaming/             # Real-time streaming tests
         |-- workflow/              # Complete workflow tests

      |-- fixtures/                  # Test data and fixtures
         |-- sample_datasets.h5     # Sample HDF5 scientific datasets
         |-- test_configurations/   # Test configuration files
         |-- mock_responses/        # Mock hardware response data
         |-- test_patterns/         # Test stimulus patterns
         |-- expected_results/      # Expected analysis outputs
         |-- timing_profiles/       # Performance baseline data

      |-- conftest.py                # Pytest configuration and shared fixtures

   |-- pyproject.toml                 # Poetry configuration and dependencies
   |-- poetry.lock                    # Locked dependency versions
   |-- pytest.ini                     # Pytest configuration
   |-- mypy.ini                       # MyPy type checking configuration
   |-- .ruff.toml                     # Ruff linting configuration

|-- shared/                            # Shared message definitions only
   |-- protocols/                     # IPC/WebSocket message formats
      |-- typescript/                # TypeScript message types
         |-- commands.ts            # Commands from frontend to backend
         |-- state-updates.ts       # State updates from backend to frontend
         |-- notifications.ts       # Notifications from backend to frontend

      |-- python/                    # Python message schemas (Pydantic V2)
          |-- __init__.py
          |-- commands.py            # Command schemas from frontend
          |-- state_updates.py       # State update schemas to frontend
          |-- notifications.py       # Notification schemas to frontend

   |-- schemas/                       # Backend validation schemas (not used by frontend)
       |-- generation_parameters.json # Backend validates generation parameters
       |-- acquisition_parameters.json # Backend validates acquisition parameters
       |-- spatial_configuration.json # Backend validates spatial configuration

|-- config/                            # Configuration management
   |-- environments/                  # Environment-specific configurations
      |-- development.yml            # macOS development configuration
      |-- production.yml             # Windows production configuration
      |-- testing.yml                # Testing environment configuration

   |-- hardware/                      # Hardware capability definitions
      |-- pco_panda_42.yml           # PCO Panda 4.2 camera specifications
      |-- rtx_4070.yml               # RTX 4070 GPU capabilities
      |-- mock_hardware.yml          # Mock hardware simulation parameters
      |-- display_specs.yml          # Monitor specifications and geometry

   |-- calibration/                   # Calibration data storage
      |-- camera_calibration.yml     # Camera dark frames and corrections
      |-- display_calibration.yml    # Display gamma and geometry
      |-- timing_calibration.yml     # System latency measurements

   |-- defaults/                      # Default parameter sets
       |-- spatial_setup.yml          # Default 3D spatial configuration
       |-- stimulus_generation.yml    # Default stimulus generation parameters
       |-- acquisition_protocol.yml   # Default acquisition protocol parameters
       |-- analysis_settings.yml      # Default ISI analysis parameters

|-- data/                              # Local data storage
   |-- datasets/                      # HDF5 scientific datasets
      |-- stimuli/                   # Generated visual stimulus datasets
      |-- acquisitions/              # Captured experimental data
      |-- analysis/                  # Processed retinotopic maps and results

   |-- cache/                         # Temporary and cache files
      |-- stimulus_cache/            # GPU-optimized stimulus cache
      |-- preview_cache/             # Downsampled preview frames
      |-- processing_cache/          # Temporary analysis files
      |-- buffer_pool/               # Pre-allocated memory buffers

   |-- logs/                          # Application and system logs
      |-- application.log            # General application logging
      |-- hardware.log               # Hardware interaction logging
      |-- errors.log                 # Error and exception logging
      |-- performance.log            # Performance metrics logging

   |-- sessions/                      # Workflow session state persistence
       |-- current_session.json      # Active session state
       |-- session_history/          # Historical session backups

|-- scripts/                           # Development and deployment scripts
   |-- setup/                         # Environment setup scripts
      |-- setup_development.sh       # macOS development environment setup
      |-- setup_production.sh        # Windows production environment setup
      |-- install_dependencies.sh    # Cross-platform dependency installation
      |-- verify_hardware.sh         # Hardware availability checking

   |-- build/                         # Build and packaging scripts
      |-- build_frontend.sh          # Frontend build and packaging
      |-- build_backend.sh           # Backend build and packaging
      |-- package_application.sh     # Complete application packaging
      |-- sign_application.sh        # Code signing for distribution

   |-- testing/                       # Testing automation scripts
      |-- run_all_tests.sh           # Comprehensive testing suite
      |-- cross_platform_tests.sh    # Cross-platform validation
      |-- performance_tests.sh       # Performance benchmarking
      |-- timing_validation.sh       # Microsecond timing verification
      |-- mock_hardware_tests.sh     # Validate mock implementations

   |-- calibration/                   # Calibration scripts
       |-- calibrate_camera.sh        # Camera calibration workflow
       |-- calibrate_display.sh       # Display calibration workflow
       |-- validate_timing.sh         # Timing validation workflow

|-- docs/                              # Documentation (existing)
   |-- design/                        # Design documentation
   |-- decisions/                     # Architecture Decision Records
   |-- references/                    # Scientific reference materials
   |-- ARCHITECTURE.md                # This document

|-- .gitignore                         # Git ignore patterns
|-- .gitattributes                     # Git file handling configuration
|-- README.md                          # Project overview and quick start
|-- LICENSE                            # Software license

```

## Key Architectural Patterns

### Thin Client Architecture Implementation

- **Backend Controls Everything**: All business logic, validation, and state management in Python backend
- **Frontend Display Only**: Electron frontend purely displays backend state and forwards user input
- **Domain Layer (Backend)**: Pure business logic with zero external dependencies
- **Application Layer (Backend)**: Use cases orchestrating domain logic and handling IPC messages
- **Infrastructure Layer (Backend)**: External concerns (hardware, storage, communication)
- **Thin Client (Frontend)**: Zero business logic, only UI rendering and IPC communication

### Cross-Platform Strategy

- **Hardware Abstraction**: Platform-specific implementations behind common interfaces
- **Configuration Management**: Environment-specific settings and capabilities
- **Mock Hardware**: Comprehensive simulation for macOS development
- **Build System**: Cross-platform build and packaging automation

### Communication Architecture

- **Unidirectional Commands**: Frontend sends user commands to backend
- **Unidirectional State**: Backend sends state updates to frontend for display
- **No Frontend Logic**: Frontend never validates, calculates, or decides - only forwards
- **Backend Authority**: Backend validates all commands and controls all state transitions
- **IPC/WebSocket Transport**: Message passing only, no business logic in transport layer

### Data Management Strategy

- **HDF5 Storage**: Scientific data with hierarchical metadata organization
- **Dataset Reuse**: Parameter-based exact matching for stimulus sharing
- **State Persistence**: Complete workflow state survives application restarts
- **Local Storage**: No external networking or cloud dependencies

### Testing Strategy

- **Unit Testing**: Comprehensive coverage for all layers with appropriate isolation
- **Integration Testing**: Cross-platform hardware abstraction validation
- **Mock Hardware**: Complete production hardware simulation for development
- **Continuous Integration**: GitHub Actions for cross-platform validation

### Separation of Responsibilities

#### Frontend (Electron/React) - Display Only

- **Renders UI**: Display components based on backend state
- **Forwards Input**: Send user clicks/input to backend via IPC
- **Shows Status**: Display hardware status, progress, errors from backend
- **Zero Logic**: No validation, no calculations, no state management
- **Pure Presentation**: Only formatting for display (e.g., number to percentage)

#### Backend (Python) - All Business Logic

- **Manages State**: Complete workflow state machine and transitions
- **Validates Input**: All parameter validation and constraint checking
- **Controls Hardware**: Exclusive hardware access and control
- **Processes Data**: All scientific calculations and data processing
- **Makes Decisions**: All business rules and workflow logic
- **Persists State**: Session management and data storage

#### What NEVER Happens

- Frontend never validates parameters (backend validates)
- Frontend never decides state transitions (backend controls workflow)
- Frontend never accesses hardware (backend exclusive control)
- Frontend never processes scientific data (backend only)
- Frontend never stores business state (backend persistence)

This architecture ensures scientific reliability, cross-platform compatibility, and long-term maintainability while adhering to established architectural principles and leveraging validated external packages.

## Complete Design Coverage

This architecture comprehensively addresses all aspects from our design documentation:

### Scientific Computing

- **Stimulus Generation**: Pattern generators, spherical transforms, GPU optimization (`algorithms/` and `hardware/`)
- **ISI Analysis**: Fourier analysis, phase unwrapping, sign mapping (`algorithms/` and domain services)
- **Real-Time Processing**: Ring buffers, frame management, streaming coordination (`streaming/`)

### Hardware Control

- **Camera Integration**: PCO SDK bindings, calibration, mock simulation (`hardware/windows/`, `hardware/macos/`)
- **GPU Acceleration**: DirectX 12, CUDA, Metal implementations (`hardware/` platform-specific)
- **Timing Synchronization**: Microsecond precision, trigger systems (`hardware/timing/`, `calibration/`)

### Data Management

- **HDF5 Storage**: Scientific datasets with metadata (`storage/hdf5_repository.py`)
- **Dataset Reuse**: Parameter matching, discovery (`storage/dataset_discovery.py`)
- **Session Persistence**: State management, recovery (`application/session_management.py`)

### User Interface

- **Thin Client**: Zero business logic, display-only frontend (`frontend/` - pure presentation)
- **3D Visualization**: Spatial configuration display (`visualization/SpatialViewer3D.tsx`)
- **Real-Time Monitoring**: Downsampled previews (`visualization/PreviewMonitor.tsx`)

### Cross-Platform Support

- **Development/Production**: macOS development, Windows production environments
- **Hardware Abstraction**: Common interfaces, platform-specific implementations
- **Mock Hardware**: Complete simulation for development without production hardware

### Error Handling & Recovery

- **Graceful Degradation**: Reduced functionality modes (`use_cases/error_recovery.py`)
- **State Recovery**: Session restoration, data preservation (`application/state_persistence.py`)
- **Hardware Failover**: Mock hardware fallback (`hardware/factory.py`)

### Testing & Validation

- **Multi-Layer Testing**: Unit, integration, end-to-end coverage
- **Performance Validation**: Timing verification, benchmarking (`scripts/testing/`)
- **Cross-Platform**: Hardware abstraction validation across platforms

### Configuration & Calibration

- **Environment Management**: Development/production/testing configurations
- **Hardware Calibration**: Camera, display, timing calibration systems
- **Parameter Management**: Default sets, validation schemas

Every major component from the design phase is represented with appropriate separation of concerns and adherence to the thin client architecture pattern.
