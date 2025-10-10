"""Phase 7 test suite - Supporting Services.

Verifies that health monitoring, startup coordination, and display detection
work correctly with NO service locator dependencies.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))


def test_no_service_locator_imports():
    """Verify NO service_locator imports in any Phase 7 module."""
    print("\n=== Test 1: NO service_locator imports ===")

    modules_to_check = ["health", "startup", "display"]

    for module_name in modules_to_check:
        module_path = Path(__file__).parent / f"{module_name}.py"

        if not module_path.exists():
            print(f"  ✗ Module not found: {module_path}")
            return False

        with open(module_path) as f:
            content = f.read()

        # Check for service_locator imports
        if "service_locator" in content:
            print(f"  ✗ FAILED: {module_name}.py contains 'service_locator'")
            return False

        # Check for get_services calls
        if "get_services" in content:
            print(f"  ✗ FAILED: {module_name}.py contains 'get_services'")
            return False

        print(f"  ✓ {module_name}.py - NO service_locator imports")

    print("  ✓ All modules clean - NO service_locator dependencies")
    return True


def test_health_monitor_instantiation():
    """Verify HealthMonitor can be instantiated with IPC."""
    print("\n=== Test 2: HealthMonitor instantiation ===")

    try:
        from health import HealthMonitor, HealthStatus
        from ipc.channels import build_multi_channel_ipc

        # Create IPC
        ipc = build_multi_channel_ipc()

        # Create health monitor with explicit dependencies
        monitor = HealthMonitor(
            ipc=ipc,
            check_interval=1.0,
            cpu_warning_threshold=80.0,
            memory_warning_threshold=85.0,
            disk_warning_threshold=90.0,
        )

        print(f"  ✓ HealthMonitor instantiated: {type(monitor).__name__}")
        print(f"  ✓ Check interval: {monitor.check_interval}s")
        print(f"  ✓ CPU warning threshold: {monitor.cpu_warning_threshold}%")

        # Cleanup
        ipc.cleanup()
        return True

    except Exception as exc:
        print(f"  ✗ FAILED: {exc}")
        import traceback

        traceback.print_exc()
        return False


def test_health_monitor_report():
    """Verify HealthMonitor can generate health reports."""
    print("\n=== Test 3: HealthMonitor health report ===")

    try:
        from health import HealthMonitor
        from ipc.channels import build_multi_channel_ipc

        ipc = build_multi_channel_ipc()
        monitor = HealthMonitor(ipc=ipc, check_interval=1.0)

        # Get health report
        report = monitor.get_health_report()

        print(f"  ✓ Health status: {report.status.value}")
        print(f"  ✓ CPU usage: {report.metrics.cpu_percent:.1f}%")
        print(f"  ✓ Memory usage: {report.metrics.memory_percent:.1f}%")
        print(f"  ✓ Disk usage: {report.metrics.disk_usage_percent:.1f}%")
        print(f"  ✓ Thread count: {report.metrics.thread_count}")
        print(f"  ✓ GPU available: {report.metrics.gpu_available}")
        print(f"  ✓ Warnings: {len(report.warnings)}")
        print(f"  ✓ Errors: {len(report.errors)}")

        # Test to_dict
        report_dict = report.to_dict()
        assert "status" in report_dict
        assert "metrics" in report_dict
        assert "is_healthy" in report_dict
        print("  ✓ Report to_dict() works")

        # Cleanup
        ipc.cleanup()
        return True

    except Exception as exc:
        print(f"  ✗ FAILED: {exc}")
        import traceback

        traceback.print_exc()
        return False


def test_health_monitor_lifecycle():
    """Verify HealthMonitor start/stop works."""
    print("\n=== Test 4: HealthMonitor lifecycle ===")

    try:
        from health import HealthMonitor
        from ipc.channels import build_multi_channel_ipc

        ipc = build_multi_channel_ipc()
        monitor = HealthMonitor(ipc=ipc, check_interval=0.5)

        # Start monitoring
        monitor.start_monitoring()
        print("  ✓ Monitoring started")
        assert monitor.is_monitoring

        # Let it run briefly
        time.sleep(1.0)

        # Stop monitoring
        monitor.stop_monitoring()
        print("  ✓ Monitoring stopped")
        assert not monitor.is_monitoring

        # Cleanup
        ipc.cleanup()
        return True

    except Exception as exc:
        print(f"  ✗ FAILED: {exc}")
        import traceback

        traceback.print_exc()
        return False


def test_startup_coordinator():
    """Verify StartupCoordinator validation functions work."""
    print("\n=== Test 5: StartupCoordinator validation ===")

    try:
        from startup import (
            StartupCoordinator,
            SystemRequirements,
            validate_system_requirements,
            check_hardware_availability,
        )

        # Test system requirements validation
        coordinator = StartupCoordinator()
        result = coordinator.validate_system_requirements()

        print(f"  ✓ System validation: {result.success}")
        print(f"  ✓ Message: {result.message}")
        if result.details:
            print(f"  ✓ Python version: {result.details.get('python_version', 'unknown')}")
            print(f"  ✓ Platform: {result.details.get('platform', 'unknown')}")

        # Test hardware availability check
        hardware = coordinator.check_hardware_availability()
        print(f"  ✓ Cameras detected: {hardware.get('cameras', 0)}")
        print(f"  ✓ GPU available: {hardware.get('gpu', False)}")
        print(f"  ✓ Displays detected: {hardware.get('displays', 0)}")

        # Test simple function APIs
        success, errors = validate_system_requirements()
        print(f"  ✓ Simple API validation: {success}")

        hardware2 = check_hardware_availability()
        print(f"  ✓ Simple API hardware check: {len(hardware2)} keys")

        return True

    except Exception as exc:
        print(f"  ✗ FAILED: {exc}")
        import traceback

        traceback.print_exc()
        return False


def test_startup_config_validation():
    """Verify StartupCoordinator can validate config files."""
    print("\n=== Test 6: StartupCoordinator config validation ===")

    try:
        from startup import StartupCoordinator

        coordinator = StartupCoordinator()

        # Test with actual config file
        config_path = Path(__file__).parents[1] / "config" / "isi_parameters.json"

        if config_path.exists():
            result = coordinator.validate_config_file(config_path)
            print(f"  ✓ Config validation: {result.success}")
            print(f"  ✓ Message: {result.message}")
            if result.details:
                print(f"  ✓ Path: {result.details.get('path', 'unknown')}")
        else:
            print(f"  ⊙ Config file not found (skipping): {config_path}")

        # Test with non-existent file
        result = coordinator.validate_config_file("/tmp/nonexistent.json")
        assert not result.success
        print("  ✓ Non-existent file correctly rejected")

        return True

    except Exception as exc:
        print(f"  ✗ FAILED: {exc}")
        import traceback

        traceback.print_exc()
        return False


def test_display_detection():
    """Verify display detection functions work."""
    print("\n=== Test 7: Display detection ===")

    try:
        from display import (
            detect_displays,
            get_primary_display,
            validate_display_config,
            get_display_by_identifier,
        )

        # Detect displays
        displays = detect_displays()
        print(f"  ✓ Displays detected: {len(displays)}")

        for idx, display in enumerate(displays):
            print(f"    Display {idx}: {display.name}")
            print(f"      Resolution: {display.width}x{display.height}")
            print(f"      Refresh rate: {display.refresh_rate}Hz")
            print(f"      Primary: {display.is_primary}")
            print(f"      Identifier: {display.identifier}")

            # Test to_dict
            display_dict = display.to_dict()
            assert "name" in display_dict
            assert "width" in display_dict
            print(f"      ✓ to_dict() works")

        # Get primary display
        primary = get_primary_display()
        if primary:
            print(f"  ✓ Primary display: {primary.name}")
        else:
            print("  ⊙ No primary display found")

        # Validate display config
        is_valid, message = validate_display_config(1920, 1080)
        print(f"  ✓ Config validation (1920x1080): {is_valid}")
        if not is_valid:
            print(f"    Message: {message}")

        # Test get by identifier
        if displays:
            display = get_display_by_identifier(displays[0].identifier)
            assert display is not None
            print(f"  ✓ get_display_by_identifier works")

        return True

    except Exception as exc:
        print(f"  ✗ FAILED: {exc}")
        import traceback

        traceback.print_exc()
        return False


def test_display_validation():
    """Verify display validation functions."""
    print("\n=== Test 8: Display validation ===")

    try:
        from display import validate_display_config, get_display_by_name

        # Test validation with reasonable requirements
        is_valid, message = validate_display_config(800, 600)
        print(f"  ✓ Validate 800x600: {is_valid}")

        # Test validation with unreasonable requirements
        is_valid, message = validate_display_config(10000, 10000)
        print(f"  ✓ Validate 10000x10000: {is_valid} (expected False)")
        assert not is_valid
        print(f"    Error message: {message}")

        # Test get by name
        display = get_display_by_name("NonExistentDisplay")
        assert display is None
        print("  ✓ get_display_by_name returns None for invalid name")

        return True

    except Exception as exc:
        print(f"  ✗ FAILED: {exc}")
        import traceback

        traceback.print_exc()
        return False


def count_lines_of_code():
    """Count total lines of code created."""
    print("\n=== Lines of Code ===")

    modules = ["health.py", "startup.py", "display.py", "test_phase7.py"]
    total_lines = 0

    for module_name in modules:
        module_path = Path(__file__).parent / module_name

        if module_path.exists():
            with open(module_path) as f:
                lines = len(f.readlines())
            total_lines += lines
            print(f"  {module_name:20s} {lines:4d} lines")

    print(f"  {'─' * 20} {'─' * 4}")
    print(f"  {'Total':20s} {total_lines:4d} lines")
    return total_lines


def main():
    """Run all Phase 7 tests."""
    print("=" * 60)
    print("Phase 7 Test Suite: Supporting Services")
    print("=" * 60)

    tests = [
        ("NO service_locator imports", test_no_service_locator_imports),
        ("HealthMonitor instantiation", test_health_monitor_instantiation),
        ("HealthMonitor report", test_health_monitor_report),
        ("HealthMonitor lifecycle", test_health_monitor_lifecycle),
        ("StartupCoordinator validation", test_startup_coordinator),
        ("StartupCoordinator config", test_startup_config_validation),
        ("Display detection", test_display_detection),
        ("Display validation", test_display_validation),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as exc:
            print(f"\n✗ Test '{test_name}' crashed: {exc}")
            import traceback

            traceback.print_exc()
            failed += 1

    # Count lines of code
    total_lines = count_lines_of_code()

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Total:  {passed + failed}")
    print(f"\n  Lines of code: {total_lines}")

    if failed == 0:
        print("\n✓ ALL TESTS PASSED")
        return 0
    else:
        print(f"\n✗ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
