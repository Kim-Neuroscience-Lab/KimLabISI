#!/usr/bin/env python3
"""Diagnostic script to check if camera frames are being written to shared memory."""

import sys
import time
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import AppConfig
from parameters import ParameterManager
from camera.manager import CameraManager
from ipc.channels import MultiChannelIPC
from ipc.shared_memory import SharedMemoryService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Test camera frame streaming to shared memory."""
    logger.info("=== Camera Frame Diagnostic ===")

    # Load config
    config_path = Path(__file__).parent / "config" / "isi_parameters.json"
    config = AppConfig.from_file(str(config_path))

    # Create param manager
    param_manager = ParameterManager(
        config_file=config.parameters.file_path.name,
        config_dir=str(config.parameters.file_path.parent)
    )

    # Check development mode
    system_params = param_manager.get_parameter_group("system")
    dev_mode = system_params.get("development_mode", False)
    logger.info(f"Development mode: {dev_mode}")

    # Create IPC
    ipc = MultiChannelIPC(
        transport=config.ipc.transport,
        health_port=config.ipc.health_port,
        sync_port=config.ipc.sync_port
    )

    # Create shared memory
    shared_memory = SharedMemoryService(
        stream_name=config.shared_memory.stream_name,
        buffer_size_mb=config.shared_memory.buffer_size_mb,
        metadata_port=config.shared_memory.metadata_port,
        camera_metadata_port=config.shared_memory.camera_metadata_port,
        analysis_metadata_port=config.shared_memory.analysis_metadata_port
    )

    # Create camera
    camera = CameraManager(
        config=param_manager,
        ipc=ipc,
        shared_memory=shared_memory,
        synchronization_tracker=None
    )

    # Detect cameras
    logger.info("Detecting cameras...")
    cameras = camera.detect_cameras(force=True)
    logger.info(f"Found {len(cameras)} cameras")

    if not cameras:
        logger.error("No cameras found!")
        return

    # Open first camera
    logger.info(f"Opening camera: {cameras[0].name}")
    if not camera.open_camera(cameras[0].index):
        logger.error("Failed to open camera")
        return

    logger.info("Camera opened successfully")

    # Check hardware timestamp support
    ts_info = camera.validate_hardware_timestamps()
    logger.info(f"Timestamp validation: {ts_info}")

    # Start acquisition
    logger.info("Starting acquisition...")
    if not camera.start_acquisition():
        logger.error("Failed to start acquisition")
        return

    logger.info("Acquisition started - monitoring for 10 seconds...")

    # Monitor for 10 seconds
    start_time = time.time()
    frame_count = 0
    last_log_time = start_time

    while time.time() - start_time < 10:
        # Check if we're still streaming
        if camera.is_streaming:
            frame_info = camera.get_latest_frame_info()
            if frame_info.get("success"):
                frame_count += 1

                # Log every second
                if time.time() - last_log_time >= 1.0:
                    fps = frame_count / (time.time() - start_time)
                    logger.info(f"Frames captured: {frame_count}, FPS: {fps:.1f}")
                    logger.info(f"Latest frame: {frame_info}")
                    last_log_time = time.time()

        time.sleep(0.1)

    logger.info(f"Test complete - Total frames: {frame_count}")

    # Stop acquisition
    camera.stop_acquisition()
    logger.info("Acquisition stopped")

if __name__ == "__main__":
    main()
