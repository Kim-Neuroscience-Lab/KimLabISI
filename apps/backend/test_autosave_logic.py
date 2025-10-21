#!/usr/bin/env python3
"""Test script to verify auto-save logic (without importing full backend)."""

from unittest.mock import Mock


def _unified_stimulus_pregenerate_handler(unified_stimulus, cmd):
    """Copy of the handler function for testing."""
    import logging
    logger = logging.getLogger(__name__)

    # Pre-generate all directions
    result = unified_stimulus.pre_generate_all_directions()

    # If pre-generation succeeded, automatically save to disk
    if result.get("success"):
        logger.info("Pre-generation successful, automatically saving library to disk...")

        save_result = unified_stimulus.save_library_to_disk()

        if save_result.get("success"):
            logger.info(f"Library auto-saved to: {save_result.get('save_path')}")
            # Add save info to result
            result["auto_saved"] = True
            result["save_path"] = save_result.get("save_path")
            result["saved_files"] = save_result.get("files")
        else:
            # Log warning but don't fail the pre-generation
            logger.warning(f"Pre-generation succeeded but auto-save failed: {save_result.get('error')}")
            result["auto_saved"] = False
            result["save_warning"] = save_result.get("error")
    else:
        # Pre-generation failed, no save attempted
        result["auto_saved"] = False

    return result


def test_autosave_success():
    """Test that auto-save is called after successful pre-generation."""
    print("Test 1: Auto-save after successful pre-generation")

    # Mock unified_stimulus controller
    unified_stimulus = Mock()

    # Mock successful pre-generation
    unified_stimulus.pre_generate_all_directions.return_value = {
        "success": True,
        "statistics": {
            "total_frames": 1000,
            "total_memory_bytes": 1000000
        }
    }

    # Mock successful save
    unified_stimulus.save_library_to_disk.return_value = {
        "success": True,
        "save_path": "/path/to/library",
        "files": ["file1.h5", "file2.h5"]
    }

    # Call handler
    result = _unified_stimulus_pregenerate_handler(unified_stimulus, {})

    # Verify pre-generation was called
    assert unified_stimulus.pre_generate_all_directions.called, "Pre-generation should be called"

    # Verify save was called after successful pre-generation
    assert unified_stimulus.save_library_to_disk.called, "Save should be called after successful pre-generation"

    # Verify result includes auto-save info
    assert result.get("success") == True, "Result should indicate success"
    assert result.get("auto_saved") == True, "Result should indicate auto-save succeeded"
    assert result.get("save_path") == "/path/to/library", "Result should include save path"

    print("✓ Test 1 passed: Auto-save called after successful pre-generation")


def test_autosave_failure():
    """Test that pre-generation success is not affected by save failure."""
    print("\nTest 2: Pre-generation succeeds even if auto-save fails")

    # Mock unified_stimulus controller
    unified_stimulus = Mock()

    # Mock successful pre-generation
    unified_stimulus.pre_generate_all_directions.return_value = {
        "success": True,
        "statistics": {
            "total_frames": 1000
        }
    }

    # Mock failed save
    unified_stimulus.save_library_to_disk.return_value = {
        "success": False,
        "error": "Disk full"
    }

    # Call handler
    result = _unified_stimulus_pregenerate_handler(unified_stimulus, {})

    # Verify pre-generation was called
    assert unified_stimulus.pre_generate_all_directions.called, "Pre-generation should be called"

    # Verify save was attempted
    assert unified_stimulus.save_library_to_disk.called, "Save should be attempted"

    # Verify result shows success (pre-generation succeeded)
    assert result.get("success") == True, "Result should indicate success despite save failure"
    assert result.get("auto_saved") == False, "Result should indicate auto-save failed"
    assert "save_warning" in result, "Result should include save warning"
    assert result.get("save_warning") == "Disk full", "Result should include save error message"

    print("✓ Test 2 passed: Pre-generation succeeds even if auto-save fails")


def test_no_autosave_on_pregen_failure():
    """Test that auto-save is not called if pre-generation fails."""
    print("\nTest 3: No auto-save when pre-generation fails")

    # Mock unified_stimulus controller
    unified_stimulus = Mock()

    # Mock failed pre-generation
    unified_stimulus.pre_generate_all_directions.return_value = {
        "success": False,
        "error": "Invalid parameters"
    }

    # Call handler
    result = _unified_stimulus_pregenerate_handler(unified_stimulus, {})

    # Verify pre-generation was called
    assert unified_stimulus.pre_generate_all_directions.called, "Pre-generation should be called"

    # Verify save was NOT called
    assert not unified_stimulus.save_library_to_disk.called, "Save should not be called after failed pre-generation"

    # Verify result shows failure
    assert result.get("success") == False, "Result should indicate failure"
    assert result.get("auto_saved") == False, "Result should indicate auto-save was not attempted"

    print("✓ Test 3 passed: No auto-save when pre-generation fails")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Auto-Save Logic")
    print("=" * 60)

    try:
        test_autosave_success()
        test_autosave_failure()
        test_no_autosave_on_pregen_failure()

        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import sys
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        import sys
        sys.exit(1)
