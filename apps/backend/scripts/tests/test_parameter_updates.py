"""Test that parameter updates propagate to components in real-time.

This test verifies the Parameter Manager refactoring is complete and working:
- Components inject ParameterManager instead of frozen configs
- Components subscribe to parameter changes
- Parameter changes trigger component updates
"""
import time
import logging
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from parameters.manager import ParameterManager
from stimulus.generator import StimulusGenerator

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def test_parameter_manager_subscription():
    """Test that ParameterManager subscription mechanism works."""
    logger.info("=" * 70)
    logger.info("TEST 1: ParameterManager Subscription Mechanism")
    logger.info("=" * 70)

    config_path = Path(__file__).parent / "config" / "isi_parameters.json"
    param_manager = ParameterManager(
        config_file=config_path.name,
        config_dir=str(config_path.parent)
    )

    # Track update notifications
    updates_received = []

    def track_update(group, updates):
        updates_received.append((group, updates))
        logger.info(f"  Received update notification: group={group}, keys={list(updates.keys())}")

    # Subscribe to stimulus updates
    param_manager.subscribe("stimulus", track_update)

    # Update a parameter
    logger.info("Updating bar_width_deg to 99.9...")
    param_manager.update_parameter_group("stimulus", {"bar_width_deg": 99.9})

    # Verify notification was received
    assert len(updates_received) == 1, f"Expected 1 update, got {len(updates_received)}"
    assert updates_received[0][0] == "stimulus", "Wrong group name"
    assert "bar_width_deg" in updates_received[0][1], "bar_width_deg not in updates"

    logger.info("✅ Subscription mechanism works correctly")
    logger.info("")


def test_stimulus_generator_reacts():
    """Test that StimulusGenerator rebuilds state when parameters change."""
    logger.info("=" * 70)
    logger.info("TEST 2: StimulusGenerator Parameter Updates")
    logger.info("=" * 70)

    config_path = Path(__file__).parent / "config" / "isi_parameters.json"
    param_manager = ParameterManager(
        config_file=config_path.name,
        config_dir=str(config_path.parent)
    )

    # Create stimulus generator (should inject ParameterManager)
    logger.info("Creating StimulusGenerator with ParameterManager...")
    stimulus_gen = StimulusGenerator(
        param_manager=param_manager,
        logger=logger
    )

    # Get initial bar width
    initial_bar_width = stimulus_gen.bar_width_deg
    logger.info(f"Initial bar_width_deg: {initial_bar_width}")

    # Change parameter
    new_width = initial_bar_width + 10.0
    logger.info(f"Updating bar_width_deg to {new_width}...")
    param_manager.update_parameter_group("stimulus", {"bar_width_deg": new_width})

    # Give time for callback to execute
    time.sleep(0.1)

    # Verify generator has new value
    updated_width = stimulus_gen.bar_width_deg
    logger.info(f"Updated bar_width_deg: {updated_width}")

    assert updated_width == new_width, \
        f"Expected {new_width}, got {updated_width}. Generator did not update!"

    logger.info("✅ StimulusGenerator reacts to parameter changes")
    logger.info("")


def test_monitor_parameter_updates():
    """Test that monitor parameter changes trigger spatial reconfiguration."""
    logger.info("=" * 70)
    logger.info("TEST 3: Monitor Parameter Updates")
    logger.info("=" * 70)

    config_path = Path(__file__).parent / "config" / "isi_parameters.json"
    param_manager = ParameterManager(
        config_file=config_path.name,
        config_dir=str(config_path.parent)
    )

    # Create stimulus generator
    logger.info("Creating StimulusGenerator with ParameterManager...")
    stimulus_gen = StimulusGenerator(
        param_manager=param_manager,
        logger=logger
    )

    # Get initial FOV
    initial_fov = stimulus_gen.spatial_config.field_of_view_horizontal
    initial_distance = stimulus_gen.monitor_distance_cm
    logger.info(f"Initial horizontal FOV: {initial_fov:.2f}°")
    logger.info(f"Initial monitor distance: {initial_distance} cm")

    # Change monitor distance (should affect FOV)
    new_distance = initial_distance + 5.0
    logger.info(f"Updating monitor_distance_cm to {new_distance}...")
    param_manager.update_parameter_group("monitor", {"monitor_distance_cm": new_distance})

    # Give time for callback to execute
    time.sleep(0.1)

    # Verify spatial config was rebuilt
    updated_fov = stimulus_gen.spatial_config.field_of_view_horizontal
    updated_distance = stimulus_gen.monitor_distance_cm
    logger.info(f"Updated horizontal FOV: {updated_fov:.2f}°")
    logger.info(f"Updated monitor distance: {updated_distance} cm")

    assert updated_distance == new_distance, \
        f"Expected distance {new_distance}, got {updated_distance}"
    assert updated_fov != initial_fov, \
        f"FOV should have changed when distance changed"

    logger.info("✅ Monitor parameter updates trigger spatial reconfiguration")
    logger.info("")


def test_parameter_persistence():
    """Test that parameter changes persist across ParameterManager instances."""
    logger.info("=" * 70)
    logger.info("TEST 4: Parameter Persistence")
    logger.info("=" * 70)

    config_path = Path(__file__).parent / "config" / "isi_parameters.json"

    # Create first instance and update parameter
    param_manager1 = ParameterManager(
        config_file=config_path.name,
        config_dir=str(config_path.parent)
    )

    test_value = 123.456
    logger.info(f"Setting checker_size_deg to {test_value}...")
    param_manager1.update_parameter_group("stimulus", {"checker_size_deg": test_value})

    # Create second instance (simulates restart)
    logger.info("Creating new ParameterManager instance (simulates restart)...")
    param_manager2 = ParameterManager(
        config_file=config_path.name,
        config_dir=str(config_path.parent)
    )

    # Verify parameter persisted
    stimulus_params = param_manager2.get_parameter_group("stimulus")
    loaded_value = stimulus_params.get("checker_size_deg")
    logger.info(f"Loaded checker_size_deg: {loaded_value}")

    assert loaded_value == test_value, \
        f"Expected {test_value}, got {loaded_value}. Parameter did not persist!"

    logger.info("✅ Parameters persist across restarts")
    logger.info("")


def main():
    """Run all tests."""
    logger.info("\n")
    logger.info("╔" + "═" * 68 + "╗")
    logger.info("║" + " " * 10 + "PARAMETER MANAGER REFACTORING TEST SUITE" + " " * 18 + "║")
    logger.info("╚" + "═" * 68 + "╝")
    logger.info("\n")

    try:
        # Run all tests
        test_parameter_manager_subscription()
        test_stimulus_generator_reacts()
        test_monitor_parameter_updates()
        test_parameter_persistence()

        # Summary
        logger.info("=" * 70)
        logger.info("✅ ALL TESTS PASSED!")
        logger.info("=" * 70)
        logger.info("")
        logger.info("Real-time parameter updates are working correctly:")
        logger.info("  • Components inject ParameterManager (no frozen configs)")
        logger.info("  • Components subscribe to parameter changes")
        logger.info("  • Parameter changes trigger component updates")
        logger.info("  • Parameters persist to JSON file")
        logger.info("")
        logger.info("The Single Source of Truth violation has been fixed!")
        logger.info("")

        return 0

    except AssertionError as e:
        logger.error("")
        logger.error("=" * 70)
        logger.error("❌ TEST FAILED")
        logger.error("=" * 70)
        logger.error(f"Error: {e}")
        logger.error("")
        return 1

    except Exception as e:
        logger.error("")
        logger.error("=" * 70)
        logger.error("❌ TEST ERROR")
        logger.error("=" * 70)
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        logger.error("")
        return 1


if __name__ == "__main__":
    sys.exit(main())
