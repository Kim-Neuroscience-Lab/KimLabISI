"""Camera hardware detection utilities.

Pure functions for camera enumeration and platform-specific detection.
No global state, no service dependencies.
"""

import platform
import subprocess
import json
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


def run_system_command(command: List[str], timeout: int = 10) -> Tuple[bool, str, str]:
    """Run a system command and return success status, stdout, and stderr.

    Args:
        command: Command and arguments as list
        timeout: Command timeout in seconds

    Returns:
        (success, stdout, stderr)
    """
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout
        )
        return (result.returncode == 0, result.stdout, result.stderr)
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out: {' '.join(command)}")
        return (False, "", "Command timed out")
    except Exception as e:
        logger.error(f"Command failed: {' '.join(command)}: {e}")
        return (False, "", str(e))


def get_available_camera_indices() -> List[int]:
    """Get list of available camera indices using platform-specific methods.

    Returns:
        List of camera indices that are likely to be available
    """
    available_indices = []

    try:
        system = platform.system()

        if system == "Darwin":  # macOS
            # Use system_profiler to get actual camera devices
            # OPTIMIZATION: Reduced timeout from 5s to 2s for faster startup
            success, stdout, stderr = run_system_command(
                ["system_profiler", "SPCameraDataType", "-json"], timeout=2
            )

            if success:
                try:
                    data = json.loads(stdout)
                    cameras = data.get("SPCameraDataType", [])
                    # Add index for each detected camera
                    for i, camera in enumerate(cameras):
                        available_indices.append(i)
                        logger.debug(
                            f"Found camera via system_profiler: {camera.get('_name', 'Unknown')}"
                        )
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse system_profiler output: {e}")
                    available_indices = [0]  # Fallback
            else:
                # Fallback: assume index 0 exists if we can't enumerate
                available_indices = [0]

        elif system == "Linux":
            # Check /dev/video* devices
            try:
                success, stdout, stderr = run_system_command(
                    ["ls", "/dev/video*"], timeout=5
                )
                if success:
                    video_devices = stdout.strip().split("\n")
                    for device in video_devices:
                        if device.startswith("/dev/video"):
                            try:
                                index = int(device.split("video")[1])
                                available_indices.append(index)
                            except (ValueError, IndexError):
                                continue
                else:
                    available_indices = [0]  # Fallback
            except Exception as e:
                logger.debug(f"Failed to enumerate Linux video devices: {e}")
                available_indices = [0]  # Fallback

        else:  # Windows or other
            # For Windows/other systems, use conservative approach
            available_indices = [0]  # Most systems have at least one camera at index 0

    except Exception as e:
        logger.debug(f"Failed to enumerate cameras via system methods: {e}")
        # Fallback to checking just index 0
        available_indices = [0]

    logger.debug(f"Available camera indices: {available_indices}")
    return available_indices


def get_system_camera_names() -> List[Tuple[int, str]]:
    """Get REAL camera names from the operating system.

    Returns list of (index, name) tuples with actual hardware camera names.
    This replaces the deprecated generate_camera_name() function.

    Returns:
        List of (index, name) tuples where name is the REAL hardware name
    """
    camera_names = []

    try:
        system = platform.system()

        if system == "Darwin":  # macOS
            # Use system_profiler to get REAL camera names
            success, stdout, stderr = run_system_command(
                ["system_profiler", "SPCameraDataType", "-json"], timeout=2
            )

            if success:
                try:
                    data = json.loads(stdout)
                    cameras = data.get("SPCameraDataType", [])
                    for i, camera in enumerate(cameras):
                        real_name = camera.get("_name", f"Camera {i}")
                        camera_names.append((i, real_name))
                        logger.debug(f"Found camera {i}: {real_name}")
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse system_profiler output: {e}")
                    # Fallback: generic name
                    camera_names.append((0, "Camera 0"))
            else:
                # Fallback: generic name
                camera_names.append((0, "Camera 0"))

        elif system == "Linux":
            # On Linux, use v4l2-ctl to get camera names (if available)
            # Otherwise fall back to generic names
            try:
                success, stdout, stderr = run_system_command(
                    ["ls", "/dev/video*"], timeout=5
                )
                if success:
                    video_devices = stdout.strip().split("\n")
                    for device in video_devices:
                        if device.startswith("/dev/video"):
                            try:
                                index = int(device.split("video")[1])
                                # Try to get real name with v4l2-ctl
                                v4l_success, v4l_stdout, _ = run_system_command(
                                    ["v4l2-ctl", "--device", device, "--info"], timeout=2
                                )
                                if v4l_success and "Card type" in v4l_stdout:
                                    # Extract camera name from v4l2-ctl output
                                    for line in v4l_stdout.split("\n"):
                                        if "Card type" in line:
                                            name = line.split(":", 1)[1].strip()
                                            camera_names.append((index, name))
                                            break
                                else:
                                    # Fallback to generic name
                                    camera_names.append((index, f"Camera {index}"))
                            except (ValueError, IndexError):
                                continue
                else:
                    camera_names.append((0, "Camera 0"))
            except Exception as e:
                logger.debug(f"Failed to enumerate Linux cameras: {e}")
                camera_names.append((0, "Camera 0"))

        else:  # Windows or other
            # Windows: could use WMI or DirectShow, but for now use generic name
            camera_names.append((0, "Camera 0"))

    except Exception as e:
        logger.error(f"Failed to get system camera names: {e}")
        # Fallback to generic name
        camera_names.append((0, "Camera 0"))

    logger.debug(f"System camera names: {camera_names}")
    return camera_names
