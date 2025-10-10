#!/usr/bin/env python3
"""Test script for Phase 2 - Camera System.

Tests:
1. Load configuration from JSON file
2. Create IPC and SharedMemory services
3. Create CameraManager with injected dependencies
4. Test camera detection
5. Verify no service_locator imports
6. Verify no global singletons
"""

import sys
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent
sys.path.insert(0, str(src_dir))

import logging

logger = logging.getLogger(__name__)


def test_phase2():
    """Test Phase 2 - Camera System implementation."""
    logger.info("=" * 80)
    logger.info("PHASE 2 TEST: Camera System")
    logger.info("=" * 80)

    # Step 1: Load configuration
    logger.info("\n[1/6] Loading configuration from JSON file...")
    from config import AppConfig

    config_path = src_dir.parent / "config" / "isi_parameters.json"
    logger.info(f"Config path: {config_path}")

    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        return False

    config = AppConfig.from_file(str(config_path))
    logger.info(f"✓ Configuration loaded successfully")
    logger.info(f"  Camera config: {config.camera.selected_camera}")
    logger.info(f"  IPC transport: {config.ipc.transport}")
    logger.info(f"  Shared memory: {config.shared_memory.stream_name}")

    # Step 2: Create IPC service
    logger.info("\n[2/6] Creating MultiChannelIPC service...")
    from ipc.channels import MultiChannelIPC

    ipc = MultiChannelIPC(
        transport=config.ipc.transport,
        health_port=config.ipc.health_port,
        sync_port=config.ipc.sync_port,
    )
    logger.info("✓ MultiChannelIPC created (constructor injection)")

    # Step 3: Create SharedMemory service
    logger.info("\n[3/6] Creating SharedMemoryService...")
    from ipc.shared_memory import SharedMemoryService

    shared_memory = SharedMemoryService(
        stream_name=config.shared_memory.stream_name,
        buffer_size_mb=config.shared_memory.buffer_size_mb,
        metadata_port=config.shared_memory.metadata_port,
        camera_metadata_port=config.shared_memory.camera_metadata_port,
    )
    logger.info("✓ SharedMemoryService created (constructor injection)")

    # Step 4: Create CameraManager with injected dependencies
    logger.info("\n[4/6] Creating CameraManager with injected dependencies...")
    from camera.manager import CameraManager

    camera_manager = CameraManager(
        config=config.camera,
        ipc=ipc,
        shared_memory=shared_memory,
        synchronization_tracker=None,  # Will be added in Phase 4
        camera_triggered_stimulus=None,  # Will be added in Phase 4
    )
    logger.info("✓ CameraManager created with constructor injection")
    logger.info("  Dependencies injected:")
    logger.info(f"    - config: {type(camera_manager.config).__name__}")
    logger.info(f"    - ipc: {type(camera_manager.ipc).__name__}")
    logger.info(
        f"    - shared_memory: {type(camera_manager.shared_memory).__name__}"
    )

    # Step 5: Test camera detection
    logger.info("\n[5/6] Testing camera detection...")
    cameras = camera_manager.detect_cameras()
    logger.info(f"✓ Camera detection completed")
    logger.info(f"  Found {len(cameras)} cameras:")
    for cam in cameras:
        logger.info(f"    - {cam.name} (index {cam.index})")
        logger.info(f"      Available: {cam.is_available}")
        if cam.properties:
            logger.info(
                f"      Resolution: {cam.properties.get('width')}x{cam.properties.get('height')}"
            )
            logger.info(f"      FPS: {cam.properties.get('fps')}")

    # Step 6: Verify architecture
    logger.info("\n[6/6] Verifying clean architecture...")

    # Check for service_locator imports (ignore comments)
    import inspect
    import re

    camera_manager_source = inspect.getsource(CameraManager)
    # Remove comments from source
    lines = camera_manager_source.split('\n')
    code_lines = []
    for line in lines:
        # Remove inline comments
        code_part = line.split('#')[0]
        code_lines.append(code_part)
    code_without_comments = '\n'.join(code_lines)

    if "service_locator" in code_without_comments.lower():
        logger.error("✗ FAILED: Found service_locator import in CameraManager code!")
        return False
    logger.info("✓ No service_locator imports in CameraManager")

    # Check for global singleton
    from camera import manager as camera_module

    if hasattr(camera_module, "camera_manager"):
        logger.error("✗ FAILED: Found global camera_manager singleton!")
        return False
    logger.info("✓ No global camera_manager singleton")

    # Verify constructor injection
    init_signature = inspect.signature(CameraManager.__init__)
    params = list(init_signature.parameters.keys())
    required_params = ["self", "config", "ipc", "shared_memory"]
    for param in required_params:
        if param not in params:
            logger.error(
                f"✗ FAILED: Missing required parameter '{param}' in __init__"
            )
            return False
    logger.info(f"✓ Constructor has required parameters: {required_params}")

    # Success!
    logger.info("\n" + "=" * 80)
    logger.info("✓ PHASE 2 TEST PASSED!")
    logger.info("=" * 80)
    logger.info("\nSummary:")
    logger.info("  ✓ Configuration loading works")
    logger.info("  ✓ IPC service created with constructor injection")
    logger.info("  ✓ SharedMemory service created with constructor injection")
    logger.info("  ✓ CameraManager created with constructor injection")
    logger.info(f"  ✓ Camera detection works ({len(cameras)} cameras found)")
    logger.info("  ✓ No service_locator imports")
    logger.info("  ✓ No global singletons")
    logger.info("  ✓ Clean dependency injection pattern")
    logger.info("\nPhase 2 implementation complete! Ready for Phase 3.")

    return True


if __name__ == "__main__":
    from logging_config import configure_logging
    configure_logging(level=logging.DEBUG)  # Verbose for tests

    try:
        success = test_phase2()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"\n✗ TEST FAILED WITH EXCEPTION: {e}", exc_info=True)
        sys.exit(1)
