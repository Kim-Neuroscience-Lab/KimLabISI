#!/usr/bin/env python3
"""Phase 6 Test Suite: Main Application Composition Root.

Verifies the complete system integration:
- main.py can be imported without errors
- create_services() instantiates all services correctly
- create_handlers() returns expected handler mapping
- NO service_locator imports exist
- Dependency graph is properly ordered

Run from backend root:
    cd /Users/Adam/KimLabISI/apps/backend && .venv/bin/python src/test_phase6.py
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from io import StringIO

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))


class TestPhase6MainApplication(unittest.TestCase):
    """Test suite for Phase 6: Main Application."""

    def test_01_import_main(self):
        """Test that main.py can be imported without errors."""
        print("\n[TEST 1] Testing main.py import...")
        try:
            import main
            print("  ✓ main.py imported successfully")
            self.assertTrue(hasattr(main, "create_services"))
            self.assertTrue(hasattr(main, "create_handlers"))
            self.assertTrue(hasattr(main, "ISIMacroscopeBackend"))
            self.assertTrue(hasattr(main, "main"))
            print("  ✓ All expected functions/classes present")
        except ImportError as e:
            self.fail(f"Failed to import main.py: {e}")

    def test_02_no_service_locator_imports(self):
        """Test that main.py does NOT import service_locator."""
        print("\n[TEST 2] Verifying NO service_locator imports...")
        main_path = Path(__file__).parent / "main.py"
        with open(main_path) as f:
            content = f.read()

        # Check for service_locator imports
        forbidden_imports = [
            "from isi_control.service_locator",
            "import service_locator",
            "get_services()",
            "set_registry(",
            "ServiceRegistry",
        ]

        violations = []
        for forbidden in forbidden_imports:
            if forbidden in content:
                violations.append(forbidden)

        if violations:
            print(f"  ✗ Found service_locator imports: {violations}")
            self.fail(f"main.py contains forbidden service_locator patterns: {violations}")
        else:
            print("  ✓ NO service_locator imports found")

    def test_03_create_services_with_mock_config(self):
        """Test that create_services() can instantiate all services."""
        print("\n[TEST 3] Testing create_services() with mock config...")

        import main
        from config import AppConfig

        # Create mock config with required attributes
        mock_config = Mock(spec=AppConfig)

        # IPC config
        mock_config.ipc = Mock()
        mock_config.ipc.transport = "tcp"
        mock_config.ipc.health_port = 5555
        mock_config.ipc.sync_port = 5558

        # Shared memory config
        mock_config.shared_memory = Mock()
        mock_config.shared_memory.stream_name = "test_stream"
        mock_config.shared_memory.buffer_size_mb = 100
        mock_config.shared_memory.metadata_port = 5557
        mock_config.shared_memory.camera_metadata_port = 5559

        # Camera config
        mock_config.camera = Mock()
        mock_config.camera.camera_width_px = 640
        mock_config.camera.camera_height_px = 480
        mock_config.camera.camera_fps = 30

        # Monitor config
        mock_config.monitor = Mock()
        mock_config.monitor.monitor_width_px = 1920
        mock_config.monitor.monitor_height_px = 1080
        mock_config.monitor.monitor_width_cm = 60.96
        mock_config.monitor.monitor_height_cm = 36.195
        mock_config.monitor.monitor_distance_cm = 10.0
        mock_config.monitor.monitor_lateral_angle_deg = 30.0
        mock_config.monitor.monitor_tilt_angle_deg = 20.0
        mock_config.monitor.monitor_fps = 60

        # Stimulus config
        mock_config.stimulus = Mock()
        mock_config.stimulus.bar_width_deg = 20.0
        mock_config.stimulus.checker_size_deg = 25.0
        mock_config.stimulus.drift_speed_deg_per_sec = 9.0
        mock_config.stimulus.contrast = 1.0
        mock_config.stimulus.background_luminance = 0.0
        mock_config.stimulus.strobe_rate_hz = 6.0

        # Acquisition config
        mock_config.acquisition = Mock()
        mock_config.acquisition.directions = ["LR", "RL", "TB", "BT"]
        mock_config.acquisition.cycles = 10
        mock_config.acquisition.baseline_sec = 5.0
        mock_config.acquisition.between_sec = 5.0

        # Analysis config
        mock_config.analysis = Mock()
        mock_config.analysis.magnitude_threshold = 0.1
        mock_config.analysis.phase_filter_sigma = 0.5
        mock_config.analysis.smoothing_sigma = 1.0
        mock_config.analysis.gradient_window_size = 3

        # Parameters config
        mock_config.parameters = Mock()
        test_path = Path("/tmp/test_params.json")
        test_path.parent.mkdir(parents=True, exist_ok=True)
        mock_config.parameters.file_path = test_path

        try:
            # Mock the ParameterManager since it requires a real config file
            with patch("main.ParameterManager") as mock_param_mgr:
                mock_param_mgr.return_value = Mock()

                services = main.create_services(mock_config)

                # Verify all expected services are present
                expected_services = [
                    "config",
                    "ipc",
                    "shared_memory",
                    "camera",
                    "stimulus_generator",
                    "acquisition",
                    "analysis_manager",
                    "analysis_renderer",
                    "playback_controller",
                    "param_manager",
                ]

                for service_name in expected_services:
                    self.assertIn(
                        service_name,
                        services,
                        f"Missing service: {service_name}"
                    )
                    print(f"  ✓ Service created: {service_name}")

                print(f"  ✓ All {len(expected_services)} services created successfully")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.fail(f"create_services() failed: {e}")

    def test_04_create_handlers(self):
        """Test that create_handlers() returns expected handler dict."""
        print("\n[TEST 4] Testing create_handlers()...")

        import main

        # Create mock services
        mock_services = {
            "config": Mock(),
            "ipc": Mock(),
            "shared_memory": Mock(),
            "camera": Mock(),
            "stimulus_generator": Mock(),
            "acquisition": Mock(),
            "analysis_manager": Mock(),
            "analysis_renderer": Mock(),
            "playback_controller": Mock(),
            "param_manager": Mock(),
        }

        try:
            handlers = main.create_handlers(mock_services)

            # Verify handler dict structure
            self.assertIsInstance(handlers, dict)
            self.assertGreater(len(handlers), 0)

            # Expected command types
            expected_commands = [
                # Camera
                "detect_cameras",
                "get_camera_capabilities",
                "start_camera_acquisition",
                "stop_camera_acquisition",
                "get_camera_histogram",
                "get_synchronization_data",
                # Acquisition
                "start_acquisition",
                "stop_acquisition",
                "get_acquisition_status",
                "set_acquisition_mode",
                # Playback
                "list_sessions",
                "load_session",
                "get_session_data",
                "unload_session",
                "get_playback_frame",
                # Analysis
                "start_analysis",
                "stop_analysis",
                "get_analysis_status",
                # Parameters
                "get_all_parameters",
                "get_parameter_group",
                "update_parameter_group",
                "reset_to_defaults",
                "get_parameter_info",
                # System
                "ping",
                "get_system_status",
                "health_check",
            ]

            missing_commands = []
            for cmd in expected_commands:
                if cmd not in handlers:
                    missing_commands.append(cmd)
                else:
                    # Verify handler is callable
                    self.assertTrue(
                        callable(handlers[cmd]),
                        f"Handler for {cmd} is not callable"
                    )
                    print(f"  ✓ Handler registered: {cmd}")

            if missing_commands:
                self.fail(f"Missing handlers: {missing_commands}")

            print(f"  ✓ All {len(expected_commands)} handlers registered")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.fail(f"create_handlers() failed: {e}")

    def test_05_handler_execution(self):
        """Test that handlers can be executed (basic smoke test)."""
        print("\n[TEST 5] Testing handler execution...")

        import main

        # Create mock services with minimal methods
        mock_camera = Mock()
        mock_camera.detect_cameras = Mock(return_value=[])
        mock_camera.get_latest_frame = Mock(return_value=None)

        mock_acquisition = Mock()
        mock_acquisition.get_status = Mock(return_value={
            "is_running": False,
            "phase": "idle"
        })
        mock_acquisition.get_synchronization_data = Mock(return_value={
            "synchronization": [],
            "statistics": {}
        })

        mock_analysis = Mock()
        mock_analysis.get_status = Mock(return_value={
            "is_running": False,
            "progress": 0.0
        })

        mock_playback = Mock()
        mock_playback.get_session_info = Mock(return_value={
            "success": True,
            "loaded": False
        })

        mock_param_mgr = Mock()
        mock_param_mgr.get_all_parameters = Mock(return_value={})
        mock_param_mgr.get_parameter_info = Mock(return_value={})

        mock_services = {
            "config": Mock(),
            "ipc": Mock(),
            "shared_memory": Mock(),
            "camera": mock_camera,
            "stimulus_generator": Mock(),
            "acquisition": mock_acquisition,
            "analysis_manager": mock_analysis,
            "analysis_renderer": Mock(),
            "playback_controller": mock_playback,
            "param_manager": mock_param_mgr,
        }

        handlers = main.create_handlers(mock_services)

        # Test a few representative handlers
        test_commands = [
            ("ping", {}),
            ("get_system_status", {}),
            ("get_acquisition_status", {}),
            ("get_analysis_status", {}),
            ("get_all_parameters", {}),
        ]

        for cmd_type, cmd_data in test_commands:
            try:
                result = handlers[cmd_type](cmd_data)
                self.assertIsInstance(result, dict, f"{cmd_type} should return dict")
                print(f"  ✓ Handler executed: {cmd_type}")
            except Exception as e:
                self.fail(f"Handler {cmd_type} execution failed: {e}")

        print(f"  ✓ All {len(test_commands)} test handlers executed successfully")

    def test_06_backend_class(self):
        """Test ISIMacroscopeBackend class structure."""
        print("\n[TEST 6] Testing ISIMacroscopeBackend class...")

        import main

        # Create mock services and handlers
        mock_services = {"ipc": Mock(), "camera": Mock(), "acquisition": Mock()}
        mock_handlers = {"ping": lambda cmd: {"success": True}}

        try:
            backend = main.ISIMacroscopeBackend(mock_services, mock_handlers)

            # Verify attributes
            self.assertEqual(backend.services, mock_services)
            self.assertEqual(backend.handlers, mock_handlers)
            self.assertFalse(backend.running)

            # Verify methods exist
            self.assertTrue(hasattr(backend, "start"))
            self.assertTrue(hasattr(backend, "shutdown"))
            self.assertTrue(hasattr(backend, "handle_signal"))

            print("  ✓ ISIMacroscopeBackend class structure valid")

        except Exception as e:
            self.fail(f"ISIMacroscopeBackend initialization failed: {e}")

    def test_07_dependency_graph_order(self):
        """Test that service creation follows proper dependency order."""
        print("\n[TEST 7] Verifying dependency graph order...")

        import main
        from config import AppConfig

        # Mock config (minimal)
        mock_config = Mock(spec=AppConfig)
        mock_config.ipc = Mock(transport="tcp", health_port=5555, sync_port=5558)
        mock_config.shared_memory = Mock(
            stream_name="test",
            buffer_size_mb=100,
            metadata_port=5557,
            camera_metadata_port=5559
        )
        mock_config.camera = Mock(
            camera_width_px=640,
            camera_height_px=480,
            camera_fps=30
        )
        mock_config.monitor = Mock(
            monitor_width_px=1920,
            monitor_height_px=1080,
            monitor_width_cm=60.0,
            monitor_height_cm=36.0,
            monitor_distance_cm=10.0,
            monitor_lateral_angle_deg=30.0,
            monitor_tilt_angle_deg=20.0,
            monitor_fps=60
        )
        mock_config.stimulus = Mock(
            bar_width_deg=20.0,
            checker_size_deg=25.0,
            drift_speed_deg_per_sec=9.0,
            contrast=1.0,
            background_luminance=0.0,
            strobe_rate_hz=6.0
        )
        mock_config.acquisition = Mock(
            directions=["LR"],
            cycles=1,
            baseline_sec=1.0,
            between_sec=1.0
        )
        mock_config.analysis = Mock(
            magnitude_threshold=0.1,
            phase_filter_sigma=0.5,
            smoothing_sigma=1.0,
            gradient_window_size=3
        )
        test_path = Path("/tmp/test.json")
        test_path.parent.mkdir(parents=True, exist_ok=True)
        mock_config.parameters = Mock(
            file_path=test_path
        )

        # Track creation order
        creation_order = []

        def track_creation(name):
            def wrapper(*args, **kwargs):
                creation_order.append(name)
                return Mock()
            return wrapper

        with patch("main.MultiChannelIPC", side_effect=track_creation("ipc")), \
             patch("main.SharedMemoryService", side_effect=track_creation("shared_memory")), \
             patch("main.ParameterManager", side_effect=track_creation("param_manager")), \
             patch("main.StimulusGenerator", side_effect=track_creation("stimulus_generator")), \
             patch("main.CameraManager", side_effect=track_creation("camera")), \
             patch("main.AnalysisPipeline", side_effect=track_creation("analysis_pipeline")), \
             patch("main.AnalysisRenderer", side_effect=track_creation("analysis_renderer")), \
             patch("main.AnalysisManager", side_effect=track_creation("analysis_manager")), \
             patch("main.AcquisitionStateCoordinator", side_effect=track_creation("state_coordinator")), \
             patch("main.TimestampSynchronizationTracker", side_effect=track_creation("sync_tracker")), \
             patch("main.CameraTriggeredStimulusController", side_effect=track_creation("camera_triggered_stimulus")), \
             patch("main.PlaybackModeController", side_effect=track_creation("playback_controller")), \
             patch("main.AcquisitionManager", side_effect=track_creation("acquisition")):

            services = main.create_services(mock_config)

            # Verify infrastructure created first
            infra_services = ["ipc", "shared_memory", "param_manager"]
            for svc in infra_services:
                self.assertIn(svc, creation_order[:5], f"{svc} should be created early")
                print(f"  ✓ Infrastructure service created early: {svc}")

            # Verify acquisition manager created after dependencies
            acq_deps = ["stimulus_generator", "state_coordinator", "sync_tracker"]
            acquisition_index = creation_order.index("acquisition")
            for dep in acq_deps:
                dep_index = creation_order.index(dep)
                self.assertLess(
                    dep_index,
                    acquisition_index,
                    f"{dep} should be created before acquisition"
                )
                print(f"  ✓ Dependency order correct: {dep} → acquisition")

            print("  ✓ Dependency graph order is correct")

    def test_08_main_function_exists(self):
        """Test that main() function exists and is properly structured."""
        print("\n[TEST 8] Verifying main() function...")

        import main
        import inspect

        # Verify main() exists
        self.assertTrue(hasattr(main, "main"))
        self.assertTrue(callable(main.main))

        # Get source code
        source = inspect.getsource(main.main)

        # Verify key steps are present
        required_steps = [
            "create_services",
            "create_handlers",
            "ISIMacroscopeBackend",
            "signal.signal",
        ]

        for step in required_steps:
            self.assertIn(step, source, f"main() should call {step}")
            print(f"  ✓ main() includes: {step}")

        print("  ✓ main() function structure valid")


def run_tests():
    """Run all Phase 6 tests."""
    print("=" * 80)
    print("PHASE 6 TEST SUITE: Main Application Composition Root")
    print("=" * 80)

    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPhase6MainApplication)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.wasSuccessful():
        print("\n✓ ALL PHASE 6 TESTS PASSED!")
        print("\nPhase 6 Complete: Main Application composition root verified")
        return 0
    else:
        print("\n✗ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
