#!/usr/bin/env python3
"""Test script for Phase 1 infrastructure components.

This script tests:
1. Loading config from isi_parameters.json
2. Creating MultiChannelIPC instance
3. Creating SharedMemoryService instance
4. Verifying all components initialize correctly
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import our new modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import AppConfig
from ipc.channels import MultiChannelIPC, build_multi_channel_ipc
from ipc.shared_memory import SharedMemoryService


def test_config_loading():
    """Test loading configuration from JSON file."""
    print("\n=== Test 1: Loading Configuration ===")

    try:
        # Use the actual config file path
        config_path = Path(__file__).resolve().parents[1] / "config" / "isi_parameters.json"
        print(f"Loading config from: {config_path}")

        config = AppConfig.from_file(str(config_path))
        print(f"✓ Config loaded successfully")
        print(f"  - IPC transport: {config.ipc.transport}")
        print(f"  - Health port: {config.ipc.health_port}")
        print(f"  - Sync port: {config.ipc.sync_port}")
        print(f"  - Shared memory buffer: {config.shared_memory.buffer_size_mb}MB")
        print(f"  - Camera: {config.camera.selected_camera}")
        print(f"  - Session: {config.session.session_name}")

        return config
    except Exception as e:
        print(f"✗ Failed to load config: {e}")
        raise


def test_multi_channel_ipc(config: AppConfig):
    """Test creating MultiChannelIPC instance."""
    print("\n=== Test 2: Creating MultiChannelIPC ===")

    try:
        # Create IPC using factory function
        ipc = build_multi_channel_ipc(
            transport=config.ipc.transport,
            health_port=config.ipc.health_port,
            sync_port=config.ipc.sync_port
        )
        print(f"✓ MultiChannelIPC created successfully")
        print(f"  - Channels initialized: {len(ipc.channels)}")
        for channel_type, channel_info in ipc.channels.items():
            print(f"    • {channel_type.value}: {channel_info.get('address')}")

        # Clean up
        ipc.cleanup()
        print(f"✓ MultiChannelIPC cleaned up successfully")

        return True
    except Exception as e:
        print(f"✗ Failed to create MultiChannelIPC: {e}")
        import traceback
        traceback.print_exc()
        raise


def test_shared_memory_service(config: AppConfig):
    """Test creating SharedMemoryService instance."""
    print("\n=== Test 3: Creating SharedMemoryService ===")

    try:
        # Create SharedMemoryService
        shared_memory = SharedMemoryService(
            stream_name=config.shared_memory.stream_name,
            buffer_size_mb=config.shared_memory.buffer_size_mb,
            metadata_port=config.shared_memory.metadata_port,
            camera_metadata_port=config.shared_memory.camera_metadata_port
        )
        print(f"✓ SharedMemoryService created successfully")
        print(f"  - Stream name: {shared_memory._stream_name}")
        print(f"  - Buffer size: {shared_memory._buffer_size_mb}MB")
        print(f"  - Metadata port: {shared_memory._metadata_port}")
        print(f"  - Camera metadata port: {shared_memory._camera_metadata_port}")

        # Initialize the stream to verify it works
        print(f"  - Initializing shared memory stream...")
        stream = shared_memory.stream  # This triggers initialization
        print(f"✓ Shared memory stream initialized successfully")

        # Clean up
        shared_memory.cleanup()
        print(f"✓ SharedMemoryService cleaned up successfully")

        return True
    except Exception as e:
        print(f"✗ Failed to create SharedMemoryService: {e}")
        import traceback
        traceback.print_exc()
        raise


def test_constructor_injection():
    """Test that all components use constructor injection (no service locator)."""
    print("\n=== Test 4: Verifying Constructor Injection ===")

    try:
        # Create components with explicit parameters
        ipc = MultiChannelIPC(
            transport="tcp",
            health_port=5555,
            sync_port=5558
        )
        print(f"✓ MultiChannelIPC accepts explicit constructor parameters")

        shared_memory = SharedMemoryService(
            stream_name="test_stream",
            buffer_size_mb=50,
            metadata_port=5557,
            camera_metadata_port=5559
        )
        print(f"✓ SharedMemoryService accepts explicit constructor parameters")

        # Verify no service_locator imports
        import inspect

        ipc_source = inspect.getsource(MultiChannelIPC.__init__)
        if "service_locator" in ipc_source.lower():
            raise ValueError("MultiChannelIPC still has service_locator references!")
        print(f"✓ MultiChannelIPC has no service_locator references")

        shm_source = inspect.getsource(SharedMemoryService.__init__)
        if "service_locator" in shm_source.lower():
            raise ValueError("SharedMemoryService still has service_locator references!")
        print(f"✓ SharedMemoryService has no service_locator references")

        # Clean up
        ipc.cleanup()
        shared_memory.cleanup()

        return True
    except Exception as e:
        print(f"✗ Constructor injection test failed: {e}")
        import traceback
        traceback.print_exc()
        raise


def main():
    """Run all Phase 1 tests."""
    print("=" * 60)
    print("Phase 1 Infrastructure Tests")
    print("=" * 60)

    try:
        # Test 1: Config loading
        config = test_config_loading()

        # Test 2: MultiChannelIPC
        test_multi_channel_ipc(config)

        # Test 3: SharedMemoryService
        test_shared_memory_service(config)

        # Test 4: Constructor injection
        test_constructor_injection()

        # Success!
        print("\n" + "=" * 60)
        print("✓ ALL PHASE 1 TESTS PASSED!")
        print("=" * 60)
        print("\nPhase 1 infrastructure is ready for use:")
        print("  ✓ config.py - Configuration dataclasses with to_dict() and from_file()")
        print("  ✓ ipc/channels.py - MultiChannelIPC with constructor injection")
        print("  ✓ ipc/shared_memory.py - SharedMemoryService with constructor injection")
        print("\nNext steps:")
        print("  - Phase 2: Camera System")
        print("  - Phase 3: Stimulus System")
        print("  - Phase 4: Acquisition System")
        print("  - Phase 5: Analysis System")
        print("  - Phase 6: Main Application")

        return 0

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"✗ PHASE 1 TESTS FAILED")
        print("=" * 60)
        print(f"\nError: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
