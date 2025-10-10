# Phase 7 Integration Guide

## Supporting Services Integration with main.py

This guide shows how to integrate the Phase 7 supporting services (health monitoring, startup coordination, and display detection) into the main.py composition root.

## Overview

Phase 7 provides three clean, service-locator-free modules:

1. **health.py** - System health monitoring with IPC reporting
2. **startup.py** - Startup validation and hardware detection
3. **display.py** - Cross-platform display detection utilities

All modules use **constructor injection only** and have **ZERO service_locator dependencies**.

## Integration Pattern

### 1. Imports

Add these imports to main.py:

```python
from health import HealthMonitor
from startup import StartupCoordinator, validate_system_requirements, check_hardware_availability
from display import detect_displays, get_primary_display, validate_display_config
```

### 2. Early Startup Validation

Before creating services, validate system requirements:

```python
def main():
    """Main entry point with startup validation."""

    # Phase 1: Validate system requirements
    print("Validating system requirements...")
    success, errors = validate_system_requirements()

    if not success:
        print("System validation failed:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    print("✓ System requirements validated")

    # Phase 2: Check hardware availability
    hardware = check_hardware_availability()
    print(f"Hardware detected: {hardware['cameras']} camera(s), "
          f"{hardware['displays']} display(s), GPU={hardware['gpu']}")

    # Phase 3: Load configuration
    config = AppConfig.from_file("config/isi_parameters.json")

    # Phase 4: Create services
    services = create_services(config)

    # Phase 5: Start health monitoring
    services["health_monitor"].start_monitoring()

    # ... rest of application
```

### 3. Service Creation

Add health monitor to the composition root:

```python
def create_services(config: AppConfig) -> dict:
    """Create all services with explicit dependency injection.

    Args:
        config: Application configuration

    Returns:
        Dictionary of service instances
    """

    # Layer 1: Infrastructure (config, IPC, shared memory)
    ipc = build_multi_channel_ipc(
        transport=config.ipc.transport,
        health_port=config.ipc.health_port,
        sync_port=config.ipc.sync_port,
    )

    shared_memory = build_shared_memory_stream(
        stream_name=config.shared_memory.stream_name,
        buffer_size_mb=config.shared_memory.buffer_size_mb,
        metadata_port=config.shared_memory.metadata_port,
    )

    # Layer 2: Camera system
    camera = build_camera_system(config.camera)

    # Layer 3: Stimulus system
    stimulus = build_stimulus_system(config.monitor, config.stimulus)

    # Layer 4: Acquisition system
    acquisition = build_acquisition_system(
        camera=camera,
        stimulus=stimulus,
        shared_memory=shared_memory,
        config=config.acquisition,
    )

    # Layer 5: Analysis system
    analysis = build_analysis_system(
        shared_memory=shared_memory,
        config=config.analysis,
    )

    # Layer 6: Supporting services (NEW!)
    health_monitor = HealthMonitor(
        ipc=ipc,
        check_interval=5.0,
        cpu_warning_threshold=80.0,
        memory_warning_threshold=85.0,
        disk_warning_threshold=90.0,
    )

    return {
        "ipc": ipc,
        "shared_memory": shared_memory,
        "camera": camera,
        "stimulus": stimulus,
        "acquisition": acquisition,
        "analysis": analysis,
        "health_monitor": health_monitor,  # NEW!
    }
```

### 4. IPC Handlers

Add handlers for health and hardware queries:

```python
def create_handlers(services: dict) -> dict:
    """Create IPC command handlers.

    Args:
        services: Dictionary of service instances

    Returns:
        Dictionary mapping command names to handler functions
    """

    health = services["health_monitor"]

    handlers = {
        # Existing handlers...
        "start_camera": lambda cmd: services["camera"].start(),
        "stop_camera": lambda cmd: services["camera"].stop(),
        "start_acquisition": lambda cmd: services["acquisition"].start(cmd),
        "stop_acquisition": lambda cmd: services["acquisition"].stop(),

        # Health monitoring (NEW!)
        "get_health": lambda cmd: health.get_health_report().to_dict(),

        # Hardware detection (NEW!)
        "check_hardware": lambda cmd: check_hardware_availability(),
        "detect_displays": lambda cmd: {
            "displays": [d.to_dict() for d in detect_displays()],
            "primary": get_primary_display().to_dict() if get_primary_display() else None,
        },
        "validate_display": lambda cmd: {
            "valid": validate_display_config(
                cmd.get("width", 1920),
                cmd.get("height", 1080),
                cmd.get("refresh_rate"),
            )[0]
        },
    }

    return handlers
```

### 5. Cleanup

Add health monitor cleanup:

```python
def cleanup(services: dict):
    """Clean up all services.

    Args:
        services: Dictionary of service instances
    """

    # Stop health monitoring
    if "health_monitor" in services:
        services["health_monitor"].stop_monitoring()

    # Stop acquisition
    if "acquisition" in services:
        services["acquisition"].stop()

    # Stop camera
    if "camera" in services:
        services["camera"].stop()

    # Stop stimulus
    if "stimulus" in services:
        services["stimulus"].stop()

    # Cleanup IPC
    if "ipc" in services:
        services["ipc"].cleanup()

    # Cleanup shared memory
    if "shared_memory" in services:
        services["shared_memory"].cleanup()
```

## Usage Examples

### Example 1: Startup Validation

```python
from startup import StartupCoordinator

coordinator = StartupCoordinator()

# Validate system requirements
result = coordinator.validate_system_requirements()
if not result.success:
    print(f"Validation failed: {result.message}")
    print(f"Errors: {result.details['errors']}")

# Check hardware
hardware = coordinator.check_hardware_availability()
print(f"Cameras: {hardware['cameras']}")
print(f"GPU: {hardware['gpu']} ({hardware['gpu_type']})")
print(f"Displays: {hardware['displays']}")

# Validate config file
config_result = coordinator.validate_config_file("config/isi_parameters.json")
if config_result.success:
    print("Configuration file is valid")
```

### Example 2: Health Monitoring

```python
from health import HealthMonitor
from ipc.channels import build_multi_channel_ipc

# Create IPC
ipc = build_multi_channel_ipc()

# Create health monitor
health = HealthMonitor(
    ipc=ipc,
    check_interval=5.0,
    cpu_warning_threshold=80.0,
    memory_warning_threshold=85.0,
)

# Get single report
report = health.get_health_report()
print(f"Status: {report.status.value}")
print(f"CPU: {report.metrics.cpu_percent}%")
print(f"Memory: {report.metrics.memory_percent}%")
print(f"GPU: {report.metrics.gpu_available}")

# Start continuous monitoring (sends reports via IPC)
health.start_monitoring()

# ... application runs ...

# Stop monitoring
health.stop_monitoring()
```

### Example 3: Display Detection

```python
from display import detect_displays, get_primary_display, validate_display_config

# Detect all displays
displays = detect_displays()
for display in displays:
    print(f"{display.name}: {display.width}x{display.height} @ {display.refresh_rate}Hz")
    print(f"  Primary: {display.is_primary}")
    print(f"  Position: ({display.position_x}, {display.position_y})")

# Get primary display
primary = get_primary_display()
if primary:
    print(f"Primary display: {primary.name}")

# Validate display requirements
is_valid, message = validate_display_config(1920, 1080, 60.0)
if not is_valid:
    print(f"Display validation failed: {message}")
```

## Architecture Benefits

### 1. Pure Dependency Injection

All services receive dependencies explicitly via constructor:

```python
# GOOD - Explicit dependencies
health = HealthMonitor(ipc=ipc, check_interval=5.0)

# BAD - Service locator (OLD CODE)
health = HealthMonitor()  # Uses get_services() internally
```

### 2. Testability

Services can be easily tested with mock dependencies:

```python
from unittest.mock import Mock

mock_ipc = Mock()
health = HealthMonitor(ipc=mock_ipc, check_interval=1.0)

report = health.get_health_report()
assert report.status in [HealthStatus.ONLINE, HealthStatus.DEGRADED]
```

### 3. No Hidden Dependencies

All dependencies are visible at the composition root:

```python
# Everything is explicit at creation time
services = {
    "health_monitor": HealthMonitor(
        ipc=ipc,                    # Clear dependency
        check_interval=5.0,         # Clear configuration
    ),
}
```

### 4. Cross-Platform Support

Display detection works on macOS, Linux, and Windows:

```python
# Works on all platforms
displays = detect_displays()

# Platform-specific implementations are internal
# macOS: system_profiler
# Linux: xrandr
# Windows: win32api
```

## Health Metrics Tracked

The HealthMonitor tracks these metrics:

- **CPU Usage** - Overall system CPU utilization (%)
- **Memory Usage** - RAM utilization (%)
- **Memory Available** - Free RAM (MB)
- **Disk Usage** - Disk utilization (%)
- **Disk Free** - Free disk space (GB)
- **Thread Count** - Active threads in process
- **Process Count** - Total system processes
- **Uptime** - Application uptime (seconds)
- **GPU Available** - Whether GPU is present
- **GPU Memory** - GPU memory usage (if available)
- **GPU Utilization** - GPU compute utilization (if available)

## Startup Validations Performed

The StartupCoordinator validates:

1. **Python Version** - Minimum Python 3.10
2. **Memory** - Minimum 2GB RAM
3. **Disk Space** - Minimum 1GB free
4. **Required Packages** - numpy, opencv-python, torch, psutil, zmq
5. **Configuration File** - Valid JSON with required structure
6. **Hardware Detection** - Cameras, GPU, displays

## Display Information Provided

The display module detects:

- **Name** - Display model/name
- **Identifier** - Unique display identifier
- **Resolution** - Width and height in pixels
- **Refresh Rate** - Display refresh rate in Hz
- **Primary Status** - Whether display is primary
- **Position** - Screen position (x, y)
- **Scale Factor** - Display scaling (Retina, etc.)

## Success Criteria

✅ 3 new files created (health.py, startup.py, display.py)
✅ Test file passing all checks (test_phase7.py)
✅ ZERO service_locator imports in any module
✅ HealthMonitor uses constructor injection
✅ Display detection works on macOS
✅ Startup validation checks essential requirements
✅ Integration guidance provided for main.py

## Statistics

- **health.py**: 304 lines
- **startup.py**: 402 lines
- **display.py**: 432 lines
- **test_phase7.py**: 407 lines
- **Total**: 1,545 lines of clean, service-locator-free code

## Next Steps

1. Integrate these services into main.py composition root
2. Add IPC handlers for health and hardware queries
3. Use startup validation before service creation
4. Replace old health_monitor.py, startup_coordinator.py, display_manager.py
5. Update frontend to consume new health reports
6. Add display selection UI using new display detection

## References

- Phase 1-6 already complete
- All modules follow KISS principle
- Constructor injection only
- No service locator anti-pattern
- Pure functions for utilities
