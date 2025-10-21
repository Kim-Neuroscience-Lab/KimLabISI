#!/usr/bin/env python3
"""Profile ISI backend startup to identify bottlenecks.

This script instruments the startup flow with timing measurements
to identify genuine performance bottlenecks.
"""

import sys
import time
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Track timing for each major operation
timings = {}

def time_operation(name):
    """Decorator to time an operation."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            timings[name] = elapsed * 1000  # Convert to ms
            print(f"[TIMING] {name:50s} {elapsed*1000:8.2f} ms")
            return result
        return wrapper
    return decorator


# Monkey-patch critical functions to measure timing
def instrument_startup():
    """Instrument startup functions with timing measurements."""

    # 1. Import modules
    start = time.perf_counter()
    from config import AppConfig
    from camera.manager import CameraManager
    from parameters import ParameterManager
    from display import detect_displays
    timings["imports"] = (time.perf_counter() - start) * 1000
    print(f"[TIMING] {'Module imports':50s} {timings['imports']:8.2f} ms")

    # 2. Patch camera detection
    original_detect = CameraManager.detect_cameras
    @time_operation("camera_detection")
    def timed_detect(self, max_cameras=10, force=False, keep_first_open=False):
        return original_detect(self, max_cameras, force, keep_first_open)
    CameraManager.detect_cameras = timed_detect

    # 3. Patch camera opening
    original_open = CameraManager.open_camera
    @time_operation("camera_open")
    def timed_open(self, camera_index):
        return original_open(self, camera_index)
    CameraManager.open_camera = timed_open

    # 4. Patch display detection
    original_detect_displays = detect_displays
    @time_operation("display_detection")
    def timed_detect_displays():
        return original_detect_displays()

    # Replace in module
    import display
    display.detect_displays = timed_detect_displays

    # 5. Patch parameter manager operations
    original_save = ParameterManager._save
    save_count = [0]

    def timed_save(self):
        save_count[0] += 1
        name = f"param_save_{save_count[0]}"
        start = time.perf_counter()
        result = original_save(self)
        elapsed = (time.perf_counter() - start) * 1000
        timings[name] = elapsed
        print(f"[TIMING] {name:50s} {elapsed:8.2f} ms")
        return result

    ParameterManager._save = timed_save

    # 6. Patch system command execution
    from camera.utils import run_system_command
    original_run_cmd = run_system_command

    def timed_run_cmd(command, timeout=10):
        cmd_name = f"syscmd: {command[0]}"
        start = time.perf_counter()
        result = original_run_cmd(command, timeout)
        elapsed = (time.perf_counter() - start) * 1000
        timings[cmd_name] = elapsed
        print(f"[TIMING] {cmd_name:50s} {elapsed:8.2f} ms")
        return result

    # Replace in module
    import camera.utils
    camera.utils.run_system_command = timed_run_cmd


def profile_startup():
    """Profile the entire startup sequence."""
    print("=" * 80)
    print("ISI Backend Startup Profiler")
    print("=" * 80)
    print()

    # Instrument before starting
    instrument_startup()

    # Now run the actual startup
    from logging_config import configure_logging
    configure_logging(level=logging.WARNING)

    from config import AppConfig
    from main import create_services, create_handlers

    # Load config
    start = time.perf_counter()
    config_path = Path(__file__).parent / "config" / "isi_parameters.json"
    if config_path.exists():
        config = AppConfig.from_file(str(config_path))
    else:
        config = AppConfig.default()
    timings["config_load"] = (time.perf_counter() - start) * 1000
    print(f"[TIMING] {'Config load':50s} {timings['config_load']:8.2f} ms")

    # Create services (this is where most time is spent)
    start = time.perf_counter()
    services = create_services(config)
    timings["create_services"] = (time.perf_counter() - start) * 1000
    print(f"[TIMING] {'create_services()':50s} {timings['create_services']:8.2f} ms")

    # Create handlers
    start = time.perf_counter()
    handlers = create_handlers(services)
    timings["create_handlers"] = (time.perf_counter() - start) * 1000
    print(f"[TIMING] {'create_handlers()':50s} {timings['create_handlers']:8.2f} ms")

    # Simulate hardware verification (what happens on frontend_ready)
    from main import _verify_hardware
    start = time.perf_counter()
    result = _verify_hardware(
        services["camera"],
        services["param_manager"],
        services["ipc"]
    )
    timings["verify_hardware"] = (time.perf_counter() - start) * 1000
    print(f"[TIMING] {'_verify_hardware()':50s} {timings['verify_hardware']:8.2f} ms")

    # Print summary
    print()
    print("=" * 80)
    print("STARTUP TIMING SUMMARY")
    print("=" * 80)

    # Group timings by category
    categories = {
        "Initialization": ["imports", "config_load", "create_services", "create_handlers"],
        "Hardware Detection": ["camera_detection", "camera_open", "display_detection", "verify_hardware"],
        "Parameter I/O": [k for k in timings.keys() if k.startswith("param_save_")],
        "System Commands": [k for k in timings.keys() if k.startswith("syscmd:")],
    }

    for category, keys in categories.items():
        total = sum(timings.get(k, 0) for k in keys)
        print(f"\n{category}:")
        for key in keys:
            if key in timings:
                print(f"  {key:45s} {timings[key]:8.2f} ms")
        print(f"  {'TOTAL':45s} {total:8.2f} ms")

    # Overall total
    overall_total = sum(timings.values())
    print()
    print(f"{'OVERALL STARTUP TIME':50s} {overall_total:8.2f} ms ({overall_total/1000:.2f}s)")
    print()

    # Identify bottlenecks (operations > 500ms)
    bottlenecks = [(k, v) for k, v in timings.items() if v > 500]
    if bottlenecks:
        print("=" * 80)
        print("IDENTIFIED BOTTLENECKS (> 500ms)")
        print("=" * 80)
        for name, time_ms in sorted(bottlenecks, key=lambda x: x[1], reverse=True):
            print(f"  {name:45s} {time_ms:8.2f} ms")
        print()

    # Count parameter saves
    param_saves = len([k for k in timings.keys() if k.startswith("param_save_")])
    if param_saves > 2:
        print("=" * 80)
        print(f"WARNING: {param_saves} parameter file writes detected during startup")
        print("Consider batching parameter updates to reduce disk I/O")
        print("=" * 80)
        print()

    return timings


if __name__ == "__main__":
    try:
        timings = profile_startup()
    except KeyboardInterrupt:
        print("\nProfiling interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\nError during profiling: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
