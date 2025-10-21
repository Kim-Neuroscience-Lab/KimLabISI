#!/usr/bin/env python3
"""Quick test to verify camera detection fix works.

This script verifies that:
1. Camera detection works without TypeError
2. Camera can be opened successfully
3. Test frame can be captured

Run this before restarting the full application to verify the fix.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from camera.manager import CameraManager
from config import AppConfig
from ipc.channels import MultiChannelIPC
from ipc.shared_memory import SharedMemoryService


def test_camera_detection_fix():
    """Test that camera detection works with correct parameters."""
    print("=" * 70)
    print("CAMERA DETECTION FIX VERIFICATION")
    print("=" * 70)
    print()

    # Load config from file (same as main.py does)
    print("1. Loading configuration from isi_parameters.json...")
    from pathlib import Path
    config_path = Path(__file__).parent / "config" / "isi_parameters.json"

    if not config_path.exists():
        print(f"   ! Config file not found: {config_path}")
        print("   Loading default configuration...")
        config = AppConfig.default()
    else:
        config = AppConfig.from_file(str(config_path))
        print(f"   ✓ Config loaded from {config_path}")
    print()

    # Create minimal IPC (not used in this test, but required by CameraManager)
    print("2. Creating IPC service (minimal)...")
    ipc = MultiChannelIPC(config.ipc.health_port, config.ipc.sync_port)
    print("   ✓ IPC service created")
    print()

    # Create minimal shared memory service (not used in this test)
    print("3. Creating shared memory service (minimal)...")
    shared_memory = SharedMemoryService(
        config.shared_memory.metadata_port,
        config.shared_memory.camera_metadata_port,
        config.shared_memory.analysis_metadata_port
    )
    print("   ✓ Shared memory service created")
    print()

    # Create camera manager
    print("4. Creating camera manager...")
    camera = CameraManager(
        config=config.camera,
        ipc=ipc,
        shared_memory=shared_memory
    )
    print("   ✓ Camera manager created")
    print()

    # Test 1: Camera detection with CORRECT parameters (no keep_first_open)
    print("5. Testing camera detection with FIXED parameters...")
    print("   Calling: detect_cameras(force=True)")
    print()

    try:
        detected_cameras = camera.detect_cameras(force=True)
        print(f"   ✓ SUCCESS: Detected {len(detected_cameras)} camera(s)")

        for cam in detected_cameras:
            print(f"      - {cam.name} (index={cam.index}, available={cam.is_available})")
            if cam.properties:
                print(f"        Resolution: {cam.properties.get('width')}x{cam.properties.get('height')}")
                print(f"        FPS: {cam.properties.get('fps')}")
        print()

    except TypeError as e:
        print(f"   ✗ FAILED: TypeError - {e}")
        print("   This means the fix didn't work!")
        return False
    except Exception as e:
        print(f"   ✗ FAILED: {type(e).__name__} - {e}")
        return False

    # Test 2: Verify we can open a camera
    if detected_cameras:
        print("6. Testing camera opening...")
        first_cam = detected_cameras[0]

        try:
            success = camera.open_camera(first_cam.index)
            if success:
                print(f"   ✓ SUCCESS: Opened '{first_cam.name}'")
                print()
            else:
                print(f"   ✗ FAILED: Could not open '{first_cam.name}'")
                return False
        except Exception as e:
            print(f"   ✗ FAILED: {type(e).__name__} - {e}")
            return False

        # Test 3: Verify we can capture a frame
        print("7. Testing frame capture...")
        try:
            frame = camera.capture_frame()
            if frame is not None:
                print(f"   ✓ SUCCESS: Captured frame {frame.shape}")
                print()
            else:
                print("   ✗ FAILED: capture_frame() returned None")
                return False
        except Exception as e:
            print(f"   ✗ FAILED: {type(e).__name__} - {e}")
            return False

        # Cleanup
        print("8. Cleanup...")
        camera.close_camera()
        print("   ✓ Camera closed")
        print()

    else:
        print("6. SKIPPING: No cameras detected (cannot test opening/capture)")
        print()

    # Summary
    print("=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)
    print()
    print("✓ Camera detection works (no TypeError)")
    if detected_cameras:
        print("✓ Camera can be opened")
        print("✓ Frames can be captured")
        print()
        print("STATUS: FIX SUCCESSFUL - Camera system should work in full application")
    else:
        print()
        print("STATUS: No cameras available (but fix is working)")
        print("        The TypeError is fixed, but no cameras detected on this system")
    print()

    return True


if __name__ == "__main__":
    try:
        success = test_camera_detection_fix()
        sys.exit(0 if success else 1)
    except Exception as e:
        print()
        print("=" * 70)
        print("UNEXPECTED ERROR")
        print("=" * 70)
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
