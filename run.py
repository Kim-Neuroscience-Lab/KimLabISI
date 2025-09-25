#!/usr/bin/env python3
"""
ISI Macroscope Control System - Unified Launcher (Cross-platform)
Starts both backend and frontend from the codebase root
"""

import os
import sys
import time
import signal
import subprocess
import argparse
from pathlib import Path
from typing import Optional
import platform

# ANSI color codes (disabled on Windows without proper terminal)
COLORS = {
    "RED": "\033[0;31m",
    "GREEN": "\033[0;32m",
    "YELLOW": "\033[1;33m",
    "BLUE": "\033[0;34m",
    "NC": "\033[0m",  # No Color
}

# Disable colors on Windows if not in a proper terminal
if platform.system() == "Windows" and not os.environ.get("WT_SESSION"):
    COLORS = {key: "" for key in COLORS}


class ISIMacroscopeLauncher:
    """Unified launcher for ISI Macroscope Control System"""

    def __init__(self, mode: str = "production", verbose: bool = False):
        self.mode = mode
        self.verbose = verbose
        self.root_dir = Path(__file__).parent.resolve()
        self.backend_dir = self.root_dir / "backend"
        self.frontend_dir = self.root_dir / "frontend"
        self.log_dir = self.root_dir / "logs"

        self.backend_process: Optional[subprocess.Popen] = None
        self.frontend_process: Optional[subprocess.Popen] = None

        # Create log directory
        self.log_dir.mkdir(exist_ok=True)

    def print_header(self):
        """Print application header"""
        print(
            f"{COLORS['BLUE']}╔════════════════════════════════════════════╗{COLORS['NC']}"
        )
        print(
            f"{COLORS['BLUE']}║   ISI Macroscope Control System Launcher   ║{COLORS['NC']}"
        )
        print(
            f"{COLORS['BLUE']}╚════════════════════════════════════════════╝{COLORS['NC']}"
        )
        print()
        print(f"{COLORS['GREEN']}Mode: {self.mode}{COLORS['NC']}")
        print()

    def check_prerequisites(self) -> bool:
        """Check if all required tools are installed"""
        print(f"{COLORS['YELLOW']}Checking prerequisites...{COLORS['NC']}")

        checks = [
            ("Python 3", self._check_python),
            ("Node.js", self._check_node),
            ("Poetry", self._check_poetry),
        ]

        all_passed = True
        for name, check_func in checks:
            if check_func():
                print(f"{COLORS['GREEN']}✓ {name} found{COLORS['NC']}")
            else:
                print(f"{COLORS['RED']}✗ {name} is not installed{COLORS['NC']}")
                all_passed = False

        return all_passed

    def _check_python(self) -> bool:
        """Check if Python 3 is available"""
        try:
            result = subprocess.run(
                [sys.executable, "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0 and "Python 3" in result.stdout
        except Exception:
            return False

    def _check_node(self) -> bool:
        """Check if Node.js is available"""
        try:
            result = subprocess.run(
                ["node", "--version"], capture_output=True, text=True, check=False
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def _check_poetry(self) -> bool:
        """Check if Poetry is available"""
        try:
            result = subprocess.run(
                ["poetry", "--version"], capture_output=True, text=True, check=False
            )
            return result.returncode == 0
        except FileNotFoundError:
            print("  Install with: pip install poetry")
            return False

    def start_backend(self) -> bool:
        """Start the Python backend"""
        print()
        print(f"{COLORS['BLUE']}Starting Backend...{COLORS['NC']}")

        # Check if virtual environment exists
        venv_path = self.backend_dir / ".venv"
        if not venv_path.exists():
            print(f"{COLORS['YELLOW']}Installing backend dependencies...{COLORS['NC']}")
            try:
                subprocess.run(
                    ["poetry", "install"],
                    cwd=self.backend_dir,
                    check=True,
                    capture_output=not self.verbose,
                )
            except subprocess.CalledProcessError as e:
                print(
                    f"{COLORS['RED']}Failed to install backend dependencies{COLORS['NC']}"
                )
                return False

        # Prepare backend command
        cmd = ["poetry", "run", "python", "src/isi_control/main.py"]
        if self.mode == "development":
            cmd.append("--dev")
            print(
                f"{COLORS['GREEN']}Starting backend in development mode...{COLORS['NC']}"
            )
        else:
            print(
                f"{COLORS['GREEN']}Starting backend in production mode...{COLORS['NC']}"
            )

        # Start backend process
        try:
            # Set up environment with PYTHONPATH
            env = os.environ.copy()
            env["PYTHONPATH"] = "src"

            if self.verbose:
                self.backend_process = subprocess.Popen(
                    cmd, cwd=self.backend_dir, env=env
                )
            else:
                log_file = open(self.log_dir / "backend.log", "w", encoding="utf-8")
                self.backend_process = subprocess.Popen(
                    cmd,
                    cwd=self.backend_dir,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    env=env,
                )

            print(
                f"{COLORS['GREEN']}✓ Backend started (PID:"
                + "{self.backend_process.pid}){COLORS['NC']}"
            )
            return True

        except Exception as e:
            print(f"{COLORS['RED']}✗ Failed to start backend: {e}{COLORS['NC']}")
            return False

    def start_frontend(self) -> bool:
        """Start the Electron frontend"""
        print()
        print(f"{COLORS['BLUE']}Starting Frontend...{COLORS['NC']}")

        # Check if node_modules exists
        node_modules = self.frontend_dir / "node_modules"
        if not node_modules.exists():
            print(
                f"{COLORS['YELLOW']}Installing frontend dependencies...{COLORS['NC']}"
            )
            try:
                subprocess.run(
                    ["npm", "install"],
                    cwd=self.frontend_dir,
                    check=True,
                    capture_output=not self.verbose,
                )
            except subprocess.CalledProcessError as e:
                print(
                    f"{COLORS['RED']}Failed to install frontend dependencies{COLORS['NC']}"
                )
                return False

        # Prepare frontend command
        if self.mode == "development":
            cmd = ["npm", "run", "dev"]
            print(
                f"{COLORS['GREEN']}Starting frontend in development mode...{COLORS['NC']}"
            )
        else:
            cmd = ["npm", "start"]
            print(
                f"{COLORS['GREEN']}Starting frontend in production mode...{COLORS['NC']}"
            )

        # Start frontend process
        try:
            if self.verbose:
                self.frontend_process = subprocess.Popen(cmd, cwd=self.frontend_dir)
            else:
                log_file = open(self.log_dir / "frontend.log", "w")
                self.frontend_process = subprocess.Popen(
                    cmd,
                    cwd=self.frontend_dir,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                )

            print(
                f"{COLORS['GREEN']}✓ Frontend started (PID:"
                + "{self.frontend_process.pid}){COLORS['NC']}"
            )
            return True

        except Exception as e:
            print(f"{COLORS['RED']}✗ Failed to start frontend: {e}{COLORS['NC']}")
            return False

    def wait_for_backend(self, timeout: int = 10) -> bool:
        """Wait for backend to initialize"""
        print(f"{COLORS['YELLOW']}Waiting for backend to initialize...{COLORS['NC']}")

        for _ in range(timeout):
            if self.backend_process and self.backend_process.poll() is None:
                # Process is still running
                time.sleep(1)
            else:
                # Process has terminated
                print(f"{COLORS['RED']}✗ Backend failed to start{COLORS['NC']}")
                print(f"Check logs at: {self.log_dir / 'backend.log'}")
                return False

        # Check one more time if process is running
        if self.backend_process and self.backend_process.poll() is None:
            return True
        else:
            print(f"{COLORS['RED']}✗ Backend failed to start{COLORS['NC']}")
            return False

    def print_status(self):
        """Print system status"""
        print()
        print(
            f"{COLORS['BLUE']}╔════════════════════════════════════════════╗{COLORS['NC']}"
        )
        print(
            f"{COLORS['BLUE']}║         System Successfully Started         ║{COLORS['NC']}"
        )
        print(
            f"{COLORS['BLUE']}╚════════════════════════════════════════════╝{COLORS['NC']}"
        )
        print()

        if self.backend_process:
            print(
                f"{COLORS['GREEN']}Backend PID:  {self.backend_process.pid}{COLORS['NC']}"
            )
        if self.frontend_process:
            print(
                f"{COLORS['GREEN']}Frontend PID: {self.frontend_process.pid}{COLORS['NC']}"
            )

        print()

        if not self.verbose:
            print("Logs:")
            print(f"  Backend:  {self.log_dir / 'backend.log'}")
            print(f"  Frontend: {self.log_dir / 'frontend.log'}")
            print()

        print(f"{COLORS['YELLOW']}Press Ctrl+C to stop all services{COLORS['NC']}")

    def cleanup(self):
        """Cleanup processes on exit"""
        print()
        print(f"{COLORS['YELLOW']}Shutting down...{COLORS['NC']}")

        if self.backend_process:
            print(
                f"{COLORS['YELLOW']}Stopping backend (PID:"
                + "{self.backend_process.pid})...{COLORS['NC']}"
            )
            try:
                self.backend_process.terminate()
                self.backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.backend_process.kill()

        if self.frontend_process:
            print(
                f"{COLORS['YELLOW']}Stopping frontend (PID:"
                + "{self.frontend_process.pid})...{COLORS['NC']}"
            )
            try:
                self.frontend_process.terminate()
                self.frontend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.frontend_process.kill()

        print(f"{COLORS['GREEN']}Shutdown complete{COLORS['NC']}")

    def run(self):
        """Main run method"""
        self.print_header()

        # Check prerequisites
        if not self.check_prerequisites():
            print(f"{COLORS['RED']}Please install missing prerequisites{COLORS['NC']}")
            sys.exit(1)

        # Start backend
        if not self.start_backend():
            self.cleanup()
            sys.exit(1)

        # Wait for backend
        if not self.wait_for_backend():
            self.cleanup()
            sys.exit(1)

        # Start frontend
        if not self.start_frontend():
            self.cleanup()
            sys.exit(1)

        # Print status
        self.print_status()

        # Wait for processes
        try:
            if self.backend_process:
                self.backend_process.wait()
            if self.frontend_process:
                self.frontend_process.wait()
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="ISI Macroscope Control System Launcher"
    )
    parser.add_argument("--dev", action="store_true", help="Run in development mode")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")

    args = parser.parse_args()

    mode = "development" if args.dev else "production"

    launcher = ISIMacroscopeLauncher(mode=mode, verbose=args.verbose)

    # Handle signals
    signal.signal(signal.SIGINT, lambda s, f: launcher.cleanup())
    signal.signal(signal.SIGTERM, lambda s, f: launcher.cleanup())

    launcher.run()


if __name__ == "__main__":
    main()
