# ISI Macroscope Backend Migration Guide

## Overview

This guide explains the migration from the original ISI Macroscope backend (using the service locator anti-pattern) to the refactored backend (using KISS principles with constructor injection).

**Migration Status:** Phase 1-8 Complete - Production Ready

## What Changed

### Architecture Changes

#### Before (Old System)
- **Service Locator Anti-Pattern:** Global singleton registry for all services
- **Hidden Dependencies:** Services accessed via `service_locator.get('service_name')`
- **Decorator-based Handlers:** Magic command registration via `@command_handler`
- **Implicit Initialization:** Services initialized when first accessed
- **Scattered Configuration:** Settings spread across multiple files and globals

#### After (New System)
- **Constructor Injection:** All dependencies passed explicitly via `__init__`
- **Explicit Dependencies:** Clear, visible dependency graph
- **KISS Handler Mapping:** Simple dict with lambda handlers
- **Explicit Composition Root:** All services wired in `main.py::create_services()`
- **Centralized Configuration:** Single `AppConfig` dataclass from JSON

### Key Benefits

1. **Testability:** Easy to mock dependencies and unit test
2. **Maintainability:** Clear dependency graph, no hidden coupling
3. **Debuggability:** Explicit flow, no magic lookups
4. **Type Safety:** Better IDE support and static analysis
5. **Simplicity:** KISS pattern - no decorators, no magic

## Migration Path

### Step 1: Verify Your Environment

```bash
cd /Users/Adam/KimLabISI/apps/backend

# Check Python version (must be 3.10+)
.venv/bin/python --version

# Verify dependencies installed
.venv/bin/python -c "import numpy, scipy, h5py, cv2, zmq; print('Dependencies OK')"
```

### Step 2: Backup Current Configuration

```bash
# Create backup of current settings
.venv/bin/python src/migrate_config.py --backup --label "pre_refactor"

# Verify backup created
.venv/bin/python src/migrate_config.py --list-backups
```

### Step 3: Run Comprehensive Tests

```bash
# Run ALL tests (Phase 1-8, integration, quality)
.venv/bin/python src/test_all.py

# Expected output:
# - All phase tests passing
# - Integration tests passing
# - Code quality checks passing
# - OVERALL RESULT: ALL TESTS PASSED
```

### Step 4: Validate Configuration

```bash
# Validate current configuration file
.venv/bin/python src/migrate_config.py --validate

# Expected output:
# - JSON parsing: OK
# - Structure check: OK
# - AppConfig loading: OK
# - Configuration is VALID
```

### Step 5: Test New System

```bash
# Test import of new main module
.venv/bin/python -c "from src.main import main; print('Import successful')"

# Run integration test specifically
.venv/bin/python src/test_integration.py

# Run code quality checks
.venv/bin/python src/test_quality.py
```

### Step 6: Deploy New System

The new system is now the default entry point via `pyproject.toml`:

```toml
[tool.poetry.scripts]
isi-macroscope = "src.main:main"              # NEW (default)
isi-macroscope-old = "isi_control.main:main"  # OLD (fallback)
```

**Production Deployment:**

1. Stop any running instances of the old backend
2. Clear any IPC ports (5555, 5557, 5558, 5559)
3. Start new backend:
   ```bash
   cd /Users/Adam/KimLabISI/apps/backend
   .venv/bin/python src/main.py
   ```

4. Or via Poetry script (once rebuilt):
   ```bash
   poetry install  # Rebuild with new entry point
   isi-macroscope  # Use new backend
   ```

## Configuration Changes

### JSON Structure (Unchanged)

The JSON configuration format **has not changed**. The same `isi_parameters.json` file is used by both old and new systems.

**Example Configuration:**
```json
{
  "current": {
    "camera": {
      "selected_camera": "FLIRCamera",
      "camera_width_px": 1920,
      "camera_height_px": 1200,
      "camera_fps": 30
    },
    "monitor": {
      "selected_display": "Display1",
      "monitor_width_px": 1920,
      "monitor_height_px": 1080
    }
  }
}
```

### Loading Configuration

**Old Way:**
```python
# Scattered across multiple files
param_manager = ParameterManager()
camera_config = param_manager.get_parameter_group('camera')
```

**New Way:**
```python
# Single source of truth
config = AppConfig.from_file('config/isi_parameters.json')
print(config.camera.selected_camera)
print(config.camera.camera_width_px)
```

## API Changes

### Command Handlers

The command interface **has not changed** - all IPC commands work identically.

**Available Commands (unchanged):**
- Camera: `detect_cameras`, `start_camera_acquisition`, `stop_camera_acquisition`
- Acquisition: `start_acquisition`, `stop_acquisition`, `get_acquisition_status`
- Playback: `list_sessions`, `load_session`, `get_playback_frame`
- Analysis: `start_analysis`, `stop_analysis`, `get_analysis_status`
- Parameters: `get_all_parameters`, `update_parameter_group`
- System: `ping`, `health_check`, `get_system_status`

### IPC Communication (Unchanged)

All IPC channels remain the same:
- **Health Port:** 5555 (stdin/stdout control)
- **Sync Port:** 5558 (ZMQ PUB for broadcasts)
- **Stimulus Metadata:** 5557 (ZMQ PUB for frame metadata)
- **Camera Metadata:** 5559 (ZMQ PUB for camera metadata)
- **Shared Memory:** `stimulus_stream` (frame data)

## Code Structure Comparison

### Old Structure (service_locator)

```
src/isi_control/
├── service_locator.py          # Global singleton registry
├── main.py                     # Scattered initialization
├── camera_manager.py           # Uses service_locator.get()
├── acquisition_manager.py      # Uses service_locator.get()
└── ...
```

### New Structure (KISS)

```
src/
├── config.py                   # Configuration dataclasses
├── main.py                     # Composition root
├── ipc/
│   ├── channels.py             # IPC service
│   └── shared_memory.py        # Shared memory service
├── camera/
│   └── manager.py              # Camera manager (constructor injection)
├── stimulus/
│   └── generator.py            # Stimulus generator (constructor injection)
├── acquisition/
│   ├── manager.py              # Acquisition manager
│   ├── state.py                # State coordinator
│   ├── sync_tracker.py         # Timestamp tracker
│   ├── camera_stimulus.py      # Camera-triggered stimulus
│   ├── recorder.py             # Session recorder
│   └── modes.py                # Playback controller
├── analysis/
│   ├── manager.py              # Analysis manager
│   ├── pipeline.py             # Analysis pipeline
│   └── renderer.py             # Analysis renderer
└── test_*.py                   # Comprehensive test suite
```

## Dependency Injection Examples

### Old Way (Service Locator)

```python
class AcquisitionManager:
    def __init__(self):
        # Hidden dependencies via service locator
        self.camera = service_locator.get('camera')
        self.ipc = service_locator.get('ipc')
        self.stimulus = service_locator.get('stimulus')
```

### New Way (Constructor Injection)

```python
class AcquisitionManager:
    def __init__(
        self,
        ipc: MultiChannelIPC,
        shared_memory: SharedMemoryService,
        stimulus_generator: StimulusGenerator,
        synchronization_tracker: TimestampSynchronizationTracker,
        state_coordinator: AcquisitionStateCoordinator,
        camera_triggered_stimulus: CameraTriggeredStimulusController,
        data_recorder: Optional[SessionRecorder],
        param_manager: ParameterManager,
    ):
        # Explicit dependencies - clear and testable
        self.ipc = ipc
        self.shared_memory = shared_memory
        self.stimulus_generator = stimulus_generator
        # ...
```

**Benefits:**
- ✅ Clear what dependencies are required
- ✅ Easy to mock for testing
- ✅ No hidden global state
- ✅ Type hints enable IDE support
- ✅ Dependency graph is explicit

## Testing

### Running Tests

```bash
# Run ALL tests (recommended)
.venv/bin/python src/test_all.py

# Run specific test suites
.venv/bin/python src/test_phase1.py  # Infrastructure
.venv/bin/python src/test_phase2.py  # Camera
.venv/bin/python src/test_phase3.py  # Stimulus
.venv/bin/python src/test_phase4.py  # Acquisition
.venv/bin/python src/test_phase5.py  # Analysis
.venv/bin/python src/test_phase6.py  # Main Application
.venv/bin/python src/test_phase7.py  # Supporting Services

# Integration and quality
.venv/bin/python src/test_integration.py
.venv/bin/python src/test_quality.py
```

### Expected Results

All tests should pass with output like:

```
================================================================================
OVERALL RESULT: ALL TESTS PASSED
================================================================================

The refactored ISI Macroscope backend is ready for deployment!
```

## Troubleshooting

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'src'`

**Solution:**
```bash
# Ensure you're running from backend directory
cd /Users/Adam/KimLabISI/apps/backend

# Use absolute path to python
/Users/Adam/KimLabISI/apps/backend/.venv/bin/python src/main.py
```

### Configuration Not Found

**Problem:** `Configuration file not found`

**Solution:**
```bash
# Verify config exists
ls -la config/isi_parameters.json

# Create default if missing
.venv/bin/python -c "from src.config import AppConfig; print('Config loads')"
```

### Port Already in Use

**Problem:** `Address already in use (port 5555)`

**Solution:**
```bash
# Find process using port
lsof -i :5555

# Kill old backend process
pkill -f "isi_control.main"
pkill -f "src.main"

# Or kill specific PID
kill <PID>
```

### Service Locator Errors

**Problem:** `service_locator.get() failed` in old code

**Solution:** The new system doesn't use service_locator. If you see this error, you're running the old backend. Switch to new:

```bash
# Run new backend explicitly
.venv/bin/python src/main.py

# NOT the old one
# .venv/bin/python -m isi_control.main  # DON'T USE
```

## Rollback Procedure

If you need to rollback to the old system:

### Step 1: Stop New Backend

```bash
# Kill any running instances
pkill -f "src.main"
```

### Step 2: Restore Old Configuration (if needed)

```bash
# List backups
.venv/bin/python src/migrate_config.py --list-backups

# Restore specific backup
.venv/bin/python src/migrate_config.py --restore --backup-file config/backups/isi_parameters_pre_refactor_*.json
```

### Step 3: Start Old Backend

```bash
# Use old entry point
.venv/bin/python -m isi_control.main

# Or via poetry script
isi-macroscope-old
```

## Verification Checklist

After migration, verify:

- [ ] All tests pass (`python src/test_all.py`)
- [ ] Configuration validates (`python src/migrate_config.py --validate`)
- [ ] New backend starts without errors (`python src/main.py`)
- [ ] IPC channels connect (check logs for "Backend ready")
- [ ] Camera detection works (send `detect_cameras` command)
- [ ] Stimulus generation works (send `start_acquisition` command)
- [ ] Frontend connects successfully
- [ ] No service_locator imports in new code (`python src/test_quality.py`)

## Performance Comparison

### Old System
- Startup time: ~2-3 seconds
- Service lookup overhead: ~0.1ms per access
- Hidden initialization costs

### New System
- Startup time: ~2-3 seconds (similar)
- No lookup overhead: Direct references
- Explicit initialization: Clear startup sequence

**Result:** Similar or better performance with much better code quality.

## Future Deprecation

### Timeline

1. **Phase 8 (Current):** Both systems coexist
   - New system is default
   - Old system available as fallback

2. **After 30 days:** Evaluate stability
   - If no issues: Mark old system as deprecated
   - Add deprecation warnings to old entry point

3. **After 90 days:** Remove old system
   - Delete `isi_control/` directory
   - Remove `isi-macroscope-old` entry point
   - Archive old code to git history

### Deprecation Checklist

Before removing old system:

- [ ] New system running in production for 30+ days
- [ ] Zero rollbacks needed
- [ ] All team members trained on new system
- [ ] Documentation updated
- [ ] No known issues with new system
- [ ] Backup of old system created

## Getting Help

### Resources

- **Test Suite:** `src/test_*.py` - Comprehensive examples
- **Main Entry Point:** `src/main.py` - See composition root
- **Configuration:** `src/config.py` - All config dataclasses
- **Migration Utility:** `src/migrate_config.py` - Config tools

### Common Questions

**Q: Can I run both systems simultaneously?**
A: No - they use the same IPC ports. Choose one.

**Q: Will my old configurations work?**
A: Yes - the JSON format is unchanged.

**Q: Do I need to retrain users?**
A: No - the frontend interface is identical.

**Q: What if I find bugs in the new system?**
A: Rollback to old system and report issues. The old system remains available.

**Q: How do I know migration was successful?**
A: Run `python src/test_all.py` - it should show "ALL TESTS PASSED".

## Summary

The migration from service_locator to KISS constructor injection provides:

1. **Better Code Quality:** No anti-patterns, explicit dependencies
2. **Easier Testing:** Simple to mock and unit test
3. **Better Debugging:** No magic, clear flow
4. **Improved Maintainability:** Clear dependency graph
5. **Type Safety:** Better IDE support

The migration is **backward compatible** - same JSON config, same IPC commands, same behavior. The only change is internal architecture.

**Ready to migrate? Start with Step 1 above!**
