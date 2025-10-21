#!/usr/bin/env python3
"""
Comprehensive test for acquisition system flow.
Tests preview mode and ensures all components work together.
"""
import subprocess
import json
import time
import sys

def send_command(backend, command_dict, timeout=5.0):
    """Send command and wait for response."""
    command_json = json.dumps(command_dict)
    print(f"\n→ Sending: {command_dict['type']}")

    backend.stdin.write(command_json + "\n")
    backend.stdin.flush()

    # Wait for response
    start_time = time.time()
    while time.time() - start_time < timeout:
        if backend.poll() is not None:
            print(f"✗ Backend process exited with code {backend.returncode}")
            return None

        # Try to read a line (non-blocking would be better, but this works for testing)
        try:
            response_line = backend.stdout.readline()
            if response_line:
                print(f"← Received: {response_line.strip()[:200]}...")

                try:
                    response = json.loads(response_line)

                    # Check if this is the response to our command
                    if response.get("messageId") == command_dict.get("messageId"):
                        return response
                    else:
                        print(f"  (Got different message: {response.get('type')})")
                        # Continue waiting for our response
                except json.JSONDecodeError:
                    print(f"  (Non-JSON output: {response_line.strip()[:100]})")
        except:
            pass

        time.sleep(0.1)

    print(f"✗ Timeout waiting for response to {command_dict['type']}")
    return None

def test_acquisition_flow():
    """Test the full acquisition flow."""
    print("=" * 80)
    print("ACQUISITION FLOW TEST")
    print("=" * 80)

    # Start backend
    print("\n[1/8] Starting backend process...")
    backend = subprocess.Popen(
        [sys.executable, "src/main.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    print(f"  Backend PID: {backend.pid}")

    try:
        # Wait for zeromq_ready
        print("\n[2/8] Waiting for backend initialization...")
        line = backend.stdout.readline()
        if "zeromq_ready" in line:
            ready_msg = json.loads(line)
            print(f"  ✓ Backend ready on ports {ready_msg['health_port']}/{ready_msg['sync_port']}")
        else:
            print(f"  ✗ Unexpected message: {line}")
            return

        time.sleep(0.5)  # Give it a moment

        # Frontend ready handshake
        print("\n[3/8] Sending frontend_ready handshake...")
        response = send_command(backend, {
            "type": "frontend_ready",
            "messageId": "test-handshake"
        })
        if response and response.get("success"):
            print(f"  ✓ Handshake complete")
        else:
            print(f"  ✗ Handshake failed: {response}")
            return

        # Detect cameras
        print("\n[4/8] Detecting cameras...")
        response = send_command(backend, {
            "type": "detect_cameras",
            "messageId": "test-cameras",
            "force": False
        })
        if response and response.get("success"):
            cameras = response.get("cameras", [])
            print(f"  ✓ Found {len(cameras)} camera(s)")
            for cam in cameras:
                print(f"    - {cam['name']} (index {cam['index']})")

            if len(cameras) == 0:
                print("  ⚠ No cameras found - cannot test acquisition")
                return
        else:
            print(f"  ✗ Camera detection failed: {response}")
            return

        # Start camera acquisition
        print("\n[5/8] Starting camera acquisition...")
        camera_name = cameras[0]["name"]
        response = send_command(backend, {
            "type": "start_camera_acquisition",
            "messageId": "test-camera-start",
            "camera_name": camera_name
        })
        if response and response.get("success"):
            print(f"  ✓ Camera acquisition started")
        else:
            print(f"  ✗ Failed to start camera: {response}")
            return

        time.sleep(1.0)  # Let camera warm up

        # Check acquisition status
        print("\n[6/8] Checking acquisition status...")
        response = send_command(backend, {
            "type": "get_acquisition_status",
            "messageId": "test-status"
        })
        if response and response.get("success"):
            status = response.get("status", {})
            print(f"  ✓ Status retrieved:")
            print(f"    - Running: {status.get('is_running')}")
            print(f"    - Mode: {status.get('mode')}")
        else:
            print(f"  ✗ Failed to get status: {response}")

        # Pre-generate stimulus (required for preview)
        print("\n[7/8] Pre-generating stimulus...")
        response = send_command(backend, {
            "type": "pre_generate_stimulus",
            "messageId": "test-pregen",
            "directions": ["LR", "RL", "UD", "DU"]
        }, timeout=30.0)  # Longer timeout for generation
        if response and response.get("success"):
            print(f"  ✓ Stimulus pre-generated")
        else:
            print(f"  ✗ Failed to pre-generate: {response}")
            # Continue anyway - preview might auto-generate

        # Start preview mode
        print("\n[8/8] Starting preview mode...")
        response = send_command(backend, {
            "type": "start_preview",
            "messageId": "test-preview",
            "direction": "LR"
        })
        if response and response.get("success"):
            print(f"  ✓ Preview mode started!")
            print(f"\nSUCCESS! Acquisition system is working.")
        else:
            print(f"  ✗ Failed to start preview: {response}")
            return

        # Let it run for a bit
        print("\nLetting preview run for 3 seconds...")
        time.sleep(3.0)

        # Stop preview
        print("\nStopping preview...")
        response = send_command(backend, {
            "type": "stop_preview",
            "messageId": "test-stop-preview"
        })
        if response:
            print(f"  ✓ Preview stopped")

        # Stop camera
        print("\nStopping camera...")
        response = send_command(backend, {
            "type": "stop_camera_acquisition",
            "messageId": "test-stop-camera"
        })
        if response:
            print(f"  ✓ Camera stopped")

        print("\n" + "=" * 80)
        print("TEST COMPLETE - ALL SYSTEMS OPERATIONAL")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\nCleaning up...")
        backend.terminate()
        try:
            backend.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend.kill()
            backend.wait()
        print("Done")

if __name__ == "__main__":
    test_acquisition_flow()
