#!/usr/bin/env python3
"""
Canonical ISI Control System Runner

This is the single, authoritative way to run the entire ISI Control System.
Modern best practices structure with unified root-level management.
"""

import sys
import os
import subprocess
from pathlib import Path


def run_application():
    """Run the complete ISI Control System (Electron app with Python backend)"""
    try:
        # We're now in the root directory with proper structure
        root_dir = Path(__file__).parent.absolute()
        os.chdir(root_dir)

        print("Starting ISI Control System...")

        # Run the complete Electron application with integrated backend using modern electron-vite
        cmd = ["npm", "run", "dev"]
        subprocess.run(cmd, cwd=root_dir, check=True)

    except subprocess.CalledProcessError as e:
        print(f"ISI Control System failed to start: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nISI Control System stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    run_application()