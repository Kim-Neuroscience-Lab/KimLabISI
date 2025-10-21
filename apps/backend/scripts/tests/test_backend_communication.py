#!/usr/bin/env python3
"""
Test script to verify backend is running and responding to commands.
"""
import subprocess
import json
import time
import sys

def test_backend():
    """Start backend and send test command."""
    print("Starting backend process...")

    # Start backend with stdin/stdout pipes
    backend = subprocess.Popen(
        [sys.executable, "src/main.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    print(f"Backend PID: {backend.pid}")

    try:
        # Wait for zeromq_ready message
        print("Waiting for zeromq_ready...")
        line = backend.stdout.readline()
        print(f"Received: {line.strip()}")

        if "zeromq_ready" in line:
            print("✓ Backend initialized successfully")

            # Give it a moment to fully initialize
            time.sleep(0.5)

            # Send a test command
            print("\nSending test command (detect_cameras)...")
            command = json.dumps({
                "type": "detect_cameras",
                "messageId": "test-1",
                "force": False
            })
            backend.stdin.write(command + "\n")
            backend.stdin.flush()

            # Wait for response
            print("Waiting for response...")
            response_line = backend.stdout.readline()
            print(f"Received: {response_line.strip()}")

            # Parse response
            try:
                response = json.loads(response_line)
                if response.get("success"):
                    print("✓ Backend is responding to commands!")
                    print(f"  Cameras: {response.get('cameras', [])}")
                else:
                    print(f"✗ Command failed: {response.get('error')}")
            except json.JSONDecodeError as e:
                print(f"✗ Invalid JSON response: {response_line}")
                print(f"  Error: {e}")

            # Try frontend_ready command
            print("\nSending frontend_ready command...")
            frontend_ready = json.dumps({
                "type": "frontend_ready",
                "messageId": "test-2"
            })
            backend.stdin.write(frontend_ready + "\n")
            backend.stdin.flush()

            print("Waiting for response...")
            time.sleep(0.5)
            response_line2 = backend.stdout.readline()
            print(f"Received: {response_line2.strip()}")

            # Check if process is still running
            time.sleep(0.5)
            if backend.poll() is None:
                print("\n✓ Backend process is still running")
            else:
                print(f"\n✗ Backend process exited with code {backend.returncode}")

        else:
            print("✗ Did not receive zeromq_ready message")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        # Cleanup
        print("\nCleaning up...")
        backend.terminate()
        backend.wait(timeout=5)
        print("Done")

if __name__ == "__main__":
    test_backend()
