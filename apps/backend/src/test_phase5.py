#!/usr/bin/env python3
"""Test suite for Phase 5: Analysis System

Verifies that the analysis system follows constructor injection pattern
and has NO service locator dependencies.
"""

import sys
import os
from pathlib import Path
import traceback
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Test results
tests_passed = 0
tests_failed = 0
test_details = []


def test_section(name: str):
    """Print test section header."""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print('='*60)


def test_result(name: str, passed: bool, details: str = ""):
    """Record and print test result."""
    global tests_passed, tests_failed, test_details

    status = "PASS" if passed else "FAIL"
    symbol = "✓" if passed else "✗"

    if passed:
        tests_passed += 1
    else:
        tests_failed += 1

    result_line = f"{symbol} {status}: {name}"
    print(result_line)

    if details:
        print(f"  {details}")

    test_details.append({
        "name": name,
        "passed": passed,
        "details": details
    })


def check_no_service_locator_imports():
    """Verify NO service_locator imports in analysis modules."""
    test_section("SERVICE LOCATOR VERIFICATION")

    analysis_dir = Path(__file__).parent / "analysis"
    analysis_files = list(analysis_dir.glob("*.py"))

    all_clean = True
    problematic_files = []

    for file_path in analysis_files:
        if file_path.name.startswith("_"):
            continue

        with open(file_path, 'r') as f:
            content = f.read()

        # Check for service_locator imports
        if "service_locator" in content.lower():
            all_clean = False
            problematic_files.append(file_path.name)
            test_result(
                f"No service_locator in {file_path.name}",
                False,
                "Found 'service_locator' reference!"
            )
        else:
            test_result(
                f"No service_locator in {file_path.name}",
                True
            )

        # Check for get_services calls
        if "get_services" in content:
            all_clean = False
            if file_path.name not in problematic_files:
                problematic_files.append(file_path.name)
            test_result(
                f"No get_services in {file_path.name}",
                False,
                "Found 'get_services' call!"
            )
        else:
            test_result(
                f"No get_services in {file_path.name}",
                True
            )

    if all_clean:
        test_result(
            "All analysis modules are service_locator-free",
            True,
            "No service locator anti-pattern found!"
        )
    else:
        test_result(
            "All analysis modules are service_locator-free",
            False,
            f"Problematic files: {', '.join(problematic_files)}"
        )


def test_imports():
    """Test that all modules can be imported."""
    test_section("MODULE IMPORTS")

    # Test config import
    try:
        from config import AnalysisConfig, AcquisitionConfig
        test_result("Import config", True)
    except Exception as e:
        test_result("Import config", False, str(e))
        return False

    # Test IPC imports
    try:
        from ipc.channels import MultiChannelIPC
        from ipc.shared_memory import SharedMemoryService
        test_result("Import IPC modules", True)
    except Exception as e:
        test_result("Import IPC modules", False, str(e))
        return False

    # Test analysis imports
    try:
        from analysis import (
            AnalysisPipeline,
            AnalysisManager,
            AnalysisRenderer,
            AnalysisResults,
            SessionData,
            DirectionData
        )
        test_result("Import analysis modules", True)
    except Exception as e:
        test_result("Import analysis modules", False, str(e))
        traceback.print_exc()
        return False

    return True


def test_constructor_injection():
    """Test that all classes use constructor injection."""
    test_section("CONSTRUCTOR INJECTION VERIFICATION")

    try:
        from config import AnalysisConfig, AcquisitionConfig, AppConfig
        from analysis import AnalysisPipeline, AnalysisManager, AnalysisRenderer
        from ipc.channels import MultiChannelIPC
        from ipc.shared_memory import SharedMemoryService

        # Test AnalysisPipeline instantiation
        try:
            config = AppConfig.default()
            pipeline = AnalysisPipeline(config=config.analysis)
            test_result(
                "AnalysisPipeline constructor injection",
                True,
                "Takes AnalysisConfig via constructor"
            )
        except Exception as e:
            test_result(
                "AnalysisPipeline constructor injection",
                False,
                f"Failed: {e}"
            )

        # Test AnalysisRenderer instantiation
        try:
            # Create mock shared memory service
            shared_mem_config = config.shared_memory
            shared_memory = SharedMemoryService(shared_mem_config)

            renderer = AnalysisRenderer(
                config=config.analysis,
                shared_memory=shared_memory
            )
            test_result(
                "AnalysisRenderer constructor injection",
                True,
                "Takes config and shared_memory via constructor"
            )
        except Exception as e:
            test_result(
                "AnalysisRenderer constructor injection",
                False,
                f"Failed: {e}"
            )

        # Test AnalysisManager instantiation (more complex)
        try:
            # Create mock IPC using simple constructor
            ipc = MultiChannelIPC(
                transport="tcp",
                health_port=5555,
                sync_port=5558
            )

            manager = AnalysisManager(
                config=config.analysis,
                acquisition_config=config.acquisition,
                ipc=ipc,
                shared_memory=shared_memory,
                pipeline=pipeline
            )
            test_result(
                "AnalysisManager constructor injection",
                True,
                "Takes all dependencies via constructor"
            )

            # Cleanup
            ipc.cleanup()
            shared_memory.cleanup()

        except Exception as e:
            test_result(
                "AnalysisManager constructor injection",
                False,
                f"Failed: {e}"
            )
            traceback.print_exc()

    except Exception as e:
        test_result(
            "Constructor injection tests",
            False,
            f"Setup failed: {e}"
        )
        traceback.print_exc()


def test_analysis_pipeline_functionality():
    """Test basic analysis pipeline functionality."""
    test_section("ANALYSIS PIPELINE FUNCTIONALITY")

    try:
        from config import AppConfig
        from analysis import AnalysisPipeline

        config = AppConfig.default()
        pipeline = AnalysisPipeline(config=config.analysis)

        # Create synthetic test data (50 frames, 100x100 pixels)
        n_frames = 50
        height, width = 100, 100

        # Generate synthetic frames with sinusoidal pattern
        frames = np.zeros((n_frames, height, width), dtype=np.float32)
        for i in range(n_frames):
            phase = 2 * np.pi * i / n_frames
            frames[i] = 128 + 127 * np.sin(phase)

        frames = frames.astype(np.uint8)

        # Test FFT computation
        try:
            stimulus_freq = 1.0 / n_frames  # 1 cycle over all frames
            phase_map, magnitude_map = pipeline.compute_fft_phase_maps(
                frames, stimulus_freq
            )

            # Check output shapes
            if phase_map.shape == (height, width) and magnitude_map.shape == (height, width):
                test_result(
                    "FFT phase map computation",
                    True,
                    f"Output shapes correct: {phase_map.shape}"
                )
            else:
                test_result(
                    "FFT phase map computation",
                    False,
                    f"Wrong shapes: phase={phase_map.shape}, mag={magnitude_map.shape}"
                )

            # Check phase range [-π, π]
            if np.all((phase_map >= -np.pi) & (phase_map <= np.pi)):
                test_result(
                    "Phase values in correct range",
                    True,
                    "Phase ∈ [-π, π]"
                )
            else:
                test_result(
                    "Phase values in correct range",
                    False,
                    f"Phase range: [{np.min(phase_map):.2f}, {np.max(phase_map):.2f}]"
                )

            # Check magnitude non-negative
            if np.all(magnitude_map >= 0):
                test_result(
                    "Magnitude values non-negative",
                    True,
                    "All magnitude values ≥ 0"
                )
            else:
                test_result(
                    "Magnitude values non-negative",
                    False,
                    f"Found negative magnitudes"
                )

        except Exception as e:
            test_result(
                "FFT phase map computation",
                False,
                f"Error: {e}"
            )
            traceback.print_exc()

        # Test bidirectional analysis
        try:
            # Create two synthetic phase maps
            forward_phase = np.random.uniform(-np.pi, np.pi, (height, width))
            reverse_phase = np.random.uniform(-np.pi, np.pi, (height, width))

            center_map = pipeline.bidirectional_analysis(forward_phase, reverse_phase)

            if center_map.shape == (height, width):
                test_result(
                    "Bidirectional analysis",
                    True,
                    f"Output shape correct: {center_map.shape}"
                )
            else:
                test_result(
                    "Bidirectional analysis",
                    False,
                    f"Wrong shape: {center_map.shape}"
                )

        except Exception as e:
            test_result(
                "Bidirectional analysis",
                False,
                f"Error: {e}"
            )
            traceback.print_exc()

        # Test gradient computation
        try:
            azimuth_map = np.random.uniform(-60, 60, (height, width))
            elevation_map = np.random.uniform(-30, 30, (height, width))

            gradients = pipeline.compute_spatial_gradients(azimuth_map, elevation_map)

            expected_keys = ['d_azimuth_dx', 'd_azimuth_dy', 'd_elevation_dx', 'd_elevation_dy']
            if all(key in gradients for key in expected_keys):
                test_result(
                    "Spatial gradient computation",
                    True,
                    f"All gradient components present"
                )
            else:
                test_result(
                    "Spatial gradient computation",
                    False,
                    f"Missing gradient components: {set(expected_keys) - set(gradients.keys())}"
                )

        except Exception as e:
            test_result(
                "Spatial gradient computation",
                False,
                f"Error: {e}"
            )
            traceback.print_exc()

        # Test visual field sign calculation
        try:
            sign_map = pipeline.calculate_visual_field_sign(gradients)

            # Check that sign map contains only -1, 0, 1
            unique_values = np.unique(sign_map)
            if np.all(np.isin(unique_values, [-1, 0, 1])):
                test_result(
                    "Visual field sign calculation",
                    True,
                    f"Sign values correct: {unique_values}"
                )
            else:
                test_result(
                    "Visual field sign calculation",
                    False,
                    f"Invalid sign values: {unique_values}"
                )

        except Exception as e:
            test_result(
                "Visual field sign calculation",
                False,
                f"Error: {e}"
            )
            traceback.print_exc()

    except Exception as e:
        test_result(
            "Analysis pipeline functionality",
            False,
            f"Setup failed: {e}"
        )
        traceback.print_exc()


def test_renderer_functionality():
    """Test renderer functionality."""
    test_section("RENDERER FUNCTIONALITY")

    try:
        from config import AppConfig
        from analysis import AnalysisRenderer
        from ipc.shared_memory import SharedMemoryService

        config = AppConfig.default()
        shared_memory = SharedMemoryService(config.shared_memory)
        renderer = AnalysisRenderer(config=config.analysis, shared_memory=shared_memory)

        height, width = 100, 100

        # Test phase map rendering
        try:
            phase_map = np.random.uniform(-np.pi, np.pi, (height, width))
            magnitude_map = np.random.uniform(0, 1, (height, width))

            rgb_image = renderer.render_phase_map(phase_map, magnitude_map)

            if rgb_image.shape == (height, width, 3) and rgb_image.dtype == np.uint8:
                test_result(
                    "Phase map rendering",
                    True,
                    f"RGB output shape correct: {rgb_image.shape}"
                )
            else:
                test_result(
                    "Phase map rendering",
                    False,
                    f"Wrong shape/dtype: {rgb_image.shape}, {rgb_image.dtype}"
                )

        except Exception as e:
            test_result(
                "Phase map rendering",
                False,
                f"Error: {e}"
            )

        # Test retinotopic map rendering
        try:
            azimuth_map = np.random.uniform(-60, 60, (height, width))

            rgb_image = renderer.render_retinotopic_map(azimuth_map, 'azimuth')

            if rgb_image.shape == (height, width, 3) and rgb_image.dtype == np.uint8:
                test_result(
                    "Retinotopic map rendering",
                    True,
                    f"RGB output shape correct"
                )
            else:
                test_result(
                    "Retinotopic map rendering",
                    False,
                    f"Wrong shape/dtype"
                )

        except Exception as e:
            test_result(
                "Retinotopic map rendering",
                False,
                f"Error: {e}"
            )

        # Test sign map rendering
        try:
            sign_map = np.random.choice([-1, 0, 1], size=(height, width))

            rgb_image = renderer.render_sign_map(sign_map)

            if rgb_image.shape == (height, width, 3) and rgb_image.dtype == np.uint8:
                test_result(
                    "Sign map rendering",
                    True,
                    f"RGB output shape correct"
                )
            else:
                test_result(
                    "Sign map rendering",
                    False,
                    f"Wrong shape/dtype"
                )

        except Exception as e:
            test_result(
                "Sign map rendering",
                False,
                f"Error: {e}"
            )

        # Cleanup
        shared_memory.cleanup()

    except Exception as e:
        test_result(
            "Renderer functionality",
            False,
            f"Setup failed: {e}"
        )
        traceback.print_exc()


def count_lines_of_code():
    """Count lines of code in analysis modules."""
    test_section("CODE METRICS")

    analysis_dir = Path(__file__).parent / "analysis"
    total_lines = 0
    file_counts = {}

    for file_path in analysis_dir.glob("*.py"):
        with open(file_path, 'r') as f:
            lines = len(f.readlines())
            file_counts[file_path.name] = lines
            total_lines += lines

        print(f"  {file_path.name}: {lines} lines")

    print(f"\n  Total: {total_lines} lines")

    # Expected rough line counts
    expected_ranges = {
        "pipeline.py": (400, 700),
        "manager.py": (300, 600),
        "renderer.py": (200, 400),
        "__init__.py": (10, 30),
    }

    all_in_range = True
    for filename, (min_lines, max_lines) in expected_ranges.items():
        if filename in file_counts:
            actual = file_counts[filename]
            if min_lines <= actual <= max_lines:
                print(f"  ✓ {filename}: {actual} lines (expected {min_lines}-{max_lines})")
            else:
                print(f"  ✗ {filename}: {actual} lines (expected {min_lines}-{max_lines})")
                all_in_range = False

    return total_lines, all_in_range


def print_summary():
    """Print test summary."""
    test_section("TEST SUMMARY")

    print(f"\nTests Passed: {tests_passed}")
    print(f"Tests Failed: {tests_failed}")
    print(f"Total Tests:  {tests_passed + tests_failed}")

    if tests_failed == 0:
        print("\n✓ ALL TESTS PASSED!")
        print("\nPhase 5 (Analysis System) is complete and ready!")
    else:
        print("\n✗ SOME TESTS FAILED")
        print("\nFailed tests:")
        for detail in test_details:
            if not detail["passed"]:
                print(f"  - {detail['name']}")
                if detail["details"]:
                    print(f"    {detail['details']}")


def main():
    """Run all tests."""
    print("="*60)
    print("  PHASE 5: ANALYSIS SYSTEM - TEST SUITE")
    print("="*60)
    print("\nVerifying constructor injection pattern and functionality...")

    # Run all tests
    check_no_service_locator_imports()

    if test_imports():
        test_constructor_injection()
        test_analysis_pipeline_functionality()
        test_renderer_functionality()

    total_lines, in_range = count_lines_of_code()

    print_summary()

    # Exit with appropriate code
    sys.exit(0 if tests_failed == 0 else 1)


if __name__ == "__main__":
    main()
