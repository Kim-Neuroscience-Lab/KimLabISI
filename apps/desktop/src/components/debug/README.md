# Debug Components

This folder contains components used for **testing and development only**. These components are **NOT** part of the production acquisition pipeline.

## Components

### CameraViewport.tsx

**Purpose**: Manual camera testing using browser WebRTC API (`navigator.mediaDevices.getUserMedia`)

**Status**: NOT used in production. This is a separate camera access path for debugging only.

**Why it's isolated**:

- Creates confusion with the production camera system (backend OpenCV)
- Uses browser APIs instead of backend hardware management
- Violates the backend-as-SSoT architecture for hardware

**Production camera system**: Use `AcquisitionViewport.tsx` which interfaces with the Python backend camera manager through shared memory.

## Architecture Note

The production system follows strict **backend-as-SSoT** (Single Source of Truth) principles:

- All hardware detection, selection, and management happens in the backend
- Frontend receives hardware state via IPC and shared memory
- Frontend can request parameter changes, but backend validates and executes them
- This ensures scientific reproducibility and centralized hardware logic
