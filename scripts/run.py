#!/usr/bin/env python3
"""
Canonical ISI Control System Backend Runner

This is the single, authoritative way to run the ISI backend.
No other run methods should exist or be used.
"""

import sys
import os
import subprocess
from pathlib import Path


def find_project_root():
    """Find the project root directory containing pyproject.toml"""
    current = Path(__file__).parent.absolute()
    while current != current.parent:
        if (current / "apps" / "pyproject.toml").exists():
            return current / "apps"
        current = current.parent
    raise RuntimeError("Could not find project root with pyproject.toml")


def setup_environment():
    """Setup the Python environment for running the backend"""
    backend_dir = find_project_root()
    os.chdir(backend_dir)

    # Add backend src to Python path
    src_path = backend_dir / "backend" / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    # Set environment variable for subprocess calls
    os.environ["PYTHONPATH"] = str(src_path)


def run_backend():
    """Run the ISI backend using poetry"""
    try:
        # Change to backend directory and run with poetry
        setup_environment()
        backend_dir = find_project_root()

        # Use poetry to run the backend in the proper environment
        cmd = ["poetry", "run", "python", "src/isi_control/main.py"]
        subprocess.run(cmd, cwd=backend_dir, check=True)

    except subprocess.CalledProcessError as e:
        print(f"Backend failed to start: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nBackend stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    run_backend()