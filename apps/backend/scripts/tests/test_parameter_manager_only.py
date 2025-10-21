"""Test ParameterManager subscription mechanism only.

This test verifies the core Parameter Manager functionality without requiring
GPU dependencies (PyTorch).
"""
import time
import logging
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from parameters.manager import ParameterManager

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
    logger.info("Subscribed to 'stimulus' parameter group")

    # Update a parameter
    logger.info("Updating bar_width_deg to 99.9...")
    param_manager.update_parameter_group("stimulus", {"bar_width_deg": 99.9})

    # Verify notification was received
    assert len(updates_received) == 1, f"Expected 1 update, got {len(updates_received)}"
    assert updates_received[0][0] == "stimulus", "Wrong group name"
    assert "bar_width_deg" in updates_received[0][1], "bar_width_deg not in updates"

    logger.info("✅ Subscription mechanism works correctly")
    logger.info("")
    return True


def test_multiple_subscribers():
    """Test that multiple subscribers receive notifications."""
    logger.info("=" * 70)
    logger.info("TEST 2: Multiple Subscribers")
    logger.info("=" * 70)

    config_path = Path(__file__).parent / "config" / "isi_parameters.json"
    param_manager = ParameterManager(
        config_file=config_path.name,
        config_dir=str(config_path.parent)
    )

    # Track updates from different subscribers
    subscriber1_updates = []
    subscriber2_updates = []

    def subscriber1(group, updates):
        subscriber1_updates.append((group, updates))
        logger.info(f"  Subscriber 1 received: {list(updates.keys())}")

    def subscriber2(group, updates):
        subscriber2_updates.append((group, updates))
        logger.info(f"  Subscriber 2 received: {list(updates.keys())}")

    # Subscribe both
    param_manager.subscribe("monitor", subscriber1)
    param_manager.subscribe("monitor", subscriber2)
    logger.info("Subscribed 2 subscribers to 'monitor' parameter group")

    # Update a parameter
    logger.info("Updating monitor_distance_cm to 25.0...")
    param_manager.update_parameter_group("monitor", {"monitor_distance_cm": 25.0})

    # Verify both received notification
    assert len(subscriber1_updates) == 1, "Subscriber 1 didn't receive update"
    assert len(subscriber2_updates) == 1, "Subscriber 2 didn't receive update"

    logger.info("✅ Multiple subscribers work correctly")
    logger.info("")
    return True


def test_parameter_persistence():
    """Test that parameter changes persist across ParameterManager instances."""
    logger.info("=" * 70)
    logger.info("TEST 3: Parameter Persistence")
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
    return True


def test_unsubscribe():
    """Test that unsubscribe works correctly."""
    logger.info("=" * 70)
    logger.info("TEST 4: Unsubscribe Mechanism")
    logger.info("=" * 70)

    config_path = Path(__file__).parent / "config" / "isi_parameters.json"
    param_manager = ParameterManager(
        config_file=config_path.name,
        config_dir=str(config_path.parent)
    )

    updates_received = []

    def callback(group, updates):
        updates_received.append((group, updates))
        logger.info(f"  Received update: {list(updates.keys())}")

    # Subscribe
    param_manager.subscribe("camera", callback)
    logger.info("Subscribed to 'camera' parameter group")

    # Update (should receive)
    logger.info("Updating camera_fps to 60...")
    param_manager.update_parameter_group("camera", {"camera_fps": 60})
    assert len(updates_received) == 1, "Didn't receive first update"

    # Unsubscribe
    logger.info("Unsubscribing...")
    param_manager.unsubscribe("camera", callback)

    # Update again (should NOT receive)
    logger.info("Updating camera_fps to 90 (should not receive)...")
    param_manager.update_parameter_group("camera", {"camera_fps": 90})
    assert len(updates_received) == 1, "Received update after unsubscribe!"

    logger.info("✅ Unsubscribe works correctly")
    logger.info("")
    return True


def main():
    """Run all tests."""
    logger.info("\n")
    logger.info("╔" + "═" * 68 + "╗")
    logger.info("║" + " " * 8 + "PARAMETER MANAGER SUBSCRIPTION TEST SUITE" + " " * 17 + "║")
    logger.info("╚" + "═" * 68 + "╝")
    logger.info("\n")

    try:
        # Run all tests
        test_parameter_manager_subscription()
        test_multiple_subscribers()
        test_parameter_persistence()
        test_unsubscribe()

        # Summary
        logger.info("=" * 70)
        logger.info("✅ ALL TESTS PASSED!")
        logger.info("=" * 70)
        logger.info("")
        logger.info("ParameterManager subscription mechanism is working correctly:")
        logger.info("  • Subscription/unsubscription works")
        logger.info("  • Multiple subscribers receive notifications")
        logger.info("  • Parameter changes trigger callbacks")
        logger.info("  • Parameters persist to JSON file")
        logger.info("")
        logger.info("The refactoring is complete and ready for component integration!")
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
