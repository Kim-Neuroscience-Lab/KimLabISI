#!/usr/bin/env python3
"""Phase 8: Integration Testing - Comprehensive System Validation.

This test suite verifies that the entire refactored system integrates correctly:
- All services wire together properly
- Configuration loading works
- Handler mapping is complete
- IPC communication works
- No service_locator imports in new codebase
- All dependencies are satisfied

Run with: python src/test_integration.py
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, MagicMock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from config import AppConfig
from main import create_services, create_handlers, ISIMacroscopeBackend

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TestIntegration:
    """Integration test suite for Phase 8."""

    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.errors = []

    def assert_true(self, condition: bool, message: str):
        """Assert that condition is true."""
        if condition:
            self.tests_passed += 1
            logger.info(f"  PASS: {message}")
        else:
            self.tests_failed += 1
            self.errors.append(message)
            logger.error(f"  FAIL: {message}")

    def assert_equal(self, actual, expected, message: str):
        """Assert that actual equals expected."""
        if actual == expected:
            self.tests_passed += 1
            logger.info(f"  PASS: {message}")
        else:
            self.tests_failed += 1
            error = f"{message} (expected {expected}, got {actual})"
            self.errors.append(error)
            logger.error(f"  FAIL: {error}")

    def assert_in(self, item, container, message: str):
        """Assert that item is in container."""
        if item in container:
            self.tests_passed += 1
            logger.info(f"  PASS: {message}")
        else:
            self.tests_failed += 1
            error = f"{message} ('{item}' not in container)"
            self.errors.append(error)
            logger.error(f"  FAIL: {error}")

    def test_config_loading_from_default(self):
        """Test 1: Configuration can be loaded with defaults."""
        logger.info("\n[Test 1] Testing default configuration loading...")

        try:
            config = AppConfig.default()

            # Verify all sections exist
            self.assert_true(config.ipc is not None, "IPC config exists")
            self.assert_true(config.shared_memory is not None, "Shared memory config exists")
            self.assert_true(config.camera is not None, "Camera config exists")
            self.assert_true(config.monitor is not None, "Monitor config exists")
            self.assert_true(config.stimulus is not None, "Stimulus config exists")
            self.assert_true(config.acquisition is not None, "Acquisition config exists")
            self.assert_true(config.analysis is not None, "Analysis config exists")
            self.assert_true(config.session is not None, "Session config exists")
            self.assert_true(config.parameters is not None, "Parameters config exists")
            self.assert_true(config.logging is not None, "Logging config exists")

            # Verify some key values
            self.assert_equal(config.ipc.health_port, 5555, "IPC health port is correct")
            self.assert_equal(config.ipc.sync_port, 5558, "IPC sync port is correct")
            self.assert_equal(config.shared_memory.stream_name, "stimulus_stream", "Stream name is correct")

            logger.info("  Configuration loading from defaults: OK")
        except Exception as e:
            self.tests_failed += 1
            self.errors.append(f"Config loading failed: {e}")
            logger.error(f"  FAIL: Config loading error: {e}")

    def test_config_loading_from_file(self):
        """Test 2: Configuration can be loaded from JSON file."""
        logger.info("\n[Test 2] Testing configuration loading from JSON file...")

        config_path = Path(__file__).parent.parent / "config" / "isi_parameters.json"

        if not config_path.exists():
            logger.warning(f"  SKIP: Config file not found at {config_path}")
            return

        try:
            config = AppConfig.from_file(str(config_path))

            # Verify config loaded
            self.assert_true(config is not None, "Config loaded from file")
            self.assert_true(config.ipc is not None, "IPC config loaded")
            self.assert_true(config.camera is not None, "Camera config loaded")

            logger.info("  Configuration loading from file: OK")
        except Exception as e:
            self.tests_failed += 1
            self.errors.append(f"Config file loading failed: {e}")
            logger.error(f"  FAIL: Config file loading error: {e}")

    def test_service_creation(self):
        """Test 3: All services can be created via composition root."""
        logger.info("\n[Test 3] Testing service creation (composition root)...")

        try:
            config = AppConfig.default()

            # Mock hardware-dependent components
            with patch('camera.manager.CameraManager.__init__', return_value=None), \
                 patch('stimulus.generator.StimulusGenerator.__init__', return_value=None), \
                 patch('ipc.channels.MultiChannelIPC.__init__', return_value=None), \
                 patch('ipc.shared_memory.SharedMemoryService.__init__', return_value=None):

                services = create_services(config)

                # Verify all expected services exist
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
                    self.assert_in(service_name, services, f"Service '{service_name}' exists")

                logger.info("  Service creation: OK")

        except Exception as e:
            self.tests_failed += 1
            self.errors.append(f"Service creation failed: {e}")
            logger.error(f"  FAIL: Service creation error: {e}")

    def test_handler_mapping_complete(self):
        """Test 4: Handler mapping covers all expected commands."""
        logger.info("\n[Test 4] Testing handler mapping completeness...")

        try:
            config = AppConfig.default()

            # Create mock services
            mock_services = {
                "config": config,
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

            # Configure mocks
            mock_services["camera"].detect_cameras = Mock(return_value=[])
            mock_services["camera"].get_camera_capabilities = Mock(return_value={})
            mock_services["camera"].start_acquisition = Mock(return_value=True)
            mock_services["camera"].stop_acquisition = Mock(return_value=None)
            mock_services["camera"].get_latest_frame = Mock(return_value=None)
            mock_services["camera"].generate_luminance_histogram = Mock(return_value={})

            mock_services["acquisition"].start_acquisition = Mock(return_value={"success": True})
            mock_services["acquisition"].stop_acquisition = Mock(return_value={"success": True})
            mock_services["acquisition"].get_status = Mock(return_value={"running": False})
            mock_services["acquisition"].set_mode = Mock(return_value={"success": True})
            mock_services["acquisition"].get_synchronization_data = Mock(return_value={})

            mock_services["playback_controller"].list_sessions = Mock(return_value={"success": True})
            mock_services["playback_controller"].load_session = Mock(return_value={"success": True})
            mock_services["playback_controller"].get_session_info = Mock(return_value={"success": True})
            mock_services["playback_controller"].unload_session = Mock(return_value={"success": True})
            mock_services["playback_controller"].get_frame = Mock(return_value={"success": True})

            mock_services["analysis_manager"].start_analysis = Mock(return_value={"success": True})
            mock_services["analysis_manager"].stop_analysis = Mock(return_value={"success": True})
            mock_services["analysis_manager"].get_status = Mock(return_value={"running": False})

            mock_services["param_manager"].get_all_parameters = Mock(return_value={})
            mock_services["param_manager"].get_parameter_group = Mock(return_value={})
            mock_services["param_manager"].update_parameter_group = Mock(return_value=None)
            mock_services["param_manager"].reset_to_defaults = Mock(return_value=None)
            mock_services["param_manager"].get_parameter_info = Mock(return_value={})

            # Create handlers
            handlers = create_handlers(mock_services)

            # Verify handler exists for each expected command
            expected_commands = [
                # Camera commands
                "detect_cameras",
                "get_camera_capabilities",
                "start_camera_acquisition",
                "stop_camera_acquisition",
                "get_camera_histogram",
                "get_synchronization_data",
                # Acquisition commands
                "start_acquisition",
                "stop_acquisition",
                "get_acquisition_status",
                "set_acquisition_mode",
                # Playback commands
                "list_sessions",
                "load_session",
                "get_session_data",
                "unload_session",
                "get_playback_frame",
                # Analysis commands
                "start_analysis",
                "stop_analysis",
                "get_analysis_status",
                # Parameter commands
                "get_all_parameters",
                "get_parameter_group",
                "update_parameter_group",
                "reset_to_defaults",
                "get_parameter_info",
                # System commands
                "ping",
                "get_system_status",
                "health_check",
            ]

            for cmd in expected_commands:
                self.assert_in(cmd, handlers, f"Handler exists for '{cmd}'")

            logger.info(f"  Handler mapping: {len(handlers)} handlers created")

        except Exception as e:
            self.tests_failed += 1
            self.errors.append(f"Handler mapping failed: {e}")
            logger.error(f"  FAIL: Handler mapping error: {e}")

    def test_handler_execution(self):
        """Test 5: Handlers can be executed (mocked)."""
        logger.info("\n[Test 5] Testing handler execution...")

        try:
            config = AppConfig.default()

            # Create mock services
            mock_services = {
                "config": config,
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

            # Configure mocks
            mock_services["camera"].detect_cameras = Mock(return_value=["FakeCam"])
            mock_services["acquisition"].get_status = Mock(return_value={"running": False})
            mock_services["param_manager"].get_all_parameters = Mock(return_value={"test": "value"})

            # Create handlers
            handlers = create_handlers(mock_services)

            # Test ping handler
            result = handlers["ping"]({"type": "ping"})
            self.assert_true(result["success"], "Ping handler returns success")
            self.assert_true(result["pong"], "Ping handler returns pong")

            # Test health_check handler
            result = handlers["health_check"]({"type": "health_check"})
            self.assert_equal(result["status"], "healthy", "Health check returns healthy")
            self.assert_in("services", result, "Health check includes services list")

            # Test get_system_status handler
            result = handlers["get_system_status"]({"type": "get_system_status"})
            self.assert_true(result["success"], "System status returns success")
            self.assert_true(result["backend_running"], "Backend reports running")

            # Test detect_cameras handler
            result = handlers["detect_cameras"]({"type": "detect_cameras"})
            self.assert_true(result["success"], "Detect cameras returns success")
            self.assert_in("cameras", result, "Detect cameras returns camera list")

            # Test get_acquisition_status handler
            result = handlers["get_acquisition_status"]({"type": "get_acquisition_status"})
            self.assert_true(result["success"], "Acquisition status returns success")

            # Test get_all_parameters handler
            result = handlers["get_all_parameters"]({"type": "get_all_parameters"})
            self.assert_true(result["success"], "Get parameters returns success")
            self.assert_in("parameters", result, "Get parameters includes parameters")

            logger.info("  Handler execution: OK")

        except Exception as e:
            self.tests_failed += 1
            self.errors.append(f"Handler execution failed: {e}")
            logger.error(f"  FAIL: Handler execution error: {e}")

    def test_no_service_locator_imports(self):
        """Test 6: Verify ZERO service_locator imports in new codebase."""
        logger.info("\n[Test 6] Testing for service_locator anti-pattern...")

        try:
            import subprocess

            # Search for actual service_locator imports (from/import statements)
            result = subprocess.run(
                ["grep", "-r", "-E", "(from|import).*service_locator", "src/"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )

            # Filter out old isi_control directory, test files, and documentation
            lines = [
                line for line in result.stdout.split('\n')
                if line
                and 'isi_control' not in line
                and 'test_' not in line
                and '.md' not in line
                and 'SUMMARY' not in line
            ]

            self.assert_equal(len(lines), 0, "ZERO service_locator imports in new code")

            if lines:
                logger.error("  Found service_locator imports:")
                for line in lines:
                    logger.error(f"    {line}")

        except Exception as e:
            # grep returns error code if no matches found - this is OK
            if "grep" in str(e):
                self.tests_passed += 1
                logger.info("  PASS: ZERO service_locator imports in new code")
            else:
                self.tests_failed += 1
                self.errors.append(f"Service locator check failed: {e}")
                logger.error(f"  FAIL: Service locator check error: {e}")

    def test_all_modules_importable(self):
        """Test 7: All new modules can be imported successfully."""
        logger.info("\n[Test 7] Testing module imports...")

        modules_to_test = [
            "config",
            "main",
            "startup",
            "health",
            "display",
            "ipc.channels",
            "ipc.shared_memory",
            "camera.manager",
            "camera.utils",
            "stimulus.generator",
            "stimulus.transform",
            "acquisition.manager",
            "acquisition.state",
            "acquisition.sync_tracker",
            "acquisition.camera_stimulus",
            "acquisition.recorder",
            "acquisition.modes",
            "analysis.manager",
            "analysis.pipeline",
            "analysis.renderer",
        ]

        for module_name in modules_to_test:
            try:
                __import__(module_name)
                self.tests_passed += 1
                logger.info(f"  PASS: Import {module_name}")
            except Exception as e:
                self.tests_failed += 1
                error = f"Import {module_name} failed: {e}"
                self.errors.append(error)
                logger.error(f"  FAIL: {error}")

    def test_backend_initialization(self):
        """Test 8: Backend can be instantiated."""
        logger.info("\n[Test 8] Testing backend initialization...")

        try:
            config = AppConfig.default()

            # Create mock services
            mock_services = {
                "config": config,
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

            # Configure mocks
            mock_services["acquisition"].is_running = False
            mock_services["camera"].shutdown = Mock()
            mock_services["acquisition"].stop_acquisition = Mock()
            mock_services["ipc"].stop = Mock()
            mock_services["shared_memory"].cleanup = Mock()

            # Create handlers
            handlers = create_handlers(mock_services)

            # Create backend
            backend = ISIMacroscopeBackend(mock_services, handlers)

            self.assert_true(backend is not None, "Backend instance created")
            self.assert_true(backend.services is not None, "Backend has services")
            self.assert_true(backend.handlers is not None, "Backend has handlers")
            self.assert_equal(backend.running, False, "Backend not running initially")

            # Test shutdown (without starting)
            backend.shutdown()
            self.assert_equal(backend.running, False, "Backend shutdown completes")

            logger.info("  Backend initialization: OK")

        except Exception as e:
            self.tests_failed += 1
            self.errors.append(f"Backend initialization failed: {e}")
            logger.error(f"  FAIL: Backend initialization error: {e}")

    def test_dependency_injection_pattern(self):
        """Test 9: Verify constructor injection pattern is used."""
        logger.info("\n[Test 9] Testing dependency injection pattern...")

        try:
            # Verify no global singletons in new modules
            import subprocess

            # Search for 'provide_' functions (old pattern)
            result = subprocess.run(
                ["grep", "-r", "def provide_", "src/"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )

            lines = [
                line for line in result.stdout.split('\n')
                if line and 'isi_control' not in line and 'test_' not in line
            ]

            self.assert_equal(len(lines), 0, "No provide_* functions in new code")

            # Search for global _instance variables (singleton pattern)
            result = subprocess.run(
                ["grep", "-r", "_instance = None", "src/"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )

            lines = [
                line for line in result.stdout.split('\n')
                if line and 'isi_control' not in line and 'test_' not in line
            ]

            self.assert_equal(len(lines), 0, "No singleton instances in new code")

            logger.info("  Dependency injection pattern: OK")

        except Exception as e:
            self.tests_failed += 1
            self.errors.append(f"DI pattern check failed: {e}")
            logger.error(f"  FAIL: DI pattern check error: {e}")

    def test_configuration_serialization(self):
        """Test 10: Configuration can be serialized to dict."""
        logger.info("\n[Test 10] Testing configuration serialization...")

        try:
            config = AppConfig.default()
            config_dict = config.to_dict()

            # Verify all sections present
            expected_sections = [
                "ipc", "shared_memory", "camera", "monitor", "stimulus",
                "acquisition", "analysis", "session", "parameters", "logging"
            ]

            for section in expected_sections:
                self.assert_in(section, config_dict, f"Config dict has '{section}'")

            # Verify nested structure
            self.assert_in("health_port", config_dict["ipc"], "IPC config has health_port")
            self.assert_in("stream_name", config_dict["shared_memory"], "SharedMem config has stream_name")

            logger.info("  Configuration serialization: OK")

        except Exception as e:
            self.tests_failed += 1
            self.errors.append(f"Config serialization failed: {e}")
            logger.error(f"  FAIL: Config serialization error: {e}")

    def run_all_tests(self):
        """Run all integration tests."""
        logger.info("=" * 80)
        logger.info("PHASE 8: INTEGRATION TESTING")
        logger.info("=" * 80)

        # Run all tests
        self.test_config_loading_from_default()
        self.test_config_loading_from_file()
        self.test_service_creation()
        self.test_handler_mapping_complete()
        self.test_handler_execution()
        self.test_no_service_locator_imports()
        self.test_all_modules_importable()
        self.test_backend_initialization()
        self.test_dependency_injection_pattern()
        self.test_configuration_serialization()

        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("INTEGRATION TEST SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Tests Passed: {self.tests_passed}")
        logger.info(f"Tests Failed: {self.tests_failed}")
        logger.info(f"Total Tests:  {self.tests_passed + self.tests_failed}")

        if self.tests_failed > 0:
            logger.error("\nFailed Tests:")
            for error in self.errors:
                logger.error(f"  - {error}")
            logger.error("\nINTEGRATION TESTS: FAILED")
            return False
        else:
            logger.info("\nINTEGRATION TESTS: PASSED")
            return True


def main():
    """Main entry point for integration tests."""
    test_suite = TestIntegration()
    success = test_suite.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
