# Backend Refactor Plan (KISS Approach)

**Last Updated:** 2025-10-10
**Status:** ✅ Ready for Implementation
**Effort:** 40-60 hours
**Approach:** Keep It Simple, Stupid

---

## Goal

Eliminate the service locator anti-pattern using the **simplest possible approach**: explicit dependency wiring in main.py with no magic, no decorators, no auto-discovery.

---

## Core Principle

**Keep It Simple, Stupid (KISS)**

- ✅ All wiring visible in main.py
- ✅ Explicit handler mapping (no decorators)
- ✅ Constructor injection only
- ✅ No magic, no hidden complexity
- ✅ Everything obvious and traceable

---

## Target Structure

### New System (Build Alongside Current)

```
apps/backend/src/
├── acquisition/              # Acquisition orchestration
│   ├── manager.py           # Main acquisition orchestrator
│   ├── state.py             # State machine
│   ├── modes.py             # Preview/Record/Playback controllers
│   ├── camera_stimulus.py   # Camera-triggered stimulus
│   ├── recorder.py          # Data recording
│   └── sync_tracker.py      # Timestamp synchronization
│
├── analysis/                 # Analysis pipeline
│   ├── pipeline.py          # Fourier analysis (ISI algorithms)
│   ├── manager.py           # Analysis orchestration
│   ├── renderer.py          # Visualization rendering
│   └── formatter.py         # Data formatting for charts
│
├── camera/                   # Camera hardware
│   ├── manager.py           # Camera control
│   └── utils.py             # Hardware detection
│
├── stimulus/                 # Stimulus generation
│   ├── generator.py         # OpenGL stimulus rendering
│   └── transform.py         # Spherical coordinate transforms
│
├── ipc/                      # Inter-process communication
│   ├── channels.py          # ZeroMQ channels
│   └── shared_memory.py     # Zero-copy frame streaming
│
├── config.py                 # Configuration management
├── startup.py               # Startup coordination
├── health.py                # System health monitoring
├── display.py               # Display detection
└── main.py                  # Application entry point (composition root)
```

### Current System (Keep Until Migration Complete)

```
apps/backend/src/isi_control/  ← DO NOT MODIFY (keep running)
└── ... (all 31 existing files)
```

---

## The KISS Pattern

### Main.py - The Composition Root

```python
import asyncio
import json
import sys
from pathlib import Path

from config import AppConfig
from ipc.channels import MultiChannelIPC
from ipc.shared_memory import SharedMemoryService
from camera.manager import CameraManager
from stimulus.generator import StimulusGenerator
from acquisition.manager import AcquisitionManager
from acquisition.state import StateCoordinator
from acquisition.sync_tracker import SyncTracker
from analysis.manager import AnalysisManager
from health import SystemHealthMonitor
from startup import StartupCoordinator

async def main():
    # 1. Load configuration
    config = AppConfig.from_file("config/isi_parameters.json")

    # 2. Create infrastructure services
    ipc = MultiChannelIPC(config.ipc)
    shared_memory = SharedMemoryService(config.shared_memory)

    # 3. Create hardware services (explicit dependencies)
    camera = CameraManager(
        config=config.camera,
        ipc=ipc,
        shared_memory=shared_memory
    )

    stimulus = StimulusGenerator(config.stimulus)

    # 4. Create domain services (explicit dependencies)
    state = StateCoordinator()
    sync_tracker = SyncTracker()

    acquisition = AcquisitionManager(
        config=config.acquisition,
        ipc=ipc,
        camera=camera,
        stimulus=stimulus,
        state=state,
        sync_tracker=sync_tracker
    )

    analysis = AnalysisManager(
        config=config.analysis,
        ipc=ipc
    )

    health = SystemHealthMonitor(ipc=ipc)
    startup = StartupCoordinator()

    # 5. Define command handlers (explicit mapping, no decorators!)
    handlers = {
        # Acquisition commands
        "start_acquisition": lambda cmd: acquisition.start_acquisition(
            config.acquisition.to_dict()
        ),
        "stop_acquisition": lambda cmd: acquisition.stop_acquisition(),
        "get_acquisition_status": lambda cmd: {"status": acquisition.get_status()},
        "set_acquisition_mode": lambda cmd: acquisition.set_mode(
            mode=cmd.get("mode", "preview"),
            direction=cmd.get("direction"),
            frame_index=cmd.get("frame_index")
        ),
        "display_black_screen": lambda cmd: acquisition.display_black_screen(),

        # Camera commands
        "detect_cameras": lambda cmd: {"success": True, "cameras": camera.detect_cameras()},
        "get_camera_capabilities": lambda cmd: camera.get_capabilities(cmd.get("camera_id")),
        "start_camera": lambda cmd: camera.start(cmd.get("camera_id")),
        "stop_camera": lambda cmd: camera.stop(),
        "get_camera_frame": lambda cmd: camera.get_latest_frame_info(),

        # Analysis commands
        "start_analysis": lambda cmd: analysis.start_analysis(
            session_path=cmd.get("session_path"),
            params=config.analysis.to_dict()
        ),
        "stop_analysis": lambda cmd: analysis.stop_analysis(),
        "get_analysis_status": lambda cmd: analysis.get_status(),
        "get_analysis_results": lambda cmd: analysis.get_results(cmd.get("session_path")),
        "get_analysis_layer": lambda cmd: analysis.get_layer(
            session_path=cmd.get("session_path"),
            layer_name=cmd.get("layer_name")
        ),

        # Stimulus commands
        "preview_stimulus": lambda cmd: stimulus.preview(
            params=cmd.get("params", {})
        ),
        "stop_stimulus": lambda cmd: stimulus.stop(),

        # Health commands
        "get_health_status": lambda cmd: health.get_status(),
        "ping": lambda cmd: {"success": True, "pong": True},
    }

    # 6. Start IPC event loop
    print("ISI Macroscope Backend Ready")
    print(f"Registered {len(handlers)} command handlers")

    try:
        while True:
            # Receive command via stdin (JSON)
            line = await asyncio.get_event_loop().run_in_executor(
                None, sys.stdin.readline
            )
            if not line:
                break

            try:
                command = json.loads(line.strip())
                command_type = command.get("type", "")

                # Look up handler
                handler = handlers.get(command_type)
                if handler:
                    response = handler(command)
                else:
                    response = {
                        "success": False,
                        "error": f"Unknown command: {command_type}"
                    }

                # Send response via stdout
                print(json.dumps(response), flush=True)

            except json.JSONDecodeError as e:
                error_response = {
                    "success": False,
                    "error": f"Invalid JSON: {str(e)}"
                }
                print(json.dumps(error_response), flush=True)

            except Exception as e:
                error_response = {
                    "success": False,
                    "error": f"Handler error: {str(e)}"
                }
                print(json.dumps(error_response), flush=True)

    except KeyboardInterrupt:
        print("\nShutting down...")

    finally:
        # 7. Cleanup
        await camera.shutdown()
        await ipc.shutdown()
        print("Backend shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
```

**Key Points:**
- ✅ ~200 lines of explicit, readable code
- ✅ All dependencies visible in one place
- ✅ All handlers defined inline (lambdas capture dependencies)
- ✅ No decorators, no magic, no hidden behavior
- ✅ Easy to understand, easy to debug
- ✅ Trivial to test (pass mock managers)

---

## Implementation Strategy

### Phase 1: Infrastructure (6-8 hours)

**Create:**
- `ipc/channels.py` - MultiChannelIPC (copy from isi_control, simplify)
- `ipc/shared_memory.py` - SharedMemoryService (copy from isi_control)
- `config.py` - Configuration dataclasses (copy from isi_control)

**Pattern:**
```python
# config.py
from dataclasses import dataclass
from pathlib import Path
import json

@dataclass
class CameraConfig:
    camera_id: int
    fps: float
    resolution: tuple[int, int]

    def to_dict(self) -> dict:
        return {
            "camera_id": self.camera_id,
            "fps": self.fps,
            "resolution": self.resolution
        }

@dataclass
class AppConfig:
    camera: CameraConfig
    acquisition: AcquisitionConfig
    analysis: AnalysisConfig
    # ...

    @staticmethod
    def from_file(path: str) -> "AppConfig":
        with open(path) as f:
            data = json.load(f)
        return AppConfig(
            camera=CameraConfig(**data["camera"]),
            # ... parse all sections
        )
```

---

### Phase 2: Camera System (4-6 hours)

**Create:**
- `camera/manager.py` - Camera hardware control (copy from isi_control, inject dependencies)
- `camera/utils.py` - Hardware detection utilities (copy from isi_control)

**Pattern (Constructor Injection):**
```python
# camera/manager.py
class CameraManager:
    def __init__(
        self,
        config: CameraConfig,
        ipc: MultiChannelIPC,
        shared_memory: SharedMemoryService
    ):
        # All dependencies passed explicitly
        self.config = config
        self.ipc = ipc
        self.shared_memory = shared_memory
        self.camera = None
        self._capture_thread = None

    def start(self, camera_id: int) -> dict:
        """Start camera capture."""
        # Implementation uses self.config, self.ipc, etc.
        return {"success": True, "camera_id": camera_id}

    def detect_cameras(self) -> list:
        """Detect available cameras."""
        # Implementation
        return []

    async def shutdown(self):
        """Clean shutdown."""
        if self._capture_thread:
            self._capture_thread.stop()
```

---

### Phase 3: Stimulus System (4-6 hours)

**Create:**
- `stimulus/generator.py` - OpenGL stimulus rendering (copy from isi_control)
- `stimulus/transform.py` - Spherical transforms (copy from isi_control)

**Pattern:**
```python
# stimulus/generator.py
class StimulusGenerator:
    def __init__(self, config: StimulusConfig):
        self.config = config
        self.window = None

    def preview(self, params: dict) -> dict:
        """Generate preview stimulus."""
        # Implementation
        return {"success": True}

    def generate_frame(self, angle: float) -> np.ndarray:
        """Generate single stimulus frame."""
        # Pure function - takes angle, returns frame
        pass
```

---

### Phase 4: Acquisition System (8-12 hours)

**Create:**
- `acquisition/manager.py` - Main orchestrator (copy from isi_control, inject deps)
- `acquisition/state.py` - State machine (copy from isi_control)
- `acquisition/modes.py` - Mode controllers (copy from isi_control)
- `acquisition/camera_stimulus.py` - Camera-triggered stimulus (copy from isi_control)
- `acquisition/recorder.py` - Data recording (copy from isi_control)
- `acquisition/sync_tracker.py` - Timestamp tracking (copy from isi_control)

**Pattern (All Dependencies Explicit):**
```python
# acquisition/manager.py
class AcquisitionManager:
    def __init__(
        self,
        config: AcquisitionConfig,
        ipc: MultiChannelIPC,
        camera: CameraManager,
        stimulus: StimulusGenerator,
        state: StateCoordinator,
        sync_tracker: SyncTracker
    ):
        # Everything passed explicitly - no service_locator!
        self.config = config
        self.ipc = ipc
        self.camera = camera
        self.stimulus = stimulus
        self.state = state
        self.sync_tracker = sync_tracker

    def start_acquisition(self, params: dict) -> dict:
        """Start acquisition with given parameters."""
        # Use injected dependencies
        self.state.transition_to("acquiring")
        self.camera.start_capture()
        return {"success": True}

    def stop_acquisition(self) -> dict:
        """Stop acquisition."""
        self.state.transition_to("idle")
        self.camera.stop_capture()
        return {"success": True}
```

---

### Phase 5: Analysis System (4-6 hours)

**Create:**
- `analysis/pipeline.py` - Fourier analysis (copy from isi_analysis.py)
- `analysis/manager.py` - Analysis orchestrator (copy from isi_control)
- `analysis/renderer.py` - Visualization (copy from isi_control)
- `analysis/formatter.py` - Data formatting (copy from isi_control)

**Pattern:**
```python
# analysis/manager.py
class AnalysisManager:
    def __init__(self, config: AnalysisConfig, ipc: MultiChannelIPC):
        self.config = config
        self.ipc = ipc
        self.pipeline = AnalysisPipeline()  # No dependencies

    def start_analysis(self, session_path: str, params: dict) -> dict:
        """Start analysis on recorded session."""
        results = self.pipeline.analyze(session_path, params)
        return {"success": True, "results": results}
```

---

### Phase 6: Main Application (6-8 hours)

**Create:** `main.py` - The composition root (see complete example above)

**Key Implementation Details:**
1. All services created with explicit constructor calls
2. All handlers defined as lambdas that capture dependencies via closure
3. Simple dict-based handler lookup (no registry class needed)
4. Explicit error handling for each command
5. Clean shutdown on exit

---

### Phase 7: Supporting Services (4-6 hours)

**Create:**
- `health.py` - System health monitoring (copy from isi_control, inject IPC)
- `startup.py` - Startup coordination (copy from isi_control)
- `display.py` - Display detection (copy from isi_control)

**Pattern:**
```python
# health.py
class SystemHealthMonitor:
    def __init__(self, ipc: MultiChannelIPC):
        self.ipc = ipc

    def get_status(self) -> dict:
        return {
            "success": True,
            "status": "healthy",
            "uptime": self._get_uptime()
        }
```

---

### Phase 8: Testing & Migration (6-10 hours)

#### 8.1 Unit Tests (3-4 hours)
```python
# tests/test_acquisition.py
import pytest
from unittest.mock import Mock
from acquisition.manager import AcquisitionManager

def test_start_acquisition():
    # Arrange: Create mocks
    mock_config = Mock()
    mock_ipc = Mock()
    mock_camera = Mock()
    mock_stimulus = Mock()
    mock_state = Mock()
    mock_sync = Mock()

    # Act: Create manager with mocked dependencies
    manager = AcquisitionManager(
        config=mock_config,
        ipc=mock_ipc,
        camera=mock_camera,
        stimulus=mock_stimulus,
        state=mock_state,
        sync_tracker=mock_sync
    )

    result = manager.start_acquisition({})

    # Assert
    assert result["success"] == True
    mock_camera.start_capture.assert_called_once()
```

#### 8.2 Integration Tests (2-3 hours)
- Test full command flow through handlers
- Test actual IPC communication
- Test with real config files

#### 8.3 Migration (1-2 hours)
- Update `pyproject.toml` entry point
- Run both systems in parallel for testing
- Switch over when confident
- Delete `isi_control/` directory

---

## Effort Summary

| Phase | Hours | Status |
|-------|-------|--------|
| Phase 1: Infrastructure | 6-8 | ⏭️ TODO |
| Phase 2: Camera | 4-6 | ⏭️ TODO |
| Phase 3: Stimulus | 4-6 | ⏭️ TODO |
| Phase 4: Acquisition | 8-12 | ⏭️ TODO |
| Phase 5: Analysis | 4-6 | ⏭️ TODO |
| Phase 6: Main | 6-8 | ⏭️ TODO |
| Phase 7: Supporting | 4-6 | ⏭️ TODO |
| Phase 8: Testing & Migration | 6-10 | ⏭️ TODO |
| **TOTAL** | **42-62** | **Not Started** |

---

## Key Decisions

### ✅ What We're Doing
- **Explicit wiring in main.py** - All dependencies visible
- **Lambda handlers** - Capture dependencies via closure
- **Constructor injection only** - No property assignment
- **No decorators** - No @ipc_handler magic
- **No auto-discovery** - Explicit handler mapping
- **Simple dict lookup** - No registry class needed
- **Strangler fig migration** - Build new alongside old

### ❌ What We're NOT Doing
- No decorators (@ipc_handler removed)
- No auto-discovery/scanning
- No partial application
- No registry class
- No service locator
- No global state
- No DI containers/frameworks
- No over-engineering

---

## Success Criteria

✅ **Zero global state** - All dependencies passed explicitly
✅ **Zero hidden behavior** - Everything visible in main.py
✅ **Trivial to test** - Just pass mock objects
✅ **Easy to understand** - Single file shows entire system
✅ **No magic** - No decorators, no scanning, no surprises
✅ **No breaking changes** - Old system runs until migration complete

---

## Why This Approach Works

### Simplicity
- **One file to understand the system**: main.py shows all wiring
- **No hidden dependencies**: Everything explicit
- **No magic**: Lambda handlers are just functions with captured variables
- **Easy debugging**: Clear stack traces, no decorator indirection

### Testability
```python
# Testing is trivial - just pass mocks!
def test_handler():
    mock_acquisition = Mock()
    handler = lambda cmd: mock_acquisition.start_acquisition(cmd)
    result = handler({"type": "start"})
    assert mock_acquisition.start_acquisition.called
```

### Maintainability
- **Add new handler**: Just add one line to handlers dict
- **Change dependencies**: Modify constructor call in main.py
- **Find handler implementation**: Search for command name in main.py
- **No refactoring needed**: Pattern scales to 100+ handlers

### Performance
- **Zero overhead**: Direct function calls, no decorator wrapping
- **No lookup cost**: Simple dict access
- **No late binding**: All dependencies resolved at startup
- **Optimal for real-time**: No hidden allocations in critical path

---

## Next Steps

**Ready to start Phase 1!**

1. Create `apps/backend/src/ipc/channels.py`
2. Create `apps/backend/src/ipc/shared_memory.py`
3. Create `apps/backend/src/config.py`
4. Verify they work with simple test script

Then proceed to Phase 2 (Camera system).
